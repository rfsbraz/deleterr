# encoding: utf-8
"""Telegram Bot API notification provider."""

import re

import requests

from app import logger
from app.modules.notifications.base import BaseNotificationProvider
from app.modules.notifications.models import RunResult


class TelegramProvider(BaseNotificationProvider):
    """Telegram Bot API notification provider with MarkdownV2 support."""

    API_BASE = "https://api.telegram.org"

    @property
    def name(self) -> str:
        return "telegram"

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("bot_token") and self.config.get("chat_id"))

    def send(self, result: RunResult) -> bool:
        """Send notification via Telegram Bot API."""
        if not self.enabled:
            return False

        try:
            bot_token = self.config.get("bot_token")
            chat_id = self.config.get("chat_id")
            parse_mode = self.config.get("parse_mode", "MarkdownV2")

            message = self._build_message(result)

            url = f"{self.API_BASE}/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": parse_mode,
            }

            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()

            result_json = response.json()
            return result_json.get("ok", False)

        except requests.exceptions.RequestException as e:
            logger.error(f"Telegram notification failed: {e}")
            return False

    def test_connection(self) -> bool:
        """Test Telegram bot connection by calling getMe."""
        if not self.enabled:
            return False

        try:
            bot_token = self.config.get("bot_token")
            url = f"{self.API_BASE}/bot{bot_token}/getMe"

            response = requests.get(url, timeout=30)
            result = response.json()
            return result.get("ok", False)

        except requests.exceptions.RequestException:
            return False

    def _build_message(self, result: RunResult) -> str:
        """Build the Telegram message with MarkdownV2 formatting."""
        lines = []

        # Title
        title = self.build_title(result)
        lines.append(f"*{self._escape_markdown(title)}*")
        lines.append("")

        # Summary
        summary = self.build_summary(result)
        lines.append(self._escape_markdown(summary))
        lines.append("")

        # Deleted items
        if result.deleted_items:
            lines.append("*Deleted Items:*")

            if result.deleted_movies:
                lines.append(f"_Movies \\({len(result.deleted_movies)}\\):_")
                for item in result.deleted_movies[:5]:
                    size = self.format_size(item.size_bytes)
                    lines.append(f"• {self._escape_markdown(item.format_title())} \\- {self._escape_markdown(size)}")
                if len(result.deleted_movies) > 5:
                    lines.append(f"_\\.\\.\\.and {len(result.deleted_movies) - 5} more_")

            if result.deleted_shows:
                lines.append(f"_TV Shows \\({len(result.deleted_shows)}\\):_")
                for item in result.deleted_shows[:5]:
                    size = self.format_size(item.size_bytes)
                    lines.append(f"• {self._escape_markdown(item.format_title())} \\- {self._escape_markdown(size)}")
                if len(result.deleted_shows) > 5:
                    lines.append(f"_\\.\\.\\.and {len(result.deleted_shows) - 5} more_")

            lines.append("")

        # Preview items
        if result.preview_items:
            preview_size = self.format_size(result.total_preview_bytes)
            lines.append(f"*Next Scheduled Deletions* \\({len(result.preview_items)} items, {self._escape_markdown(preview_size)}\\):")

            deletion_date_str = getattr(result, "deletion_date_str", None)
            if deletion_date_str:
                lines.append(f"Removal date: *{self._escape_markdown(deletion_date_str)}*")

            for item in result.preview_items[:5]:
                size = self.format_size(item.size_bytes)
                lines.append(f"• {self._escape_markdown(item.format_title())} \\- {self._escape_markdown(size)}")

            if len(result.preview_items) > 5:
                lines.append(f"_\\.\\.\\.and {len(result.preview_items) - 5} more_")

        return "\n".join(lines)

    def _escape_markdown(self, text: str) -> str:
        """Escape special characters for MarkdownV2."""
        # Characters that need to be escaped in MarkdownV2
        special_chars = r"_*[]()~`>#+-=|{}.!"
        return re.sub(f"([{re.escape(special_chars)}])", r"\\\1", str(text))
