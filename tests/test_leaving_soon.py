# encoding: utf-8
"""Unit tests for leaving_soon feature in MediaCleaner."""

import pytest
from unittest.mock import MagicMock, patch, call

from app.media_cleaner import MediaCleaner


@pytest.fixture
def standard_config():
    """Create a standard test configuration."""
    return MagicMock(
        settings={
            "dry_run": False,
            "sonarr": {"api_key": "test_api_key", "url": "http://localhost:8989"},
            "plex": {"url": "http://localhost:32400", "token": "test_token"},
            "tautulli": {"url": "http://localhost:8181", "api_key": "test_api_key"},
        }
    )


@pytest.fixture
def mock_media_server():
    """Create a mock media server."""
    return MagicMock()


@pytest.fixture(autouse=True)
def mock_plex_server():
    """Mock PlexServer to avoid real connections."""
    with patch("app.media_cleaner.PlexServer", return_value=MagicMock()):
        yield


@pytest.fixture
def media_cleaner(standard_config, mock_media_server):
    """Create MediaCleaner with mocked dependencies."""
    return MediaCleaner(standard_config, media_server=mock_media_server)


class TestProcessLeavingSoon:
    """Tests for process_leaving_soon method."""

    def test_skips_when_disabled(self, media_cleaner, mock_media_server):
        """Test that processing is skipped when leaving_soon is disabled."""
        library_config = {
            "name": "Movies",
            "leaving_soon": {"enabled": False},
        }
        plex_library = MagicMock()
        items_to_tag = [{"title": "Movie 1"}]

        media_cleaner.process_leaving_soon(library_config, plex_library, items_to_tag, "movie")

        # Should not interact with media server
        mock_media_server.find_item.assert_not_called()

    def test_skips_when_no_config(self, media_cleaner, mock_media_server):
        """Test that processing is skipped when leaving_soon config is missing."""
        library_config = {"name": "Movies"}
        plex_library = MagicMock()
        items_to_tag = [{"title": "Movie 1"}]

        media_cleaner.process_leaving_soon(library_config, plex_library, items_to_tag, "movie")

        mock_media_server.find_item.assert_not_called()

    def test_skips_when_no_media_server(self, standard_config):
        """Test that processing is skipped when media_server is not configured."""
        cleaner = MediaCleaner(standard_config, media_server=None)
        library_config = {
            "name": "Movies",
            "leaving_soon": {"enabled": True},
        }

        # Should not raise, just log warning
        cleaner.process_leaving_soon(library_config, MagicMock(), [], "movie")

    def test_finds_plex_items_for_movies(self, media_cleaner, mock_media_server):
        """Test that Plex items are found for movie candidates."""
        library_config = {
            "name": "Movies",
            "leaving_soon": {
                "enabled": True,
                "collection": {"enabled": True},
            },
        }
        plex_library = MagicMock()
        mock_plex_item = MagicMock()
        mock_media_server.find_item.return_value = mock_plex_item
        mock_media_server.get_or_create_collection.return_value = MagicMock()

        items_to_tag = [
            {"title": "Movie 1", "year": 2020, "tmdbId": 550, "imdbId": "tt0137523"},
        ]

        media_cleaner.process_leaving_soon(library_config, plex_library, items_to_tag, "movie")

        mock_media_server.find_item.assert_called_once_with(
            plex_library,
            tmdb_id=550,
            tvdb_id=None,
            imdb_id="tt0137523",
            title="Movie 1",
            year=2020,
        )

    def test_finds_plex_items_for_shows(self, media_cleaner, mock_media_server):
        """Test that Plex items are found for show candidates."""
        library_config = {
            "name": "TV Shows",
            "leaving_soon": {
                "enabled": True,
                "collection": {"enabled": True},
            },
        }
        plex_library = MagicMock()
        mock_plex_item = MagicMock()
        mock_media_server.find_item.return_value = mock_plex_item
        mock_media_server.get_or_create_collection.return_value = MagicMock()

        items_to_tag = [
            {"title": "Show 1", "year": 2018, "tvdbId": 81189, "imdbId": "tt1234567"},
        ]

        media_cleaner.process_leaving_soon(library_config, plex_library, items_to_tag, "show")

        mock_media_server.find_item.assert_called_once_with(
            plex_library,
            tmdb_id=None,
            tvdb_id=81189,
            imdb_id="tt1234567",
            title="Show 1",
            year=2018,
        )

    def test_updates_collection_when_enabled(self, media_cleaner, mock_media_server):
        """Test that collection is updated when collection is enabled."""
        library_config = {
            "name": "Movies",
            "leaving_soon": {
                "enabled": True,
                "collection": {"enabled": True, "name": "Leaving Soon"},
            },
        }
        plex_library = MagicMock()
        mock_plex_item = MagicMock()
        mock_collection = MagicMock()
        mock_media_server.find_item.return_value = mock_plex_item
        mock_media_server.get_or_create_collection.return_value = mock_collection

        items_to_tag = [{"title": "Movie 1", "year": 2020}]

        media_cleaner.process_leaving_soon(library_config, plex_library, items_to_tag, "movie")

        mock_media_server.get_or_create_collection.assert_called_once_with(
            plex_library, "Leaving Soon"
        )
        mock_media_server.set_collection_items.assert_called_once_with(
            mock_collection, [mock_plex_item]
        )

    def test_updates_labels_when_enabled(self, media_cleaner, mock_media_server):
        """Test that labels are updated when labels is enabled."""
        library_config = {
            "name": "Movies",
            "leaving_soon": {
                "enabled": True,
                "labels": {"enabled": True, "name": "leaving-soon", "clear_on_run": True},
            },
        }
        plex_library = MagicMock()
        mock_plex_item = MagicMock()
        mock_plex_item.ratingKey = "1001"
        mock_plex_item.labels = []
        mock_media_server.find_item.return_value = mock_plex_item
        mock_media_server.get_items_with_label.return_value = []

        items_to_tag = [{"title": "Movie 1", "year": 2020}]

        media_cleaner.process_leaving_soon(library_config, plex_library, items_to_tag, "movie")

        mock_media_server.add_label.assert_called_once_with(mock_plex_item, "leaving-soon")

    def test_clears_old_labels_when_configured(self, media_cleaner, mock_media_server):
        """Test that old labels are removed when clear_on_run is True."""
        library_config = {
            "name": "Movies",
            "leaving_soon": {
                "enabled": True,
                "labels": {"enabled": True, "name": "leaving-soon", "clear_on_run": True},
            },
        }
        plex_library = MagicMock()

        # Current item to tag
        mock_plex_item = MagicMock()
        mock_plex_item.ratingKey = "1001"
        mock_plex_item.labels = []

        # Old item that had the label but is no longer in the list
        old_labeled_item = MagicMock()
        old_labeled_item.ratingKey = "9999"

        mock_media_server.find_item.return_value = mock_plex_item
        mock_media_server.get_items_with_label.return_value = [old_labeled_item]

        items_to_tag = [{"title": "Movie 1", "year": 2020}]

        media_cleaner.process_leaving_soon(library_config, plex_library, items_to_tag, "movie")

        # Should remove label from old item
        mock_media_server.remove_label.assert_called_once_with(old_labeled_item, "leaving-soon")
        # Should add label to new item
        mock_media_server.add_label.assert_called_once_with(mock_plex_item, "leaving-soon")

    def test_handles_missing_plex_items(self, media_cleaner, mock_media_server):
        """Test that missing Plex items are handled gracefully."""
        library_config = {
            "name": "Movies",
            "leaving_soon": {
                "enabled": True,
                "collection": {"enabled": True},
            },
        }
        plex_library = MagicMock()
        mock_media_server.find_item.return_value = None
        mock_media_server.get_or_create_collection.return_value = MagicMock()

        items_to_tag = [{"title": "Missing Movie", "year": 2020}]

        # Should not raise
        media_cleaner.process_leaving_soon(library_config, plex_library, items_to_tag, "movie")

        # Collection should be updated with empty list
        mock_media_server.set_collection_items.assert_called_once()

    def test_does_not_skip_label_if_already_present(self, media_cleaner, mock_media_server):
        """Test that labels are not re-added if already present."""
        library_config = {
            "name": "Movies",
            "leaving_soon": {
                "enabled": True,
                "labels": {"enabled": True, "name": "leaving-soon", "clear_on_run": False},
            },
        }
        plex_library = MagicMock()

        mock_label = MagicMock()
        mock_label.tag = "leaving-soon"
        mock_plex_item = MagicMock()
        mock_plex_item.ratingKey = "1001"
        mock_plex_item.labels = [mock_label]

        mock_media_server.find_item.return_value = mock_plex_item
        mock_media_server.get_items_with_label.return_value = []

        items_to_tag = [{"title": "Movie 1", "year": 2020}]

        media_cleaner.process_leaving_soon(library_config, plex_library, items_to_tag, "movie")

        # Should not add label since it's already present
        mock_media_server.add_label.assert_not_called()


class TestTaggingOnlyMode:
    """Tests for tagging_only mode in process_movie and process_show."""

    @pytest.fixture
    def media_cleaner_non_dry_run(self, mock_media_server):
        """Create MediaCleaner with dry_run=False."""
        config = MagicMock(
            settings={
                "dry_run": False,
                "action_delay": 0,
                "plex": {"url": "http://localhost:32400", "token": "test"},
                "tautulli": {"url": "http://localhost:8181", "api_key": "test"},
            }
        )
        return MediaCleaner(config, media_server=mock_media_server)

    def test_process_movie_tagging_only_skips_deletion(self, media_cleaner_non_dry_run):
        """Test that tagging_only mode skips movie deletion."""
        library = {
            "name": "Movies",
            "leaving_soon": {"enabled": True, "tagging_only": True},
        }
        radarr_instance = MagicMock()
        radarr_movie = {"title": "Test Movie", "sizeOnDisk": 1000000000}

        media_cleaner_non_dry_run.process_movie(
            library, radarr_instance, radarr_movie, 0, 10
        )

        # Should not call delete
        radarr_instance.del_movie.assert_not_called()

    def test_process_show_tagging_only_skips_deletion(self, media_cleaner_non_dry_run):
        """Test that tagging_only mode skips show deletion."""
        library = {
            "name": "TV Shows",
            "leaving_soon": {"enabled": True, "tagging_only": True},
        }
        sonarr_instance = MagicMock()
        sonarr_show = {
            "id": 1,
            "title": "Test Show",
            "statistics": {"sizeOnDisk": 1000000000, "episodeFileCount": 10},
        }

        media_cleaner_non_dry_run.process_show(
            library, sonarr_instance, sonarr_show, 0, 10
        )

        # Should not call delete methods
        sonarr_instance.get_episode.assert_not_called()

    def test_process_movie_normal_mode_deletes(self, media_cleaner_non_dry_run):
        """Test that normal mode (not tagging_only) deletes movies."""
        library = {
            "name": "Movies",
            "leaving_soon": {"enabled": True, "tagging_only": False},
        }
        radarr_instance = MagicMock()
        radarr_movie = {"id": 1, "title": "Test Movie", "sizeOnDisk": 1000000000}

        media_cleaner_non_dry_run.process_movie(
            library, radarr_instance, radarr_movie, 0, 10
        )

        # Should call delete
        radarr_instance.del_movie.assert_called_once()

    def test_process_movie_without_leaving_soon_deletes(self, media_cleaner_non_dry_run):
        """Test that movies are deleted when leaving_soon is not configured."""
        library = {"name": "Movies"}
        radarr_instance = MagicMock()
        radarr_movie = {"id": 1, "title": "Test Movie", "sizeOnDisk": 1000000000}

        media_cleaner_non_dry_run.process_movie(
            library, radarr_instance, radarr_movie, 0, 10
        )

        # Should call delete
        radarr_instance.del_movie.assert_called_once()


class TestLeavingSoonWithPreviewItems:
    """Tests for leaving_soon with preview candidates."""

    @pytest.fixture
    def media_cleaner_with_server(self, standard_config, mock_media_server):
        """Create MediaCleaner with mocked media server."""
        return MediaCleaner(standard_config, media_server=mock_media_server)

    def test_process_multiple_items(self, media_cleaner_with_server, mock_media_server):
        """Test processing multiple preview items."""
        library_config = {
            "name": "Movies",
            "leaving_soon": {
                "enabled": True,
                "collection": {"enabled": True},
            },
        }
        plex_library = MagicMock()

        # Create multiple mock items
        mock_items = []
        for i in range(3):
            item = MagicMock()
            item.ratingKey = str(1000 + i)
            mock_items.append(item)

        mock_media_server.find_item.side_effect = mock_items
        mock_collection = MagicMock()
        mock_media_server.get_or_create_collection.return_value = mock_collection

        items_to_tag = [
            {"title": f"Movie {i}", "year": 2020 + i, "tmdbId": 550 + i}
            for i in range(3)
        ]

        media_cleaner_with_server.process_leaving_soon(
            library_config, plex_library, items_to_tag, "movie"
        )

        # Should find all items
        assert mock_media_server.find_item.call_count == 3
        # Should update collection with all items
        mock_media_server.set_collection_items.assert_called_once_with(
            mock_collection, mock_items
        )

    def test_empty_items_clears_collection(self, media_cleaner_with_server, mock_media_server):
        """Test that empty items list clears the collection."""
        library_config = {
            "name": "Movies",
            "leaving_soon": {
                "enabled": True,
                "collection": {"enabled": True, "clear_on_run": True},
            },
        }
        plex_library = MagicMock()
        mock_collection = MagicMock()
        mock_media_server.get_or_create_collection.return_value = mock_collection

        media_cleaner_with_server.process_leaving_soon(
            library_config, plex_library, [], "movie"
        )

        # Should update collection with empty list
        mock_media_server.set_collection_items.assert_called_once_with(
            mock_collection, []
        )
