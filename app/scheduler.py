# encoding: utf-8
"""
Built-in scheduler for Deleterr.

Provides an optional native scheduling solution as an alternative to external
schedulers like Ofelia or system cron.
"""

import signal
import sys
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app import logger


# Schedule presets mapping to cron expressions
SCHEDULE_PRESETS = {
    "hourly": "0 * * * *",      # Every hour at minute 0
    "daily": "0 3 * * *",       # Daily at 3 AM
    "weekly": "0 3 * * 0",      # Sunday at 3 AM
    "monthly": "0 3 1 * *",     # First day of month at 3 AM
}


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
                return False
            logger.info("Scheduled run completed successfully")
            return True
        except Exception as e:
            logger.error(f"Scheduled run failed: {e}")
            # Don't re-raise - we want the scheduler to continue for transient errors
            return True  # Not a config error, allow retries

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
            logger.error(f"Invalid schedule configuration: {e}")
            sys.exit(1)

        # Add the job
        self.scheduler.add_job(
            self._run_deleterr,
            trigger,
            id="deleterr_cleanup",
            name="Deleterr Media Cleanup",
            replace_existing=True,
        )

        logger.info("Deleterr scheduler started")
        logger.info(f"Schedule: {schedule}")
        logger.info(f"Timezone: {self.scheduler_config.get('timezone', 'UTC')}")

        # Run immediately if configured
        if run_on_startup:
            logger.info("run_on_startup enabled, executing initial run...")
            success = self._run_deleterr()
            if not success:
                logger.error(
                    "Initial run failed due to configuration errors. "
                    "Scheduler will not start until configuration is fixed."
                )
                sys.exit(1)

        # Start the scheduler (blocks)
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped")
