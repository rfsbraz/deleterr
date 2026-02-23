# Seerr / Overseerr

Integrate with [Seerr](https://seerr.dev/) (or [Overseerr](https://overseerr.dev/)) to make deletion decisions based on user requests. Deleterr supports two capabilities:

1. **Exclude or target media** based on whether it was requested through Seerr
2. **Mark deleted media** in Seerr so users can request it again

!!! note "Overseerr Compatibility"
    Deleterr works with both Seerr and Overseerr -- they share the same API. The `overseerr` config key is still accepted for backward compatibility but `seerr` is now the recommended key.

## Prerequisites

1. A running Seerr (or Overseerr) instance
2. API key from Seerr Settings > General

## Setup

### 1. Add global Seerr connection

```yaml
seerr:
  url: "http://localhost:5055"
  api_key: "YOUR_SEERR_API_KEY"
```

### 2. Add Seerr exclusions to your library

```yaml
libraries:
  - name: "Movies"
    radarr: "Radarr"
    action_mode: "delete"
    exclude:
      seerr:
        mode: "exclude"
```

## Modes

### Exclude Mode (default)

Protects requested media from deletion. Use this when you want to keep content that users asked for.

```yaml
exclude:
  seerr:
    mode: "exclude"
```

**Use case**: "Don't delete movies that someone specifically requested."

### Include-Only Mode

Only deletes media that was requested through Seerr. Everything else is skipped.

```yaml
exclude:
  seerr:
    mode: "include_only"
```

**Use case**: "Only clean up content that came in through Seerr -- leave manually added content alone."

## Filtering Options

### Filter by User

Only consider requests from specific users (matched by username, email, or Plex username):

```yaml
exclude:
  seerr:
    mode: "exclude"
    users: ["admin", "family-member"]
```

### Filter by Request Status

Only consider requests with specific statuses (`pending`, `approved`, `declined`):

```yaml
exclude:
  seerr:
    mode: "exclude"
    request_status: ["approved"]
```

### Include Pending Requests

Control whether pending (not yet approved) requests count:

```yaml
exclude:
  seerr:
    mode: "exclude"
    include_pending: false  # Only protect approved requests
```

### Minimum Request Age

Only consider requests older than a certain number of days. This gives users a window to watch before the protection expires:

```yaml
exclude:
  seerr:
    mode: "exclude"
    min_request_age_days: 30  # Requests older than 30 days can be deleted
```

## Post-Deletion: Update Status

When `update_status` is enabled, Deleterr marks deleted media in Seerr so it can be requested again:

```yaml
exclude:
  seerr:
    mode: "exclude"
    update_status: true
```

Without this, deleted media still shows as "available" in Seerr and users can't re-request it.

## Full Example

```yaml
seerr:
  url: "http://localhost:5055"
  api_key: "YOUR_SEERR_API_KEY"

libraries:
  - name: "Movies"
    radarr: "Radarr"
    action_mode: "delete"
    last_watched_threshold: 90
    added_at_threshold: 180
    max_actions_per_run: 20
    exclude:
      seerr:
        mode: "exclude"
        include_pending: true
        request_status: ["approved", "pending"]
        update_status: true

  - name: "TV Shows"
    sonarr: "Sonarr"
    series_type: "standard"
    action_mode: "delete"
    last_watched_threshold: 90
    added_at_threshold: 180
    max_actions_per_run: 20
    exclude:
      seerr:
        mode: "exclude"
        users: ["admin"]
        min_request_age_days: 60
        update_status: true
```

## Migrating from `overseerr` config key

If you're upgrading from a version that used the `overseerr` config key, your existing config will continue to work. Deleterr automatically migrates `overseerr` to `seerr` at startup with a deprecation notice. To silence the notice, rename your config keys:

```yaml
# Before (still works, but deprecated)
overseerr:
  url: "http://localhost:5055"
  api_key: "YOUR_API_KEY"

# After (recommended)
seerr:
  url: "http://localhost:5055"
  api_key: "YOUR_API_KEY"
```

The same applies to library-level exclusions: rename `exclude.overseerr` to `exclude.seerr`.

## Configuration Reference

| Option | Default | Description |
|--------|---------|-------------|
| `mode` | `"exclude"` | `exclude` protects requested items; `include_only` deletes only requested items |
| `users` | `[]` | Filter by username, email, or Plex username. Empty = all users |
| `include_pending` | `true` | Whether pending requests count |
| `request_status` | `[]` | Filter by status: `pending`, `approved`, `declined`. Empty = all |
| `min_request_age_days` | `0` | Only consider requests older than this many days |
| `update_status` | `false` | Mark deleted media in Seerr so it can be re-requested |

See [Configuration Reference](../CONFIGURATION.md) for the full field reference.
