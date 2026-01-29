# encoding: utf-8

import argparse
import locale
import os

from app.modules.radarr import DRadarr
from app.modules.sonarr import DSonarr

from app import logger
from app.config import load_config
from app.media_cleaner import MediaCleaner
from app.utils import print_readable_freed_space


class Deleterr:
    def __init__(self, config):
        self.config = config

        self.media_cleaner = MediaCleaner(config)

        self.sonarr = {
            connection["name"]: DSonarr(connection["name"], connection["url"], connection["api_key"])
            for connection in config.settings.get("sonarr", [])
        }
        self.radarr = {
            connection["name"]: DRadarr(connection["name"], connection["url"], connection["api_key"])
            for connection in config.settings.get("radarr", [])
        }

        self.process_radarr()
        self.process_sonarr()

    def process_radarr(self):
        for name, radarr in self.radarr.items():
            logger.info("Processing radarr instance: '%s'", name)

            saved_space = 0
            for library in self.config.settings.get("libraries", []):
                if library.get("radarr") == name:
                    saved_space += self.media_cleaner.process_library_movies(
                        library, radarr
                    )

            logger.info(
                "Freed %s of space by deleting movies",
                print_readable_freed_space(saved_space),
            )

    def process_sonarr(self):
        for name, sonarr in self.sonarr.items():
            logger.info("Processing sonarr instance: '%s'", name)
            unfiltered_all_show_data = sonarr.get_series()

            saved_space = 0
            for library in self.config.settings.get("libraries", []):
                if library.get("sonarr") == name:
                    saved_space += self.media_cleaner.process_library(
                        library, sonarr, unfiltered_all_show_data
                    )

            logger.info(
                "Freed %s of space by deleting shows",
                print_readable_freed_space(saved_space),
            )


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
    scheduler_enabled = scheduler_config.get("enabled", True)

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
        Deleterr(config)


if __name__ == "__main__":
    main()
