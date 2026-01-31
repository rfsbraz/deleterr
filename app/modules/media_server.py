# encoding: utf-8
"""Abstract interface for media server operations.

This module provides an abstraction layer for media server operations,
allowing the application to work with different media servers (Plex, Jellyfin, etc.)
through a common interface.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseMediaServer(ABC):
    """Abstract base class for media server operations.

    Provides a common interface for collection and label management
    across different media servers.
    """

    @abstractmethod
    def get_library(self, name: str) -> Any:
        """Get library by name.

        Args:
            name: The name of the library.

        Returns:
            The library object.

        Raises:
            Exception if library not found.
        """
        pass

    @abstractmethod
    def get_or_create_collection(self, library: Any, name: str) -> Any:
        """Get existing collection or create a new one.

        Args:
            library: The library object.
            name: The name of the collection.

        Returns:
            The collection object.
        """
        pass

    @abstractmethod
    def set_collection_items(self, collection: Any, items: list) -> None:
        """Replace collection contents with given items.

        Args:
            collection: The collection object.
            items: List of media items to set in the collection.
        """
        pass

    @abstractmethod
    def add_label(self, item: Any, label: str) -> None:
        """Add a label/tag to a media item.

        Args:
            item: The media item.
            label: The label to add.
        """
        pass

    @abstractmethod
    def remove_label(self, item: Any, label: str) -> None:
        """Remove a label/tag from a media item.

        Args:
            item: The media item.
            label: The label to remove.
        """
        pass

    @abstractmethod
    def get_items_with_label(self, library: Any, label: str) -> list:
        """Get all items in library with given label.

        Args:
            library: The library object.
            label: The label to search for.

        Returns:
            List of media items with the label.
        """
        pass

    @abstractmethod
    def find_item(
        self,
        library: Any,
        title: Optional[str] = None,
        year: Optional[int] = None,
        tmdb_id: Optional[int] = None,
        tvdb_id: Optional[int] = None,
        imdb_id: Optional[str] = None,
    ) -> Optional[Any]:
        """Find a media item by various identifiers.

        Args:
            library: The library object.
            title: The title of the media.
            year: The release year.
            tmdb_id: The TMDB ID.
            tvdb_id: The TVDB ID.
            imdb_id: The IMDB ID.

        Returns:
            The media item if found, None otherwise.
        """
        pass
