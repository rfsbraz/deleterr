---
title: Deleterr
---

# Deleterr

Automated media library management for Plex using Radarr, Sonarr, and Tautulli.

Deleterr identifies and deletes media files based on user-specified criteria. Setup Deleterr to run on a schedule and it will automatically delete media files that meet your criteria, keeping your library fresh and clean without manual management.

> **Warning**: Do not use this with media content you can't afford to lose. Enable the recycle bin in Sonarr/Radarr settings if you want to recover deleted files.

---

## Quick Links

- [Getting Started](getting-started) - Docker setup and first run
- [Configuration Reference](CONFIGURATION) - All settings explained
- [Templates](templates) - Copy-paste ready configurations

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

## Features

- **Multi-instance support** - Configure multiple Radarr/Sonarr instances (e.g., 4K libraries)
- **Flexible exclusions** - Protect media by title, genre, actor, collection, Trakt lists, or streaming availability
- **Watch-based rules** - Delete only watched content or content not watched within a threshold
- **Disk thresholds** - Only delete when disk space falls below a limit
- **Sorting options** - Prioritize deletion by size, age, rating, or other fields
- **Dry run mode** - Preview changes before executing

---

## Image Availability

```
ghcr.io/rfsbraz/deleterr:latest
rfsbraz/deleterr:latest
```

**Tags**: `latest` (stable), `edge` (development), `X.Y.Z` (specific version)
