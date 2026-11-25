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
        self._local_server_ids = set()
        self._show_ref_cache = {}

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

    def get_activity(self, section, library_items=None):
        raw_data = self._fetch_history(section)
        if not raw_data:
            return {}

        self._refs_by_key = {}
        self._local_server_ids = self._unique_local_plex_servers(raw_data, section)
        # With server_name set, rating keys from the managed server are
        # still used even if other Plex servers share this library id.
        if len(self._local_server_ids) > 1 and not self._managed_server_id():
            logger.warning(
                "Tracearr history includes %d Plex servers with library id %s; "
                "rating keys will not be used as activity keys. Set "
                "tracearr.server_name to choose one server.",
                len(self._local_server_ids),
                section,
            )
        allowed = self._library_identity_keys(library_items)
        library_types = self._library_media_types(library_items)
        last_activity = {}
        for entry in raw_data:
            activity_entry = self._prepare_activity_entry(entry)
            if activity_entry is None:
                raise TracearrApiError(
                    "Tracearr returned a history record with an unparseable "
                    "watch timestamp; incomplete history cannot be used for "
                    "deletion decisions."
                )
            local = self._is_local_plex_record(entry, section)
            if not self._relates_to_library(
                entry, local, allowed, library_types
            ):
                continue
            for key in self._activity_keys(entry, local=local):
                existing = last_activity.get(key)
                if (
                    existing is None
                    or activity_entry["last_watched"] > existing["last_watched"]
                ):
                    last_activity[key] = activity_entry
            self._remember_refs(entry, local=local)

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
                str(key), section
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
            # identity_name is a user-defined display name, not the
            # server-account username. A colliding display name must not
            # un-protect a requester who has not watched the title.
            name = account.get("username")
            if name and name.strip().lower() == needle:
                return True
        return False

    def _fetch_history(self, section):
        params = {"pageSize": HISTORY_PAGE_SIZE}
        # Resolve the managed server so rating keys can be scoped, but do
        # not pass server_id here. A newer Jellyfin or Emby play of the
        # same title must still be able to match through provider refs.
        if self.server_name and not self._cached_server_id():
            self._resolve_server_id()

        raw_data = []
        cursor = None
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

            raw_data.extend(body["data"])

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

    def _activity_keys(self, entry, local=False):
        keys = []
        if local:
            for field in ("rating_key", "grandparent_rating_key"):
                value = entry.get(field)
                if value:
                    keys.append(str(value))
        required = not local
        if local:
            media_type = entry.get("media_type")
            if media_type == "episode" and not entry.get("grandparent_rating_key"):
                # Rating-key protection for the show is unavailable; the
                # show:* mapping must be resolved or the library skipped.
                required = True
            elif media_type == "movie" and not entry.get("rating_key"):
                required = True
        keys.extend(self._identity_keys(entry, required=required))
        return keys

    @staticmethod
    def _library_identity_keys(library_items):
        if library_items is None:
            return None
        from app.media_cleaner import provider_refs_from_plex

        allowed = set()
        for item in library_items:
            rating_key = getattr(item, "ratingKey", None)
            if rating_key:
                allowed.add(str(rating_key))
            guid = getattr(item, "guid", None)
            if guid:
                allowed.add(str(guid))
            allowed.update(provider_refs_from_plex(item))
        return allowed

    def _relates_to_library(self, entry, local, allowed, library_types=None):
        if local:
            return True
        # None means the caller did not provide the library; keep only local
        # plays so unrelated history cannot bypass the empty-history guard.
        if not allowed:
            return False
        # Skip incompatible types before resolving identity, so a 404 for
        # an unrelated TV episode cannot abort a Movies library run.
        if not self._entry_compatible_with_library(entry, library_types):
            return False
        for key in self._identity_keys(entry, required=True):
            if key in allowed:
                return True
        return False

    @staticmethod
    def _library_media_types(library_items):
        types = set()
        for item in library_items or []:
            media_type = getattr(item, "type", None)
            if media_type:
                types.add(media_type)
        return types

    @staticmethod
    def _entry_compatible_with_library(entry, library_types):
        if not library_types:
            return True
        media_type = entry.get("media_type")
        if media_type == "movie":
            return "movie" in library_types
        if media_type in ("episode", "show"):
            return bool(library_types & {"show", "episode"})
        return True

    def _identity_keys(self, entry, required=False):
        keys = []
        media_type = entry.get("media_type")
        if media_type == "movie":
            keys.extend(self._movie_identity_keys(entry, required=required))
        elif media_type == "episode":
            keys.extend(self._provider_refs("episode", entry))
            keys.extend(self._show_identity_keys(entry, required=required))
        if entry.get("media_id"):
            keys.append(str(entry["media_id"]))
        return keys

    def _movie_identity_keys(self, entry, required=False):
        """Resolve movie:* refs, including via GET /media/{media_id}."""
        refs = self._provider_refs("movie", entry)
        if not refs and entry.get("media_id"):
            body = self._get(
                f"{API_PREFIX}/media/{quote(str(entry['media_id']), safe=':')}",
                allow_404=True,
            )
            if isinstance(body, dict) and body.get("media_type") == "movie":
                refs = self._provider_refs("movie", body)
        if required and not any(key.startswith("movie:") for key in refs):
            target = entry.get("media_id") or "movie"
            raise TracearrApiError(
                "Tracearr did not resolve a canonical movie identity "
                f"for {target}; incomplete history cannot be used for "
                "deletion decisions."
            )
        return refs

    def _show_identity_keys(self, entry, required=False):
        """Map an episode to its show UUID and show:* provider refs."""
        show_media_id = entry.get("show_media_id")
        if not show_media_id and entry.get("media_id"):
            show_media_id = self._show_media_id_from_ref(entry["media_id"])
        if not show_media_id:
            for ref in self._provider_refs("episode", entry):
                show_media_id = self._show_media_id_from_ref(ref)
                if show_media_id:
                    break
        keys = []
        if show_media_id:
            keys.append(str(show_media_id))
            keys.extend(self._show_provider_refs(show_media_id))
        if required and not any(key.startswith("show:") for key in keys):
            target = show_media_id or entry.get("media_id") or "episode"
            raise TracearrApiError(
                "Tracearr did not resolve a canonical show identity "
                f"for {target}; incomplete history cannot be used for "
                "deletion decisions."
            )
        return keys

    def _show_media_id_from_ref(self, ref):
        body = self._get(
            f"{API_PREFIX}/media/{quote(str(ref), safe=':')}",
            allow_404=True,
        )
        if not isinstance(body, dict):
            return None
        if body.get("show_media_id"):
            return str(body["show_media_id"])
        if body.get("media_type") == "show" and body.get("id"):
            return str(body["id"])
        return None

    def _show_provider_refs(self, show_media_id):
        """Resolve a show uuid to show:tvdb:/show:tmdb:/show:imdb: refs."""
        cache_key = str(show_media_id)
        if cache_key in self._show_ref_cache:
            return self._show_ref_cache[cache_key]
        body = self._get(
            f"{API_PREFIX}/media/{quote(cache_key, safe=':')}",
            allow_404=True,
        )
        refs = []
        if isinstance(body, dict) and body.get("media_type") == "show":
            refs = self._provider_refs("show", body)
        self._show_ref_cache[cache_key] = refs
        return refs

    @staticmethod
    def _unique_local_plex_servers(records, section):
        section_id = str(section) if section is not None else None
        return {
            entry.get("server_id")
            for entry in records
            if entry.get("server_type") == "plex"
            and entry.get("server_id")
            and entry.get("library_id") is not None
            and section_id is not None
            and str(entry.get("library_id")) == section_id
        }

    def _is_local_plex_record(self, entry, section):
        """True when this play can safely be keyed by a Plex rating key.

        Library IDs and rating keys are server-local and commonly reused
        (1, 2, 3...). Only a verified managed Plex server (server_name, or
        another resolved identity in _server_id) may publish rating keys.
        Otherwise plays match through provider refs only, as they already
        do when more than one Plex server shares that library id.
        """
        if entry.get("server_type") != "plex":
            return False
        managed = self._managed_server_id()
        if not managed or entry.get("server_id") != managed:
            return False
        library_id = entry.get("library_id")
        return library_id is not None and str(library_id) == str(section)

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

    def _remember_refs(self, entry, local=False):
        if not local:
            return
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

    def _resolve_ref_from_history(self, rating_key, section=None):
        params = {"pageSize": HISTORY_PAGE_SIZE, "rating_key": rating_key}
        server_id = self._managed_server_id()
        if self.server_name and not server_id:
            try:
                server_id = self._resolve_server_id()
            except TracearrApiError:
                return None
        # Without a verified managed server, a unique library-id match is
        # not enough: rating keys are server-local and commonly reused.
        if not server_id:
            return None
        params["server_id"] = server_id
        try:
            records = []
            cursor = None
            while True:
                page_params = dict(params)
                if cursor:
                    page_params["cursor"] = cursor
                body = self._get(f"{API_PREFIX}/history", params=page_params)
                page = body.get("data") if isinstance(body, dict) else None
                if not page:
                    break
                records.extend(page)
                cursor = (body.get("meta") or {}).get("nextCursor")
                if not cursor:
                    break
        except TracearrApiError:
            return None

        candidates = [
            entry
            for entry in records
            if self._is_managed_plex_history(entry, section, server_id)
        ]
        if not candidates:
            return None
        if not server_id:
            servers = {
                entry.get("server_id")
                for entry in candidates
                if entry.get("server_id")
            }
            if len(servers) != 1:
                return None

        entry = candidates[0]
        self._remember_refs(entry, local=True)
        if str(entry.get("grandparent_rating_key") or "") == str(rating_key) and entry.get(
            "show_media_id"
        ):
            return str(entry["show_media_id"])
        cached = self._refs_by_key.get(str(rating_key))
        if cached:
            return cached
        return self._preferred_ref(entry)

    def _managed_server_id(self):
        """The verified managed Plex server, or None.

        A unique library-id match is not a verified identity: library IDs
        are server-local and commonly reused.
        """
        return self._server_id

    def _is_managed_plex_history(self, entry, section, server_id=None):
        if entry.get("server_type") != "plex":
            return False
        if section is not None:
            library_id = entry.get("library_id")
            if library_id is None or str(library_id) != str(section):
                return False
        managed = server_id or self._managed_server_id()
        if managed:
            return entry.get("server_id") == managed
        return True

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
            http_error = requests.HTTPError(
                f"{response.status_code} Error",
                response=response,
            )
            raise TracearrApiError(
                f"Tracearr returned HTTP {response.status_code} for {path}."
            ) from http_error
        try:
            return response.json()
        except ValueError as exc:
            raise TracearrApiError(
                f"Tracearr returned a non-JSON response for {path}."
            ) from exc
