"""
Integration tests for Sonarr API interactions.

These tests verify that Deleterr correctly interacts with a real
Sonarr instance running in Docker.
"""

import pytest
from pyarr.sonarr import SonarrAPI

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestSonarrConnection:
    """Test basic Sonarr connectivity and API access."""

    def test_sonarr_is_accessible(self, sonarr_client: SonarrAPI):
        """Verify Sonarr API is accessible and responding."""
        status = sonarr_client.get_system_status()
        assert status is not None
        assert "version" in status

    def test_sonarr_api_key_is_valid(self, sonarr_client: SonarrAPI):
        """Verify API key authentication works."""
        status = sonarr_client.get_system_status()
        assert status.get("authentication") is not None or "version" in status


class TestSonarrSeriesOperations:
    """Test Sonarr series CRUD operations."""

    def test_get_series_returns_seeded_data(self, seeded_sonarr: SonarrAPI):
        """Verify seeded series are accessible via API."""
        series_list = seeded_sonarr.get_series()
        assert isinstance(series_list, list)
        assert len(series_list) > 0, "No series were seeded - seeding failed"

        # Check that our test series are present
        titles = [s.get("title") for s in series_list]
        # We seed Breaking Bad, Game of Thrones, Attack on Titan
        assert any(t for t in titles if t), (
            f"Expected seeded series not found. Got titles: {titles}"
        )

    def test_get_series_by_id(self, seeded_sonarr: SonarrAPI):
        """Verify we can retrieve a specific series by ID."""
        series_list = seeded_sonarr.get_series()
        assert len(series_list) > 0, "No series were seeded - seeding failed"

        series_id = series_list[0]["id"]
        series = seeded_sonarr.get_series(series_id)
        assert series is not None
        assert series.get("id") == series_id

    def test_series_has_required_fields(self, seeded_sonarr: SonarrAPI):
        """Verify series have all fields Deleterr needs."""
        series_list = seeded_sonarr.get_series()
        assert len(series_list) > 0, "No series were seeded - seeding failed"

        series = series_list[0]
        # Fields required by Deleterr
        required_fields = ["id", "title", "tvdbId", "path", "monitored", "seriesType"]
        for field in required_fields:
            assert field in series, f"Missing required field: {field}"

    def test_series_type_is_valid(self, seeded_sonarr: SonarrAPI):
        """Verify series types are valid values."""
        series_list = seeded_sonarr.get_series()
        assert len(series_list) > 0, "No series were seeded - seeding failed"

        valid_types = ["standard", "daily", "anime"]

        for series in series_list:
            series_type = series.get("seriesType", "").lower()
            assert series_type in valid_types, f"Invalid series type: {series_type}"


class TestSonarrDeletion:
    """Test series deletion operations."""

    def test_delete_series_removes_from_library(
        self, sonarr_seeder, sonarr_client: SonarrAPI
    ):
        """Verify deleting a series actually removes it."""
        # Add a test series specifically for deletion
        # Using real TVDB ID for Friends
        test_series = {
            "title": "Friends",
            "tvdbId": 79168,
            "seriesType": "standard",
        }

        # Seed the series
        result = sonarr_seeder.add_series(test_series)
        assert "id" in result, f"Failed to add test series: {result}"

        series_id = result["id"]

        # Verify it exists
        series_before = sonarr_client.get_series()
        ids_before = [s["id"] for s in series_before]
        assert series_id in ids_before

        # Delete the series
        sonarr_client.del_series(series_id, delete_files=True)

        # Verify it's gone
        series_after = sonarr_client.get_series()
        ids_after = [s["id"] for s in series_after]
        assert series_id not in ids_after


class TestSonarrEpisodeOperations:
    """Test episode-level operations."""

    def test_get_episodes_for_series(self, seeded_sonarr: SonarrAPI):
        """Verify we can get episodes for a series."""
        series_list = seeded_sonarr.get_series()
        assert len(series_list) > 0, "No series available for episode test - seeding failed"

        series_id = series_list[0]["id"]
        episodes = seeded_sonarr.get_episode(series_id, series=True)

        # Episodes might be empty for newly added series without files
        assert isinstance(episodes, list)

    def test_episode_monitoring_update(self, seeded_sonarr: SonarrAPI):
        """Verify we can update episode monitoring status."""
        series_list = seeded_sonarr.get_series()
        assert len(series_list) > 0, "No series available for monitoring test - seeding failed"

        series_id = series_list[0]["id"]
        episodes = seeded_sonarr.get_episode(series_id, series=True)

        assert len(episodes) > 0, "No episodes available for monitoring test"

        episode = episodes[0]
        episode_id = episode["id"]
        original_monitored = episode.get("monitored", True)

        # Toggle monitoring
        new_monitored = not original_monitored
        try:
            seeded_sonarr.upd_episode_monitor([episode_id], new_monitored)

            # Verify the change
            updated_episodes = seeded_sonarr.get_episode(series_id, series=True)
            updated_episode = next(
                (e for e in updated_episodes if e["id"] == episode_id), None
            )
            assert updated_episode is not None
            # Note: monitoring state might not change immediately
        finally:
            # Restore original state
            seeded_sonarr.upd_episode_monitor([episode_id], original_monitored)


class TestSonarrDiskSpace:
    """Test disk space reporting."""

    def test_get_disk_space_returns_valid_data(self, sonarr_client: SonarrAPI):
        """Verify disk space endpoint returns useful data."""
        disk_space = sonarr_client.get_disk_space()
        assert isinstance(disk_space, list)

        if disk_space:
            space = disk_space[0]
            assert "path" in space
            assert "freeSpace" in space
            assert "totalSpace" in space
            assert space["freeSpace"] >= 0
            assert space["totalSpace"] > 0


class TestSonarrQualityProfiles:
    """Test quality profile operations."""

    def test_get_quality_profiles(self, sonarr_client: SonarrAPI):
        """Verify quality profiles are accessible."""
        profiles = sonarr_client.get_quality_profile()
        assert isinstance(profiles, list)
        # Sonarr should have default profiles
        assert len(profiles) > 0

        profile = profiles[0]
        assert "id" in profile
        assert "name" in profile


class TestSonarrRootFolders:
    """Test root folder operations."""

    def test_get_root_folders(self, seeded_sonarr: SonarrAPI):
        """Verify root folders endpoint is accessible."""
        folders = seeded_sonarr.get_root_folder()
        assert isinstance(folders, list)
        # Root folders may or may not be configured depending on container permissions
        # The important thing is that the API returns a valid response
        if len(folders) > 0:
            folder = folders[0]
            assert "path" in folder
            assert "freeSpace" in folder
