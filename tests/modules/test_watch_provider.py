import logging
from pathlib import Path

import pytest
from unittest.mock import MagicMock, patch

from app.modules.tautulli import Tautulli
from app.modules.watch_provider import WatchDataProvider, create_watch_provider


class TestWatchDataProviderProtocol:
    def test_tautulli_satisfies_protocol(self):
        """Tautulli class structurally conforms to WatchDataProvider protocol."""
        assert issubclass(Tautulli, WatchDataProvider)

    def test_tautulli_instance_satisfies_protocol(self):
        """A Tautulli instance is recognized as a WatchDataProvider."""
        mock_api = MagicMock()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("app.modules.tautulli.RawAPI", lambda *a, **kw: mock_api)
            instance = Tautulli("http://localhost:8181", "test_key")
        assert isinstance(instance, WatchDataProvider)


class TestCreateWatchProvider:
    def test_create_with_tautulli_config(self):
        """Factory returns a Tautulli instance when tautulli is configured."""
        config = MagicMock(
            settings={
                "tautulli": {
                    "url": "http://localhost:8181",
                    "api_key": "test_key",
                },
            }
        )
        with pytest.MonkeyPatch.context() as mp:
            mock_api = MagicMock()
            mp.setattr("app.modules.tautulli.RawAPI", lambda *a, **kw: mock_api)
            provider = create_watch_provider(config)
        assert isinstance(provider, Tautulli)
        assert isinstance(provider, WatchDataProvider)

    def test_create_with_plex_config(self):
        """Factory returns a PlexWatchProvider when tautulli is not configured."""
        config = MagicMock(
            settings={
                "plex": {
                    "url": "http://localhost:32400",
                    "token": "test_token",
                },
            }
        )
        with patch("app.modules.plex_watch_provider.PlexServer"):
            from app.modules.plex_watch_provider import PlexWatchProvider

            provider = create_watch_provider(config)
        assert isinstance(provider, PlexWatchProvider)
        assert isinstance(provider, WatchDataProvider)

    def test_tautulli_takes_priority_over_plex(self):
        """Factory returns Tautulli when both tautulli and plex are configured."""
        config = MagicMock(
            settings={
                "plex": {
                    "url": "http://localhost:32400",
                    "token": "test_token",
                },
                "tautulli": {
                    "url": "http://localhost:8181",
                    "api_key": "test_key",
                },
            }
        )
        with pytest.MonkeyPatch.context() as mp:
            mock_api = MagicMock()
            mp.setattr("app.modules.tautulli.RawAPI", lambda *a, **kw: mock_api)
            provider = create_watch_provider(config)
        assert isinstance(provider, Tautulli)

    def test_create_no_config_raises(self):
        """Factory raises KeyError when no provider is configured."""
        config = MagicMock(settings={})
        with pytest.raises(KeyError, match="No watch data provider configured"):
            create_watch_provider(config)


    def test_create_with_tracearr_config(self):
        """Factory returns a Tracearr instance when tracearr is configured and tautulli is not."""
        from app.modules.tracearr import Tracearr

        config = MagicMock(
            settings={
                "plex": {
                    "url": "http://localhost:32400",
                    "token": "test_token",
                },
                "tracearr": {
                    "url": "http://localhost:3000",
                    "api_key": "trr_pub_test",
                    "server_name": "Attic",
                },
            }
        )
        provider = create_watch_provider(config)
        assert isinstance(provider, Tracearr)
        assert isinstance(provider, WatchDataProvider)
        assert provider.server_name == "Attic"

    def test_tautulli_takes_priority_over_tracearr(self):
        """Factory still returns Tautulli when both tautulli and tracearr are configured."""
        config = MagicMock(
            settings={
                "tautulli": {
                    "url": "http://localhost:8181",
                    "api_key": "test_key",
                },
                "tracearr": {
                    "url": "http://localhost:3000",
                    "api_key": "trr_pub_test",
                },
            }
        )
        with pytest.MonkeyPatch.context() as mp:
            mock_api = MagicMock()
            mp.setattr("app.modules.tautulli.RawAPI", lambda *a, **kw: mock_api)
            provider = create_watch_provider(config)
        assert isinstance(provider, Tautulli)

    def test_tracearr_takes_priority_over_plex(self):
        """Factory prefers Tracearr over the Plex fallback when tautulli is absent."""
        from app.modules.tracearr import Tracearr

        config = MagicMock(
            settings={
                "plex": {
                    "url": "http://localhost:32400",
                    "token": "test_token",
                },
                "tracearr": {
                    "url": "http://localhost:3000",
                    "api_key": "trr_pub_test",
                },
            }
        )
        provider = create_watch_provider(config)
        assert isinstance(provider, Tracearr)


class TestTracearrServerNameWarning:
    WARNING = (
        "Tracearr is configured for Plex without server_name. The "
        "requester-watched exclusion will never apply, and items with no "
        "tmdb, tvdb, or imdb GUIDs cannot be matched to Tracearr plays, so "
        "they look unwatched. Set tracearr.server_name to the managed Plex "
        "server."
    )

    def test_warns_when_tracearr_is_used_for_plex_without_server_name(self, caplog):
        from app.modules.tracearr import Tracearr

        config = MagicMock(
            settings={
                "plex": {
                    "url": "http://localhost:32400",
                    "token": "test_token",
                },
                "tracearr": {
                    "url": "http://localhost:3000",
                    "api_key": "trr_pub_test",
                },
            }
        )
        with caplog.at_level(logging.WARNING, logger="deleterr"):
            provider = create_watch_provider(config)
        assert isinstance(provider, Tracearr)
        assert self.WARNING in [r.getMessage() for r in caplog.records]

    def test_does_not_warn_when_server_name_is_set(self, caplog):
        config = MagicMock(
            settings={
                "plex": {
                    "url": "http://localhost:32400",
                    "token": "test_token",
                },
                "tracearr": {
                    "url": "http://localhost:3000",
                    "api_key": "trr_pub_test",
                    "server_name": "Attic",
                },
            }
        )
        with caplog.at_level(logging.WARNING, logger="deleterr"):
            create_watch_provider(config)
        assert self.WARNING not in [r.getMessage() for r in caplog.records]

    def test_does_not_warn_when_tautulli_takes_priority(self, caplog):
        config = MagicMock(
            settings={
                "plex": {
                    "url": "http://localhost:32400",
                    "token": "test_token",
                },
                "tautulli": {
                    "url": "http://localhost:8181",
                    "api_key": "test_key",
                },
                "tracearr": {
                    "url": "http://localhost:3000",
                    "api_key": "trr_pub_test",
                },
            }
        )
        with pytest.MonkeyPatch.context() as mp, caplog.at_level(
            logging.WARNING, logger="app"
        ):
            mp.setattr("app.modules.tautulli.RawAPI", lambda *a, **kw: MagicMock())
            create_watch_provider(config)
        assert self.WARNING not in [r.getMessage() for r in caplog.records]


class TestTracearrIntegrationDocs:
    def test_documents_plex_limits_without_server_name(self):
        text = Path("docs/integrations/tracearr.md").read_text()
        assert (
            "Deleterr still manages Plex libraries through Radarr and Sonarr. "
            "Tracearr history is matched to those Plex items by rating key "
            "first, then by provider ids"
        ) not in text
        assert "When `server_name` is set, Tracearr history is matched" in text
        assert "requester-watched exclusion never applies" in text
        assert (
            "no tmdb, tvdb, or imdb GUIDs cannot be matched to Tracearr plays, "
            "so they look unwatched"
        ) in text
        assert "Set `server_name`" in text or "set `server_name`" in text
