import sys
import unittest
from unittest.mock import MagicMock, patch

import pytest

from app.deleterr import Deleterr, acquire_instance_lock, release_instance_lock, main


@pytest.fixture
def deleterr():
    with patch("app.deleterr.MediaCleaner", return_value=MagicMock()), \
         patch("app.deleterr.PlexMediaServer", return_value=MagicMock()), \
         patch("app.deleterr.StateManager", return_value=MagicMock()):
        yield Deleterr(MagicMock())


@patch("app.deleterr.DSonarr")
@patch("app.modules.radarr.DRadarr")
def test_process_radarr(radarr_mock, sonarr_mock, deleterr):
    # Arrange
    deleterr.radarr = {
        "Radarr1": MagicMock(
            get_movie=MagicMock(return_value=[{"title": "Test Movie"}])
        ),
    }
    deleterr.config.settings = {
        "libraries": [{"radarr": "Radarr1"}],
    }
    # Return 3-tuple (saved_space, deleted_items, preview_candidates)
    deleterr.media_cleaner.process_library_movies = MagicMock(return_value=(1000, [{"title": "Test Movie"}], []))

    # Act
    deleterr.process_radarr()

    # Assert
    deleterr.media_cleaner.process_library_movies.assert_called_once_with(
        {"radarr": "Radarr1"},
        deleterr.radarr["Radarr1"],
    )


@patch("app.deleterr.DSonarr")
@patch("app.modules.radarr.DRadarr")
def test_process_radarr_trakt_failure_skips_library(radarr_mock, sonarr_mock, deleterr):
    """A Trakt outage must skip the library (no deletions) instead of crashing."""
    from app.modules.trakt import TraktError

    # Arrange
    deleterr.radarr = {"Radarr1": MagicMock()}
    deleterr.config.settings = {
        "libraries": [{"radarr": "Radarr1"}],
    }
    deleterr.media_cleaner.process_library_movies = MagicMock(
        side_effect=TraktError("Failed to fetch Trakt list 'watchlist' for movies")
    )
    deleterr.run_result = MagicMock()
    failed_before = deleterr.libraries_failed
    processed_before = deleterr.libraries_processed

    # Act - must not raise
    deleterr.process_radarr()

    # Assert - library counted as failed, nothing deleted
    assert deleterr.libraries_failed == failed_before + 1
    assert deleterr.libraries_processed == processed_before
    deleterr.run_result.add_deleted.assert_not_called()


@patch("app.deleterr.DSonarr")
@patch("app.modules.radarr.DRadarr")
def test_process_sonarr(radarr_mock, sonarr_mock, deleterr):
    # Arrange
    deleterr.sonarr = {
        "Sonarr1": MagicMock(
            get_series=MagicMock(return_value=[{"title": "Test Show"}])
        ),
    }
    deleterr.config.settings = {
        "libraries": [{"sonarr": "Sonarr1"}],
    }
    # Return 3-tuple (saved_space, deleted_items, preview_candidates)
    deleterr.media_cleaner.process_library = MagicMock(return_value=(1000, [{"title": "Test Show"}], []))

    # Act
    deleterr.process_sonarr()

    # Assert
    deleterr.media_cleaner.process_library.assert_called_once_with(
        {"sonarr": "Sonarr1"},
        deleterr.sonarr["Sonarr1"],
        [{"title": "Test Show"}],
    )


class TestInstanceLock:
    """Tests for single-instance lock functionality."""

    def test_acquire_lock_returns_true_on_windows(self):
        """On Windows, lock is skipped and always returns True."""
        with patch.object(sys, "platform", "win32"):
            # Reset the global lock handle
            import app.deleterr
            app.deleterr._lock_file_handle = None
            assert acquire_instance_lock() is True

    @pytest.mark.skipif(sys.platform == "win32", reason="fcntl not available on Windows")
    def test_acquire_lock_succeeds_when_no_other_instance(self, tmp_path):
        """Lock acquisition succeeds when no other instance holds it."""
        import app.deleterr

        # Use a temp file for testing
        lock_file = tmp_path / ".deleterr.lock"
        original_lock_file = app.deleterr.LOCK_FILE
        app.deleterr.LOCK_FILE = str(lock_file)
        app.deleterr._lock_file_handle = None

        try:
            assert acquire_instance_lock() is True
            assert lock_file.exists()
        finally:
            release_instance_lock()
            app.deleterr.LOCK_FILE = original_lock_file

    @pytest.mark.skipif(sys.platform == "win32", reason="fcntl not available on Windows")
    def test_acquire_lock_fails_when_already_locked(self, tmp_path):
        """Lock acquisition fails when another instance holds the lock."""
        import fcntl
        import app.deleterr

        lock_file = tmp_path / ".deleterr.lock"
        original_lock_file = app.deleterr.LOCK_FILE
        app.deleterr.LOCK_FILE = str(lock_file)
        app.deleterr._lock_file_handle = None

        try:
            # Simulate another instance holding the lock
            with open(lock_file, "w") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                f.write("12345")
                f.flush()

                # Now try to acquire from "our" instance
                assert acquire_instance_lock() is False
        finally:
            app.deleterr.LOCK_FILE = original_lock_file
            app.deleterr._lock_file_handle = None
