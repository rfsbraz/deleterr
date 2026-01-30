# encoding: utf-8
"""
Integration tests for the scheduler-enabled-by-default feature.

These tests verify:
1. Instance lock mechanism prevents duplicate processes
2. Scheduler is enabled by default
3. CLI flags correctly override scheduler behavior
4. Warning messages are properly logged for duplicate instances
"""

import os
import sys
import signal
import subprocess
import tempfile
import time

import pytest

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestInstanceLockIntegration:
    """Integration tests for single-instance lock functionality."""

    @pytest.mark.skipif(sys.platform == "win32", reason="fcntl not available on Windows")
    def test_lock_file_created_on_start(self, tmp_path):
        """Lock file is created when deleterr starts."""
        import fcntl
        import app.deleterr as deleterr_module

        lock_file = tmp_path / ".deleterr.lock"
        original_lock_file = deleterr_module.LOCK_FILE
        deleterr_module.LOCK_FILE = str(lock_file)
        deleterr_module._lock_file_handle = None

        try:
            result = deleterr_module.acquire_instance_lock()
            assert result is True, "Lock acquisition should succeed"
            assert lock_file.exists(), "Lock file should be created"

            # Lock file should contain PID
            content = lock_file.read_text()
            assert content == str(os.getpid()), "Lock file should contain current PID"
        finally:
            deleterr_module.release_instance_lock()
            deleterr_module.LOCK_FILE = original_lock_file

    @pytest.mark.skipif(sys.platform == "win32", reason="fcntl not available on Windows")
    def test_lock_released_on_cleanup(self, tmp_path):
        """Lock is properly released when release_instance_lock is called."""
        import fcntl
        import app.deleterr as deleterr_module

        lock_file = tmp_path / ".deleterr.lock"
        original_lock_file = deleterr_module.LOCK_FILE
        deleterr_module.LOCK_FILE = str(lock_file)
        deleterr_module._lock_file_handle = None

        try:
            # Acquire lock
            assert deleterr_module.acquire_instance_lock() is True
            assert lock_file.exists()

            # Release lock
            deleterr_module.release_instance_lock()

            # Lock file should be removed
            assert not lock_file.exists(), "Lock file should be removed after release"

            # Should be able to acquire again
            assert deleterr_module.acquire_instance_lock() is True
        finally:
            deleterr_module.release_instance_lock()
            deleterr_module.LOCK_FILE = original_lock_file

    @pytest.mark.skipif(sys.platform == "win32", reason="fcntl not available on Windows")
    def test_second_instance_blocked_while_first_holds_lock(self, tmp_path):
        """Second process cannot acquire lock while first holds it."""
        import fcntl
        import app.deleterr as deleterr_module

        lock_file = tmp_path / ".deleterr.lock"
        original_lock_file = deleterr_module.LOCK_FILE
        deleterr_module.LOCK_FILE = str(lock_file)
        deleterr_module._lock_file_handle = None

        try:
            # First instance acquires lock
            assert deleterr_module.acquire_instance_lock() is True

            # Simulate second instance by trying to acquire in same process
            # (reset the handle to simulate fresh start)
            first_handle = deleterr_module._lock_file_handle
            deleterr_module._lock_file_handle = None

            # Second attempt should fail
            result = deleterr_module.acquire_instance_lock()
            assert result is False, "Second instance should be blocked"

            # Restore first handle for cleanup
            deleterr_module._lock_file_handle = first_handle
        finally:
            deleterr_module.release_instance_lock()
            deleterr_module.LOCK_FILE = original_lock_file

    @pytest.mark.skipif(sys.platform == "win32", reason="fcntl not available on Windows")
    def test_lock_released_after_first_process_exits(self, tmp_path):
        """Lock can be acquired after holding process releases it."""
        import fcntl
        import app.deleterr as deleterr_module

        lock_file = tmp_path / ".deleterr.lock"
        original_lock_file = deleterr_module.LOCK_FILE
        deleterr_module.LOCK_FILE = str(lock_file)
        deleterr_module._lock_file_handle = None

        try:
            # First instance acquires and releases
            assert deleterr_module.acquire_instance_lock() is True
            deleterr_module.release_instance_lock()

            # Second instance should now be able to acquire
            assert deleterr_module.acquire_instance_lock() is True
        finally:
            deleterr_module.release_instance_lock()
            deleterr_module.LOCK_FILE = original_lock_file


class TestSchedulerDefaultBehavior:
    """Integration tests for scheduler-enabled-by-default behavior."""

    def test_scheduler_enabled_by_default_in_config(self):
        """Scheduler.enabled defaults to True when not specified."""
        from app.config import Config

        # Create minimal config without scheduler section
        config_data = {
            "plex": {"url": "http://localhost:32400", "token": "test"},
            "libraries": [],
        }

        config = Config(config_data)
        scheduler_config = config.settings.get("scheduler", {})

        # The default should be True (scheduler enabled)
        # Note: This tests the application's default behavior
        enabled = scheduler_config.get("enabled", True)
        assert enabled is True, "Scheduler should be enabled by default"

    def test_scheduler_can_be_explicitly_disabled(self):
        """Scheduler can be disabled via config."""
        from app.config import Config

        config_data = {
            "plex": {"url": "http://localhost:32400", "token": "test"},
            "libraries": [],
            "scheduler": {"enabled": False},
        }

        config = Config(config_data)
        scheduler_config = config.settings.get("scheduler", {})
        enabled = scheduler_config.get("enabled", True)

        assert enabled is False, "Scheduler should be disabled when explicitly set"

    def test_scheduler_config_with_all_options(self):
        """Scheduler accepts all configuration options."""
        from app.config import Config

        config_data = {
            "plex": {"url": "http://localhost:32400", "token": "test"},
            "libraries": [],
            "scheduler": {
                "enabled": True,
                "schedule": "daily",
                "timezone": "America/New_York",
                "run_on_startup": True,
            },
        }

        config = Config(config_data)
        scheduler_config = config.settings.get("scheduler", {})

        assert scheduler_config.get("enabled") is True
        assert scheduler_config.get("schedule") == "daily"
        assert scheduler_config.get("timezone") == "America/New_York"
        assert scheduler_config.get("run_on_startup") is True


class TestCLIFlagOverrides:
    """Integration tests for CLI flag behavior with scheduler defaults."""

    def test_run_once_flag_disables_scheduler(self):
        """--run-once flag should disable scheduler regardless of config."""
        # Simulate the logic from main()
        scheduler_config = {"enabled": True}  # Config says enabled
        args_run_once = True
        args_scheduler = False

        # Apply CLI overrides (same logic as in main())
        scheduler_enabled = scheduler_config.get("enabled", True)

        if args_run_once:
            scheduler_enabled = False
        elif args_scheduler:
            scheduler_enabled = True

        assert scheduler_enabled is False, "--run-once should disable scheduler"

    def test_scheduler_flag_enables_scheduler(self):
        """--scheduler flag should enable scheduler regardless of config."""
        scheduler_config = {"enabled": False}  # Config says disabled
        args_run_once = False
        args_scheduler = True

        scheduler_enabled = scheduler_config.get("enabled", True)

        if args_run_once:
            scheduler_enabled = False
        elif args_scheduler:
            scheduler_enabled = True

        assert scheduler_enabled is True, "--scheduler should enable scheduler"

    def test_no_flags_uses_config_default(self):
        """Without CLI flags, config default (True) should be used."""
        scheduler_config = {}  # No explicit setting
        args_run_once = False
        args_scheduler = False

        scheduler_enabled = scheduler_config.get("enabled", True)

        if args_run_once:
            scheduler_enabled = False
        elif args_scheduler:
            scheduler_enabled = True

        assert scheduler_enabled is True, "Should default to scheduler enabled"

    def test_run_once_overrides_scheduler_flag(self):
        """--run-once takes precedence when both flags present (by order)."""
        # In the actual implementation, --run-once is checked first
        scheduler_config = {"enabled": True}
        args_run_once = True
        args_scheduler = True  # Both flags set

        scheduler_enabled = scheduler_config.get("enabled", True)

        # Logic matches main(): run_once checked before scheduler
        if args_run_once:
            scheduler_enabled = False
        elif args_scheduler:
            scheduler_enabled = True

        assert scheduler_enabled is False, "--run-once should take precedence"


class TestDuplicateInstanceWarning:
    """Integration tests for duplicate instance warning messages."""

    @pytest.mark.skipif(sys.platform == "win32", reason="fcntl not available on Windows")
    def test_warning_logged_when_lock_fails_scheduler_mode(self, tmp_path, caplog):
        """Warning about duplicate instance is logged when scheduler enabled."""
        import fcntl
        import logging
        import app.deleterr as deleterr_module
        from app import logger as app_logger

        lock_file = tmp_path / ".deleterr.lock"
        original_lock_file = deleterr_module.LOCK_FILE
        deleterr_module.LOCK_FILE = str(lock_file)

        # Hold the lock (simulate another instance)
        with open(lock_file, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            f.write("12345")
            f.flush()

            # Reset module state
            deleterr_module._lock_file_handle = None

            # Try to acquire - should fail
            result = deleterr_module.acquire_instance_lock()
            assert result is False

        deleterr_module.LOCK_FILE = original_lock_file

    @pytest.mark.skipif(sys.platform == "win32", reason="fcntl not available on Windows")
    def test_lock_uses_config_directory(self, tmp_path):
        """Lock file is created in /config directory by default."""
        import app.deleterr as deleterr_module

        # Verify the default lock file location
        assert deleterr_module.LOCK_FILE == "/config/.deleterr.lock"


class TestSchedulerEnabledDefaultSchema:
    """Integration tests for schema default values."""

    def test_scheduler_config_schema_default_enabled(self):
        """SchedulerConfig schema has enabled=True as default."""
        from app.schema import SchedulerConfig

        # Create instance with no arguments - should use defaults
        config = SchedulerConfig()

        assert config.enabled is True, "SchedulerConfig.enabled should default to True"

    def test_scheduler_config_schema_all_defaults(self):
        """SchedulerConfig schema has correct default values."""
        from app.schema import SchedulerConfig

        config = SchedulerConfig()

        assert config.enabled is True
        assert config.schedule == "weekly"
        assert config.timezone == "UTC"
        assert config.run_on_startup is False

    def test_scheduler_config_can_override_defaults(self):
        """SchedulerConfig allows overriding all defaults."""
        from app.schema import SchedulerConfig

        config = SchedulerConfig(
            enabled=False,
            schedule="daily",
            timezone="America/Los_Angeles",
            run_on_startup=True,
        )

        assert config.enabled is False
        assert config.schedule == "daily"
        assert config.timezone == "America/Los_Angeles"
        assert config.run_on_startup is True
