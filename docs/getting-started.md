---
title: Getting Started
---

# Getting Started

This guide walks you through deploying Deleterr and running your first cleanup.

---

## Prerequisites

Before starting, ensure you have:

- [ ] Plex Media Server with a valid token ([how to get token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/))
- [ ] Tautulli installed and configured with API key
- [ ] Radarr and/or Sonarr with API keys
- [ ] Docker installed on your system

---

## Docker Compose Setup

There are two ways to schedule Deleterr: using the **built-in scheduler** (recommended for simplicity) or an **external scheduler** like Ofelia.

### Option A: Built-in Scheduler (Recommended)

The simplest setup - Deleterr handles its own scheduling:

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
    restart: unless-stopped
```

Add to your `settings.yaml`:
```yaml
scheduler:
  enabled: true
  schedule: "weekly"  # or "daily", "hourly", "monthly", or cron expression
  timezone: "America/New_York"
```

### Option B: External Scheduler (Ofelia)

For more advanced scheduling control, use [Ofelia](https://github.com/mcuadros/ofelia):

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

### Create settings.yaml

Create `config/settings.yaml` with your configuration. Start with dry run enabled:

```yaml
dry_run: true  # Preview changes without deleting

plex:
  url: "http://plex:32400"
  token: "YOUR_PLEX_TOKEN"

tautulli:
  url: "http://tautulli:8181"
  api_key: "YOUR_TAUTULLI_API_KEY"

radarr:
  - name: "Radarr"
    url: "http://radarr:7878"
    api_key: "YOUR_RADARR_API_KEY"

libraries:
  - name: "Movies"
    radarr: "Radarr"
    action_mode: "delete"
    last_watched_threshold: 90
    added_at_threshold: 180
```

### 3. Start the stack

```bash
docker compose up -d
```

---

## Scheduling Options

### Built-in Scheduler

The built-in scheduler supports presets and standard cron expressions:

| Schedule | Value |
|----------|-------|
| Weekly (Sunday 3am) | `weekly` |
| Daily at 3am | `daily` |
| Hourly | `hourly` |
| Monthly (1st at 3am) | `monthly` |
| Custom cron | `0 3 * * 0` (Sunday 3am) |

Example configuration:
```yaml
scheduler:
  enabled: true
  schedule: "0 4 * * 1,4"  # Monday and Thursday at 4am
  timezone: "Europe/London"
  run_on_startup: true  # Also run when container starts
```

### Ofelia (External Scheduler)

If using Ofelia, common scheduling patterns:

| Schedule | Label Value |
|----------|-------------|
| Weekly (Sunday midnight) | `@weekly` |
| Daily at 3am | `0 3 * * *` |
| Every 6 hours | `@every 6h` |
| Monthly | `@monthly` |

See [Ofelia documentation](https://github.com/mcuadros/ofelia#jobs) for full syntax.

---

## Portainer Deployment

When deploying with Portainer, you may encounter bind mount errors because Portainer doesn't auto-create host directories.

**Solution 1: Enable path creation**

In Portainer CE 2.19+: Stacks > Add stack > Advanced options > Enable "Create path on host if it doesn't exist"

**Solution 2: Create directories manually**

```bash
mkdir -p /path/to/deleterr/config
mkdir -p /path/to/deleterr/logs
```

Then use absolute paths in your stack.

**Solution 3: Named volumes**

```yaml
volumes:
  - deleterr_config:/config
  - deleterr_logs:/config/logs

# Add at bottom of compose file:
volumes:
  deleterr_config:
  deleterr_logs:
```

Note: With named volumes, copy settings.yaml using: `docker cp settings.yaml deleterr:/config/settings.yaml`

---

## Standalone Docker

Run Deleterr manually without a scheduler:

```bash
docker run -v ./config:/config -v ./logs:/config/logs \
  -e LOG_LEVEL=DEBUG \
  ghcr.io/rfsbraz/deleterr:latest
```

---

## First Run Walkthrough

1. **Start with dry_run: true** - This logs what would be deleted without actually deleting
2. **Check logs** - Review `logs/deleterr.log` to see what media would be affected
3. **Adjust thresholds** - Modify `last_watched_threshold` and `added_at_threshold` based on results
4. **Add exclusions** - Protect important media with exclusion rules
5. **Disable dry_run** - Set `dry_run: false` when satisfied with the preview
6. **Enable scheduling** - Let Ofelia run Deleterr automatically

---

## Verifying Configuration

Run Deleterr once manually to verify your setup:

```bash
docker compose run --rm deleterr
```

Check the logs for:
- Successful connections to Plex, Tautulli, Radarr/Sonarr
- Media items identified for deletion
- Any errors or warnings

---

## Next Steps

- [Configuration Reference](CONFIGURATION) - Full list of all settings
- [Templates](templates) - Ready-to-use configuration examples
