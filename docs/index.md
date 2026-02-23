# Deleterr

Automated media library management for Plex using Radarr, Sonarr, and Tautulli.

Deleterr identifies and deletes media files based on user-specified criteria. Setup Deleterr to run on a schedule and it will automatically delete media files that meet your criteria, keeping your library fresh and clean without manual management.

!!! warning
    Do not use this with media content you can't afford to lose. Enable the recycle bin in Sonarr/Radarr settings if you want to recover deleted files.

---

## Quick Links

- [Getting Started](getting-started.md) - Docker setup and first run
- [Configuration Reference](CONFIGURATION.md) - All settings explained
- [Templates](templates.md) - Copy-paste ready configurations
- [Exclusions](features/exclusions.md) - Protect content from deletion
- [Integrations](integrations/trakt.md) - Trakt, MDBList, JustWatch, Overseerr

---

## Requirements

| Service | Required | Purpose |
|---------|----------|---------|
| Plex | Yes | Media server to manage |
| Tautulli | Yes | Watch history tracking |
| Radarr | No* | Movie library management |
| Sonarr | No* | TV show library management |

*At least one of Radarr or Sonarr is required.

---

## How It Works

1. **Connects** to your Plex, Tautulli, and Radarr/Sonarr instances
2. **Analyzes** watch history and media metadata
3. **Filters** media based on your rules (watched status, age, exclusions)
4. **Deletes** matching media through Radarr/Sonarr
5. **Optionally** triggers library scans and adds list exclusions

---

## Key Features

### Leaving Soon Collections

Deleterr's signature feature - a "death row" pattern where items are tagged to a "Leaving Soon" collection first, users get notified, and deletion happens on the next run. This gives users time to watch content before it's removed.

[Learn more about Leaving Soon](features/leaving-soon.md)

### User Notifications

Alert your users via Email, Discord, Slack, or Telegram about content that's expiring soon.

[Learn more about Notifications](features/notifications.md)

### Smart Exclusions

Protect content by genre, actor, Plex labels, streaming availability (JustWatch), Trakt lists, MDBList lists, and more.

[Learn more about Exclusions](features/exclusions.md)

### Multi-Instance Support

Configure multiple Radarr/Sonarr instances (e.g., separate 4K libraries) with different retention policies.

[Learn more about Multi-Instance Support](features/multi-instance.md)

### Disk Thresholds

Only delete when disk space falls below a specified limit - perfect for space-constrained systems.

[Learn more about Disk Thresholds](features/disk-thresholds.md)

---

## Image Availability

```
ghcr.io/rfsbraz/deleterr:latest
rfsbraz/deleterr:latest
```

**Tags**: `latest` (stable), `edge` (development), `X.Y.Z` (specific version)
