# encoding: utf-8
"""Tests for the built-in scheduler module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from apscheduler.triggers.cron import CronTrigger

from app.scheduler import DeleterrScheduler, SCHEDULE_PRESETS


class TestSchedulePresets:
    """Tests for schedule preset definitions."""

    def test_hourly_preset(self):
        """Hourly preset runs every hour at minute 0."""
        assert SCHEDULE_PRESETS["hourly"] == "0 * * * *"

    def test_daily_preset(self):
        """Daily preset runs at 3 AM."""
        assert SCHEDULE_PRESETS["daily"] == "0 3 * * *"

    def test_weekly_preset(self):
        """Weekly preset runs on Sunday at 3 AM."""
        assert SCHEDULE_PRESETS["weekly"] == "0 3 * * 0"

    def test_monthly_preset(self):
        """Monthly preset runs on the 1st at 3 AM."""
        assert SCHEDULE_PRESETS["monthly"] == "0 3 1 * *"


class TestDeleterrScheduler:
    """Tests for DeleterrScheduler class."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock config object."""
        config = Mock()
        config.settings = {
            "scheduler": {
                "enabled": True,
                "schedule": "weekly",
                "timezone": "UTC",
                "run_on_startup": False,
            }
        }
        return config

    @pytest.fixture
    def scheduler(self, mock_config):
        """Create a DeleterrScheduler instance."""
        with patch("app.scheduler.BlockingScheduler"):
            return DeleterrScheduler(mock_config)

    def test_init_stores_config(self, mock_config):
        """Scheduler stores the config on init."""
        with patch("app.scheduler.BlockingScheduler"):
            scheduler = DeleterrScheduler(mock_config)
            assert scheduler.config == mock_config
            assert scheduler.scheduler_config == mock_config.settings["scheduler"]

    def test_parse_schedule_with_preset(self, scheduler):
        """Parsing a preset returns correct CronTrigger."""
        trigger = scheduler._parse_schedule("weekly")
        assert isinstance(trigger, CronTrigger)

    def test_parse_schedule_with_cron_expression(self, scheduler):
        """Parsing a cron expression returns correct CronTrigger."""
        trigger = scheduler._parse_schedule("0 4 * * 1")
        assert isinstance(trigger, CronTrigger)

    def test_parse_schedule_preset_case_insensitive(self, scheduler):
        """Preset names are case insensitive."""
        trigger1 = scheduler._parse_schedule("WEEKLY")
        trigger2 = scheduler._parse_schedule("Weekly")
        trigger3 = scheduler._parse_schedule("weekly")
        # All should create valid triggers
        assert isinstance(trigger1, CronTrigger)
        assert isinstance(trigger2, CronTrigger)
        assert isinstance(trigger3, CronTrigger)

    def test_parse_schedule_invalid_cron(self, scheduler):
        """Invalid cron expression raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            scheduler._parse_schedule("invalid")
        assert "Invalid cron expression" in str(exc_info.value)

    def test_parse_schedule_wrong_field_count(self, scheduler):
        """Cron expression with wrong field count raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            scheduler._parse_schedule("0 3 * *")  # Only 4 fields
        assert "Expected 5 fields" in str(exc_info.value)

    def test_parse_schedule_uses_config_timezone(self, mock_config):
        """Scheduler uses timezone from config."""
        mock_config.settings["scheduler"]["timezone"] = "America/New_York"
        with patch("app.scheduler.BlockingScheduler"):
            scheduler = DeleterrScheduler(mock_config)
            trigger = scheduler._parse_schedule("weekly")
            assert str(trigger.timezone) == "America/New_York"

    def test_run_deleterr_creates_deleterr_instance(self, scheduler):
        """Running deleterr creates a Deleterr instance."""
        with patch("app.deleterr.Deleterr") as mock_deleterr:
            scheduler._run_deleterr()
            mock_deleterr.assert_called_once_with(scheduler.config)

    def test_run_deleterr_catches_exceptions(self, scheduler):
        """Running deleterr catches and logs exceptions."""
        with patch("app.deleterr.Deleterr") as mock_deleterr:
            mock_deleterr.side_effect = Exception("Test error")
            # Should not raise
            scheduler._run_deleterr()

    def test_start_adds_job(self, scheduler):
        """Starting scheduler adds job to scheduler."""
        scheduler.scheduler = Mock()
        scheduler.scheduler.get_job = Mock(return_value=None)

        with patch.object(scheduler, "_parse_schedule") as mock_parse:
            mock_parse.return_value = Mock()
            with patch.object(scheduler.scheduler, "start"):
                try:
                    scheduler.start()
                except SystemExit:
                    pass  # Expected when scheduler stops

                scheduler.scheduler.add_job.assert_called_once()

    def test_start_runs_on_startup_when_configured(self, mock_config):
        """Scheduler runs immediately when run_on_startup is True."""
        mock_config.settings["scheduler"]["run_on_startup"] = True

        with patch("app.scheduler.BlockingScheduler") as mock_blocking_scheduler:
            mock_scheduler_instance = Mock()
            mock_scheduler_instance.get_job = Mock(return_value=Mock(next_run_time=None))
            mock_blocking_scheduler.return_value = mock_scheduler_instance

            scheduler = DeleterrScheduler(mock_config)

            with patch.object(scheduler, "_run_deleterr") as mock_run:
                with patch.object(scheduler, "_parse_schedule", return_value=Mock()):
                    mock_scheduler_instance.start.side_effect = KeyboardInterrupt()
                    try:
                        scheduler.start()
                    except (KeyboardInterrupt, SystemExit):
                        pass

                    mock_run.assert_called_once()


class TestSchedulerIntegration:
    """Integration tests for scheduler with config validation."""

    def test_scheduler_config_defaults(self):
        """Scheduler config has sensible defaults."""
        config = Mock()
        config.settings = {}  # No scheduler config

        with patch("app.scheduler.BlockingScheduler"):
            scheduler = DeleterrScheduler(config)
            assert scheduler.scheduler_config == {}

    def test_scheduler_with_all_presets(self):
        """All presets can be parsed successfully."""
        config = Mock()
        config.settings = {"scheduler": {"timezone": "UTC"}}

        with patch("app.scheduler.BlockingScheduler"):
            scheduler = DeleterrScheduler(config)

            for preset in SCHEDULE_PRESETS.keys():
                trigger = scheduler._parse_schedule(preset)
                assert isinstance(trigger, CronTrigger)

    def test_common_cron_expressions(self):
        """Common cron expressions parse successfully."""
        config = Mock()
        config.settings = {"scheduler": {"timezone": "UTC"}}

        expressions = [
            "0 0 * * *",      # Midnight daily
            "0 3 * * 0",      # Sunday 3am
            "0 */4 * * *",    # Every 4 hours
            "30 2 * * 1-5",   # Weekdays at 2:30am
            "0 0 1,15 * *",   # 1st and 15th of month
        ]

        with patch("app.scheduler.BlockingScheduler"):
            scheduler = DeleterrScheduler(config)

            for expr in expressions:
                trigger = scheduler._parse_schedule(expr)
                assert isinstance(trigger, CronTrigger)
