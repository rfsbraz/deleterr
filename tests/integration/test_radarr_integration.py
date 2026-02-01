"""
Integration tests for Deleterr's Radarr wrapper (DRadarr).

These tests verify that Deleterr's DRadarr wrapper correctly delegates to the
pyarr library against a real Radarr instance. This catches issues like method
name typos that unit tests with MagicMock won't detect.
"""

import pytest
from pyarr.radarr import RadarrAPI

from app.modules.radarr import DRadarr

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestDRadarrWrapper:
    """Test DRadarr wrapper class with real Radarr instance.

    These tests verify that the application's wrapper class correctly
    delegates to the pyarr library. This catches issues like method name
    typos that unit tests with MagicMock won't detect.
    """

    def test_dradarr_validate_connection(self, dradarr_client: DRadarr):
        """Verify DRadarr can validate connection to real Radarr."""
        assert dradarr_client.validate_connection() is True

    def test_dradarr_get_disk_space(self, dradarr_client: DRadarr):
        """Verify DRadarr.get_disk_space() works with real Radarr.

        This test would have caught issue #177 where the wrapper called
        get_diskspace() instead of get_disk_space().
        """
        disk_space = dradarr_client.get_disk_space()
        assert isinstance(disk_space, list)

        if disk_space:
            space = disk_space[0]
            assert "path" in space
            assert "freeSpace" in space
            assert "totalSpace" in space

    def test_dradarr_get_movies(self, dradarr_client: DRadarr, seeded_radarr):
        """Verify DRadarr.get_movies() works with real Radarr."""
        movies = dradarr_client.get_movies()
        assert isinstance(movies, list)
        assert len(movies) > 0

    def test_dradarr_get_tags(self, dradarr_client: DRadarr):
        """Verify DRadarr.get_tags() works with real Radarr."""
        tags = dradarr_client.get_tags()
        assert isinstance(tags, list)

    def test_dradarr_get_quality_profiles(self, dradarr_client: DRadarr):
        """Verify DRadarr.get_quality_profiles() works with real Radarr."""
        profiles = dradarr_client.get_quality_profiles()
        assert isinstance(profiles, list)
        assert len(profiles) > 0

    def test_dradarr_del_movie(self, dradarr_client: DRadarr, radarr_seeder):
        """Verify DRadarr.del_movie() works with real Radarr.

        This test would have caught issue #180 where the wrapper was missing
        the del_movie method entirely.
        """
        # Add a movie specifically for deletion
        test_movie = {
            "title": "Test Movie For Deletion",
            "year": 2020,
            "tmdbId": 438631,  # Dune (2021)
        }
        result = radarr_seeder.add_movie(test_movie)
        assert "id" in result, f"Failed to add test movie: {result}"
        movie_id = result["id"]

        # Verify the movie exists
        movies_before = dradarr_client.get_movies()
        ids_before = [m["id"] for m in movies_before]
        assert movie_id in ids_before

        # Delete via wrapper method
        dradarr_client.del_movie(movie_id, delete_files=True, add_exclusion=False)

        # Verify deletion
        movies_after = dradarr_client.get_movies()
        ids_after = [m["id"] for m in movies_after]
        assert movie_id not in ids_after
