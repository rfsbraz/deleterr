# encoding: utf-8

from datetime import datetime
from typing import Dict, Optional

from plexapi.server import PlexServer

from app import logger


class PlexWatchProvider:
    """Watch data provider using Plex API directly (no Tautulli needed)."""

    def __init__(self, plex_url, plex_token, ssl_verify=False):
        session = None
        if not ssl_verify:
            import requests

            session = requests.Session()
            session.verify = False
        self.plex = PlexServer(plex_url, plex_token, session=session)
        self._account_id_cache = {}

    def test_connection(self):
        self.plex.library.sections()

    def refresh_library(self, section_id):
        self.plex.library.sectionByID(int(section_id)).refresh()

    def get_activity(self, section) -> Dict[str, Dict]:
        """Get watch activity for a library section.

        Fetches history from Plex and transforms into the same format as
        Tautulli: a dict keyed by GUID and rating key, with values containing
        last_watched, title, and year.
        """
        history = self.plex.history(librarySectionID=int(section), maxresults=100000)

        if not history:
            return {}

        last_activity = {}
        for item in history:
            viewed_at = item.viewedAt
            if not viewed_at:
                continue
            if isinstance(viewed_at, datetime):
                last_watched = viewed_at
            else:
                last_watched = datetime.fromtimestamp(float(viewed_at))

            is_episode = item.type == "episode"
            title = item.grandparentTitle if is_episode else item.title
            year = getattr(item, "year", None)
            if is_episode:
                year = getattr(item, "grandparentYear", year)

            activity_entry = {
                "last_watched": last_watched,
                "title": title,
                "year": year,
            }

            # Key by GUID
            guid = getattr(item, "guid", None)
            if guid:
                self._update_if_newer(last_activity, guid, activity_entry)

            # Key by rating key (grandparentRatingKey for episodes, ratingKey for movies)
            if is_episode:
                grandparent_key = getattr(item, "grandparentRatingKey", None)
                if grandparent_key:
                    self._update_if_newer(
                        last_activity, str(grandparent_key), activity_entry
                    )
            else:
                rating_key = getattr(item, "ratingKey", None)
                if rating_key:
                    self._update_if_newer(
                        last_activity, str(rating_key), activity_entry
                    )

        logger.debug("Processed %d unique items from Plex history", len(last_activity))
        return last_activity

    def has_user_watched(self, section, rating_key, grandparent_rating_key, user):
        """Check if a specific user has watched a media item.

        Args:
            section: Plex library section ID
            rating_key: Rating key for movies
            grandparent_rating_key: Grandparent rating key for TV shows
            user: Plex username to check

        Returns:
            True if the user has watched the item, False otherwise
        """
        if not user:
            return False

        key = grandparent_rating_key or rating_key
        if not key:
            return False

        account_id = self._get_account_id(user)
        if account_id is None:
            logger.warning(f"Could not find Plex account for user '{user}'")
            return False

        try:
            results = self.plex.history(
                librarySectionID=int(section),
                ratingKey=int(key),
                accountID=account_id,
                maxresults=1,
            )
            return len(results) > 0
        except Exception as e:
            logger.warning(
                f"Failed to check Plex watch history for user '{user}' "
                f"(key: {key}): {e}"
            )
            return False

    def _get_account_id(self, username) -> Optional[int]:
        """Resolve a Plex username to a SystemAccount ID, with caching."""
        if username in self._account_id_cache:
            return self._account_id_cache[username]

        try:
            for account in self.plex.systemAccounts():
                if account.name == username:
                    self._account_id_cache[username] = account.id
                    return account.id
            # Lookup succeeded but user was not found - cache the negative result
            self._account_id_cache[username] = None
            return None
        except Exception as e:
            # Do not cache on failure so subsequent calls can retry the API
            logger.warning(f"Failed to fetch Plex system accounts: {e}")
            return None

    @staticmethod
    def _update_if_newer(activity_dict, key, entry):
        """Only update the entry if it's newer than the existing one."""
        if key not in activity_dict or entry["last_watched"] > activity_dict[key]["last_watched"]:
            activity_dict[key] = entry
