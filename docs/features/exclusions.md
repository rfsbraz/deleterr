# Exclusions

Exclusions protect media from deletion. If any exclusion rule matches an item, that item is skipped entirely -- exclusions use **OR logic**, so a single match is enough to protect it.

## Quick Reference

| Category | Exclusion Types |
|----------|----------------|
| **Metadata** | `titles`, `genres`, `collections`, `actors`, `directors`, `writers`, `producers`, `studios`, `plex_labels`, `release_years` |
| **Radarr** | `tags`, `quality_profiles`, `paths`, `monitored` |
| **Sonarr** | `status`, `tags`, `quality_profiles`, `paths`, `monitored` |
| **Integrations** | [`trakt`](../integrations/trakt.md), [`mdblist`](../integrations/mdblist.md), [`justwatch`](../integrations/justwatch.md), [`seerr`](../integrations/overseerr.md) |

All exclusions are configured under the `exclude` key inside a library block:

```yaml
libraries:
  - name: "Movies"
    radarr: "Radarr"
    action_mode: "delete"
    exclude:
      # Your exclusion rules here
```

---

## Metadata Exclusions

### Titles

Exact title match (case-insensitive):

```yaml
exclude:
  titles:
    - "Forrest Gump"
    - "The Godfather"
```

### Genres

Match against Plex genre tags (case-insensitive):

```yaml
exclude:
  genres:
    - "documentary"
    - "horror"
```

### Collections

Match against Plex collection names (case-insensitive):

```yaml
exclude:
  collections:
    - "Marvel Cinematic Universe"
    - "Star Wars Collection"
```

### Actors

Match against Plex actor credits (case-insensitive):

```yaml
exclude:
  actors:
    - "Tom Hanks"
    - "Brad Pitt"
```

### Directors

```yaml
exclude:
  directors:
    - "Christopher Nolan"
    - "Denis Villeneuve"
```

### Writers

```yaml
exclude:
  writers:
    - "Aaron Sorkin"
```

### Producers

```yaml
exclude:
  producers:
    - "Steven Spielberg"
```

### Studios

```yaml
exclude:
  studios:
    - "Studio Ghibli"
    - "A24"
```

### Plex Labels

Protect items you've manually labeled in Plex:

```yaml
exclude:
  plex_labels:
    - "favorite"
    - "keep"
    - "classic"
```

!!! tip "Manual Override"
    `plex_labels` is the easiest way to protect individual items. Add a "keep" label to any item in Plex and exclude that label in your config.

### Release Years

Protect media released within the last X years:

```yaml
exclude:
  release_years: 2  # Keep anything released in the last 2 years
```

---

## Radarr Exclusions

These apply only to movie libraries backed by Radarr.

```yaml
exclude:
  radarr:
    tags: ["4K", "keep", "favorite"]         # Case-insensitive tag match
    quality_profiles: ["Remux-2160p"]         # Exact profile name match
    paths: ["/data/media/4k"]                 # Substring match against movie path
    monitored: true                           # true = exclude monitored, false = exclude unmonitored
```

---

## Sonarr Exclusions

These apply only to TV show libraries backed by Sonarr.

```yaml
exclude:
  sonarr:
    status: ["continuing", "upcoming"]        # Series status: continuing, ended, upcoming, deleted
    tags: ["4K", "keep"]                      # Case-insensitive tag match
    quality_profiles: ["Bluray-2160p"]        # Exact profile name match
    paths: ["/data/media/4k"]                 # Substring match against series path
    monitored: true                           # true = exclude monitored, false = exclude unmonitored
```

---

## Integration Exclusions

Deleterr integrates with external services for more advanced exclusion logic:

| Integration | What It Does | API Key Required? |
|-------------|-------------|-------------------|
| [Trakt](../integrations/trakt.md) | Protect media on Trakt lists (trending, popular, user lists) | Yes |
| [MDBList](../integrations/mdblist.md) | Protect media on MDBList lists (aggregates IMDB, TMDB, Trakt, etc.) | Yes |
| [JustWatch](../integrations/justwatch.md) | Protect based on streaming availability | No |
| [Seerr / Overseerr](../integrations/overseerr.md) | Protect or target media based on user requests | Yes |

See each integration page for setup details and configuration options.

---

## Tips

- **OR logic**: Any single exclusion match protects the item. You don't need an item to match all rules.
- **Debug logging**: Set `LOG_LEVEL: DEBUG` to see exactly which exclusion rule is protecting each item.
- **Plex labels as manual override**: The simplest way to protect a specific item is to add a label in Plex and exclude that label.
- **Combine exclusions freely**: Metadata, Radarr/Sonarr, and integration exclusions all work together.

See [Configuration Reference](../CONFIGURATION.md) for the full list of exclusion fields and their types. For ready-to-use patterns, see the [Common Exclusion Patterns](../templates.md#common-exclusion-patterns) section in Templates.
