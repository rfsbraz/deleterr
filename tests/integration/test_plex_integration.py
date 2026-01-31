# encoding: utf-8
"""
Integration tests using real PlexAPI.

These tests demonstrate the pattern for testing with a real Plex server,
using the PlexTestHelper and pre-seeded media files.
"""

import pytest

pytestmark = pytest.mark.integration


class TestPlexServerConnection:
    """Test basic Plex server connectivity."""

    def test_server_connection(self, plex_server):
        """Verify we can connect to the Plex server."""
        assert plex_server is not None
        # machineIdentifier is available on all Plex servers
        assert plex_server.machineIdentifier is not None

    def test_movies_library_exists(self, plex_movies_library):
        """Verify Movies library exists."""
        assert plex_movies_library is not None
        assert plex_movies_library.title == "Movies"
        assert plex_movies_library.type == "movie"

    def test_tvshows_library_exists(self, plex_tvshows_library):
        """Verify TV Shows library exists."""
        assert plex_tvshows_library is not None
        assert plex_tvshows_library.title == "TV Shows"
        assert plex_tvshows_library.type == "show"


class TestPlexLibraryContent:
    """Test that pre-seeded content is available."""

    def test_movies_are_seeded(self, plex_test_helper):
        """Verify movies were seeded during bootstrap."""
        movies = plex_test_helper.get_all_movies()
        assert len(movies) > 0, "No movies found in library"

        # Check for expected movies from bootstrap (matching JustWatch cache)
        movie_titles = [m.title for m in movies]
        assert "The Matrix" in movie_titles or "Dune" in movie_titles or len(movies) >= 3

    def test_tvshows_are_seeded(self, plex_test_helper):
        """Verify TV shows were seeded during bootstrap."""
        shows = plex_test_helper.get_all_shows()
        assert len(shows) > 0, "No TV shows found in library"

    def test_library_stats(self, plex_test_helper):
        """Test getting library statistics."""
        stats = plex_test_helper.get_library_stats()

        assert "movies" in stats
        assert "tvshows" in stats
        assert stats["movies"]["count"] > 0
        assert stats["tvshows"]["count"] > 0


class TestPlexCollectionOperations:
    """Test collection operations using real PlexAPI."""

    def test_create_and_delete_collection(self, clean_plex_test_data):
        """Test creating and deleting a collection."""
        helper = clean_plex_test_data

        # Get some movies to add to collection
        movies = helper.get_all_movies()[:2]
        if len(movies) < 2:
            pytest.skip("Not enough movies in library")

        # Create collection
        collection = helper.create_collection("Test Collection", movies)
        assert collection is not None
        assert collection.title == "Test Collection"

        # Verify items in collection
        items = helper.get_collection_items("Test Collection")
        assert len(items) == 2

        # Delete collection
        result = helper.delete_collection("Test Collection")
        assert result is True

        # Verify deletion
        assert helper.get_collection("Test Collection") is None

    def test_add_to_existing_collection(self, clean_plex_test_data):
        """Test adding items to an existing collection."""
        helper = clean_plex_test_data

        movies = helper.get_all_movies()[:3]
        if len(movies) < 3:
            pytest.skip("Not enough movies in library")

        # Create collection with first movie
        helper.create_collection("Test Add Collection", [movies[0]])

        # Add more movies
        helper.add_to_collection("Test Add Collection", [movies[1], movies[2]])

        # Verify all items in collection
        items = helper.get_collection_items("Test Add Collection")
        assert len(items) == 3

        # Cleanup
        helper.delete_collection("Test Add Collection")

    def test_remove_from_collection(self, clean_plex_test_data):
        """Test removing items from a collection."""
        helper = clean_plex_test_data

        movies = helper.get_all_movies()[:3]
        if len(movies) < 3:
            pytest.skip("Not enough movies in library")

        # Create collection with all movies
        helper.create_collection("Test Remove Collection", movies)

        # Remove one movie
        helper.remove_from_collection("Test Remove Collection", [movies[0]])

        # Verify remaining items
        items = helper.get_collection_items("Test Remove Collection")
        assert len(items) == 2

        # Cleanup
        helper.delete_collection("Test Remove Collection")


class TestPlexLabelOperations:
    """Test label operations using real PlexAPI."""

    def test_add_and_remove_label(self, clean_plex_test_data):
        """Test adding and removing labels from an item."""
        helper = clean_plex_test_data

        movies = helper.get_all_movies()
        if not movies:
            pytest.skip("No movies in library")

        movie = movies[0]

        # Add label
        helper.add_label(movie, "test-label")

        # Refresh and check
        movie.reload()
        assert helper.has_label(movie, "test-label")

        # Remove label
        helper.remove_label(movie, "test-label")

        # Refresh and check
        movie.reload()
        assert not helper.has_label(movie, "test-label")

    def test_leaving_soon_label(self, clean_plex_test_data):
        """Test the leaving-soon label pattern."""
        helper = clean_plex_test_data

        movies = helper.get_all_movies()[:2]
        if len(movies) < 2:
            pytest.skip("Not enough movies in library")

        # Add leaving-soon label to movies
        for movie in movies:
            helper.add_label(movie, "leaving-soon")

        # Find all items with leaving-soon label
        labeled_items = helper.get_items_with_label("leaving-soon")
        assert len(labeled_items) >= 2

        # Cleanup
        for movie in movies:
            movie.reload()
            helper.remove_label(movie, "leaving-soon")


class TestPlexLeavingSoonPattern:
    """Test the leaving_soon collection/label pattern with real Plex."""

    def test_leaving_soon_collection_workflow(self, clean_plex_test_data):
        """Test the full leaving_soon collection workflow."""
        helper = clean_plex_test_data

        movies = helper.get_all_movies()[:3]
        if len(movies) < 3:
            pytest.skip("Not enough movies in library")

        # 1. First run: Tag items for deletion (add to collection)
        collection = helper.create_collection("Leaving Soon", movies[:2])
        assert len(helper.get_collection_items("Leaving Soon")) == 2

        # 2. New item becomes a candidate
        helper.add_to_collection("Leaving Soon", [movies[2]])
        assert len(helper.get_collection_items("Leaving Soon")) == 3

        # 3. One item gets watched (remove from collection)
        helper.remove_from_collection("Leaving Soon", [movies[0]])
        assert len(helper.get_collection_items("Leaving Soon")) == 2

        # 4. Cleanup (delete collection after actual deletions)
        helper.delete_collection("Leaving Soon")
        assert helper.get_collection("Leaving Soon") is None

    def test_leaving_soon_label_workflow(self, clean_plex_test_data):
        """Test the full leaving_soon label workflow."""
        helper = clean_plex_test_data

        movies = helper.get_all_movies()[:3]
        if len(movies) < 3:
            pytest.skip("Not enough movies in library")

        # 1. First run: Tag items for deletion
        for movie in movies[:2]:
            helper.add_label(movie, "leaving-soon")

        # Verify labels
        labeled = helper.get_items_with_label("leaving-soon")
        assert len(labeled) >= 2

        # 2. Check specific movie has label
        movies[0].reload()
        assert helper.has_label(movies[0], "leaving-soon")

        # 3. Item gets watched - remove label
        helper.remove_label(movies[0], "leaving-soon")
        movies[0].reload()
        assert not helper.has_label(movies[0], "leaving-soon")

        # Cleanup
        for movie in movies:
            movie.reload()
            if helper.has_label(movie, "leaving-soon"):
                helper.remove_label(movie, "leaving-soon")


class TestJustWatchCacheAlignment:
    """Verify Plex seed data aligns with JustWatch cache for integration tests."""

    def test_movies_match_justwatch_cache(self, plex_test_helper):
        """Verify seeded movies have matching JustWatch cache entries."""
        movies = plex_test_helper.get_all_movies()
        movie_titles = [m.title for m in movies]

        # These movies have cached JustWatch responses
        cached_movies = ["The Matrix", "Dune", "The Seventh Seal", "Test Movie"]

        # At least some cached movies should be present
        matching = [t for t in cached_movies if t in movie_titles]
        assert len(matching) >= 2, f"Expected cached movies in library. Found: {movie_titles}"

    def test_shows_match_justwatch_cache(self, plex_test_helper):
        """Verify seeded shows have matching JustWatch cache entries."""
        shows = plex_test_helper.get_all_shows()
        show_titles = [s.title for s in shows]

        # These shows have cached JustWatch responses
        cached_shows = ["Breaking Bad", "Better Call Saul"]

        # At least one cached show should be present
        matching = [t for t in cached_shows if t in show_titles]
        assert len(matching) >= 1, f"Expected cached shows in library. Found: {show_titles}"
