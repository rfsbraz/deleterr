# encoding: utf-8
"""Tests for notification providers."""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.notifications.models import DeletedItem, RunResult
from app.modules.notifications.providers.webhook import WebhookProvider
from app.modules.notifications.providers.discord import DiscordProvider
from app.modules.notifications.providers.email import EmailProvider
from app.modules.notifications.providers.slack import SlackProvider
from app.modules.notifications.providers.telegram import TelegramProvider


def create_test_result(
    is_dry_run=True,
    deleted_movies=0,
    deleted_shows=0,
    preview_movies=0,
    preview_shows=0,
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

    for i in range(preview_shows):
        result.add_preview(
            DeletedItem(f"Preview Show {i+1}", 2019 + i, "show", 3000000000 * (i + 1), "TV Shows", "Sonarr")
        )

    return result


@pytest.mark.unit
class TestWebhookProvider:
    """Tests for WebhookProvider."""

    def test_is_enabled_with_url(self):
        """Test provider is enabled when URL is configured."""
        provider = WebhookProvider({"url": "https://example.com/webhook"})
        assert provider.enabled is True

    def test_is_enabled_without_url(self):
        """Test provider is disabled when URL is not configured."""
        provider = WebhookProvider({})
        assert provider.enabled is False

    def test_is_enabled_with_empty_url(self):
        """Test provider is disabled when URL is empty."""
        provider = WebhookProvider({"url": ""})
        assert provider.enabled is False

    def test_name(self):
        """Test provider name."""
        provider = WebhookProvider({})
        assert provider.name == "webhook"

    @patch("app.modules.notifications.providers.webhook.requests.request")
    def test_send_success(self, mock_request):
        """Test successful webhook send."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        provider = WebhookProvider({"url": "https://example.com/webhook"})
        result = create_test_result(deleted_movies=2, deleted_shows=1)

        success = provider.send(result)

        assert success is True
        mock_request.assert_called_once()

        # Verify the call arguments
        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["url"] == "https://example.com/webhook"
        assert "json" in call_kwargs

    @patch("app.modules.notifications.providers.webhook.requests.request")
    def test_send_failure(self, mock_request):
        """Test failed webhook send."""
        import requests as req
        mock_request.side_effect = req.exceptions.RequestException("Connection error")

        provider = WebhookProvider({"url": "https://example.com/webhook"})
        result = create_test_result(deleted_movies=1)

        success = provider.send(result)

        assert success is False

    def test_send_disabled(self):
        """Test send returns False when provider is disabled."""
        provider = WebhookProvider({})
        result = create_test_result(deleted_movies=1)

        success = provider.send(result)

        assert success is False

    @patch("app.modules.notifications.providers.webhook.requests.request")
    def test_custom_method(self, mock_request):
        """Test custom HTTP method."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        provider = WebhookProvider({"url": "https://example.com/webhook", "method": "PUT"})
        result = create_test_result(deleted_movies=1)

        provider.send(result)

        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["method"] == "PUT"

    @patch("app.modules.notifications.providers.webhook.requests.request")
    def test_custom_headers(self, mock_request):
        """Test custom headers."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        provider = WebhookProvider({
            "url": "https://example.com/webhook",
            "headers": {"Authorization": "Bearer token123"},
        })
        result = create_test_result(deleted_movies=1)

        provider.send(result)

        call_kwargs = mock_request.call_args[1]
        assert "Authorization" in call_kwargs["headers"]
        assert call_kwargs["headers"]["Authorization"] == "Bearer token123"

    def test_build_payload_structure(self):
        """Test webhook payload structure."""
        provider = WebhookProvider({"url": "https://example.com/webhook"})
        result = create_test_result(
            is_dry_run=True,
            deleted_movies=2,
            deleted_shows=1,
            preview_movies=1,
        )

        payload = provider._build_payload(result)

        assert payload["type"] == "deleterr_run_complete"
        assert payload["is_dry_run"] is True
        assert "timestamp" in payload
        assert "summary" in payload
        assert payload["summary"]["deleted_count"] == 3
        assert "deleted" in payload
        assert len(payload["deleted"]["movies"]) == 2
        assert len(payload["deleted"]["shows"]) == 1
        assert "preview" in payload
        assert len(payload["preview"]["movies"]) == 1


@pytest.mark.unit
class TestDiscordProvider:
    """Tests for DiscordProvider."""

    def test_is_enabled_with_webhook_url(self):
        """Test provider is enabled when webhook URL is configured."""
        provider = DiscordProvider({"webhook_url": "https://discord.com/api/webhooks/..."})
        assert provider.enabled is True

    def test_is_enabled_without_webhook_url(self):
        """Test provider is disabled when webhook URL is not configured."""
        provider = DiscordProvider({})
        assert provider.enabled is False

    def test_name(self):
        """Test provider name."""
        provider = DiscordProvider({})
        assert provider.name == "discord"

    @patch("app.modules.notifications.providers.discord.requests.post")
    def test_send_success(self, mock_post):
        """Test successful Discord send."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        provider = DiscordProvider({"webhook_url": "https://discord.com/api/webhooks/..."})
        result = create_test_result(deleted_movies=2, deleted_shows=1)

        success = provider.send(result)

        assert success is True
        mock_post.assert_called_once()

    @patch("app.modules.notifications.providers.discord.requests.post")
    def test_send_failure(self, mock_post):
        """Test failed Discord send."""
        import requests as req
        mock_post.side_effect = req.exceptions.RequestException("Connection error")

        provider = DiscordProvider({"webhook_url": "https://discord.com/api/webhooks/..."})
        result = create_test_result(deleted_movies=1)

        success = provider.send(result)

        assert success is False

    @patch("app.modules.notifications.providers.discord.requests.post")
    def test_custom_username(self, mock_post):
        """Test custom username."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        provider = DiscordProvider({
            "webhook_url": "https://discord.com/api/webhooks/...",
            "username": "MyBot",
        })
        result = create_test_result(deleted_movies=1)

        provider.send(result)

        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["username"] == "MyBot"

    def test_build_payload_embeds(self):
        """Test Discord payload has embeds."""
        provider = DiscordProvider({"webhook_url": "https://discord.com/api/webhooks/..."})
        result = create_test_result(deleted_movies=2, preview_movies=1)

        payload = provider._build_payload(result, "Deleterr", None)

        assert "embeds" in payload
        assert len(payload["embeds"]) >= 1  # At least main embed
        assert payload["username"] == "Deleterr"


@pytest.mark.unit
class TestSlackProvider:
    """Tests for SlackProvider."""

    def test_is_enabled_with_webhook_url(self):
        """Test provider is enabled when webhook URL is configured."""
        provider = SlackProvider({"webhook_url": "https://hooks.slack.com/services/..."})
        assert provider.enabled is True

    def test_is_enabled_without_webhook_url(self):
        """Test provider is disabled when webhook URL is not configured."""
        provider = SlackProvider({})
        assert provider.enabled is False

    def test_name(self):
        """Test provider name."""
        provider = SlackProvider({})
        assert provider.name == "slack"

    @patch("app.modules.notifications.providers.slack.requests.post")
    def test_send_success(self, mock_post):
        """Test successful Slack send."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.text = "ok"
        mock_post.return_value = mock_response

        provider = SlackProvider({"webhook_url": "https://hooks.slack.com/services/..."})
        result = create_test_result(deleted_movies=2)

        success = provider.send(result)

        assert success is True
        mock_post.assert_called_once()

    @patch("app.modules.notifications.providers.slack.requests.post")
    def test_send_not_ok(self, mock_post):
        """Test Slack send with non-ok response."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.text = "invalid_token"
        mock_post.return_value = mock_response

        provider = SlackProvider({"webhook_url": "https://hooks.slack.com/services/..."})
        result = create_test_result(deleted_movies=1)

        success = provider.send(result)

        assert success is False

    @patch("app.modules.notifications.providers.slack.requests.post")
    def test_custom_channel(self, mock_post):
        """Test custom channel."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.text = "ok"
        mock_post.return_value = mock_response

        provider = SlackProvider({
            "webhook_url": "https://hooks.slack.com/services/...",
            "channel": "#media-cleanup",
        })
        result = create_test_result(deleted_movies=1)

        provider.send(result)

        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["channel"] == "#media-cleanup"

    def test_build_payload_blocks(self):
        """Test Slack payload has blocks."""
        provider = SlackProvider({"webhook_url": "https://hooks.slack.com/services/..."})
        result = create_test_result(deleted_movies=2)

        payload = provider._build_payload(result, None, "Deleterr", ":wastebasket:")

        assert "blocks" in payload
        assert len(payload["blocks"]) >= 1
        assert payload["username"] == "Deleterr"


@pytest.mark.unit
class TestTelegramProvider:
    """Tests for TelegramProvider."""

    def test_is_enabled_with_both_required(self):
        """Test provider is enabled when both bot_token and chat_id are configured."""
        provider = TelegramProvider({"bot_token": "123:ABC", "chat_id": "456"})
        assert provider.enabled is True

    def test_is_enabled_without_bot_token(self):
        """Test provider is disabled when bot_token is missing."""
        provider = TelegramProvider({"chat_id": "456"})
        assert provider.enabled is False

    def test_is_enabled_without_chat_id(self):
        """Test provider is disabled when chat_id is missing."""
        provider = TelegramProvider({"bot_token": "123:ABC"})
        assert provider.enabled is False

    def test_name(self):
        """Test provider name."""
        provider = TelegramProvider({})
        assert provider.name == "telegram"

    @patch("app.modules.notifications.providers.telegram.requests.post")
    def test_send_success(self, mock_post):
        """Test successful Telegram send."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_post.return_value = mock_response

        provider = TelegramProvider({"bot_token": "123:ABC", "chat_id": "456"})
        result = create_test_result(deleted_movies=2)

        success = provider.send(result)

        assert success is True
        mock_post.assert_called_once()

    @patch("app.modules.notifications.providers.telegram.requests.post")
    def test_send_api_error(self, mock_post):
        """Test Telegram send with API error."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"ok": False, "description": "Bad Request"}
        mock_post.return_value = mock_response

        provider = TelegramProvider({"bot_token": "123:ABC", "chat_id": "456"})
        result = create_test_result(deleted_movies=1)

        success = provider.send(result)

        assert success is False

    def test_escape_markdown(self):
        """Test Telegram markdown escaping."""
        provider = TelegramProvider({})

        escaped = provider._escape_markdown("Test (2020) - 5.5 GB")

        # Should escape special characters
        assert "\\(" in escaped
        assert "\\)" in escaped
        assert "\\-" in escaped
        assert "\\." in escaped

    @patch("app.modules.notifications.providers.telegram.requests.get")
    def test_test_connection_success(self, mock_get):
        """Test successful connection test."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_get.return_value = mock_response

        provider = TelegramProvider({"bot_token": "123:ABC", "chat_id": "456"})

        result = provider.test_connection()

        assert result is True


@pytest.mark.unit
class TestEmailProvider:
    """Tests for EmailProvider."""

    def test_is_enabled_with_required_fields(self):
        """Test provider is enabled when all required fields are configured."""
        provider = EmailProvider({
            "smtp_server": "smtp.example.com",
            "from_address": "test@example.com",
            "to_addresses": ["user@example.com"],
        })
        assert provider.enabled is True

    def test_is_enabled_without_smtp_server(self):
        """Test provider is disabled when smtp_server is missing."""
        provider = EmailProvider({
            "from_address": "test@example.com",
            "to_addresses": ["user@example.com"],
        })
        assert provider.enabled is False

    def test_is_enabled_without_from_address(self):
        """Test provider is disabled when from_address is missing."""
        provider = EmailProvider({
            "smtp_server": "smtp.example.com",
            "to_addresses": ["user@example.com"],
        })
        assert provider.enabled is False

    def test_is_enabled_without_to_addresses(self):
        """Test provider is disabled when to_addresses is missing."""
        provider = EmailProvider({
            "smtp_server": "smtp.example.com",
            "from_address": "test@example.com",
        })
        assert provider.enabled is False

    def test_is_enabled_with_empty_to_addresses(self):
        """Test provider is disabled when to_addresses is empty."""
        provider = EmailProvider({
            "smtp_server": "smtp.example.com",
            "from_address": "test@example.com",
            "to_addresses": [],
        })
        assert provider.enabled is False

    def test_name(self):
        """Test provider name."""
        provider = EmailProvider({})
        assert provider.name == "email"

    @patch("app.modules.notifications.providers.email.smtplib.SMTP")
    def test_send_success(self, mock_smtp_class):
        """Test successful email send."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        provider = EmailProvider({
            "smtp_server": "smtp.example.com",
            "smtp_port": 587,
            "from_address": "test@example.com",
            "to_addresses": ["user@example.com"],
            "use_tls": True,
        })
        result = create_test_result(deleted_movies=2, deleted_shows=1)

        success = provider.send(result)

        assert success is True
        mock_smtp.starttls.assert_called_once()
        mock_smtp.sendmail.assert_called_once()
        mock_smtp.quit.assert_called_once()

    @patch("app.modules.notifications.providers.email.smtplib.SMTP")
    def test_send_with_auth(self, mock_smtp_class):
        """Test email send with authentication."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        provider = EmailProvider({
            "smtp_server": "smtp.example.com",
            "smtp_username": "user",
            "smtp_password": "pass",
            "from_address": "test@example.com",
            "to_addresses": ["user@example.com"],
        })
        result = create_test_result(deleted_movies=1)

        provider.send(result)

        mock_smtp.login.assert_called_once_with("user", "pass")

    @patch("app.modules.notifications.providers.email.smtplib.SMTP_SSL")
    def test_send_with_ssl(self, mock_smtp_ssl_class):
        """Test email send with SSL."""
        mock_smtp = MagicMock()
        mock_smtp_ssl_class.return_value = mock_smtp

        provider = EmailProvider({
            "smtp_server": "smtp.example.com",
            "smtp_port": 465,
            "from_address": "test@example.com",
            "to_addresses": ["user@example.com"],
            "use_ssl": True,
            "use_tls": False,
        })
        result = create_test_result(deleted_movies=1)

        success = provider.send(result)

        assert success is True
        mock_smtp_ssl_class.assert_called_once()

    @patch("app.modules.notifications.providers.email.smtplib.SMTP")
    def test_send_failure(self, mock_smtp_class):
        """Test failed email send."""
        mock_smtp_class.side_effect = Exception("Connection failed")

        provider = EmailProvider({
            "smtp_server": "smtp.example.com",
            "from_address": "test@example.com",
            "to_addresses": ["user@example.com"],
        })
        result = create_test_result(deleted_movies=1)

        success = provider.send(result)

        assert success is False

    def test_send_disabled(self):
        """Test send returns False when provider is disabled."""
        provider = EmailProvider({})
        result = create_test_result(deleted_movies=1)

        success = provider.send(result)

        assert success is False

    def test_build_run_summary_html_contains_items(self):
        """Test that HTML summary contains deleted items."""
        provider = EmailProvider({
            "smtp_server": "smtp.example.com",
            "from_address": "test@example.com",
            "to_addresses": ["user@example.com"],
        })
        result = create_test_result(deleted_movies=2, deleted_shows=1)

        html = provider._build_run_summary_html(result)

        assert "Movie 1" in html
        assert "Movie 2" in html
        assert "Show 1" in html
        assert "Deleted Movies" in html
        assert "Deleted TV Shows" in html

    def test_build_run_summary_text_contains_items(self):
        """Test that plain text summary contains deleted items."""
        provider = EmailProvider({
            "smtp_server": "smtp.example.com",
            "from_address": "test@example.com",
            "to_addresses": ["user@example.com"],
        })
        result = create_test_result(deleted_movies=1, deleted_shows=1)

        text = provider._build_run_summary_text(result)

        assert "Movie 1" in text
        assert "Show 1" in text

    @patch("app.modules.notifications.providers.email.smtplib.SMTP")
    def test_send_leaving_soon_success(self, mock_smtp_class):
        """Test successful leaving soon email send."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        provider = EmailProvider({
            "smtp_server": "smtp.example.com",
            "from_address": "test@example.com",
            "to_addresses": ["user@example.com"],
        })

        items = [
            DeletedItem("Movie 1", 2020, "movie", 1000000000, "Movies", "Radarr"),
            DeletedItem("Show 1", 2019, "show", 2000000000, "TV Shows", "Sonarr"),
        ]

        success = provider.send_leaving_soon(items)

        assert success is True
        mock_smtp.sendmail.assert_called_once()

    @patch("app.modules.notifications.providers.email.smtplib.SMTP")
    def test_send_leaving_soon_with_context(self, mock_smtp_class):
        """Test leaving soon email with context variables."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        provider = EmailProvider({
            "smtp_server": "smtp.example.com",
            "from_address": "test@example.com",
            "to_addresses": ["user@example.com"],
        })

        items = [
            DeletedItem("Movie 1", 2020, "movie", 1000000000, "Movies", "Radarr"),
        ]

        success = provider.send_leaving_soon(
            items,
            context={
                "plex_url": "http://plex.local:32400",
                "seerr_url": "http://seerr.local:5055",
            },
        )

        assert success is True

    def test_build_leaving_soon_context(self):
        """Test building leaving soon context."""
        provider = EmailProvider({})

        items = [
            DeletedItem("Movie 1", 2020, "movie", 1000000000, "Movies", "Radarr"),
            DeletedItem("Movie 2", 2021, "movie", 2000000000, "Movies", "Radarr"),
            DeletedItem("Show 1", 2019, "show", 3000000000, "TV Shows", "Sonarr"),
        ]

        context = provider._build_leaving_soon_context(items, {"plex_url": "http://test"})

        assert len(context["movies"]) == 2
        assert len(context["shows"]) == 1
        assert context["total_count"] == 3
        assert context["movie_count"] == 2
        assert context["show_count"] == 1
        assert context["plex_url"] == "http://test"

    @patch("app.modules.notifications.providers.email.smtplib.SMTP")
    def test_test_connection_success(self, mock_smtp_class):
        """Test successful connection test."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        provider = EmailProvider({
            "smtp_server": "smtp.example.com",
            "from_address": "test@example.com",
            "to_addresses": ["user@example.com"],
        })

        result = provider.test_connection()

        assert result is True
        mock_smtp.quit.assert_called_once()

    @patch("app.modules.notifications.providers.email.smtplib.SMTP")
    def test_test_connection_failure(self, mock_smtp_class):
        """Test failed connection test."""
        mock_smtp_class.side_effect = Exception("Connection refused")

        provider = EmailProvider({
            "smtp_server": "smtp.example.com",
            "from_address": "test@example.com",
            "to_addresses": ["user@example.com"],
        })

        result = provider.test_connection()

        assert result is False
