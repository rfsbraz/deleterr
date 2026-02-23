# Multi-Instance Support

Deleterr supports multiple Radarr and Sonarr instances, allowing you to manage separate libraries (e.g., standard and 4K) with different retention policies.

## Use Case

A common setup has separate instances for different quality tiers:

- **Standard Radarr/Sonarr** for 1080p content with aggressive cleanup
- **4K Radarr/Sonarr** for 2160p content with conservative cleanup

Each instance can have different deletion thresholds, exclusions, and limits.

## Setup

### 1. Define Named Instances

List your Radarr and/or Sonarr instances at the top level. Each instance needs a unique `name`:

```yaml
radarr:
  - name: "Radarr"
    url: "http://localhost:7878"
    api_key: "YOUR_RADARR_API_KEY"
  - name: "Radarr 4K"
    url: "http://localhost:7879"
    api_key: "YOUR_RADARR_4K_API_KEY"

sonarr:
  - name: "Sonarr"
    url: "http://localhost:8989"
    api_key: "YOUR_SONARR_API_KEY"
  - name: "Sonarr 4K"
    url: "http://localhost:8990"
    api_key: "YOUR_SONARR_4K_API_KEY"
```

### 2. Reference Instances in Library Blocks

Each library block references an instance by name:

```yaml
libraries:
  - name: "Movies"
    radarr: "Radarr"         # References the instance named "Radarr"
    action_mode: "delete"
    # ...

  - name: "Movies 4K"
    radarr: "Radarr 4K"      # References the instance named "Radarr 4K"
    action_mode: "delete"
    # ...
```

!!! note
    The library `name` must match the exact Plex library name. The `radarr`/`sonarr` value must match an instance `name` defined above.

## Full Example

```yaml
dry_run: true

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
  - name: "Radarr 4K"
    url: "http://localhost:7879"
    api_key: "YOUR_RADARR_4K_API_KEY"

sonarr:
  - name: "Sonarr"
    url: "http://localhost:8989"
    api_key: "YOUR_SONARR_API_KEY"
  - name: "Sonarr 4K"
    url: "http://localhost:8990"
    api_key: "YOUR_SONARR_4K_API_KEY"

libraries:
  # Standard quality - more aggressive cleanup
  - name: "Movies"
    radarr: "Radarr"
    action_mode: "delete"
    last_watched_threshold: 60
    added_at_threshold: 90
    max_actions_per_run: 50

  # 4K - conservative cleanup
  - name: "Movies 4K"
    radarr: "Radarr 4K"
    action_mode: "delete"
    last_watched_threshold: 180
    added_at_threshold: 365
    max_actions_per_run: 10
    exclude:
      radarr:
        tags: ["keep", "favorite"]

  - name: "TV Shows"
    sonarr: "Sonarr"
    series_type: "standard"
    action_mode: "delete"
    last_watched_threshold: 90
    added_at_threshold: 180
    max_actions_per_run: 20

  - name: "TV Shows 4K"
    sonarr: "Sonarr 4K"
    series_type: "standard"
    action_mode: "delete"
    last_watched_threshold: 365
    added_at_threshold: 365
    max_actions_per_run: 5
```

## Tips

- **Different thresholds per tier**: 4K content is harder to re-download, so use longer thresholds and lower `max_actions_per_run`.
- **Instance-specific exclusions**: Use Radarr/Sonarr tag exclusions per instance to protect specific content in one instance but not the other.
- **Disk thresholds per path**: If 4K and standard content are on separate drives, use [disk thresholds](disk-thresholds.md) with different paths.

See the [4K Multi-Instance template](../templates.md#2-4k-multi-instance) for a ready-to-use configuration. See [Configuration Reference](../CONFIGURATION.md) for the full field reference.
