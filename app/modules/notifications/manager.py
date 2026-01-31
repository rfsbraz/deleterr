# encoding: utf-8
"""Notification manager that orchestrates all notification providers."""

from typing import Optional

from app import logger
from app.modules.notifications.models import DeletedItem, RunResult


class NotificationManager:
    """Manages and coordinates notification providers."""

    def __init__(self, config):
        """
        Initialize the notification manager.

        Args:
            config: Application configuration object with settings attribute.
        """
        self.config = config
        self.providers = []
        self.leaving_soon_providers = []
        self._notification_config = config.settings.get("notifications", {})
        self._leaving_soon_config = self._notification_config.get("leaving_soon", {})

        # Only initialize providers if notifications are enabled
        if self._notification_config.get("enabled", True):
            self._init_providers()

        # Initialize leaving_soon providers (separate from regular notifications)
        if self._leaving_soon_config:
            self._init_leaving_soon_providers()

    def _init_providers(self) -> None:
        """Initialize configured notification providers."""
        from app.modules.notifications.providers import (
            DiscordProvider,
            EmailProvider,
            SlackProvider,
            TelegramProvider,
            WebhookProvider,
        )

        provider_classes = {
            "discord": DiscordProvider,
            "email": EmailProvider,
            "slack": SlackProvider,
            "telegram": TelegramProvider,
            "webhook": WebhookProvider,
        }

        for name, provider_class in provider_classes.items():
            provider_config = self._notification_config.get(name, {})
            if provider_config:
                provider = provider_class(provider_config)
                if provider.enabled:
                    self.providers.append(provider)
                    logger.debug(f"Initialized {name} notification provider")

    def _init_leaving_soon_providers(self) -> None:
        """Initialize leaving_soon notification providers (separate from regular providers)."""
        from app.modules.notifications.providers import (
            DiscordProvider,
            EmailProvider,
            SlackProvider,
            TelegramProvider,
            WebhookProvider,
        )

        provider_classes = {
            "discord": DiscordProvider,
            "email": EmailProvider,
            "slack": SlackProvider,
            "telegram": TelegramProvider,
            "webhook": WebhookProvider,
        }

        for name, provider_class in provider_classes.items():
            provider_config = self._leaving_soon_config.get(name, {})
            if provider_config:
                provider = provider_class(provider_config)
                if provider.enabled:
                    self.leaving_soon_providers.append(provider)
                    logger.debug(f"Initialized {name} leaving_soon notification provider")

    def is_enabled(self) -> bool:
        """Check if any notification providers are enabled."""
        return bool(self.providers)

    def should_notify(self, result: RunResult) -> bool:
        """
        Determine if a notification should be sent based on config and results.

        Args:
            result: The run result to evaluate.

        Returns:
            True if notification should be sent, False otherwise.
        """
        # Check if we should notify on dry runs
        if result.is_dry_run and not self._notification_config.get(
            "notify_on_dry_run", True
        ):
            logger.debug("Skipping notification: dry run notifications disabled")
            return False

        # Check minimum deletions threshold
        min_deletions = self._notification_config.get("min_deletions_to_notify", 0)
        if len(result.deleted_items) < min_deletions:
            logger.debug(
                f"Skipping notification: {len(result.deleted_items)} deletions < {min_deletions} minimum"
            )
            return False

        # Check if there's any content to report
        include_preview = self._notification_config.get("include_preview", True)
        has_deletions = bool(result.deleted_items)
        has_preview = include_preview and bool(result.preview_items)

        if not has_deletions and not has_preview:
            logger.debug("Skipping notification: no content to report")
            return False

        return True

    def send_run_summary(self, result: RunResult) -> bool:
        """
        Send run summary to all configured providers.

        Args:
            result: The run result containing deleted and preview items.

        Returns:
            True if at least one provider succeeded, False otherwise.
        """
        if not self.is_enabled():
            logger.debug("Notifications disabled or no providers configured")
            return False

        if not self.should_notify(result):
            return False

        success_count = 0
        for provider in self.providers:
            try:
                if provider.send(result):
                    success_count += 1
                    logger.info(f"Sent notification via {provider.name}")
                else:
                    logger.warning(f"Failed to send notification via {provider.name}")
            except Exception as e:
                logger.error(f"Error sending notification via {provider.name}: {e}")

        return success_count > 0

    def test_connections(self) -> dict[str, bool]:
        """
        Test connections to all configured providers.

        Returns:
            Dictionary mapping provider names to connection status.
        """
        results = {}
        for provider in self.providers:
            try:
                results[provider.name] = provider.test_connection()
            except Exception as e:
                logger.error(f"Error testing {provider.name} connection: {e}")
                results[provider.name] = False
        return results

    def is_leaving_soon_enabled(self) -> bool:
        """Check if any leaving_soon notification providers are enabled."""
        return bool(self.leaving_soon_providers)

    def send_leaving_soon(
        self,
        items: list[DeletedItem],
        plex_url: Optional[str] = None,
        overseerr_url: Optional[str] = None,
    ) -> bool:
        """
        Send leaving soon notifications to all configured leaving_soon providers.

        This is separate from the regular run summary notifications - it's designed
        for user-facing "watch before deletion" alerts.

        Args:
            items: List of items scheduled for deletion (preview items)
            plex_url: Optional base Plex URL for "Watch Now" links
            overseerr_url: Optional Overseerr URL for "Request Again" links

        Returns:
            True if at least one provider succeeded, False otherwise.
        """
        if not self.is_leaving_soon_enabled():
            logger.debug("Leaving soon notifications disabled or no providers configured")
            return False

        if not items:
            logger.debug("No items to send in leaving soon notification")
            return False

        # Build context for templates
        context = {}
        if plex_url:
            context["plex_url"] = plex_url
        if overseerr_url:
            context["overseerr_url"] = overseerr_url

        # Get template and subject from config
        template_path = self._leaving_soon_config.get("template")
        subject = self._leaving_soon_config.get(
            "subject", "Leaving Soon - Content scheduled for removal"
        )

        success_count = 0
        for provider in self.leaving_soon_providers:
            try:
                # Email provider has special send_leaving_soon method
                if hasattr(provider, "send_leaving_soon"):
                    if provider.send_leaving_soon(
                        items,
                        template_path=template_path,
                        subject=subject,
                        context=context,
                    ):
                        success_count += 1
                        logger.info(f"Sent leaving soon notification via {provider.name}")
                    else:
                        logger.warning(
                            f"Failed to send leaving soon notification via {provider.name}"
                        )
                else:
                    # For other providers, create a RunResult with preview items
                    result = RunResult(is_dry_run=False)
                    for item in items:
                        result.add_preview(item)
                    if provider.send(result):
                        success_count += 1
                        logger.info(f"Sent leaving soon notification via {provider.name}")
                    else:
                        logger.warning(
                            f"Failed to send leaving soon notification via {provider.name}"
                        )
            except Exception as e:
                logger.error(f"Error sending leaving soon notification via {provider.name}: {e}")

        return success_count > 0
