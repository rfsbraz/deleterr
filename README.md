# Deleterr

[![CI](https://github.com/rfsbraz/deleterr/actions/workflows/ci.yml/badge.svg)](https://github.com/rfsbraz/deleterr/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker Pulls](https://img.shields.io/docker/pulls/rfsbraz/deleterr)](https://hub.docker.com/r/rfsbraz/deleterr)
[![GitHub Release](https://img.shields.io/github/v/release/rfsbraz/deleterr)](https://github.com/rfsbraz/deleterr/releases)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=rfsbraz_deleterr&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=rfsbraz_deleterr)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=rfsbraz_deleterr&metric=coverage)](https://sonarcloud.io/summary/new_code?id=rfsbraz_deleterr)

**Intelligent media library cleanup for Plex.**

Deleterr uses Radarr, Sonarr, and Tautulli to identify and delete media files based on user-specified criteria like watch history, age, and streaming availability.

## Key Features

- **Smart Exclusions** - Protect content by genre, actor, collection, streaming availability (JustWatch), Trakt lists, and more
- **Watch-Based Rules** - Delete only unwatched content, or content not watched in X days
- **Multi-Instance Support** - Manage multiple Radarr/Sonarr instances (regular + 4K libraries)
- **Dry Run Mode** - Preview what would be deleted before enabling real deletions
- **Leaving Soon Collections** - Warn users before content is removed with Plex collections and notifications
- **Built-in Scheduler** - Runs on a schedule automatically (daily, weekly, or custom cron)

## Documentation

- **[Getting Started](https://rfsbraz.github.io/deleterr/getting-started)** - Docker setup and first run
- **[Configuration Reference](https://rfsbraz.github.io/deleterr/CONFIGURATION)** - All settings explained
- **[Templates](https://rfsbraz.github.io/deleterr/templates)** - Copy-paste ready configurations

## WARNING

* **DO NOT USE THIS WITH MEDIA CONTENT YOU CAN'T AFFORD TO LOSE**
* Turn on the recycle bin in your Sonarr/Radarr settings if you want to be able to recover deleted files (not recommended for remote mounts)

## Quick Start

### Docker Compose

Deleterr includes a built-in scheduler that runs automatically. Here's an example that runs weekly:

```yaml
services:
  deleterr:
    image: ghcr.io/rfsbraz/deleterr:latest
    container_name: deleterr
    environment:
      LOG_LEVEL: INFO
    volumes:
      - ./config:/config
    restart: unless-stopped
```

By default, Deleterr runs weekly on Sunday at midnight. Configure the schedule in your `settings.yaml`:

```yaml
schedule:
  cron: "0 0 * * 0"  # Every Sunday at midnight (default)
  # cron: "0 3 * * *"  # Daily at 3 AM
  # cron: "0 0 * * 0,3"  # Sundays and Wednesdays at midnight
```

### Portainer

When deploying with Portainer, you may encounter a bind mount error like:
```
Error response from daemon: Bind mount failed: '/path/to/config' does not exist
```

This happens because Portainer (unlike `docker-compose` CLI) does not automatically create host directories for bind mounts.

**Option 1: Enable "Create path on host" in Portainer (Recommended)**

When adding the stack in Portainer:
1. Go to **Stacks** → **Add stack**
2. After pasting your compose file, scroll down to **Advanced options**
3. Enable **"Create path on host if it doesn't exist"** (available in Portainer CE 2.19+ / BE 2.16+)

**Option 2: Create directories manually**

Before deploying the stack, SSH into your server and create the required directories:

```bash
mkdir -p /path/to/your/deleterr/config
```

Then use absolute paths in your stack:

```yaml
services:
  deleterr:
    image: ghcr.io/rfsbraz/deleterr:latest
    container_name: deleterr
    environment:
      LOG_LEVEL: INFO
    volumes:
      - /path/to/your/deleterr/config:/config
    restart: unless-stopped
```

**Option 3: Use named volumes**

Named volumes are automatically created by Docker and don't require host directories:

```yaml
services:
  deleterr:
    image: ghcr.io/rfsbraz/deleterr:latest
    container_name: deleterr
    environment:
      LOG_LEVEL: INFO
    volumes:
      - deleterr_config:/config
    restart: unless-stopped

volumes:
  deleterr_config:
```

> **Note**: With named volumes, you'll need to place your `settings.yaml` file inside the volume. You can do this by first starting the container, then copying the file using `docker cp settings.yaml deleterr:/config/settings.yaml`.

### Docker CLI

Set your settings file in `config/settings.yaml` and run:

```bash
docker run -v ./config:/config ghcr.io/rfsbraz/deleterr:latest
```

For a one-time run (no scheduler), add `--run-once`:

```bash
docker run -v ./config:/config ghcr.io/rfsbraz/deleterr:latest --run-once
```

## Leaving Soon: Give Users Time to Watch

The **Leaving Soon** feature implements a "death row" pattern that warns users before content is removed:

1. **First run**: Items matching deletion criteria are tagged with a "Leaving Soon" collection/label
2. **Users get notified**: Via email, Discord, Slack, or Telegram with a list of expiring content
3. **Grace period**: Users can watch the content before the next scheduled run
4. **Next run**: Previously tagged items are deleted, new candidates are tagged

This creates a Netflix-like experience where users see what's leaving and can prioritize their watchlist.

```yaml
# Example: Enable Leaving Soon with notifications
libraries:
  - name: "Movies"
    radarr: "Radarr"
    action_mode: "delete"
    max_actions_per_run: 20
    leaving_soon:
      collection:
        name: "Leaving Soon"
      labels:
        name: "leaving-soon"

notifications:
  leaving_soon:
    subject: "Content leaving your Plex server soon!"
    email:
      smtp_server: "smtp.gmail.com"
      to_addresses: ["family@example.com"]
```

## Configuration

Deleterr is configured via a YAML file. An example configuration file, `settings.example.yaml`, is provided. Copy this file to `settings.yaml` and adjust the settings as needed.

Please refer to the [configuration guide](https://rfsbraz.github.io/deleterr/CONFIGURATION) for a full list of options and their descriptions.

## Image Availability

The image is available through:

* [GitHub Container Registry](https://github.com/rfsbraz/deleterr/pkgs/container/deleterr): `ghcr.io/rfsbraz/deleterr:<tag>`
* [Docker Hub](https://hub.docker.com/r/rfsbraz/deleterr): `rfsbraz/deleterr:<tag>`

### Tags

* `latest`: The latest stable release
* `edge`: The latest development build (from main branch)
* `X.Y.Z`: A specific version
* `X.Y`: The latest release in the vX.Y series
* `X`: The latest release in the vX series
