#!/usr/bin/env python3
"""
Generate CONFIGURATION.md from the Pydantic schema.

Usage:
    python -m scripts.generate_docs

This script reads the schema from app/schema.py and generates
docs/CONFIGURATION.md with accurate type information, defaults, and descriptions.
"""

import sys
from pathlib import Path
from typing import Any, get_args, get_origin

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from app.schema import (
    DeleterrConfig,
    PlexConfig,
    TautulliConfig,
    RadarrInstance,
    SonarrInstance,
    TraktConfig,
    JustWatchGlobalConfig,
    OverseerrConfig,
    SchedulerConfig,
    LibraryConfig,
    DiskSizeThreshold,
    SortConfig,
    Exclusions,
    TraktExclusions,
    JustWatchExclusions,
    RadarrExclusions,
    SonarrExclusions,
    OverseerrExclusions,
    NotificationConfig,
    DiscordNotificationConfig,
    SlackNotificationConfig,
    TelegramNotificationConfig,
    WebhookNotificationConfig,
    EmailNotificationConfig,
    LeavingSoonNotificationConfig,
    LeavingSoonConfig,
    LeavingSoonCollectionConfig,
    LeavingSoonLabelConfig,
)


def get_type_str(annotation: Any) -> str:
    """Convert a type annotation to a readable string."""
    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is None:
        # Simple type
        if annotation is type(None):
            return "null"
        if hasattr(annotation, "__name__"):
            name = annotation.__name__
            return {
                "str": "string",
                "int": "integer",
                "bool": "boolean",
                "float": "number",
            }.get(name, name)
        return str(annotation)

    # Handle Optional (Union with None)
    if origin is type(None):
        return "null"

    # Handle Literal
    if str(origin) == "typing.Literal":
        values = ", ".join(f"`{v}`" for v in args)
        return f"string ({values})"

    # Handle list
    if origin is list:
        if args:
            inner = get_type_str(args[0])
            return f"array[{inner}]"
        return "array"

    # Handle Optional (Union[X, None])
    if str(origin) in ("typing.Union", "types.UnionType"):
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return get_type_str(non_none[0])
        return " | ".join(get_type_str(a) for a in non_none)

    return str(annotation)


def get_default_str(field_info: FieldInfo) -> str:
    """Get a readable default value string."""
    if field_info.is_required():
        return "-"

    # Check for default_factory first
    if field_info.default_factory is not None:
        try:
            val = field_info.default_factory()
            if val == []:
                return "`[]`"
            if val == {}:
                return "`{}`"
            return f"`{val}`"
        except:
            return "`[]`"  # Assume list for default_factory

    default = field_info.default
    # Handle PydanticUndefined
    if default is None or str(type(default).__name__) == "PydanticUndefinedType":
        return "-"
    if isinstance(default, bool):
        return f"`{str(default).lower()}`"
    if isinstance(default, str):
        return f"`\"{default}\"`"
    if isinstance(default, int):
        return f"`{default}`"
    return f"`{default}`"


def is_required(field_info: FieldInfo) -> str:
    """Check if field is required."""
    return "Yes" if field_info.is_required() else "No"


def generate_table(model: type[BaseModel], prefix: str = "") -> str:
    """Generate a markdown table for a model's fields."""
    lines = ["| Property | Type | Required | Default | Description |"]
    lines.append("|----------|------|----------|---------|-------------|")

    for name, field_info in model.model_fields.items():
        prop_name = f"`{prefix}{name}`" if prefix else f"`{name}`"
        type_str = get_type_str(field_info.annotation)
        required = is_required(field_info)
        default = get_default_str(field_info)
        desc = field_info.description or ""

        lines.append(f"| {prop_name} | {type_str} | {required} | {default} | {desc} |")

    return "\n".join(lines)


def generate_example(model: type[BaseModel], indent: int = 0) -> str:
    """Generate a YAML example from model schema."""
    lines = []
    prefix = "  " * indent

    for name, field_info in model.model_fields.items():
        extra = field_info.json_schema_extra or {}
        example = extra.get("example")

        if example is not None:
            if isinstance(example, str):
                lines.append(f'{prefix}{name}: "{example}"')
            elif isinstance(example, list):
                if example and isinstance(example[0], str):
                    lines.append(f"{prefix}{name}:")
                    for item in example[:2]:  # Limit to 2 examples
                        lines.append(f'{prefix}  - "{item}"')
                else:
                    lines.append(f"{prefix}{name}: {example}")
            else:
                lines.append(f"{prefix}{name}: {example}")

    return "\n".join(lines)


def main():
    output_path = Path(__file__).parent.parent / "docs" / "CONFIGURATION.md"

    doc = """# Configuration Reference

Complete reference for all Deleterr configuration options.

Deleterr's **Leaving Soon** feature implements a "death row" pattern—items are first tagged to a Plex collection, users receive notifications, and deletion happens on the next run. See [Leaving Soon](#leaving-soon) and [Leaving Soon Notifications](#leaving-soon-notifications) for details.

!!! note "Auto-generated Documentation"
    This documentation is auto-generated from the [Pydantic schema](https://github.com/rfsbraz/deleterr/blob/main/app/schema.py).
    Run `python -m scripts.generate_docs` to regenerate after schema changes.

---

## Environment Variables

You can use environment variables in your configuration file using the `!env` tag. This is useful for keeping sensitive information like API keys and tokens out of your configuration file.

```yaml
plex:
  url: "http://localhost:32400"
  token: !env PLEX_TOKEN

tautulli:
  url: "http://localhost:8181"
  api_key: !env TAUTULLI_API_KEY

radarr:
  - name: "Radarr"
    url: "http://localhost:7878"
    api_key: !env RADARR_API_KEY
```

When using Docker, you can pass environment variables using the `-e` flag:

```bash
docker run -e PLEX_TOKEN=your_token -e TAUTULLI_API_KEY=your_key ...
```

Or in a `docker-compose.yml`:

```yaml
services:
  deleterr:
    image: ghcr.io/rfsbraz/deleterr:latest
    environment:
      - PLEX_TOKEN=your_token
      - TAUTULLI_API_KEY=your_key
```

!!! warning
    If an environment variable is not set, Deleterr will fail to start with an error message indicating which variable is missing.

---

## General Settings

Root-level settings that apply globally.

{general_table}

```yaml
dry_run: true
ssl_verify: false
action_delay: 25
plex_library_scan_after_actions: false
tautulli_library_scan_after_actions: false
```

---

## Plex

**Required.** Connection details for your Plex server.

{plex_table}

```yaml
plex:
  url: "http://localhost:32400"
  token: "YOUR_PLEX_TOKEN"
```

---

## Tautulli

**Required.** Connection details for Tautulli (watch history tracking).

{tautulli_table}

```yaml
tautulli:
  url: "http://localhost:8181"
  api_key: "YOUR_TAUTULLI_API_KEY"
```

---

## Radarr

Connection settings for one or more Radarr instances.

{radarr_table}

```yaml
radarr:
  - name: "Radarr"
    url: "http://localhost:7878"
    api_key: "YOUR_RADARR_API_KEY"
  - name: "Radarr 4K"
    url: "http://localhost:7879"
    api_key: "YOUR_RADARR_4K_API_KEY"
```

---

## Sonarr

Connection settings for one or more Sonarr instances.

{sonarr_table}

```yaml
sonarr:
  - name: "Sonarr"
    url: "http://localhost:8989"
    api_key: "YOUR_SONARR_API_KEY"
  - name: "Sonarr 4K"
    url: "http://localhost:8990"
    api_key: "YOUR_SONARR_4K_API_KEY"
```

---

## Trakt

Optional. Required only for Trakt list exclusions.

{trakt_table}

Create an application at [trakt.tv/oauth/applications](https://trakt.tv/oauth/applications) to get credentials.

```yaml
trakt:
  client_id: "YOUR_TRAKT_CLIENT_ID"
  client_secret: "YOUR_TRAKT_CLIENT_SECRET"
```

---

## JustWatch

Optional. Global settings for streaming availability lookups.

{justwatch_table}

```yaml
justwatch:
  country: "US"
  language: "en"
```

---

## Overseerr

Optional. Connection settings for [Overseerr](https://overseerr.dev/) request-based exclusions.

{overseerr_table}

```yaml
overseerr:
  url: "http://localhost:5055"
  api_key: "YOUR_OVERSEERR_API_KEY"
```

---

## Scheduler

Optional. Built-in scheduler as an alternative to external schedulers like Ofelia or system cron.

When enabled, Deleterr runs as a long-lived process and executes cleanup on the configured schedule. When disabled (default), Deleterr runs once and exits, suitable for triggering via external schedulers.

{scheduler_table}

**Schedule Presets:**
- `hourly` - Every hour at minute 0
- `daily` - Daily at 3 AM
- `weekly` - Sunday at 3 AM
- `monthly` - First day of month at 3 AM

**Using a preset:**
```yaml
scheduler:
  enabled: true
  schedule: "weekly"
  timezone: "America/New_York"
```

**Using a cron expression:**
```yaml
scheduler:
  enabled: true
  schedule: "0 3 * * 0"  # Sunday at 3 AM
  timezone: "UTC"
  run_on_startup: true
```

**Command-line overrides:**
- `--scheduler` - Force scheduler mode (overrides config)
- `--run-once` - Force single run mode (overrides scheduler config)

---

## Notifications

Optional. Configure notification providers to receive alerts when Deleterr deletes media.

### General Settings

{notifications_table}

### Discord

Send notifications to Discord via webhooks with rich embeds.

{discord_table}

```yaml
notifications:
  enabled: true
  notify_on_dry_run: true
  include_preview: true
  discord:
    webhook_url: "https://discord.com/api/webhooks/..."
    username: "Deleterr"
    avatar_url: "https://example.com/deleterr-avatar.png"
```

### Slack

Send notifications to Slack via Incoming Webhooks.

{slack_table}

```yaml
notifications:
  slack:
    webhook_url: "https://hooks.slack.com/services/..."
    channel: "#media-cleanup"
    username: "Deleterr"
    icon_emoji: ":wastebasket:"
```

### Telegram

Send notifications via Telegram Bot API.

{telegram_table}

```yaml
notifications:
  telegram:
    bot_token: "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
    chat_id: "-1001234567890"
    parse_mode: "MarkdownV2"
```

### Webhook (Generic)

Send JSON payloads to any HTTP endpoint for custom integrations.

{webhook_table}

```yaml
notifications:
  webhook:
    url: "https://example.com/webhook"
    method: "POST"
    headers:
      Authorization: "Bearer your-token"
      Content-Type: "application/json"
    timeout: 30
```

### Email

Send notifications via SMTP email with HTML formatting.

{email_table}

```yaml
notifications:
  email:
    smtp_server: "smtp.gmail.com"
    smtp_port: 587
    smtp_username: !env SMTP_USERNAME
    smtp_password: !env SMTP_PASSWORD
    use_tls: true
    from_address: "deleterr@yourdomain.com"
    to_addresses:
      - "admin@yourdomain.com"
    subject: "Deleterr Run Complete"
```

**Gmail Setup:**
1. Enable [2-Step Verification](https://myaccount.google.com/signinoptions/two-step-verification) on your Google account
2. Create an [App Password](https://myaccount.google.com/apppasswords) for Deleterr
3. Use the app password as `smtp_password`

### Leaving Soon Notifications

User-facing notifications specifically for items scheduled for deletion. These are **separate** from the admin deletion notifications above - they're designed to alert your users about content they should watch before it's removed.

!!! note
    Providers configured under `leaving_soon` do NOT inherit from the parent notification config. You must explicitly configure each provider you want to use.

{leaving_soon_notification_table}

**Basic example (email only):**
```yaml
notifications:
  # Admin notifications (what was deleted)
  discord:
    webhook_url: !env DISCORD_ADMIN_WEBHOOK

  # User-facing leaving soon notifications
  leaving_soon:
    subject: "🎬 Content leaving your Plex server soon!"
    email:
      smtp_server: "smtp.gmail.com"
      smtp_port: 587
      smtp_username: !env SMTP_USERNAME
      smtp_password: !env SMTP_PASSWORD
      use_tls: true
      from_address: "plex@yourdomain.com"
      to_addresses:
        - "user1@example.com"
        - "user2@example.com"
        - "family@example.com"
```

**With custom template:**
```yaml
notifications:
  leaving_soon:
    template: "/config/my-custom-template.html"
    subject: "Watch Before It's Gone!"
    email:
      smtp_server: "smtp.gmail.com"
      # ... email settings
```

**Multiple providers for leaving soon:**
```yaml
notifications:
  leaving_soon:
    email:
      # Email for detailed notifications
      smtp_server: "smtp.gmail.com"
      # ... email settings
    discord:
      # Discord for quick alerts
      webhook_url: !env DISCORD_USERS_WEBHOOK
```

The built-in template includes:
- Warning explaining items will be removed
- Tip box explaining how watching keeps items
- Grouped sections for Movies and TV Shows
- Links to Plex (if configured)
- Links to Overseerr for re-requesting (if configured)

### Multiple Providers

You can configure multiple notification providers simultaneously:

```yaml
notifications:
  enabled: true
  notify_on_dry_run: false
  min_deletions_to_notify: 1
  discord:
    webhook_url: !env DISCORD_WEBHOOK_URL
  telegram:
    bot_token: !env TELEGRAM_BOT_TOKEN
    chat_id: !env TELEGRAM_CHAT_ID
```

### Testing Notifications

Test your notification configuration with sample data before relying on it:

```bash
# Test leaving_soon notifications (default)
docker run --rm -v ./config:/config deleterr python -m scripts.test_notifications

# Test run summary notifications
docker run --rm -v ./config:/config deleterr python -m scripts.test_notifications --type run_summary

# Test a specific provider only
docker run --rm -v ./config:/config deleterr python -m scripts.test_notifications --provider email

# Preview without sending (dry run)
docker run --rm -v ./config:/config deleterr python -m scripts.test_notifications --dry-run

# Show configuration status
docker run --rm -v ./config:/config deleterr python -m scripts.test_notifications --status
```

The test script sends notifications with sample movie and TV show data so you can verify:
- Email formatting and delivery
- Discord/Slack/Telegram message appearance
- Webhook payload structure
- Template rendering (for leaving_soon)

---

## Libraries

Configuration for each Plex library to manage.

{library_table}

*One of `radarr` or `sonarr` is required per library.

### Disk Size Threshold

{disk_table}

### Sort Configuration

{sort_table}

### Leaving Soon

Mark media scheduled for deletion with a Plex collection and/or labels.
This implements a "death row" pattern where items are tagged on one run, then deleted on the next run.

{leaving_soon_table}

**Collection Settings:**

{leaving_soon_collection_table}

**Label Settings:**

{leaving_soon_labels_table}

**How it works:**
1. **First run:** Items matching deletion criteria are tagged (added to collection/labeled), but NOT deleted
2. **Subsequent runs:** Previously tagged items are deleted, new candidates are tagged
3. This gives users a "warning period" to watch items before they're deleted

**Basic configuration with collection only:**
```yaml
libraries:
  - name: "Movies"
    radarr: "Radarr"
    action_mode: "delete"
    max_actions_per_run: 20
    preview_next: 10
    leaving_soon:
      collection:
        name: "Leaving Soon"
```

**With both collection and labels:**
```yaml
libraries:
  - name: "Movies"
    radarr: "Radarr"
    action_mode: "delete"
    max_actions_per_run: 20
    preview_next: 10
    leaving_soon:
      collection:
        name: "Leaving Soon"
      labels:
        name: "leaving-soon"
```

!!! warning
    `preview_next` cannot be set to `0` when `leaving_soon` is configured, as the feature needs to tag upcoming deletions.

```yaml
libraries:
  - name: "Movies"
    radarr: "Radarr"
    action_mode: "delete"
    watch_status: "watched"
    last_watched_threshold: 90
    added_at_threshold: 180
    apply_last_watch_threshold_to_collections: true
    add_list_exclusion_on_delete: true
    max_actions_per_run: 50
    disk_size_threshold:
      - path: "/data/media"
        threshold: "1TB"
    sort:
      field: "size"
      order: "desc"
```

---

## Exclusions

Protect media from deletion based on metadata, Trakt lists, JustWatch, or Radarr-specific criteria.

### Metadata Exclusions

{exclusions_table}

```yaml
exclude:
  titles: ["Forrest Gump", "The Godfather"]
  plex_labels: ["favorite", "keep"]
  genres: ["documentary"]
  collections: ["Marvel Cinematic Universe"]
  actors: ["Tom Hanks"]
  directors: ["Christopher Nolan"]
  studios: ["Studio Ghibli", "A24"]
  release_years: 2
```

### Trakt Exclusions

{trakt_exclusions_table}

Supports official lists and user lists:

```yaml
exclude:
  trakt:
    max_items_per_list: 200
    lists:
      # Official Trakt lists
      - "https://trakt.tv/movies/trending"
      - "https://trakt.tv/movies/popular"
      - "https://trakt.tv/movies/watched/yearly"
      # User lists
      - "https://trakt.tv/users/justin/lists/imdb-top-rated-movies"
```

### JustWatch Exclusions

Exclude based on streaming availability. `available_on` and `not_available_on` are mutually exclusive.

{justwatch_exclusions_table}

Common providers: `netflix`, `amazon`, `disneyplus`, `hbomax`, `max`, `hulu`, `appletvplus`, `peacocktv`, `paramountplus`, `crunchyroll`, `stan`, `binge`

**Keep media that's available on streaming:**
```yaml
exclude:
  justwatch:
    country: "US"
    available_on: ["netflix", "disneyplus"]
```

**Keep media NOT available on streaming:**
```yaml
exclude:
  justwatch:
    country: "US"
    not_available_on: ["any"]
```

### Radarr Exclusions (Movies Only)

Exclude based on Radarr-specific metadata. Only applies to movie libraries.

{radarr_exclusions_table}

```yaml
exclude:
  radarr:
    tags: ["4K", "keep", "favorite"]
    quality_profiles: ["Remux-2160p", "Bluray-2160p"]
    paths: ["/data/media/4k", "/data/protected"]
    monitored: true
```

### Sonarr Exclusions (TV Shows Only)

Exclude based on Sonarr-specific metadata. Only applies to TV show libraries.

{sonarr_exclusions_table}

**Protect continuing shows from deletion:**
```yaml
exclude:
  sonarr:
    status: ["continuing", "upcoming"]
```

**Protect tagged shows:**
```yaml
exclude:
  sonarr:
    tags: ["4K", "keep", "favorite"]
    quality_profiles: ["Remux-2160p"]
    paths: ["/data/media/4k"]
    monitored: true
```

### Overseerr Exclusions

Exclude or include media based on Overseerr request status. Requires global `overseerr` config.

{overseerr_exclusions_table}

**Protect requested content:**
```yaml
exclude:
  overseerr:
    mode: "exclude"
    include_pending: true
```

**Cleanup old user requests:**
```yaml
exclude:
  overseerr:
    mode: "include_only"
    users: ["user1"]
    request_status: ["approved"]
    min_request_age_days: 90
    update_status: true
```

---

## Complete Example

```yaml
dry_run: true
ssl_verify: false
action_delay: 10
plex_library_scan_after_actions: false

# Built-in scheduler (remove this section to use external scheduler like Ofelia)
scheduler:
  enabled: true
  schedule: "weekly"
  timezone: "UTC"

# Discord notifications for deletion alerts
notifications:
  enabled: true
  notify_on_dry_run: true
  include_preview: true
  min_deletions_to_notify: 1
  discord:
    webhook_url: !env DISCORD_WEBHOOK_URL
    username: "Deleterr"

plex:
  url: "http://localhost:32400"
  token: "YOUR_PLEX_TOKEN"

tautulli:
  url: "http://localhost:8181"
  api_key: "YOUR_TAUTULLI_API_KEY"

radarr:
  - name: "Radarr"
    url: "http://localhost:7878"
    api_key: "YOUR_RADARR_API_KEY"

sonarr:
  - name: "Sonarr"
    url: "http://localhost:8989"
    api_key: "YOUR_SONARR_API_KEY"

trakt:
  client_id: "YOUR_TRAKT_CLIENT_ID"
  client_secret: "YOUR_TRAKT_CLIENT_SECRET"

justwatch:
  country: "US"

libraries:
  - name: "Movies"
    radarr: "Radarr"
    action_mode: "delete"
    watch_status: "watched"
    last_watched_threshold: 90
    added_at_threshold: 180
    apply_last_watch_threshold_to_collections: true
    add_list_exclusion_on_delete: true
    max_actions_per_run: 20
    sort:
      field: "size"
      order: "desc"
    exclude:
      plex_labels: ["favorite", "keep"]
      genres: ["documentary"]
      release_years: 2
      trakt:
        max_items_per_list: 100
        lists:
          - "https://trakt.tv/movies/trending"
          - "https://trakt.tv/movies/popular"
      justwatch:
        not_available_on: ["any"]
      radarr:
        tags: ["keep"]
        monitored: true

  - name: "TV Shows"
    sonarr: "Sonarr"
    series_type: "standard"
    action_mode: "delete"
    last_watched_threshold: 180
    added_at_threshold: 365
    max_actions_per_run: 10
    exclude:
      plex_labels: ["favorite"]
      trakt:
        lists:
          - "https://trakt.tv/shows/trending"
      sonarr:
        status: ["continuing", "upcoming"]
        tags: ["keep"]
        monitored: true
```

---

## Next Steps

- [Templates](templates.md) - Ready-to-use configuration examples
- [Getting Started](getting-started.md) - Installation guide
"""

    # Generate general settings table (subset of DeleterrConfig)
    general_fields = ["dry_run", "ssl_verify", "action_delay",
                      "plex_library_scan_after_actions", "tautulli_library_scan_after_actions"]
    general_lines = ["| Property | Type | Required | Default | Description |"]
    general_lines.append("|----------|------|----------|---------|-------------|")
    for name in general_fields:
        field_info = DeleterrConfig.model_fields[name]
        type_str = get_type_str(field_info.annotation)
        required = is_required(field_info)
        default = get_default_str(field_info)
        desc = field_info.description or ""
        general_lines.append(f"| `{name}` | {type_str} | {required} | {default} | {desc} |")
    general_table = "\n".join(general_lines)

    # Generate library table without nested objects
    library_fields = ["name", "radarr", "sonarr", "series_type", "action_mode", "watch_status",
                      "last_watched_threshold", "added_at_threshold", "apply_last_watch_threshold_to_collections",
                      "add_list_exclusion_on_delete", "max_actions_per_run", "preview_next", "disk_size_threshold", "sort",
                      "leaving_soon"]
    library_lines = ["| Property | Type | Required | Default | Description |"]
    library_lines.append("|----------|------|----------|---------|-------------|")
    for name in library_fields:
        field_info = LibraryConfig.model_fields[name]
        type_str = get_type_str(field_info.annotation)
        # Simplify complex types
        if "DiskSizeThreshold" in type_str:
            type_str = "array"
        if "SortConfig" in type_str:
            type_str = "object"
        if "LeavingSoonConfig" in type_str:
            type_str = "object"
        required = is_required(field_info)
        default = get_default_str(field_info)
        desc = field_info.description or ""
        library_lines.append(f"| `{name}` | {type_str} | {required} | {default} | {desc} |")
    library_table = "\n".join(library_lines)

    # Generate exclusions table without nested objects
    exclusion_fields = ["titles", "plex_labels", "genres", "collections", "actors",
                        "producers", "directors", "writers", "studios", "release_years"]
    exclusion_lines = ["| Property | Type | Required | Default | Description |"]
    exclusion_lines.append("|----------|------|----------|---------|-------------|")
    for name in exclusion_fields:
        field_info = Exclusions.model_fields[name]
        type_str = get_type_str(field_info.annotation)
        required = is_required(field_info)
        default = get_default_str(field_info)
        desc = field_info.description or ""
        exclusion_lines.append(f"| `{name}` | {type_str} | {required} | {default} | {desc} |")
    exclusions_table = "\n".join(exclusion_lines)

    # Generate notifications table (general settings only)
    notifications_fields = ["enabled", "notify_on_dry_run", "include_preview", "min_deletions_to_notify"]
    notifications_lines = ["| Property | Type | Required | Default | Description |"]
    notifications_lines.append("|----------|------|----------|---------|-------------|")
    for name in notifications_fields:
        field_info = NotificationConfig.model_fields[name]
        type_str = get_type_str(field_info.annotation)
        required = is_required(field_info)
        default = get_default_str(field_info)
        desc = field_info.description or ""
        notifications_lines.append(f"| `{name}` | {type_str} | {required} | {default} | {desc} |")
    notifications_table = "\n".join(notifications_lines)

    # Format the document
    doc = doc.format(
        general_table=general_table,
        plex_table=generate_table(PlexConfig),
        tautulli_table=generate_table(TautulliConfig),
        radarr_table=generate_table(RadarrInstance),
        sonarr_table=generate_table(SonarrInstance),
        trakt_table=generate_table(TraktConfig),
        justwatch_table=generate_table(JustWatchGlobalConfig),
        overseerr_table=generate_table(OverseerrConfig),
        scheduler_table=generate_table(SchedulerConfig),
        notifications_table=notifications_table,
        discord_table=generate_table(DiscordNotificationConfig),
        slack_table=generate_table(SlackNotificationConfig),
        telegram_table=generate_table(TelegramNotificationConfig),
        webhook_table=generate_table(WebhookNotificationConfig),
        email_table=generate_table(EmailNotificationConfig),
        leaving_soon_notification_table=generate_table(LeavingSoonNotificationConfig, "leaving_soon."),
        library_table=library_table,
        disk_table=generate_table(DiskSizeThreshold),
        sort_table=generate_table(SortConfig),
        leaving_soon_table=generate_table(LeavingSoonConfig, "leaving_soon."),
        leaving_soon_collection_table=generate_table(LeavingSoonCollectionConfig, "leaving_soon.collection."),
        leaving_soon_labels_table=generate_table(LeavingSoonLabelConfig, "leaving_soon.labels."),
        exclusions_table=exclusions_table,
        trakt_exclusions_table=generate_table(TraktExclusions, "trakt."),
        justwatch_exclusions_table=generate_table(JustWatchExclusions, "justwatch."),
        radarr_exclusions_table=generate_table(RadarrExclusions, "radarr."),
        sonarr_exclusions_table=generate_table(SonarrExclusions, "sonarr."),
        overseerr_exclusions_table=generate_table(OverseerrExclusions, "overseerr."),
    )

    output_path.write_text(doc, encoding="utf-8")
    print(f"Generated {output_path}")
    print(f"Schema source: app/schema.py")


if __name__ == "__main__":
    main()
