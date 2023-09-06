import trakt
import re
from app import logger


class Trakt:
    def __init__(self, trakt_id, trakt_secret):
        self._configure_trakt(trakt_id, trakt_secret)

    def _configure_trakt(self, trakt_id, trakt_secret):
        trakt.Trakt.configuration.defaults.client(
            id=trakt_id,
            secret=trakt_secret,
        )

    def test_connection(self):
        # Test connection
        trakt.Trakt["lists"].trending(exceptions=True, per_page=1)

    def get_all_movies_for_url(self, trakt_config):
        return self._get_all_items_for_url("movie", trakt_config)

    def get_all_shows_for_url(self, trakt_config):
        return self._get_all_items_for_url("show", trakt_config)

    def _get_all_items_for_url(self, media_type, trakt_config):
        items = {}
        max_items_per_list = trakt_config.get("max_items_per_list", 100)
        for url in trakt_config.get("lists", []):
            username, listname, recurrence = extract_info_from_url(url)
            list_items = self._fetch_list_items(
                media_type, username, listname, recurrence, max_items_per_list
            )
            key = "tmdb" if media_type == "movie" else "tvdb"
            _process_trakt_item_list(items, list_items, url, key)
        return items

    def _fetch_list_items(
        self, media_type, username, listname, recurrence, max_items_per_list
    ):
        if username and listname:
            return self._fetch_user_list_items(
                media_type, username, listname, max_items_per_list
            )
        elif listname and recurrence:
            return self._fetch_recurrent_list_items(media_type, listname)
        elif listname:
            return self._fetch_general_list_items(
                media_type, listname, max_items_per_list
            )
        return []

    def _fetch_user_list_items(
        self, media_type, username, listname, max_items_per_list
    ):
        if listname == "watchlist":
            return trakt.Trakt["users/*/watchlist"].get(
                username,
                media=media_type,
                exceptions=True,
                per_page=max_items_per_list,
            )
        elif listname == "favorites":
            logger.warning(
                f"Traktpy does not support {listname} {media_type}s. Skipping..."
            )
            return []
        
        return trakt.Trakt["users/*/lists/*"].items(
            username,
            listname,
            media=media_type,
            exceptions=True,
            per_page=max_items_per_list,
        )

    def _fetch_recurrent_list_items(self, media_type, listname):
        logger.warning(
            f"Traktpy does not support {listname} {media_type}s. Skipping..."
        )
        return []

    def _fetch_general_list_items(self, media_type, listname, max_items_per_list):
        if listname == "popular":
            return trakt.Trakt[f"{media_type}s"].popular(
                exceptions=True, per_page=max_items_per_list
            )
        elif listname == "trending":
            return trakt.Trakt[f"{media_type}s"].trending(
                exceptions=True, per_page=max_items_per_list
            )
        return []


"""
Transforms a list of trakt items into a dictionary of usable items
"""


def _process_trakt_item_list(items, list_items, url, key):
    for m in list_items:
        try:
            items[int(m.get_key(key))] = {"trakt": m, "list": url}
        except TypeError:
            logger.debug(f"Could not get {key} for {m}")


"""
Extracts the username and listname from a trakt url
returns username, listname, recurrence
"""


def extract_info_from_url(url):
    # Pattern to capture the username and list name
    user_watchlist_pattern = r"https://trakt.tv/users/(?P<username>[^/]+)/(?P<listname>(watchlist|favorites))"
    # Pattern to capture the username and list name
    user_list_pattern = (
        r"https://trakt.tv/users/(?P<username>[^/]+)/lists/(?P<listname>[^/]+)"
    )
    # Pattern to capture trending, popular movies
    movie_pattern = r"https://trakt.tv/(movies|shows)/(?P<listname>trending|popular|anticipated|boxoffice)"
    # Pattern to capture watched, collected along with their period
    movie_action_period_pattern = r"https://trakt.tv/(movies|shows)/(?P<listname>favorited|watched|collected|)/(?P<period>daily|weekly|monthly|yearly)"

    # Check movie action with period pattern
    match = re.match(movie_action_period_pattern, url)
    if match:
        return None, match.group("listname"), match.group("period")

    # Check movie pattern
    match = re.match(movie_pattern, url)
    if match:
        return None, match.group("listname"), None

    # Check user watchlist pattern
    match = re.match(user_watchlist_pattern, url)
    if match:
        return match.group("username"), match.group("listname"), None

    # Check user list pattern
    match = re.match(user_list_pattern, url)
    if match:
        return match.group("username"), match.group("listname"), None

    return None, None, None
