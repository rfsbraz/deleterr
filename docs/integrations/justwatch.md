# JustWatch

Protect or target media based on streaming availability using [JustWatch](https://www.justwatch.com/). No API key required -- Deleterr queries JustWatch's public API directly.

## How It Works

JustWatch checks whether a title is currently available on streaming services in your country. You can use this to:

- **Keep content that's not streaming anywhere** (you can only watch it locally)
- **Delete content that's available on your streaming subscriptions** (why store it locally?)

## Setup

### 1. Add global JustWatch settings

```yaml
justwatch:
  country: "US"
  language: "en"
```

The `country` field uses [ISO 3166-1 alpha-2](https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2) country codes (e.g., `US`, `GB`, `DE`, `FR`, `AU`).

### 2. Add JustWatch exclusions to your library

JustWatch offers two mutually exclusive modes -- you must pick one per library:

=== "available_on (exclude if streaming)"

    Protect media that is available on specified providers. Items available on these services won't be deleted.

    ```yaml
    exclude:
      justwatch:
        available_on: ["netflix", "disneyplus", "amazon"]
    ```

    **Use case**: "Don't delete movies I can rewatch on Netflix."

=== "not_available_on (exclude if NOT streaming)"

    Protect media that is NOT available on specified providers. Items that can't be streamed won't be deleted.

    ```yaml
    exclude:
      justwatch:
        not_available_on: ["any"]
    ```

    **Use case**: "Keep movies that aren't on any streaming service -- I can only watch them locally."

!!! warning "Mutually Exclusive"
    You cannot use `available_on` and `not_available_on` in the same library. Pick the mode that matches your intent.

## Common Provider Names

| Provider | Technical Name |
|----------|---------------|
| Netflix | `netflix` |
| Amazon Prime Video | `amazon` |
| Disney+ | `disneyplus` |
| HBO Max | `hbomax` |
| Hulu | `hulu` |
| Apple TV+ | `apple` |
| Paramount+ | `paramount` |
| Peacock | `peacock` |
| *Any service* | `any` |

Use `any` as a special value to match any streaming provider.

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `country` | Global setting | Override the global country code for this library |
| `language` | Global setting | Override the global language for this library |
| `available_on` | - | Exclude media available on these providers |
| `not_available_on` | - | Exclude media NOT available on these providers |

## Title Matching

JustWatch searches by title and matches results using:

1. Exact title + exact year
2. Case-insensitive title + exact year
3. Case-insensitive title + 1-year tolerance (release dates vary by region)

If no match is found, the item is not excluded (JustWatch has no opinion on it).

## Rate Limiting

JustWatch may return HTTP 429 (Too Many Requests) if you process many items quickly. When this happens:

- Deleterr logs a warning on the first occurrence
- Subsequent rate-limited items are silently skipped
- The rate limit resets automatically

If you frequently hit rate limits, consider reducing `max_actions_per_run` or running less frequently.

## Full Example

```yaml
justwatch:
  country: "US"
  language: "en"

libraries:
  # Main library: keep movies not available anywhere
  - name: "Movies"
    radarr: "Radarr"
    action_mode: "delete"
    last_watched_threshold: 90
    added_at_threshold: 180
    max_actions_per_run: 20
    exclude:
      justwatch:
        not_available_on: ["any"]

  # Streaming copies: more aggressive for content on your services
  - name: "Streaming Copies"
    radarr: "Radarr"
    action_mode: "delete"
    last_watched_threshold: 30
    added_at_threshold: 90
    max_actions_per_run: 50
    exclude:
      justwatch:
        available_on: ["netflix", "disneyplus", "amazon", "hbomax", "hulu"]
```

See [Configuration Reference](../CONFIGURATION.md) for the full field reference.
