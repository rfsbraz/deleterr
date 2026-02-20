import re
from urllib.parse import urlparse

import requests

from app import logger


class Mdblist:
    def __init__(self, api_key, ssl_verify=True):
        self.api_key = api_key
        self.ssl_verify = ssl_verify
        self.base_url = "https://api.mdblist.com"

    def get_all_items_for_url(self, media_type, mdblist_config):
        if media_type not in ["movie", "show"]:
            raise ValueError("Invalid media type. Expected 'movie' or 'show'.")

        items = {}
        max_items_per_list = mdblist_config.get("max_items_per_list", 1000)
        for url in mdblist_config.get("lists", []):
            list_items = self._fetch_list_items(url, max_items_per_list)
            _process_mdblist_item_list(items, list_items, url, media_type)
        return items

    def _fetch_list_items(self, list_url, max_items_per_list):
        list_path = extract_list_path(list_url)
        if not list_path:
            logger.error(f"Could not extract list path from URL: {list_url}")
            return []

        all_items = []
        offset = 0
        limit = 1000

        try:
            while len(all_items) < max_items_per_list:
                response = requests.get(
                    f"{self.base_url}/lists/{list_path}/items/",
                    params={
                        "apikey": self.api_key,
                        "limit": limit,
                        "offset": offset,
                    },
                    verify=self.ssl_verify,
                )
                response.raise_for_status()

                items = response.json()
                if not items:
                    break

                all_items.extend(items)
                offset += limit

                has_more = response.headers.get("X-Has-More", "false").lower() == "true"
                if not has_more:
                    break

        except Exception as e:
            logger.error(f"Failed to fetch Mdblist items from {list_url}")
            logger.debug(f"Error: {e}")

        return all_items[:max_items_per_list]


def extract_list_path(url):
    """Extract the list path from a Mdblist URL.

    Examples:
        https://mdblist.com/lists/username/listname -> username/listname
        https://mdblist.com/lists/username/listname/ -> username/listname
    """
    match = re.match(r"https?://mdblist\.com/lists/(?P<path>[^?#]+)", url)
    if match:
        return match.group("path").rstrip("/")
    return None


def _process_mdblist_item_list(items, list_items, url, media_type):
    """Index Mdblist items by tmdbid (movies) or tvdbid (shows)."""
    for item in list_items:
        try:
            if media_type == "movie":
                item_id = item.get("tmdbid") or item.get("id")
                if item_id is not None:
                    items[int(item_id)] = {"mdblist": item, "list": url}
            else:
                item_id = item.get("tvdbid")
                if item_id is not None:
                    items[int(item_id)] = {"mdblist": item, "list": url}
        except (TypeError, ValueError):
            logger.debug(f"Could not get ID for Mdblist item: {item.get('title', 'unknown')}")
