# encoding: utf-8

import os
import signal
import sys
import time

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
from app.modules.radarr import DRadarr
from app.modules.sonarr import DSonarr
from app.modules.trakt import Trakt
from app.modules.overseerr import Overseerr
from app.utils import validate_units

def env_constructor(loader, node):
    env_var = loader.construct_scalar(node)
    env_value = os.getenv(env_var)
    
    if env_value is None:
        message = f"Environment variable '{env_var}' is not set."
        logger.error(message)
        raise ValueError(message)
    
    return env_value


def hang_on_error(msg):
    """Log error and hang indefinitely to prevent restart loops."""
    logger.error(msg)
    logger.error("Container will stay idle. Fix the configuration and restart the container.")
    # Set up signal handler for graceful shutdown
    def shutdown_handler(signum, frame):
        logger.info("Received shutdown signal, exiting.")
        sys.exit(1)
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)
    # Sleep forever until manually stopped
    while True:
        time.sleep(3600)


def load_config(config_file):
    try:
        full_path = os.path.abspath(config_file)

        with open(full_path, "r", encoding="utf8") as stream:
            logger.debug("Loading configuration from %s", full_path)
            return load_yaml(stream)

    except FileNotFoundError:
        hang_on_error(
            f"Configuration file {config_file} not found. Copy the example config and edit it to your needs."
        )
    except yaml.YAMLError as exc:
        hang_on_error(f"YAML parsing error: {exc}")

def load_yaml(stream):
    class CustomLoader(yaml.SafeLoader):
        pass
    
    CustomLoader.add_constructor('!env', env_constructor)

    return Config(yaml.load(stream, Loader=CustomLoader))  

def test_radarr_connection(connection):
    name = connection["name"]
    url = connection["url"]
    try:
        if not DRadarr(name, url, connection["api_key"]).validate_connection():
            logger.error(
                f"Radarr '{name}' at {url} did not respond correctly. "
                "Verify the URL and API key are correct."
            )
            return False
        return True
    except Exception as err:
        error_msg = str(err).lower()
        if "401" in error_msg or "unauthorized" in error_msg:
            logger.error(
                f"Radarr '{name}' authentication failed: Invalid API key. "
                "Check your api_key configuration."
            )
        elif "connection" in error_msg or "timeout" in error_msg:
            logger.error(
                f"Cannot reach Radarr '{name}' at {url}: {err}. "
                "Verify the URL is correct and Radarr is running."
            )
        else:
            logger.error(f"Failed to connect to Radarr '{name}' at {url}: {err}")
        return False


class Config:
    def __init__(self, config_file):
        self.settings = config_file

    def validate(self):
        if not self.validate_config():
            self.log_and_exit("Invalid configuration, exiting.")

        if self.settings.get("dry_run"):
            logger.info("Running in dry-run mode, no changes will be made.")


    def log_and_exit(self, msg):
        hang_on_error(msg)

    def validate_config(self):
        return (
                self.validate_trakt()
                and self.validate_sonarr_and_radarr_instances()
                and self.validate_tautulli()
                and self.validate_overseerr()
                and self.validate_notifications()
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
            error_msg = str(err).lower()
            if "401" in error_msg or "unauthorized" in error_msg or "invalid" in error_msg:
                logger.error(
                    f"Trakt authentication failed: {err}. "
                    "Verify your client_id and client_secret are correct."
                )
            elif "timeout" in error_msg or "connection" in error_msg:
                logger.error(
                    f"Cannot reach Trakt API: {err}. "
                    "Check your internet connection and firewall settings."
                )
            else:
                logger.error(f"Trakt connection failed: {err}")
            return False

    def validate_notifications(self):
        """Validate notification configuration if present."""
        notification_config = self.settings.get("notifications")
        if not notification_config:
            return True

        # Validate min_deletions_to_notify is non-negative
        min_deletions = notification_config.get("min_deletions_to_notify", 0)
        if not isinstance(min_deletions, int) or min_deletions < 0:
            self.log_and_exit(
                "notifications.min_deletions_to_notify must be a non-negative integer"
            )

        # Validate webhook method if configured
        webhook_config = notification_config.get("webhook", {})
        if webhook_config:
            method = webhook_config.get("method", "POST")
            if method not in ["POST", "PUT"]:
                self.log_and_exit(
                    f"Invalid webhook method '{method}'. Supported values are POST and PUT."
                )

        # Log configured providers
        providers = []
        if notification_config.get("discord", {}).get("webhook_url"):
            providers.append("discord")
        if notification_config.get("slack", {}).get("webhook_url"):
            providers.append("slack")
        if notification_config.get("telegram", {}).get("bot_token") and notification_config.get("telegram", {}).get("chat_id"):
            providers.append("telegram")
        if notification_config.get("webhook", {}).get("url"):
            providers.append("webhook")

        if providers:
            logger.info(f"Notification providers configured: {', '.join(providers)}")
        elif notification_config.get("enabled", True):
            logger.warning("Notifications enabled but no providers configured")

        return True

    def validate_overseerr(self):
        """Validate Overseerr connection if configured."""
        overseerr_config = self.settings.get("overseerr")
        if not overseerr_config:
            return True

        if not overseerr_config.get("url"):
            logger.error("Overseerr URL is required when overseerr is configured.")
            return False

        if not overseerr_config.get("api_key"):
            logger.error("Overseerr API key is required when overseerr is configured.")
            return False

        try:
            ssl_verify = self.settings.get("ssl_verify", False)
            overseerr = Overseerr(
                overseerr_config.get("url"),
                overseerr_config.get("api_key"),
                ssl_verify=ssl_verify,
            )
            if not overseerr.test_connection():
                logger.error(
                    f"Failed to connect to Overseerr at {overseerr_config.get('url')}, check your configuration."
                )
                return False
            return True
        except Exception as err:
            error_msg = str(err).lower()
            url = overseerr_config.get('url')
            if "401" in error_msg or "403" in error_msg or "unauthorized" in error_msg:
                logger.error(
                    f"Overseerr authentication failed at {url}: {err}. "
                    "Verify your API key is correct."
                )
            elif "timeout" in error_msg or "connection" in error_msg:
                logger.error(
                    f"Cannot reach Overseerr at {url}: {err}. "
                    "Check the URL and ensure Overseerr is running."
                )
            elif "ssl" in error_msg or "certificate" in error_msg:
                logger.error(
                    f"SSL error connecting to Overseerr at {url}: {err}. "
                    "Try setting ssl_verify: false in your config if using self-signed certificates."
                )
            else:
                logger.error(f"Overseerr connection failed at {url}: {err}")
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

    def validate_sonarr_and_radarr_instances(self):
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
            for connection in sonarr_settings
        ) and all(
            test_radarr_connection(connection)
            for connection in radarr_settings
        )

    def test_api_connection(self, connection):
        name = connection['name']
        url = connection['url']
        try:
            response = requests.get(
                f"{url}/api",
                params={"apiKey": connection["api_key"]},
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            return True
        except requests.exceptions.ConnectionError as err:
            logger.error(
                f"Cannot reach Sonarr instance '{name}' at {url}: {err}. "
                "Verify the URL is correct and Sonarr is running."
            )
            return False
        except requests.exceptions.Timeout as err:
            logger.error(
                f"Connection to Sonarr '{name}' at {url} timed out: {err}. "
                "The server may be slow or overloaded."
            )
            return False
        except requests.exceptions.HTTPError as err:
            status_code = err.response.status_code if err.response else "unknown"
            if status_code == 401:
                logger.error(
                    f"Sonarr '{name}' authentication failed (HTTP 401): Invalid API key. "
                    "Check your api_key configuration."
                )
            elif status_code == 403:
                logger.error(
                    f"Sonarr '{name}' access denied (HTTP 403): API key may lack permissions."
                )
            elif status_code >= 500:
                logger.error(
                    f"Sonarr '{name}' server error (HTTP {status_code}): {err}. "
                    "Check Sonarr logs for details."
                )
            else:
                logger.error(f"Sonarr '{name}' returned HTTP {status_code}: {err}")
            return False
        except requests.exceptions.RequestException as err:
            logger.error(f"Failed to connect to Sonarr '{name}' at {url}: {err}")
            return False

    def validate_tautulli(self):
        try:
            tautulli_config = self.settings.get("tautulli")
            if not tautulli_config:
                raise KeyError
            tautulli = Tautulli(tautulli_config["url"], tautulli_config["api_key"])
            tautulli.test_connection()
        except KeyError:
            logger.error(
                "Tautulli configuration not found. "
                "Add 'tautulli' section with 'url' and 'api_key' to your config."
            )
            return False
        except Exception as err:
            url = tautulli_config.get('url', 'unknown')
            error_msg = str(err).lower()
            if "401" in error_msg or "unauthorized" in error_msg or "invalid" in error_msg:
                logger.error(
                    f"Tautulli authentication failed at {url}: {err}. "
                    "Verify your API key is correct (Settings -> Web Interface -> API Key)."
                )
            elif "timeout" in error_msg or "connection" in error_msg:
                logger.error(
                    f"Cannot reach Tautulli at {url}: {err}. "
                    "Check the URL and ensure Tautulli is running."
                )
            else:
                logger.error(f"Tautulli connection failed at {url}: {err}")
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
            self.validate_justwatch_exclusions(library)
            self.validate_radarr_exclusions(library)
            self.validate_sonarr_exclusions(library)
            self.validate_overseerr_exclusions(library)

        return True

    def validate_justwatch_exclusions(self, library):
        """Validate JustWatch exclusion configuration for a library."""
        jw_exclusions = library.get("exclude", {}).get("justwatch", {})
        if not jw_exclusions:
            return True

        # Check that available_on and not_available_on are mutually exclusive
        if jw_exclusions.get("available_on") and jw_exclusions.get("not_available_on"):
            self.log_and_exit(
                f"JustWatch exclusions in library '{library.get('name')}': "
                "'available_on' and 'not_available_on' are mutually exclusive. Use only one."
            )

        # Require country setting (from library config or global config)
        global_jw = self.settings.get("justwatch", {})
        library_country = jw_exclusions.get("country")
        global_country = global_jw.get("country")

        if not library_country and not global_country:
            self.log_and_exit(
                f"JustWatch exclusions in library '{library.get('name')}' require a 'country' setting. "
                "Set it either in the library's exclude.justwatch.country or globally in justwatch.country."
            )

        # Validate that providers is a list if provided
        for mode in ["available_on", "not_available_on"]:
            providers = jw_exclusions.get(mode)
            if providers is not None and not isinstance(providers, list):
                self.log_and_exit(
                    f"JustWatch exclusions in library '{library.get('name')}': "
                    f"'{mode}' must be a list of provider names."
                )

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

            # Support comma-separated fields for multi-level sorting
            if sort_field:
                fields = [f.strip() for f in sort_field.split(",")]
                for field in fields:
                    if field not in VALID_SORT_FIELDS:
                        self.log_and_exit(
                            f"Invalid sort field '{field}' in library '{library['name']}', supported values are {VALID_SORT_FIELDS}."
                        )

            # Support comma-separated orders for multi-level sorting
            if sort_order:
                orders = [o.strip() for o in sort_order.split(",")]
                for order in orders:
                    if order not in VALID_SORT_ORDERS:
                        self.log_and_exit(
                            f"Invalid sort order '{order}' in library '{library['name']}', supported values are {VALID_SORT_ORDERS}."
                        )

    def validate_radarr_exclusions(self, library):
        exclude = library.get("exclude", {})

        # If exclude is not set, no need to validate
        if not exclude:
            return True

        radar_exclusions = exclude.get("radarr", {})
        if not radar_exclusions:
            return True

        if not library.get("radarr"):
            self.log_and_exit(
                f"Radarr exclusions set for library '{library['name']}' but no radarr instance is set."
            )

        allowed_exclusions = ["tags", "quality_profiles", "paths", "monitored"]
        for exclusion in radar_exclusions:
            if exclusion not in allowed_exclusions:
                self.log_and_exit(
                    f"Invalid exclusion '{exclusion}' in library '{library['name']}', supported values are {allowed_exclusions}."
                )

        radarr_settings = self.settings.get("radarr", [])
        # Warn if tags do not exist in radarr
        if "tags" in radar_exclusions:
            for connection in radarr_settings:
                radarr_instance = DRadarr(connection["name"], connection["url"], connection["api_key"])
                tags = radarr_instance.get_tags()
                for tag in radar_exclusions["tags"]:
                    if tag not in [t["label"] for t in tags]:
                        logger.warning(
                            f"Radarr tag '{tag}' does not exist in instance '{connection['name']}'"
                        )

        # Warn if quality profiles do not exist in radarr
        if "quality_profiles" in radar_exclusions:
            profiles = radarr_instance.get_quality_profiles()
            for profile in radar_exclusions["quality_profiles"]:
                if profile not in [p["name"] for p in profiles]:
                    logger.warning(
                        f"Radarr profile '{profile}' does not exist in instance '{connection['name']}'"
                    )

        return True

    def validate_sonarr_exclusions(self, library):
        exclude = library.get("exclude", {})

        # If exclude is not set, no need to validate
        if not exclude:
            return True

        sonarr_exclusions = exclude.get("sonarr", {})
        if not sonarr_exclusions:
            return True

        if not library.get("sonarr"):
            self.log_and_exit(
                f"Sonarr exclusions set for library '{library['name']}' but no sonarr instance is set."
            )

        allowed_exclusions = ["status", "tags", "quality_profiles", "paths", "monitored"]
        for exclusion in sonarr_exclusions:
            if exclusion not in allowed_exclusions:
                self.log_and_exit(
                    f"Invalid exclusion '{exclusion}' in library '{library['name']}', supported values are {allowed_exclusions}."
                )

        # Validate status values
        valid_statuses = ["continuing", "ended", "upcoming", "deleted"]
        if "status" in sonarr_exclusions:
            for status in sonarr_exclusions["status"]:
                if status.lower() not in valid_statuses:
                    self.log_and_exit(
                        f"Invalid Sonarr status '{status}' in library '{library['name']}'. Supported values are {valid_statuses}."
                    )

        sonarr_settings = self.settings.get("sonarr", [])
        # Warn if tags do not exist in sonarr
        if "tags" in sonarr_exclusions:
            for connection in sonarr_settings:
                sonarr_instance = DSonarr(connection["name"], connection["url"], connection["api_key"])
                tags = sonarr_instance.get_tags()
                for tag in sonarr_exclusions["tags"]:
                    if tag.lower() not in [t["label"].lower() for t in tags]:
                        logger.warning(
                            f"Sonarr tag '{tag}' does not exist in instance '{connection['name']}'"
                        )

        # Warn if quality profiles do not exist in sonarr
        if "quality_profiles" in sonarr_exclusions:
            for connection in sonarr_settings:
                sonarr_instance = DSonarr(connection["name"], connection["url"], connection["api_key"])
                profiles = sonarr_instance.get_quality_profiles()
                for profile in sonarr_exclusions["quality_profiles"]:
                    if profile not in [p["name"] for p in profiles]:
                        logger.warning(
                            f"Sonarr profile '{profile}' does not exist in instance '{connection['name']}'"
                        )

        return True

    def validate_overseerr_exclusions(self, library):
        """Validate Overseerr exclusion configuration for a library."""
        overseerr_exclusions = library.get("exclude", {}).get("overseerr", {})
        if not overseerr_exclusions:
            return True

        # Require global Overseerr config if exclusions are used
        if not self.settings.get("overseerr"):
            self.log_and_exit(
                f"Overseerr exclusions in library '{library.get('name')}' require a global 'overseerr' configuration. "
                "Add overseerr.url and overseerr.api_key to your config."
            )

        # Validate mode
        valid_modes = ["exclude", "include_only"]
        mode = overseerr_exclusions.get("mode", "exclude")
        if mode not in valid_modes:
            self.log_and_exit(
                f"Invalid Overseerr exclusion mode '{mode}' in library '{library.get('name')}'. "
                f"Supported values are {valid_modes}."
            )

        # Validate users list format
        users = overseerr_exclusions.get("users")
        if users is not None and not isinstance(users, list):
            self.log_and_exit(
                f"Overseerr exclusions in library '{library.get('name')}': "
                "'users' must be a list of usernames or emails."
            )

        # Validate request_status list format
        request_status = overseerr_exclusions.get("request_status")
        if request_status is not None:
            if not isinstance(request_status, list):
                self.log_and_exit(
                    f"Overseerr exclusions in library '{library.get('name')}': "
                    "'request_status' must be a list of status values."
                )
            valid_statuses = ["pending", "approved", "declined"]
            for status in request_status:
                if status.lower() not in valid_statuses:
                    self.log_and_exit(
                        f"Invalid Overseerr request_status '{status}' in library '{library.get('name')}'. "
                        f"Supported values are {valid_statuses}."
                    )

        # Validate min_request_age_days format
        min_request_age_days = overseerr_exclusions.get("min_request_age_days")
        if min_request_age_days is not None:
            if not isinstance(min_request_age_days, int) or min_request_age_days < 0:
                self.log_and_exit(
                    f"Overseerr exclusions in library '{library.get('name')}': "
                    "'min_request_age_days' must be a non-negative integer."
                )

        return True
