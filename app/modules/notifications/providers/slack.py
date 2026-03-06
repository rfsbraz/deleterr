# encoding: utf-8
"""Slack webhook notification provider."""

from typing import Optional

import requests

from app import logger
from app.modules.notifications.base import BaseNotificationProvider
from app.modules.notifications.models import RunResult


class SlackProvider(BaseNotificationProvider):
    """Slack webhook notification provider with Block Kit support."""

    @property
    def name(self) -> str:
        return "slack"

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("webhook_url"))

    def send(self, result: RunResult) -> bool:
        """Send notification via Slack webhook."""
        if not self.enabled:
            return False

        try:
            channel = self.config.get("channel")
            username = self.config.get("username", "Deleterr")
            icon_emoji = self.config.get("icon_emoji", ":wastebasket:")

            payload = self._build_payload(result, channel, username, icon_emoji)

            response = requests.post(
                self.config.get("webhook_url"),
                json=payload,
                timeout=30,
            )
            response.raise_for_status()

            # Slack returns "ok" for successful requests
            return response.text == "ok"

        except requests.exceptions.RequestException as e:
            logger.error(f"Slack notification failed: {e}")
            return False

    def test_connection(self) -> bool:
        """Test Slack webhook connection."""
        if not self.enabled:
            return False

        try:
            response = requests.post(
                self.config.get("webhook_url"),
                json={
                    "text": "Deleterr connection test successful!",
                    "username": self.config.get("username", "Deleterr"),
                },
                timeout=30,
            )
            return response.text == "ok"
        except requests.exceptions.RequestException:
            return False

    def _build_payload(
        self,
        result: RunResult,
        channel: Optional[str],
        username: str,
        icon_emoji: str,
    ) -> dict:
        """Build the Slack webhook payload with Block Kit."""
        blocks = []

        # Header block
        blocks.append(self._build_header_block(result))

        # Summary block
        blocks.append(self._build_summary_block(result))

        # Deleted items section
        if result.deleted_items:
            blocks.append({"type": "divider"})
            blocks.extend(self._build_deleted_blocks(result))

        # Preview section
        if result.preview_items:
            blocks.append({"type": "divider"})
            blocks.extend(self._build_preview_blocks(result))

        # Context/footer
        blocks.append(self._build_context_block(result))

        payload = {
            "username": username,
            "icon_emoji": icon_emoji,
            "blocks": blocks,
        }

        if channel:
            payload["channel"] = channel

        return payload

    def _build_header_block(self, result: RunResult) -> dict:
        """Build the header block."""
        title = self.build_title(result)
        return {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": title,
                "emoji": True,
            },
        }

    def _build_summary_block(self, result: RunResult) -> dict:
        """Build the summary section block."""
        deleted_count = len(result.deleted_items)
        freed_size = self.format_size(result.total_freed_bytes)

        movies_count = len(result.deleted_movies)
        shows_count = len(result.deleted_shows)

        parts = []
        if movies_count:
            parts.append(f"*{movies_count}* movies")
        if shows_count:
            parts.append(f"*{shows_count}* TV shows")

        item_summary = " and ".join(parts) if parts else "0 items"

        if result.is_dry_run:
            text = f"Would delete {item_summary}, freeing *{freed_size}*"
        else:
            text = f"Deleted {item_summary}, freed *{freed_size}*"

        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": text,
            },
        }

    def _build_deleted_blocks(self, result: RunResult) -> list[dict]:
        """Build blocks for deleted items."""
        blocks = []

        # Section header
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Deleted Items*",
            },
        })

        # Movies
        if result.deleted_movies:
            lines = ["*Movies:*"]
            for item in result.deleted_movies[:5]:
                lines.append(f"• {item.format_title()} - {self.format_size(item.size_bytes)}")
            if len(result.deleted_movies) > 5:
                lines.append(f"_...and {len(result.deleted_movies) - 5} more_")

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "\n".join(lines),
                },
            })

        # TV Shows
        if result.deleted_shows:
            lines = ["*TV Shows:*"]
            for item in result.deleted_shows[:5]:
                lines.append(f"• {item.format_title()} - {self.format_size(item.size_bytes)}")
            if len(result.deleted_shows) > 5:
                lines.append(f"_...and {len(result.deleted_shows) - 5} more_")

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "\n".join(lines),
                },
            })

        return blocks

    def _build_preview_blocks(self, result: RunResult) -> list[dict]:
        """Build blocks for preview items."""
        blocks = []

        preview_size = self.format_size(result.total_preview_bytes)
        preview_count = len(result.preview_items)

        deletion_date_str = getattr(result, "deletion_date_str", None)
        if deletion_date_str:
            header_text = f"*Next Scheduled Deletions* ({preview_count} items, {preview_size}) - Removal date: *{deletion_date_str}*"
        else:
            header_text = f"*Next Scheduled Deletions* ({preview_count} items, {preview_size})"

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": header_text,
            },
        })

        lines = []
        for item in result.preview_items[:5]:
            lines.append(f"• {item.format_title()} - {self.format_size(item.size_bytes)}")

        if len(result.preview_items) > 5:
            lines.append(f"_...and {len(result.preview_items) - 5} more_")

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(lines),
            },
        })

        return blocks

    def _build_context_block(self, result: RunResult) -> dict:
        """Build the context/footer block."""
        mode = "Dry Run" if result.is_dry_run else "Live"
        return {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Deleterr • {mode} Mode",
                },
            ],
        }
