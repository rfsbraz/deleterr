import trakt
import re
import logger


class Trakt:
    def __init__(self, config):
        trakt.Trakt.configuration.defaults.client(
            id=config.get("trakt").get("client_id"),
            secret=config.get("trakt").get("client_secret"),
        )

    def test_connection(self):
        # Test connection
        trakt.Trakt["lists"].trending(exceptions=True, per_page=1)

    def get_all_movies_for_url(self, trakt_config):
        return self.get_trakt_items_for_url("movie", trakt_config)
    
    def get_all_shows_for_url(self, trakt_config):
        return self.get_trakt_items_for_url("show", trakt_config)

    def get_trakt_items_for_url(self, media_type, trakt_config):
        items = {}
        max_items_per_list = trakt_config.get("max_items_per_list", 100)

        for url in trakt_config.get("lists", []):
            username, listname, recurrence = extract_info_from_url(url)

            key = "tmdb" if media_type == "movie" else "tvdb"

            if username and listname:
                for m in trakt.Trakt["users/*/lists/*"].items(
                    username,
                    listname,
                    media=media_type,
                    exceptions=True,
                    per_page=max_items_per_list,
                ):
                    items[int(m.get_key(key))] = {"trakt": m, "list": url}
            elif listname and recurrence:
                list_items = []
                if listname == "favorited":
                    logger.warning(
                        f"Traktpy does not support favorited {media_type}s. Skipping..."
                    )
                elif listname == "watched":
                    logger.warning(
                        f"Traktpy does not support watched {media_type}s. Skipping..."
                    )
                elif listname == "collected":
                    logger.warning(
                        f"Traktpy does not support collected {media_type}s. Skipping..."
                    )
                for m in list_items:
                    items[int(m.get_key(key))] = {"trakt": m, "list": url}
            elif listname:
                list_items = []
                if listname == "popular":
                    list_items = trakt.Trakt[f"{media_type}s"].popular(
                        exceptions=True, per_page=max_items_per_list
                    )
                elif listname == "trending":
                    list_items = trakt.Trakt[f"{media_type}s"].trending(
                        exceptions=True, per_page=max_items_per_list
                    )
                for m in list_items:
                    items[int(m.get_key(key))] = {"trakt": m, "list": url}
        return items


"""
Extracts the username and listname from a trakt url
returns username, listname, recurrence
"""


def extract_info_from_url(url):
    # Pattern to capture the username and list name
    user_list_pattern = (
        r"https://trakt.tv/users/(?P<username>[^/]+)/lists/(?P<listname>[^/]+)"
    )
    # Pattern to capture trending, popular movies
    movie_pattern = (
        r"https://trakt.tv/(movies|shows)/(?P<listname>trending|popular|anticipated|boxoffice)"
    )
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

    # Check user list pattern
    match = re.match(user_list_pattern, url)
    if match:
        return match.group("username"), match.group("listname"), None

    return None, None, None
