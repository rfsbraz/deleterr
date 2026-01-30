---
title: Configuration Reference
---

# Configuration Reference

Complete reference for all Deleterr configuration options.

> **Note**: This documentation is auto-generated from the [Pydantic schema](../app/schema.py).
> Run `python -m scripts.generate_docs` to regenerate after schema changes.

---

* TOC
{:toc}

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

> **Note**: If an environment variable is not set, Deleterr will fail to start with an error message indicating which variable is missing.

---

## General Settings

Root-level settings that apply globally.

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `dry_run` | boolean | No | `true` | If true, actions are only logged, not performed |
| `ssl_verify` | boolean | No | `false` | Enable SSL certificate verification for API connections |
| `action_delay` | integer | No | `0` | Delay (in seconds) between actions. Increase if Plex/Sonarr/Radarr timeout on remote mounts |
| `plex_library_scan_after_actions` | boolean | No | `false` | Trigger a Plex library scan after actions are performed |
| `tautulli_library_scan_after_actions` | boolean | No | `false` | Trigger a Tautulli library scan after actions are performed |

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

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `url` | string | Yes | - | URL of your Plex server |
| `token` | string | Yes | - | Plex authentication token. [How to get](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/) |

```yaml
plex:
  url: "http://localhost:32400"
  token: "YOUR_PLEX_TOKEN"
```

---

## Tautulli

**Required.** Connection details for Tautulli (watch history tracking).

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `url` | string | Yes | - | URL of your Tautulli server |
| `api_key` | string | Yes | - | Tautulli API key |

```yaml
tautulli:
  url: "http://localhost:8181"
  api_key: "YOUR_TAUTULLI_API_KEY"
```

---

## Radarr

Connection settings for one or more Radarr instances.

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `name` | string | Yes | - | Identifier for this Radarr instance (used in library config) |
| `url` | string | Yes | - | URL of your Radarr server |
| `api_key` | string | Yes | - | Radarr API key |

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

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `name` | string | Yes | - | Identifier for this Sonarr instance (used in library config) |
| `url` | string | Yes | - | URL of your Sonarr server |
| `api_key` | string | Yes | - | Sonarr API key |

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

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `client_id` | string | Yes | - | Trakt client ID. Create an app at [trakt.tv/oauth/applications](https://trakt.tv/oauth/applications) |
| `client_secret` | string | Yes | - | Trakt client secret |

Create an application at [trakt.tv/oauth/applications](https://trakt.tv/oauth/applications) to get credentials.

```yaml
trakt:
  client_id: "YOUR_TRAKT_CLIENT_ID"
  client_secret: "YOUR_TRAKT_CLIENT_SECRET"
```

---

## JustWatch

Optional. Global settings for streaming availability lookups.

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `country` | string | No | - | ISO 3166-1 alpha-2 country code (e.g., US, GB, DE) |
| `language` | string | No | `"en"` | Language code for API responses |

```yaml
justwatch:
  country: "US"
  language: "en"
```

---

## Overseerr

Optional. Connection settings for [Overseerr](https://overseerr.dev/) request-based exclusions.

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `url` | string | Yes | - | URL of your Overseerr server |
| `api_key` | string | Yes | - | Overseerr API key. Found in Overseerr Settings → General |

```yaml
overseerr:
  url: "http://localhost:5055"
  api_key: "YOUR_OVERSEERR_API_KEY"
```

---

## Scheduler

Optional. Built-in scheduler as an alternative to external schedulers like Ofelia or system cron.

When enabled, Deleterr runs as a long-lived process and executes cleanup on the configured schedule. When disabled (default), Deleterr runs once and exits, suitable for triggering via external schedulers.

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `enabled` | boolean | No | `false` | Enable built-in scheduler. When false, Deleterr runs once and exits (for external schedulers) |
| `schedule` | string | No | `"weekly"` | Cron expression or preset (hourly, daily, weekly, monthly). Examples: 'weekly', '0 3 * * 0' (Sunday 3 AM) |
| `timezone` | string | No | `"UTC"` | Timezone for schedule (e.g., 'America/New_York', 'Europe/London') |
| `run_on_startup` | boolean | No | `false` | Run immediately when container starts, in addition to scheduled runs |

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

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `name` | string | Yes | - | Name of the Plex library (must match exactly) |
| `radarr` | string | No | - | Name of the Radarr instance to use. Mutually exclusive with sonarr |
| `sonarr` | string | No | - | Name of the Sonarr instance to use. Mutually exclusive with radarr |
| `series_type` | string (`standard`, `anime`, `daily`) | No | `"standard"` | Series type filter for Sonarr libraries |
| `action_mode` | string (`delete`) | Yes | - | Action to perform on matching media |
| `watch_status` | string (`watched`, `unwatched`) | No | - | Filter by watch status. If not set, both watched and unwatched media are considered |
| `last_watched_threshold` | integer | No | - | Days since last watch. Media watched within this period is protected |
| `added_at_threshold` | integer | No | - | Days since added to Plex. Media added within this period is protected |
| `apply_last_watch_threshold_to_collections` | boolean | No | `false` | Apply last watched threshold to all items in the same collection |
| `add_list_exclusion_on_delete` | boolean | No | `false` | Prevent Radarr from re-importing deleted media from lists. Radarr only |
| `max_actions_per_run` | integer | No | `10` | Maximum deletions per run |
| `preview_next` | integer | No | - | Number of items to preview for next run. Defaults to max_actions_per_run. Set to 0 to disable |
| `disk_size_threshold` | array | No | `[]` | Only delete when disk space is below threshold |
| `sort` | object | No | - | Sorting configuration for deletion order |

*One of `radarr` or `sonarr` is required per library.

### Disk Size Threshold

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `path` | string | Yes | - | Path accessible by Sonarr/Radarr to check disk space |
| `threshold` | string | Yes | - | Size threshold. Units: B, KB, MB, GB, TB, PB, EB |

### Sort Configuration

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `field` | string (`title`, `size`, `release_year`, `runtime`, `added_date`, `rating`, `seasons`, `episodes`) | No | `"title"` | Field to sort by: title, size, release_year, runtime, added_date, rating, seasons, episodes |
| `order` | string (`asc`, `desc`) | No | `"asc"` | Sort order: asc (ascending), desc (descending) |

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

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `titles` | array[string] | No | `[]` | Exact titles to exclude |
| `plex_labels` | array[string] | No | `[]` | Plex labels to exclude |
| `genres` | array[string] | No | `[]` | Genres to exclude |
| `collections` | array[string] | No | `[]` | Collections to exclude |
| `actors` | array[string] | No | `[]` | Actors to exclude |
| `producers` | array[string] | No | `[]` | Producers to exclude |
| `directors` | array[string] | No | `[]` | Directors to exclude |
| `writers` | array[string] | No | `[]` | Writers to exclude |
| `studios` | array[string] | No | `[]` | Studios to exclude |
| `release_years` | integer | No | `0` | Exclude media released within last X years |

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

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `trakt.max_items_per_list` | integer | No | `100` | Maximum items to fetch from each Trakt list |
| `trakt.lists` | array[string] | No | `[]` | Trakt list URLs to exclude. Supports official lists (trending, popular) and user lists |

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

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `justwatch.country` | string | No | - | Override global country setting for this library |
| `justwatch.language` | string | No | - | Override global language setting for this library |
| `justwatch.available_on` | array[string] | No | - | Exclude media available on these providers. Use ['any'] for any service. Mutually exclusive with not_available_on |
| `justwatch.not_available_on` | array[string] | No | - | Exclude media NOT available on these providers. Mutually exclusive with available_on |

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

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `radarr.tags` | array[string] | No | `[]` | Radarr tags to exclude (case-insensitive) |
| `radarr.quality_profiles` | array[string] | No | `[]` | Quality profiles to exclude (exact match) |
| `radarr.paths` | array[string] | No | `[]` | Paths to exclude (substring match) |
| `radarr.monitored` | boolean | No | - | True to exclude monitored movies, False to exclude unmonitored |

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

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `sonarr.status` | array[string] | No | `[]` | Sonarr series status to exclude: continuing, ended, upcoming, deleted |
| `sonarr.tags` | array[string] | No | `[]` | Sonarr tags to exclude (case-insensitive) |
| `sonarr.quality_profiles` | array[string] | No | `[]` | Quality profiles to exclude (exact match) |
| `sonarr.paths` | array[string] | No | `[]` | Paths to exclude (substring match) |
| `sonarr.monitored` | boolean | No | - | True to exclude monitored shows, False to exclude unmonitored |

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

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `overseerr.mode` | string (`exclude`, `include_only`) | No | `"exclude"` | How to handle requested media. `exclude` protects requested items from deletion. `include_only` deletes ONLY requested items |
| `overseerr.users` | array[string] | No | `[]` | Only consider requests from these users (username, email, or Plex username). If empty, all requests are considered |
| `overseerr.include_pending` | boolean | No | `true` | Whether to include pending (not yet approved) requests |
| `overseerr.request_status` | array[string] | No | `[]` | Only consider requests with these statuses: `pending`, `approved`, `declined`. If empty, all statuses are considered |
| `overseerr.min_request_age_days` | integer | No | `0` | Only consider requests older than this many days |
| `overseerr.update_status` | boolean | No | `false` | After deletion, mark the media as deleted in Overseerr so it can be requested again |

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
      sonarr:
        status: ["continuing", "upcoming"]
        tags: ["keep"]
        monitored: true
```

---

## Next Steps

- [Templates](templates) - Ready-to-use configuration examples
- [Getting Started](getting-started) - Installation guide
