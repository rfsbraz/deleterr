# enconding: utf-8

from tautulli import RawAPI
import logging
from datetime import datetime, timedelta
import json
import logger
import time


def filter_by_most_recent(data, key, sort_key):
    # Create an empty dictionary to hold the highest stopped value for each id
    max_sort_key = {}

    # Go through each dictionary in the list
    for item in data:
        id_ = item[key]
        sort_key_value = item[sort_key]

        # If the id isn't in max_sort_key, add it
        # If it is, but the current sort_key value is higher than the saved one, replace it
        if id_ not in max_sort_key or sort_key_value > max_sort_key[id_][sort_key]:
            max_sort_key[id_] = item

    # Convert the resulting max_sort_key dictionary to a list
    return list(max_sort_key.values())


class Tautulli:
    def __init__(self, config):
        self.config = config
        self.api = RawAPI(
            config.get("tautulli", "url"), config.get("tautulli", "api_key")
        )

    def get_last_episode_activity(self, library_config, section):
        return self.get_activity(section)

    def refresh_library(self, section_id):
        self.api.get_library_media_info(section_id=section_id, refresh=True)

    def get_activity(self, library_config, section):
        last_watched_threshold_date = datetime.now() - timedelta(
            days=library_config.get("last_watched_threshold")
        )
        unwatched_threshold_date = datetime.now() - timedelta(
            days=library_config.get("added_at_threshold")
        )
        min_date = min(last_watched_threshold_date, unwatched_threshold_date)

        # Request params
        start = 0

        # create a dictionary to store last watch activity for each show
        last_activity = {}
        raw_data = []

        while True:
            # load the data
            history = self.api.get_history(
                section_id=section,
                order_column="date",
                order_direction="asc",
                start=start,
                after=min_date,
                length=100,
                include_activity=1
            )

            if len(history["data"]) == 0:
                break

            start += len(history["data"])
            raw_data += history["data"]

            logger.debug(
                "Got %s history items. next start: %s", len(history["data"]), start
            )

        # TODO: we may need to handle rating_key and parent_rating_key to support more complex rules regarding deleting shows, seasons and episodes
        key = (
            "grandparent_rating_key"
            if raw_data[0].get("grandparent_rating_key", "") != ""
            else "rating_key"
        )

        filtered_data = filter_by_most_recent(raw_data, key, "stopped")
        i = 0
        for entry in filtered_data:
            i += 1
            metadata = self.api.get_metadata(entry[key])
            if not metadata:
                # Media was deleted, skip
                continue
            
            last_activity[metadata["guid"]] = {
                "last_watched": datetime.fromtimestamp(entry["stopped"]),
                "title": metadata["title"],
                "year": int(metadata["year"]),
            }

            # Print progress
            logger.debug("[%s/%s] Processed items", i, len(filtered_data))

        return last_activity
