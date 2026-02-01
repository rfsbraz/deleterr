# encoding: utf-8
"""
Integration tests for Plex-related Deleterr functionality.

These tests verify Deleterr code that interacts with Plex, not PlexAPI itself.
"""

import pytest

pytestmark = pytest.mark.integration


class TestJustWatchCacheAlignment:
    """Verify Plex seed data aligns with JustWatch cache for integration tests."""

    def test_movies_match_justwatch_cache(self, plex_test_helper):
        """Verify seeded movies have matching JustWatch cache entries."""
        if plex_test_helper.movies_section is None:
            pytest.skip("Movies library not available")

        movies = plex_test_helper.get_all_movies()
        if not movies:
            pytest.skip("No movies in library - Plex scan may not have completed")

        movie_titles = [m.title for m in movies]

        # These movies have cached JustWatch responses
        cached_movies = ["The Matrix", "Dune", "The Seventh Seal", "Test Movie"]

        # At least some cached movies should be present
        matching = [t for t in cached_movies if t in movie_titles]
        assert len(matching) >= 2, f"Expected cached movies in library. Found: {movie_titles}"

    def test_shows_match_justwatch_cache(self, plex_test_helper):
        """Verify seeded shows have matching JustWatch cache entries."""
        if plex_test_helper.tvshows_section is None:
            pytest.skip("TV Shows library not available")

        shows = plex_test_helper.get_all_shows()
        if not shows:
            pytest.skip("No shows in library - Plex scan may not have completed")

        show_titles = [s.title for s in shows]

        # These shows have cached JustWatch responses
        cached_shows = ["Breaking Bad", "Better Call Saul"]

        # At least one cached show should be present
        matching = [t for t in cached_shows if t in show_titles]
        assert len(matching) >= 1, f"Expected cached shows in library. Found: {show_titles}"
