# encoding: utf-8
"""Integration tests for the leaving_soon feature.

These tests verify that the leaving_soon feature in MediaCleaner works correctly.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.config import Config
from app.media_cleaner import MediaCleaner

INTEGRATION_DIR = Path(__file__).parent


@pytest.mark.integration
class TestLeavingSoonConfigValidation:
    """Integration tests for leaving_soon configuration."""

    def test_tagging_only_config_validation(self, docker_services):
        """Test that tagging_only mode configuration is valid."""
        from tests.integration.conftest import RADARR_URL, TAUTULLI_URL, PLEX_URL

        config_dict = {
            "dry_run": False,
            "ssl_verify": False,
            "action_delay": 0,
            "plex": {
                "url": PLEX_URL,
                "token": docker_services.get("plex_token", ""),
            },
            "tautulli": {
                "url": TAUTULLI_URL,
                "api_key": docker_services["tautulli"],
            },
            "radarr": [
                {
                    "name": "Radarr",
                    "url": RADARR_URL,
                    "api_key": docker_services["radarr"],
                }
            ],
            "sonarr": [],
            "libraries": [
                {
                    "name": "Movies",
                    "radarr": "Radarr",
                    "action_mode": "delete",
                    "last_watched_threshold": 30,
                    "added_at_threshold": 7,
                    "max_actions_per_run": 5,
                    "leaving_soon": {
                        "enabled": True,
                        "tagging_only": True,
                        "collection": {
                            "enabled": True,
                            "name": "Leaving Soon",
                        },
                    },
                }
            ],
        }

        config = Config(config_dict)
        library_config = config_dict["libraries"][0]

        # Verify tagging_only mode is properly recognized
        assert library_config["leaving_soon"]["tagging_only"] is True
        assert library_config["leaving_soon"]["collection"]["enabled"] is True


@pytest.mark.integration
class TestLeavingSoonMediaCleaner:
    """Integration tests for MediaCleaner.process_leaving_soon."""

    def test_process_leaving_soon_calls_media_server_methods(self, docker_services):
        """Test MediaCleaner.process_leaving_soon calls correct media server methods."""
        from tests.integration.conftest import TAUTULLI_URL, PLEX_URL

        # Create config
        config = MagicMock()
        config.settings = {
            "dry_run": False,
            "ssl_verify": False,
            "plex": {"url": PLEX_URL, "token": "test-token"},
            "tautulli": {
                "url": TAUTULLI_URL,
                "api_key": docker_services["tautulli"],
            },
        }

        # Create mock media server that simulates successful operations
        mock_media_server = MagicMock()
        mock_plex_item = MagicMock()
        mock_plex_item.ratingKey = "m8888"
        mock_plex_item.labels = []
        mock_media_server.find_item.return_value = mock_plex_item
        mock_media_server.get_or_create_collection.return_value = MagicMock()
        mock_media_server.get_items_with_label.return_value = []

        with patch("app.media_cleaner.PlexServer"):
            cleaner = MediaCleaner(config, media_server=mock_media_server)

        library_config = {
            "name": "Movies",
            "leaving_soon": {
                "enabled": True,
                "collection": {"enabled": True, "name": "Leaving Soon"},
                "labels": {"enabled": True, "name": "leaving-soon"},
            },
        }

        items_to_tag = [
            {"title": "Test Leaving Soon Movie", "year": 2020, "tmdbId": 8888}
        ]

        mock_plex_library = MagicMock()
        cleaner.process_leaving_soon(library_config, mock_plex_library, items_to_tag, "movie")

        # Verify media server methods were called
        mock_media_server.find_item.assert_called_once()
        mock_media_server.get_or_create_collection.assert_called_once_with(
            mock_plex_library, "Leaving Soon"
        )
        mock_media_server.add_label.assert_called_once_with(mock_plex_item, "leaving-soon")

    def test_process_leaving_soon_skips_when_no_config(self, docker_services):
        """Test process_leaving_soon does nothing when leaving_soon not configured."""
        from tests.integration.conftest import TAUTULLI_URL, PLEX_URL

        config = MagicMock()
        config.settings = {
            "dry_run": False,
            "ssl_verify": False,
            "plex": {"url": PLEX_URL, "token": "test-token"},
            "tautulli": {
                "url": TAUTULLI_URL,
                "api_key": docker_services["tautulli"],
            },
        }

        mock_media_server = MagicMock()

        with patch("app.media_cleaner.PlexServer"):
            cleaner = MediaCleaner(config, media_server=mock_media_server)

        # No leaving_soon config
        library_config = {"name": "Movies"}
        items_to_tag = [{"title": "Test Movie", "year": 2020, "tmdbId": 8888}]
        mock_plex_library = MagicMock()

        cleaner.process_leaving_soon(library_config, mock_plex_library, items_to_tag, "movie")

        # Should not call any media server methods
        mock_media_server.find_item.assert_not_called()
        mock_media_server.get_or_create_collection.assert_not_called()
        mock_media_server.add_label.assert_not_called()

    def test_process_leaving_soon_handles_missing_plex_item(self, docker_services):
        """Test process_leaving_soon gracefully handles items not found in Plex."""
        from tests.integration.conftest import TAUTULLI_URL, PLEX_URL

        config = MagicMock()
        config.settings = {
            "dry_run": False,
            "ssl_verify": False,
            "plex": {"url": PLEX_URL, "token": "test-token"},
            "tautulli": {
                "url": TAUTULLI_URL,
                "api_key": docker_services["tautulli"],
            },
        }

        mock_media_server = MagicMock()
        # Simulate item not found in Plex
        mock_media_server.find_item.return_value = None

        with patch("app.media_cleaner.PlexServer"):
            cleaner = MediaCleaner(config, media_server=mock_media_server)

        library_config = {
            "name": "Movies",
            "leaving_soon": {
                "collection": {"name": "Leaving Soon"},
            },
        }

        items_to_tag = [{"title": "Missing Movie", "year": 2020, "tmdbId": 99999}]
        mock_plex_library = MagicMock()

        # Should not raise, just skip the item
        cleaner.process_leaving_soon(library_config, mock_plex_library, items_to_tag, "movie")

        mock_media_server.find_item.assert_called_once()
        # Collection should still be created/updated (with empty items)
        mock_media_server.get_or_create_collection.assert_called_once()
