# encoding: utf-8
"""
Built-in scheduler for Deleterr.

Provides an optional native scheduling solution as an alternative to external
schedulers like Ofelia or system cron.
"""

import json
import os
import signal
import sys
import tempfile
from datetime import datetime, timedelta

from apscheduler.events import EVENT_JOB_MISSED, EVENT_JOB_MAX_INSTANCES
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app import logger
from app.config import hang_on_error

LAST_RUN_FILE = "/config/.deleterr_last_run.json"
MISFIRE_GRACE_SECONDS = 6 * 60 * 60

# Schedule presets mapping to cron expressions
SCHEDULE_PRESETS = {
    "hourly": "0 * * * *",      # Every hour at minute 0
    "daily": "0 3 * * *",       # Daily at 3 AM
    "weekly": "0 3 * * 0",      # Sunday at 3 AM
    "monthly": "0 3 1 * *",     # First day of month at 3 AM
}


def schedule_interval_seconds(schedule, timezone="UTC"):
    """Return the longest gap, in seconds, between consecutive runs of a schedule."""
    cron_expr = SCHEDULE_PRESETS.get(schedule.lower(), schedule)
    parts = cron_expr.split()
    if len(parts) != 5:
        raise ValueError(
            f"Invalid cron expression '{cron_expr}'. "
            "Expected 5 fields: minute hour day month day_of_week"
        )
    minute, hour, day, month, day_of_week = parts
    trigger = CronTrigger(
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
        timezone=timezone,
    )
    return _max_cron_gap_seconds(trigger)


def _next_cron_fire(trigger, fire):
    return trigger.get_next_fire_time(fire, fire + timedelta(seconds=1))


def _last_fire_on_or_before(trigger, lo_fire, probe):
    """Latest fire in [lo_fire, probe]. lo_fire must itself be a fire time."""
    if probe <= lo_fire:
        return lo_fire
    if trigger.get_next_fire_time(None, probe) == probe:
        return probe
    left, right = lo_fire, probe
    while (right - left).total_seconds() > 1:
        mid = left + timedelta(seconds=(right - left).total_seconds() / 2)
        found = trigger.get_next_fire_time(None, mid)
        if found is not None and found <= probe:
            left = found
        else:
            right = mid
    return left


def _extend_sparse_horizon(last, nxt, end, n, extended):
    """Keep walking until a second fire is seen, up to 40 years out."""
    if nxt is None or nxt <= end:
        return end, extended, nxt is None
    if n < 2:
        cap = last + timedelta(days=40 * 366)
        if nxt <= cap:
            return cap, True, False
        return cap, True, True
    return end, extended, True


def _skip_dense_cron_burst(trigger, last, gap, end, max_gap, n, extended):
    """Jump through a tight burst and return after the next idle gap, if any."""
    step = max(gap * 4, 60.0)
    cluster_last = last
    while True:
        # Measure the immediate next fire before jumping, so an irregular
        # schedule cannot hide a longer gap behind the probe.
        after = _next_cron_fire(trigger, cluster_last)
        if after is None:
            return cluster_last, max_gap, n, extended, True
        g2 = (after - cluster_last).total_seconds()
        if g2 > max_gap:
            max_gap = g2
        n += 1
        end, extended, stop = _extend_sparse_horizon(cluster_last, after, end, n, extended)
        if stop:
            return cluster_last, max_gap, n, extended, True
        if g2 > gap * 1.5:
            return after, max_gap, n, extended, False
        probe = cluster_last + timedelta(seconds=step)
        if probe > end:
            probe = end
        cluster_last = _last_fire_on_or_before(trigger, after, probe)
        last = cluster_last
        step = min(step * 2, 40 * 24 * 3600)
        if probe >= end:
            return last, max_gap, n, extended, True


def _max_cron_gap_seconds(trigger, horizon_days=800):
    # Measure the longest gap without visiting every fire in a dense burst.
    # Annual and leap-day crons need a window longer than one year; clustered
    # crons such as "* 3 * * *" and "* * * 1-6 *" must still include the
    # idle stretch, not only the one-minute samples inside the burst.
    cursor = datetime.now(trigger.timezone)
    end = cursor + timedelta(days=horizon_days)
    last = trigger.get_next_fire_time(None, cursor)
    if last is None:
        raise ValueError("Could not measure the schedule interval")

    max_gap = 0
    n = 1
    extended = False

    while True:
        nxt = _next_cron_fire(trigger, last)
        end, extended, stop = _extend_sparse_horizon(last, nxt, end, n, extended)
        if stop:
            break

        gap = (nxt - last).total_seconds()
        if gap > max_gap:
            max_gap = gap
        n += 1

        # Only skip tight bursts (every minute or so). Longer irregular
        # gaps, such as a few hours, are walked fire-to-fire.
        if gap > 3600:
            last = nxt
            continue

        last, max_gap, n, extended, stop = _skip_dense_cron_burst(
            trigger, nxt, gap, end, max_gap, n, extended
        )
        if stop:
            break

    if n < 2 or max_gap <= 0:
        raise ValueError("Could not measure the schedule interval")
    return int(max_gap)


def _as_int(value, default=0):
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return default


def _read_last_run(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _atomic_write_last_run(path, data):
    fd, tmp_path = tempfile.mkstemp(
        dir=os.path.dirname(path) or ".", prefix=".deleterr_last_run_", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def record_startup_failure(error, path=None):
    """Write a failed last-run status before hang_on_error idles the process."""
    path = path or LAST_RUN_FILE
    previous = _read_last_run(path)
    now = datetime.now().isoformat()
    data = {
        "status": "failed",
        "timestamp": now,
        "error": logger.redact(error) if error else error,
        "interval_seconds": previous.get("interval_seconds") or 7 * 24 * 60 * 60,
        "last_success_at": previous.get("last_success_at"),
        "libraries_processed": 0,
        "libraries_failed": 0,
        "items_deleted": 0,
        "items_tagged": 0,
        "dry_run": previous.get("dry_run"),
    }
    try:
        _atomic_write_last_run(path, data)
    except OSError as exc:
        logger.warning(f"Failed to write last run status to '{path}': {exc}")


class DeleterrScheduler:
    """
    Scheduler for running Deleterr on a configurable schedule.

    Supports both cron expressions and preset schedules (hourly, daily, weekly, monthly).
    """

    def __init__(self, config):
        """
        Initialize the scheduler.

        Args:
            config: Deleterr Config object
        """
        self.config = config
        self.scheduler_config = config.settings.get("scheduler", {})
        self.scheduler = BlockingScheduler()
        self.last_run_file = LAST_RUN_FILE
        self.scheduler.add_listener(
            self._handle_missed_run, EVENT_JOB_MISSED | EVENT_JOB_MAX_INSTANCES
        )
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """Set up graceful shutdown handlers."""
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info("Received shutdown signal, stopping scheduler...")
        self.scheduler.shutdown(wait=False)
        sys.exit(0)

    def _parse_schedule(self, schedule):
        """
        Parse schedule string into a CronTrigger.

        Args:
            schedule: Either a preset name (hourly, daily, weekly, monthly)
                     or a cron expression (e.g., "0 3 * * 0")

        Returns:
            CronTrigger configured for the schedule
        """
        # Check if it's a preset
        if schedule.lower() in SCHEDULE_PRESETS:
            cron_expr = SCHEDULE_PRESETS[schedule.lower()]
            logger.info(f"Using schedule preset '{schedule}' ({cron_expr})")
        else:
            cron_expr = schedule
            logger.info(f"Using custom cron schedule: {cron_expr}")

        # Parse cron expression
        parts = cron_expr.split()
        if len(parts) != 5:
            raise ValueError(
                f"Invalid cron expression '{cron_expr}'. "
                "Expected 5 fields: minute hour day month day_of_week"
            )

        minute, hour, day, month, day_of_week = parts
        timezone = self.scheduler_config.get("timezone", "UTC")

        return CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            timezone=timezone,
        )

    def _run_deleterr(self):
        """Execute Deleterr cleanup job.

        Returns:
            bool: True if run completed successfully, False if there were fatal errors.
        """
        from app.deleterr import Deleterr

        logger.info("=" * 60)
        logger.info(f"Scheduled run starting at {datetime.now().isoformat()}")
        logger.info("=" * 60)

        try:
            deleterr = Deleterr(self.config)
            if deleterr.has_fatal_errors():
                logger.error(
                    "All libraries failed due to configuration errors. "
                    "Please check your settings.yaml and fix the errors above."
                )
                # Redact each message on its own so a secret at the end of one
                # cannot swallow the separator before the next library
                error = "All libraries failed: " + "; ".join(
                    f"{name}: {logger.redact(message)}" for name, message in deleterr.library_failures
                )
                self._record_last_run("failed", error, deleterr)
                if not deleterr.notification_sent:
                    self._notify_failure(error)
                return False
            if deleterr.library_failures:
                # The run summary notification already lists the failed libraries
                prefix = "Some libraries failed: " if deleterr.libraries_processed else "All libraries failed: "
                error = prefix + "; ".join(
                    f"{name}: {logger.redact(message)}" for name, message in deleterr.library_failures
                )
                logger.warning(f"Scheduled run completed with errors. {error}")
                self._record_last_run("partial" if deleterr.libraries_processed else "failed", error, deleterr)
                return True  # Service failures remain retryable, including at startup.
            if self.config.settings.get("dry_run"):
                logger.info("[DRY-RUN] Scheduled run completed successfully (no changes were made)")
            else:
                logger.info("Scheduled run completed successfully")
            self._record_last_run("success", deleterr=deleterr)
            return True
        except Exception as e:
            error = logger.redact(f"{type(e).__name__}: {e}")
            logger.error(f"Scheduled run failed: {e}")
            self._record_last_run("failed", error)
            self._notify_failure(error)
            # Don't re-raise - we want the scheduler to continue for transient errors
            return True  # Not a config error, allow retries

    def _handle_missed_run(self, event):
        """Surface expired or overlapping cleanup runs through normal reporting."""
        if event.job_id != "deleterr_cleanup":
            return
        if event.code == EVENT_JOB_MAX_INSTANCES:
            times = ", ".join(t.isoformat() for t in event.scheduled_run_times)
            error = (
                f"Scheduled cleanup skipped because another cleanup is still running "
                f"(scheduled for {times}); no overlapping cleanup was started."
            )
        else:
            error = (
                f"Scheduled cleanup missed its {MISFIRE_GRACE_SECONDS // 3600}-hour "
                f"catch-up window (scheduled for {event.scheduled_run_time.isoformat()})."
            )
        logger.warning(error)
        self._record_last_run("failed", error)
        self._notify_failure(error)

    def _notify_failure(self, error):
        """Send a failed-run notification. Never raises."""
        from app.modules.notifications import NotificationManager

        try:
            NotificationManager(self.config).send_run_failure(
                error, is_dry_run=bool(self.config.settings.get("dry_run", True))
            )
        except Exception as e:
            logger.error(f"Failed to send run failure notification: {e}")

    def _interval_seconds(self):
        cached = getattr(self, "_cached_interval_seconds", None)
        if cached is not None:
            return cached
        schedule = self.scheduler_config.get("schedule", "weekly")
        timezone = self.scheduler_config.get("timezone", "UTC")
        try:
            value = schedule_interval_seconds(schedule, timezone)
        except ValueError:
            value = schedule_interval_seconds("weekly", timezone)
        self._cached_interval_seconds = value
        return value

    def _previous_last_run(self):
        return _read_last_run(self.last_run_file)

    def _run_counts(self, deleterr=None):
        dry_run = bool(self.config.settings.get("dry_run", True))
        if deleterr is None:
            return {
                "libraries_processed": 0,
                "libraries_failed": 0,
                "items_deleted": 0,
                "items_tagged": 0,
                "dry_run": dry_run,
            }
        result = getattr(deleterr, "run_result", None)
        deleted = getattr(result, "deleted_items", None) if result is not None else None
        deleted_count = len(deleted) if isinstance(deleted, list) else 0
        return {
            "libraries_processed": _as_int(getattr(deleterr, "libraries_processed", 0)),
            "libraries_failed": _as_int(getattr(deleterr, "libraries_failed", 0)),
            "items_deleted": 0 if dry_run else deleted_count,
            "items_tagged": _as_int(getattr(deleterr, "items_tagged", 0)),
            "dry_run": dry_run,
        }

    def _record_last_run(self, status, error=None, deleterr=None):
        """Atomically write the last run status for healthchecks. Never raises."""
        now = datetime.now().isoformat()
        previous = self._previous_last_run()
        if status in ("success", "partial"):
            last_success_at = now
        else:
            last_success_at = previous.get("last_success_at")
        data = {
            "status": status,
            "timestamp": now,
            "error": error,
            "interval_seconds": self._interval_seconds(),
            "last_success_at": last_success_at,
            **self._run_counts(deleterr),
        }
        try:
            _atomic_write_last_run(self.last_run_file, data)
        except OSError as e:
            logger.warning(f"Failed to write last run status to '{self.last_run_file}': {e}")

    def start(self):
        """
        Start the scheduler.

        This method blocks until the scheduler is stopped.
        """
        schedule = self.scheduler_config.get("schedule", "weekly")
        run_on_startup = self.scheduler_config.get("run_on_startup", False)

        try:
            trigger = self._parse_schedule(schedule)
        except ValueError as e:
            hang_on_error(f"Invalid schedule configuration: {e}")

        # Add the job
        self.scheduler.add_job(
            self._run_deleterr,
            trigger,
            id="deleterr_cleanup",
            name="Deleterr Media Cleanup",
            replace_existing=True,
            misfire_grace_time=MISFIRE_GRACE_SECONDS,
            coalesce=True,
            max_instances=1,
        )

        logger.info("Deleterr scheduler started")
        logger.info(f"Schedule: {schedule}")
        logger.info(f"Timezone: {self.scheduler_config.get('timezone', 'UTC')}")

        # So the HEALTHCHECK has a file before the first run.
        self._record_last_run("starting")

        # Run immediately if configured
        if run_on_startup:
            logger.info("run_on_startup enabled, executing initial run...")
            success = self._run_deleterr()
            if not success:
                hang_on_error(
                    "Initial run failed due to configuration errors. "
                    "Scheduler will not start until configuration is fixed.",
                    record=False,
                )

        # Start the scheduler (blocks)
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped")
