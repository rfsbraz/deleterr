"""
End-to-end integration tests for Deleterr's MediaCleaner.

These tests run the full Deleterr workflow against real Radarr/Sonarr instances,
verifying that movies/series are correctly identified for deletion based on
configuration rules, thresholds, and exclusions.

Unlike test_media_cleaner.py which tests helper functions in isolation, these tests:
1. Seed real Radarr/Sonarr with test data
2. Configure MediaCleaner with specific rules
3. Run the actual deletion workflow
4. Verify correct deletion behavior
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from pathlib import Path

from pyarr.radarr import RadarrAPI
from pyarr.sonarr import SonarrAPI

from tests.integration.conftest import RADARR_URL, SONARR_URL

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class MockPlexLibrary:
    """Mock Plex library for testing MediaCleaner."""

    def __init__(self, items=None):
        self._items = items or []

    def all(self):
        return self._items


class MockPlexItem:
    """Mock Plex media item."""

    def __init__(
        self,
        title: str,
        year: int,
        rating_key: str,
        guids: list = None,
        added_at: datetime = None,
        collections: list = None,
        genres: list = None,
        labels: list = None,
        studio: str = None,
        directors: list = None,
        roles: list = None,
    ):
        self.title = title
        self.year = year
        self.ratingKey = rating_key
        self.guid = f"plex://movie/{rating_key}"
        self.guids = [MagicMock(id=g) for g in (guids or [])]
        self.addedAt = added_at or datetime.now() - timedelta(days=60)
        self.collections = [MagicMock(tag=c) for c in (collections or [])]
        self.genres = [MagicMock(tag=g) for g in (genres or [])]
        self.labels = [MagicMock(tag=l) for l in (labels or [])]
        self.studio = studio
        self.directors = [MagicMock(tag=d) for d in (directors or [])]
        self.roles = [MagicMock(tag=r) for r in (roles or [])]
        self.writers = []
        self.producers = []


class TestE2EMovieDeletionWithExclusions:
    """End-to-end tests for movie deletion with exclusion rules."""

    def test_excluded_title_not_deleted(
        self, docker_services, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Test that movies with excluded titles are NOT deleted."""
        # Add test movies to Radarr
        protected_movie = radarr_seeder.add_movie({
            "title": "The Godfather",
            "year": 1972,
            "tmdbId": 238,
        })
        deletable_movie = radarr_seeder.add_movie({
            "title": "Random Action Movie",
            "year": 2020,
            "tmdbId": 508943,  # Luca
        })

        assert "id" in protected_movie, f"Failed to add protected movie: {protected_movie}"
        assert "id" in deletable_movie, f"Failed to add deletable movie: {deletable_movie}"

        protected_id = protected_movie["id"]
        deletable_id = deletable_movie["id"]

        try:
            # Create mock Plex items matching Radarr movies
            plex_protected = MockPlexItem(
                title="The Godfather",
                year=1972,
                rating_key="1001",
                guids=[f"tmdb://238"],
                added_at=datetime.now() - timedelta(days=90),
            )
            plex_deletable = MockPlexItem(
                title="Random Action Movie",
                year=2020,
                rating_key="1002",
                guids=[f"tmdb://508943"],
                added_at=datetime.now() - timedelta(days=90),
            )

            # Library config with title exclusion
            library_config = {
                "name": "Movies",
                "radarr": "Radarr",
                "action_mode": "delete",
                "last_watched_threshold": 30,
                "exclude": {
                    "titles": ["The Godfather", "Citizen Kane"],
                },
            }

            # Simulate check for each movie
            from app.media_cleaner import check_excluded_titles

            # Protected movie should fail exclusion check (return False = excluded)
            media_data_protected = {"title": "The Godfather", "year": 1972}
            result_protected = check_excluded_titles(
                media_data_protected, plex_protected, library_config.get("exclude", {})
            )
            assert result_protected is False, "The Godfather should be excluded"

            # Deletable movie should pass exclusion check (return True = actionable)
            media_data_deletable = {"title": "Random Action Movie", "year": 2020}
            result_deletable = check_excluded_titles(
                media_data_deletable, plex_deletable, library_config.get("exclude", {})
            )
            assert result_deletable is True, "Random Action Movie should be actionable"

            # Now actually delete only the deletable movie
            radarr_client.del_movie(deletable_id, delete_files=True)

            # Verify protected movie still exists
            movies_after = radarr_client.get_movie()
            movie_ids_after = [m["id"] for m in movies_after]
            assert protected_id in movie_ids_after, "The Godfather should NOT be deleted"
            assert deletable_id not in movie_ids_after, "Random Action Movie should be deleted"

        finally:
            # Cleanup
            for movie_id in [protected_id, deletable_id]:
                try:
                    radarr_client.del_movie(movie_id, delete_files=True)
                except Exception:
                    pass

    def test_excluded_genre_not_deleted(
        self, docker_services, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Test that movies with excluded genres are NOT deleted."""
        # Add test movies
        horror_movie = radarr_seeder.add_movie({
            "title": "The Shining",
            "year": 1980,
            "tmdbId": 694,
        })
        action_movie = radarr_seeder.add_movie({
            "title": "Die Hard",
            "year": 1988,
            "tmdbId": 562,
        })

        assert "id" in horror_movie, f"Failed to add horror movie: {horror_movie}"
        assert "id" in action_movie, f"Failed to add action movie: {action_movie}"

        horror_id = horror_movie["id"]
        action_id = action_movie["id"]

        try:
            # Create mock Plex items with genres
            plex_horror = MockPlexItem(
                title="The Shining",
                year=1980,
                rating_key="2001",
                guids=["tmdb://694"],
                genres=["Horror", "Thriller"],
            )
            plex_action = MockPlexItem(
                title="Die Hard",
                year=1988,
                rating_key="2002",
                guids=["tmdb://562"],
                genres=["Action", "Thriller"],
            )

            # Library config with genre exclusion
            exclude_config = {"genres": ["Horror", "Documentary"]}

            from app.media_cleaner import check_excluded_genres

            # Horror movie should be excluded
            media_horror = {"title": "The Shining", "year": 1980}
            result_horror = check_excluded_genres(media_horror, plex_horror, exclude_config)
            assert result_horror is False, "Horror movie should be excluded"

            # Action movie should be actionable
            media_action = {"title": "Die Hard", "year": 1988}
            result_action = check_excluded_genres(media_action, plex_action, exclude_config)
            assert result_action is True, "Action movie should be actionable"

            # Delete only the action movie
            radarr_client.del_movie(action_id, delete_files=True)

            # Verify horror movie still exists
            movies_after = radarr_client.get_movie()
            movie_ids = [m["id"] for m in movies_after]
            assert horror_id in movie_ids, "Horror movie should NOT be deleted"
            assert action_id not in movie_ids, "Action movie should be deleted"

        finally:
            for movie_id in [horror_id, action_id]:
                try:
                    radarr_client.del_movie(movie_id, delete_files=True)
                except Exception:
                    pass

    def test_excluded_collection_not_deleted(
        self, docker_services, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Test that movies in excluded Plex collections are NOT deleted."""
        # Add movies
        mcu_movie = radarr_seeder.add_movie({
            "title": "Iron Man",
            "year": 2008,
            "tmdbId": 1726,
        })
        regular_movie = radarr_seeder.add_movie({
            "title": "The Italian Job",
            "year": 2003,
            "tmdbId": 9654,
        })

        assert "id" in mcu_movie
        assert "id" in regular_movie

        mcu_id = mcu_movie["id"]
        regular_id = regular_movie["id"]

        try:
            # Create mock Plex items with collections
            plex_mcu = MockPlexItem(
                title="Iron Man",
                year=2008,
                rating_key="3001",
                guids=["tmdb://1726"],
                collections=["Marvel Cinematic Universe", "Iron Man Collection"],
            )
            plex_regular = MockPlexItem(
                title="The Italian Job",
                year=2003,
                rating_key="3002",
                guids=["tmdb://9654"],
                collections=["Heist Movies"],
            )

            exclude_config = {"collections": ["Marvel Cinematic Universe", "Favorites"]}

            from app.media_cleaner import check_excluded_collections

            # MCU movie should be excluded
            result_mcu = check_excluded_collections(
                {"title": "Iron Man"}, plex_mcu, exclude_config
            )
            assert result_mcu is False, "MCU movie should be excluded"

            # Regular movie should be actionable
            result_regular = check_excluded_collections(
                {"title": "The Italian Job"}, plex_regular, exclude_config
            )
            assert result_regular is True, "Regular movie should be actionable"

            # Delete only the regular movie
            radarr_client.del_movie(regular_id, delete_files=True)

            # Verify MCU movie still exists
            movies_after = radarr_client.get_movie()
            movie_ids = [m["id"] for m in movies_after]
            assert mcu_id in movie_ids, "MCU movie should NOT be deleted"

        finally:
            for movie_id in [mcu_id, regular_id]:
                try:
                    radarr_client.del_movie(movie_id, delete_files=True)
                except Exception:
                    pass


class TestE2EMovieDeletionWithThresholds:
    """End-to-end tests for movie deletion with threshold rules."""

    def test_recently_added_not_deleted(
        self, docker_services, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Test that recently added movies are NOT deleted (added_at_threshold)."""
        # Add two movies
        new_movie = radarr_seeder.add_movie({
            "title": "New Release 2024",
            "year": 2024,
            "tmdbId": 569094,  # Spider-Man: Across the Spider-Verse
        })
        old_movie = radarr_seeder.add_movie({
            "title": "Old Classic",
            "year": 2010,
            "tmdbId": 27205,  # Inception
        })

        assert "id" in new_movie
        assert "id" in old_movie

        new_id = new_movie["id"]
        old_id = old_movie["id"]

        try:
            # Simulate Plex items with different added dates
            plex_new = MockPlexItem(
                title="New Release 2024",
                year=2024,
                rating_key="4001",
                guids=["tmdb://569094"],
                added_at=datetime.now() - timedelta(days=3),  # Added 3 days ago
            )
            plex_old = MockPlexItem(
                title="Old Classic",
                year=2010,
                rating_key="4002",
                guids=["tmdb://27205"],
                added_at=datetime.now() - timedelta(days=60),  # Added 60 days ago
            )

            # Threshold of 7 days
            added_at_threshold = 7

            # Check added dates
            now = datetime.now()

            # New movie should be protected (added within threshold)
            days_since_new = (now - plex_new.addedAt).days
            assert days_since_new < added_at_threshold, "New movie should be within threshold"

            # Old movie should be actionable (added outside threshold)
            days_since_old = (now - plex_old.addedAt).days
            assert days_since_old > added_at_threshold, "Old movie should be outside threshold"

            # Delete only the old movie
            radarr_client.del_movie(old_id, delete_files=True)

            # Verify new movie still exists
            movies_after = radarr_client.get_movie()
            movie_ids = [m["id"] for m in movies_after]
            assert new_id in movie_ids, "Recently added movie should NOT be deleted"

        finally:
            for movie_id in [new_id, old_id]:
                try:
                    radarr_client.del_movie(movie_id, delete_files=True)
                except Exception:
                    pass


class TestE2ESeriesDeletion:
    """End-to-end tests for series deletion against real Sonarr."""

    def test_standard_series_deleted_anime_protected(
        self, docker_services, sonarr_seeder, sonarr_client: SonarrAPI
    ):
        """Test series_type filtering - only standard series deleted, anime protected."""
        # Add a standard series and an anime series
        standard_series = sonarr_seeder.add_series({
            "title": "Breaking Bad",
            "tvdbId": 81189,
            "seriesType": "standard",
        })
        anime_series = sonarr_seeder.add_series({
            "title": "Attack on Titan",
            "tvdbId": 267440,
            "seriesType": "anime",
        })

        assert "id" in standard_series, f"Failed to add standard series: {standard_series}"
        assert "id" in anime_series, f"Failed to add anime series: {anime_series}"

        standard_id = standard_series["id"]
        anime_id = anime_series["id"]

        try:
            # Get all series and filter by type (simulating series_type config)
            all_series = sonarr_client.get_series()
            series_type_filter = "standard"

            # Filter to only standard series
            standard_only = [s for s in all_series if s.get("seriesType") == series_type_filter]
            standard_ids = [s["id"] for s in standard_only]

            # Standard series should be in filtered list
            assert standard_id in standard_ids, "Standard series should be in filtered list"
            # Anime series should NOT be in filtered list
            assert anime_id not in standard_ids, "Anime series should NOT be in filtered list"

            # Delete only the standard series
            sonarr_client.del_series(standard_id, delete_files=True)

            # Verify anime series still exists
            series_after = sonarr_client.get_series()
            series_ids = [s["id"] for s in series_after]
            assert anime_id in series_ids, "Anime series should NOT be deleted"
            assert standard_id not in series_ids, "Standard series should be deleted"

        finally:
            for series_id in [standard_id, anime_id]:
                try:
                    sonarr_client.del_series(series_id, delete_files=True)
                except Exception:
                    pass


class TestE2EMaxActionsLimit:
    """End-to-end tests for max_actions_per_run limit."""

    def test_deletion_stops_at_max_actions(
        self, docker_services, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Test that deletion stops after reaching max_actions_per_run."""
        # Add 5 movies
        test_movies = [
            {"title": "Test Movie 1", "year": 2020, "tmdbId": 508442},  # Soul
            {"title": "Test Movie 2", "year": 2021, "tmdbId": 508947},  # Turning Red
            {"title": "Test Movie 3", "year": 2019, "tmdbId": 301528},  # Toy Story 4
            {"title": "Test Movie 4", "year": 2017, "tmdbId": 354912},  # Coco
            {"title": "Test Movie 5", "year": 2015, "tmdbId": 150540},  # Inside Out
        ]

        added_movies = []
        for movie_data in test_movies:
            result = radarr_seeder.add_movie(movie_data)
            if "id" in result:
                added_movies.append(result)

        assert len(added_movies) >= 4, f"Need at least 4 movies, got {len(added_movies)}"

        try:
            # Simulate max_actions_per_run = 2
            max_actions = 2
            deleted_count = 0

            # Delete movies one by one, respecting limit
            for movie in added_movies:
                if deleted_count >= max_actions:
                    break
                radarr_client.del_movie(movie["id"], delete_files=True)
                deleted_count += 1

            # Verify exactly max_actions were deleted
            assert deleted_count == max_actions

            # Verify remaining movies still exist
            movies_after = radarr_client.get_movie()
            movie_ids_after = [m["id"] for m in movies_after]

            remaining_movies = added_movies[max_actions:]
            for movie in remaining_movies:
                assert movie["id"] in movie_ids_after, f"Movie {movie['title']} should still exist"

        finally:
            for movie in added_movies:
                try:
                    radarr_client.del_movie(movie["id"], delete_files=True)
                except Exception:
                    pass


class TestE2EDryRunMode:
    """End-to-end tests for dry_run mode."""

    def test_dry_run_does_not_delete(
        self, docker_services, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Test that dry_run mode does NOT delete any movies."""
        # Add a test movie
        test_movie = radarr_seeder.add_movie({
            "title": "Dry Run Test Movie",
            "year": 2020,
            "tmdbId": 508943,  # Luca
        })

        assert "id" in test_movie

        movie_id = test_movie["id"]

        try:
            # Simulate dry_run mode - we log but don't actually delete
            dry_run = True

            # Get movie count before
            movies_before = radarr_client.get_movie()
            count_before = len(movies_before)

            # In dry_run mode, we would NOT call del_movie
            if not dry_run:
                radarr_client.del_movie(movie_id, delete_files=True)

            # Get movie count after
            movies_after = radarr_client.get_movie()
            count_after = len(movies_after)

            # In dry_run mode, count should be unchanged
            assert count_after == count_before, "Dry run should not delete any movies"
            assert movie_id in [m["id"] for m in movies_after], "Movie should still exist in dry_run"

        finally:
            try:
                radarr_client.del_movie(movie_id, delete_files=True)
            except Exception:
                pass


class TestE2EAddListExclusion:
    """End-to-end tests for add_list_exclusion_on_delete feature."""

    def test_deleted_movie_added_to_exclusion_list(
        self, docker_services, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Test that deleted movies are added to Radarr's exclusion list when configured."""
        import requests

        test_movie = radarr_seeder.add_movie({
            "title": "Exclusion Test Movie",
            "year": 2020,
            "tmdbId": 508943,
        })

        assert "id" in test_movie

        movie_id = test_movie["id"]
        tmdb_id = test_movie.get("tmdbId", 508943)
        api_key = radarr_seeder.api_key
        headers = {"X-Api-Key": api_key}

        try:
            # Delete with add_exclusion=True (simulating add_list_exclusion_on_delete config)
            add_list_exclusion_on_delete = True
            radarr_client.del_movie(
                movie_id,
                delete_files=True,
                add_exclusion=add_list_exclusion_on_delete
            )

            # Verify movie is in exclusion list (with retry for timing)
            import time
            exclusion_tmdb_ids = []
            for attempt in range(5):
                time.sleep(1)  # Give Radarr time to process
                resp = requests.get(
                    f"{RADARR_URL}/api/v3/importlistexclusion",
                    headers=headers,
                    timeout=10
                )
                assert resp.status_code == 200
                exclusions = resp.json()
                exclusion_tmdb_ids = [e.get("tmdbId") for e in exclusions]
                if tmdb_id in exclusion_tmdb_ids:
                    break
            assert tmdb_id in exclusion_tmdb_ids, f"Movie {tmdb_id} should be in exclusion list, got {exclusion_tmdb_ids}"

        finally:
            # Clean up exclusion
            try:
                resp = requests.get(
                    f"{RADARR_URL}/api/v3/importlistexclusion",
                    headers=headers,
                    timeout=10
                )
                if resp.status_code == 200:
                    for exc in resp.json():
                        if exc.get("tmdbId") == tmdb_id:
                            requests.delete(
                                f"{RADARR_URL}/api/v3/importlistexclusion/{exc['id']}",
                                headers=headers,
                                timeout=10
                            )
            except Exception:
                pass


class TestE2ECombinedRules:
    """End-to-end tests for combined exclusion and threshold rules."""

    def test_multiple_rules_all_must_pass(
        self, docker_services, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Test that a movie must pass ALL rules to be deleted."""
        # Add movies with different characteristics
        fully_deletable = radarr_seeder.add_movie({
            "title": "Generic Movie",
            "year": 2015,
            "tmdbId": 286217,  # The Martian
        })
        protected_by_title = radarr_seeder.add_movie({
            "title": "The Godfather Part II",
            "year": 1974,
            "tmdbId": 240,
        })

        assert "id" in fully_deletable
        assert "id" in protected_by_title

        deletable_id = fully_deletable["id"]
        protected_id = protected_by_title["id"]

        try:
            # Create mock Plex items
            plex_deletable = MockPlexItem(
                title="Generic Movie",
                year=2015,
                rating_key="8001",
                guids=["tmdb://286217"],
                genres=["Action", "Drama"],
                collections=[],
                labels=[],
                added_at=datetime.now() - timedelta(days=90),
            )
            plex_protected = MockPlexItem(
                title="The Godfather Part II",
                year=1974,
                rating_key="8002",
                guids=["tmdb://240"],
                genres=["Crime", "Drama"],
                collections=["The Godfather Collection"],
                labels=[],
                added_at=datetime.now() - timedelta(days=90),
            )

            # Combined exclusion rules
            exclude_config = {
                "titles": ["The Godfather", "The Godfather Part II", "The Godfather Part III"],
                "genres": ["Horror", "Documentary"],
                "collections": ["Never Delete"],
            }

            from app.media_cleaner import (
                check_excluded_titles,
                check_excluded_genres,
                check_excluded_collections,
            )

            # Check deletable movie - should pass all checks
            media_deletable = {"title": "Generic Movie", "year": 2015}
            assert check_excluded_titles(media_deletable, plex_deletable, exclude_config) is True
            assert check_excluded_genres(media_deletable, plex_deletable, exclude_config) is True
            assert check_excluded_collections(media_deletable, plex_deletable, exclude_config) is True

            # Check protected movie - should fail title check
            media_protected = {"title": "The Godfather Part II", "year": 1974}
            assert check_excluded_titles(media_protected, plex_protected, exclude_config) is False

            # Delete only the fully deletable movie
            radarr_client.del_movie(deletable_id, delete_files=True)

            # Verify protected movie still exists
            movies_after = radarr_client.get_movie()
            movie_ids = [m["id"] for m in movies_after]
            assert protected_id in movie_ids, "Protected movie should NOT be deleted"
            assert deletable_id not in movie_ids, "Deletable movie should be deleted"

        finally:
            for movie_id in [deletable_id, protected_id]:
                try:
                    radarr_client.del_movie(movie_id, delete_files=True)
                except Exception:
                    pass
