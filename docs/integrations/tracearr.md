# Tracearr

[Tracearr](https://docs.tracearr.com) can supply watch history instead of Tautulli. It covers Plex, Jellyfin, and Emby, and Deleterr talks to its [public API v2](https://docs.tracearr.com/api). You need Tracearr 2.0 or later.

Tautulli behaviour is unchanged. If both services are configured, Deleterr keeps using Tautulli and ignores the Tracearr block.

## Setup

1. Generate an API key in Tracearr **Settings > Data & API > API**. The key starts with `trr_pub_`.
2. Add a `tracearr` block and omit `tautulli`:

```yaml
tracearr:
  url: "http://localhost:3000"
  api_key: "trr_pub_YOUR_TRACEARR_API_KEY"
  server_name: "Plex"  # Optional: which Tracearr-monitored server to query
```

Set `server_name` to the managed Plex server whenever Deleterr is cleaning Plex libraries. When it is set, Deleterr only uses rating keys from that server, and plays from other servers still match through provider ids (so a Jellyfin or Emby play can protect the same Plex title).

When `server_name` is set, an unresolvable play from another server fails the library run closed (the library is skipped) rather than that play being dropped. This is intentional.

When `server_name` is omitted, rating keys are not used. Plays can still match through provider ids, with two limits for Plex:

- The requester-watched exclusion never applies, because that lookup needs a verified Plex server.
- Plex items with no tmdb, tvdb, or imdb GUIDs cannot be matched to Tracearr plays, so they look unwatched.

## How it maps onto Deleterr

Deleterr still manages Plex libraries through Radarr and Sonarr. When `server_name` is set, Tracearr history is matched to those Plex items by rating key first, then by provider ids such as `movie:tmdb:27205` or `show:tvdb:81189`. Without `server_name`, only the provider ids are used. Matching uses the media-scoped v2 endpoints documented by Tracearr:

- `GET /api/v2/public/history` loads last-watched times for a library
- `GET /api/v2/public/media/{ref}/watchers` answers whether a specific user has watched a title
- `GET /api/v2/public/servers` is used to test the connection and resolve `server_name`

A title with no history in Tracearr is treated as unwatched, the same as with Tautulli.
