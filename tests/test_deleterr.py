import sys
import unittest
from unittest.mock import MagicMock, patch

import pytest

from app.deleterr import Deleterr, acquire_instance_lock, release_instance_lock, main


@pytest.fixture
def deleterr():
    with patch("app.deleterr.MediaCleaner", return_value=MagicMock()):
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
    deleterr.media_cleaner.process_library_movies = MagicMock(return_value=1000)

    # Act
    deleterr.process_radarr()

    # Assert
    deleterr.media_cleaner.process_library_movies.assert_called_once_with(
        {"radarr": "Radarr1"},
        deleterr.radarr["Radarr1"],
    )


@patch("app.deleterr.DSonarr")
@patch("app.modules.radarr.DRadarr")
def test_process_sonarr(radarr_mock, sonarr_mock, deleterr):
    # Arrange
    deleterr.sonarr = {
        "Sonarr1": MagicMock(
            get_series=MagicMock(return_value=[{"title": "Test Movie"}])
        ),
    }
    deleterr.config.settings = {
        "libraries": [{"sonarr": "Sonarr1"}],
    }
    deleterr.media_cleaner.process_library = MagicMock(return_value=1000)

    # Act
    deleterr.process_sonarr()

    # Assert
    deleterr.media_cleaner.process_library.assert_called_once_with(
        {"sonarr": "Sonarr1"},
        deleterr.sonarr["Sonarr1"],
        [{"title": "Test Movie"}],
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
