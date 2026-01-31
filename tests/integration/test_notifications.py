# encoding: utf-8
"""
Integration tests for notification system using real HTTP requests.

These tests verify that notification providers correctly send HTTP requests
with properly formatted payloads by using a mock webhook receiver service.
"""

import pytest
import requests

from app.modules.notifications.models import DeletedItem, RunResult
from app.modules.notifications.providers.webhook import WebhookProvider
from app.modules.notifications.providers.discord import DiscordProvider
from app.modules.notifications.providers.slack import SlackProvider
from app.modules.notifications.manager import NotificationManager


def create_test_result(
    is_dry_run: bool = True,
    movies: int = 2,
    shows: int = 1,
) -> RunResult:
    """Create a RunResult with test data for notification testing."""
    result = RunResult(is_dry_run=is_dry_run)

    for i in range(movies):
        result.add_deleted(
            DeletedItem(
                title=f"Test Movie {i + 1}",
                year=2020 + i,
                media_type="movie",
                size_bytes=(i + 1) * 1024 * 1024 * 1024,  # 1GB, 2GB, etc.
                library_name="Movies",
                instance_name="Radarr",
            )
        )

    for i in range(shows):
        result.add_deleted(
            DeletedItem(
                title=f"Test Show {i + 1}",
                year=2019 + i,
                media_type="show",
                size_bytes=(i + 1) * 500 * 1024 * 1024,  # 500MB, 1GB, etc.
                library_name="TV Shows",
                instance_name="Sonarr",
            )
        )

    return result


@pytest.mark.integration
class TestWebhookProviderIntegration:
    """Integration tests for the generic webhook provider."""

    def test_webhook_receives_correct_payload(self, webhook_helper, webhook_receiver_url):
        """Verify webhook receives full JSON payload via real HTTP."""
        provider = WebhookProvider({"url": f"{webhook_receiver_url}/webhook"})
        result = create_test_result(is_dry_run=True, movies=2, shows=1)

        success = provider.send(result)

        assert success is True

        webhook = webhook_helper.get_latest_webhook()
        assert webhook is not None
        assert webhook["method"] == "POST"
        assert webhook["path"] == "/webhook"

        body = webhook["body"]
        assert body["type"] == "deleterr_run_complete"
        assert body["is_dry_run"] is True
        assert body["summary"]["deleted_count"] == 3
        assert body["summary"]["total_freed_bytes"] > 0
        assert len(body["deleted"]["movies"]) == 2
        assert len(body["deleted"]["shows"]) == 1

    def test_webhook_custom_headers_sent(self, webhook_helper, webhook_receiver_url):
        """Verify custom headers are actually transmitted via HTTP."""
        custom_headers = {
            "X-Custom-Header": "test-value",
            "Authorization": "Bearer test-token-123",
        }
        provider = WebhookProvider({
            "url": f"{webhook_receiver_url}/webhook",
            "headers": custom_headers,
        })
        result = create_test_result(movies=1, shows=0)

        success = provider.send(result)

        assert success is True

        webhook = webhook_helper.get_latest_webhook()
        assert webhook is not None

        headers = webhook["headers"]
        assert headers.get("X-Custom-Header") == "test-value"
        assert headers.get("Authorization") == "Bearer test-token-123"
        assert headers.get("Content-Type") == "application/json"

    def test_webhook_custom_method(self, webhook_helper, webhook_receiver_url):
        """Verify PUT method works instead of POST."""
        provider = WebhookProvider({
            "url": f"{webhook_receiver_url}/webhook",
            "method": "PUT",
        })
        result = create_test_result(movies=1, shows=0)

        success = provider.send(result)

        assert success is True

        webhook = webhook_helper.get_latest_webhook()
        assert webhook is not None
        assert webhook["method"] == "PUT"

    def test_webhook_test_connection(self, webhook_helper, webhook_receiver_url):
        """Verify test_connection sends minimal payload."""
        provider = WebhookProvider({"url": f"{webhook_receiver_url}/webhook"})

        success = provider.test_connection()

        assert success is True

        webhook = webhook_helper.get_latest_webhook()
        assert webhook is not None
        body = webhook["body"]
        assert body["type"] == "deleterr_test"
        assert body["message"] == "Connection test"

    def test_webhook_connection_refused(self, webhook_helper):
        """Verify graceful handling when webhook endpoint is unreachable."""
        provider = WebhookProvider({
            "url": "http://localhost:59999/unreachable",
            "timeout": 1,
        })
        result = create_test_result(movies=1, shows=0)

        success = provider.send(result)

        assert success is False
        assert webhook_helper.get_webhook_count() == 0


@pytest.mark.integration
class TestDiscordProviderIntegration:
    """Integration tests for the Discord webhook provider."""

    def test_discord_embed_format(self, webhook_helper, webhook_receiver_url):
        """Verify Discord webhook sends properly formatted embeds."""
        provider = DiscordProvider({
            "webhook_url": f"{webhook_receiver_url}/discord",
            "username": "Deleterr Test",
        })
        result = create_test_result(is_dry_run=False, movies=2, shows=1)

        success = provider.send(result)

        assert success is True

        webhook = webhook_helper.get_latest_webhook()
        assert webhook is not None
        assert webhook["method"] == "POST"
        assert webhook["path"] == "/discord"

        body = webhook["body"]
        assert body["username"] == "Deleterr Test"
        assert "embeds" in body
        assert len(body["embeds"]) >= 1

        # Verify main embed structure
        main_embed = body["embeds"][0]
        assert "title" in main_embed
        assert "color" in main_embed
        assert "fields" in main_embed
        assert "timestamp" in main_embed

    def test_discord_avatar_url(self, webhook_helper, webhook_receiver_url):
        """Verify avatar_url is included when configured."""
        avatar = "https://example.com/avatar.png"
        provider = DiscordProvider({
            "webhook_url": f"{webhook_receiver_url}/discord",
            "avatar_url": avatar,
        })
        result = create_test_result(movies=1, shows=0)

        success = provider.send(result)

        assert success is True

        webhook = webhook_helper.get_latest_webhook()
        body = webhook["body"]
        assert body.get("avatar_url") == avatar

    def test_discord_dry_run_vs_live(self, webhook_helper, webhook_receiver_url):
        """Verify different colors for dry run vs live mode."""
        provider = DiscordProvider({
            "webhook_url": f"{webhook_receiver_url}/discord",
        })

        # Send dry run
        dry_run_result = create_test_result(is_dry_run=True, movies=1, shows=0)
        provider.send(dry_run_result)
        dry_run_webhook = webhook_helper.get_latest_webhook()
        dry_run_color = dry_run_webhook["body"]["embeds"][0]["color"]

        webhook_helper.reset()

        # Send live
        live_result = create_test_result(is_dry_run=False, movies=1, shows=0)
        provider.send(live_result)
        live_webhook = webhook_helper.get_latest_webhook()
        live_color = live_webhook["body"]["embeds"][0]["color"]

        # Colors should be different (blue for dry run, green for live)
        assert dry_run_color != live_color
        assert dry_run_color == DiscordProvider.COLOR_DRY_RUN
        assert live_color == DiscordProvider.COLOR_SUCCESS


@pytest.mark.integration
class TestSlackProviderIntegration:
    """Integration tests for the Slack webhook provider."""

    def test_slack_blocks_format(self, webhook_helper, webhook_receiver_url):
        """Verify Slack webhook sends properly formatted Block Kit blocks."""
        provider = SlackProvider({
            "webhook_url": f"{webhook_receiver_url}/slack",
            "username": "Deleterr Test",
            "icon_emoji": ":test:",
        })
        result = create_test_result(is_dry_run=True, movies=2, shows=1)

        success = provider.send(result)

        assert success is True

        webhook = webhook_helper.get_latest_webhook()
        assert webhook is not None
        assert webhook["method"] == "POST"
        assert webhook["path"] == "/slack"

        body = webhook["body"]
        assert body["username"] == "Deleterr Test"
        assert body["icon_emoji"] == ":test:"
        assert "blocks" in body
        assert len(body["blocks"]) >= 1

        # Verify header block exists
        block_types = [b["type"] for b in body["blocks"]]
        assert "header" in block_types
        assert "section" in block_types

    def test_slack_channel_override(self, webhook_helper, webhook_receiver_url):
        """Verify channel is included when configured."""
        provider = SlackProvider({
            "webhook_url": f"{webhook_receiver_url}/slack",
            "channel": "#test-channel",
        })
        result = create_test_result(movies=1, shows=0)

        success = provider.send(result)

        assert success is True

        webhook = webhook_helper.get_latest_webhook()
        body = webhook["body"]
        assert body.get("channel") == "#test-channel"

    def test_slack_context_block(self, webhook_helper, webhook_receiver_url):
        """Verify context block contains mode information."""
        provider = SlackProvider({
            "webhook_url": f"{webhook_receiver_url}/slack",
        })
        result = create_test_result(is_dry_run=True, movies=1, shows=0)

        success = provider.send(result)

        assert success is True

        webhook = webhook_helper.get_latest_webhook()
        body = webhook["body"]

        # Find context block
        context_blocks = [b for b in body["blocks"] if b["type"] == "context"]
        assert len(context_blocks) >= 1

        context = context_blocks[0]
        assert "elements" in context
        # Should contain mode info
        context_text = context["elements"][0]["text"]
        assert "Dry Run" in context_text or "Live" in context_text


@pytest.mark.integration
class TestNotificationManagerIntegration:
    """Integration tests for the notification manager with multiple providers."""

    def test_multiple_providers_actual_http(self, webhook_helper, webhook_receiver_url):
        """Verify manager sends to multiple webhook endpoints."""
        # Create a mock config object
        class MockConfig:
            def __init__(self, settings):
                self.settings = settings

        settings = {
            "notifications": {
                "enabled": True,
                "webhook": {
                    "url": f"{webhook_receiver_url}/webhook/endpoint1",
                },
                "discord": {
                    "webhook_url": f"{webhook_receiver_url}/discord/endpoint2",
                },
            }
        }

        config = MockConfig(settings)
        manager = NotificationManager(config)

        assert len(manager.providers) == 2

        result = create_test_result(movies=2, shows=1)
        success = manager.send_run_summary(result)

        assert success is True

        webhooks = webhook_helper.get_all_webhooks()
        assert len(webhooks) == 2

        paths = [w["path"] for w in webhooks]
        assert "/webhook/endpoint1" in paths
        assert "/discord/endpoint2" in paths

    def test_manager_partial_failure(self, webhook_helper, webhook_receiver_url):
        """Verify manager returns True if at least one provider succeeds."""

        class MockConfig:
            def __init__(self, settings):
                self.settings = settings

        settings = {
            "notifications": {
                "enabled": True,
                "webhook": {
                    "url": f"{webhook_receiver_url}/webhook",
                },
                "discord": {
                    # This will fail - unreachable endpoint
                    "webhook_url": "http://localhost:59999/unreachable",
                },
            }
        }

        config = MockConfig(settings)
        manager = NotificationManager(config)

        result = create_test_result(movies=1, shows=0)
        success = manager.send_run_summary(result)

        # Should succeed because at least one provider worked
        assert success is True

        webhooks = webhook_helper.get_all_webhooks()
        assert len(webhooks) == 1
        assert webhooks[0]["path"] == "/webhook"

    def test_manager_test_connections(self, webhook_helper, webhook_receiver_url):
        """Verify test_connections tests all configured providers."""

        class MockConfig:
            def __init__(self, settings):
                self.settings = settings

        settings = {
            "notifications": {
                "enabled": True,
                "webhook": {
                    "url": f"{webhook_receiver_url}/webhook",
                },
                "slack": {
                    "webhook_url": f"{webhook_receiver_url}/slack",
                },
            }
        }

        config = MockConfig(settings)
        manager = NotificationManager(config)

        results = manager.test_connections()

        assert results["webhook"] is True
        assert results["slack"] is True

        # Should have sent test payloads
        webhooks = webhook_helper.get_all_webhooks()
        assert len(webhooks) == 2


@pytest.mark.integration
class TestWebhookPayloadStructure:
    """Integration tests verifying detailed payload structure."""

    def test_deleted_items_structure(self, webhook_helper, webhook_receiver_url):
        """Verify each deleted item has all required fields."""
        provider = WebhookProvider({"url": f"{webhook_receiver_url}/webhook"})
        result = create_test_result(movies=1, shows=1)

        provider.send(result)

        webhook = webhook_helper.get_latest_webhook()
        body = webhook["body"]

        movie = body["deleted"]["movies"][0]
        assert "title" in movie
        assert "year" in movie
        assert "size_bytes" in movie
        assert "size_formatted" in movie
        assert "library" in movie
        assert "instance" in movie

        show = body["deleted"]["shows"][0]
        assert "title" in show
        assert "year" in show
        assert "size_bytes" in show

    def test_summary_calculations(self, webhook_helper, webhook_receiver_url):
        """Verify summary calculations are correct."""
        provider = WebhookProvider({"url": f"{webhook_receiver_url}/webhook"})

        # Create result with known sizes
        result = RunResult(is_dry_run=False)
        result.add_deleted(
            DeletedItem(
                title="Movie 1",
                year=2020,
                media_type="movie",
                size_bytes=1073741824,  # Exactly 1 GB
                library_name="Movies",
                instance_name="Radarr",
            )
        )
        result.add_deleted(
            DeletedItem(
                title="Movie 2",
                year=2021,
                media_type="movie",
                size_bytes=2147483648,  # Exactly 2 GB
                library_name="Movies",
                instance_name="Radarr",
            )
        )

        provider.send(result)

        webhook = webhook_helper.get_latest_webhook()
        body = webhook["body"]

        summary = body["summary"]
        assert summary["deleted_count"] == 2
        assert summary["total_freed_bytes"] == 3221225472  # 3 GB
        assert "3" in summary["total_freed_formatted"]  # Should contain "3"
        assert "GB" in summary["total_freed_formatted"]

    def test_preview_items_included(self, webhook_helper, webhook_receiver_url):
        """Verify preview items are included in payload."""
        provider = WebhookProvider({"url": f"{webhook_receiver_url}/webhook"})

        result = RunResult(is_dry_run=True)
        result.add_deleted(
            DeletedItem(
                title="Deleted Movie",
                year=2020,
                media_type="movie",
                size_bytes=1000000000,
                library_name="Movies",
                instance_name="Radarr",
            )
        )
        result.add_preview(
            DeletedItem(
                title="Preview Movie",
                year=2021,
                media_type="movie",
                size_bytes=2000000000,
                library_name="Movies",
                instance_name="Radarr",
            )
        )

        provider.send(result)

        webhook = webhook_helper.get_latest_webhook()
        body = webhook["body"]

        assert body["summary"]["deleted_count"] == 1
        assert body["summary"]["preview_count"] == 1
        assert len(body["deleted"]["movies"]) == 1
        assert len(body["preview"]["movies"]) == 1
        assert body["preview"]["movies"][0]["title"] == "Preview Movie"

    def test_timestamp_format(self, webhook_helper, webhook_receiver_url):
        """Verify timestamp is in ISO format."""
        provider = WebhookProvider({"url": f"{webhook_receiver_url}/webhook"})
        result = create_test_result(movies=1, shows=0)

        provider.send(result)

        webhook = webhook_helper.get_latest_webhook()
        body = webhook["body"]

        timestamp = body["timestamp"]
        # Should be ISO format with timezone
        assert "T" in timestamp
        assert "+" in timestamp or "Z" in timestamp
