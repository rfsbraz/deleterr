# encoding: utf-8
"""Unit tests for PlexMediaServer class."""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from app.modules.plex import PlexMediaServer
from app.modules.media_server import BaseMediaServer


class TestPlexMediaServerInterface:
    """Test that PlexMediaServer properly implements BaseMediaServer."""

    def test_implements_base_class(self):
        """Verify PlexMediaServer is a subclass of BaseMediaServer."""
        assert issubclass(PlexMediaServer, BaseMediaServer)

    @patch("app.modules.plex.PlexServer")
    def test_init_creates_server_connection(self, mock_plex_server):
        """Test that initialization creates a PlexServer instance."""
        plex = PlexMediaServer("http://localhost:32400", "test-token")
        mock_plex_server.assert_called_once()
        assert plex.server == mock_plex_server.return_value

    @patch("app.modules.plex.PlexServer")
    def test_init_with_ssl_verify_false(self, mock_plex_server):
        """Test that SSL verification setting is passed to session."""
        plex = PlexMediaServer("http://localhost:32400", "test-token", ssl_verify=False)
        # The session.verify should be set to False
        call_kwargs = mock_plex_server.call_args
        session = call_kwargs[1]["session"]
        assert session.verify is False

    @patch("app.modules.plex.PlexServer")
    def test_init_with_custom_timeout(self, mock_plex_server):
        """Test that custom timeout is passed to PlexServer."""
        plex = PlexMediaServer("http://localhost:32400", "test-token", timeout=60)
        call_kwargs = mock_plex_server.call_args
        assert call_kwargs[1]["timeout"] == 60


class TestPlexMediaServerLibrary:
    """Test library operations."""

    @pytest.fixture
    def plex_server(self):
        """Create a PlexMediaServer with mocked PlexServer."""
        with patch("app.modules.plex.PlexServer") as mock:
            server = PlexMediaServer("http://localhost:32400", "test-token")
            yield server, mock.return_value

    def test_get_library(self, plex_server):
        """Test getting a library by name."""
        plex, mock_server = plex_server
        mock_library = MagicMock()
        mock_server.library.section.return_value = mock_library

        result = plex.get_library("Movies")

        mock_server.library.section.assert_called_once_with("Movies")
        assert result == mock_library


class TestPlexMediaServerCollections:
    """Test collection operations."""

    @pytest.fixture
    def plex_server(self):
        """Create a PlexMediaServer with mocked PlexServer."""
        with patch("app.modules.plex.PlexServer") as mock:
            server = PlexMediaServer("http://localhost:32400", "test-token")
            yield server, mock.return_value

    def test_get_existing_collection(self, plex_server):
        """Test getting an existing collection."""
        plex, _ = plex_server
        mock_library = MagicMock()
        mock_collection = MagicMock()
        mock_library.collection.return_value = mock_collection

        result = plex.get_or_create_collection(mock_library, "Leaving Soon")

        mock_library.collection.assert_called_once_with("Leaving Soon")
        assert result == mock_collection

    def test_create_collection_when_not_found_with_items(self, plex_server):
        """Test creating a collection when it doesn't exist and items are provided."""
        from plexapi.exceptions import NotFound

        plex, _ = plex_server
        mock_library = MagicMock()
        mock_library.collection.side_effect = NotFound("Not found")
        mock_new_collection = MagicMock()
        mock_library.createCollection.return_value = mock_new_collection
        mock_items = [MagicMock(), MagicMock()]

        result = plex.get_or_create_collection(mock_library, "Leaving Soon", items=mock_items)

        mock_library.createCollection.assert_called_once_with(
            title="Leaving Soon", smart=False, items=mock_items
        )
        assert result == mock_new_collection

    def test_create_collection_when_not_found_no_items_returns_none(self, plex_server):
        """Test that None is returned when collection doesn't exist and no items provided."""
        from plexapi.exceptions import NotFound

        plex, _ = plex_server
        mock_library = MagicMock()
        mock_library.collection.side_effect = NotFound("Not found")

        result = plex.get_or_create_collection(mock_library, "Leaving Soon")

        mock_library.createCollection.assert_not_called()
        assert result is None

    def test_set_collection_items_replaces_all(self, plex_server):
        """Test that set_collection_items replaces all items."""
        plex, _ = plex_server
        mock_collection = MagicMock()
        current_items = [MagicMock(), MagicMock()]
        mock_collection.items.return_value = current_items
        new_items = [MagicMock(), MagicMock(), MagicMock()]

        plex.set_collection_items(mock_collection, new_items)

        mock_collection.removeItems.assert_called_once_with(current_items)
        mock_collection.addItems.assert_called_once_with(new_items)

    def test_set_collection_items_empty_collection(self, plex_server):
        """Test setting items on an empty collection."""
        plex, _ = plex_server
        mock_collection = MagicMock()
        mock_collection.items.return_value = []
        new_items = [MagicMock()]

        plex.set_collection_items(mock_collection, new_items)

        mock_collection.removeItems.assert_not_called()
        mock_collection.addItems.assert_called_once_with(new_items)

    def test_set_collection_items_to_empty(self, plex_server):
        """Test clearing a collection by setting empty items."""
        plex, _ = plex_server
        mock_collection = MagicMock()
        current_items = [MagicMock()]
        mock_collection.items.return_value = current_items

        plex.set_collection_items(mock_collection, [])

        mock_collection.removeItems.assert_called_once_with(current_items)
        mock_collection.addItems.assert_not_called()


class TestPlexMediaServerLabels:
    """Test label operations."""

    @pytest.fixture
    def plex_server(self):
        """Create a PlexMediaServer with mocked PlexServer."""
        with patch("app.modules.plex.PlexServer") as mock:
            server = PlexMediaServer("http://localhost:32400", "test-token")
            yield server, mock.return_value

    def test_add_label(self, plex_server):
        """Test adding a label to an item."""
        plex, _ = plex_server
        mock_item = MagicMock()

        plex.add_label(mock_item, "leaving-soon")

        mock_item.addLabel.assert_called_once_with("leaving-soon")

    def test_add_label_handles_error(self, plex_server):
        """Test that add_label handles errors gracefully."""
        plex, _ = plex_server
        mock_item = MagicMock()
        mock_item.title = "Test Movie"
        mock_item.addLabel.side_effect = Exception("API Error")

        # Should not raise exception
        plex.add_label(mock_item, "leaving-soon")

    def test_remove_label(self, plex_server):
        """Test removing a label from an item."""
        plex, _ = plex_server
        mock_item = MagicMock()

        plex.remove_label(mock_item, "leaving-soon")

        mock_item.removeLabel.assert_called_once_with("leaving-soon")

    def test_remove_label_handles_error(self, plex_server):
        """Test that remove_label handles errors gracefully."""
        plex, _ = plex_server
        mock_item = MagicMock()
        mock_item.title = "Test Movie"
        mock_item.removeLabel.side_effect = Exception("API Error")

        # Should not raise exception
        plex.remove_label(mock_item, "leaving-soon")

    def test_get_items_with_label(self, plex_server):
        """Test getting all items with a specific label."""
        plex, _ = plex_server
        mock_library = MagicMock()
        mock_items = [MagicMock(), MagicMock()]
        mock_library.search.return_value = mock_items

        result = plex.get_items_with_label(mock_library, "leaving-soon")

        mock_library.search.assert_called_once_with(label="leaving-soon")
        assert result == mock_items

    def test_get_items_with_label_handles_error(self, plex_server):
        """Test that get_items_with_label handles errors gracefully."""
        plex, _ = plex_server
        mock_library = MagicMock()
        mock_library.search.side_effect = Exception("API Error")

        result = plex.get_items_with_label(mock_library, "leaving-soon")

        assert result == []


class TestPlexMediaServerFindItem:
    """Test item finding operations."""

    @pytest.fixture
    def plex_server(self):
        """Create a PlexMediaServer with mocked PlexServer."""
        with patch("app.modules.plex.PlexServer") as mock:
            server = PlexMediaServer("http://localhost:32400", "test-token")
            yield server, mock.return_value

    def test_find_item_by_tmdb_id(self, plex_server):
        """Test finding an item by TMDB ID."""
        plex, _ = plex_server
        mock_library = MagicMock()
        mock_item = MagicMock()
        mock_library.search.return_value = [mock_item]

        result = plex.find_item(mock_library, tmdb_id=550)

        mock_library.search.assert_called_with(guid="tmdb://550")
        assert result == mock_item

    def test_find_item_by_tvdb_id(self, plex_server):
        """Test finding an item by TVDB ID."""
        plex, _ = plex_server
        mock_library = MagicMock()
        mock_item = MagicMock()
        # When only tvdb_id is provided, only tvdb search is performed
        mock_library.search.return_value = [mock_item]

        result = plex.find_item(mock_library, tvdb_id=81189)

        mock_library.search.assert_called_with(guid="tvdb://81189")
        assert result == mock_item

    def test_find_item_by_imdb_id(self, plex_server):
        """Test finding an item by IMDB ID."""
        plex, _ = plex_server
        mock_library = MagicMock()
        mock_item = MagicMock()
        # When only imdb_id is provided, only imdb search is performed
        mock_library.search.return_value = [mock_item]

        result = plex.find_item(mock_library, imdb_id="tt0137523")

        mock_library.search.assert_called_with(guid="imdb://tt0137523")
        assert result == mock_item

    def test_find_item_by_title_and_year(self, plex_server):
        """Test finding an item by title and year."""
        plex, _ = plex_server
        mock_library = MagicMock()
        mock_item = MagicMock()
        mock_item.year = 2020
        mock_library.search.return_value = [mock_item]

        result = plex.find_item(mock_library, title="Test Movie", year=2020)

        mock_library.search.assert_called_with(title="Test Movie")
        assert result == mock_item

    def test_find_item_by_title_with_year_tolerance(self, plex_server):
        """Test finding an item allows 2-year tolerance."""
        plex, _ = plex_server
        mock_library = MagicMock()
        mock_item = MagicMock()
        mock_item.year = 2018  # 2 years off from 2020
        mock_library.search.return_value = [mock_item]

        result = plex.find_item(mock_library, title="Test Movie", year=2020)

        assert result == mock_item

    def test_find_item_returns_none_when_not_found(self, plex_server):
        """Test that find_item returns None when item not found."""
        plex, _ = plex_server
        mock_library = MagicMock()
        mock_library.search.return_value = []

        result = plex.find_item(mock_library, title="Nonexistent")

        assert result is None
