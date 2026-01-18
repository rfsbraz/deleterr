"""
Integration tests for Radarr tag/field exclusions.

These tests verify that Radarr-based exclusions work correctly
with real Radarr containers for tags, quality profiles, paths, and monitored status.
"""

import pytest
from pyarr.radarr import RadarrAPI

from app.modules.radarr import DRadarr
from tests.integration.conftest import RADARR_URL

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestRadarrTagExclusions:
    """Test Radarr tag-based exclusions with real Radarr instance."""

    def test_create_and_get_tags(
        self, docker_services, radarr_seeder
    ):
        """Test that we can create and retrieve tags from Radarr."""
        # Create a test tag
        tag = radarr_seeder.create_tag("test-keep-tag")
        assert "id" in tag
        assert tag["label"] == "test-keep-tag"

        # Verify the tag exists in the list
        all_tags = radarr_seeder.get_tags()
        tag_labels = [t["label"] for t in all_tags]
        assert "test-keep-tag" in tag_labels

    def test_add_tag_to_movie(
        self, docker_services, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Test that we can add a tag to a movie."""
        # Create a tag
        tag = radarr_seeder.create_tag("4K-protection")

        # Add a test movie
        test_movie = {
            "title": "Tag Test Movie",
            "year": 2020,
            "tmdbId": 526896,  # Meg 2: The Trench
        }
        result = radarr_seeder.add_movie(test_movie)
        assert "id" in result, f"Failed to add test movie: {result}"
        movie_id = result["id"]

        try:
            # Add tag to movie
            updated_movie = radarr_seeder.add_tag_to_movie(movie_id, tag["id"])
            assert tag["id"] in updated_movie["tags"]

            # Verify via DRadarr
            dradarr = DRadarr("TestRadarr", RADARR_URL, radarr_seeder.api_key)
            has_tag = dradarr.check_movie_has_tags(updated_movie, ["4K-protection"])
            assert has_tag is True

        finally:
            # Cleanup
            try:
                radarr_client.del_movie(movie_id, delete_files=True)
            except Exception:
                pass

    def test_movie_without_matching_tag(
        self, docker_services, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Test that movie without matching tag is not flagged as having it."""
        # Create a tag but don't assign it
        radarr_seeder.create_tag("never-delete")

        # Add a test movie without the tag
        test_movie = {
            "title": "No Tag Movie",
            "year": 2021,
            "tmdbId": 385687,  # Fast X
        }
        result = radarr_seeder.add_movie(test_movie)
        assert "id" in result, f"Failed to add test movie: {result}"
        movie_id = result["id"]

        try:
            # Verify the movie doesn't have the tag
            dradarr = DRadarr("TestRadarr", RADARR_URL, radarr_seeder.api_key)
            movie = radarr_client.get_movie(movie_id)
            has_tag = dradarr.check_movie_has_tags(movie, ["never-delete"])
            assert has_tag is False

        finally:
            try:
                radarr_client.del_movie(movie_id, delete_files=True)
            except Exception:
                pass


class TestRadarrQualityProfileExclusions:
    """Test Radarr quality profile-based exclusions."""

    def test_get_quality_profiles(
        self, docker_services, radarr_seeder
    ):
        """Test that we can get quality profiles from Radarr."""
        profiles = radarr_seeder.get_quality_profiles()
        assert len(profiles) > 0
        # Default Radarr has at least one quality profile
        assert "id" in profiles[0]
        assert "name" in profiles[0]

    def test_movie_has_quality_profile(
        self, docker_services, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Test quality profile detection on movies."""
        # Add a test movie
        test_movie = {
            "title": "Quality Profile Test Movie",
            "year": 2022,
            "tmdbId": 505642,  # Black Panther: Wakanda Forever
        }
        result = radarr_seeder.add_movie(test_movie)
        assert "id" in result, f"Failed to add test movie: {result}"
        movie_id = result["id"]

        try:
            # Get the movie and its quality profile
            movie = radarr_client.get_movie(movie_id)
            quality_profile_id = movie["qualityProfileId"]

            # Get profile name
            profiles = radarr_seeder.get_quality_profiles()
            profile_name = None
            for p in profiles:
                if p["id"] == quality_profile_id:
                    profile_name = p["name"]
                    break

            assert profile_name is not None

            # Verify DRadarr can detect the quality profile
            dradarr = DRadarr("TestRadarr", RADARR_URL, radarr_seeder.api_key)
            has_profile = dradarr.check_movie_has_quality_profiles(movie, [profile_name])
            assert has_profile is True

            # Verify non-matching profile returns False
            has_fake_profile = dradarr.check_movie_has_quality_profiles(
                movie, ["NonExistent-Profile-XYZ"]
            )
            assert has_fake_profile is False

        finally:
            try:
                radarr_client.del_movie(movie_id, delete_files=True)
            except Exception:
                pass


class TestRadarrMonitoredStatusExclusions:
    """Test Radarr monitored status-based exclusions."""

    def test_movie_monitored_status(
        self, docker_services, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Test that we can detect and update monitored status."""
        # Add a test movie (by default, seeder sets monitored=False)
        test_movie = {
            "title": "Monitored Test Movie",
            "year": 2023,
            "tmdbId": 667538,  # Transformers: Rise of the Beasts
        }
        result = radarr_seeder.add_movie(test_movie)
        assert "id" in result, f"Failed to add test movie: {result}"
        movie_id = result["id"]

        try:
            # Verify initial monitored status is False
            movie = radarr_client.get_movie(movie_id)
            assert movie["monitored"] is False

            # Update monitored status to True
            updated = radarr_seeder.update_movie_monitored(movie_id, True)
            assert updated["monitored"] is True

            # Verify the change persists
            movie = radarr_client.get_movie(movie_id)
            assert movie["monitored"] is True

        finally:
            try:
                radarr_client.del_movie(movie_id, delete_files=True)
            except Exception:
                pass


class TestRadarrPathExclusions:
    """Test Radarr path-based exclusions."""

    def test_movie_path_detection(
        self, docker_services, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Test that movie paths are correctly detected."""
        # Add a test movie
        test_movie = {
            "title": "Path Test Movie",
            "year": 2019,
            "tmdbId": 475557,  # Joker
            "rootFolderPath": "/movies",
        }
        result = radarr_seeder.add_movie(test_movie)
        assert "id" in result, f"Failed to add test movie: {result}"
        movie_id = result["id"]

        try:
            # Get the movie and verify path
            movie = radarr_client.get_movie(movie_id)
            assert "path" in movie
            assert movie["path"].startswith("/movies")

            # Path exclusion check (would be done in media_cleaner)
            excluded_paths = ["/movies"]
            movie_path = movie.get("path", "")
            is_excluded = any(path in movie_path for path in excluded_paths)
            assert is_excluded is True

            # Non-matching path
            excluded_paths_4k = ["/media/4k"]
            is_excluded_4k = any(path in movie_path for path in excluded_paths_4k)
            assert is_excluded_4k is False

        finally:
            try:
                radarr_client.del_movie(movie_id, delete_files=True)
            except Exception:
                pass


class TestDRadarrIntegration:
    """Test DRadarr wrapper class with real Radarr instance."""

    def test_dradarr_connection(self, docker_services, radarr_seeder):
        """Test DRadarr can connect to real Radarr instance."""
        dradarr = DRadarr("TestRadarr", RADARR_URL, radarr_seeder.api_key)
        assert dradarr.validate_connection() is True

    def test_dradarr_get_tags_caches(
        self, docker_services, radarr_seeder
    ):
        """Test that DRadarr caches tags after first call."""
        # Create a tag first
        radarr_seeder.create_tag("cache-test-tag")

        dradarr = DRadarr("TestRadarr", RADARR_URL, radarr_seeder.api_key)

        # First call fetches from API
        tags1 = dradarr.get_tags()
        assert len(tags1) > 0

        # Second call should use cache
        tags2 = dradarr.get_tags()
        assert tags1 == tags2

    def test_dradarr_get_quality_profiles_caches(
        self, docker_services, radarr_seeder
    ):
        """Test that DRadarr caches quality profiles after first call."""
        dradarr = DRadarr("TestRadarr", RADARR_URL, radarr_seeder.api_key)

        # First call fetches from API
        profiles1 = dradarr.get_quality_profiles()
        assert len(profiles1) > 0

        # Second call should use cache
        profiles2 = dradarr.get_quality_profiles()
        assert profiles1 == profiles2

    def test_dradarr_get_movies(
        self, docker_services, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Test DRadarr can get movies from Radarr."""
        # Add a test movie
        test_movie = {
            "title": "DRadarr Get Test Movie",
            "year": 2018,
            "tmdbId": 299536,  # Avengers: Infinity War
        }
        result = radarr_seeder.add_movie(test_movie)
        assert "id" in result, f"Failed to add test movie: {result}"
        movie_id = result["id"]

        try:
            dradarr = DRadarr("TestRadarr", RADARR_URL, radarr_seeder.api_key)
            movies = dradarr.get_movies()

            assert len(movies) > 0
            # Find our movie
            found = any(m["id"] == movie_id for m in movies)
            assert found is True

        finally:
            try:
                radarr_client.del_movie(movie_id, delete_files=True)
            except Exception:
                pass


class TestRadarrCombinedExclusions:
    """Test multiple Radarr exclusion criteria together."""

    def test_movie_with_multiple_exclusion_criteria(
        self, docker_services, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Test a movie that matches multiple exclusion criteria."""
        # Create tags
        keep_tag = radarr_seeder.create_tag("keep")
        favorite_tag = radarr_seeder.create_tag("favorite")

        # Add a test movie
        test_movie = {
            "title": "Multi-Exclusion Test Movie",
            "year": 2021,
            "tmdbId": 580489,  # Venom: Let There Be Carnage
        }
        result = radarr_seeder.add_movie(test_movie)
        assert "id" in result, f"Failed to add test movie: {result}"
        movie_id = result["id"]

        try:
            # Add multiple tags
            radarr_seeder.add_tag_to_movie(movie_id, keep_tag["id"])
            radarr_seeder.add_tag_to_movie(movie_id, favorite_tag["id"])

            # Update to monitored
            radarr_seeder.update_movie_monitored(movie_id, True)

            # Get updated movie
            movie = radarr_client.get_movie(movie_id)

            # Verify all criteria
            dradarr = DRadarr("TestRadarr", RADARR_URL, radarr_seeder.api_key)

            # Has both tags
            assert dradarr.check_movie_has_tags(movie, ["keep"]) is True
            assert dradarr.check_movie_has_tags(movie, ["favorite"]) is True
            assert dradarr.check_movie_has_tags(movie, ["keep", "favorite"]) is True

            # Is monitored
            assert movie["monitored"] is True

            # Has correct path
            assert movie["path"].startswith("/movies")

        finally:
            try:
                radarr_client.del_movie(movie_id, delete_files=True)
            except Exception:
                pass
