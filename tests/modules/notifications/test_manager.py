# encoding: utf-8
"""Tests for NotificationManager."""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.notifications.manager import NotificationManager
from app.modules.notifications.models import DeletedItem, RunResult


def create_test_result(
    is_dry_run=True,
    deleted_movies=0,
    deleted_shows=0,
    preview_movies=0,
):
    """Helper to create a test RunResult."""
    result = RunResult(is_dry_run=is_dry_run)

    for i in range(deleted_movies):
        result.add_deleted(
            DeletedItem(f"Movie {i+1}", 2020 + i, "movie", 1000000000 * (i + 1), "Movies", "Radarr")
        )

    for i in range(deleted_shows):
        result.add_deleted(
            DeletedItem(f"Show {i+1}", 2018 + i, "show", 5000000000 * (i + 1), "TV Shows", "Sonarr")
        )

    for i in range(preview_movies):
        result.add_preview(
            DeletedItem(f"Preview Movie {i+1}", 2021 + i, "movie", 2000000000 * (i + 1), "Movies", "Radarr")
        )

    return result


@pytest.mark.unit
class TestNotificationManager:
    """Tests for NotificationManager."""

    def test_init_no_notifications_config(self):
        """Test manager initialization with no notifications config."""
        mock_config = MagicMock()
        mock_config.settings = {}

        manager = NotificationManager(mock_config)

        assert manager.providers == []
        assert manager.is_enabled() is False

    def test_init_notifications_disabled(self):
        """Test manager initialization with notifications disabled."""
        mock_config = MagicMock()
        mock_config.settings = {
            "notifications": {
                "enabled": False,
                "webhook": {"url": "https://example.com"},
            }
        }

        manager = NotificationManager(mock_config)

        assert manager.providers == []
        assert manager.is_enabled() is False

    def test_init_with_webhook_provider(self):
        """Test manager initialization with webhook provider."""
        mock_config = MagicMock()
        mock_config.settings = {
            "notifications": {
                "enabled": True,
                "webhook": {"url": "https://example.com"},
            }
        }

        manager = NotificationManager(mock_config)

        assert len(manager.providers) == 1
        assert manager.providers[0].name == "webhook"
        assert manager.is_enabled() is True

    def test_init_with_multiple_providers(self):
        """Test manager initialization with multiple providers."""
        mock_config = MagicMock()
        mock_config.settings = {
            "notifications": {
                "enabled": True,
                "webhook": {"url": "https://example.com"},
                "discord": {"webhook_url": "https://discord.com/api/webhooks/..."},
            }
        }

        manager = NotificationManager(mock_config)

        assert len(manager.providers) == 2
        provider_names = [p.name for p in manager.providers]
        assert "webhook" in provider_names
        assert "discord" in provider_names

    def test_should_notify_dry_run_allowed(self):
        """Test should_notify with dry run allowed."""
        mock_config = MagicMock()
        mock_config.settings = {
            "notifications": {
                "enabled": True,
                "notify_on_dry_run": True,
                "webhook": {"url": "https://example.com"},
            }
        }

        manager = NotificationManager(mock_config)
        result = create_test_result(is_dry_run=True, deleted_movies=1)

        assert manager.should_notify(result) is True

    def test_should_notify_dry_run_not_allowed(self):
        """Test should_notify with dry run not allowed."""
        mock_config = MagicMock()
        mock_config.settings = {
            "notifications": {
                "enabled": True,
                "notify_on_dry_run": False,
                "webhook": {"url": "https://example.com"},
            }
        }

        manager = NotificationManager(mock_config)
        result = create_test_result(is_dry_run=True, deleted_movies=1)

        assert manager.should_notify(result) is False

    def test_should_notify_min_deletions_met(self):
        """Test should_notify when min deletions threshold is met."""
        mock_config = MagicMock()
        mock_config.settings = {
            "notifications": {
                "enabled": True,
                "min_deletions_to_notify": 2,
                "webhook": {"url": "https://example.com"},
            }
        }

        manager = NotificationManager(mock_config)
        result = create_test_result(deleted_movies=3)

        assert manager.should_notify(result) is True

    def test_should_notify_min_deletions_not_met(self):
        """Test should_notify when min deletions threshold is not met."""
        mock_config = MagicMock()
        mock_config.settings = {
            "notifications": {
                "enabled": True,
                "min_deletions_to_notify": 5,
                "webhook": {"url": "https://example.com"},
            }
        }

        manager = NotificationManager(mock_config)
        result = create_test_result(deleted_movies=2)

        assert manager.should_notify(result) is False

    def test_should_notify_no_content(self):
        """Test should_notify with no content to report."""
        mock_config = MagicMock()
        mock_config.settings = {
            "notifications": {
                "enabled": True,
                "include_preview": False,
                "webhook": {"url": "https://example.com"},
            }
        }

        manager = NotificationManager(mock_config)
        result = create_test_result()  # No deleted or preview items

        assert manager.should_notify(result) is False

    def test_should_notify_preview_only(self):
        """Test should_notify with preview items only."""
        mock_config = MagicMock()
        mock_config.settings = {
            "notifications": {
                "enabled": True,
                "include_preview": True,
                "webhook": {"url": "https://example.com"},
            }
        }

        manager = NotificationManager(mock_config)
        result = create_test_result(preview_movies=2)  # Only preview items

        assert manager.should_notify(result) is True

    def test_should_notify_preview_disabled(self):
        """Test should_notify with preview disabled and only preview items."""
        mock_config = MagicMock()
        mock_config.settings = {
            "notifications": {
                "enabled": True,
                "include_preview": False,
                "webhook": {"url": "https://example.com"},
            }
        }

        manager = NotificationManager(mock_config)
        result = create_test_result(preview_movies=2)  # Only preview items

        assert manager.should_notify(result) is False

    @patch("app.modules.notifications.providers.webhook.requests.request")
    def test_send_run_summary_success(self, mock_request):
        """Test send_run_summary sends to all providers."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        mock_config = MagicMock()
        mock_config.settings = {
            "notifications": {
                "enabled": True,
                "webhook": {"url": "https://example.com"},
            }
        }

        manager = NotificationManager(mock_config)
        result = create_test_result(deleted_movies=2)

        success = manager.send_run_summary(result)

        assert success is True
        assert mock_request.call_count == 1

    @patch("app.modules.notifications.providers.webhook.requests.request")
    def test_send_run_summary_provider_failure(self, mock_request):
        """Test send_run_summary handles provider failures."""
        import requests as req
        mock_request.side_effect = req.exceptions.RequestException("Error")

        mock_config = MagicMock()
        mock_config.settings = {
            "notifications": {
                "enabled": True,
                "webhook": {"url": "https://example.com"},
            }
        }

        manager = NotificationManager(mock_config)
        result = create_test_result(deleted_movies=2)

        success = manager.send_run_summary(result)

        assert success is False

    def test_send_run_summary_skipped(self):
        """Test send_run_summary returns False when notification should not be sent."""
        mock_config = MagicMock()
        mock_config.settings = {
            "notifications": {
                "enabled": True,
                "min_deletions_to_notify": 10,
                "webhook": {"url": "https://example.com"},
            }
        }

        manager = NotificationManager(mock_config)
        result = create_test_result(deleted_movies=2)

        success = manager.send_run_summary(result)

        assert success is False

    @patch("app.modules.notifications.providers.webhook.requests.request")
    def test_test_connections(self, mock_request):
        """Test test_connections checks all providers."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        mock_config = MagicMock()
        mock_config.settings = {
            "notifications": {
                "enabled": True,
                "webhook": {"url": "https://example.com"},
            }
        }

        manager = NotificationManager(mock_config)
        results = manager.test_connections()

        assert "webhook" in results
