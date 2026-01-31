# encoding: utf-8
"""Generic webhook notification provider."""

from datetime import datetime, timezone

import requests

from app import logger
from app.modules.notifications.base import BaseNotificationProvider
from app.modules.notifications.models import RunResult


class WebhookProvider(BaseNotificationProvider):
    """Generic webhook notification provider."""

    @property
    def name(self) -> str:
        return "webhook"

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("url"))

    def send(self, result: RunResult) -> bool:
        """Send notification via webhook."""
        if not self.enabled:
            return False

        try:
            payload = self._build_payload(result)

            response = requests.request(
                method=self.config.get("method", "POST"),
                url=self.config.get("url"),
                json=payload,
                headers=self._build_headers(),
                timeout=self.config.get("timeout", 30),
            )
            response.raise_for_status()
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Webhook notification failed: {e}")
            return False

    def test_connection(self) -> bool:
        """Test webhook connection with a minimal request."""
        if not self.enabled:
            return False

        try:
            response = requests.request(
                method=self.config.get("method", "POST"),
                url=self.config.get("url"),
                json={"type": "deleterr_test", "message": "Connection test"},
                headers=self._build_headers(),
                timeout=self.config.get("timeout", 30),
            )
            return response.status_code < 500
        except requests.exceptions.RequestException:
            return False

    def _build_headers(self) -> dict:
        """Build request headers."""
        headers = {"Content-Type": "application/json"}
        if custom_headers := self.config.get("headers"):
            headers.update(custom_headers)
        return headers

    def _build_payload(self, result: RunResult) -> dict:
        """Build the webhook payload."""
        payload = {
            "type": "deleterr_run_complete",
            "is_dry_run": result.is_dry_run,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "deleted_count": len(result.deleted_items),
                "preview_count": len(result.preview_items),
                "total_freed_bytes": result.total_freed_bytes,
                "total_freed_formatted": self.format_size(result.total_freed_bytes),
                "total_preview_bytes": result.total_preview_bytes,
                "total_preview_formatted": self.format_size(result.total_preview_bytes),
            },
            "deleted": {
                "movies": [self._format_item(item) for item in result.deleted_movies],
                "shows": [self._format_item(item) for item in result.deleted_shows],
            },
            "preview": {
                "movies": [self._format_item(item) for item in result.preview_movies],
                "shows": [self._format_item(item) for item in result.preview_shows],
            },
        }
        return payload

    def _format_item(self, item) -> dict:
        """Format a DeletedItem for the payload."""
        return {
            "title": item.title,
            "year": item.year,
            "size_bytes": item.size_bytes,
            "size_formatted": self.format_size(item.size_bytes),
            "library": item.library_name,
            "instance": item.instance_name,
        }
