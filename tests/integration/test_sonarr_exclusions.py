"""
Integration tests for Sonarr tag/field exclusions.

These tests verify that Sonarr-based exclusions work correctly
with real Sonarr containers for status, tags, quality profiles, paths, and monitored status.
"""

import pytest
from pyarr.sonarr import SonarrAPI

from app.modules.sonarr import DSonarr
from tests.integration.conftest import SONARR_URL

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestSonarrStatusExclusions:
    """Test Sonarr status-based exclusions with real Sonarr instance."""

    def test_series_has_status_field(
        self, docker_services, sonarr_seeder, sonarr_client: SonarrAPI
    ):
        """Test that series have a status field from Sonarr API."""
        # Add a test series - using unique TVDB ID to avoid conflicts with seed data
        test_series = {
            "title": "Status Test Series",
            "tvdbId": 279121,  # The Crown (different from seed data)
            "seriesType": "standard",
        }
        result = sonarr_seeder.add_series(test_series)
        assert "id" in result, f"Failed to add test series: {result}"
        series_id = result["id"]

        try:
            # Get the series and verify status field exists
            series = sonarr_client.get_series(series_id)
            assert "status" in series
            # Valid status values: continuing, ended, upcoming, deleted
            assert series["status"] in ["continuing", "ended", "upcoming", "deleted"]

        finally:
            try:
                sonarr_client.del_series(series_id, delete_files=True)
            except Exception:
                pass

    def test_ended_series_status(
        self, docker_services, sonarr_seeder, sonarr_client: SonarrAPI
    ):
        """Test that ended series are correctly identified."""
        # Mad Men ended in 2015 - using different TVDB ID from seed data
        test_series = {
            "title": "Mad Men",
            "tvdbId": 80337,
            "seriesType": "standard",
        }
        result = sonarr_seeder.add_series(test_series)
        assert "id" in result, f"Failed to add test series: {result}"
        series_id = result["id"]

        try:
            series = sonarr_client.get_series(series_id)
            assert series["status"] == "ended"

        finally:
            try:
                sonarr_client.del_series(series_id, delete_files=True)
            except Exception:
                pass


class TestSonarrTagExclusions:
    """Test Sonarr tag-based exclusions with real Sonarr instance."""

    def test_create_and_get_tags(
        self, docker_services, sonarr_seeder
    ):
        """Test that we can create and retrieve tags from Sonarr."""
        # Create a test tag
        tag = sonarr_seeder.create_tag("test-keep-tag")
        assert "id" in tag
        assert tag["label"] == "test-keep-tag"

        # Verify the tag exists in the list
        all_tags = sonarr_seeder.get_tags()
        tag_labels = [t["label"] for t in all_tags]
        assert "test-keep-tag" in tag_labels

    def test_add_tag_to_series(
        self, docker_services, sonarr_seeder, sonarr_client: SonarrAPI
    ):
        """Test that we can add a tag to a series."""
        # Create a tag
        tag = sonarr_seeder.create_tag("4K-protection")

        # Add a test series - using unique TVDB ID to avoid conflicts with seed data
        test_series = {
            "title": "Tag Test Series",
            "tvdbId": 305074,  # The Witcher (different from seed data)
            "seriesType": "standard",
        }
        result = sonarr_seeder.add_series(test_series)
        assert "id" in result, f"Failed to add test series: {result}"
        series_id = result["id"]

        try:
            # Add tag to series
            updated_series = sonarr_seeder.add_tag_to_series(series_id, tag["id"])
            assert tag["id"] in updated_series["tags"]

            # Verify via DSonarr
            dsonarr = DSonarr("TestSonarr", SONARR_URL, sonarr_seeder.api_key)
            has_tag = dsonarr.check_series_has_tags(updated_series, ["4K-protection"])
            assert has_tag is True

        finally:
            # Cleanup
            try:
                sonarr_client.del_series(series_id, delete_files=True)
            except Exception:
                pass

    def test_series_without_matching_tag(
        self, docker_services, sonarr_seeder, sonarr_client: SonarrAPI
    ):
        """Test that series without matching tag is not flagged as having it."""
        # Create a tag but don't assign it
        sonarr_seeder.create_tag("never-delete")

        # Add a test series without the tag
        test_series = {
            "title": "No Tag Series",
            "tvdbId": 305288,  # Stranger Things
            "seriesType": "standard",
        }
        result = sonarr_seeder.add_series(test_series)
        assert "id" in result, f"Failed to add test series: {result}"
        series_id = result["id"]

        try:
            # Verify the series doesn't have the tag
            dsonarr = DSonarr("TestSonarr", SONARR_URL, sonarr_seeder.api_key)
            series = sonarr_client.get_series(series_id)
            has_tag = dsonarr.check_series_has_tags(series, ["never-delete"])
            assert has_tag is False

        finally:
            try:
                sonarr_client.del_series(series_id, delete_files=True)
            except Exception:
                pass


class TestSonarrQualityProfileExclusions:
    """Test Sonarr quality profile-based exclusions."""

    def test_get_quality_profiles(
        self, docker_services, sonarr_seeder
    ):
        """Test that we can get quality profiles from Sonarr."""
        profiles = sonarr_seeder.get_quality_profiles()
        assert len(profiles) > 0
        # Default Sonarr has at least one quality profile
        assert "id" in profiles[0]
        assert "name" in profiles[0]

    def test_series_has_quality_profile(
        self, docker_services, sonarr_seeder, sonarr_client: SonarrAPI
    ):
        """Test quality profile detection on series."""
        # Add a test series
        test_series = {
            "title": "Quality Profile Test Series",
            "tvdbId": 328724,  # The Mandalorian
            "seriesType": "standard",
        }
        result = sonarr_seeder.add_series(test_series)
        assert "id" in result, f"Failed to add test series: {result}"
        series_id = result["id"]

        try:
            # Get the series and its quality profile
            series = sonarr_client.get_series(series_id)
            quality_profile_id = series["qualityProfileId"]

            # Get profile name
            profiles = sonarr_seeder.get_quality_profiles()
            profile_name = None
            for p in profiles:
                if p["id"] == quality_profile_id:
                    profile_name = p["name"]
                    break

            assert profile_name is not None

            # Verify DSonarr can detect the quality profile
            dsonarr = DSonarr("TestSonarr", SONARR_URL, sonarr_seeder.api_key)
            has_profile = dsonarr.check_series_has_quality_profiles(series, [profile_name])
            assert has_profile is True

            # Verify non-matching profile returns False
            has_fake_profile = dsonarr.check_series_has_quality_profiles(
                series, ["NonExistent-Profile-XYZ"]
            )
            assert has_fake_profile is False

        finally:
            try:
                sonarr_client.del_series(series_id, delete_files=True)
            except Exception:
                pass


class TestSonarrMonitoredStatusExclusions:
    """Test Sonarr monitored status-based exclusions."""

    @pytest.mark.xfail(
        reason="Sonarr API sometimes rejects monitored updates for newly added series"
    )
    def test_series_monitored_status(
        self, docker_services, sonarr_seeder, sonarr_client: SonarrAPI
    ):
        """Test that we can detect and update monitored status."""
        # Add a test series (by default, seeder sets monitored=False)
        # Using unique TVDB ID to avoid conflicts with seed data
        test_series = {
            "title": "Monitored Test Series",
            "tvdbId": 378426,  # Severance (different from seed data)
            "seriesType": "standard",
        }
        result = sonarr_seeder.add_series(test_series)
        assert "id" in result, f"Failed to add test series: {result}"
        series_id = result["id"]

        try:
            # Verify initial monitored status is False
            series = sonarr_client.get_series(series_id)
            assert series["monitored"] is False

            # Update monitored status to True - fetch fresh data to avoid stale state
            updated = sonarr_seeder.update_series_monitored(series_id, True)

            # Verify the change by fetching fresh data (Sonarr PUT response may not reflect change)
            series = sonarr_client.get_series(series_id)
            assert series["monitored"] is True

        finally:
            try:
                sonarr_client.del_series(series_id, delete_files=True)
            except Exception:
                pass


class TestSonarrPathExclusions:
    """Test Sonarr path-based exclusions."""

    def test_series_path_detection(
        self, docker_services, sonarr_seeder, sonarr_client: SonarrAPI
    ):
        """Test that series paths are correctly detected."""
        # Add a test series
        test_series = {
            "title": "Path Test Series",
            "tvdbId": 153021,  # The Walking Dead
            "rootFolderPath": "/tv",
            "seriesType": "standard",
        }
        result = sonarr_seeder.add_series(test_series)
        assert "id" in result, f"Failed to add test series: {result}"
        series_id = result["id"]

        try:
            # Get the series and verify path
            series = sonarr_client.get_series(series_id)
            assert "path" in series
            assert series["path"].startswith("/tv")

            # Path exclusion check (would be done in media_cleaner)
            excluded_paths = ["/tv"]
            series_path = series.get("path", "")
            is_excluded = any(path in series_path for path in excluded_paths)
            assert is_excluded is True

            # Non-matching path
            excluded_paths_4k = ["/media/4k"]
            is_excluded_4k = any(path in series_path for path in excluded_paths_4k)
            assert is_excluded_4k is False

        finally:
            try:
                sonarr_client.del_series(series_id, delete_files=True)
            except Exception:
                pass


class TestDSonarrIntegration:
    """Test DSonarr wrapper class with real Sonarr instance."""

    def test_dsonarr_connection(self, docker_services, sonarr_seeder):
        """Test DSonarr can connect to real Sonarr instance."""
        dsonarr = DSonarr("TestSonarr", SONARR_URL, sonarr_seeder.api_key)
        assert dsonarr.validate_connection() is True

    def test_dsonarr_get_tags_caches(
        self, docker_services, sonarr_seeder
    ):
        """Test that DSonarr caches tags after first call."""
        # Create a tag first
        sonarr_seeder.create_tag("cache-test-tag")

        dsonarr = DSonarr("TestSonarr", SONARR_URL, sonarr_seeder.api_key)

        # First call fetches from API
        tags1 = dsonarr.get_tags()
        assert len(tags1) > 0

        # Second call should use cache
        tags2 = dsonarr.get_tags()
        assert tags1 == tags2

    def test_dsonarr_get_quality_profiles_caches(
        self, docker_services, sonarr_seeder
    ):
        """Test that DSonarr caches quality profiles after first call."""
        dsonarr = DSonarr("TestSonarr", SONARR_URL, sonarr_seeder.api_key)

        # First call fetches from API
        profiles1 = dsonarr.get_quality_profiles()
        assert len(profiles1) > 0

        # Second call should use cache
        profiles2 = dsonarr.get_quality_profiles()
        assert profiles1 == profiles2

    def test_dsonarr_get_series(
        self, docker_services, sonarr_seeder, sonarr_client: SonarrAPI
    ):
        """Test DSonarr can get series from Sonarr."""
        # Add a test series
        test_series = {
            "title": "DSonarr Get Test Series",
            "tvdbId": 73545,  # Battlestar Galactica
            "seriesType": "standard",
        }
        result = sonarr_seeder.add_series(test_series)
        assert "id" in result, f"Failed to add test series: {result}"
        series_id = result["id"]

        try:
            dsonarr = DSonarr("TestSonarr", SONARR_URL, sonarr_seeder.api_key)
            series_list = dsonarr.get_series()

            assert len(series_list) > 0
            # Find our series
            found = any(s["id"] == series_id for s in series_list)
            assert found is True

        finally:
            try:
                sonarr_client.del_series(series_id, delete_files=True)
            except Exception:
                pass


class TestSonarrCombinedExclusions:
    """Test multiple Sonarr exclusion criteria together."""

    @pytest.mark.xfail(
        reason="Sonarr API sometimes rejects tag/monitored updates for newly added series"
    )
    def test_series_with_multiple_exclusion_criteria(
        self, docker_services, sonarr_seeder, sonarr_client: SonarrAPI
    ):
        """Test a series that matches multiple exclusion criteria."""
        # Create tags
        keep_tag = sonarr_seeder.create_tag("keep")
        favorite_tag = sonarr_seeder.create_tag("favorite")

        # Add a test series - using valid TVDB ID that doesn't conflict with seed data
        test_series = {
            "title": "Multi-Exclusion Test Series",
            "tvdbId": 296762,  # Westworld (correct TVDB ID)
            "seriesType": "standard",
        }
        result = sonarr_seeder.add_series(test_series)
        assert "id" in result, f"Failed to add test series: {result}"
        series_id = result["id"]

        try:
            # Add multiple tags in a single operation to avoid race conditions
            series_with_tags = sonarr_seeder.add_tags_to_series(
                series_id, [keep_tag["id"], favorite_tag["id"]]
            )

            # Verify tags were added before proceeding
            assert keep_tag["id"] in series_with_tags.get("tags", []), \
                f"Keep tag {keep_tag['id']} not in series tags: {series_with_tags.get('tags')}"
            assert favorite_tag["id"] in series_with_tags.get("tags", []), \
                f"Favorite tag {favorite_tag['id']} not in series tags: {series_with_tags.get('tags')}"

            # Update to monitored, passing the series to avoid race condition
            series = sonarr_seeder.update_series_monitored(
                series_id, True, series=series_with_tags
            )

            # Verify all criteria
            dsonarr = DSonarr("TestSonarr", SONARR_URL, sonarr_seeder.api_key)

            # Has both tags
            assert dsonarr.check_series_has_tags(series, ["keep"]) is True
            assert dsonarr.check_series_has_tags(series, ["favorite"]) is True
            assert dsonarr.check_series_has_tags(series, ["keep", "favorite"]) is True

            # Is monitored
            assert series["monitored"] is True

            # Has correct path
            assert series["path"].startswith("/tv")

            # Has a valid status
            assert series["status"] in ["continuing", "ended", "upcoming", "deleted"]

        finally:
            try:
                sonarr_client.del_series(series_id, delete_files=True)
            except Exception:
                pass
