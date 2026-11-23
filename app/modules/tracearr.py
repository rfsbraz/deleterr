# encoding: utf-8

from datetime import datetime
from urllib.parse import quote

import requests

from app import logger
from app.modules.tautulli import TautulliApiError

HISTORY_PAGE_SIZE = 100
API_PREFIX = "/api/v2/public"


class TracearrApiError(TautulliApiError):
    """Raised when Tracearr returns an invalid or unexpected API response.

    Subclasses TautulliApiError so the existing per-library watch-provider
    error handling (scheduled runs and --free-up) skips the library instead
    of treating incomplete history as "nothing was watched".
    """


def _parse_iso_datetime(value):
    """Parse an API date-time into a naive local datetime.

    Tautulli uses datetime.fromtimestamp, which is also naive local, and
    deletion rules subtract last_watched from datetime.now().
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone().replace(tzinfo=None)
    return parsed


class Tracearr:
    """Watch-history provider backed by Tracearr Public API v2."""

    def __init__(self, url, api_key, ssl_verify=True, server_name=None):
        self.url = (url or "").rstrip("/")
        self.api_key = api_key
        self.ssl_verify = ssl_verify
        self.server_name = server_name
        self._server_id = None
        self._refs_by_key = {}

    def test_connection(self):
        body = self._get(f"{API_PREFIX}/servers")
        servers = self._require_list(body, "data", "servers")
        if self.server_name:
            self._resolve_server_id(servers)

    def refresh_library(self, section_id):
        logger.debug(
            "Tracearr has no public library refresh endpoint; skipping section %s",
            section_id,
        )

    def get_activity(self, section):
        raw_data = self._fetch_history(section)
        if not raw_data:
            return {}

        self._refs_by_key = {}
        last_activity = {}
        for entry in raw_data:
            activity_entry = self._prepare_activity_entry(entry)
            if activity_entry is None:
                continue
            for key in self._activity_keys(entry):
                existing = last_activity.get(key)
                if (
                    existing is None
                    or activity_entry["last_watched"] > existing["last_watched"]
                ):
                    last_activity[key] = activity_entry
            self._remember_refs(entry)

        logger.debug("Processed %d unique items from Tracearr history", len(last_activity))
        return last_activity

    def has_user_watched(self, section, rating_key, grandparent_rating_key, user):
        if not user:
            return False

        key = grandparent_rating_key or rating_key
        if not key:
            return False

        try:
            ref = self._refs_by_key.get(str(key)) or self._resolve_ref_from_history(
                str(key)
            )
            if not ref:
                return False
            params = {"window": "all_time"}
            server_id = self._cached_server_id()
            if server_id:
                params["server_id"] = server_id
            body = self._get(
                f"{API_PREFIX}/media/{quote(str(ref), safe=':')}/watchers",
                params=params,
                allow_404=True,
            )
        except TracearrApiError as exc:
            logger.warning(
                "Failed to check Tracearr watchers for user '%s' (key: %s): %s",
                user,
                key,
                exc,
            )
            return False

        if not body:
            return False
        watchers = body.get("watchers")
        if not isinstance(watchers, list):
            logger.warning("Tracearr returned an invalid watchers response")
            return False

        needle = user.strip().lower()
        for watcher in watchers:
            account = watcher.get("user") or {}
            for name in (account.get("username"), account.get("identity_name")):
                if name and name.strip().lower() == needle:
                    return True
        return False

    def _fetch_history(self, section):
        params = {"pageSize": HISTORY_PAGE_SIZE}
        server_id = self._cached_server_id()
        if self.server_name and not server_id:
            server_id = self._resolve_server_id()
        if server_id:
            params["server_id"] = server_id

        raw_data = []
        cursor = None
        section_id = str(section) if section is not None else None
        while True:
            page_params = dict(params)
            if cursor:
                page_params["cursor"] = cursor
            try:
                body = self._get(f"{API_PREFIX}/history", params=page_params)
            except TracearrApiError as exc:
                raise TracearrApiError(
                    "Tracearr history request failed"
                    f"{' during pagination' if cursor else ''}; "
                    "incomplete history cannot be used for deletion decisions."
                ) from exc

            if (
                not isinstance(body, dict)
                or "data" not in body
                or "meta" not in body
                or not isinstance(body["data"], list)
            ):
                raise TracearrApiError(
                    "Tracearr returned an invalid history response: expected a "
                    "dict with 'data' and 'meta' keys. Check that Tracearr is "
                    "reachable and running 2.0 or later before retrying."
                )

            for entry in body["data"]:
                library_id = entry.get("library_id")
                if (
                    section_id
                    and library_id is not None
                    and str(library_id) != section_id
                ):
                    continue
                raw_data.append(entry)

            cursor = (body.get("meta") or {}).get("nextCursor")
            if not cursor or not body["data"]:
                break

        logger.debug("Fetched %s Tracearr history entries", len(raw_data))
        return raw_data

    def _prepare_activity_entry(self, entry):
        last_watched = _parse_iso_datetime(
            entry.get("stopped_at") or entry.get("started_at")
        )
        if last_watched is None:
            return None
        title = entry.get("show_title") or entry.get("media_title")
        return {
            "last_watched": last_watched,
            "title": title,
            "year": int(entry.get("year") or 0),
        }

    def _activity_keys(self, entry):
        keys = []
        for field in ("rating_key", "grandparent_rating_key"):
            value = entry.get(field)
            if value:
                keys.append(str(value))
        media_type = entry.get("media_type")
        if media_type == "movie":
            keys.extend(self._provider_refs("movie", entry))
        elif media_type == "episode":
            keys.extend(self._provider_refs("episode", entry))
            if entry.get("show_media_id"):
                keys.append(str(entry["show_media_id"]))
        if entry.get("media_id"):
            keys.append(str(entry["media_id"]))
        return keys

    @staticmethod
    def _provider_refs(kind, entry):
        refs = []
        if entry.get("tmdb_id") is not None:
            refs.append(f"{kind}:tmdb:{entry['tmdb_id']}")
        if entry.get("imdb_id"):
            refs.append(f"{kind}:imdb:{entry['imdb_id']}")
        if entry.get("tvdb_id") is not None:
            refs.append(f"{kind}:tvdb:{entry['tvdb_id']}")
        return refs

    def _preferred_ref(self, entry):
        media_type = entry.get("media_type")
        if media_type == "movie":
            refs = self._provider_refs("movie", entry)
            return refs[0] if refs else entry.get("media_id")
        if media_type == "episode":
            if entry.get("media_id"):
                return entry["media_id"]
            refs = self._provider_refs("episode", entry)
            return refs[0] if refs else None
        return entry.get("media_id")

    def _remember_refs(self, entry):
        show_ref = entry.get("show_media_id")
        grandparent = entry.get("grandparent_rating_key")
        if grandparent and show_ref:
            self._refs_by_key[str(grandparent)] = str(show_ref)

        rating_key = entry.get("rating_key")
        if not rating_key:
            return
        if entry.get("media_type") == "movie":
            ref = self._preferred_ref(entry)
        else:
            ref = entry.get("media_id") or self._preferred_ref(entry)
        if ref:
            self._refs_by_key[str(rating_key)] = str(ref)

    def _resolve_ref_from_history(self, rating_key):
        params = {"pageSize": 1, "rating_key": rating_key}
        server_id = self._cached_server_id()
        if self.server_name and not server_id:
            try:
                server_id = self._resolve_server_id()
            except TracearrApiError:
                server_id = None
        if server_id:
            params["server_id"] = server_id
        try:
            body = self._get(f"{API_PREFIX}/history", params=params)
        except TracearrApiError:
            return None
        records = body.get("data") if isinstance(body, dict) else None
        if not records:
            return None
        entry = records[0]
        self._remember_refs(entry)
        if str(entry.get("grandparent_rating_key") or "") == str(rating_key) and entry.get(
            "show_media_id"
        ):
            return str(entry["show_media_id"])
        return self._refs_by_key.get(str(rating_key)) or self._preferred_ref(entry)

    def _cached_server_id(self):
        return self._server_id

    def _resolve_server_id(self, servers=None):
        if self._server_id:
            return self._server_id
        if not self.server_name:
            return None
        if servers is None:
            body = self._get(f"{API_PREFIX}/servers")
            servers = self._require_list(body, "data", "servers")
        name = self.server_name.lower()
        matches = [
            server
            for server in servers
            if (server.get("server_name") or "").lower() == name
        ]
        if not matches:
            raise TracearrApiError(
                f"No Tracearr server named '{self.server_name}' was found."
            )
        if len(matches) > 1:
            raise TracearrApiError(
                f"Multiple Tracearr servers are named '{self.server_name}'."
            )
        self._server_id = matches[0]["server_id"]
        return self._server_id

    def _require_list(self, body, key, label):
        if not isinstance(body, dict) or key not in body or not isinstance(body[key], list):
            raise TracearrApiError(
                f"Tracearr returned an invalid {label} response: expected a "
                f"dict with a '{key}' list."
            )
        return body[key]

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

    def _get(self, path, params=None, allow_404=False):
        url = f"{self.url}{path}"
        try:
            response = requests.get(
                url,
                headers=self._headers(),
                params=params,
                verify=self.ssl_verify,
                timeout=30,
            )
        except requests.RequestException as exc:
            raise TracearrApiError(
                f"Tracearr request failed for {path} ({type(exc).__name__}); "
                "incomplete history cannot be used for deletion decisions."
            ) from exc

        if response.status_code == 404 and allow_404:
            return None
        if response.status_code >= 400:
            raise TracearrApiError(
                f"Tracearr returned HTTP {response.status_code} for {path}."
            )
        try:
            return response.json()
        except ValueError as exc:
            raise TracearrApiError(
                f"Tracearr returned a non-JSON response for {path}."
            ) from exc
