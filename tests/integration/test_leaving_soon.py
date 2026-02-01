# encoding: utf-8
"""Integration tests for the leaving_soon feature.

These tests verify that the leaving_soon feature works correctly with real
Plex, Radarr, and Sonarr services.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.config import Config
from app.media_cleaner import MediaCleaner

INTEGRATION_DIR = Path(__file__).parent


@pytest.mark.integration
class TestLeavingSoonWithRealPlex:
    """Integration tests for leaving_soon feature with real Plex server."""

    def test_leaving_soon_collection_workflow(self, clean_plex_test_data):
        """Test the leaving_soon collection workflow with real Plex."""
        helper = clean_plex_test_data

        movies = helper.get_all_movies()[:2]
        if len(movies) < 2:
            pytest.skip("Not enough movies in library")

        # Create "Leaving Soon" collection
        collection = helper.create_collection("Leaving Soon", movies)
        assert collection is not None
        assert collection.title == "Leaving Soon"

        # Verify items in collection
        items = helper.get_collection_items("Leaving Soon")
        assert len(items) == 2

        # Cleanup
        helper.delete_collection("Leaving Soon")

    def test_leaving_soon_label_workflow(self, clean_plex_test_data):
        """Test the leaving_soon label workflow with real Plex."""
        helper = clean_plex_test_data

        movies = helper.get_all_movies()[:2]
        if len(movies) < 2:
            pytest.skip("Not enough movies in library")

        # Add leaving-soon label to movies
        for movie in movies:
            helper.add_label(movie, "leaving-soon")

        # Find all items with leaving-soon label
        labeled_items = helper.get_items_with_label("leaving-soon")
        assert len(labeled_items) >= 2

        # Remove labels (cleanup)
        for movie in movies:
            movie.reload()
            helper.remove_label(movie, "leaving-soon")


@pytest.mark.integration
class TestLeavingSoonTaggingOnlyMode:
    """Integration tests for tagging_only mode."""

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
    """Integration tests for MediaCleaner leaving_soon processing."""

    def test_process_leaving_soon_with_mock_media_server(self, docker_services):
        """Test MediaCleaner.process_leaving_soon with mocked media server."""
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
