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

`server_name` is optional. When it is set, Deleterr only uses plays from that server. When it is omitted, plays from every server Tracearr monitors are included, which can protect a Plex item that was watched on Jellyfin or Emby.

## How it maps onto Deleterr

Deleterr still manages Plex libraries through Radarr and Sonarr. Tracearr history is matched to those Plex items by rating key first, then by provider ids such as `movie:tmdb:27205` or `show:tvdb:81189`, using the media-scoped v2 endpoints documented by Tracearr:

- `GET /api/v2/public/history` loads last-watched times for a library
- `GET /api/v2/public/media/{ref}/watchers` answers whether a specific user has watched a title
- `GET /api/v2/public/servers` is used to test the connection and resolve `server_name`

A title with no history in Tracearr is treated as unwatched, the same as with Tautulli.
