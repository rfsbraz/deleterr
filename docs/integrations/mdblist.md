# MDBList

Protect media that appears on [MDBList](https://mdblist.com/) lists. MDBList aggregates lists from IMDB, TMDB, Trakt, Letterboxd, and more into a single platform -- so you can reuse the same lists you already use for Radarr/Sonarr imports as exclusion rules.

## Prerequisites

1. Create an account at [mdblist.com](https://mdblist.com/)
2. Get your API key from [mdblist.com/preferences/](https://mdblist.com/preferences/)

## Setup

### 1. Add global MDBList credentials

```yaml
mdblist:
  api_key: "YOUR_MDBLIST_API_KEY"
```

### 2. Add MDBList exclusions to your library

```yaml
libraries:
  - name: "Movies"
    radarr: "Radarr"
    action_mode: "delete"
    exclude:
      mdblist:
        lists:
          - "https://mdblist.com/lists/linaspuransen/top-250-movies"
          - "https://mdblist.com/lists/username/my-custom-list"
```

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `max_items_per_list` | `1000` | Maximum items to fetch from each list |
| `lists` | `[]` | List of MDBList URLs to exclude |

## URL Format

MDBList list URLs follow the pattern:

```
https://mdblist.com/lists/<username>/<listname>
```

You can find the URL by navigating to any list on mdblist.com and copying the URL from your browser.

## How Matching Works

- **Movies** are matched by TMDB ID
- **TV Shows** are matched by TVDB ID

Items are fetched in pages of 1000 and capped at `max_items_per_list`. If a list has more items than the limit, only the first N items are checked.

## Full Example

```yaml
mdblist:
  api_key: "YOUR_MDBLIST_API_KEY"

libraries:
  - name: "Movies"
    radarr: "Radarr"
    action_mode: "delete"
    last_watched_threshold: 90
    added_at_threshold: 180
    max_actions_per_run: 20
    exclude:
      mdblist:
        max_items_per_list: 2000
        lists:
          - "https://mdblist.com/lists/linaspuransen/top-250-movies"
          - "https://mdblist.com/lists/hdlists/top-ten-pirated-movies-of-the-week"

  - name: "TV Shows"
    sonarr: "Sonarr"
    series_type: "standard"
    action_mode: "delete"
    last_watched_threshold: 90
    added_at_threshold: 180
    max_actions_per_run: 20
    exclude:
      mdblist:
        lists:
          - "https://mdblist.com/lists/garycrawfordgc/top-rated-tv"
```

## Tips

- MDBList is a good alternative to Trakt if you already use MDBList lists to manage your Radarr/Sonarr imports.
- Set `max_items_per_list` higher (e.g., `2000`) for large curated lists.
- Enable `LOG_LEVEL: DEBUG` to confirm which items are being matched against your lists.

See [Configuration Reference](../CONFIGURATION.md) for the full field reference.
