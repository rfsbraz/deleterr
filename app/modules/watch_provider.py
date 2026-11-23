# encoding: utf-8

from typing import Dict, Optional, Protocol, runtime_checkable

from app import logger
from app.modules.tautulli import Tautulli


@runtime_checkable
class WatchDataProvider(Protocol):
    """Protocol for watch data providers (Tautulli, Tracearr, Plex, etc.)."""

    def get_activity(self, section: str) -> Dict[str, Dict]:
        """Get watch activity for a library section."""
        ...

    def test_connection(self) -> None:
        """Test the connection to the watch data provider."""
        ...

    def refresh_library(self, section_id: str) -> None:
        """Refresh library metadata."""
        ...

    def has_user_watched(
        self,
        section: str,
        rating_key: Optional[str],
        grandparent_rating_key: Optional[str],
        user: str,
    ) -> bool:
        """Check if a specific user has watched a media item."""
        ...


def create_watch_provider(config, ssl_verify=False) -> WatchDataProvider:
    """Create a watch data provider from config.

    If 'tautulli' is configured, uses Tautulli. Else if 'tracearr' is
    configured, uses Tracearr. Otherwise falls back to Plex's built-in
    watch history API.

    Args:
        config: Application config object with settings dict
        ssl_verify: Whether to verify SSL certificates

    Returns:
        A WatchDataProvider instance

    Raises:
        KeyError: If neither tautulli, tracearr, nor plex is configured
    """
    tautulli_config = config.settings.get("tautulli")
    if tautulli_config:
        if config.settings.get("tracearr"):
            logger.info(
                "Both Tautulli and Tracearr are configured; using Tautulli "
                "for watch history and ignoring Tracearr."
            )
        logger.debug("Using Tautulli as watch data provider")
        return Tautulli(
            tautulli_config["url"],
            tautulli_config["api_key"],
            ssl_verify=ssl_verify,
        )

    tracearr_config = config.settings.get("tracearr")
    if tracearr_config:
        from app.modules.tracearr import Tracearr

        logger.debug("Using Tracearr as watch data provider")
        return Tracearr(
            tracearr_config["url"],
            tracearr_config["api_key"],
            ssl_verify=ssl_verify,
            server_name=tracearr_config.get("server_name"),
        )

    plex_config = config.settings.get("plex")
    if plex_config:
        from app.modules.plex_watch_provider import PlexWatchProvider

        logger.debug("Using Plex as watch data provider (no Tautulli or Tracearr configured)")
        return PlexWatchProvider(
            plex_config["url"],
            plex_config["token"],
            ssl_verify=ssl_verify,
        )

    raise KeyError(
        "No watch data provider configured. "
        "Add a 'tautulli' section with 'url' and 'api_key', a 'tracearr' "
        "section with 'url' and 'api_key', or configure 'plex' with 'url' "
        "and 'token' to use Plex directly."
    )
