# Deleterr

[![CI](https://github.com/rfsbraz/deleterr/actions/workflows/ci.yml/badge.svg)](https://github.com/rfsbraz/deleterr/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker Pulls](https://img.shields.io/docker/pulls/rfsbraz/deleterr)](https://hub.docker.com/r/rfsbraz/deleterr)
[![GitHub Release](https://img.shields.io/github/v/release/rfsbraz/deleterr)](https://github.com/rfsbraz/deleterr/releases)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=rfsbraz_deleterr&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=rfsbraz_deleterr)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=rfsbraz_deleterr&metric=coverage)](https://sonarcloud.io/summary/new_code?id=rfsbraz_deleterr)

**Intelligent media library cleanup for Plex with user-friendly "Leaving Soon" notifications.**

Deleterr uses Radarr, Sonarr, and Tautulli to identify and delete media files based on user-specified criteria. Its **Leaving Soon** system warns your users before content is removed—giving them a chance to watch it first.

## Key Features

- **Leaving Soon Collections** - Automatically create Plex collections showing content scheduled for deletion
- **User Notifications** - Email, Discord, Slack, or Telegram alerts to your users about expiring content
- **Smart Exclusions** - Protect content by genre, actor, collection, streaming availability (JustWatch), Trakt lists, and more
- **Watch-Based Rules** - Delete only unwatched content, or content not watched in X days
- **Multi-Instance Support** - Manage multiple Radarr/Sonarr instances (regular + 4K libraries)
- **Dry Run Mode** - Preview what would be deleted before enabling real deletions

## Leaving Soon: Give Users Time to Watch

The **Leaving Soon** feature implements a "death row" pattern:

1. **First run**: Items matching deletion criteria are tagged with a "Leaving Soon" collection/label
2. **Users get notified**: Via email, Discord, Slack, or Telegram with a beautiful list of expiring content
3. **Grace period**: Users can watch the content before the next scheduled run
4. **Next run**: Previously tagged items are deleted, new candidates are tagged

This creates a Netflix-like experience where users see what's leaving and can prioritize their watchlist accordingly.

```yaml
# Example: Enable Leaving Soon with email notifications
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

Setup Deleterr to run on a schedule and it will automatically delete media files that meet your criteria while keeping your users informed. This allows you to keep your library fresh and clean, without surprising anyone with missing content.

## Documentation

- **[Getting Started](https://rfsbraz.github.io/deleterr/getting-started)** - Docker setup and first run
- **[Configuration Reference](https://rfsbraz.github.io/deleterr/CONFIGURATION)** - All settings explained
- **[Templates](https://rfsbraz.github.io/deleterr/templates)** - Copy-paste ready configurations

## WARNING

* **DO NOT USE THIS WITH MEDIA CONTENT YOU CAN'T AFFORD TO LOSE**
* Turn on the recycle bin in your Sonarr/Radarr settings if you want to be able to recover deleted files (not recommended for remote mounts)

### Docker Compose

Adding deleterr to your docker-compose file is really easy and can be combined with ofelia to run at a schedule. Here's an example that runs deleterr weekly:

```yaml
version: "3.9"
services:
    deleterr:
        image: ghcr.io/rfsbraz/deleterr:latest
        container_name: deleterr
        environment:
            LOG_LEVEL: INFO
        volumes:
            - ./config:/config
            - ./logs:/config/logs
        restart: no
    scheduler:
        image: mcuadros/ofelia:latest
        container_name: scheduler
        depends_on:
            - deleterr
        command: daemon --docker
        volumes:
            - /var/run/docker.sock:/var/run/docker.sock:ro
        restart: unless-stopped
        labels:
            ofelia.job-run.deleterr.schedule: "@weekly"
            ofelia.job-run.deleterr.container: "deleterr"
```

You can find more information about ofelia's scheduling options [here](https://github.com/mcuadros/ofelia#jobs).

### Portainer

When deploying with Portainer, you may encounter a bind mount error like:
```
Error response from daemon: Bind mount failed: '/path/to/config' does not exist
```

This happens because Portainer (unlike `docker-compose` CLI) does not automatically create host directories for bind mounts. Here are several solutions:

**Option 1: Enable "Create path on host" in Portainer (Recommended)**

When adding the stack in Portainer:
1. Go to **Stacks** → **Add stack**
2. After pasting your compose file, scroll down to **Advanced options**
3. Enable **"Create path on host if it doesn't exist"** (available in Portainer CE 2.19+ / BE 2.16+)

This allows you to use the standard docker-compose example without modifications.

**Option 2: Create directories manually**

Before deploying the stack, SSH into your server and create the required directories:

```bash
mkdir -p /path/to/your/deleterr/config
mkdir -p /path/to/your/deleterr/logs
```

Then use absolute paths in your stack:

```yaml
version: "3.9"
services:
    deleterr:
        image: ghcr.io/rfsbraz/deleterr:latest
        container_name: deleterr
        environment:
            LOG_LEVEL: INFO
        volumes:
            - /path/to/your/deleterr/config:/config
            - /path/to/your/deleterr/logs:/config/logs
        restart: no
    scheduler:
        image: mcuadros/ofelia:latest
        container_name: scheduler
        depends_on:
            - deleterr
        command: daemon --docker
        volumes:
            - /var/run/docker.sock:/var/run/docker.sock:ro
        restart: unless-stopped
        labels:
            ofelia.job-run.deleterr.schedule: "@weekly"
            ofelia.job-run.deleterr.container: "deleterr"
```

**Option 3: Use named volumes**

Named volumes are automatically created by Docker and don't require host directories:

```yaml
version: "3.9"
services:
    deleterr:
        image: ghcr.io/rfsbraz/deleterr:latest
        container_name: deleterr
        environment:
            LOG_LEVEL: INFO
        volumes:
            - deleterr_config:/config
            - deleterr_logs:/config/logs
        restart: no
    scheduler:
        image: mcuadros/ofelia:latest
        container_name: scheduler
        depends_on:
            - deleterr
        command: daemon --docker
        volumes:
            - /var/run/docker.sock:/var/run/docker.sock:ro
        restart: unless-stopped
        labels:
            ofelia.job-run.deleterr.schedule: "@weekly"
            ofelia.job-run.deleterr.container: "deleterr"

volumes:
    deleterr_config:
    deleterr_logs:
```

> **Note**: With named volumes, you'll need to place your `settings.yaml` file inside the volume. You can do this by first starting the container, then copying the file using `docker cp settings.yaml deleterr:/config/settings.yaml`.

### Docker

Set your settings file in `config/settings.yaml` and run the following command:

```bash
docker run -v ./config:/config -v ./logs:/config/logs ghcr.io/rfsbraz/deleterr:latest -e LOG_LEVEL=DEBUG
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