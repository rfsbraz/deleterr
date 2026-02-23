# Disk Thresholds

Only delete media when disk space falls below a specified limit. This is useful if you only want Deleterr to clean up when you're actually running low on storage.

## How It Works

1. Deleterr queries the Radarr/Sonarr API for disk space information
2. If free space on the configured path is **above** the threshold, the library is skipped entirely
3. If free space is **below** the threshold, Deleterr proceeds with normal deletion logic

## Configuration

```yaml
libraries:
  - name: "Movies"
    radarr: "Radarr"
    action_mode: "delete"
    disk_size_threshold:
      - path: "/data/media"
        threshold: "500GB"
```

## Options

| Option | Description |
|--------|-------------|
| `path` | Path to check disk space for (must match a root folder in Radarr/Sonarr) |
| `threshold` | Minimum free space. If free space is above this, the library is skipped |

### Size Units

Supported units: `B`, `KB`, `MB`, `GB`, `TB`, `PB`, `EB`

```yaml
threshold: "500GB"
threshold: "1TB"
threshold: "100MB"
```

## Path Gotcha

!!! warning "Use the Container Path"
    The `path` must be a path accessible to Radarr/Sonarr, not the host path. This is the root folder path as configured in Radarr/Sonarr settings.

For example, if your Docker Compose maps `/mnt/storage/media` on the host to `/data/media` inside the Radarr container, use `/data/media`:

```yaml
disk_size_threshold:
  - path: "/data/media"       # Radarr/Sonarr container path
    threshold: "500GB"
```

If the path doesn't match any root folder in Radarr/Sonarr, Deleterr will raise a configuration error.

## Multiple Paths

You can specify multiple paths. All paths must be below their respective thresholds for deletion to proceed:

```yaml
disk_size_threshold:
  - path: "/data/movies"
    threshold: "200GB"
  - path: "/data/tv"
    threshold: "300GB"
```

## Combining with Sorting

Disk thresholds work well with size-based sorting to maximize space reclaimed:

```yaml
libraries:
  - name: "Movies"
    radarr: "Radarr"
    action_mode: "delete"
    max_actions_per_run: 50
    disk_size_threshold:
      - path: "/data/media"
        threshold: "500GB"
    sort:
      field: "size"
      order: "desc"  # Delete largest files first
```

## Combining with Leaving Soon

When combined with [Leaving Soon](leaving-soon.md), items are only tagged to the collection when disk space is low:

```yaml
libraries:
  - name: "Movies"
    radarr: "Radarr"
    action_mode: "delete"
    max_actions_per_run: 20
    preview_next: 10
    disk_size_threshold:
      - path: "/data/media"
        threshold: "500GB"
    leaving_soon:
      collection:
        name: "Leaving Soon"
```

See [Configuration Reference](../CONFIGURATION.md) for the full field reference.
