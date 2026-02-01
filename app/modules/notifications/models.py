# encoding: utf-8
"""Data models for the notification system."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class LibraryStats:
    """Statistics for a single library during a run."""

    name: str
    instance_name: str
    instance_type: str  # "radarr" or "sonarr"
    items_found: int = 0
    items_deleted: int = 0
    items_unmatched: int = 0
    bytes_freed: int = 0


@dataclass
class DeletedItem:
    """Represents a deleted or preview media item."""

    title: str
    year: Optional[int]
    media_type: str  # "movie" or "show"
    size_bytes: int
    library_name: str
    instance_name: str

    def format_title(self) -> str:
        """Format title with year if available."""
        if self.year:
            return f"{self.title} ({self.year})"
        return self.title

    @classmethod
    def from_radarr(cls, data: dict, library_name: str, instance_name: str) -> "DeletedItem":
        """Create DeletedItem from Radarr movie data."""
        return cls(
            title=data.get("title", "Unknown"),
            year=data.get("year"),
            media_type="movie",
            size_bytes=data.get("sizeOnDisk", 0),
            library_name=library_name,
            instance_name=instance_name,
        )

    @classmethod
    def from_sonarr(cls, data: dict, library_name: str, instance_name: str) -> "DeletedItem":
        """Create DeletedItem from Sonarr series data."""
        return cls(
            title=data.get("title", "Unknown"),
            year=data.get("year"),
            media_type="show",
            size_bytes=data.get("statistics", {}).get("sizeOnDisk", 0),
            library_name=library_name,
            instance_name=instance_name,
        )


@dataclass
class RunResult:
    """Aggregates results from a Deleterr run."""

    is_dry_run: bool = True
    deleted_items: list[DeletedItem] = field(default_factory=list)
    preview_items: list[DeletedItem] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    library_stats: list[LibraryStats] = field(default_factory=list)

    def add_deleted(self, item: DeletedItem) -> None:
        """Add a deleted item to the results."""
        self.deleted_items.append(item)

    def add_preview(self, item: DeletedItem) -> None:
        """Add a preview item to the results."""
        self.preview_items.append(item)

    @property
    def total_freed_bytes(self) -> int:
        """Calculate total bytes freed by deletions."""
        return sum(item.size_bytes for item in self.deleted_items)

    @property
    def total_preview_bytes(self) -> int:
        """Calculate total bytes in preview items."""
        return sum(item.size_bytes for item in self.preview_items)

    @property
    def deleted_movies(self) -> list[DeletedItem]:
        """Get deleted movies only."""
        return [item for item in self.deleted_items if item.media_type == "movie"]

    @property
    def deleted_shows(self) -> list[DeletedItem]:
        """Get deleted shows only."""
        return [item for item in self.deleted_items if item.media_type == "show"]

    @property
    def preview_movies(self) -> list[DeletedItem]:
        """Get preview movies only."""
        return [item for item in self.preview_items if item.media_type == "movie"]

    @property
    def preview_shows(self) -> list[DeletedItem]:
        """Get preview shows only."""
        return [item for item in self.preview_items if item.media_type == "show"]

    def has_content(self) -> bool:
        """Check if there's any content to report."""
        return bool(self.deleted_items or self.preview_items)

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate run duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    @property
    def total_items_found(self) -> int:
        """Total items found across all libraries."""
        return sum(stats.items_found for stats in self.library_stats)

    @property
    def total_unmatched(self) -> int:
        """Total unmatched items across all libraries."""
        return sum(stats.items_unmatched for stats in self.library_stats)

    def add_library_stats(self, stats: LibraryStats) -> None:
        """Add statistics for a library."""
        self.library_stats.append(stats)
