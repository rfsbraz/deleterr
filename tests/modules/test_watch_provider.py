import pytest
from unittest.mock import MagicMock

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

    def test_create_no_config_raises(self):
        """Factory raises KeyError when no provider is configured."""
        config = MagicMock(settings={})
        with pytest.raises(KeyError, match="No watch data provider configured"):
            create_watch_provider(config)
