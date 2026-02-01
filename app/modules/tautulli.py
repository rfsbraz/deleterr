# encoding: utf-8

from datetime import datetime

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

    def get_activity(self, section):
        """
        Get watch activity for a library section.

        Fetches all history data from Tautulli and extracts GUID, title, year directly
        from the history response (no separate metadata API calls needed).

        Args:
            section: Plex library section ID

        Returns:
            Dictionary mapping GUID to activity data (last_watched, title, year)
        """
        logger.debug("Fetching all activity history for section %s", section)
        raw_data = self._fetch_history_data(section)

        # Return empty dictionary if no data is found
        if not raw_data:
            return {}

        key = self._determine_key(raw_data)
        filtered_data = filter_by_most_recent(raw_data, key, "stopped")

        # Extract data directly from history response - no metadata API calls needed!
        # The get_history endpoint already returns guid, title, year, grandparent_title
        last_activity = {}
        for entry in filtered_data:
            guid = entry.get("guid")
            if guid:
                last_activity[guid] = self._prepare_activity_entry(entry)

        logger.debug("Processed %d unique items from history", len(last_activity))
        return last_activity

    def _fetch_history_data(self, section):
        start = 0
        raw_data = []
        while True:
            history = self.api.get_history(
                section_id=section,
                order_column="date",
                order_direction="asc",
                start=start,
                length=HISTORY_PAGE_SIZE,
                include_activity=1,
            )
            if not history["data"]:
                break

            start += len(history["data"])
            raw_data.extend(history["data"])

        logger.debug("Fetched %s history entries", len(raw_data))

        return raw_data

    def _determine_key(self, raw_data):
        return (
            "grandparent_rating_key"
            if raw_data[0].get("grandparent_rating_key", "")
            else "rating_key"
        )

    def _prepare_activity_entry(self, entry):
        """
        Prepare activity entry from history data.

        For TV shows, uses grandparent_title (series name).
        For movies, uses title directly.

        Args:
            entry: History entry from Tautulli get_history

        Returns:
            Dict with last_watched, title, and year
        """
        # For TV shows, grandparent_title is the series name
        # For movies, title is the movie name
        title = entry.get("grandparent_title") or entry.get("title")
        return {
            "last_watched": datetime.fromtimestamp(entry["stopped"]),
            "title": title,
            "year": int(entry.get("year") or 0),
        }
