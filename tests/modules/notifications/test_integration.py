# encoding: utf-8
"""Integration tests for notification providers."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from app.modules.notifications.manager import NotificationManager
from app.modules.notifications.models import DeletedItem, RunResult
from app.modules.notifications.providers.discord import DiscordProvider
from app.modules.notifications.providers.slack import SlackProvider
from app.modules.notifications.providers.telegram import TelegramProvider
from app.modules.notifications.providers.webhook import WebhookProvider


def create_full_run_result():
    """Create a comprehensive test RunResult with various items."""
    result = RunResult(is_dry_run=False)

    # Add deleted movies
    result.add_deleted(
        DeletedItem(
            title="The Matrix",
            year=1999,
            media_type="movie",
            size_bytes=8 * 1024 * 1024 * 1024,  # 8 GB
            library_name="Movies",
            instance_name="Radarr",
        )
    )
    result.add_deleted(
        DeletedItem(
            title="Inception",
            year=2010,
            media_type="movie",
            size_bytes=12 * 1024 * 1024 * 1024,  # 12 GB
            library_name="Movies",
            instance_name="Radarr",
        )
    )

    # Add deleted shows
    result.add_deleted(
        DeletedItem(
            title="Breaking Bad",
            year=2008,
            media_type="show",
            size_bytes=50 * 1024 * 1024 * 1024,  # 50 GB
            library_name="TV Shows",
            instance_name="Sonarr",
        )
    )

    # Add preview items
    result.add_preview(
        DeletedItem(
            title="Interstellar",
            year=2014,
            media_type="movie",
            size_bytes=15 * 1024 * 1024 * 1024,  # 15 GB
            library_name="Movies",
            instance_name="Radarr",
        )
    )

    return result


@pytest.mark.integration
class TestWebhookProviderIntegration:
    """Integration tests for WebhookProvider with real HTTP mocking."""

    @patch("app.modules.notifications.providers.webhook.requests.request")
    def test_full_payload_structure(self, mock_request):
        """Test that the full payload is correctly structured and sent."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        provider = WebhookProvider({
            "url": "https://example.com/webhook",
            "method": "POST",
            "headers": {"X-Custom-Header": "test-value"},
        })
        result = create_full_run_result()

        success = provider.send(result)

        assert success is True

        # Verify request structure
        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["url"] == "https://example.com/webhook"
        assert call_kwargs["headers"]["X-Custom-Header"] == "test-value"
        assert call_kwargs["headers"]["Content-Type"] == "application/json"

        # Verify payload structure
        payload = call_kwargs["json"]
        assert payload["type"] == "deleterr_run_complete"
        assert payload["is_dry_run"] is False
        assert payload["summary"]["deleted_count"] == 3
        assert payload["summary"]["preview_count"] == 1
        assert len(payload["deleted"]["movies"]) == 2
        assert len(payload["deleted"]["shows"]) == 1
        assert len(payload["preview"]["movies"]) == 1

    @patch("app.modules.notifications.providers.webhook.requests.request")
    def test_connection_timeout_handling(self, mock_request):
        """Test that connection timeouts are handled gracefully."""
        mock_request.side_effect = requests.exceptions.ConnectTimeout("Connection timed out")

        provider = WebhookProvider({"url": "https://example.com/webhook"})
        result = create_full_run_result()

        success = provider.send(result)

        assert success is False

    @patch("app.modules.notifications.providers.webhook.requests.request")
    def test_http_error_handling(self, mock_request):
        """Test that HTTP errors are handled gracefully."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_request.return_value = mock_response

        provider = WebhookProvider({"url": "https://example.com/webhook"})
        result = create_full_run_result()

        success = provider.send(result)

        assert success is False


@pytest.mark.integration
class TestDiscordProviderIntegration:
    """Integration tests for DiscordProvider."""

    @patch("app.modules.notifications.providers.discord.requests.post")
    def test_discord_embed_structure(self, mock_post):
        """Test that Discord embeds are correctly structured."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        provider = DiscordProvider({
            "webhook_url": "https://discord.com/api/webhooks/test",
            "username": "Deleterr",
            "avatar_url": "https://example.com/avatar.png",
        })
        result = create_full_run_result()

        success = provider.send(result)

        assert success is True

        # Verify Discord payload structure
        call_kwargs = mock_post.call_args[1]
        payload = call_kwargs["json"]
        assert payload["username"] == "Deleterr"
        assert payload["avatar_url"] == "https://example.com/avatar.png"
        assert "embeds" in payload
        assert len(payload["embeds"]) >= 1

        # Check main embed
        main_embed = payload["embeds"][0]
        assert "title" in main_embed
        assert "description" in main_embed
        assert "color" in main_embed
        assert "fields" in main_embed

    @patch("app.modules.notifications.providers.discord.requests.post")
    def test_discord_dry_run_indicator(self, mock_post):
        """Test that dry run is clearly indicated in Discord messages."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        provider = DiscordProvider({"webhook_url": "https://discord.com/api/webhooks/test"})
        result = RunResult(is_dry_run=True)
        result.add_deleted(
            DeletedItem("Test Movie", 2020, "movie", 1000000000, "Movies", "Radarr")
        )

        provider.send(result)

        call_kwargs = mock_post.call_args[1]
        payload = call_kwargs["json"]
        main_embed = payload["embeds"][0]

        # Dry run should be indicated in title or description
        title_and_desc = main_embed.get("title", "") + main_embed.get("description", "")
        assert "DRY RUN" in title_and_desc.upper() or "DRY-RUN" in title_and_desc.upper()


@pytest.mark.integration
class TestSlackProviderIntegration:
    """Integration tests for SlackProvider."""

    @patch("app.modules.notifications.providers.slack.requests.post")
    def test_slack_block_kit_structure(self, mock_post):
        """Test that Slack Block Kit blocks are correctly structured."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.text = "ok"
        mock_post.return_value = mock_response

        provider = SlackProvider({
            "webhook_url": "https://hooks.slack.com/services/test",
            "channel": "#deleterr",
            "username": "Deleterr Bot",
            "icon_emoji": ":wastebasket:",
        })
        result = create_full_run_result()

        success = provider.send(result)

        assert success is True

        # Verify Slack payload structure
        call_kwargs = mock_post.call_args[1]
        payload = call_kwargs["json"]
        assert payload["channel"] == "#deleterr"
        assert payload["username"] == "Deleterr Bot"
        assert payload["icon_emoji"] == ":wastebasket:"
        assert "blocks" in payload
        assert len(payload["blocks"]) >= 1

    @patch("app.modules.notifications.providers.slack.requests.post")
    def test_slack_error_response_handling(self, mock_post):
        """Test that Slack error responses are handled correctly."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.text = "channel_not_found"  # Slack error
        mock_post.return_value = mock_response

        provider = SlackProvider({"webhook_url": "https://hooks.slack.com/services/test"})
        result = create_full_run_result()

        success = provider.send(result)

        assert success is False


@pytest.mark.integration
class TestTelegramProviderIntegration:
    """Integration tests for TelegramProvider."""

    @patch("app.modules.notifications.providers.telegram.requests.post")
    def test_telegram_markdown_formatting(self, mock_post):
        """Test that Telegram messages use correct MarkdownV2 formatting."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_post.return_value = mock_response

        provider = TelegramProvider({
            "bot_token": "123456:ABC-DEF",
            "chat_id": "-1001234567890",
        })
        result = create_full_run_result()

        success = provider.send(result)

        assert success is True

        # Verify API call
        call_args = mock_post.call_args
        assert "123456:ABC-DEF" in call_args[0][0]  # URL contains bot token

        # Verify payload
        call_kwargs = call_args[1]
        payload = call_kwargs["json"]
        assert payload["chat_id"] == "-1001234567890"
        assert payload["parse_mode"] == "MarkdownV2"
        assert "text" in payload

    @patch("app.modules.notifications.providers.telegram.requests.post")
    def test_telegram_special_character_escaping(self, mock_post):
        """Test that special characters are escaped for MarkdownV2."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_post.return_value = mock_response

        provider = TelegramProvider({
            "bot_token": "123456:ABC",
            "chat_id": "456",
        })

        # Create result with special characters
        result = RunResult(is_dry_run=False)
        result.add_deleted(
            DeletedItem(
                title="Test (2020) - Special.Characters!",
                year=2020,
                media_type="movie",
                size_bytes=1000000000,
                library_name="Movies",
                instance_name="Radarr",
            )
        )

        provider.send(result)

        call_kwargs = mock_post.call_args[1]
        text = call_kwargs["json"]["text"]

        # Special characters should be escaped
        assert "\\(" in text or "(" not in text or text.count("\\(") == text.count("(")

    @patch("app.modules.notifications.providers.telegram.requests.post")
    def test_telegram_api_error_handling(self, mock_post):
        """Test that Telegram API errors are handled correctly."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "ok": False,
            "error_code": 400,
            "description": "Bad Request: chat not found",
        }
        mock_post.return_value = mock_response

        provider = TelegramProvider({
            "bot_token": "123456:ABC",
            "chat_id": "invalid",
        })
        result = create_full_run_result()

        success = provider.send(result)

        assert success is False


@pytest.mark.integration
class TestNotificationManagerIntegration:
    """Integration tests for NotificationManager with multiple providers."""

    @patch("app.modules.notifications.providers.webhook.requests.request")
    @patch("app.modules.notifications.providers.discord.requests.post")
    def test_multiple_providers_all_succeed(self, mock_discord_post, mock_webhook_request):
        """Test sending to multiple providers when all succeed."""
        # Setup webhook mock
        mock_webhook_response = MagicMock()
        mock_webhook_response.raise_for_status = MagicMock()
        mock_webhook_request.return_value = mock_webhook_response

        # Setup discord mock
        mock_discord_response = MagicMock()
        mock_discord_response.raise_for_status = MagicMock()
        mock_discord_post.return_value = mock_discord_response

        mock_config = MagicMock()
        mock_config.settings = {
            "notifications": {
                "enabled": True,
                "webhook": {"url": "https://example.com/webhook"},
                "discord": {"webhook_url": "https://discord.com/api/webhooks/test"},
            }
        }

        manager = NotificationManager(mock_config)
        result = create_full_run_result()

        success = manager.send_run_summary(result)

        assert success is True
        assert mock_webhook_request.call_count == 1
        assert mock_discord_post.call_count == 1

    @patch("app.modules.notifications.providers.webhook.requests.request")
    @patch("app.modules.notifications.providers.discord.requests.post")
    def test_multiple_providers_partial_failure(self, mock_discord_post, mock_webhook_request):
        """Test sending to multiple providers when one fails."""
        # Setup webhook to succeed
        mock_webhook_response = MagicMock()
        mock_webhook_response.raise_for_status = MagicMock()
        mock_webhook_request.return_value = mock_webhook_response

        # Setup discord to fail
        mock_discord_post.side_effect = requests.exceptions.RequestException("Discord error")

        mock_config = MagicMock()
        mock_config.settings = {
            "notifications": {
                "enabled": True,
                "webhook": {"url": "https://example.com/webhook"},
                "discord": {"webhook_url": "https://discord.com/api/webhooks/test"},
            }
        }

        manager = NotificationManager(mock_config)
        result = create_full_run_result()

        # Should return True because at least one provider succeeded
        success = manager.send_run_summary(result)

        assert success is True
        # Both should have been called
        assert mock_webhook_request.call_count == 1
        assert mock_discord_post.call_count == 1

    @patch("app.modules.notifications.providers.webhook.requests.request")
    @patch("app.modules.notifications.providers.discord.requests.post")
    def test_multiple_providers_all_fail(self, mock_discord_post, mock_webhook_request):
        """Test sending to multiple providers when all fail."""
        # Setup both to fail
        mock_webhook_request.side_effect = requests.exceptions.RequestException("Webhook error")
        mock_discord_post.side_effect = requests.exceptions.RequestException("Discord error")

        mock_config = MagicMock()
        mock_config.settings = {
            "notifications": {
                "enabled": True,
                "webhook": {"url": "https://example.com/webhook"},
                "discord": {"webhook_url": "https://discord.com/api/webhooks/test"},
            }
        }

        manager = NotificationManager(mock_config)
        result = create_full_run_result()

        # Should return False because all providers failed
        success = manager.send_run_summary(result)

        assert success is False
        # Both should have been called
        assert mock_webhook_request.call_count == 1
        assert mock_discord_post.call_count == 1

    def test_notification_filtering_dry_run(self):
        """Test that dry run notifications are filtered based on config."""
        mock_config = MagicMock()
        mock_config.settings = {
            "notifications": {
                "enabled": True,
                "notify_on_dry_run": False,
                "webhook": {"url": "https://example.com/webhook"},
            }
        }

        manager = NotificationManager(mock_config)
        result = RunResult(is_dry_run=True)
        result.add_deleted(
            DeletedItem("Test Movie", 2020, "movie", 1000000000, "Movies", "Radarr")
        )

        should_notify = manager.should_notify(result)

        assert should_notify is False

    def test_notification_filtering_min_deletions(self):
        """Test that notifications are filtered based on minimum deletions."""
        mock_config = MagicMock()
        mock_config.settings = {
            "notifications": {
                "enabled": True,
                "min_deletions_to_notify": 5,
                "webhook": {"url": "https://example.com/webhook"},
            }
        }

        manager = NotificationManager(mock_config)
        result = RunResult(is_dry_run=False)
        result.add_deleted(
            DeletedItem("Test Movie", 2020, "movie", 1000000000, "Movies", "Radarr")
        )

        should_notify = manager.should_notify(result)

        assert should_notify is False

    def test_notification_filtering_preview_only(self):
        """Test that preview-only results respect include_preview setting."""
        # Test with include_preview = False
        mock_config = MagicMock()
        mock_config.settings = {
            "notifications": {
                "enabled": True,
                "include_preview": False,
                "webhook": {"url": "https://example.com/webhook"},
            }
        }

        manager = NotificationManager(mock_config)
        result = RunResult(is_dry_run=False)
        result.add_preview(
            DeletedItem("Preview Movie", 2021, "movie", 2000000000, "Movies", "Radarr")
        )

        should_notify = manager.should_notify(result)
        assert should_notify is False

        # Test with include_preview = True
        mock_config.settings["notifications"]["include_preview"] = True
        manager = NotificationManager(mock_config)

        should_notify = manager.should_notify(result)
        assert should_notify is True


@pytest.mark.integration
class TestProviderConnectionTests:
    """Integration tests for provider connection testing."""

    @patch("app.modules.notifications.providers.webhook.requests.request")
    def test_webhook_test_connection(self, mock_request):
        """Test webhook connection testing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        provider = WebhookProvider({"url": "https://example.com/webhook"})
        result = provider.test_connection()

        assert result is True

    @patch("app.modules.notifications.providers.telegram.requests.get")
    def test_telegram_test_connection(self, mock_get):
        """Test Telegram bot connection testing."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_get.return_value = mock_response

        provider = TelegramProvider({
            "bot_token": "123456:ABC",
            "chat_id": "456",
        })
        result = provider.test_connection()

        assert result is True
        # Should call getMe endpoint
        assert "getMe" in mock_get.call_args[0][0]

    @patch("app.modules.notifications.providers.telegram.requests.get")
    def test_telegram_test_connection_failure(self, mock_get):
        """Test Telegram bot connection testing with invalid token."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": False,
            "error_code": 401,
            "description": "Unauthorized",
        }
        mock_get.return_value = mock_response

        provider = TelegramProvider({
            "bot_token": "invalid_token",
            "chat_id": "456",
        })
        result = provider.test_connection()

        assert result is False
