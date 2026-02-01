# encoding: utf-8
"""
Helper utilities for Plex integration testing.

Provides a test helper class that works with real PlexAPI for integration tests.
"""

import time
from typing import Optional, List
from plexapi.server import PlexServer
from plexapi.library import LibrarySection, MovieSection, ShowSection
from plexapi.video import Movie, Show
from plexapi.collection import Collection


class PlexTestHelper:
    """
    Helper class for Plex integration testing.

    Provides methods to interact with a real Plex server for testing,
    including collection and label management.
    """

    def __init__(self, server: PlexServer):
        self.server = server
        self._movies_section = None
        self._tvshows_section = None

    @property
    def movies_section(self) -> Optional[MovieSection]:
        """Get the Movies library section."""
        if self._movies_section is None:
            from plexapi.exceptions import NotFound
            try:
                self._movies_section = self.server.library.section("Movies")
            except NotFound:
                return None
        return self._movies_section

    @property
    def tvshows_section(self) -> Optional[ShowSection]:
        """Get the TV Shows library section."""
        if self._tvshows_section is None:
            from plexapi.exceptions import NotFound
            try:
                self._tvshows_section = self.server.library.section("TV Shows")
            except NotFound:
                return None
        return self._tvshows_section

    def get_all_movies(self) -> List[Movie]:
        """Get all movies in the library."""
        if self.movies_section is None:
            return []
        return self.movies_section.all()

    def get_all_shows(self) -> List[Show]:
        """Get all TV shows in the library."""
        if self.tvshows_section is None:
            return []
        return self.tvshows_section.all()

    def get_movie_by_title(self, title: str) -> Optional[Movie]:
        """Find a movie by title."""
        try:
            results = self.movies_section.search(title=title)
            return results[0] if results else None
        except Exception:
            return None

    def get_show_by_title(self, title: str) -> Optional[Show]:
        """Find a show by title."""
        try:
            results = self.tvshows_section.search(title=title)
            return results[0] if results else None
        except Exception:
            return None

    # Collection operations

    def get_collection(
        self, name: str, section: Optional[LibrarySection] = None
    ) -> Optional[Collection]:
        """Get a collection by name."""
        section = section or self.movies_section
        try:
            return section.collection(name)
        except Exception:
            return None

    def create_collection(
        self, name: str, items: List, section: Optional[LibrarySection] = None
    ) -> Collection:
        """Create a collection with the given items."""
        section = section or self.movies_section
        return section.createCollection(title=name, items=items)

    def delete_collection(
        self, name: str, section: Optional[LibrarySection] = None
    ) -> bool:
        """Delete a collection by name."""
        collection = self.get_collection(name, section)
        if collection:
            collection.delete()
            return True
        return False

    def add_to_collection(
        self, collection_name: str, items: List, section: Optional[LibrarySection] = None
    ) -> Collection:
        """Add items to a collection, creating it if needed."""
        section = section or self.movies_section
        collection = self.get_collection(collection_name, section)
        if collection:
            collection.addItems(items)
            return collection
        else:
            return self.create_collection(collection_name, items, section)

    def remove_from_collection(
        self, collection_name: str, items: List, section: Optional[LibrarySection] = None
    ) -> bool:
        """Remove items from a collection."""
        collection = self.get_collection(collection_name, section)
        if collection:
            collection.removeItems(items)
            return True
        return False

    def get_collection_items(
        self, collection_name: str, section: Optional[LibrarySection] = None
    ) -> List:
        """Get all items in a collection."""
        collection = self.get_collection(collection_name, section)
        if collection:
            return collection.items()
        return []

    # Label operations

    def add_label(self, item, label: str, wait: float = 0.5) -> None:
        """Add a label to an item.

        Args:
            item: The Plex item to label
            label: The label to add
            wait: Seconds to wait for Plex to process (default 0.5)
        """
        item.addLabel(label)
        if wait:
            time.sleep(wait)

    def remove_label(self, item, label: str, wait: float = 0.5) -> None:
        """Remove a label from an item.

        Args:
            item: The Plex item to unlabel
            label: The label to remove
            wait: Seconds to wait for Plex to process (default 0.5)
        """
        item.removeLabel(label)
        if wait:
            time.sleep(wait)

    def get_labels(self, item) -> List[str]:
        """Get all labels on an item."""
        return [label.tag for label in item.labels]

    def has_label(self, item, label: str) -> bool:
        """Check if an item has a specific label."""
        return label in self.get_labels(item)

    def get_items_with_label(
        self, label: str, section: Optional[LibrarySection] = None
    ) -> List:
        """Get all items with a specific label."""
        section = section or self.movies_section
        return section.search(label=label)

    # Cleanup helpers

    def cleanup_test_collections(self, prefix: str = "Test") -> int:
        """Delete all collections starting with a prefix."""
        count = 0
        for section in [self.movies_section, self.tvshows_section]:
            for collection in section.collections():
                if collection.title.startswith(prefix):
                    collection.delete()
                    count += 1
        return count

    def cleanup_test_labels(self, labels: List[str]) -> int:
        """Remove specific labels from all items."""
        count = 0
        for section in [self.movies_section, self.tvshows_section]:
            for item in section.all():
                for label in labels:
                    if self.has_label(item, label):
                        self.remove_label(item, label)
                        count += 1
        return count

    # Test data info

    def get_library_stats(self) -> dict:
        """Get statistics about the libraries."""
        return {
            "movies": {
                "count": len(self.get_all_movies()),
                "collections": len(self.movies_section.collections()),
            },
            "tvshows": {
                "count": len(self.get_all_shows()),
                "collections": len(self.tvshows_section.collections()),
            },
        }


def create_plex_helper(plex_url: str, plex_token: str = "") -> PlexTestHelper:
    """Create a PlexTestHelper instance."""
    if plex_token:
        server = PlexServer(plex_url, plex_token)
    else:
        server = PlexServer(plex_url)
    return PlexTestHelper(server)
