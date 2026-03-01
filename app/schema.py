# encoding: utf-8
"""
Pydantic schema for Deleterr configuration.

This module serves as the single source of truth for:
1. Configuration validation
2. Documentation generation
3. Type hints

Run `python -m scripts.generate_docs` to regenerate documentation from this schema.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field, model_validator


class PlexConfig(BaseModel):
    """Plex server connection settings."""

    url: str = Field(
        ...,
        description="URL of your Plex server",
        json_schema_extra={"example": "http://localhost:32400"},
    )
    token: str = Field(
        ...,
        description="Plex authentication token. [How to get](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)",
        json_schema_extra={"example": "YOUR_PLEX_TOKEN"},
    )


class TautulliConfig(BaseModel):
    """Tautulli connection settings for watch history tracking."""

    url: str = Field(
        ...,
        description="URL of your Tautulli server",
        json_schema_extra={"example": "http://localhost:8181"},
    )
    api_key: str = Field(
        ...,
        description="Tautulli API key",
        json_schema_extra={"example": "YOUR_TAUTULLI_API_KEY"},
    )


class RadarrInstance(BaseModel):
    """Radarr instance connection settings."""

    name: str = Field(
        ...,
        description="Identifier for this Radarr instance (used in library config)",
        json_schema_extra={"example": "Radarr"},
    )
    url: str = Field(
        ...,
        description="URL of your Radarr server",
        json_schema_extra={"example": "http://localhost:7878"},
    )
    api_key: str = Field(
        ...,
        description="Radarr API key",
        json_schema_extra={"example": "YOUR_RADARR_API_KEY"},
    )


class SonarrInstance(BaseModel):
    """Sonarr instance connection settings."""

    name: str = Field(
        ...,
        description="Identifier for this Sonarr instance (used in library config)",
        json_schema_extra={"example": "Sonarr"},
    )
    url: str = Field(
        ...,
        description="URL of your Sonarr server",
        json_schema_extra={"example": "http://localhost:8989"},
    )
    api_key: str = Field(
        ...,
        description="Sonarr API key",
        json_schema_extra={"example": "YOUR_SONARR_API_KEY"},
    )


class TraktConfig(BaseModel):
    """Trakt API credentials. Required only for Trakt list exclusions."""

    client_id: str = Field(
        ...,
        description="Trakt client ID. Create an app at [trakt.tv/oauth/applications](https://trakt.tv/oauth/applications)",
        json_schema_extra={"example": "YOUR_TRAKT_CLIENT_ID"},
    )
    client_secret: str = Field(
        ...,
        description="Trakt client secret",
        json_schema_extra={"example": "YOUR_TRAKT_CLIENT_SECRET"},
    )


class MdblistConfig(BaseModel):
    """Mdblist API credentials. Required only for Mdblist list exclusions."""

    api_key: str = Field(
        ...,
        description="Mdblist API key from https://mdblist.com/preferences/",
        json_schema_extra={"example": "YOUR_MDBLIST_API_KEY"},
    )


class JustWatchGlobalConfig(BaseModel):
    """Global JustWatch settings for streaming availability lookups."""

    country: Optional[str] = Field(
        default=None,
        description="ISO 3166-1 alpha-2 country code (e.g., US, GB, DE)",
        json_schema_extra={"example": "US"},
    )
    language: str = Field(
        default="en",
        description="Language code for API responses",
        json_schema_extra={"example": "en"},
    )


class SchedulerConfig(BaseModel):
    """
    Built-in scheduler configuration.

    Provides an alternative to external schedulers like Ofelia or system cron.
    When enabled, Deleterr runs as a long-lived process and executes on the
    configured schedule.
    """

    enabled: bool = Field(
        default=True,
        description="Enable built-in scheduler. Set to false for external schedulers (Ofelia, cron) where Deleterr should run once and exit",
    )
    schedule: str = Field(
        default="weekly",
        description="Cron expression or preset (hourly, daily, weekly, monthly). Examples: 'weekly', '0 3 * * 0' (Sunday 3 AM)",
        json_schema_extra={"example": "weekly"},
    )
    timezone: str = Field(
        default="UTC",
        description="Timezone for schedule (e.g., 'America/New_York', 'Europe/London')",
        json_schema_extra={"example": "UTC"},
    )
    run_on_startup: bool = Field(
        default=False,
        description="Run immediately when container starts, in addition to scheduled runs",
    )


class DiskSizeThreshold(BaseModel):
    """Disk size threshold configuration."""

    path: str = Field(
        ...,
        description="Path accessible by Sonarr/Radarr to check disk space",
        json_schema_extra={"example": "/data/media"},
    )
    threshold: str = Field(
        ...,
        description="Size threshold. Units: B, KB, MB, GB, TB, PB, EB",
        json_schema_extra={"example": "1TB"},
    )


class SortConfig(BaseModel):
    """Sorting configuration for deletion order."""

    field: str = Field(
        default="title",
        description="Field(s) to sort by. Comma-separated for multi-level sorting. "
                    "Options: title, size, release_year, runtime, added_date, rating, "
                    "seasons, episodes, last_watched. "
                    "Example: 'last_watched,size' sorts by watch status first, then size",
    )
    order: str = Field(
        default="asc",
        description="Sort order(s): asc (ascending), desc (descending). "
                    "Comma-separated to match fields. If fewer orders than fields, "
                    "last order is reused. Example: 'desc,asc' or just 'desc'",
    )

    @model_validator(mode="after")
    def validate_sort_fields(self):
        valid_fields = {"title", "size", "release_year", "runtime", "added_date",
                        "rating", "seasons", "episodes", "last_watched"}
        valid_orders = {"asc", "desc"}

        fields = [f.strip() for f in self.field.split(",")]
        for f in fields:
            if f not in valid_fields:
                raise ValueError(f"Invalid sort field: {f}. Valid: {', '.join(sorted(valid_fields))}")

        orders = [o.strip() for o in self.order.split(",")]
        for o in orders:
            if o not in valid_orders:
                raise ValueError(f"Invalid sort order: {o}. Valid: asc, desc")

        return self


class LeavingSoonCollectionConfig(BaseModel):
    """Configuration for Leaving Soon collection in Plex."""

    name: str = Field(
        default="Leaving Soon",
        description="Name of the collection to create in Plex",
    )
    promote_home: bool = Field(
        default=True,
        description="Promote collection to appear on your Plex Home page",
    )
    promote_shared: bool = Field(
        default=True,
        description="Promote collection to appear on shared users' Home pages (Friends' Home)",
    )


class LeavingSoonLabelConfig(BaseModel):
    """Configuration for Leaving Soon labels in Plex."""

    name: str = Field(
        default="leaving-soon",
        description="Label/tag to add to items scheduled for deletion",
    )


class LeavingSoonConfig(BaseModel):
    """
    Configuration for marking media that is scheduled for deletion.

    Implements a "death row" pattern: items are first tagged to the collection/label,
    then deleted on the next run. This gives users a warning period before deletion.

    First run: Tag preview candidates, no deletions
    Subsequent runs: Delete previously tagged items, then tag new candidates
    """

    duration: Optional[str] = Field(
        default=None,
        description="How long items stay in 'Leaving Soon' before deletion. "
                    "Used to display the deletion date in notifications and collection descriptions. "
                    "Examples: '7d', '24h', '30d'. Defaults to schedule interval if not set",
        json_schema_extra={"example": "7d"},
    )
    collection: Optional[LeavingSoonCollectionConfig] = Field(
        default=None,
        description="Configuration for the Leaving Soon collection",
    )
    labels: Optional[LeavingSoonLabelConfig] = Field(
        default=None,
        description="Configuration for the Leaving Soon labels",
    )


class TraktExclusions(BaseModel):
    """Trakt list exclusions."""

    max_items_per_list: int = Field(
        default=100,
        description="Maximum items to fetch from each Trakt list",
    )
    lists: list[str] = Field(
        default_factory=list,
        description="Trakt list URLs to exclude. Supports official lists (trending, popular) and user lists",
        json_schema_extra={"example": ["https://trakt.tv/movies/trending", "https://trakt.tv/users/justin/lists/imdb-top-rated-movies"]},
    )


class MdblistExclusions(BaseModel):
    """Mdblist list exclusions."""

    max_items_per_list: int = Field(
        default=1000,
        description="Maximum items to fetch from each Mdblist list",
    )
    lists: list[str] = Field(
        default_factory=list,
        description="Mdblist list URLs to exclude",
        json_schema_extra={"example": ["https://mdblist.com/lists/username/listname"]},
    )


class JustWatchExclusions(BaseModel):
    """JustWatch streaming availability exclusions."""

    country: Optional[str] = Field(
        default=None,
        description="Override global country setting for this library",
        json_schema_extra={"example": "US"},
    )
    language: Optional[str] = Field(
        default=None,
        description="Override global language setting for this library",
    )
    available_on: Optional[list[str]] = Field(
        default=None,
        description="Exclude media available on these providers. Use ['any'] for any service. Mutually exclusive with not_available_on",
        json_schema_extra={"example": ["netflix", "disneyplus"]},
    )
    not_available_on: Optional[list[str]] = Field(
        default=None,
        description="Exclude media NOT available on these providers. Mutually exclusive with available_on",
        json_schema_extra={"example": ["any"]},
    )

    @model_validator(mode="after")
    def check_mutual_exclusivity(self):
        if self.available_on and self.not_available_on:
            raise ValueError("available_on and not_available_on are mutually exclusive")
        return self


class SeerrConfig(BaseModel):
    """Seerr/Overseerr connection settings for request-based exclusions."""

    url: str = Field(
        ...,
        description="URL of your Seerr (or Overseerr) server",
        json_schema_extra={"example": "http://localhost:5055"},
    )
    api_key: str = Field(
        ...,
        description="Seerr API key. Found in Seerr Settings → General",
        json_schema_extra={"example": "YOUR_SEERR_API_KEY"},
    )


class SeerrExclusions(BaseModel):
    """Seerr/Overseerr request-based exclusions."""

    mode: Literal["exclude", "include_only"] = Field(
        default="exclude",
        description="How to handle requested media. `exclude` protects requested items from deletion. `include_only` deletes ONLY requested items",
    )
    users: list[str] = Field(
        default_factory=list,
        description="Only consider requests from these users (username, email, or Plex username). If empty, all requests are considered",
        json_schema_extra={"example": ["user1", "admin"]},
    )
    include_pending: bool = Field(
        default=True,
        description="Whether to include pending (not yet approved) requests",
    )
    request_status: list[str] = Field(
        default_factory=list,
        description="Only consider requests with these statuses: `pending`, `approved`, `declined`. If empty, all statuses are considered",
        json_schema_extra={"example": ["approved"]},
    )
    min_request_age_days: int = Field(
        default=0,
        description="Only consider requests older than this many days",
    )
    update_status: bool = Field(
        default=False,
        description="After deletion, mark the media as deleted in Seerr so it can be requested again",
    )


class RadarrExclusions(BaseModel):
    """Radarr-specific exclusions. Only applies to movie libraries."""

    tags: list[str] = Field(
        default_factory=list,
        description="Radarr tags to exclude (case-insensitive)",
        json_schema_extra={"example": ["4K", "keep", "favorite"]},
    )
    quality_profiles: list[str] = Field(
        default_factory=list,
        description="Quality profiles to exclude (exact match)",
        json_schema_extra={"example": ["Remux-2160p", "Bluray-2160p"]},
    )
    paths: list[str] = Field(
        default_factory=list,
        description="Paths to exclude (substring match)",
        json_schema_extra={"example": ["/data/media/4k"]},
    )
    monitored: Optional[bool] = Field(
        default=None,
        description="True to exclude monitored movies, False to exclude unmonitored",
    )


class SonarrExclusions(BaseModel):
    """Sonarr-specific exclusions. Only applies to TV show libraries."""

    status: list[str] = Field(
        default_factory=list,
        description="Sonarr series status to exclude: continuing, ended, upcoming, deleted",
        json_schema_extra={"example": ["continuing", "upcoming"]},
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Sonarr tags to exclude (case-insensitive)",
        json_schema_extra={"example": ["4K", "keep", "favorite"]},
    )
    quality_profiles: list[str] = Field(
        default_factory=list,
        description="Quality profiles to exclude (exact match)",
        json_schema_extra={"example": ["Remux-2160p", "Bluray-2160p"]},
    )
    paths: list[str] = Field(
        default_factory=list,
        description="Paths to exclude (substring match)",
        json_schema_extra={"example": ["/data/media/4k"]},
    )
    monitored: Optional[bool] = Field(
        default=None,
        description="True to exclude monitored shows, False to exclude unmonitored",
    )


class Exclusions(BaseModel):
    """Exclusion rules to protect media from deletion."""

    titles: list[str] = Field(
        default_factory=list,
        description="Exact titles to exclude",
        json_schema_extra={"example": ["Forrest Gump", "The Godfather"]},
    )
    plex_labels: list[str] = Field(
        default_factory=list,
        description="Plex labels to exclude",
        json_schema_extra={"example": ["favorite", "keep"]},
    )
    genres: list[str] = Field(
        default_factory=list,
        description="Genres to exclude",
        json_schema_extra={"example": ["documentary", "horror"]},
    )
    collections: list[str] = Field(
        default_factory=list,
        description="Collections to exclude",
        json_schema_extra={"example": ["Marvel Cinematic Universe"]},
    )
    actors: list[str] = Field(
        default_factory=list,
        description="Actors to exclude",
        json_schema_extra={"example": ["Tom Hanks", "Brad Pitt"]},
    )
    producers: list[str] = Field(
        default_factory=list,
        description="Producers to exclude",
        json_schema_extra={"example": ["Steven Spielberg"]},
    )
    directors: list[str] = Field(
        default_factory=list,
        description="Directors to exclude",
        json_schema_extra={"example": ["Christopher Nolan"]},
    )
    writers: list[str] = Field(
        default_factory=list,
        description="Writers to exclude",
        json_schema_extra={"example": ["Aaron Sorkin"]},
    )
    studios: list[str] = Field(
        default_factory=list,
        description="Studios to exclude",
        json_schema_extra={"example": ["Studio Ghibli", "A24"]},
    )
    release_years: int = Field(
        default=0,
        description="Exclude media released within last X years",
        json_schema_extra={"example": 2},
    )
    trakt: Optional[TraktExclusions] = Field(
        default=None,
        description="Trakt list exclusions",
    )
    mdblist: Optional[MdblistExclusions] = Field(
        default=None,
        description="Mdblist list exclusions",
    )
    justwatch: Optional[JustWatchExclusions] = Field(
        default=None,
        description="JustWatch streaming availability exclusions",
    )
    radarr: Optional[RadarrExclusions] = Field(
        default=None,
        description="Radarr-specific exclusions (movies only)",
    )
    sonarr: Optional[SonarrExclusions] = Field(
        default=None,
        description="Sonarr-specific exclusions (TV shows only)",
    )
    seerr: Optional[SeerrExclusions] = Field(
        default=None,
        description="Seerr/Overseerr request-based exclusions",
    )


class LibraryConfig(BaseModel):
    """Configuration for a Plex library."""

    name: str = Field(
        ...,
        description="Name of the Plex library (must match exactly)",
        json_schema_extra={"example": "Movies"},
    )
    radarr: Optional[str] = Field(
        default=None,
        description="Name of the Radarr instance to use. Mutually exclusive with sonarr",
        json_schema_extra={"example": "Radarr"},
    )
    sonarr: Optional[str] = Field(
        default=None,
        description="Name of the Sonarr instance to use. Mutually exclusive with radarr",
        json_schema_extra={"example": "Sonarr"},
    )
    series_type: Literal["standard", "anime", "daily"] = Field(
        default="standard",
        description="Series type filter for Sonarr libraries",
    )
    action_mode: Literal["delete"] = Field(
        ...,
        description="Action to perform on matching media",
    )
    watch_status: Optional[Literal["watched", "unwatched"]] = Field(
        default=None,
        description="Filter by watch status. If not set, both watched and unwatched media are considered",
    )
    last_watched_threshold: Optional[int] = Field(
        default=None,
        description="Days since last watch. Media watched within this period is protected",
        json_schema_extra={"example": 90},
    )
    added_at_threshold: Optional[int] = Field(
        default=None,
        description="Days since added to Plex. Media added within this period is protected",
        json_schema_extra={"example": 180},
    )
    apply_last_watch_threshold_to_collections: bool = Field(
        default=False,
        description="Apply last watched threshold to all items in the same collection",
    )
    add_list_exclusion_on_delete: bool = Field(
        default=False,
        description="Prevent Radarr from re-importing deleted media from lists. Radarr only",
    )
    max_actions_per_run: int = Field(
        default=10,
        description="Maximum deletions per run",
    )
    preview_next: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of items to preview for next run. Defaults to max_actions_per_run. Set to 0 to disable",
    )
    disk_size_threshold: list[DiskSizeThreshold] = Field(
        default_factory=list,
        description="Only delete when disk space is below threshold",
    )
    sort: Optional[SortConfig] = Field(
        default=None,
        description="Sorting configuration for deletion order",
    )
    exclude: Optional[Exclusions] = Field(
        default=None,
        description="Exclusion rules to protect media",
    )
    leaving_soon: Optional[LeavingSoonConfig] = Field(
        default=None,
        description="Configuration for 'death row' deletion pattern. Items are first "
                    "tagged to collection/label, then deleted on the next run. "
                    "Presence of this config enables the feature (no 'enabled' field needed)",
    )

    @model_validator(mode="after")
    def check_instance_set(self):
        if not self.radarr and not self.sonarr:
            raise ValueError("Either radarr or sonarr must be set")
        if self.radarr and self.sonarr:
            raise ValueError("Only one of radarr or sonarr can be set")
        return self

    @model_validator(mode="after")
    def check_leaving_soon_requires_preview(self):
        if self.leaving_soon is not None:
            if self.preview_next is not None and self.preview_next == 0:
                raise ValueError(
                    "leaving_soon requires preview_next > 0 (cannot be explicitly set to 0)"
                )
        return self


class DiscordNotificationConfig(BaseModel):
    """Discord webhook notification settings."""

    webhook_url: Optional[str] = Field(
        default=None,
        description="Discord webhook URL. Create one in Server Settings → Integrations → Webhooks",
        json_schema_extra={"example": "https://discord.com/api/webhooks/..."},
    )
    username: str = Field(
        default="Deleterr",
        description="Bot username displayed in Discord",
    )
    avatar_url: Optional[str] = Field(
        default=None,
        description="URL to avatar image for the bot",
    )


class SlackNotificationConfig(BaseModel):
    """Slack webhook notification settings."""

    webhook_url: Optional[str] = Field(
        default=None,
        description="Slack Incoming Webhook URL. Create one at api.slack.com/apps",
        json_schema_extra={"example": "https://hooks.slack.com/services/..."},
    )
    channel: Optional[str] = Field(
        default=None,
        description="Override the default channel for this webhook",
        json_schema_extra={"example": "#media-cleanup"},
    )
    username: str = Field(
        default="Deleterr",
        description="Bot username displayed in Slack",
    )
    icon_emoji: str = Field(
        default=":wastebasket:",
        description="Emoji icon for the bot",
    )


class TelegramNotificationConfig(BaseModel):
    """Telegram Bot API notification settings."""

    bot_token: Optional[str] = Field(
        default=None,
        description="Telegram bot token from @BotFather",
        json_schema_extra={"example": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"},
    )
    chat_id: Optional[str] = Field(
        default=None,
        description="Telegram chat ID (user, group, or channel). Use @userinfobot to find your ID",
        json_schema_extra={"example": "-1001234567890"},
    )
    parse_mode: str = Field(
        default="MarkdownV2",
        description="Message parsing mode: MarkdownV2, HTML, or Markdown",
    )


class WebhookNotificationConfig(BaseModel):
    """Generic webhook notification settings."""

    url: Optional[str] = Field(
        default=None,
        description="Webhook URL to receive JSON payloads",
        json_schema_extra={"example": "https://example.com/webhook"},
    )
    method: str = Field(
        default="POST",
        description="HTTP method: POST or PUT",
    )
    headers: Optional[dict[str, str]] = Field(
        default=None,
        description="Custom HTTP headers to include with requests",
        json_schema_extra={"example": {"Authorization": "Bearer token"}},
    )
    timeout: int = Field(
        default=30,
        description="Request timeout in seconds",
    )


class EmailNotificationConfig(BaseModel):
    """Email notification settings via SMTP."""

    smtp_server: Optional[str] = Field(
        default=None,
        description="SMTP server hostname",
        json_schema_extra={"example": "smtp.gmail.com"},
    )
    smtp_port: int = Field(
        default=587,
        description="SMTP port (587 for TLS, 465 for SSL)",
    )
    smtp_username: Optional[str] = Field(
        default=None,
        description="SMTP username for authentication",
    )
    smtp_password: Optional[str] = Field(
        default=None,
        description="SMTP password for authentication",
    )
    use_tls: bool = Field(
        default=True,
        description="Use TLS encryption (STARTTLS on port 587)",
    )
    use_ssl: bool = Field(
        default=False,
        description="Use SSL encryption (implicit SSL on port 465)",
    )
    from_address: Optional[str] = Field(
        default=None,
        description="Sender email address",
        json_schema_extra={"example": "deleterr@yourdomain.com"},
    )
    to_addresses: list[str] = Field(
        default_factory=list,
        description="Recipient email addresses",
        json_schema_extra={"example": ["user1@example.com", "user2@example.com"]},
    )
    subject: str = Field(
        default="Deleterr Run Complete",
        description="Email subject line",
    )


class LeavingSoonNotificationConfig(BaseModel):
    """
    Dedicated notifications for leaving soon items (user-facing).

    These notifications inform users about content scheduled for deletion,
    giving them a chance to watch before items are removed.

    Note: Presence of this config = enabled (no explicit 'enabled' field).
    Providers must be explicitly configured here - they do NOT inherit
    from the main notification config.
    """

    template: Optional[str] = Field(
        default=None,
        description="Path to custom HTML template for emails. Uses built-in template if not specified",
        json_schema_extra={"example": "/config/my-custom-template.html"},
    )
    subject: str = Field(
        default="Leaving Soon - Content scheduled for removal",
        description="Email subject for leaving soon notifications",
    )
    # Provider configs - EXPLICIT ONLY, no inheritance from parent
    email: Optional[EmailNotificationConfig] = Field(
        default=None,
        description="Email notification settings for leaving soon alerts",
    )
    discord: Optional[DiscordNotificationConfig] = Field(
        default=None,
        description="Discord webhook settings for leaving soon alerts",
    )
    slack: Optional[SlackNotificationConfig] = Field(
        default=None,
        description="Slack webhook settings for leaving soon alerts",
    )
    telegram: Optional[TelegramNotificationConfig] = Field(
        default=None,
        description="Telegram settings for leaving soon alerts",
    )
    webhook: Optional[WebhookNotificationConfig] = Field(
        default=None,
        description="Generic webhook settings for leaving soon alerts",
    )


class NotificationConfig(BaseModel):
    """
    Notification settings for alerting about deletions.

    Configure one or more notification providers to receive alerts when
    Deleterr deletes media or has items scheduled for deletion.
    """

    enabled: bool = Field(
        default=True,
        description="Enable/disable all notifications",
    )
    notify_on_dry_run: bool = Field(
        default=True,
        description="Send notifications even in dry-run mode",
    )
    include_preview: bool = Field(
        default=True,
        description="Include next scheduled deletions in notifications",
    )
    min_deletions_to_notify: int = Field(
        default=0,
        ge=0,
        description="Minimum number of deletions required to send a notification. Set to 0 to always notify",
    )
    discord: Optional[DiscordNotificationConfig] = Field(
        default=None,
        description="Discord webhook notification settings",
    )
    slack: Optional[SlackNotificationConfig] = Field(
        default=None,
        description="Slack webhook notification settings",
    )
    telegram: Optional[TelegramNotificationConfig] = Field(
        default=None,
        description="Telegram Bot API notification settings",
    )
    webhook: Optional[WebhookNotificationConfig] = Field(
        default=None,
        description="Generic webhook notification settings",
    )
    email: Optional[EmailNotificationConfig] = Field(
        default=None,
        description="Email notification settings via SMTP",
    )
    leaving_soon: Optional[LeavingSoonNotificationConfig] = Field(
        default=None,
        description="User-facing notifications for items scheduled for deletion. "
                    "Presence of this config enables the feature (no 'enabled' field needed)",
    )


class DeleterrConfig(BaseModel):
    """
    Root configuration for Deleterr.

    Deleterr uses Radarr, Sonarr, and Tautulli to identify and delete media files
    based on user-specified criteria.
    """

    # General settings
    dry_run: bool = Field(
        default=True,
        description="If true, actions are only logged, not performed",
    )
    ssl_verify: bool = Field(
        default=False,
        description="Enable SSL certificate verification for API connections",
    )
    action_delay: int = Field(
        default=0,
        description="Delay (in seconds) between actions. Increase if Plex/Sonarr/Radarr timeout on remote mounts",
    )
    plex_library_scan_after_actions: bool = Field(
        default=False,
        description="Trigger a Plex library scan after actions are performed",
    )
    tautulli_library_scan_after_actions: bool = Field(
        default=False,
        description="Trigger a Tautulli library scan after actions are performed",
    )

    # Service connections
    plex: PlexConfig = Field(
        ...,
        description="Plex server connection settings",
    )
    tautulli: TautulliConfig = Field(
        ...,
        description="Tautulli connection settings",
    )
    radarr: list[RadarrInstance] = Field(
        default_factory=list,
        description="Radarr instance connections. Configure multiple for 4K instances",
    )
    sonarr: list[SonarrInstance] = Field(
        default_factory=list,
        description="Sonarr instance connections. Configure multiple for 4K instances",
    )
    trakt: Optional[TraktConfig] = Field(
        default=None,
        description="Trakt API credentials. Required only for Trakt list exclusions",
    )
    mdblist: Optional[MdblistConfig] = Field(
        default=None,
        description="Mdblist API credentials. Required only for Mdblist list exclusions",
    )
    justwatch: Optional[JustWatchGlobalConfig] = Field(
        default=None,
        description="Global JustWatch settings for streaming availability lookups",
    )
    seerr: Optional[SeerrConfig] = Field(
        default=None,
        description="Seerr/Overseerr connection settings for request-based exclusions",
    )

    # Scheduler
    scheduler: Optional[SchedulerConfig] = Field(
        default=None,
        description="Built-in scheduler configuration. Alternative to external schedulers like Ofelia",
    )

    # Notifications
    notifications: Optional[NotificationConfig] = Field(
        default=None,
        description="Notification settings for alerting about deletions via Discord, Slack, Telegram, or webhooks",
    )

    # Libraries
    libraries: list[LibraryConfig] = Field(
        ...,
        description="Configuration for each Plex library to manage",
        min_length=1,
    )

    @model_validator(mode="after")
    def check_instances_exist(self):
        if not self.radarr and not self.sonarr:
            raise ValueError("At least one Radarr or Sonarr instance must be configured")
        return self
