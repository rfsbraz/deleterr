# encoding: utf-8
"""Plex media server implementation.

Implements the BaseMediaServer interface for Plex-specific operations
using the PlexAPI library.
"""

from typing import Any, Optional

import requests
from plexapi.exceptions import NotFound
from plexapi.server import PlexServer

from app import logger
from app.modules.media_server import BaseMediaServer


class PlexMediaServer(BaseMediaServer):
    """Plex implementation of the media server interface."""

    def __init__(self, url: str, token: str, ssl_verify: bool = True, timeout: int = 120):
        """Initialize Plex server connection.

        Args:
            url: Plex server URL.
            token: Plex authentication token.
            ssl_verify: Whether to verify SSL certificates.
            timeout: Request timeout in seconds.
        """
        session = requests.Session()
        session.verify = ssl_verify
        self.server = PlexServer(url, token, session=session, timeout=timeout)

    def get_library(self, name: str) -> Any:
        """Get library by name.

        Args:
            name: The name of the library.

        Returns:
            The Plex library section.

        Raises:
            NotFound if library doesn't exist.
        """
        return self.server.library.section(name)

    def get_or_create_collection(self, library: Any, name: str) -> Any:
        """Get existing collection or create a new one.

        Args:
            library: The Plex library section.
            name: The name of the collection.

        Returns:
            The collection object.
        """
        try:
            return library.collection(name)
        except NotFound:
            # Create an empty collection
            # PlexAPI's createCollection requires items, so we create with smart=True
            # which allows an empty collection
            logger.debug(f"Creating new collection '{name}' in library '{library.title}'")
            return library.createCollection(title=name, smart=False, items=[])

    def set_collection_items(self, collection: Any, items: list) -> None:
        """Replace collection contents with given items.

        Args:
            collection: The Plex collection.
            items: List of Plex media items to set in the collection.
        """
        # Get current items in collection
        try:
            current_items = collection.items()
        except Exception:
            current_items = []

        # Remove all current items
        if current_items:
            try:
                collection.removeItems(current_items)
            except Exception as e:
                logger.warning(f"Error removing items from collection: {e}")

        # Add new items
        if items:
            try:
                collection.addItems(items)
            except Exception as e:
                logger.warning(f"Error adding items to collection: {e}")

    def add_label(self, item: Any, label: str) -> None:
        """Add a label to a Plex media item.

        Args:
            item: The Plex media item.
            label: The label to add.
        """
        try:
            item.addLabel(label)
        except Exception as e:
            logger.warning(f"Error adding label '{label}' to '{item.title}': {e}")

    def remove_label(self, item: Any, label: str) -> None:
        """Remove a label from a Plex media item.

        Args:
            item: The Plex media item.
            label: The label to remove.
        """
        try:
            item.removeLabel(label)
        except Exception as e:
            logger.warning(f"Error removing label '{label}' from '{item.title}': {e}")

    def get_items_with_label(self, library: Any, label: str) -> list:
        """Get all items in library with given label.

        Args:
            library: The Plex library section.
            label: The label to search for.

        Returns:
            List of Plex media items with the label.
        """
        try:
            return library.search(label=label)
        except Exception as e:
            logger.warning(f"Error searching for items with label '{label}': {e}")
            return []

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

        Searches by GUID first (most reliable), then falls back to title+year.

        Args:
            library: The Plex library section.
            title: The title of the media.
            year: The release year.
            tmdb_id: The TMDB ID.
            tvdb_id: The TVDB ID.
            imdb_id: The IMDB ID.

        Returns:
            The Plex media item if found, None otherwise.
        """
        # Try searching by GUID first (most reliable)
        if tmdb_id:
            try:
                results = library.search(guid=f"tmdb://{tmdb_id}")
                if results:
                    return results[0]
            except Exception:
                pass

        if tvdb_id:
            try:
                results = library.search(guid=f"tvdb://{tvdb_id}")
                if results:
                    return results[0]
            except Exception:
                pass

        if imdb_id:
            try:
                results = library.search(guid=f"imdb://{imdb_id}")
                if results:
                    return results[0]
            except Exception:
                pass

        # Fall back to title + year search
        if title:
            try:
                results = library.search(title=title)
                for item in results:
                    # Check year match (allow 2 year tolerance)
                    if year and item.year:
                        if abs(item.year - year) <= 2:
                            return item
                    elif not year:
                        # No year specified, return first title match
                        return item
            except Exception as e:
                logger.debug(f"Error searching for '{title}' ({year}): {e}")

        return None
