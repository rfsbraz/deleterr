# encoding: utf-8
"""Notification providers for Deleterr."""

from app.modules.notifications.providers.discord import DiscordProvider
from app.modules.notifications.providers.slack import SlackProvider
from app.modules.notifications.providers.telegram import TelegramProvider
from app.modules.notifications.providers.webhook import WebhookProvider

__all__ = [
    "DiscordProvider",
    "SlackProvider",
    "TelegramProvider",
    "WebhookProvider",
]
