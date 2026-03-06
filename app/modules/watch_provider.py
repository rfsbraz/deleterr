# encoding: utf-8

from typing import Dict, Protocol, runtime_checkable

from app import logger
from app.modules.tautulli import Tautulli


@runtime_checkable
class WatchDataProvider(Protocol):
    """Protocol for watch data providers (Tautulli, Plex, etc.)."""

    def get_activity(self, section: str) -> Dict[str, Dict]:
        """Get watch activity for a library section."""
        ...

    def test_connection(self) -> None:
        """Test the connection to the watch data provider."""
        ...

    def refresh_library(self, section_id: str) -> None:
        """Refresh library metadata."""
        ...


def create_watch_provider(config, ssl_verify=False) -> WatchDataProvider:
    """Create a watch data provider from config.

    Currently supports Tautulli only. Future providers (Plex, Jellyfin)
    will be added here.

    Args:
        config: Application config object with settings dict
        ssl_verify: Whether to verify SSL certificates

    Returns:
        A WatchDataProvider instance

    Raises:
        KeyError: If no watch provider is configured
    """
    tautulli_config = config.settings.get("tautulli")
    if tautulli_config:
        logger.debug("Using Tautulli as watch data provider")
        return Tautulli(
            tautulli_config["url"],
            tautulli_config["api_key"],
            ssl_verify=ssl_verify,
        )

    raise KeyError(
        "No watch data provider configured. "
        "Add 'tautulli' section with 'url' and 'api_key' to your config."
    )
