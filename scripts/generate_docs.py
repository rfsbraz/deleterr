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
    OverseerrExclusions,
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

    doc = """---
title: Configuration Reference
---

# Configuration Reference

Complete reference for all Deleterr configuration options.

> **Note**: This documentation is auto-generated from the [Pydantic schema](../app/schema.py).
> Run `python -m scripts.generate_docs` to regenerate after schema changes.

---

* TOC
{{:toc}}

---

## General Settings

Root-level settings that apply globally.

{general_table}

```yaml
dry_run: true
ssl_verify: false
action_delay: 25
interactive: false
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

## Libraries

Configuration for each Plex library to manage.

{library_table}

*One of `radarr` or `sonarr` is required per library.

### Disk Size Threshold

{disk_table}

### Sort Configuration

{sort_table}

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
```

---

## Next Steps

- [Templates](templates) - Ready-to-use configuration examples
- [Getting Started](getting-started) - Installation guide
"""

    # Generate general settings table (subset of DeleterrConfig)
    general_fields = ["dry_run", "interactive", "ssl_verify", "action_delay",
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
                      "add_list_exclusion_on_delete", "max_actions_per_run", "disk_size_threshold", "sort"]
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
        library_table=library_table,
        disk_table=generate_table(DiskSizeThreshold),
        sort_table=generate_table(SortConfig),
        exclusions_table=exclusions_table,
        trakt_exclusions_table=generate_table(TraktExclusions, "trakt."),
        justwatch_exclusions_table=generate_table(JustWatchExclusions, "justwatch."),
        radarr_exclusions_table=generate_table(RadarrExclusions, "radarr."),
        overseerr_exclusions_table=generate_table(OverseerrExclusions, "overseerr."),
    )

    output_path.write_text(doc, encoding="utf-8")
    print(f"Generated {output_path}")
    print(f"Schema source: app/schema.py")


if __name__ == "__main__":
    main()
