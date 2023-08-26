# encoding: utf-8

import yaml
import logger
import sys
import requests
from tautulli import RawAPI
from modules.trakt import Trakt

class Config:
    def __init__(self, config_file):
        self.load_config(config_file)
        self.post_init_validations()

    def load_config(self, config_file):
        try:
            with open(config_file, "r", encoding="utf8") as stream:
                self.settings = yaml.safe_load(stream)
        except FileNotFoundError:
            self.log_and_exit(
                f"Configuration file {config_file} not found. Copy the example config and edit it to your needs."
            )
        except yaml.YAMLError as exc:
            self.log_and_exit(exc)

    def post_init_validations(self):
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
            t = Trakt(self.settings.get("trakt", {}).get("client_id"), self.settings.get("trakt", {}).get("client_secret"))
            t.test_connection()
            return True
        except Exception as err:
            logger.error(f"Failed to connect to Trakt, check your configuration.")
            logger.debug(f"Error: {err}")
            return False

    def validate_sonarr_and_radarr(self):
        for connection in self.settings.get("sonarr") + self.settings.get("radarr"):
            if not self.test_api_connection(connection):
                return False
        return True

    def test_api_connection(self, connection):
        try:
            response = requests.get(
                f"{connection['url']}/system/status",
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
            tautulli = self.settings.get("tautulli")
            if not tautulli:
                raise KeyError
            api = RawAPI(base_url=tautulli["url"], api_key=tautulli["api_key"])
            api.status()
        except KeyError:
            logger.error("Tautulli configuration not found, check your configuration.")
            return False
        except Exception as err:
            logger.error(
                f"Failed to connect to tautulli at {tautulli['url']}, check your configuration."
            )
            logger.debug(f"Error: {err}")
            return False
        
        return True

    def validate_libraries(self):
        trakt_configured = self.settings.get("trakt") is not None

        for library in self.settings.get("libraries", []):
            if (
                len(library.get("exclude", {}).get("trakt_lists", [])) > 0
                and not trakt_configured
            ):
                logger.error(
                    f"Trakt lists configured for {library['name']} but trakt is not configured, check your configuration."
                )
                return False

            if library["action_mode"] not in ["delete"]:
                logger.error(
                    f"Invalid action_mode '{library['action_mode']}' in library '{library['name']}', it should be either 'delete'."
                )
                return False
        
        return True