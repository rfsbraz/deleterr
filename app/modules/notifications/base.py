# encoding: utf-8
"""Base class for notification providers."""

from abc import ABC, abstractmethod
from typing import Optional

from app.modules.notifications.models import DeletedItem, RunResult


class BaseNotificationProvider(ABC):
    """Abstract base class for notification providers."""

    def __init__(self, config: dict):
        """Initialize the provider with configuration."""
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name."""
        pass

    @property
    @abstractmethod
    def enabled(self) -> bool:
        """Return whether the provider is properly configured and enabled."""
        pass

    @abstractmethod
    def send(self, result: RunResult) -> bool:
        """
        Send a notification with the run results.

        Args:
            result: The run result containing deleted and preview items.

        Returns:
            True if notification was sent successfully, False otherwise.
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test the provider connection.

        Returns:
            True if connection is successful, False otherwise.
        """
        pass

    @staticmethod
    def format_size(size_bytes: int) -> str:
        """Format bytes as human-readable size."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if abs(size_bytes) < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"

    def build_title(self, result: RunResult) -> str:
        """Build the notification title."""
        prefix = "[DRY-RUN] " if result.is_dry_run else ""
        return f"{prefix}Deleterr Run Complete"

    def build_summary(self, result: RunResult) -> str:
        """Build the summary text."""
        deleted_count = len(result.deleted_items)
        freed_size = self.format_size(result.total_freed_bytes)

        if result.is_dry_run:
            return f"Would delete {deleted_count} items, freeing {freed_size}"
        return f"Deleted {deleted_count} items, freed {freed_size}"

    def build_item_list(
        self, items: list[DeletedItem], max_items: int = 10
    ) -> list[str]:
        """Build a list of formatted item strings."""
        lines = []
        for item in items[:max_items]:
            size = self.format_size(item.size_bytes)
            lines.append(f"• {item.format_title()} - {size}")

        if len(items) > max_items:
            remaining = len(items) - max_items
            lines.append(f"... and {remaining} more")

        return lines

    def build_preview_section(
        self, result: RunResult, max_items: int = 5
    ) -> Optional[str]:
        """Build the preview section if there are preview items."""
        if not result.preview_items:
            return None

        preview_count = len(result.preview_items)
        preview_size = self.format_size(result.total_preview_bytes)

        lines = [f"Next scheduled deletions ({preview_count} items, {preview_size}):"]
        lines.extend(self.build_item_list(result.preview_items, max_items))

        return "\n".join(lines)
