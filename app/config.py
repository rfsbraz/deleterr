# encoding: utf-8

import yaml
from app import logger
import sys
import os
import requests
from app.modules.trakt import Trakt
from app.modules.tautulli import Tautulli
from app.constants import VALID_SORT_FIELDS, VALID_SORT_ORDERS, VALID_ACTION_MODES
from app.utils import validate_units


def load_config(config_file):
    try:
        full_path = os.path.abspath(config_file)
        with open(full_path, "r", encoding="utf8") as stream:
            logger.debug("Loading configuration from %s", full_path)
            return Config(yaml.safe_load(stream))
    except FileNotFoundError:
        logger.error(
            f"Configuration file {config_file} not found. Copy the example config and edit it to your needs."
        )
    except yaml.YAMLError as exc:
        logger.error(exc)

    sys.exit(1)


class Config:
    def __init__(self, config_file):
        self.settings = config_file

    def validate(self):
        if not self.validate_config():
            self.log_and_exit("Invalid configuration, exiting.")

        if self.settings.get("dry_run"):
            logger.info("Running in dry-run mode, no changes will be made.")

        if self.settings.get("interactive"):
            logger.info(
                "Running in interactive mode, you will be prompted before any changes are made."
            )

    def log_and_exit(self, msg):
        logger.error(msg)
        sys.exit(1)

    def validate_config(self):
        return (
            self.validate_trakt()
            and self.validate_sonarr_and_radarr()
            and self.validate_tautulli()
            and self.validate_libraries()
        )

    def validate_trakt(self):
        if not self.settings.get("trakt"):
            return True
        try:
            t = Trakt(
                self.settings.get("trakt", {}).get("client_id"),
                self.settings.get("trakt", {}).get("client_secret"),
            )
            t.test_connection()
            return True
        except Exception as err:
            logger.error("Failed to connect to Trakt, check your configuration.")
            logger.debug(f"Error: {err}")
            return False

    def validate_sonarr_and_radarr(self):
        sonarr_settings = self.settings.get("sonarr", [])
        radarr_settings = self.settings.get("radarr", [])

        # Check if sonarr_settings and radarr_settings are lists
        if not isinstance(sonarr_settings, list) or not isinstance(
            radarr_settings, list
        ):
            self.log_and_exit(
                "sonarr and radarr settings should be a list of dictionaries."
            )

        return all(
            self.test_api_connection(connection)
            for connection in sonarr_settings + radarr_settings
        )

    def test_api_connection(self, connection):
        try:
            response = requests.get(
                f"{connection['url']}/api",
                params={"apiKey": connection["api_key"]},
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as err:
            logger.error(
                f"Failed to connect to {connection['name']} at {connection['url']}, check your configuration."
            )
            logger.debug(f"Error: {err}")
            return False

    def validate_tautulli(self):
        try:
            tautulliConfig = self.settings.get("tautulli")
            if not tautulliConfig:
                raise KeyError
            tautulli = Tautulli(tautulliConfig["url"], tautulliConfig["api_key"])
            tautulli.test_connection()
        except KeyError:
            logger.error("Tautulli configuration not found, check your configuration.")
            return False
        except Exception as err:
            logger.error(
                f"Failed to connect to tautulli at {tautulliConfig['url']}, check your configuration."
            )
            logger.debug(f"Error: {err}")
            return False

        return True

    def validate_libraries(self):
        trakt_configured = self.settings.get("trakt") is not None

        libraries = self.settings.get("libraries", [])

        if not libraries:
            self.log_and_exit(
                "No libraries configured. Please check your configuration."
            )

        for library in libraries:
            if "sonarr" in library:
                if not any(
                    connection["name"] == library["sonarr"]
                    for connection in self.settings.get("sonarr", [])
                ):
                    self.log_and_exit(
                        f"Sonarr '{library['sonarr']}' is not configured. Please check your configuration."
                    )
            if "radarr" in library:
                if not any(
                    connection["name"] == library["radarr"]
                    for connection in self.settings.get("radarr", [])
                ):
                    self.log_and_exit(
                        f"Radarr '{library['radarr']}' is not configured. Please check your configuration."
                    )

            for item in library.get("disk_size_threshold", []):
                path = item.get("path")
                threshold = item.get("threshold")

                try:
                    validate_units(threshold)
                except ValueError as err:
                    self.log_and_exit(
                        f"Invalid threshold '{threshold}' for path '{path}' in library '{library.get('name')}': {err}"
                    )

            if (
                len(library.get("exclude", {}).get("trakt_lists", [])) > 0
                and not trakt_configured
            ):
                self.log_and_exit(
                    f"Trakt lists configured for {library['name']} but trakt is not configured, check your configuration."
                )

            if library["action_mode"] not in VALID_ACTION_MODES:
                self.log_and_exit(
                    f"Invalid action_mode '{library['action_mode']}' in library '{library['name']}', it should be either 'delete'."
                )

            if "watch_status" in library and library["watch_status"] not in [
                "watched",
                "unwatched",
            ]:
                self.log_and_exit(
                    self.log_and_exit(
                        f"Invalid watch_status '{library.get('watch_status')}' in library "
                        f"'{library.get('name')}', it must be either 'watched', 'unwatched', "
                        "or not set."
                    )
                )

            if (
                "watch_status" in library
                and "apply_last_watch_threshold_to_collections" in library
            ):
                self.log_and_exit(
                    self.log_and_exit(
                        f"'apply_last_watch_threshold_to_collections' cannot be used when "
                        f"'watch_status' is set in library '{library.get('name')}'. This would "
                        f"mean entire collections would be deleted when a single item in the "
                        f"collection meets the watch_status criteria."
                    )
                )

        if sort_config := library.get("sort", {}):
            sort_field = sort_config.get("field")
            sort_order = sort_config.get("order")

            if sort_field and sort_field not in VALID_SORT_FIELDS:
                self.log_and_exit(
                    f"Invalid sort field '{sort_field}' in library '{library['name']}', supported values are {VALID_SORT_FIELDS}."
                )

            if sort_order and sort_order not in VALID_SORT_ORDERS:
                self.log_and_exit(
                    f"Invalid sort order '{sort_order}' in library '{library['name']}', supported values are {VALID_SORT_ORDERS}."
                )

        return True
