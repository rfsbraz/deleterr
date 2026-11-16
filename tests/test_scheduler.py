# encoding: utf-8
"""Tests for the built-in scheduler module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from apscheduler.triggers.cron import CronTrigger

from app.scheduler import DeleterrScheduler, SCHEDULE_PRESETS


@pytest.fixture(autouse=True)
def _last_run_file(tmp_path, monkeypatch):
    """Keep scheduler tests from writing the real /config last run file."""
    monkeypatch.setattr("app.scheduler.LAST_RUN_FILE", str(tmp_path / ".deleterr_last_run.json"))


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


class TestScheduledRunFailure:
    """A crashed scheduled run must notify and record a failed status (#293)."""

    HOOK_URL = "http://hook.test/deleterr"

    @pytest.fixture
    def scheduler(self, tmp_path):
        config = Mock()
        config.settings = {
            "dry_run": False,
            "plex": {"url": "http://plex.test:32400", "token": "plex-token"},
            "scheduler": {"enabled": True, "schedule": "weekly"},
            "notifications": {"webhook": {"url": self.HOOK_URL}},
        }
        with patch("app.scheduler.BlockingScheduler"):
            s = DeleterrScheduler(config)
        s.last_run_file = str(tmp_path / ".deleterr_last_run.json")
        return s

    def _last_run(self, scheduler):
        import json

        with open(scheduler.last_run_file, encoding="utf-8") as f:
            return json.load(f)

    def _sent_payloads(self, mock_request):
        return [c.kwargs["json"] for c in mock_request.call_args_list]

    @patch("app.modules.notifications.providers.webhook.requests.request")
    def test_crash_in_deleterr_init_notifies_and_records_failure(self, mock_request, scheduler):
        with patch(
            "app.deleterr.PlexMediaServer",
            side_effect=Exception("401 Unauthorized for http://plex.test/?X-Plex-Token=plex-token"),
        ):
            scheduler._run_deleterr()

        payloads = self._sent_payloads(mock_request)
        assert len(payloads) == 1
        assert payloads[0]["type"] == "deleterr_run_failed"
        assert "401 Unauthorized" in payloads[0]["error"]
        assert "plex-token" not in payloads[0]["error"]

        last_run = self._last_run(scheduler)
        assert last_run["status"] == "failed"
        assert "401 Unauthorized" in last_run["error"]
        assert "plex-token" not in last_run["error"]
        assert last_run["timestamp"]

    @patch("app.modules.notifications.providers.webhook.requests.request")
    def test_crash_during_run_notifies_and_records_failure(self, mock_request, scheduler):
        with patch("app.deleterr.PlexMediaServer"), \
             patch("app.deleterr.MediaCleaner"), \
             patch("app.deleterr.StateManager"), \
             patch("app.deleterr.NotificationManager"), \
             patch("app.deleterr.Deleterr.process_radarr", side_effect=RuntimeError("Radarr went away")):
            scheduler._run_deleterr()

        payloads = self._sent_payloads(mock_request)
        assert len(payloads) == 1
        assert payloads[0]["type"] == "deleterr_run_failed"
        assert "Radarr went away" in payloads[0]["error"]

        last_run = self._last_run(scheduler)
        assert last_run["status"] == "failed"
        assert "Radarr went away" in last_run["error"]

    @patch("app.modules.notifications.providers.webhook.requests.request")
    def test_successful_run_records_success_without_failure_notification(self, mock_request, scheduler):
        with patch("app.deleterr.Deleterr") as mock_deleterr:
            mock_deleterr.return_value.has_fatal_errors.return_value = False
            mock_deleterr.return_value.library_failures = []
            scheduler._run_deleterr()

        mock_request.assert_not_called()
        last_run = self._last_run(scheduler)
        assert last_run["status"] == "success"
        assert last_run["error"] is None

    @patch("app.modules.notifications.providers.webhook.requests.request")
    def test_all_libraries_failing_on_config_notifies_and_records_failure(self, mock_request, scheduler):
        from app.media_cleaner import ConfigurationError

        scheduler.config.settings["radarr"] = [{"name": "Radarr", "url": "http://radarr.test", "api_key": "k"}]
        scheduler.config.settings["libraries"] = [
            {"name": "Movies", "radarr": "Radarr"},
            {"name": "Kids Movies", "radarr": "Radarr"},
        ]
        errors = {
            "Movies": ConfigurationError("Radarr rejected http://radarr.test/api?apikey=radarr-secret"),
            "Kids Movies": ConfigurationError("Unknown sort field 'size_on_disk'"),
        }
        cleaner = MagicMock()
        cleaner.process_library_movies.side_effect = lambda library, instance: (_ for _ in ()).throw(
            errors[library["name"]]
        )

        with patch("app.deleterr.PlexMediaServer"), \
             patch("app.deleterr.MediaCleaner", return_value=cleaner), \
             patch("app.deleterr.StateManager"), \
             patch("app.deleterr.NotificationManager") as manager, \
             patch("app.deleterr.DRadarr"):
            manager.return_value.send_run_failure.return_value = False
            assert scheduler._run_deleterr() is False

        payloads = self._sent_payloads(mock_request)
        assert len(payloads) == 1
        assert payloads[0]["type"] == "deleterr_run_failed"
        error = payloads[0]["error"]
        assert "All libraries failed" in error
        assert "Movies: Radarr rejected" in error
        assert "Kids Movies: Unknown sort field 'size_on_disk'" in error
        assert "radarr-secret" not in error
        assert "[REDACTED]; Kids Movies" in error

        last_run = self._last_run(scheduler)
        assert last_run["status"] == "failed"
        assert last_run["error"] == error

    @patch("app.modules.notifications.providers.webhook.requests.request")
    def test_some_libraries_failing_records_partial_and_reports_them_redacted(self, mock_request, scheduler):
        from app.media_cleaner import ConfigurationError

        scheduler.config.settings["radarr"] = [
            {"name": "Radarr", "url": "http://radarr.test", "api_key": "radarr-secret"}
        ]
        scheduler.config.settings["libraries"] = [
            {"name": "Movies", "radarr": "Radarr"},
            {"name": "Kids Movies", "radarr": "Radarr"},
        ]
        movie = {"title": "Synthetic Movie", "year": 2001, "sizeOnDisk": 1000}

        def process(library, instance):
            if library["name"] == "Kids Movies":
                raise ConfigurationError(
                    "Radarr rejected http://radarr.test/api/v3/movie?apikey=radarr-secret "
                    "(key radarr-secret) via http://admin:hunter2@proxy.test/ "
                    "with X-Plex-Token=plex-token"
                )
            return 1000, [movie], []

        cleaner = MagicMock()
        cleaner.process_library_movies.side_effect = process

        with patch("app.deleterr.PlexMediaServer"), \
             patch("app.deleterr.MediaCleaner", return_value=cleaner), \
             patch("app.deleterr.StateManager"), \
             patch("app.deleterr.DRadarr"):
            assert scheduler._run_deleterr() is True

        payloads = self._sent_payloads(mock_request)
        assert len(payloads) == 1
        payload = payloads[0]
        assert payload["type"] == "deleterr_run_complete"
        assert payload["summary"]["deleted_count"] == 1
        assert [f["library"] for f in payload["failed_libraries"]] == ["Kids Movies"]
        error = payload["failed_libraries"][0]["error"]
        assert "Radarr rejected" in error

        last_run = self._last_run(scheduler)
        assert last_run["status"] == "partial"
        assert last_run["error"].startswith("Some libraries failed: Kids Movies: Radarr rejected")

        for text in (str(payload), last_run["error"]):
            assert "radarr-secret" not in text
            assert "hunter2" not in text
            assert "plex-token" not in text

    def test_failing_notification_does_not_break_the_scheduler(self, scheduler):
        with patch("app.deleterr.Deleterr", side_effect=Exception("boom")), \
             patch("app.modules.notifications.NotificationManager.send_run_failure", side_effect=Exception("smtp down")):
            assert scheduler._run_deleterr() is True

        assert self._last_run(scheduler)["status"] == "failed"


class TestLastRunStats:
    """The last-run file also records counts and the schedule interval (#294)."""

    @pytest.fixture
    def scheduler(self, tmp_path):
        config = Mock()
        config.settings = {
            "dry_run": False,
            "scheduler": {"enabled": True, "schedule": "weekly", "timezone": "UTC"},
        }
        with patch("app.scheduler.BlockingScheduler"):
            s = DeleterrScheduler(config)
        s.last_run_file = str(tmp_path / ".deleterr_last_run.json")
        return s

    def _last_run(self, scheduler):
        import json

        with open(scheduler.last_run_file, encoding="utf-8") as f:
            return json.load(f)

    def test_successful_run_records_counts_and_interval(self, scheduler):
        from app.modules.notifications.models import DeletedItem, RunResult

        result = RunResult(
            is_dry_run=False,
            deleted_items=[
                DeletedItem("A", 2020, "movie", 1, "Movies", "Radarr"),
            ],
            preview_items=[
                DeletedItem("B", 2021, "movie", 2, "Movies", "Radarr"),
                DeletedItem("C", 2022, "movie", 3, "Movies", "Radarr"),
            ],
        )
        with patch("app.deleterr.Deleterr") as mock_deleterr:
            instance = mock_deleterr.return_value
            instance.has_fatal_errors.return_value = False
            instance.library_failures = []
            instance.libraries_processed = 3
            instance.libraries_failed = 0
            instance.items_tagged = 2
            instance.run_result = result
            scheduler._run_deleterr()

        last_run = self._last_run(scheduler)
        assert last_run["status"] == "success"
        assert last_run["libraries_processed"] == 3
        assert last_run["libraries_failed"] == 0
        assert last_run["items_deleted"] == 1
        assert last_run["items_tagged"] == 2
        assert last_run["interval_seconds"] == 7 * 24 * 60 * 60
        assert last_run["last_success_at"] == last_run["timestamp"]
        assert last_run["dry_run"] is False

    def test_dry_run_records_zero_deletions_and_the_dry_run_flag(self, scheduler):
        from app.modules.notifications.models import DeletedItem, RunResult

        scheduler.config.settings["dry_run"] = True
        result = RunResult(
            is_dry_run=True,
            deleted_items=[DeletedItem("A", 2020, "movie", 1, "Movies", "Radarr")],
        )
        with patch("app.deleterr.Deleterr") as mock_deleterr:
            instance = mock_deleterr.return_value
            instance.has_fatal_errors.return_value = False
            instance.library_failures = []
            instance.libraries_processed = 1
            instance.libraries_failed = 0
            instance.items_tagged = 0
            instance.run_result = result
            scheduler._run_deleterr()

        last_run = self._last_run(scheduler)
        assert last_run["status"] == "success"
        assert last_run["dry_run"] is True
        assert last_run["items_deleted"] == 0
        assert last_run["items_tagged"] == 0

    def test_tagged_count_comes_from_deleterr_not_preview_items(self, scheduler):
        from app.modules.notifications.models import RunResult

        with patch("app.deleterr.Deleterr") as mock_deleterr:
            instance = mock_deleterr.return_value
            instance.has_fatal_errors.return_value = False
            instance.library_failures = []
            instance.libraries_processed = 1
            instance.libraries_failed = 0
            instance.items_tagged = 4
            instance.run_result = RunResult(is_dry_run=False)
            scheduler._run_deleterr()

        last_run = self._last_run(scheduler)
        assert last_run["items_tagged"] == 4
        assert last_run["items_deleted"] == 0

    def test_failed_run_keeps_the_previous_success_timestamp(self, scheduler):
        import json

        previous = {
            "status": "success",
            "timestamp": "2026-11-01T03:00:00",
            "error": None,
            "libraries_processed": 2,
            "libraries_failed": 0,
            "items_deleted": 4,
            "items_tagged": 1,
            "interval_seconds": 604800,
            "last_success_at": "2026-11-01T03:00:00",
        }
        with open(scheduler.last_run_file, "w", encoding="utf-8") as f:
            json.dump(previous, f)

        with patch("app.deleterr.Deleterr", side_effect=Exception("boom")), \
             patch("app.modules.notifications.NotificationManager.send_run_failure"):
            scheduler._run_deleterr()

        last_run = self._last_run(scheduler)
        assert last_run["status"] == "failed"
        assert last_run["libraries_processed"] == 0
        assert last_run["libraries_failed"] == 0
        assert last_run["items_deleted"] == 0
        assert last_run["items_tagged"] == 0
        assert last_run["last_success_at"] == "2026-11-01T03:00:00"
        assert last_run["interval_seconds"] == 7 * 24 * 60 * 60

    def test_start_records_a_starting_status_before_the_first_run(self, scheduler):
        scheduler.scheduler = Mock()
        scheduler.scheduler.start.side_effect = KeyboardInterrupt()
        with patch.object(scheduler, "_parse_schedule", return_value=Mock()):
            try:
                scheduler.start()
            except (KeyboardInterrupt, SystemExit):
                pass

        last_run = self._last_run(scheduler)
        assert last_run["status"] == "starting"
        assert last_run["interval_seconds"] == 7 * 24 * 60 * 60
        assert last_run["last_success_at"] is None
        assert last_run["timestamp"]


class TestScheduleInterval:
    def test_weekly_preset_is_seven_days(self):
        from app.scheduler import schedule_interval_seconds

        assert schedule_interval_seconds("weekly") == 7 * 24 * 60 * 60

    def test_hourly_and_daily_presets(self):
        from app.scheduler import schedule_interval_seconds

        assert schedule_interval_seconds("hourly") == 3600
        assert schedule_interval_seconds("daily") == 24 * 60 * 60

    def test_every_four_hours_cron(self):
        from app.scheduler import schedule_interval_seconds

        assert schedule_interval_seconds("0 */4 * * *") == 4 * 60 * 60

    def test_monday_and_thursday_uses_the_longer_gap(self):
        from app.scheduler import schedule_interval_seconds

        # Thursday 4am to Monday 4am is four days.
        assert schedule_interval_seconds("0 4 * * 1,4") == 4 * 24 * 60 * 60


    def test_every_minute_during_hour_three_includes_the_overnight_gap(self):
        from app.scheduler import schedule_interval_seconds

        # * 3 * * * fires every minute at 03:00-03:59, then waits until the next 03:00.
        assert schedule_interval_seconds("* 3 * * *") == 23 * 60 * 60 + 60



    def _freeze_scheduler_now(self, monkeypatch, when):
        from datetime import datetime

        class FrozenDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return when if tz is None else when.astimezone(tz)

        monkeypatch.setattr("app.scheduler.datetime", FrozenDateTime)

    def test_annual_schedule_is_a_full_year_even_in_november(self, monkeypatch):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from app.scheduler import schedule_interval_seconds

        self._freeze_scheduler_now(monkeypatch, datetime(2026, 11, 16, tzinfo=ZoneInfo("UTC")))
        # From mid-November the next two 1 January fires are 365 days apart.
        # A 400-day sample window only sees the first fire and used to fall back
        # to a week, marking a healthy yearly scheduler unhealthy.
        assert schedule_interval_seconds("0 0 1 1 *") in (
            365 * 24 * 60 * 60,
            366 * 24 * 60 * 60,
        )

    def test_every_minute_for_the_first_half_of_the_year_includes_the_idle_half(self, monkeypatch):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from app.scheduler import schedule_interval_seconds

        self._freeze_scheduler_now(monkeypatch, datetime(2026, 11, 16, tzinfo=ZoneInfo("UTC")))
        # * * * 1-6 * fires every minute from January to June, then idles until
        # January. The idle gap is 184 days and one minute (30 June 23:59 to
        # 1 January 00:00). A 200_000-sample cap used to stop in the burst and
        # report 60 seconds.
        assert schedule_interval_seconds("* * * 1-6 *") == 184 * 24 * 60 * 60 + 60

    def test_leap_day_schedule_uses_the_four_year_gap(self, monkeypatch):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from app.scheduler import schedule_interval_seconds

        self._freeze_scheduler_now(monkeypatch, datetime(2026, 11, 16, tzinfo=ZoneInfo("UTC")))
        # 29 February 2028 to 29 February 2032 is 1461 days.
        assert schedule_interval_seconds("0 0 29 2 *") == 1461 * 24 * 60 * 60

class TestStartupFailureStatus:
    def test_hang_on_error_records_a_failed_status(self, tmp_path, monkeypatch):
        import json

        from app.config import hang_on_error

        path = tmp_path / ".deleterr_last_run.json"
        monkeypatch.setattr("app.scheduler.LAST_RUN_FILE", str(path))

        def stop(_seconds):
            raise SystemExit(0)

        monkeypatch.setattr("app.config.time.sleep", stop)
        with pytest.raises(SystemExit):
            hang_on_error("YAML parsing error: bad indent")

        with open(path, encoding="utf-8") as f:
            last_run = json.load(f)
        assert last_run["status"] == "failed"
        assert "YAML parsing error" in last_run["error"]

    def test_startup_failure_redacts_api_keys(self, tmp_path, monkeypatch):
        import json

        from app.config import hang_on_error

        path = tmp_path / ".deleterr_last_run.json"
        monkeypatch.setattr("app.scheduler.LAST_RUN_FILE", str(path))

        def stop(_seconds):
            raise SystemExit(0)

        monkeypatch.setattr("app.config.time.sleep", stop)
        secret = "super-secret-sonarr-key"
        with pytest.raises(SystemExit):
            hang_on_error(
                "YAML parsing error: url: http://sonarr:8989/api?apikey=" + secret
            )

        with open(path, encoding="utf-8") as f:
            last_run = json.load(f)
        assert last_run["status"] == "failed"
        assert secret not in last_run["error"]
        assert "[REDACTED]" in last_run["error"]

    def test_startup_hang_preserves_a_recorded_cleanup_failure(self, tmp_path, monkeypatch):
        import json
        from unittest.mock import Mock, patch

        from app.scheduler import DeleterrScheduler

        path = tmp_path / ".deleterr_last_run.json"
        recorded = {
            "status": "failed",
            "timestamp": "2026-11-16T09:00:00",
            "error": "All libraries failed: Movies: connection refused",
            "libraries_processed": 0,
            "libraries_failed": 2,
            "items_deleted": 0,
            "items_tagged": 0,
        }
        monkeypatch.setattr("app.scheduler.LAST_RUN_FILE", str(path))

        config = Mock()
        config.settings = {
            "scheduler": {"enabled": True, "schedule": "weekly", "run_on_startup": True}
        }
        with patch("app.scheduler.BlockingScheduler"):
            scheduler = DeleterrScheduler(config)
        scheduler.last_run_file = str(path)

        def already_recorded():
            with open(path, "w", encoding="utf-8") as f:
                json.dump(recorded, f)
            return False

        monkeypatch.setattr(scheduler, "_run_deleterr", already_recorded)
        monkeypatch.setattr(scheduler, "_parse_schedule", Mock())
        monkeypatch.setattr("app.config.time.sleep", lambda _s: (_ for _ in ()).throw(SystemExit(0)))

        with pytest.raises(SystemExit):
            scheduler.start()

        with open(path, encoding="utf-8") as f:
            last_run = json.load(f)
        assert last_run["status"] == "failed"
        assert last_run["libraries_failed"] == 2
        assert last_run["error"] == recorded["error"]
        assert "Initial run failed" not in (last_run["error"] or "")

