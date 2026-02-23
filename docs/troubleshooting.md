# Troubleshooting

Common issues and solutions for Deleterr.

## Connection Issues

### Plex Connection Failed

**Symptoms**: `Failed to connect to Plex` or `Plex token invalid`

**Solutions**:

1. **Verify URL format**: Include protocol and port
   ```yaml
   plex:
     url: "http://192.168.1.100:32400"  # Not just "192.168.1.100"
   ```

2. **Check token**: Get a fresh token from [Plex documentation](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)

3. **SSL issues**: If using HTTPS with self-signed certificates:
   ```yaml
   ssl_verify: false
   ```

4. **Network access**: Ensure Deleterr container can reach Plex
   ```bash
   docker exec deleterr curl -s http://plex:32400/identity
   ```

### Tautulli Connection Failed

**Symptoms**: `Failed to connect to Tautulli` or `API key invalid`

**Solutions**:

1. **Find API key**: Tautulli > Settings > Web Interface > API Key

2. **Test connection**:
   ```bash
   curl "http://tautulli:8181/api/v2?apikey=YOUR_KEY&cmd=get_server_info"
   ```

3. **Check API access**: Ensure API is enabled in Tautulli settings

### Radarr/Sonarr Connection Failed

**Symptoms**: `Failed to connect to Radarr/Sonarr`

**Solutions**:

1. **Find API key**: Settings > General > Security > API Key

2. **Verify URL**: Include `/api/v3` is NOT needed - Deleterr handles this

3. **Test connection**:
   ```bash
   curl -H "X-Api-Key: YOUR_KEY" http://radarr:7878/api/v3/system/status
   ```

## Library Issues

### Library Not Found

**Symptoms**: `Library 'Movies' not found in Plex`

**Solutions**:

1. **Check exact name**: Library name must match exactly (case-sensitive)
   ```bash
   # List Plex libraries
   curl -H "X-Plex-Token: YOUR_TOKEN" \
     http://plex:32400/library/sections | grep title
   ```

2. **Use Plex library name**: Not the folder name or Radarr root folder name

### No Items Found for Deletion

**Symptoms**: Run completes but finds no items

**Solutions**:

1. **Check thresholds**: Items must meet ALL criteria
   ```yaml
   last_watched_threshold: 90   # Watched 90+ days ago
   added_at_threshold: 180      # Added 180+ days ago
   ```

2. **Verify watch history**: Ensure Tautulli has watch data

3. **Check exclusions**: Your exclusion rules might be too broad

4. **Review watch_status**:
   ```yaml
   watch_status: "watched"     # Only delete watched items
   watch_status: "unwatched"   # Only delete unwatched items
   watch_status: "all"         # Delete regardless of watch status
   ```

### Wrong Items Being Deleted

**Symptoms**: Items deleted that shouldn't be

**Solutions**:

1. **Always start with dry_run**:
   ```yaml
   dry_run: true
   ```

2. **Add exclusions**: Protect important content
   ```yaml
   exclude:
     plex_labels: ["favorite", "keep"]
     collections: ["Marvel Cinematic Universe"]
   ```

3. **Check library mapping**: Ensure Radarr/Sonarr instance matches the Plex library

## Disk Threshold Issues

### Threshold Not Working

**Symptoms**: Items deleted even when disk has space (or not deleted when low)

**Solutions**:

1. **Verify path**: Must be a path accessible inside the container
   ```yaml
   disk_size_threshold:
     - path: "/data/media"      # Container path, not host path
       threshold: "500GB"
   ```

2. **Check mount**: Ensure the volume is mounted correctly
   ```bash
   docker exec deleterr df -h /data/media
   ```

3. **Threshold format**: Use quotes and valid units
   ```yaml
   threshold: "500GB"   # Correct
   threshold: 500GB     # May cause issues
   threshold: "500"     # Assumes bytes
   ```

## Notification Issues

See [Notifications Troubleshooting](features/notifications.md#troubleshooting) for notification-specific issues.

## Docker Issues

### Container Exits Immediately

**Symptoms**: Container starts and stops immediately

**Solutions**:

1. **Check logs**:
   ```bash
   docker logs deleterr
   ```

2. **Verify config file**: Ensure `settings.yaml` exists and is valid
   ```bash
   docker run --rm -v ./config:/config deleterr \
     python -c "import yaml; yaml.safe_load(open('/config/settings.yaml'))"
   ```

3. **Check scheduler**: If using built-in scheduler, container should stay running
   ```yaml
   scheduler:
     enabled: true
   ```

### Permission Denied Errors

**Symptoms**: `Permission denied` when accessing config or logs

**Solutions**:

1. **Check ownership**: Container runs as UID 1000 by default
   ```bash
   sudo chown -R 1000:1000 ./config ./logs
   ```

2. **Or use PUID/PGID**:
   ```yaml
   environment:
     - PUID=1000
     - PGID=1000
   ```

### Config Changes Not Applied

**Symptoms**: Changes to `settings.yaml` don't take effect

**Solutions**:

1. **Restart container**:
   ```bash
   docker compose restart deleterr
   ```

2. **Check file location**: Config must be at `/config/settings.yaml` inside container

3. **Validate YAML syntax**: Use a YAML validator

## Scheduler Issues

### Scheduler Not Running

**Symptoms**: Using built-in scheduler but Deleterr only runs once

**Solutions**:

1. **Enable scheduler**:
   ```yaml
   scheduler:
     enabled: true
     schedule: "weekly"
   ```

2. **Check restart policy**:
   ```yaml
   services:
     deleterr:
       restart: unless-stopped  # Not "no"
   ```

3. **View scheduler status**:
   ```bash
   docker logs deleterr | grep -i schedul
   ```

### Ofelia Not Triggering

**Symptoms**: Using Ofelia but Deleterr never runs

**Solutions**:

1. **Check Ofelia logs**:
   ```bash
   docker logs scheduler
   ```

2. **Verify labels**:
   ```yaml
   labels:
     ofelia.job-run.deleterr.schedule: "@weekly"
     ofelia.job-run.deleterr.container: "deleterr"  # Must match container_name
   ```

3. **Ensure Docker socket mounted**:
   ```yaml
   volumes:
     - /var/run/docker.sock:/var/run/docker.sock:ro
   ```

## JustWatch Issues

### Streaming Check Not Working

**Symptoms**: Items aren't being excluded even though they're on Netflix/etc.

**Solutions**:

1. **Check country code**: Must match your streaming region
   ```yaml
   justwatch:
     country: "US"  # ISO 3166-1 alpha-2 code
   ```

2. **Title matching**: JustWatch searches by title -- unusual characters or regional titles may not match. Enable `LOG_LEVEL: DEBUG` to see search results.

3. **Rate limiting**: If you see `JustWatch API rate limit hit` in logs, reduce `max_actions_per_run` or run less frequently.

See [JustWatch Integration](integrations/justwatch.md) for full setup details.

## Overseerr Issues

### Overseerr Connection Failed

**Symptoms**: `Cannot reach Overseerr` or `API authentication failed`

**Solutions**:

1. **Check URL and API key**:
   ```yaml
   overseerr:
     url: "http://localhost:5055"
     api_key: "YOUR_API_KEY"  # From Overseerr Settings > General
   ```

2. **Test connection**:
   ```bash
   curl -H "X-Api-Key: YOUR_KEY" http://overseerr:5055/api/v1/status
   ```

3. **Seerr users**: The same configuration works for Seerr -- no changes needed.

### Deleted Media Still Shows as Available

If deleted media still shows "available" in Overseerr, enable `update_status`:

```yaml
exclude:
  overseerr:
    update_status: true
```

See [Overseerr Integration](integrations/overseerr.md) for full setup details.

## Trakt / MDBList Issues

### List Items Not Being Excluded

**Symptoms**: Items on Trakt/MDBList lists are still being deleted

**Solutions**:

1. **Verify credentials**: Ensure `trakt.client_id`/`client_secret` or `mdblist.api_key` are correct

2. **Check list URL format**: URLs must match supported patterns
   ```yaml
   # Trakt
   - "https://trakt.tv/movies/trending"
   - "https://trakt.tv/users/username/lists/listname"

   # MDBList
   - "https://mdblist.com/lists/username/listname"
   ```

3. **Increase max_items_per_list**: If your list has more items than the default limit
   ```yaml
   trakt:
     max_items_per_list: 200   # Default: 100
   mdblist:
     max_items_per_list: 2000  # Default: 1000
   ```

4. **Check matching IDs**: Trakt matches by TMDB/TVDB ID. If an item lacks these IDs, it won't match.

See [Trakt Integration](integrations/trakt.md) and [MDBList Integration](integrations/mdblist.md) for full setup details.

## Getting Help

If you're still stuck:

1. **Enable debug logging**:
   ```yaml
   environment:
     LOG_LEVEL: DEBUG
   ```

2. **Check GitHub Issues**: [github.com/rfsbraz/deleterr/issues](https://github.com/rfsbraz/deleterr/issues)

3. **Create a new issue** with:
   - Deleterr version
   - Sanitized config (remove API keys/tokens)
   - Relevant log output
   - Steps to reproduce
