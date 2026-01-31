# encoding: utf-8

import argparse
import locale
import os
import sys

from app.modules.radarr import DRadarr
from app.modules.sonarr import DSonarr
from app.modules.plex import PlexMediaServer

from app import logger
from app.config import hang_on_error, load_config
from app.media_cleaner import ConfigurationError, MediaCleaner
from app.modules.notifications import NotificationManager, RunResult, DeletedItem
from app.utils import print_readable_freed_space


class Deleterr:
    def __init__(self, config):
        self.config = config

        # Initialize media server for leaving_soon feature
        ssl_verify = config.settings.get("ssl_verify", False)
        self.media_server = PlexMediaServer(
            config.settings.get("plex").get("url"),
            config.settings.get("plex").get("token"),
            ssl_verify=ssl_verify,
        )

        self.media_cleaner = MediaCleaner(config, media_server=self.media_server)
        self.notifications = NotificationManager(config)
        self.run_result = RunResult(is_dry_run=config.settings.get("dry_run", True))

        self.sonarr = {
            connection["name"]: DSonarr(connection["name"], connection["url"], connection["api_key"])
            for connection in config.settings.get("sonarr", [])
        }
        self.radarr = {
            connection["name"]: DRadarr(connection["name"], connection["url"], connection["api_key"])
            for connection in config.settings.get("radarr", [])
        }

        self.libraries_processed = 0
        self.libraries_failed = 0

        self.process_radarr()
        self.process_sonarr()

        # Send notification after all processing
        self._send_notification()

    def process_radarr(self):
        for name, radarr in self.radarr.items():
            logger.info("Processing radarr instance: '%s'", name)

            saved_space = 0
            all_preview = []
            for library in self.config.settings.get("libraries", []):
                if library.get("radarr") == name:
                    try:
                        space, deleted, preview = self.media_cleaner.process_library_movies(
                            library, radarr
                        )
                        saved_space += space
                        all_preview.extend(preview)
                        self.libraries_processed += 1

                        # Track deleted items for notifications
                        library_name = library.get("name", "Unknown")
                        for item in deleted:
                            self.run_result.add_deleted(
                                DeletedItem.from_radarr(item, library_name, name)
                            )

                        # Process leaving_soon feature
                        self._process_library_leaving_soon(
                            library, deleted, preview, "movie"
                        )
                    except ConfigurationError as e:
                        logger.error(str(e))
                        self.libraries_failed += 1

            if self.config.settings.get("dry_run"):
                logger.info(
                    "[DRY-RUN] Would have freed %s of space by deleting movies",
                    print_readable_freed_space(saved_space),
                )
            else:
                logger.info(
                    "Freed %s of space by deleting movies",
                    print_readable_freed_space(saved_space),
                )

            # Log preview of next scheduled deletions
            self._log_preview(all_preview, "movie")

    def process_sonarr(self):
        for name, sonarr in self.sonarr.items():
            logger.info("Processing sonarr instance: '%s'", name)
            unfiltered_all_show_data = sonarr.get_series()

            saved_space = 0
            all_preview = []
            for library in self.config.settings.get("libraries", []):
                if library.get("sonarr") == name:
                    try:
                        space, deleted, preview = self.media_cleaner.process_library(
                            library, sonarr, unfiltered_all_show_data
                        )
                        saved_space += space
                        all_preview.extend(preview)
                        self.libraries_processed += 1

                        # Track deleted items for notifications
                        library_name = library.get("name", "Unknown")
                        for item in deleted:
                            self.run_result.add_deleted(
                                DeletedItem.from_sonarr(item, library_name, name)
                            )

                        # Process leaving_soon feature
                        self._process_library_leaving_soon(
                            library, deleted, preview, "show"
                        )
                    except ConfigurationError as e:
                        logger.error(str(e))
                        self.libraries_failed += 1

            if self.config.settings.get("dry_run"):
                logger.info(
                    "[DRY-RUN] Would have freed %s of space by deleting shows",
                    print_readable_freed_space(saved_space),
                )
            else:
                logger.info(
                    "Freed %s of space by deleting shows",
                    print_readable_freed_space(saved_space),
                )

            # Log preview of next scheduled deletions
            self._log_preview(all_preview, "show")

    def _process_library_leaving_soon(self, library, deleted, preview, media_type):
        """
        Process leaving_soon feature for a library.

        Determines which items to tag based on mode:
        - tagging_only mode: tag deleted items (what WOULD be deleted)
        - normal mode: tag preview items (what will be deleted next run)

        Args:
            library: Library configuration dict
            deleted: List of items that were deleted this run
            preview: List of items that would be deleted next run
            media_type: 'movie' or 'show'
        """
        leaving_soon_config = library.get("leaving_soon", {})
        if not leaving_soon_config.get("enabled", False):
            return

        is_dry_run = self.config.settings.get("dry_run", True)
        tagging_only = leaving_soon_config.get("tagging_only", False)

        # In dry_run mode without tagging_only, skip tagging
        # (unless tagging_only is explicitly enabled)
        if is_dry_run and not tagging_only:
            logger.debug(
                "Skipping leaving_soon processing in dry-run mode "
                "(enable tagging_only to update collection/labels in dry-run)"
            )
            return

        # Determine which items to tag
        if tagging_only:
            # In tagging_only mode, tag what WOULD be deleted (the deleted list
            # contains items that were evaluated but not actually deleted)
            items_to_tag = deleted
            logger.info(
                f"[TAGGING-ONLY] Processing {len(items_to_tag)} items for leaving_soon"
            )
        else:
            # Normal mode: tag preview items (next run's deletions)
            items_to_tag = preview

        if not items_to_tag:
            logger.debug("No items to process for leaving_soon")
            return

        # Get the Plex library
        try:
            plex_library = self.media_server.get_library(library.get("name"))
        except Exception as e:
            logger.error(f"Failed to get Plex library '{library.get('name')}': {e}")
            return

        # Process leaving_soon
        self.media_cleaner.process_leaving_soon(
            library, plex_library, items_to_tag, media_type
        )

    def _log_preview(self, preview_items, media_type):
        """
        Log preview of items that would be deleted on the next run.

        Args:
            preview_items: List of media items from Radarr/Sonarr
            media_type: 'movie' or 'show' for appropriate size extraction
        """
        if not preview_items:
            return

        # Calculate total preview size
        total_size = 0
        for item in preview_items:
            if media_type == "movie":
                total_size += item.get("sizeOnDisk", 0)
            else:  # show
                total_size += item.get("statistics", {}).get("sizeOnDisk", 0)

        # Determine log prefix for dry-run mode
        prefix = "[DRY-RUN] " if self.config.settings.get("dry_run") else ""
        action_word = "Would be deleted" if self.config.settings.get("dry_run") else "Next scheduled deletions"

        logger.info(
            "%s%s (%d items, %s):",
            prefix,
            action_word,
            len(preview_items),
            print_readable_freed_space(total_size),
        )

        # Log each preview item
        for i, item in enumerate(preview_items, 1):
            if media_type == "movie":
                size = item.get("sizeOnDisk", 0)
            else:  # show
                size = item.get("statistics", {}).get("sizeOnDisk", 0)

            logger.info(
                "%s  %d. %s (%s)",
                prefix,
                i,
                item["title"],
                print_readable_freed_space(size),
            )

    def _send_notification(self):
        """Send notification with run results."""
        if self.notifications.is_enabled():
            try:
                self.notifications.send_run_summary(self.run_result)
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")

    def has_fatal_errors(self):
        """Returns True if all libraries failed due to configuration errors."""
        total_libraries = self.libraries_processed + self.libraries_failed
        return total_libraries > 0 and self.libraries_failed == total_libraries


def get_file_contents(file_path):
    try:
        with open(file_path, "r") as file:
            return file.read().strip()
    except FileNotFoundError:
        print(f"File not found: {file_path}")
    except IOError as e:
        print(f"Error reading file {file_path}: {e}")


def main():
    """
    Deleterr application entry point. Parses arguments, configs and
    initializes the application.

    Supports two modes:
    1. Single run (default): Runs once and exits. Use with external schedulers (Ofelia, cron).
    2. Scheduler mode: Runs as a long-lived process with built-in scheduling.
       Enable via `scheduler.enabled: true` in settings.yaml.
    """

    locale.setlocale(locale.LC_ALL, "")

    log_level = os.environ.get("LOG_LEVEL", "info").upper()
    logger.init_logger(
        console=True, log_dir="/config/logs", verbose=log_level == "DEBUG"
    )

    logger.info("Running version %s", get_file_contents("/app/commit_tag.txt"))
    logger.info("Log level set to %s", log_level)

    parser = argparse.ArgumentParser(description="Deleterr - Automated media cleanup for Plex")
    parser.add_argument(
        "--config",
        "--c",
        default="/config/settings.yaml",
        help="Path to the config file",
    )
    parser.add_argument(
        "--jw-providers", action="store_true", help="Gather JustWatch providers"
    )
    parser.add_argument(
        "--scheduler",
        action="store_true",
        help="Force scheduler mode (overrides config setting)",
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Force single run mode (overrides scheduler config)",
    )

    args, unknown = parser.parse_known_args()

    config = load_config(args.config)
    config.validate()

    # If providers flag is set, gather JustWatch providers and exit
    if args.jw_providers:
        from app.scripts.justwatch_providers import gather_providers

        providers = gather_providers(
            config.settings.get("trakt", {}).get("client_id"),
            config.settings.get("trakt", {}).get("client_secret"),
        )

        print(providers)
        logger.info("# of Trakt Providers: " + str(len(providers)))

        return

    # Determine run mode
    scheduler_config = config.settings.get("scheduler", {})
    scheduler_enabled = scheduler_config.get("enabled", False)

    # CLI flags override config
    if args.run_once:
        scheduler_enabled = False
    elif args.scheduler:
        scheduler_enabled = True

    if scheduler_enabled:
        # Run in scheduler mode (long-lived process)
        from app.scheduler import DeleterrScheduler

        logger.info("Starting in scheduler mode")
        scheduler = DeleterrScheduler(config)
        scheduler.start()  # Blocks until shutdown
    else:
        # Run once and exit (for external schedulers like Ofelia or cron)
        logger.info("Running in single-run mode")
        deleterr = Deleterr(config)

        if deleterr.has_fatal_errors():
            hang_on_error(
                "All libraries failed due to configuration errors. "
                "Please check your settings.yaml and fix the errors above."
            )


if __name__ == "__main__":
    main()
