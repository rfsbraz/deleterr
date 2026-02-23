# Trakt

Protect media that appears on [Trakt](https://trakt.tv/) lists. Keep trending, popular, and personally curated content safe from deletion.

## Prerequisites

1. Create a Trakt API application at [trakt.tv/oauth/applications](https://trakt.tv/oauth/applications)
2. Note the **Client ID** and **Client Secret**

## Setup

### 1. Add global Trakt credentials

```yaml
trakt:
  client_id: "YOUR_TRAKT_CLIENT_ID"
  client_secret: "YOUR_TRAKT_CLIENT_SECRET"
```

### 2. Add Trakt exclusions to your library

```yaml
libraries:
  - name: "Movies"
    radarr: "Radarr"
    action_mode: "delete"
    exclude:
      trakt:
        lists:
          - "https://trakt.tv/movies/trending"
          - "https://trakt.tv/movies/popular"
```

## Supported List Types

### Official Lists

Curated by Trakt based on community activity:

```yaml
exclude:
  trakt:
    lists:
      - "https://trakt.tv/movies/trending"
      - "https://trakt.tv/movies/popular"
      - "https://trakt.tv/movies/anticipated"
      - "https://trakt.tv/movies/boxoffice"
      - "https://trakt.tv/shows/trending"
      - "https://trakt.tv/shows/popular"
      - "https://trakt.tv/shows/anticipated"
```

### User Watchlists

A user's personal watchlist:

```yaml
exclude:
  trakt:
    lists:
      - "https://trakt.tv/users/yourusername/watchlist"
```

### Custom User Lists

Any public user list:

```yaml
exclude:
  trakt:
    lists:
      - "https://trakt.tv/users/justin/lists/imdb-top-rated-movies"
      - "https://trakt.tv/users/lwerndly/lists/anime-best-series-of-all-time"
```

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `max_items_per_list` | `100` | Maximum items to fetch from each list |
| `lists` | `[]` | List of Trakt URLs to exclude |

## How Matching Works

- **Movies** are matched by TMDB ID
- **TV Shows** are matched by TVDB ID

## Known Limitations

- **Favorites lists** (`https://trakt.tv/users/.../favorites`) are not supported by the underlying Trakt library. Use custom lists as an alternative.
- **Periodic lists** (e.g., `watched/weekly`, `collected/monthly`) are not currently supported.

## Full Example

```yaml
trakt:
  client_id: "YOUR_TRAKT_CLIENT_ID"
  client_secret: "YOUR_TRAKT_CLIENT_SECRET"

libraries:
  - name: "Movies"
    radarr: "Radarr"
    action_mode: "delete"
    last_watched_threshold: 90
    added_at_threshold: 180
    max_actions_per_run: 20
    exclude:
      trakt:
        max_items_per_list: 200
        lists:
          - "https://trakt.tv/movies/trending"
          - "https://trakt.tv/movies/popular"
          - "https://trakt.tv/users/justin/lists/imdb-top-rated-movies"

  - name: "TV Shows"
    sonarr: "Sonarr"
    series_type: "standard"
    action_mode: "delete"
    last_watched_threshold: 90
    added_at_threshold: 180
    max_actions_per_run: 20
    exclude:
      trakt:
        lists:
          - "https://trakt.tv/shows/trending"
          - "https://trakt.tv/shows/popular"
```

See [Configuration Reference](../CONFIGURATION.md) for the full field reference.
