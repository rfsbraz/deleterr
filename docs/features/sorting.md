# Sorting & Prioritization

Sorting controls which items get deleted first when `max_actions_per_run` limits the number of deletions per run. Without sorting, deletion order is undefined.

## Why Sorting Matters

If your library has 100 items eligible for deletion but `max_actions_per_run: 10`, sorting determines which 10 get deleted. You might want to delete the largest files first to reclaim the most space, or the lowest-rated content first to keep better media longer.

## Configuration

```yaml
libraries:
  - name: "Movies"
    radarr: "Radarr"
    action_mode: "delete"
    max_actions_per_run: 20
    sort:
      field: "size"
      order: "desc"  # Largest first
```

## Sort Fields

| Field | Description | Applies To |
|-------|-------------|------------|
| `title` | Alphabetical by sort title | Movies, TV Shows |
| `size` | File size on disk | Movies, TV Shows |
| `release_year` | Year of release | Movies, TV Shows |
| `runtime` | Duration in minutes | Movies |
| `added_date` | Date added to Radarr/Sonarr | Movies, TV Shows |
| `rating` | IMDB or TMDB rating | Movies, TV Shows |
| `seasons` | Number of seasons | TV Shows |
| `episodes` | Total episode count | TV Shows |
| `last_watched` | Days since last watch | Movies, TV Shows |

## Multi-Level Sorting

Sort by multiple fields using comma-separated values. The first field is the primary sort; ties are broken by subsequent fields.

```yaml
sort:
  field: "last_watched,size"
  order: "desc,desc"
```

If fewer orders than fields are provided, the last order is reused:

```yaml
sort:
  field: "last_watched,size,title"
  order: "desc"  # All three fields sort descending
```

## last_watched Special Behavior

When sorting by `last_watched`, **unwatched items always sort first** regardless of the order setting. The `order` only affects how watched items are sorted among themselves.

This ensures unwatched content is prioritized for deletion before recently-watched content -- the logic being that if nobody has ever watched it, it's a better candidate for removal than something someone watched recently.

## Common Strategies

### Largest Files First

Reclaim the most disk space per deletion:

```yaml
sort:
  field: "size"
  order: "desc"
```

### Oldest Content First

Delete media that was released longest ago:

```yaml
sort:
  field: "release_year"
  order: "asc"
```

### Lowest Rated First

Keep the best-rated content longest:

```yaml
sort:
  field: "rating"
  order: "asc"
```

### Unwatched + Largest First

Prioritize unwatched content, then largest files among those:

```yaml
sort:
  field: "last_watched,size"
  order: "desc,desc"
```

### TV Shows by Episode Count

Delete shows with the most episodes first (reclaim space from long-running series):

```yaml
sort:
  field: "episodes"
  order: "desc"
```

See [Configuration Reference](../CONFIGURATION.md) for the full field reference.
