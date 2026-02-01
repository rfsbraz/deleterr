"""
Integration tests for Deleterr's Sonarr wrapper (DSonarr).

These tests verify that Deleterr's DSonarr wrapper correctly delegates to the
pyarr library against a real Sonarr instance. This catches issues like method
name typos that unit tests with MagicMock won't detect.
"""

import pytest
from pyarr.sonarr import SonarrAPI

from app.modules.sonarr import DSonarr

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestDSonarrWrapper:
    """Test DSonarr wrapper class with real Sonarr instance.

    These tests verify that the application's wrapper class correctly
    delegates to the pyarr library. This catches issues like method name
    typos that unit tests with MagicMock won't detect.
    """

    def test_dsonarr_validate_connection(self, dsonarr_client: DSonarr):
        """Verify DSonarr can validate connection to real Sonarr."""
        assert dsonarr_client.validate_connection() is True

    def test_dsonarr_get_disk_space(self, dsonarr_client: DSonarr):
        """Verify DSonarr.get_disk_space() works with real Sonarr.

        This test would have caught issue #177 where the wrapper called
        get_diskspace() instead of get_disk_space().
        """
        disk_space = dsonarr_client.get_disk_space()
        assert isinstance(disk_space, list)

        if disk_space:
            space = disk_space[0]
            assert "path" in space
            assert "freeSpace" in space
            assert "totalSpace" in space

    def test_dsonarr_get_series(self, dsonarr_client: DSonarr, seeded_sonarr):
        """Verify DSonarr.get_series() works with real Sonarr."""
        series = dsonarr_client.get_series()
        assert isinstance(series, list)
        assert len(series) > 0

    def test_dsonarr_get_tags(self, dsonarr_client: DSonarr):
        """Verify DSonarr.get_tags() works with real Sonarr."""
        tags = dsonarr_client.get_tags()
        assert isinstance(tags, list)

    def test_dsonarr_get_quality_profiles(self, dsonarr_client: DSonarr):
        """Verify DSonarr.get_quality_profiles() works with real Sonarr."""
        profiles = dsonarr_client.get_quality_profiles()
        assert isinstance(profiles, list)
        assert len(profiles) > 0
