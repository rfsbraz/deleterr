# encoding: utf-8

import os
import sys

import requests
import yaml

from app import logger
from app.constants import (
    SETTINGS_PER_ACTION,
    SETTINGS_PER_INSTANCE,
    VALID_ACTION_MODES,
    VALID_SORT_FIELDS,
    VALID_SORT_ORDERS,
)
from app.modules.tautulli import Tautulli
from app.modules.trakt import Trakt
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

    def validate_settings_for_instance(self, library):
        instance_type = "radarr" if "radarr" in library else "sonarr"
        for setting in library:
            if (
                setting in SETTINGS_PER_INSTANCE
                and instance_type not in SETTINGS_PER_INSTANCE[setting]
            ):
                self.log_and_exit(
                    f"'{setting}' can only be set for instances of type: {SETTINGS_PER_INSTANCE[setting]}"
                )

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
            tautulli_config = self.settings.get("tautulli")
            if not tautulli_config:
                raise KeyError
            tautulli = Tautulli(tautulli_config["url"], tautulli_config["api_key"])
            tautulli.test_connection()
        except KeyError:
            logger.error("Tautulli configuration not found, check your configuration.")
            return False
        except Exception as err:
            logger.error(
                f"Failed to connect to tautulli at {tautulli_config['url']}, check your configuration."
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
            self.validate_library_connections(library)
            self.validate_disk_size_threshold(library)
            self.validate_trakt_configuration(library, trakt_configured)
            self.validate_action_mode(library)
            self.validate_watch_status(library)
            self.validate_sort_configuration(library)
            self.validate_settings_for_instance(library)

        return True

    def validate_library_connections(self, library):
        self.validate_connection(library, "sonarr")
        self.validate_connection(library, "radarr")

    def validate_connection(self, library, connection_name):
        if connection_name in library and not any(
            connection["name"] == library[connection_name]
            for connection in self.settings.get(connection_name, [])
        ):
            self.log_and_exit(
                f"{connection_name.capitalize()} '{library[connection_name]}' is not configured. Please check your configuration."
            )

    def validate_disk_size_threshold(self, library):
        for item in library.get("disk_size_threshold", []):
            path = item.get("path")
            threshold = item.get("threshold")

            try:
                validate_units(threshold)
            except ValueError as err:
                self.log_and_exit(
                    f"Invalid threshold '{threshold}' for path '{path}' in library '{library.get('name')}': {err}"
                )

    def validate_trakt_configuration(self, library, trakt_configured):
        if (
            len(library.get("exclude", {}).get("trakt_lists", [])) > 0
            and not trakt_configured
        ):
            self.log_and_exit(
                f"Trakt lists configured for {library['name']} but trakt is not configured, check your configuration."
            )

    def validate_action_mode(self, library):
        if library["action_mode"] not in VALID_ACTION_MODES:
            self.log_and_exit(
                f"Invalid action_mode '{library['action_mode']}' in library '{library['name']}', it should be either 'delete'."
            )

        # Validate settings per action
        for setting in library:
            if setting in SETTINGS_PER_ACTION and library[
                "action_mode"
            ] not in SETTINGS_PER_ACTION.get(setting, []):
                self.log_and_exit(
                    f"'{setting}' can only be set when action_mode is '{library['action_mode']}' for library '{library['name']}'."
                )

    def validate_watch_status(self, library):
        if "watch_status" in library and library["watch_status"] not in [
            "watched",
            "unwatched",
        ]:
            self.log_and_exit(
                f"Invalid watch_status '{library.get('watch_status')}' in library '{library.get('name')}', it must be either 'watched', 'unwatched', or not set."
            )

        if (
            "watch_status" in library
            and "apply_last_watch_threshold_to_collections" in library
        ):
            self.log_and_exit(
                f"'apply_last_watch_threshold_to_collections' cannot be used when 'watch_status' is set in library '{library.get('name')}'. This would mean entire collections would be deleted when a single item in the collection meets the watch_status criteria."
            )

    def validate_sort_configuration(self, library):
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
