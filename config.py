# encoding: utf-8

import yaml
import logger
import sys
import requests
from tautulli import RawAPI
from modules.trakt import Trakt

class Config:
    def __init__(self, config_file):
        try:
            with open(config_file, "r", encoding="utf8") as stream:
                self.config = yaml.safe_load(stream)

                if not self.validate_config():
                    logger.error("Invalid configuration, exiting.")
                    exit(1)

                if self.config.get("dry_run"):
                    logger.info("Running in dry-run mode, no changes will be made.")

                if self.config.get("interactive"):
                    logger.info("Running in interactive mode, you will be prompted before any changes are made.")

        except FileNotFoundError:
            logger.error(
                f"Configuration file {config_file} not found. Copy the example config and edit it to your needs."
            )
            sys.exit(1)
        except yaml.YAMLError as exc:
            logger.error(exc)
            sys.exit(1)

    def validate_config(self):
        trakt_configured = False
        if self.config.get("trakt"):
            try:
                t = Trakt(self.config)
                t.test_connection()
                trakt_configured = True
            except Exception as err:
                logger.error(
                    f"Failed to connect to trakt, check your configuration."
                )
                logger.debug(f"Error: {err}")
                return False

        for connection in self.config.get("sonarr") + self.config.get("radarr"):
            try:
                response = requests.get(
                    f"{connection['url']}/system/status",
                    params={"apiKey": connection["api_key"]},
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
            except requests.exceptions.RequestException as err:
                logger.error(
                    f"Failed to connect to {connection['name']} at {connection['url']}, check your configuration."
                )
                logger.debug(f"Error: {err}")
                return False

        try:
            tautulli = self.config.get("tautulli")
            if not tautulli:
                raise KeyError
            api = RawAPI(base_url=tautulli["url"], api_key=tautulli["api_key"])
            api.status()
            response.raise_for_status()
        except KeyError:
            logger.error("Tautulli configuration not found, check your configuration.")
            return False
        except Exception as err:
            logger.error(
                f"Failed to connect to tautulli at {tautulli['url']}, check your configuration."
            )
            logger.debug(f"Error: {err}")
            return False

        for library in self.config.get("libraries", []):
            if len(library.get("exclude", {}).get("trakt_lists", [])) > 0 and not trakt_configured:
                logger.error(
                    f"Trakt lists configured for {library['name']} but trakt is not configured, check your configuration."
                )
                return False
        
            if library["action_mode"] not in ["delete", "unmonitor"]:
                print(
                    f"Invalid action_mode '{library['action_mode']}' in library '{library['name']}', it should be either 'delete' or 'unmonitor'."
                )
                return False

        return True

    def get(self, *keys, default=None):
        """
        Traverse the configuration dictionary with the given keys. If any key is not found,
        return the default value. If no default is provided, None is returned.
        """
        config = self.config
        try:
            for key in keys:
                config = config[key]
            return config
        except KeyError:
            return default
