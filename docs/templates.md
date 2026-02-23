# Configuration Templates

Ready-to-use configurations for common scenarios. Copy, paste, and customize.

---

## Docker Compose Examples

=== "Built-in Scheduler (Recommended)"

    Single container with integrated scheduling:

    ```yaml
    version: "3.9"
    services:
      deleterr:
        image: ghcr.io/rfsbraz/deleterr:latest
        container_name: deleterr
        environment:
          LOG_LEVEL: INFO
          TZ: America/New_York
        volumes:
          - ./config:/config
          - ./logs:/config/logs
        restart: unless-stopped
    ```

    Add to your `settings.yaml`:
    ```yaml
    scheduler:
      enabled: true
      schedule: "weekly"
      timezone: "America/New_York"
    ```

=== "External Scheduler (Ofelia)"

    For advanced scheduling with Docker socket access:

    ```yaml
    version: "3.9"
    services:
      deleterr:
        image: ghcr.io/rfsbraz/deleterr:latest
        container_name: deleterr
        environment:
          LOG_LEVEL: INFO
        volumes:
          - ./config:/config
          - ./logs:/config/logs
        restart: no

      scheduler:
        image: mcuadros/ofelia:latest
        container_name: scheduler
        depends_on:
          - deleterr
        command: daemon --docker
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
        restart: unless-stopped
        labels:
          ofelia.job-run.deleterr.schedule: "@weekly"
          ofelia.job-run.deleterr.container: "deleterr"
    ```

---

## 1. Minimal Movies

Basic single-library setup with sensible defaults.

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

libraries:
  - name: "Movies"
    radarr: "Radarr"
    action_mode: "delete"
    last_watched_threshold: 90
    added_at_threshold: 180
    max_actions_per_run: 10
```

**What it does**: Deletes movies watched more than 90 days ago, if they were added more than 180 days ago. Limits to 10 deletions per run.

---

## 2. 4K Multi-Instance

Separate management for standard and 4K libraries.

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
  # Standard quality - more aggressive
  - name: "Movies"
    radarr: "Radarr"
    action_mode: "delete"
    last_watched_threshold: 60
    added_at_threshold: 90
    max_actions_per_run: 50

  # 4K - more conservative
  - name: "Movies 4K"
    radarr: "Radarr 4K"
    action_mode: "delete"
    last_watched_threshold: 180
    added_at_threshold: 365
    max_actions_per_run: 10

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

**What it does**: Manages 4 libraries with different retention policies. 4K content has longer thresholds and lower deletion limits.

---

## 3. Aggressive Disk Management

Size-based sorting with disk thresholds for space-constrained systems.

```yaml
dry_run: true
action_delay: 5

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

libraries:
  - name: "Movies"
    radarr: "Radarr"
    action_mode: "delete"
    last_watched_threshold: 30
    added_at_threshold: 60
    max_actions_per_run: 100
    disk_size_threshold:
      - path: "/data/media"
        threshold: 500GB
    sort:
      field: "size"
      order: "desc"  # Delete largest files first
    exclude:
      release_years: 1  # Keep movies from last year

  - name: "TV Shows"
    sonarr: "Sonarr"
    series_type: "standard"
    action_mode: "delete"
    last_watched_threshold: 30
    added_at_threshold: 60
    max_actions_per_run: 50
    disk_size_threshold:
      - path: "/data/media"
        threshold: 500GB
    sort:
      field: "size"
      order: "desc"
```

**What it does**: Only deletes when disk space falls below 500GB. Prioritizes largest files first. Short retention periods with high deletion limits.

---

## 4. Preservation Focus

Heavy exclusions to protect valuable content.

```yaml
dry_run: true
action_delay: 10

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

trakt:
  client_id: "YOUR_TRAKT_CLIENT_ID"
  client_secret: "YOUR_TRAKT_CLIENT_SECRET"

libraries:
  - name: "Movies"
    radarr: "Radarr"
    action_mode: "delete"
    add_list_exclusion_on_delete: true
    last_watched_threshold: 365
    added_at_threshold: 365
    apply_last_watch_threshold_to_collections: true
    max_actions_per_run: 5
    sort:
      field: "rating"
      order: "asc"  # Delete lowest rated first
    exclude:
      # Metadata exclusions
      plex_labels: ["favorite", "keep", "classic"]
      genres: ["documentary"]
      release_years: 3
      collections:
        - "Marvel Cinematic Universe"
        - "Star Wars Collection"
        - "The Lord of the Rings Collection"
        - "Harry Potter Collection"
        - "DC Extended Universe"
      actors:
        - "Christopher Nolan"
        - "Denis Villeneuve"
      directors:
        - "Christopher Nolan"
        - "Denis Villeneuve"
        - "Quentin Tarantino"
      studios:
        - "Studio Ghibli"
        - "A24"
        - "Pixar"
      # Trakt exclusions
      trakt:
        max_items_per_list: 200
        lists:
          - "https://trakt.tv/movies/trending"
          - "https://trakt.tv/movies/popular"
          - "https://trakt.tv/movies/watched/yearly"
          - "https://trakt.tv/users/justin/lists/imdb-top-rated-movies"
      # Radarr exclusions
      radarr:
        tags: ["keep", "4k", "hdr"]
        quality_profiles: ["Remux-2160p"]
        monitored: true  # Keep monitored movies
```

**What it does**: Extremely conservative deletion with 1-year thresholds, extensive exclusions by metadata/Trakt/Radarr tags, and only 5 deletions per run.

---

## 5. Streaming-Aware

JustWatch integration to keep locally what's not streaming.

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

justwatch:
  country: "US"
  language: "en"

libraries:
  - name: "Movies"
    radarr: "Radarr"
    action_mode: "delete"
    last_watched_threshold: 90
    added_at_threshold: 180
    max_actions_per_run: 20
    exclude:
      justwatch:
        # Keep movies NOT available on streaming (you can only watch them locally)
        not_available_on: ["any"]

  - name: "Streaming Copies"
    radarr: "Radarr"
    action_mode: "delete"
    last_watched_threshold: 30
    added_at_threshold: 90
    max_actions_per_run: 50
    exclude:
      justwatch:
        # Delete freely if available on your streaming services
        available_on: ["netflix", "disneyplus", "amazon", "hbomax", "hulu"]
```

**What it does**:

- Main library: Preserves movies not available on any streaming service
- Streaming copies: More aggressive deletion of content available on your subscribed services

---

## 6. Protect Unwatched Seerr Requests

Keep content that users requested but haven't watched yet.

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

sonarr:
  - name: "Sonarr"
    url: "http://localhost:8989"
    api_key: "YOUR_SONARR_API_KEY"

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
        include_pending: true
        request_status: ["approved", "pending"]
```

**What it does**: Protects all content that was requested through Seerr (approved or pending). Only deletes content that wasn't explicitly requested by a user. This ensures users don't lose content they asked for before they've had a chance to watch it.

### Variations

Protect requests from specific users only:
```yaml
exclude:
  seerr:
    mode: "exclude"
    users: ["admin", "family-member"]
```

Only protect recent requests (give users 30 days to watch):
```yaml
exclude:
  seerr:
    mode: "exclude"
    min_request_age_days: 30  # Requests older than 30 days can be deleted
```

---

## Common Exclusion Patterns

### Protect MCU and Major Franchises

```yaml
exclude:
  collections:
    - "Marvel Cinematic Universe"
    - "DC Extended Universe"
    - "Star Wars Collection"
    - "The Lord of the Rings Collection"
    - "Harry Potter Collection"
    - "James Bond Collection"
    - "Fast & Furious Collection"
    - "Mission: Impossible Collection"
    - "Jurassic Park Collection"
    - "The Matrix Collection"
```

### Protect by Plex Labels

Add labels in Plex, then exclude them:

```yaml
exclude:
  plex_labels:
    - "favorite"
    - "keep"
    - "classic"
    - "family"
    - "rewatch"
```

### Protect Trending/Popular Content

```yaml
trakt:
  client_id: "YOUR_TRAKT_CLIENT_ID"
  client_secret: "YOUR_TRAKT_CLIENT_SECRET"

libraries:
  - name: "Movies"
    exclude:
      trakt:
        max_items_per_list: 100
        lists:
          - "https://trakt.tv/movies/trending"
          - "https://trakt.tv/movies/popular"
          - "https://trakt.tv/movies/watched/weekly"
          - "https://trakt.tv/movies/anticipated"
```

### Protect by Quality (Radarr)

```yaml
exclude:
  radarr:
    tags: ["4k", "hdr", "dolby-vision", "remux"]
    quality_profiles: ["Remux-2160p", "Bluray-2160p"]
    paths: ["/data/media/4k"]
```

### Anime Library Configuration

```yaml
libraries:
  - name: "Anime"
    sonarr: "Sonarr"
    series_type: "anime"  # Important: filters for anime type
    action_mode: "delete"
    last_watched_threshold: 365
    added_at_threshold: 180
    max_actions_per_run: 10
    sort:
      field: "episodes"
      order: "desc"  # Delete shows with most episodes first
    exclude:
      titles:
        - "Dragon Ball"
        - "Dragon Ball Z"
        - "Naruto"
        - "One Piece"
      studios:
        - "Studio Ghibli"
        - "Kyoto Animation"
        - "Madhouse"
      trakt:
        max_items_per_list: 100
        lists:
          - "https://trakt.tv/users/lwerndly/lists/anime-best-series-of-all-time"
```

---

## Next Steps

- [Configuration Reference](CONFIGURATION.md) - Detailed documentation of all options
- [Getting Started](getting-started.md) - Installation and setup guide
- [Exclusions](features/exclusions.md) - Understand how exclusion rules work
- [Sorting & Prioritization](features/sorting.md) - Control deletion order
- [Disk Thresholds](features/disk-thresholds.md) - Only delete when disk space is low
- [Multi-Instance Support](features/multi-instance.md) - Manage 4K and standard libraries separately

### Integration Guides

- [Trakt](integrations/trakt.md) - Protect media on Trakt lists
- [MDBList](integrations/mdblist.md) - Protect media on MDBList lists
- [JustWatch](integrations/justwatch.md) - Streaming availability exclusions
- [Seerr / Overseerr](integrations/overseerr.md) - Request-based exclusions
