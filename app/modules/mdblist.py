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
            list_items = self._fetch_list_items(url, media_type, max_items_per_list)
            _process_mdblist_item_list(items, list_items, url, media_type)
        return items

    def _fetch_list_items(self, list_url, media_type, max_items_per_list):
        list_path = extract_list_path(list_url)
        if not list_path:
            logger.error(f"Could not extract list path from URL: {list_url}")
            return []

        # API returns {"movies": [...], "shows": [...]}
        response_key = "movies" if media_type == "movie" else "shows"
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

                data = response.json()
                if isinstance(data, dict):
                    items = data.get(response_key, [])
                elif isinstance(data, list):
                    items = data
                else:
                    logger.warning(f"Unexpected mdblist response type from {list_url}: {type(data)}")
                    break

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
    """Index Mdblist items by tmdb id (movies) or tvdb id (shows)."""
    for item in list_items:
        try:
            if media_type == "movie":
                # API fields: "id" is tmdb id; also check nested "ids.tmdb"
                item_id = item.get("id") or (item.get("ids") or {}).get("tmdb")
                if item_id is not None:
                    items[int(item_id)] = {"mdblist": item, "list": url}
            else:
                # API fields: "tvdb_id" or nested "ids.tvdb"
                item_id = item.get("tvdb_id") or (item.get("ids") or {}).get("tvdb")
                if item_id is not None:
                    items[int(item_id)] = {"mdblist": item, "list": url}
        except (TypeError, ValueError):
            logger.debug(f"Could not get ID for Mdblist item: {item.get('title', 'unknown')}")
