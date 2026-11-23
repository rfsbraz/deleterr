from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from app.modules.tautulli import TautulliApiError
from app.modules.tracearr import Tracearr, TracearrApiError
from app.modules.watch_provider import WatchDataProvider
from tests.modules.fixtures.tracearr_v2 import (
    EPISODE_HISTORY,
    MOVIE_HISTORY,
    MOVIE_MEDIA_ID,
    SERVER_ID,
    SERVERS_RESPONSE,
    SHOW_MEDIA,
    SHOW_MEDIA_ID,
    history_record,
    history_response,
    media_resource,
    watchers_response,
)


def _iso_to_local(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone().replace(
        tzinfo=None
    )


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.status_code = status_code
        self._payload = payload
        self.content = b"{}" if payload is not None else b""

    def json(self):
        if self._payload is None or isinstance(self._payload, str):
            raise ValueError("No JSON")
        return self._payload


class FakeSession:
    """Records requests and returns canned Tracearr v2 payloads by path."""

    def __init__(self, routes):
        # routes: list of (method, path_suffix_or_callable, response_or_callable)
        self.routes = list(routes)
        self.calls = []

    def get(self, url, headers=None, params=None, verify=True, timeout=None):
        self.calls.append(
            {"url": url, "headers": headers or {}, "params": params or {}, "verify": verify, "timeout": timeout}
        )
        parsed = urlparse(url)
        path = parsed.path
        for matcher, responder in self.routes:
            if matcher(path, params or {}):
                result = responder(path, params or {}) if callable(responder) else responder
                if isinstance(result, FakeResponse):
                    return result
                return FakeResponse(result)
        raise AssertionError(f"No fake route for GET {path} params={params}")


def _path_is(suffix):
    return lambda path, params: path.endswith(suffix)


def _is_show_media(path, params):
    return path.endswith(f"/media/{SHOW_MEDIA_ID}") and not path.endswith("/watchers")


@pytest.fixture
def provider_factory():
    def factory(routes, server_name=None, ssl_verify=False):
        session = FakeSession(routes)
        with patch("app.modules.tracearr.requests.get", session.get):
            provider = Tracearr(
                "http://tracearr.example.com",
                "trr_pub_test",
                ssl_verify=ssl_verify,
                server_name=server_name,
            )
            # Keep the patch active for the returned object's lifetime by
            # attaching the session; tests should use the context themselves.
        return provider, session

    return factory



def _with_managed_server(routes):
    """Prefix the official /servers payload so server_name can be resolved."""
    return [(_path_is("/api/v2/public/servers"), SERVERS_RESPONSE), *routes]


def _provider(routes, **kwargs):
    session = FakeSession(routes)
    patcher = patch("app.modules.tracearr.requests.get", session.get)
    patcher.start()
    provider = Tracearr(
        "http://tracearr.example.com",
        "trr_pub_test",
        ssl_verify=kwargs.get("ssl_verify", False),
        server_name=kwargs.get("server_name"),
    )
    return provider, session, patcher


class TestTracearrProtocol:
    def test_class_satisfies_protocol(self):
        assert issubclass(Tracearr, WatchDataProvider)

    def test_error_is_handled_like_tautulli(self):
        assert issubclass(TracearrApiError, TautulliApiError)


class TestTestConnection:
    def test_servers_endpoint_and_bearer_auth(self):
        provider, session, patcher = _provider(
            [(_path_is("/api/v2/public/servers"), SERVERS_RESPONSE)]
        )
        try:
            provider.test_connection()
        finally:
            patcher.stop()

        assert len(session.calls) == 1
        call = session.calls[0]
        assert call["url"] == "http://tracearr.example.com/api/v2/public/servers"
        assert call["headers"]["Authorization"] == "Bearer trr_pub_test"
        assert call["timeout"] == 30
        assert call["verify"] is False

    def test_unknown_server_name_raises(self):
        provider, session, patcher = _provider(
            [(_path_is("/api/v2/public/servers"), SERVERS_RESPONSE)],
            server_name="Not A Server",
        )
        try:
            with pytest.raises(TracearrApiError, match="Not A Server"):
                provider.test_connection()
        finally:
            patcher.stop()

    def test_http_error_raises_without_leaking_key(self):
        provider, session, patcher = _provider(
            [(_path_is("/api/v2/public/servers"), FakeResponse(None, status_code=401))]
        )
        try:
            with pytest.raises(TracearrApiError, match="401") as raised:
                provider.test_connection()
        finally:
            patcher.stop()
        assert "trr_pub_test" not in str(raised.value)

    def test_v1_only_instance_404s_as_error(self):
        provider, _, patcher = _provider(
            [(_path_is("/api/v2/public/servers"), FakeResponse(None, status_code=404))]
        )
        try:
            with pytest.raises(TracearrApiError, match="404"):
                provider.test_connection()
        finally:
            patcher.stop()


class TestGetActivity:
    def test_movies_keyed_by_rating_key_and_provider_ref(self):
        provider, session, patcher = _provider(
            _with_managed_server(
                [
                    (
                        _path_is("/api/v2/public/history"),
                        history_response([MOVIE_HISTORY]),
                    )
                ]
            ),
            server_name="Attic",
        )
        try:
            result = provider.get_activity("1")
        finally:
            patcher.stop()

        expected_watched = _iso_to_local(MOVIE_HISTORY["stopped_at"])
        assert result["12345"]["title"] == "Inception"
        assert result["12345"]["year"] == 2010
        assert result["12345"]["last_watched"] == expected_watched
        assert result["movie:tmdb:27205"]["title"] == "Inception"
        assert result["movie:imdb:tt1375666"]["title"] == "Inception"
        assert result[MOVIE_MEDIA_ID]["title"] == "Inception"
        history_calls = [c for c in session.calls if c["url"].endswith("/history")]
        assert history_calls[0]["url"] == "http://tracearr.example.com/api/v2/public/history"
        assert history_calls[0]["params"]["pageSize"] == 100

    def test_tv_episodes_roll_up_to_show_rating_key(self):
        provider, _, patcher = _provider(
            _with_managed_server(
                [
                    (
                        _path_is("/api/v2/public/history"),
                        history_response([EPISODE_HISTORY]),
                    ),
                    (_is_show_media, SHOW_MEDIA),
                ]
            ),
            server_name="Attic",
        )
        try:
            result = provider.get_activity("2")
        finally:
            patcher.stop()

        assert result["456"]["title"] == "Breaking Bad"
        assert result["456"]["year"] == 2008
        assert result[SHOW_MEDIA_ID]["title"] == "Breaking Bad"
        assert result["9001"]["title"] == "Breaking Bad"
        assert result["show:tvdb:81189"]["title"] == "Breaking Bad"
        assert result["show:tmdb:1396"]["title"] == "Breaking Bad"

    def test_filters_to_library_section(self):
        other_library = history_record(
            rating_key="999",
            library_id="2",
            media_title="Other Movie",
            tmdb_id=1,
            imdb_id="tt0000001",
            media_id="00000000-0000-4000-8000-000000000001",
        )
        provider, _, patcher = _provider(
            _with_managed_server(
                [
                    (
                        _path_is("/api/v2/public/history"),
                        history_response([MOVIE_HISTORY, other_library]),
                    )
                ]
            ),
            server_name="Attic",
        )
        try:
            result = provider.get_activity("1")
        finally:
            patcher.stop()

        assert "12345" in result
        assert "999" not in result

    def test_keeps_most_recent_play(self):
        older = history_record(
            stopped_at="2026-01-01T12:00:00.000Z",
            started_at="2026-01-01T10:00:00.000Z",
        )
        newer = history_record(
            id="dddddddd-eeee-4fff-8000-111111111111",
            reference_id="dddddddd-eeee-4fff-8000-111111111111",
            stopped_at="2026-09-15T12:00:00.000Z",
            started_at="2026-09-15T10:00:00.000Z",
        )
        provider, _, patcher = _provider(
            _with_managed_server(
                [(_path_is("/api/v2/public/history"), history_response([newer, older]))]
            ),
            server_name="Attic",
        )
        try:
            result = provider.get_activity("1")
        finally:
            patcher.stop()

        assert result["12345"]["last_watched"] == _iso_to_local(newer["stopped_at"])

    def test_paginates_with_next_cursor(self):
        first = history_record()
        second = history_record(
            id="eeeeeeee-ffff-4000-8000-222222222222",
            reference_id="eeeeeeee-ffff-4000-8000-222222222222",
            rating_key="67890",
            media_title="Heat",
            tmdb_id=949,
            imdb_id="tt0113270",
            media_id="00000000-0000-4000-8000-000000000002",
            stopped_at="2026-05-01T20:00:00.000Z",
            started_at="2026-05-01T18:00:00.000Z",
        )

        def respond(path, params):
            if params.get("cursor") == "page-2":
                return history_response([second])
            return history_response([first], next_cursor="page-2")

        provider, session, patcher = _provider(
            _with_managed_server(
                [(_path_is("/api/v2/public/history"), respond)]
            ),
            server_name="Attic",
        )
        try:
            result = provider.get_activity("1")
        finally:
            patcher.stop()

        assert "12345" in result
        assert "67890" in result
        assert result["67890"]["title"] == "Heat"
        history_calls = [c for c in session.calls if c["url"].endswith("/history")]
        assert history_calls[0]["params"].get("cursor") is None
        assert history_calls[1]["params"]["cursor"] == "page-2"

    def test_filters_by_server_name(self):
        def respond(path, params):
            if path.endswith("/servers"):
                return SERVERS_RESPONSE
            assert params.get("server_id") == SERVER_ID
            return history_response([MOVIE_HISTORY])

        provider, session, patcher = _provider(
            [
                (_path_is("/api/v2/public/servers"), respond),
                (_path_is("/api/v2/public/history"), respond),
            ],
            server_name="Attic",
        )
        try:
            result = provider.get_activity("1")
        finally:
            patcher.stop()

        assert "12345" in result
        history_calls = [c for c in session.calls if c["url"].endswith("/history")]
        assert history_calls[0]["params"]["server_id"] == SERVER_ID

    def test_empty_history_returns_empty_dict(self):
        provider, _, patcher = _provider(
            [(_path_is("/api/v2/public/history"), history_response([]))]
        )
        try:
            assert provider.get_activity("1") == {}
        finally:
            patcher.stop()

    def test_invalid_history_response_raises(self):
        provider, _, patcher = _provider(
            [(_path_is("/api/v2/public/history"), {"error": "boom"})]
        )
        try:
            with pytest.raises(TracearrApiError, match="data"):
                provider.get_activity("1")
        finally:
            patcher.stop()

    def test_failure_mid_pagination_raises_instead_of_returning_partial(self):
        def respond(path, params):
            if params.get("cursor") == "page-2":
                return FakeResponse(None, status_code=500)
            return history_response([MOVIE_HISTORY], next_cursor="page-2")

        provider, _, patcher = _provider(
            [(_path_is("/api/v2/public/history"), respond)]
        )
        try:
            with pytest.raises(TracearrApiError, match="incomplete history"):
                provider.get_activity("1")
        finally:
            patcher.stop()

    def test_refresh_library_is_a_noop(self):
        provider, session, patcher = _provider([])
        try:
            provider.refresh_library("1")
        finally:
            patcher.stop()
        assert session.calls == []


class TestHasUserWatched:
    def test_uses_media_scoped_watchers_endpoint(self):
        def respond(path, params):
            if path.endswith("/history"):
                return history_response([MOVIE_HISTORY])
            if "/media/" in path and path.endswith("/watchers"):
                assert "movie:tmdb:27205" in path or MOVIE_MEDIA_ID in path
                assert params.get("window") == "all_time"
                return watchers_response(["john_doe"])
            raise AssertionError(path)

        provider, session, patcher = _provider(
            _with_managed_server(
                [
                    (_path_is("/api/v2/public/history"), respond),
                    (lambda path, params: "/media/" in path and path.endswith("/watchers"), respond),
                ]
            ),
            server_name="Attic",
        )
        try:
            provider.get_activity("1")
            assert provider.has_user_watched("1", "12345", None, "john_doe") is True
            assert provider.has_user_watched("1", "12345", None, "someone_else") is False
        finally:
            patcher.stop()

        watcher_calls = [c for c in session.calls if c["url"].rstrip("/").endswith("/watchers")]
        assert watcher_calls
        assert watcher_calls[0]["params"]["window"] == "all_time"

    def test_show_uses_show_media_ref(self):
        def respond(path, params):
            if path.endswith("/history"):
                return history_response([EPISODE_HISTORY])
            if path.endswith(f"/media/{SHOW_MEDIA_ID}") and not path.endswith("/watchers"):
                return SHOW_MEDIA
            if "/media/" in path and path.endswith("/watchers"):
                assert SHOW_MEDIA_ID in path
                return watchers_response(["john_doe"], media_id=SHOW_MEDIA_ID, media_type="show")
            raise AssertionError(path)

        provider, _, patcher = _provider(
            _with_managed_server(
                [
                    (_path_is("/api/v2/public/history"), respond),
                    (_is_show_media, respond),
                    (lambda path, params: "/media/" in path and path.endswith("/watchers"), respond),
                ]
            ),
            server_name="Attic",
        )
        try:
            provider.get_activity("2")
            assert (
                provider.has_user_watched("2", None, "456", "john_doe") is True
            )
        finally:
            patcher.stop()

    def test_resolves_ref_from_history_when_activity_was_not_fetched(self):
        def respond(path, params):
            if path.endswith("/history"):
                assert params.get("rating_key") == "12345"
                return history_response([MOVIE_HISTORY])
            if "/media/" in path and path.endswith("/watchers"):
                return watchers_response(["john_doe"])
            raise AssertionError(path)

        provider, session, patcher = _provider(
            _with_managed_server(
                [
                    (_path_is("/api/v2/public/history"), respond),
                    (lambda path, params: "/media/" in path and path.endswith("/watchers"), respond),
                ]
            ),
            server_name="Attic",
        )
        try:
            assert provider.has_user_watched("1", "12345", None, "john_doe") is True
        finally:
            patcher.stop()

    def test_unknown_media_returns_false(self):
        def respond(path, params):
            if path.endswith("/history"):
                return history_response([])
            return FakeResponse(None, status_code=404)

        provider, _, patcher = _provider(
            [
                (_path_is("/api/v2/public/history"), respond),
                (lambda path, params: "/media/" in path, respond),
            ]
        )
        try:
            assert provider.has_user_watched("1", "12345", None, "john_doe") is False
        finally:
            patcher.stop()

    def test_empty_user_returns_false_without_request(self):
        provider, session, patcher = _provider([])
        try:
            assert provider.has_user_watched("1", "12345", None, "") is False
            assert provider.has_user_watched("1", "12345", None, None) is False
        finally:
            patcher.stop()
        assert session.calls == []


class TestFindWatchedDataProviderRefs:
    def test_matches_plex_item_by_tmdb_guid_when_rating_key_is_absent(self):
        from app.media_cleaner import find_watched_data

        provider, _, patcher = _provider(
            _with_managed_server(
                [(_path_is("/api/v2/public/history"), history_response([MOVIE_HISTORY]))]
            ),
            server_name="Attic",
        )
        try:
            activity = provider.get_activity("1")
        finally:
            patcher.stop()

        # Drop rating-key entries so the new provider-ref lookup is what matches.
        activity_without_keys = {
            key: value
            for key, value in activity.items()
            if not str(key).isdigit()
        }
        plex_item = MagicMock()
        plex_item.guid = "plex://movie/5d77682a594b2b001c64d4e8"
        plex_item.ratingKey = 99999
        plex_item.title = "Some Other Title"
        plex_item.year = 1999
        plex_item.type = "movie"
        plex_item.guids = [MagicMock(id="tmdb://27205"), MagicMock(id="imdb://tt1375666")]

        watched = find_watched_data(plex_item, activity_without_keys)
        assert watched is not None
        assert watched["title"] == "Inception"


    def test_foreign_server_play_is_kept_by_provider_ref_only(self):
        """Jellyfin plays of the same title count, but their rating keys do not."""
        jellyfin_play = history_record(
            server_id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
            server_name="Jellyfin",
            server_type="jellyfin",
            rating_key="jf-99",
            library_id="not-a-plex-section",
            media_title="Inception",
            tmdb_id=27205,
            imdb_id="tt1375666",
            media_id="00000000-0000-4000-8000-000000000099",
            stopped_at="2026-10-01T12:00:00.000Z",
            started_at="2026-10-01T10:00:00.000Z",
        )
        # Older Plex play of a different title sharing no provider ids
        provider, _, patcher = _provider(
            _with_managed_server(
                [
                    (
                        _path_is("/api/v2/public/history"),
                        history_response([MOVIE_HISTORY, jellyfin_play]),
                    )
                ]
            ),
            server_name="Attic",
        )
        plex_item = MagicMock()
        plex_item.guid = "plex://movie/abc"
        plex_item.ratingKey = 12345
        plex_item.title = "Inception"
        plex_item.year = 2010
        plex_item.type = "movie"
        plex_item.guids = [MagicMock(id="tmdb://27205")]
        try:
            result = provider.get_activity("1", library_items=[plex_item])
        finally:
            patcher.stop()

        assert "12345" in result
        assert "jf-99" not in result
        assert result["movie:tmdb:27205"]["last_watched"] == _iso_to_local(
            jellyfin_play["stopped_at"]
        )

    def test_foreign_rating_key_does_not_collide_with_local_plex_key(self):
        foreign = history_record(
            server_id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
            server_name="Jellyfin",
            server_type="jellyfin",
            rating_key="12345",
            library_id="1",
            media_title="Some Other Film",
            tmdb_id=1,
            imdb_id="tt0000001",
            media_id="00000000-0000-4000-8000-000000000001",
            stopped_at="2026-10-01T12:00:00.000Z",
            started_at="2026-10-01T10:00:00.000Z",
        )
        provider, _, patcher = _provider(
            _with_managed_server(
                [
                    (
                        _path_is("/api/v2/public/history"),
                        history_response([MOVIE_HISTORY, foreign]),
                    )
                ]
            ),
            server_name="Attic",
        )
        try:
            result = provider.get_activity("1")
        finally:
            patcher.stop()

        assert result["12345"]["title"] == "Inception"
        assert "movie:tmdb:1" not in result

    def test_episode_without_plex_key_matches_show_provider_ref(self):
        episode = dict(EPISODE_HISTORY)
        episode.update(
            {
                "rating_key": None,
                "parent_rating_key": None,
                "grandparent_rating_key": None,
                "year": 2009,
                "server_type": "jellyfin",
                "server_id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
                "library_id": "other",
            }
        )
        provider, _, patcher = _provider(
            [
                (_path_is("/api/v2/public/history"), history_response([episode])),
                (_is_show_media, SHOW_MEDIA),
            ]
        )
        plex_show = MagicMock()
        plex_show.guid = "plex://show/abc"
        plex_show.ratingKey = 99999
        plex_show.title = "Breaking Bad"
        plex_show.year = 2008
        plex_show.type = "show"
        plex_show.guids = [MagicMock(id="tvdb://81189")]
        try:
            activity = provider.get_activity("2", library_items=[plex_show])
        finally:
            patcher.stop()

        from app.media_cleaner import find_watched_data

        watched = find_watched_data(plex_show, activity)
        assert watched is not None
        assert watched["title"] == "Breaking Bad"



    def test_prefers_newer_provider_ref_over_older_rating_key_or_title(self):
        """A stale rating-key or title match must not hide a newer provider-ref play."""
        from datetime import timedelta

        from app.media_cleaner import find_watched_data

        older = {
            "title": "Inception",
            "year": 2010,
            "last_watched": datetime.now() - timedelta(days=90),
        }
        newer = {
            "title": "Inception",
            "year": 2010,
            "last_watched": datetime.now() - timedelta(days=2),
        }
        activity = {
            "12345": older,
            "other-key": older,
            "movie:tmdb:27205": newer,
        }
        plex_item = MagicMock()
        plex_item.guid = "plex://movie/abc"
        plex_item.ratingKey = 12345
        plex_item.title = "Inception"
        plex_item.year = 2010
        plex_item.type = "movie"
        plex_item.guids = [MagicMock(id="tmdb://27205")]

        watched = find_watched_data(plex_item, activity)
        assert watched is newer


class TestTransientErrors:
    def test_http_503_is_transient_for_startup_retry(self):
        from app.config import is_transient_exception

        provider, _, patcher = _provider(
            [(_path_is("/api/v2/public/servers"), FakeResponse(None, status_code=503))]
        )
        try:
            with pytest.raises(TracearrApiError) as raised:
                provider.test_connection()
        finally:
            patcher.stop()
        assert is_transient_exception(raised.value) is True

    def test_http_401_is_not_transient(self):
        from app.config import is_transient_exception

        provider, _, patcher = _provider(
            [(_path_is("/api/v2/public/servers"), FakeResponse(None, status_code=401))]
        )
        try:
            with pytest.raises(TracearrApiError) as raised:
                provider.test_connection()
        finally:
            patcher.stop()
        assert is_transient_exception(raised.value) is False

class TestActivityScoping:
    def test_unrelated_foreign_play_leaves_activity_empty(self):
        """A play from another library must not populate activity for this section."""
        foreign = history_record(
            server_id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
            server_name="Jellyfin",
            server_type="jellyfin",
            rating_key="jf-99",
            library_id="other",
            media_title="Some Other Film",
            tmdb_id=1,
            imdb_id="tt0000001",
            media_id="00000000-0000-4000-8000-000000000001",
        )
        provider, _, patcher = _provider(
            [(_path_is("/api/v2/public/history"), history_response([foreign]))]
        )
        try:
            result = provider.get_activity("1")
        finally:
            patcher.stop()
        assert result == {}

    def test_foreign_play_is_kept_only_when_it_matches_a_library_item(self):
        foreign = history_record(
            server_id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
            server_name="Jellyfin",
            server_type="jellyfin",
            rating_key="jf-99",
            library_id="other",
            media_title="Inception",
            tmdb_id=27205,
            imdb_id="tt1375666",
            media_id="00000000-0000-4000-8000-000000000099",
            stopped_at="2026-10-01T12:00:00.000Z",
            started_at="2026-10-01T10:00:00.000Z",
        )
        plex_item = MagicMock()
        plex_item.guid = "plex://movie/abc"
        plex_item.ratingKey = 12345
        plex_item.title = "Inception"
        plex_item.year = 2010
        plex_item.type = "movie"
        plex_item.guids = [MagicMock(id="tmdb://27205")]

        provider, _, patcher = _provider(
            [(_path_is("/api/v2/public/history"), history_response([foreign]))]
        )
        try:
            kept = provider.get_activity("1", library_items=[plex_item])
            omitted = provider.get_activity("1")
        finally:
            patcher.stop()

        assert "jf-99" not in kept
        assert kept["movie:tmdb:27205"]["title"] == "Inception"
        assert omitted == {}


class TestResolveRefScoping:
    def test_uncached_rating_key_ignores_a_foreign_first_record(self):
        """has_user_watched must not use a non-local history hit for a Plex rating key."""
        foreign = history_record(
            server_id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
            server_name="Jellyfin",
            server_type="jellyfin",
            rating_key="12345",
            library_id="1",
            media_title="Some Other Film",
            tmdb_id=1,
            imdb_id="tt0000001",
            media_id="00000000-0000-4000-8000-000000000001",
        )

        def respond(path, params):
            if path.endswith("/history"):
                return history_response([foreign])
            if "/media/" in path and path.endswith("/watchers"):
                return watchers_response(["john_doe"], media_id=foreign["media_id"])
            raise AssertionError(path)

        provider, session, patcher = _provider(
            [
                (_path_is("/api/v2/public/history"), respond),
                (lambda path, params: "/media/" in path, respond),
            ]
        )
        try:
            watched = provider.has_user_watched("1", "12345", None, "john_doe")
        finally:
            patcher.stop()

        assert watched is False
        assert not any(c["url"].rstrip("/").endswith("/watchers") for c in session.calls)

    def test_uncached_rating_key_with_server_name_ignores_a_foreign_first_record(self):
        """With server_name set, a foreign first history hit must still be ignored."""
        foreign = history_record(
            server_id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
            server_name="Jellyfin",
            server_type="jellyfin",
            rating_key="12345",
            library_id="1",
            media_title="Some Other Film",
            tmdb_id=1,
            imdb_id="tt0000001",
            media_id="00000000-0000-4000-8000-000000000001",
        )

        def respond(path, params):
            if path.endswith("/servers"):
                return SERVERS_RESPONSE
            if path.endswith("/history"):
                return history_response([foreign, MOVIE_HISTORY])
            if "/media/" in path and path.endswith("/watchers"):
                if "000000000001" in path or "movie:tmdb:1" in path:
                    return watchers_response(
                        ["john_doe"],
                        media_id=foreign["media_id"],
                    )
                return watchers_response(["someone_else"])
            raise AssertionError(path)

        provider, session, patcher = _provider(
            [
                (_path_is("/api/v2/public/servers"), respond),
                (_path_is("/api/v2/public/history"), respond),
                (lambda path, params: "/media/" in path, respond),
            ],
            server_name="Attic",
        )
        try:
            watched = provider.has_user_watched("1", "12345", None, "john_doe")
        finally:
            patcher.stop()

        assert watched is False
        watcher_calls = [c for c in session.calls if c["url"].rstrip("/").endswith("/watchers")]
        assert watcher_calls
        assert all(
            "000000000001" not in c["url"] and "movie:tmdb:1" not in c["url"]
            for c in watcher_calls
        )


class TestUnresolvedShowIdentity:
    def test_unresolved_show_identity_raises(self):
        episode = dict(EPISODE_HISTORY)
        episode.update(
            {
                "rating_key": None,
                "parent_rating_key": None,
                "grandparent_rating_key": None,
                "year": 2009,
                "server_type": "jellyfin",
                "server_id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
                "library_id": "other",
            }
        )
        provider, _, patcher = _provider(
            [
                (_path_is("/api/v2/public/history"), history_response([episode])),
                (
                    _is_show_media,
                    FakeResponse(None, status_code=404),
                ),
            ]
        )
        try:
            with pytest.raises(TracearrApiError, match="canonical show identity"):
                provider.get_activity(
                    "2",
                    library_items=[MagicMock(
                        guid="plex://show/abc",
                        ratingKey=99999,
                        title="Breaking Bad",
                        year=2008,
                        type="show",
                        guids=[MagicMock(id="tvdb://81189")],
                    )],
                )
        finally:
            patcher.stop()


class TestUnparseableTimestamps:
    def test_unparseable_timestamp_among_valid_records_raises(self):
        """A skipped bad timestamp must not leave other titles looking unwatched."""
        broken = history_record(
            id="ffffffff-0000-4000-8000-333333333333",
            reference_id="ffffffff-0000-4000-8000-333333333333",
            rating_key="67890",
            media_title="Heat",
            tmdb_id=949,
            imdb_id="tt0113270",
            media_id="00000000-0000-4000-8000-000000000002",
            stopped_at="not-a-timestamp",
            started_at="also-not-a-timestamp",
        )
        provider, _, patcher = _provider(
            [
                (
                    _path_is("/api/v2/public/history"),
                    history_response([MOVIE_HISTORY, broken]),
                )
            ]
        )
        try:
            with pytest.raises(TracearrApiError, match="unparseable watch timestamp"):
                provider.get_activity("1")
        finally:
            patcher.stop()


class TestUnverifiedRatingKeys:
    def test_unique_library_id_without_server_name_does_not_use_rating_keys(self):
        """Library IDs and rating keys are server-local and commonly reused."""
        other_plex = history_record(
            server_id="bbbbbbbb-cccc-4ddd-8eee-ffffffffffff",
            server_name="Someone Else's Plex",
            server_type="plex",
            rating_key="12345",
            library_id="1",
            media_title="Some Other Film",
            tmdb_id=1,
            imdb_id="tt0000001",
            media_id="00000000-0000-4000-8000-000000000001",
        )
        plex_item = MagicMock()
        plex_item.guid = "plex://movie/abc"
        plex_item.ratingKey = 12345
        plex_item.title = "Inception"
        plex_item.year = 2010
        plex_item.type = "movie"
        plex_item.guids = [MagicMock(id="tmdb://27205")]

        provider, _, patcher = _provider(
            [(_path_is("/api/v2/public/history"), history_response([other_plex]))]
        )
        try:
            result = provider.get_activity("1", library_items=[plex_item])
        finally:
            patcher.stop()

        assert "12345" not in result
        assert "movie:tmdb:1" not in result

        from app.media_cleaner import find_watched_data

        assert find_watched_data(plex_item, result) is None

    def test_unverified_plex_play_matches_by_provider_ref_only(self):
        plex_item = MagicMock()
        plex_item.guid = "plex://movie/abc"
        plex_item.ratingKey = 12345
        plex_item.title = "Inception"
        plex_item.year = 2010
        plex_item.type = "movie"
        plex_item.guids = [MagicMock(id="tmdb://27205")]

        provider, _, patcher = _provider(
            [(_path_is("/api/v2/public/history"), history_response([MOVIE_HISTORY]))]
        )
        try:
            result = provider.get_activity("1", library_items=[plex_item])
        finally:
            patcher.stop()

        assert "12345" not in result
        assert result["movie:tmdb:27205"]["title"] == "Inception"

        from app.media_cleaner import find_watched_data

        assert find_watched_data(plex_item, result) is not None

    def test_uncached_rating_key_is_not_resolved_without_a_verified_server(self):
        def respond(path, params):
            if path.endswith("/history"):
                return history_response([MOVIE_HISTORY])
            if "/media/" in path and path.endswith("/watchers"):
                return watchers_response(["john_doe"])
            raise AssertionError(path)

        provider, session, patcher = _provider(
            [
                (_path_is("/api/v2/public/history"), respond),
                (lambda path, params: "/media/" in path, respond),
            ]
        )
        try:
            watched = provider.has_user_watched("1", "12345", None, "john_doe")
        finally:
            patcher.stop()

        assert watched is False
        assert not any(c["url"].rstrip("/").endswith("/watchers") for c in session.calls)


class TestWatcherUsernameOnly:
    def test_has_user_watched_ignores_identity_display_name(self):
        def respond(path, params):
            if path.endswith("/servers"):
                return SERVERS_RESPONSE
            if path.endswith("/history"):
                return history_response([MOVIE_HISTORY])
            if "/media/" in path and path.endswith("/watchers"):
                return watchers_response(
                    [{"username": "alice", "identity_name": "john_doe"}]
                )
            raise AssertionError(path)

        provider, _, patcher = _provider(
            [
                (_path_is("/api/v2/public/servers"), respond),
                (_path_is("/api/v2/public/history"), respond),
                (lambda path, params: "/media/" in path, respond),
            ],
            server_name="Attic",
        )
        try:
            assert provider.has_user_watched("1", "12345", None, "john_doe") is False
            assert provider.has_user_watched("1", "12345", None, "alice") is True
        finally:
            patcher.stop()


HEAT_MEDIA_ID = "22222222-3333-4444-8555-666666666666"


class TestMovieIdentityWithoutProviderIds:
    def _heat_item(self):
        plex_item = MagicMock()
        plex_item.guid = "plex://movie/heat"
        plex_item.ratingKey = 67890
        plex_item.title = "Heat"
        plex_item.year = 1995
        plex_item.type = "movie"
        plex_item.guids = [MagicMock(id="tmdb://949")]
        return plex_item

    def _inception_item(self):
        plex_item = MagicMock()
        plex_item.guid = "plex://movie/abc"
        plex_item.ratingKey = 12345
        plex_item.title = "Inception"
        plex_item.year = 2010
        plex_item.type = "movie"
        plex_item.guids = [MagicMock(id="tmdb://27205")]
        return plex_item

    def _heat_history(self):
        return history_record(
            id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeee0001",
            reference_id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeee0001",
            rating_key="heat-99",
            library_id="other",
            server_type="jellyfin",
            server_id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
            server_name="Jellyfin",
            media_title="Heat",
            year=1995,
            tmdb_id=None,
            imdb_id=None,
            tvdb_id=None,
            media_id=HEAT_MEDIA_ID,
        )

    def test_resolves_missing_movie_provider_ids_via_media_id(self):
        heat = self._heat_history()
        movie_resource = media_resource(
            id=HEAT_MEDIA_ID,
            media_type="movie",
            title="Heat",
            year=1995,
            imdb_id="tt0113270",
            tmdb_id=949,
            tvdb_id=None,
            show_media_id=None,
            season_count=None,
            episode_count=None,
        )
        provider, _, patcher = _provider(
            [
                (
                    _path_is("/api/v2/public/history"),
                    history_response([MOVIE_HISTORY, heat]),
                ),
                (
                    lambda path, params: path.endswith(f"/media/{HEAT_MEDIA_ID}"),
                    movie_resource,
                ),
            ]
        )
        try:
            result = provider.get_activity(
                "1",
                library_items=[self._inception_item(), self._heat_item()],
            )
        finally:
            patcher.stop()

        assert "movie:tmdb:949" in result
        from app.media_cleaner import find_watched_data

        assert find_watched_data(self._heat_item(), result) is not None

    def test_unresolved_movie_identity_raises(self):
        heat = self._heat_history()
        provider, _, patcher = _provider(
            [
                (
                    _path_is("/api/v2/public/history"),
                    history_response([MOVIE_HISTORY, heat]),
                ),
                (
                    lambda path, params: path.endswith(f"/media/{HEAT_MEDIA_ID}"),
                    FakeResponse(None, status_code=404),
                ),
            ]
        )
        try:
            with pytest.raises(TracearrApiError, match="canonical movie identity"):
                provider.get_activity(
                    "1",
                    library_items=[self._inception_item(), self._heat_item()],
                )
        finally:
            patcher.stop()


class TestIncompatibleHistoryDoesNotAbortLibrary:
    def test_unresolved_episode_does_not_abort_a_movie_library(self):
        episode = dict(EPISODE_HISTORY)
        episode.update(
            {
                "rating_key": None,
                "parent_rating_key": None,
                "grandparent_rating_key": None,
                "library_id": "2",
                "server_type": "jellyfin",
                "server_id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
            }
        )
        plex_item = MagicMock()
        plex_item.guid = "plex://movie/abc"
        plex_item.ratingKey = 12345
        plex_item.title = "Inception"
        plex_item.year = 2010
        plex_item.type = "movie"
        plex_item.guids = [MagicMock(id="tmdb://27205")]

        provider, _, patcher = _provider(
            [
                (
                    _path_is("/api/v2/public/history"),
                    history_response([MOVIE_HISTORY, episode]),
                ),
                (
                    _is_show_media,
                    FakeResponse(None, status_code=404),
                ),
            ]
        )
        try:
            result = provider.get_activity("1", library_items=[plex_item])
        finally:
            patcher.stop()

        assert result["movie:tmdb:27205"]["title"] == "Inception"
