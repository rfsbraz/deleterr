# encoding: utf-8
"""Discord webhook notification provider."""

from datetime import datetime, timezone
from typing import Optional

import requests

from app import logger
from app.modules.notifications.base import BaseNotificationProvider
from app.modules.notifications.models import DeletedItem, RunResult


class DiscordProvider(BaseNotificationProvider):
    """Discord webhook notification provider with embed support."""

    # Discord embed color constants
    COLOR_SUCCESS = 0x2ECC71  # Green
    COLOR_DRY_RUN = 0x3498DB  # Blue
    COLOR_WARNING = 0xF39C12  # Orange

    @property
    def name(self) -> str:
        return "discord"

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("webhook_url"))

    def send(self, result: RunResult) -> bool:
        """Send notification via Discord webhook."""
        if not self.enabled:
            return False

        try:
            username = self.config.get("username", "Deleterr")
            avatar_url = self.config.get("avatar_url")

            payload = self._build_payload(result, username, avatar_url)

            response = requests.post(
                self.config.get("webhook_url"),
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Discord notification failed: {e}")
            return False

    def test_connection(self) -> bool:
        """Test Discord webhook connection."""
        if not self.enabled:
            return False

        try:
            response = requests.post(
                self.config.get("webhook_url"),
                json={
                    "username": self.config.get("username", "Deleterr"),
                    "content": "Connection test successful!",
                },
                timeout=30,
            )
            return response.status_code in (200, 204)
        except requests.exceptions.RequestException:
            return False

    def _build_payload(
        self,
        result: RunResult,
        username: str,
        avatar_url: Optional[str],
    ) -> dict:
        """Build the Discord webhook payload with embeds."""
        embeds = []

        # Main summary embed
        embeds.append(self._build_summary_embed(result))

        # Deleted items embed (if any)
        if result.deleted_items:
            embeds.append(self._build_deleted_embed(result))

        # Preview embed (if any)
        if result.preview_items:
            embeds.append(self._build_preview_embed(result))

        payload = {
            "username": username,
            "embeds": embeds,
        }

        if avatar_url:
            payload["avatar_url"] = avatar_url

        return payload

    def _build_summary_embed(self, result: RunResult) -> dict:
        """Build the main summary embed."""
        color = self.COLOR_DRY_RUN if result.is_dry_run else self.COLOR_SUCCESS

        title = self.build_title(result)
        description = self.build_summary(result)

        fields = []

        # Add movie count if any
        if result.deleted_movies:
            fields.append({
                "name": "Movies",
                "value": str(len(result.deleted_movies)),
                "inline": True,
            })

        # Add show count if any
        if result.deleted_shows:
            fields.append({
                "name": "TV Shows",
                "value": str(len(result.deleted_shows)),
                "inline": True,
            })

        # Add space freed
        fields.append({
            "name": "Space Freed",
            "value": self.format_size(result.total_freed_bytes),
            "inline": True,
        })

        return {
            "title": title,
            "description": description,
            "color": color,
            "fields": fields,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _build_deleted_embed(self, result: RunResult) -> dict:
        """Build embed for deleted items."""
        lines = []

        if result.deleted_movies:
            lines.append("**Movies:**")
            for item in result.deleted_movies[:5]:
                lines.append(f"• {item.format_title()} - {self.format_size(item.size_bytes)}")
            if len(result.deleted_movies) > 5:
                lines.append(f"*...and {len(result.deleted_movies) - 5} more*")

        if result.deleted_shows:
            if lines:
                lines.append("")
            lines.append("**TV Shows:**")
            for item in result.deleted_shows[:5]:
                lines.append(f"• {item.format_title()} - {self.format_size(item.size_bytes)}")
            if len(result.deleted_shows) > 5:
                lines.append(f"*...and {len(result.deleted_shows) - 5} more*")

        return {
            "title": "Deleted Items",
            "description": "\n".join(lines),
            "color": self.COLOR_SUCCESS if not result.is_dry_run else self.COLOR_DRY_RUN,
        }

    def _build_preview_embed(self, result: RunResult) -> dict:
        """Build embed for preview items."""
        preview_size = self.format_size(result.total_preview_bytes)
        lines = [f"*{len(result.preview_items)} items, {preview_size}*", ""]

        deletion_date_str = getattr(result, "deletion_date_str", None)
        if deletion_date_str:
            lines.append(f"**Removal date: {deletion_date_str}**")
            lines.append("")

        for item in result.preview_items[:5]:
            lines.append(f"• {item.format_title()} - {self.format_size(item.size_bytes)}")

        if len(result.preview_items) > 5:
            lines.append(f"*...and {len(result.preview_items) - 5} more*")

        return {
            "title": "Next Scheduled Deletions",
            "description": "\n".join(lines),
            "color": self.COLOR_WARNING,
        }
