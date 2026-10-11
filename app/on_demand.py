# encoding: utf-8
"""
On-demand emergency cleanup mode (``--free-up``).

Sweeps across *all* configured Radarr and Sonarr libraries at once and deletes
actionable content immediately until every targeted disk has a requested amount
of free space, then stops.

This is deliberately different from the per-library ``disk_size_threshold`` gate
(``library_meets_disk_space_threshold``): that is a one-shot on/off gate evaluated
per library ("skip this library if free space > threshold"). On-demand mode is
cross-library, drives toward a free-space target per disk, deletes incrementally,
and stops the instant the target is met.

Protections are fully honored - it reuses :meth:`MediaCleaner.get_ordered_candidates`
(exclusions, genres, Trakt/mdblist, watch/added thresholds, each library's sort).
Only ``max_actions_per_run`` and the per-library disk gate are overridden, and the
Leaving Soon / death-row grace period is bypassed (immediate hard delete).
"""

from datetime import datetime

from app import logger
from app.media_cleaner import ConfigurationError, MediaCleaner
from app.modules.notifications import NotificationManager, RunResult, DeletedItem
from app.modules.plex import PlexMediaServer
from app.modules.radarr import DRadarr
from app.modules.sonarr import DSonarr
from app.modules.tautulli import TautulliApiError
from app.utils import print_readable_freed_space

# Re-query the arr's real free space after this many deletions to correct for
# Radarr/Sonarr's lagging freeSpace (we optimistically sum sizeOnDisk between
# re-queries, which is fast but drifts).
REQUERY_EVERY_N_DELETIONS = 10


def normalize_path(path):
    """Strip a trailing slash so path prefix comparisons are segment-accurate."""
    if not path:
        return path
    return path.rstrip("/") or "/"


def is_subpath(path, base):
    """
    Return True if ``path`` is ``base`` itself or lives under it, comparing on
    path-segment boundaries so ``/data`` is not treated as a prefix of ``/data2``.
    """
    if not path or not base:
        return False
    path = normalize_path(path)
    base = normalize_path(base)
    if base == "/":
        return True
    return path == base or path.startswith(base + "/")


def map_path_to_disk(item_path, disk_paths):
    """
    Map a media item's path to the disk it lives on by longest-prefix match.

    Args:
        item_path: The Radarr/Sonarr folder path of a media item.
        disk_paths: Iterable of candidate disk (mount/root-folder) paths.

    Returns:
        The disk path that is the longest prefix of ``item_path``, or None if the
        item does not fall under any of the given disks.
    """
    if not item_path:
        return None
    best = None
    for disk_path in disk_paths:
        if is_subpath(item_path, disk_path):
            if best is None or len(normalize_path(disk_path)) > len(normalize_path(best)):
                best = disk_path
    return best


def item_size(item, media_type):
    """Return the on-disk size in bytes for a Radarr/Sonarr media item."""
    if media_type == "movie":
        return item.get("sizeOnDisk", 0) or 0
    return item.get("statistics", {}).get("sizeOnDisk", 0) or 0


class OnDemandCleaner:
    """
    Emergency cross-library cleanup that frees disks toward a target and stops.

    Organized per disk (a Radarr mount and a Sonarr mount can be the same physical
    disk, and the target is per-disk): build under-target disks, gather ordered
    candidates from every library, map each candidate to its disk, then round-robin
    delete across the libraries on each disk - one item at a time, re-checking the
    target after every deletion - until the target is met or candidates run out.
    """

    def __init__(self, config):
        self.config = config
        self.is_dry_run = config.settings.get("dry_run", True)

        ssl_verify = config.settings.get("ssl_verify", False)
        self.media_server = PlexMediaServer(
            config.settings.get("plex").get("url"),
            config.settings.get("plex").get("token"),
            ssl_verify=ssl_verify,
        )
        self.media_cleaner = MediaCleaner(config, media_server=self.media_server)
        self.notifications = NotificationManager(config)
        self.run_result = RunResult(
            is_dry_run=self.is_dry_run,
            start_time=datetime.now(),
        )

        self.sonarr = {
            connection["name"]: DSonarr(connection["name"], connection["url"], connection["api_key"])
            for connection in config.settings.get("sonarr", [])
        }
        self.radarr = {
            connection["name"]: DRadarr(connection["name"], connection["url"], connection["api_key"])
            for connection in config.settings.get("radarr", [])
        }

        self.libraries_processed = 0
        self.libraries_failed = 0

    # -- orchestration ---------------------------------------------------------

    def run(self, target_bytes, free_up_path=None):
        """
        Free every targeted disk up to ``target_bytes`` of free space, then stop.

        Args:
            target_bytes: Desired free space per disk, in bytes.
            free_up_path: Optional mount/root-folder to restrict cleanup to.
        """
        mode = "[DRY-RUN] " if self.is_dry_run else ""
        logger.info(
            "%sOn-demand cleanup: freeing every disk up to %s free%s",
            mode,
            print_readable_freed_space(target_bytes),
            f" (restricted to '{free_up_path}')" if free_up_path else "",
        )

        disks = self._build_disk_targets(target_bytes, free_up_path)
        if not disks:
            logger.info("No targeted disk is below the requested free-space target - nothing to do")
            self.run_result.end_time = datetime.now()
            return

        self._gather_candidates(disks, target_bytes)

        for disk in disks:
            self._process_disk(disk)

        self.run_result.end_time = datetime.now()
        self._log_summary(disks, target_bytes)
        self._send_notification()

    # -- step 1: disk targets --------------------------------------------------

    def _build_disk_targets(self, target_bytes, free_up_path):
        """
        Build the list of disks that are below the free-space target.

        Queries ``get_disk_space()`` on every configured instance, dedupes folders
        that are the same physical mount (by path), applies the optional
        ``free_up_path`` filter, and keeps only folders whose free space is below
        the target.
        """
        disks = {}
        for instances in (self.radarr, self.sonarr):
            for name, instance in instances.items():
                try:
                    disk_space = instance.get_disk_space()
                except Exception as e:
                    logger.error(f"Failed to get disk space from instance '{name}': {e}")
                    continue

                for folder in disk_space or []:
                    path = folder.get("path")
                    if path is None:
                        continue
                    if free_up_path and not (
                        is_subpath(path, free_up_path) or is_subpath(free_up_path, path)
                    ):
                        continue
                    if path in disks:
                        # Same physical mount already recorded (e.g. reported by
                        # both a Radarr and a Sonarr instance) - don't double-count.
                        continue
                    disks[path] = {
                        "path": path,
                        "free_space": folder.get("freeSpace", 0) or 0,
                        "instance": instance,
                        "libraries": [],
                    }

        if not disks:
            logger.warning(
                "No disks matched%s - check that the instances are reachable and the "
                "path (if given) matches a Radarr/Sonarr root folder",
                f" '{free_up_path}'" if free_up_path else "",
            )
            return []

        targets = []
        for path, disk in disks.items():
            if disk["free_space"] < target_bytes:
                disk["target"] = target_bytes
                disk["deficit"] = target_bytes - disk["free_space"]
                disk["freed"] = 0
                disk["final_free"] = disk["free_space"]
                logger.info(
                    "Disk '%s': %s free, need to free %s more",
                    path,
                    print_readable_freed_space(disk["free_space"]),
                    print_readable_freed_space(disk["deficit"]),
                )
                targets.append(disk)
            else:
                logger.info(
                    "Disk '%s' already has %s free (>= target) - skipping",
                    path,
                    print_readable_freed_space(disk["free_space"]),
                )
        return targets

    # -- step 2: gather candidates ---------------------------------------------

    def _resolve_library(self, library, series_cache):
        """Resolve a library to its (instance, media_type, all_data)."""
        radarr_name = library.get("radarr")
        if radarr_name:
            if radarr_name in self.radarr:
                return self.radarr[radarr_name], "movie", None
            logger.warning(
                "Library '%s' references unknown radarr instance '%s' - skipping",
                library.get("name", "Unknown"), radarr_name,
            )
            return None, None, None

        sonarr_name = library.get("sonarr")
        if sonarr_name:
            if sonarr_name in self.sonarr:
                instance = self.sonarr[sonarr_name]
                if sonarr_name not in series_cache:
                    series_cache[sonarr_name] = instance.get_series()
                return instance, "show", series_cache[sonarr_name]
            logger.warning(
                "Library '%s' references unknown sonarr instance '%s' - skipping",
                library.get("name", "Unknown"), sonarr_name,
            )
            return None, None, None

        return None, None, None

    def _gather_candidates(self, disks, target_bytes):
        """
        Gather ordered deletion candidates from every library and bucket them onto
        the disk each item lives on, preserving library (config) order per disk.
        """
        disk_by_path = {disk["path"]: disk for disk in disks}
        disk_paths = list(disk_by_path.keys())
        series_cache = {}

        for library in self.config.settings.get("libraries", []):
            instance, media_type, all_data = self._resolve_library(library, series_cache)
            if instance is None:
                continue

            library_name = library.get("name", "Unknown")
            try:
                candidates = self.media_cleaner.get_ordered_candidates(
                    library, instance, media_type, all_data
                )
            except (ConfigurationError, TautulliApiError) as e:
                logger.error(f"Failed to gather candidates for library '{library_name}': {e}")
                self.libraries_failed += 1
                continue
            except Exception as e:
                logger.error(f"Unexpected error gathering candidates for library '{library_name}': {e}")
                self.libraries_failed += 1
                continue

            self.libraries_processed += 1

            queue_by_disk = {}
            unmapped = 0
            for item in candidates:
                disk_path = map_path_to_disk(item.get("path"), disk_paths)
                if disk_path is None:
                    unmapped += 1
                    continue
                queue_by_disk.setdefault(disk_path, []).append(item)

            for disk_path, items in queue_by_disk.items():
                disk_by_path[disk_path]["libraries"].append({
                    "library": library,
                    "instance": instance,
                    "media_type": media_type,
                    "queue": items,
                })

            mapped = sum(len(v) for v in queue_by_disk.values())
            logger.info(
                "Library '%s': %d candidate(s) on targeted disks%s",
                library_name,
                mapped,
                f" ({unmapped} on other disks)" if unmapped else "",
            )

    # -- step 3: round-robin delete per disk -----------------------------------

    def _process_disk(self, disk):
        """
        Round-robin across the libraries on a disk, deleting one candidate at a
        time and re-checking the target after each deletion, until the target is
        met or every candidate pool is exhausted.
        """
        target = disk["target"]
        path = disk["path"]
        free_space = disk["free_space"]
        freed = 0
        since_requery = 0

        active = [q for q in disk["libraries"] if q["queue"]]
        if not active:
            logger.warning(
                "Disk '%s' is below target but has no actionable candidates "
                "(all protected or on other disks)",
                path,
            )
            disk["final_free"] = free_space
            disk["freed"] = 0
            return

        logger.info("Freeing disk '%s' (round-robin across %d librar%s)",
                    path, len(active), "y" if len(active) == 1 else "ies")

        while free_space < target and active:
            for q in active:
                if free_space >= target:
                    break
                if not q["queue"]:
                    continue
                item = q["queue"].pop(0)
                size = self._delete(q, item)
                if size is None:
                    # Deletion skipped (e.g. episode file in use) - don't count it.
                    continue
                freed += size
                free_space += size
                since_requery += 1

                if not self.is_dry_run and since_requery >= REQUERY_EVERY_N_DELETIONS:
                    since_requery = 0
                    requeried = self._requery_free_space(disk)
                    if requeried is not None:
                        free_space = requeried

            active = [q for q in active if q["queue"]]

        disk["freed"] = freed
        disk["final_free"] = free_space

        if free_space >= target:
            logger.info(
                "Disk '%s': target met - freed %s (now %s free)",
                path,
                print_readable_freed_space(freed),
                print_readable_freed_space(free_space),
            )
        else:
            logger.warning(
                "Disk '%s': ran out of candidates before reaching target - "
                "freed %s of %s needed",
                path,
                print_readable_freed_space(freed),
                print_readable_freed_space(disk["deficit"]),
            )

    def _delete(self, queue_entry, item):
        """
        Delete (or, in dry-run, simulate deleting) a single media item.

        Returns:
            The bytes freed, or None if the deletion was skipped/failed and must
            not count toward the target.
        """
        library = queue_entry["library"]
        instance = queue_entry["instance"]
        media_type = queue_entry["media_type"]
        title = item.get("title", "Unknown")
        size = item_size(item, media_type)

        logger.log_deletion(
            title=title,
            size_bytes=size,
            media_type=media_type,
            is_dry_run=self.is_dry_run,
        )

        if not self.is_dry_run:
            try:
                if media_type == "movie":
                    self.media_cleaner.delete_movie_if_allowed(library, instance, item)
                else:
                    if not self.media_cleaner.delete_series(instance, item):
                        # e.g. an episode file is in use - skip and don't count it.
                        logger.warning(
                            f"Skipped '{title}' (deletion could not complete) - "
                            "not counting toward the free-space target"
                        )
                        return None
                    self.media_cleaner._update_seerr_status(library, item, "tv")
            except Exception as e:
                logger.error(f"Failed to delete '{title}': {e}")
                return None

        instance_name = library.get("radarr") or library.get("sonarr") or "Unknown"
        library_name = library.get("name", "Unknown")
        if media_type == "movie":
            self.run_result.add_deleted(DeletedItem.from_radarr(item, library_name, instance_name))
        else:
            self.run_result.add_deleted(DeletedItem.from_sonarr(item, library_name, instance_name))

        return size

    def _requery_free_space(self, disk):
        """Re-query an arr for the current free space of this disk's path."""
        instance = disk["instance"]
        try:
            for folder in instance.get_disk_space() or []:
                if folder.get("path") == disk["path"]:
                    return folder.get("freeSpace", disk["free_space"])
        except Exception as e:
            logger.debug(f"Could not re-query free space for '{disk['path']}': {e}")
        return None

    # -- step 4: reporting -----------------------------------------------------

    def _log_summary(self, disks, target_bytes):
        separator = "=" * 60
        logger.info(separator)
        logger.info("ON-DEMAND CLEANUP SUMMARY")
        logger.info(separator)

        if self.is_dry_run:
            logger.info("[DRY-RUN MODE] No changes were made")

        if self.run_result.duration_seconds is not None:
            logger.info(f"Duration: {logger.format_duration(self.run_result.duration_seconds)}")

        logger.info(f"Libraries processed: {self.libraries_processed}")
        if self.libraries_failed > 0:
            logger.info(f"Libraries failed: {self.libraries_failed}")

        logger.info("-" * 40)
        logger.info("Per-Disk Results (target: %s free):", print_readable_freed_space(target_bytes))
        for disk in disks:
            met = disk["final_free"] >= target_bytes
            logger.info(
                "  %s %s: freed %s, now %s free",
                "[met]" if met else "[unmet]",
                disk["path"],
                print_readable_freed_space(disk.get("freed", 0)),
                print_readable_freed_space(disk.get("final_free", disk["free_space"])),
            )

        logger.info("-" * 40)
        logger.info(f"Total items deleted: {len(self.run_result.deleted_items)}")
        total_freed = self.run_result.total_freed_bytes
        if total_freed > 0:
            logger.info(f"Total space freed: {print_readable_freed_space(total_freed)}")
        logger.info(separator)

    def _send_notification(self):
        if self.notifications.is_enabled():
            try:
                self.notifications.send_run_summary(self.run_result)
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")
