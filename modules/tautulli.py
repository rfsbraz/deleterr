# enconding: utf-8

from tautulli import RawAPI
import logging
from datetime import datetime
import json
import logger


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

    def get_last_episode_activity(self):
        return self.get_activity("episode")

    def get_last_movie_activity(self):
        return self.get_activity("movie")

    def refresh_library(self, section_id):
        self.api.get_library_media_info(section_id=section_id, refresh=True)

    def get_activity(self, media_type, length=100):
        # load the data
        history = self.api.get_history(media_type=media_type, length=length)

        # create a dictionary to store last watch activity for each show
        last_activity = []

        key = (
            "grandparent_rating_key"
            if history.get("data")[0].get("grandparent_rating_key", "") != ""
            else "rating_key"
        )

        filtered_data = filter_by_most_recent(history["data"], key, "stopped")
        i = 0
        for entry in filtered_data:
            i += 1
            metadata = self.api.get_metadata(entry["rating_key"])

            item_id = None
            for guid in metadata.get("guids", []):
                if "tmdb://" in guid:
                    item_id = guid.replace("tmdb://", "")
                    break

            last_activity.append(
                {
                    "last_watched": datetime.fromtimestamp(entry["stopped"]),
                    "title": entry["title"],
                    "year": entry["year"],
                    "guid": item_id,
                    "rating_key": entry["rating_key"],
                }
            )

            # Print progress
            logger.debug("[%s/%s] Processed movies", i, len(filtered_data))

        return last_activity
