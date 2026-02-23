# Overseerr / Seerr

Integrate with [Overseerr](https://overseerr.dev/) to make deletion decisions based on user requests. Deleterr supports two capabilities:

1. **Exclude or target media** based on whether it was requested through Overseerr
2. **Mark deleted media** in Overseerr so users can request it again

!!! note "Seerr Compatibility"
    Deleterr works with both Overseerr and [Seerr](https://github.com/jorenn92/maintainerr) -- they share the same API. Use the same configuration for either.

## Prerequisites

1. A running Overseerr (or Seerr) instance
2. API key from Overseerr Settings > General

## Setup

### 1. Add global Overseerr connection

```yaml
overseerr:
  url: "http://localhost:5055"
  api_key: "YOUR_OVERSEERR_API_KEY"
```

### 2. Add Overseerr exclusions to your library

```yaml
libraries:
  - name: "Movies"
    radarr: "Radarr"
    action_mode: "delete"
    exclude:
      overseerr:
        mode: "exclude"
```

## Modes

### Exclude Mode (default)

Protects requested media from deletion. Use this when you want to keep content that users asked for.

```yaml
exclude:
  overseerr:
    mode: "exclude"
```

**Use case**: "Don't delete movies that someone specifically requested."

### Include-Only Mode

Only deletes media that was requested through Overseerr. Everything else is skipped.

```yaml
exclude:
  overseerr:
    mode: "include_only"
```

**Use case**: "Only clean up content that came in through Overseerr -- leave manually added content alone."

## Filtering Options

### Filter by User

Only consider requests from specific users (matched by username, email, or Plex username):

```yaml
exclude:
  overseerr:
    mode: "exclude"
    users: ["admin", "family-member"]
```

### Filter by Request Status

Only consider requests with specific statuses (`pending`, `approved`, `declined`):

```yaml
exclude:
  overseerr:
    mode: "exclude"
    request_status: ["approved"]
```

### Include Pending Requests

Control whether pending (not yet approved) requests count:

```yaml
exclude:
  overseerr:
    mode: "exclude"
    include_pending: false  # Only protect approved requests
```

### Minimum Request Age

Only consider requests older than a certain number of days. This gives users a window to watch before the protection expires:

```yaml
exclude:
  overseerr:
    mode: "exclude"
    min_request_age_days: 30  # Requests older than 30 days can be deleted
```

## Post-Deletion: Update Status

When `update_status` is enabled, Deleterr marks deleted media in Overseerr so it can be requested again:

```yaml
exclude:
  overseerr:
    mode: "exclude"
    update_status: true
```

Without this, deleted media still shows as "available" in Overseerr and users can't re-request it.

## Full Example

```yaml
overseerr:
  url: "http://localhost:5055"
  api_key: "YOUR_OVERSEERR_API_KEY"

libraries:
  - name: "Movies"
    radarr: "Radarr"
    action_mode: "delete"
    last_watched_threshold: 90
    added_at_threshold: 180
    max_actions_per_run: 20
    exclude:
      overseerr:
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
      overseerr:
        mode: "exclude"
        users: ["admin"]
        min_request_age_days: 60
        update_status: true
```

## Configuration Reference

| Option | Default | Description |
|--------|---------|-------------|
| `mode` | `"exclude"` | `exclude` protects requested items; `include_only` deletes only requested items |
| `users` | `[]` | Filter by username, email, or Plex username. Empty = all users |
| `include_pending` | `true` | Whether pending requests count |
| `request_status` | `[]` | Filter by status: `pending`, `approved`, `declined`. Empty = all |
| `min_request_age_days` | `0` | Only consider requests older than this many days |
| `update_status` | `false` | Mark deleted media in Overseerr so it can be re-requested |

See [Configuration Reference](../CONFIGURATION.md) for the full field reference.
