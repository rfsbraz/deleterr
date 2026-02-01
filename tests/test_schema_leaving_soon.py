# encoding: utf-8
"""Unit tests for LeavingSoon schema models."""

import pytest
from pydantic import ValidationError

from app.schema import (
    LeavingSoonConfig,
    LeavingSoonCollectionConfig,
    LeavingSoonLabelConfig,
    LeavingSoonNotificationConfig,
    LibraryConfig,
    NotificationConfig,
    EmailNotificationConfig,
    DiscordNotificationConfig,
)


class TestLeavingSoonCollectionConfig:
    """Tests for LeavingSoonCollectionConfig model."""

    def test_default_values(self):
        """Test default values for collection config."""
        config = LeavingSoonCollectionConfig()
        assert config.name == "Leaving Soon"

    def test_custom_name(self):
        """Test custom name for collection config."""
        config = LeavingSoonCollectionConfig(name="Expiring Content")
        assert config.name == "Expiring Content"

    def test_from_dict(self):
        """Test creating config from dictionary."""
        data = {"name": "Custom Collection"}
        config = LeavingSoonCollectionConfig(**data)
        assert config.name == "Custom Collection"


class TestLeavingSoonLabelConfig:
    """Tests for LeavingSoonLabelConfig model."""

    def test_default_values(self):
        """Test default values for label config."""
        config = LeavingSoonLabelConfig()
        assert config.name == "leaving-soon"

    def test_custom_name(self):
        """Test custom name for label config."""
        config = LeavingSoonLabelConfig(name="expiring")
        assert config.name == "expiring"


class TestLeavingSoonConfig:
    """Tests for LeavingSoonConfig model."""

    def test_default_values(self):
        """Test default values for leaving soon config."""
        config = LeavingSoonConfig()
        assert config.collection is None
        assert config.labels is None

    def test_with_collection(self):
        """Test configuring with collection."""
        config = LeavingSoonConfig(
            collection=LeavingSoonCollectionConfig(),
        )
        assert config.collection is not None
        assert config.collection.name == "Leaving Soon"

    def test_with_labels(self):
        """Test configuring with labels."""
        config = LeavingSoonConfig(
            labels=LeavingSoonLabelConfig(name="expiring"),
        )
        assert config.labels is not None
        assert config.labels.name == "expiring"

    def test_both_collection_and_labels(self):
        """Test configuring both collection and labels."""
        config = LeavingSoonConfig(
            collection=LeavingSoonCollectionConfig(),
            labels=LeavingSoonLabelConfig(),
        )
        assert config.collection is not None
        assert config.labels is not None

    def test_from_dict(self):
        """Test creating config from nested dictionary."""
        data = {
            "collection": {
                "name": "Leaving Soon",
            },
            "labels": {
                "name": "leaving-soon",
            },
        }
        config = LeavingSoonConfig(**data)
        assert config.collection.name == "Leaving Soon"
        assert config.labels.name == "leaving-soon"


class TestLibraryConfigWithLeavingSoon:
    """Tests for LibraryConfig with leaving_soon field."""

    def test_library_without_leaving_soon(self):
        """Test library config without leaving_soon (backward compatible)."""
        config = LibraryConfig(
            name="Movies",
            radarr="Radarr",
            action_mode="delete",
        )
        assert config.leaving_soon is None

    def test_library_with_leaving_soon(self):
        """Test library config with leaving_soon configured."""
        config = LibraryConfig(
            name="Movies",
            radarr="Radarr",
            action_mode="delete",
            leaving_soon=LeavingSoonConfig(
                collection=LeavingSoonCollectionConfig(),
            ),
        )
        assert config.leaving_soon is not None
        assert config.leaving_soon.collection.name == "Leaving Soon"

    def test_library_with_leaving_soon_from_dict(self):
        """Test library config with leaving_soon from dictionary."""
        data = {
            "name": "Movies",
            "radarr": "Radarr",
            "action_mode": "delete",
            "leaving_soon": {
                "collection": {
                    "name": "Leaving Soon",
                },
            },
        }
        config = LibraryConfig(**data)
        assert config.leaving_soon is not None
        assert config.leaving_soon.collection.name == "Leaving Soon"

    def test_library_config_validation_still_works(self):
        """Test that library validation still works with leaving_soon."""
        # Should fail: neither radarr nor sonarr set
        with pytest.raises(ValidationError) as exc_info:
            LibraryConfig(
                name="Movies",
                action_mode="delete",
                leaving_soon=LeavingSoonConfig(),
            )
        assert "Either radarr or sonarr must be set" in str(exc_info.value)

    def test_sonarr_library_with_leaving_soon(self):
        """Test Sonarr library config with leaving_soon."""
        config = LibraryConfig(
            name="TV Shows",
            sonarr="Sonarr",
            action_mode="delete",
            series_type="standard",
            leaving_soon=LeavingSoonConfig(
                labels=LeavingSoonLabelConfig(),
            ),
        )
        assert config.sonarr == "Sonarr"
        assert config.leaving_soon.labels is not None

    def test_leaving_soon_requires_preview_next_not_zero(self):
        """Test that leaving_soon raises error when preview_next is explicitly 0."""
        with pytest.raises(ValidationError) as exc_info:
            LibraryConfig(
                name="Movies",
                radarr="Radarr",
                action_mode="delete",
                preview_next=0,
                leaving_soon=LeavingSoonConfig(
                    collection=LeavingSoonCollectionConfig(),
                ),
            )
        assert "leaving_soon requires preview_next > 0" in str(exc_info.value)

    def test_leaving_soon_works_with_preview_next_positive(self):
        """Test that leaving_soon works when preview_next is positive."""
        config = LibraryConfig(
            name="Movies",
            radarr="Radarr",
            action_mode="delete",
            preview_next=5,
            leaving_soon=LeavingSoonConfig(
                collection=LeavingSoonCollectionConfig(),
            ),
        )
        assert config.preview_next == 5
        assert config.leaving_soon is not None

    def test_leaving_soon_works_with_preview_next_none(self):
        """Test that leaving_soon works when preview_next is not set (defaults to max_actions_per_run)."""
        config = LibraryConfig(
            name="Movies",
            radarr="Radarr",
            action_mode="delete",
            leaving_soon=LeavingSoonConfig(
                collection=LeavingSoonCollectionConfig(),
            ),
        )
        assert config.preview_next is None  # Will default to max_actions_per_run at runtime
        assert config.leaving_soon is not None

    def test_presence_of_config_means_enabled(self):
        """Test that presence of leaving_soon config means it's enabled (no enabled field)."""
        config = LibraryConfig(
            name="Movies",
            radarr="Radarr",
            action_mode="delete",
            leaving_soon=LeavingSoonConfig(
                collection=LeavingSoonCollectionConfig(),
            ),
        )
        # No 'enabled' field - presence of config means it's enabled
        assert config.leaving_soon is not None
        assert not hasattr(config.leaving_soon, 'enabled') or 'enabled' not in config.leaving_soon.model_fields


class TestEmailNotificationConfig:
    """Tests for EmailNotificationConfig model."""

    def test_default_values(self):
        """Test default values for email config."""
        config = EmailNotificationConfig()
        assert config.smtp_server is None
        assert config.smtp_port == 587
        assert config.smtp_username is None
        assert config.smtp_password is None
        assert config.use_tls is True
        assert config.use_ssl is False
        assert config.from_address is None
        assert config.to_addresses == []
        assert config.subject == "Deleterr Run Complete"

    def test_custom_values(self):
        """Test custom values for email config."""
        config = EmailNotificationConfig(
            smtp_server="smtp.example.com",
            smtp_port=465,
            smtp_username="user",
            smtp_password="pass",
            use_tls=False,
            use_ssl=True,
            from_address="test@example.com",
            to_addresses=["user1@example.com", "user2@example.com"],
            subject="Custom Subject",
        )
        assert config.smtp_server == "smtp.example.com"
        assert config.smtp_port == 465
        assert config.use_ssl is True
        assert config.use_tls is False
        assert len(config.to_addresses) == 2

    def test_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "from_address": "test@gmail.com",
            "to_addresses": ["user@example.com"],
        }
        config = EmailNotificationConfig(**data)
        assert config.smtp_server == "smtp.gmail.com"
        assert config.from_address == "test@gmail.com"


class TestLeavingSoonNotificationConfig:
    """Tests for LeavingSoonNotificationConfig model."""

    def test_default_values(self):
        """Test default values for leaving soon notification config."""
        config = LeavingSoonNotificationConfig()
        assert config.template is None
        assert config.subject == "Leaving Soon - Content scheduled for removal"
        assert config.email is None
        assert config.discord is None
        assert config.slack is None
        assert config.telegram is None
        assert config.webhook is None

    def test_with_email_provider(self):
        """Test configuring with email provider."""
        config = LeavingSoonNotificationConfig(
            email=EmailNotificationConfig(
                smtp_server="smtp.example.com",
                from_address="test@example.com",
                to_addresses=["user@example.com"],
            ),
        )
        assert config.email is not None
        assert config.email.smtp_server == "smtp.example.com"

    def test_with_discord_provider(self):
        """Test configuring with discord provider."""
        config = LeavingSoonNotificationConfig(
            discord=DiscordNotificationConfig(
                webhook_url="https://discord.com/api/webhooks/...",
            ),
        )
        assert config.discord is not None
        assert config.discord.webhook_url == "https://discord.com/api/webhooks/..."

    def test_with_multiple_providers(self):
        """Test configuring with multiple providers."""
        config = LeavingSoonNotificationConfig(
            email=EmailNotificationConfig(
                smtp_server="smtp.example.com",
                from_address="test@example.com",
                to_addresses=["user@example.com"],
            ),
            discord=DiscordNotificationConfig(
                webhook_url="https://discord.com/api/webhooks/...",
            ),
        )
        assert config.email is not None
        assert config.discord is not None

    def test_custom_template_and_subject(self):
        """Test custom template and subject."""
        config = LeavingSoonNotificationConfig(
            template="/config/my-template.html",
            subject="Watch Before It's Gone!",
        )
        assert config.template == "/config/my-template.html"
        assert config.subject == "Watch Before It's Gone!"

    def test_from_dict(self):
        """Test creating config from nested dictionary."""
        data = {
            "template": "/config/template.html",
            "subject": "Custom Subject",
            "email": {
                "smtp_server": "smtp.example.com",
                "from_address": "test@example.com",
                "to_addresses": ["user@example.com"],
            },
        }
        config = LeavingSoonNotificationConfig(**data)
        assert config.template == "/config/template.html"
        assert config.email.smtp_server == "smtp.example.com"


class TestNotificationConfigWithLeavingSoon:
    """Tests for NotificationConfig with leaving_soon and email fields."""

    def test_notification_config_with_email(self):
        """Test notification config with email provider."""
        config = NotificationConfig(
            email=EmailNotificationConfig(
                smtp_server="smtp.example.com",
                from_address="test@example.com",
                to_addresses=["user@example.com"],
            ),
        )
        assert config.email is not None
        assert config.email.smtp_server == "smtp.example.com"

    def test_notification_config_with_leaving_soon(self):
        """Test notification config with leaving_soon section."""
        config = NotificationConfig(
            leaving_soon=LeavingSoonNotificationConfig(
                email=EmailNotificationConfig(
                    smtp_server="smtp.example.com",
                    from_address="test@example.com",
                    to_addresses=["user@example.com"],
                ),
            ),
        )
        assert config.leaving_soon is not None
        assert config.leaving_soon.email is not None

    def test_separate_admin_and_user_notifications(self):
        """Test configuring separate admin and user notifications."""
        config = NotificationConfig(
            # Admin notifications (what was deleted)
            discord=DiscordNotificationConfig(
                webhook_url="https://discord.com/api/webhooks/admin",
            ),
            # User-facing leaving soon notifications
            leaving_soon=LeavingSoonNotificationConfig(
                email=EmailNotificationConfig(
                    smtp_server="smtp.example.com",
                    from_address="test@example.com",
                    to_addresses=["user1@example.com", "user2@example.com"],
                ),
                discord=DiscordNotificationConfig(
                    webhook_url="https://discord.com/api/webhooks/users",
                ),
            ),
        )
        # Admin discord
        assert config.discord.webhook_url == "https://discord.com/api/webhooks/admin"
        # User discord (different webhook)
        assert config.leaving_soon.discord.webhook_url == "https://discord.com/api/webhooks/users"
        # User email
        assert len(config.leaving_soon.email.to_addresses) == 2

    def test_from_dict_full_config(self):
        """Test creating full notification config from dictionary."""
        data = {
            "enabled": True,
            "notify_on_dry_run": False,
            "discord": {
                "webhook_url": "https://discord.com/api/webhooks/admin",
            },
            "email": {
                "smtp_server": "smtp.example.com",
                "from_address": "admin@example.com",
                "to_addresses": ["admin@example.com"],
            },
            "leaving_soon": {
                "subject": "Content Leaving Soon!",
                "email": {
                    "smtp_server": "smtp.example.com",
                    "from_address": "plex@example.com",
                    "to_addresses": ["family@example.com"],
                },
            },
        }
        config = NotificationConfig(**data)
        assert config.discord.webhook_url == "https://discord.com/api/webhooks/admin"
        assert config.email.from_address == "admin@example.com"
        assert config.leaving_soon.email.from_address == "plex@example.com"
        assert config.leaving_soon.subject == "Content Leaving Soon!"
