# encoding: utf-8

from datetime import datetime, timedelta

from tautulli import RawAPI

from app import logger

HISTORY_PAGE_SIZE = 300


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
    def __init__(self, url, api_key, ssl_verify=True):
        self.api = RawAPI(url, api_key, verify=ssl_verify)

    def test_connection(self):
        self.api.status()

    def refresh_library(self, section_id):
        self.api.get_library_media_info(section_id=section_id, refresh=True)

    def get_activity(self, library_config, section):
        last_activity = {}
        min_date = self._calculate_min_date(library_config)
        logger.debug("Fetching last activity since %s", min_date)
        raw_data = self._fetch_history_data(section, min_date)

        # Return empty dictionary if no data is found
        if not raw_data:
            return last_activity

        key = self._determine_key(raw_data)
        filtered_data = filter_by_most_recent(raw_data, key, "stopped")

        for index, entry in enumerate(filtered_data):
            metadata = self.api.get_metadata(entry[key])
            if metadata:
                last_activity[metadata["guid"]] = self._prepare_activity_entry(
                    entry, metadata
                )
            logger.debug("[%s/%s] Processed items", index + 1, len(filtered_data))

        return last_activity

    def _calculate_min_date(self, library_config):
        last_watched_threshold = library_config.get("last_watched_threshold", 0)
        added_at_threshold = library_config.get("added_at_threshold", 0)

        last_watched_threshold_date = datetime.now() - timedelta(
            days=last_watched_threshold
        )
        unwatched_threshold_date = datetime.now() - timedelta(days=added_at_threshold)

        return min(last_watched_threshold_date, unwatched_threshold_date)

    def _fetch_history_data(self, section, min_date):
        start = 0
        raw_data = []
        while True:
            history = self.api.get_history(
                section_id=section,
                order_column="date",
                order_direction="asc",
                start=start,
                after=min_date,
                length=HISTORY_PAGE_SIZE,
                include_activity=1,
            )
            if not history["data"]:
                break

            start += len(history["data"])
            raw_data.extend(history["data"])

        logger.debug("Fetched %s items", len(raw_data))

        return raw_data

    def _determine_key(self, raw_data):
        return (
            "grandparent_rating_key"
            if raw_data[0].get("grandparent_rating_key", "")
            else "rating_key"
        )

    def _prepare_activity_entry(self, entry, metadata):
        return {
            "last_watched": datetime.fromtimestamp(entry["stopped"]),
            "title": metadata["title"],
            "year": int(metadata.get("year") or 0),
        }
