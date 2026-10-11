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

    def get_or_create_collection(self, library: Any, name: str, items: Optional[list] = None) -> Optional[Any]:
        """Get existing collection or create a new one.

        Args:
            library: The Plex library section.
            name: The name of the collection.
            items: Optional list of items to create the collection with.

        Returns:
            The collection object, or None if it doesn't exist and no items to create with.
        """
        try:
            return library.collection(name)
        except NotFound:
            if items:
                logger.debug(f"Creating new collection '{name}' with {len(items)} items")
                return library.createCollection(title=name, smart=False, items=items)
            else:
                logger.debug(f"Collection '{name}' does not exist and no items to add, skipping creation")
                return None

    def set_collection_visibility(
        self, collection: Any, home: bool = False, shared: bool = True
    ) -> None:
        """Set collection visibility on home screens.

        Args:
            collection: The Plex collection.
            home: Whether to show on owner's Home page.
            shared: Whether to show on shared users' (Friends') Home pages.
        """
        try:
            hub = collection.visibility()
            hub.updateVisibility(home=home, shared=shared)
            logger.debug(
                f"Set collection '{collection.title}' visibility: home={home}, shared={shared}"
            )
        except Exception as e:
            logger.warning(
                f"Could not set visibility for collection '{collection.title}': {e}. "
                "The collection will still work but may not appear on home screens."
            )

    def get_collection(self, library: Any, name: str) -> Optional[Any]:
        """Get collection by name if it exists.

        Args:
            library: The Plex library section.
            name: The name of the collection.

        Returns:
            The collection object if found, None otherwise.
        """
        try:
            return library.collection(name)
        except NotFound:
            return None

    def set_collection_summary(self, collection: Any, summary: str) -> None:
        """Set the summary/description of a Plex collection.

        Args:
            collection: The Plex collection.
            summary: The summary text to set.
        """
        try:
            collection.editSummary(summary)
            logger.debug(f"Set summary for collection '{collection.title}'")
        except Exception as e:
            logger.warning(
                f"Could not set summary for collection '{collection.title}': {e}. "
                "The collection will still work but won't show the deletion date."
            )

    def set_collection_items(
        self, collection: Any, items: list, library: Optional[Any] = None
    ) -> tuple[Any, list]:
        """Replace collection contents with given items.

        Args:
            collection: The Plex collection.
            items: List of Plex media items to set in the collection.
            library: The Plex library the collection belongs to. If given, a
                collection that rejects every add (batch and per-item) is
                deleted and recreated from scratch, which clears whatever
                stale server-side collection state was causing Plex to
                reject the add.

        Returns:
            A tuple of (collection, added_items): the collection actually
            in use (may be a freshly recreated one) and the items that were
            successfully added to it.
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
                logger.warning(
                    f"Error removing {len(current_items)} items from collection '{collection.title}': {e}. "
                    "Some items may remain in the collection."
                )

        if not items:
            return collection, []

        # Try a single batch add first. Some Plex servers reject the batch add-items
        # URI (e.g. a 400 on a long multi-id request), so fall back to adding items
        # one at a time rather than losing the whole set. Return the items that made
        # it in so the caller only records genuinely-tagged items in state.
        try:
            collection.addItems(items)
            return collection, list(items)
        except Exception as e:
            logger.warning(
                f"Batch add of {len(items)} items to collection '{collection.title}' failed: {e}. "
                "Retrying one item at a time."
            )

        added = []
        for item in items:
            try:
                collection.addItems([item])
                added.append(item)
            except Exception as e:
                logger.warning(
                    f"Could not add '{getattr(item, 'title', 'Unknown')}' to collection "
                    f"'{collection.title}': {e}."
                )

        if added:
            return collection, added

        if library is None:
            logger.error(
                f"Failed to add any of {len(items)} items to collection '{collection.title}'. "
                "The leaving_soon death row cannot progress until items can be tagged in Plex."
            )
            return collection, added

        # Every add attempt failed, batch and per-item alike - this matches the
        # symptom of a Plex collection stuck in some broken internal state that
        # rejects all adds with a generic 400. Deleting and recreating it clears
        # that state (confirmed manually on 2026-08-17: recreated collections
        # accepted every item on the first batch add).
        logger.warning(
            f"Collection '{collection.title}' rejected every item (batch and single-item retries). "
            "Deleting and recreating it - this usually clears stale Plex-side collection state."
        )
        collection_name = collection.title
        try:
            collection.delete()
            new_collection = library.createCollection(
                title=collection_name, smart=False, items=items
            )
            logger.info(
                f"Recreated collection '{collection_name}' with {len(items)} items after delete."
            )
            return new_collection, list(items)
        except Exception as e:
            logger.error(
                f"Failed to delete and recreate collection '{collection_name}': {e}. "
                "The leaving_soon death row cannot progress until items can be tagged in Plex."
            )
            return collection, added

    def add_label(self, item: Any, label: str) -> None:
        """Add a label to a Plex media item.

        Args:
            item: The Plex media item.
            label: The label to add.
        """
        try:
            item.addLabel(label)
        except Exception as e:
            logger.debug(f"Could not add label '{label}' to '{item.title}': {e}")

    def remove_label(self, item: Any, label: str) -> None:
        """Remove a label from a Plex media item.

        Args:
            item: The Plex media item.
            label: The label to remove.
        """
        try:
            item.removeLabel(label)
        except Exception as e:
            logger.debug(f"Could not remove label '{label}' from '{item.title}': {e}")

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
            logger.warning(
                f"Error searching for items with label '{label}' in library '{library.title}': {e}. "
                "Labeled items may not be processed correctly."
            )
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

    def get_guids(self, item: Any) -> dict:
        """Extract GUIDs from a Plex media item.

        Args:
            item: The Plex media item.

        Returns:
            Dictionary with tmdb_id, tvdb_id, imdb_id keys (values may be None).
        """
        guids = {"tmdb_id": None, "tvdb_id": None, "imdb_id": None}

        try:
            for guid in item.guids:
                if guid.id.startswith("tmdb://"):
                    guids["tmdb_id"] = int(guid.id.replace("tmdb://", ""))
                elif guid.id.startswith("tvdb://"):
                    guids["tvdb_id"] = int(guid.id.replace("tvdb://", ""))
                elif guid.id.startswith("imdb://"):
                    guids["imdb_id"] = guid.id.replace("imdb://", "")
        except Exception as e:
            logger.debug(f"Error extracting GUIDs from '{item.title}': {e}")

        return guids
