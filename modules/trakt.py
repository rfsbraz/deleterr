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
        items = {}
        max_items_per_list = trakt_config.get("max_items_per_list", 100)

        for url in trakt_config.get("lists", []):
            username, listname, recurrence = extract_info_from_url(url)

            if username and listname:
                for m in trakt.Trakt["users/*/lists/*"].items(
                    username,
                    listname,
                    media="movie",
                    exceptions=True,
                    per_page=max_items_per_list,
                ):
                    items[int(m.get_key("tmdb"))] = {"trakt": m, "list": url}
            elif listname and recurrence:
                movies = []
                if listname == "favorited":
                    logger.warning(
                        "Traktpy does not support favorited movies. Skipping..."
                    )
                elif listname == "watched":
                    logger.warning(
                        "Traktpy does not support watched movies. Skipping..."
                    )
                elif listname == "collected":
                    logger.warning(
                        "Traktpy does not support collected movies. Skipping..."
                    )
                for m in movies:
                    items[int(m.get_key("tmdb"))] = {"trakt": m, "list": url}
            elif listname:
                movies = []
                if listname == "popular":
                    movies = trakt.Trakt["movies"].popular(
                        exceptions=True, per_page=max_items_per_list
                    )
                elif listname == "trending":
                    movies = trakt.Trakt["movies"].trending(
                        exceptions=True, per_page=max_items_per_list
                    )
                for m in movies:
                    items[int(m.get_key("tmdb"))] = {"trakt": m, "list": url}
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
        r"https://trakt.tv/movies/(?P<listname>trending|popular|anticipated|boxoffice)"
    )
    # Pattern to capture watched, collected along with their period
    movie_action_period_pattern = r"https://trakt.tv/movies/(?P<listname>favorited|watched|collected|)/(?P<period>daily|weekly|monthly|yearly)"

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
