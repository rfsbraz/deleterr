# Deleterr Configuration Guide

This guide provides a detailed explanation for each configuration setting you'll need to set up Deleterr.

You can find a sample configuration file in the [config](../config) directory.

Fields marked with **\*** are mandatory and must be configured.

## General Settings

General settings set at the root level of the configuration file.

| Property | Description | Example |
|----------|-------------|---------|
| `dry_run` | If true, actions are only logged, not performed. | `true` |
| `plex_library_scan_after_actions` | Trigger a Plex library scan after actions are performed. | `false` |
| `tautulli_library_scan_after_actions` | Trigger a Tautulli library scan after actions are performed. | `false` |
| `action_delay` | Delay (in seconds) between actions. Defaults to `0`. Sometimes the Plex/Sonarr/Radarr instances start to timeout when the delay is set to zero (specially if deleting remote media). Increase this to prevent errors | `25` |

<details>
  <summary>See example</summary>

```yaml
dry_run: false
plex_library_scan_after_actions: false
tautulli_library_scan_after_actions: false
action_delay: 0
```
</details>

## Plex *
This section holds the connection details for your Plex server. The URL is the address where your Plex server is hosted, and the token is your unique Plex authentication token.

| Property | Description | Example |
|----------|-------------|---------|
| `url` | URL of your Plex server. | `"http://localhost:32400"` |
| `token` | Plex authentication token. | `"YOUR_PLEX_TOKEN"` |

<details>
  <summary>See example</summary>

```yaml
plex:
    url: "http://localhost:32400"
    token: "YOUR_PLEX_TOKEN"
```
</details>

## Radarr

Here, you can specify the connection settings for **one or more** Radarr instances.

You can configure multiple Radarr instances by adding additional entries to the `radarr` array (useful for 4k instances, for example)

| Property | Description | Example |
|----------|-------------|---------|
| `name` | Custom name for each Radarr connection. | `"Radarr"` |
| `url` | URL of your Radarr server. | `"http://localhost:7878"` |
| `api_key` | Radarr API key. | `"YOUR_RADARR_API_KEY1"` |

<details>
  <summary>See example</summary>

```yaml
radarr:
  - name: "Radarr"
    url: "http://localhost:7878"
    api_key: "YOUR_RADARR_API_KEY1"
  - name: "Radarr 4K"
    url: "http://localhost:7879"
    api_key: "YOUR_RADARR_API_KEY2"
```
</details>

## Sonarr [NOT IMPLEMENTED YET]

Here, you can specify the connection settings for **one or more** Sonarr instances.

You can configure multiple Sonarr instances by adding additional entries to the `sonarr` array (useful for 4k instances, for example)

| Property | Description | Example |
|----------|-------------|---------|
| `name` | Custom name for each Sonarr connection. | `"Sonarr"` |
| `url` | URL of your Sonarr server. | `"http://localhost:8989"` |
| `api_key` | Sonarr API key. | `"YOUR_SONARR_API_KEY1"` |

<details>
  <summary>See example</summary>

```yaml
radarr:
  - name: "Sonarr"
    url: "http://localhost:8989"
    api_key: "YOUR_SONARR_API_KEY1"
  - name: "Sonarr 4K"
    url: "http://localhost:8990"
    api_key: "YOUR_SONARR_API_KEY2"
```
</details>

## Tautulli *

[Tautulli](https://tautulli.com/) is a third-party application for monitoring your Plex Media Server. It's used to determine the watch history of your media.

| Property | Description | Example |
|----------|-------------|---------|
| `url` | URL of your Tautulli server. | `"http://localhost:8181"` |
| `api_key` | Tautulli API key. | `"YOUR_TAUTULLI_API_KEY"` |

<details>
  <summary>See example</summary>

```yaml
tautulli:
    url: "http://localhost:8181"
    api_key: "YOUR_TAUTULLI_API_KEY"
```
</details>

## Trakt

If you use Trakt, this section is where you provide your Trakt application details. This is necessary for integration and fetching data from Trakt. The client ID and client secret can be obtained by [creating an application](https://trakt.tv/oauth/applications) on Trakt's website.

| Property | Description | Example |
|----------|-------------|---------|
| `client_id` | Trakt client ID. | `"YOUR_TRAKT_CLIENT_ID"` |
| `client_secret` | Trakt client secret. | `"YOUR_TRAKT_CLIENT_SECRET"` |

<details>
  <summary>See example</summary>

```yaml
trakt:
  client_id: "YOUR_TRAKT_CLIENT_ID"
  client_secret: "YOUR_TRAKT_CLIENT_SECRET"
```
</details>

### Library

For each of your Plex libraries, specify how you want Deleterr to behave. Define the name of the library, which instances to use, the action mode, and various thresholds related to watched status and addition date. You can also define exclusion rules here to protect certain media items from being actioned.

| Property | Description | Example |
|----------|-------------|---------|
| `name` | Name of the Plex library you wish to manage. Must match the name of your Plex Library | `"Movies", "TV Shows", "Anime` |
| `radarr` | Identifier of the Radarr instance to be used for this library (matches a `name` under the `radarr` configuration). Exclusive with the `sonarr` property | `"Radarr", "Radarr 4K"` |
| `sonarr` | Identifier of the Sonarr instance to be used for this library (matches a `name` under the `sonarr` configuration). Exclusive with the `radarr` property | `"Sonarr", "Sonarr 4K"` |
| `action_mode` | The action to perform on the media items. Possible values: `"delete"`. | `"delete"` |
| `last_watched_threshold` | Time threshold in days. Media watched in this period will not be actionable | `90` |
| `apply_last_watch_threshold_to_collections` | If set to `true`, the last watched threshold will be applied to all other items in the same collection. | `true` |
| `added_at_threshold` | Media that added to Plex within this period (in days) will not be actionable | `180` |
| `max_actions_per_run` | Limit the number of actions performed per run. Defaults to `10` | `3000` |

<details>
  <summary>See example</summary>

```yaml
libraries:
  - name: "Movies"
    radarr: Radarr
    action_mode: "delete"
    last_watched_threshold: 90
    added_at_threshold: 180
    apply_last_watch_threshold_to_collections: true
    max_actions_per_run: 3000
```
</details>

#### Exclusions

For each library, you can also specify exclusions to prevent certain media from being affected by the actions.

Metadata is matched against the media's metadata in Plex.

| Property | Description | Example |
|----------|-------------|---------|
| `titles` | Array of titles to exclude media. | `["Forrest Gump"]` |
| `tags` | Array of tags to exclude media. | `["children", "favorite"]` |
| `genres` | Array of genres to exclude media. | `["horror", "thriller"]` |
| `collections` | Exclude media that are part of specific collections. | `["Marvel Cinematic Universe"]` |
| `actors` | Exclude media featuring specific actors. | `["Tom Cruise", "Brad Pitt"]` |
| `producers` | Exclude media produced by specific producers. | `["Steven Spielberg"]` |
| `directors` | Exclude media directed by specific directors. | `["Makoto Shinkai"]` |
| `writers` | Exclude media written by specific writers. | `["Hayao Miyazaki"]` |
| `studios` | Exclude media from specific studios. | `["Studio Ghibli"]` |
| `release_years` | Exclude media released within the last X years. | `5` |
| `trakt` -> `max_items_per_list` | Maximum number of items to fetch from each Trakt list. | `100` |
| `trakt` -> `lists` | Array of Trakt list URLs to exclude media from. | `[ "https://trakt.tv/movies/trending", "https://trakt.tv/users/justin/lists/imdb-top-rated-movies" ]` |

<details>
  <summary>See example</summary>

```yaml
libraries:
  - name: "Movies"
    ...
    exclude:
      titles: ["Forrest Gump"]
      tags: ["children", "favorite"]
      genres: ["horror", "thriller"]
      collections: ["Marvel Cinematic Universe"]
      actors: ["Tom Cruise", "Brad Pitt"]
      producers: ["Steven Spielberg"]
      directors: ["Makoto Shinkai"]
      writers: ["Hayao Miyazaki"]
      studios: ["Studio Ghibli"]
      release_years: 5
      trakt:
        max_items_per_list: 200
        lists:
          [
            "https://trakt.tv/movies/trending",
            "https://trakt.tv/movies/popular",
            "https://trakt.tv/movies/watched/yearly",
            "https://trakt.tv/movies/collected/yearly",
            "https://trakt.tv/users/justin/lists/imdb-top-rated-movies"
          ]
```
</details>