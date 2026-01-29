"""
Integration tests for Radarr API interactions.

These tests verify that Deleterr correctly interacts with a real
Radarr instance running in Docker.
"""

import pytest
from pyarr.radarr import RadarrAPI

from app.modules.radarr import DRadarr

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestRadarrConnection:
    """Test basic Radarr connectivity and API access."""

    def test_radarr_is_accessible(self, radarr_client: RadarrAPI):
        """Verify Radarr API is accessible and responding."""
        status = radarr_client.get_system_status()
        assert status is not None
        assert "version" in status

    def test_radarr_api_key_is_valid(self, radarr_client: RadarrAPI):
        """Verify API key authentication works."""
        # If we can get status, the API key is valid
        status = radarr_client.get_system_status()
        assert status.get("authentication") is not None or "version" in status


class TestRadarrMovieOperations:
    """Test Radarr movie CRUD operations."""

    def test_get_movies_returns_seeded_data(self, seeded_radarr: RadarrAPI):
        """Verify seeded movies are accessible via API."""
        movies = seeded_radarr.get_movie()
        assert isinstance(movies, list)
        assert len(movies) > 0, "No movies were seeded - seeding failed"

        # Check that our test movies are present
        titles = [m.get("title") for m in movies]
        # We seed Fight Club, The Matrix, and Inception
        assert "Fight Club" in titles or "The Matrix" in titles, (
            f"Expected seeded movies not found. Got titles: {titles}"
        )

    def test_get_movie_by_id(self, seeded_radarr: RadarrAPI):
        """Verify we can retrieve a specific movie by ID."""
        movies = seeded_radarr.get_movie()
        assert len(movies) > 0, "No movies were seeded - seeding failed"

        movie_id = movies[0]["id"]
        movie = seeded_radarr.get_movie(movie_id)
        assert movie is not None
        assert movie.get("id") == movie_id

    def test_movie_has_required_fields(self, seeded_radarr: RadarrAPI):
        """Verify movies have all fields Deleterr needs."""
        movies = seeded_radarr.get_movie()
        assert len(movies) > 0, "No movies were seeded - seeding failed"

        movie = movies[0]
        # Fields required by Deleterr
        required_fields = ["id", "title", "tmdbId", "path", "monitored"]
        for field in required_fields:
            assert field in movie, f"Missing required field: {field}"


class TestRadarrDeletion:
    """Test movie deletion operations."""

    def test_delete_movie_removes_from_library(
        self, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Verify deleting a movie actually removes it."""
        # Add a test movie specifically for deletion
        # Using real TMDb ID for The Prestige
        test_movie = {
            "title": "The Prestige",
            "year": 2006,
            "tmdbId": 1124,
        }

        # Seed the movie
        result = radarr_seeder.add_movie(test_movie)
        assert "id" in result, f"Failed to add test movie: {result}"

        movie_id = result["id"]

        # Verify it exists
        movies_before = radarr_client.get_movie()
        ids_before = [m["id"] for m in movies_before]
        assert movie_id in ids_before

        # Delete the movie
        radarr_client.del_movie(movie_id, delete_files=True)

        # Verify it's gone
        movies_after = radarr_client.get_movie()
        ids_after = [m["id"] for m in movies_after]
        assert movie_id not in ids_after


class TestRadarrDiskSpace:
    """Test disk space reporting."""

    def test_get_disk_space_returns_valid_data(self, radarr_client: RadarrAPI):
        """Verify disk space endpoint returns useful data."""
        disk_space = radarr_client.get_disk_space()
        assert isinstance(disk_space, list)

        if disk_space:
            space = disk_space[0]
            assert "path" in space
            assert "freeSpace" in space
            assert "totalSpace" in space
            assert space["freeSpace"] >= 0
            assert space["totalSpace"] > 0


class TestRadarrQualityProfiles:
    """Test quality profile operations."""

    def test_get_quality_profiles(self, radarr_client: RadarrAPI):
        """Verify quality profiles are accessible."""
        profiles = radarr_client.get_quality_profile()
        assert isinstance(profiles, list)
        # Radarr should have default profiles
        assert len(profiles) > 0

        profile = profiles[0]
        assert "id" in profile
        assert "name" in profile


class TestRadarrRootFolders:
    """Test root folder operations."""

    def test_get_root_folders(self, seeded_radarr: RadarrAPI):
        """Verify root folders endpoint is accessible."""
        folders = seeded_radarr.get_root_folder()
        assert isinstance(folders, list)
        # Root folders may or may not be configured depending on container permissions
        # The important thing is that the API returns a valid response
        if len(folders) > 0:
            folder = folders[0]
            assert "path" in folder
            assert "freeSpace" in folder


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
