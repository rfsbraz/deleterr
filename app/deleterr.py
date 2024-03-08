# encoding: utf-8

import locale
import os
import argparse

from pyarr.sonarr import SonarrAPI
from pyarr.radarr import RadarrAPI
from app import logger
from app.utils import print_readable_freed_space
from app.media_cleaner import MediaCleaner
from app.config import load_config
from pyarr.exceptions import PyarrResourceNotFound, PyarrServerError


class Deleterr:
    def __init__(self, config):
        self.config = config

        self.media_cleaner = MediaCleaner(config)

        self.sonarr = {
            connection["name"]: SonarrAPI(connection["url"], connection["api_key"])
            for connection in config.settings.get("sonarr", [])
        }
        self.radarr = {
            connection["name"]: RadarrAPI(connection["url"], connection["api_key"])
            for connection in config.settings.get("radarr", [])
        }

        self.watched_collections = set()

        self.process_sonarr()
        self.process_radarr()

    def delete_series(self, sonarr, sonarr_show):
        # PyArr doesn't support deleting the series files, so we need to do it manually
        episodes = sonarr.get_episode(sonarr_show["id"], series=True)

        # Mark all episodes as unmonitored so they don't get re-downloaded while we're deleting them
        sonarr.upd_episode_monitor([episode["id"] for episode in episodes], False)

        # delete the files
        skip_deleting_show = False
        for episode in episodes:
            try:
                if episode["episodeFileId"] != 0:
                    sonarr.del_episode_file(episode["episodeFileId"])
            except PyarrResourceNotFound as e:
                # If the episode file doesn't exist, it's probably because it was already deleted by sonarr
                # Sometimes happens for multi-episode files
                logger.debug(
                    f"Failed to delete episode file {episode['episodeFileId']} for show {sonarr_show['id']} ({sonarr_show['title']}): {e}"
                )
            except PyarrServerError as e:
                # If the episode file is still in use, we can't delete the show
                logger.error(
                    f"Failed to delete episode file {episode['episodeFileId']} for show {sonarr_show['id']} ({sonarr_show['title']}): {e}"
                )
                skip_deleting_show = True
                break

        # delete the series
        if not skip_deleting_show:
            sonarr.del_series(sonarr_show["id"], delete_files=True)
        else:
            logger.info(
                f"Skipping deleting show {sonarr_show['id']} ({sonarr_show['title']}) due to errors deleting episode files. It will be deleted on the next run."
            )

    def process_radarr(self):
        for name, radarr in self.radarr.items():
            logger.info("Processing radarr instance: '%s'", name)
            all_movie_data = radarr.get_movie()

            saved_space = 0
            for library in self.config.settings.get("libraries", []):
                if library.get("radarr") == name:
                    saved_space += self.media_cleaner.process_library_movies(
                        library, radarr, all_movie_data
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
    """

    locale.setlocale(locale.LC_ALL, "")

    log_level = os.environ.get("LOG_LEVEL", "info").upper()
    logger.init_logger(
        console=True, log_dir="/config/logs", verbose=log_level == "DEBUG"
    )

    logger.info("Running version %s", get_file_contents("/app/commit_tag.txt"))
    logger.info("Log level set to %s", log_level)

    parser = argparse.ArgumentParser(description="Process some integers.")
    parser.add_argument(
        "--config",
        "--c",
        default="/config/settings.yaml",
        help="Path to the config file",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    config.validate()

    Deleterr(config)


if __name__ == "__main__":
    main()
