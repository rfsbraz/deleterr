# encoding: utf-8

import argparse
import atexit
import locale
import os
import sys
import time
from datetime import datetime

from app.modules.radarr import DRadarr
from app.modules.sonarr import DSonarr
from app.modules.plex import PlexMediaServer

from app import logger
from app.config import hang_on_error, load_config
from app.media_cleaner import ConfigurationError, MediaCleaner
from app.modules.notifications import NotificationManager, RunResult, DeletedItem, LibraryStats
from app.utils import print_readable_freed_space

# Lock file for single instance detection
LOCK_FILE = "/config/.deleterr.lock"
_lock_file_handle = None


def acquire_instance_lock():
    """
    Try to acquire an exclusive lock to ensure only one instance runs.

    Returns:
        bool: True if lock acquired, False if another instance is running.
    """
    global _lock_file_handle

    # Skip on Windows (primarily for local development)
    if sys.platform == "win32":
        return True

    try:
        import fcntl

        _lock_file_handle = open(LOCK_FILE, "w")
        fcntl.flock(_lock_file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_file_handle.write(str(os.getpid()))
        _lock_file_handle.flush()

        # Register cleanup on exit
        atexit.register(release_instance_lock)
        return True
    except (IOError, OSError):
        # Lock is held by another process
        return False
    except ImportError:
        # fcntl not available (non-Unix)
        return True


def release_instance_lock():
    """Release the instance lock."""
    global _lock_file_handle

    if _lock_file_handle:
        try:
            import fcntl
            fcntl.flock(_lock_file_handle.fileno(), fcntl.LOCK_UN)
            _lock_file_handle.close()
            os.remove(LOCK_FILE)
        except Exception:
            pass
        _lock_file_handle = None


class Deleterr:
    def __init__(self, config):
        self.config = config

        # Initialize media server for leaving_soon feature
        ssl_verify = config.settings.get("ssl_verify", False)
        self.media_server = PlexMediaServer(
            config.settings.get("plex").get("url"),
            config.settings.get("plex").get("token"),
            ssl_verify=ssl_verify,
        )

        self.media_cleaner = MediaCleaner(config, media_server=self.media_server)
        self.notifications = NotificationManager(config)
        self.run_result = RunResult(
            is_dry_run=config.settings.get("dry_run", True),
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

        self.process_radarr()
        self.process_sonarr()

        # Record end time and log summary
        self.run_result.end_time = datetime.now()
        self._log_run_summary()

        # Send notification after all processing
        self._send_notification()

    def _get_death_row_items(self, library, plex_library):
        """
        Get Plex items that were tagged for deletion on the previous run.

        Args:
            library: Library configuration dict
            plex_library: Plex library section

        Returns:
            List of Plex media items that should be deleted
        """
        leaving_soon_config = library.get("leaving_soon")
        if not leaving_soon_config:
            return []

        items_to_delete = []
        seen_keys = set()

        # Get items from collection (presence of config = enabled)
        collection_config = leaving_soon_config.get("collection")
        if collection_config is not None:
            collection_name = collection_config.get("name", "Leaving Soon")
            collection = self.media_server.get_collection(plex_library, collection_name)
            if collection:
                try:
                    for item in collection.items():
                        if item.ratingKey not in seen_keys:
                            items_to_delete.append(item)
                            seen_keys.add(item.ratingKey)
                except Exception as e:
                    logger.error(
                        f"Failed to read items from collection '{collection_name}' in library '{library.get('name')}': {e}. "
                        "Items in this collection will NOT be deleted on this run."
                    )

        # Get items with label (presence of config = enabled)
        labels_config = leaving_soon_config.get("labels")
        if labels_config is not None:
            label_name = labels_config.get("name", "leaving-soon")
            labeled_items = self.media_server.get_items_with_label(plex_library, label_name)
            for item in labeled_items:
                if item.ratingKey not in seen_keys:
                    items_to_delete.append(item)
                    seen_keys.add(item.ratingKey)

        return items_to_delete

    def _lookup_radarr_movie(self, plex_item, radarr_instance):
        """
        Look up a Radarr movie from a Plex item.

        Args:
            plex_item: Plex media item
            radarr_instance: Radarr instance to search

        Returns:
            Radarr movie data dict, or None if not found
        """
        guids = self.media_server.get_guids(plex_item)

        # Try TMDB ID first (most reliable for movies)
        if guids.get("tmdb_id"):
            try:
                movies = radarr_instance.get_movie(guids["tmdb_id"])
                if movies:
                    return movies[0]
            except Exception as e:
                logger.debug(f"Radarr lookup by TMDB ID {guids.get('tmdb_id')} failed: {e}")

        # Try IMDB ID
        if guids.get("imdb_id"):
            try:
                movies = radarr_instance.get_movie(guids["imdb_id"])
                if movies:
                    return movies[0]
            except Exception as e:
                logger.debug(f"Radarr lookup by IMDB ID {guids.get('imdb_id')} failed: {e}")

        logger.warning(
            f"'{plex_item.title}' is in the leaving_soon collection but not found in Radarr "
            f"(TMDB: {guids.get('tmdb_id')}, IMDB: {guids.get('imdb_id')}). "
            "It may have been deleted manually or the IDs don't match."
        )
        return None

    def _lookup_sonarr_show(self, plex_item, sonarr_instance):
        """
        Look up a Sonarr show from a Plex item.

        Args:
            plex_item: Plex media item
            sonarr_instance: Sonarr instance to search

        Returns:
            Sonarr series data dict, or None if not found
        """
        guids = self.media_server.get_guids(plex_item)

        # Try TVDB ID first (most reliable for shows)
        if guids.get("tvdb_id"):
            try:
                series = sonarr_instance.get_series(guids["tvdb_id"])
                if series:
                    return series
            except Exception as e:
                logger.debug(f"Sonarr lookup by TVDB ID {guids.get('tvdb_id')} failed: {e}")

        # Try IMDB ID
        if guids.get("imdb_id"):
            try:
                # Sonarr doesn't have direct IMDB lookup, search all series
                all_series = sonarr_instance.get_series()
                for series in all_series:
                    if series.get("imdbId") == guids["imdb_id"]:
                        return series
            except Exception as e:
                logger.debug(f"Sonarr lookup by IMDB ID {guids.get('imdb_id')} failed: {e}")

        logger.warning(
            f"'{plex_item.title}' is in the leaving_soon collection but not found in Sonarr "
            f"(TVDB: {guids.get('tvdb_id')}, IMDB: {guids.get('imdb_id')}). "
            "It may have been deleted manually or the IDs don't match."
        )
        return None

    def _process_death_row(self, library, media_instance, media_type, all_data=None):
        """
        Process items using the death row pattern (unified for movies and shows).

        The death row collection is NOT the source of truth for deletions.
        We delete items that BOTH:
        1. Currently match deletion rules (watched, past threshold, not excluded, etc.)
        2. Were previously tagged in the death row collection/labels

        This ensures items watched since being tagged won't be deleted.

        Args:
            library: Library configuration dict
            media_instance: Radarr or Sonarr instance
            media_type: 'movie' or 'show'
            all_data: All show data from Sonarr (only needed for shows)

        Returns:
            tuple: (saved_space, deleted_items, preview_candidates)
        """
        from app.media_cleaner import library_meets_disk_space_threshold

        if not library_meets_disk_space_threshold(library, media_instance):
            library_name = library.get("name", "Unknown")
            leaving_soon_config = library.get("leaving_soon")
            if leaving_soon_config:
                logger.info(
                    "Disk space above threshold for library '%s' - "
                    "death row will be cleared (no deletions needed)",
                    library_name,
                )
            return 0, [], []

        library_name = library.get("name", "Unknown")
        logger.info(f"Processing library '{library_name}' with leaving_soon (death row pattern)")

        # Get Plex library
        try:
            plex_library = self.media_server.get_library(library_name)
        except Exception as e:
            logger.error(f"Failed to get Plex library '{library_name}': {e}")
            return 0, [], []

        # Get death row items (items tagged on previous run)
        death_row_plex_items = self._get_death_row_items(library, plex_library)
        death_row_keys = {item.ratingKey for item in death_row_plex_items}

        # Get ALL items that currently match deletion rules
        all_deletion_candidates = self._get_deletion_candidates(
            library, media_instance, plex_library, media_type, all_data
        )

        # Items to delete = intersection of death row AND current candidates
        # Only build the Plex lookup map if there are death row items to check
        items_to_delete = []
        if death_row_keys:
            # Build a map of Plex ratingKey -> media item for candidates
            candidate_by_plex_key = {}
            for media_item in all_deletion_candidates:
                if media_type == "movie":
                    plex_item = self.media_server.find_item(
                        plex_library,
                        tmdb_id=media_item.get("tmdbId"),
                        imdb_id=media_item.get("imdbId"),
                        title=media_item.get("title"),
                        year=media_item.get("year"),
                    )
                else:
                    plex_item = self.media_server.find_item(
                        plex_library,
                        tvdb_id=media_item.get("tvdbId"),
                        imdb_id=media_item.get("imdbId"),
                        title=media_item.get("title"),
                    )
                if plex_item:
                    candidate_by_plex_key[plex_item.ratingKey] = media_item

            for plex_key in death_row_keys:
                if plex_key in candidate_by_plex_key:
                    items_to_delete.append(candidate_by_plex_key[plex_key])

        saved_space = 0
        deleted_items = []
        is_dry_run = self.config.settings.get("dry_run", True)

        if death_row_plex_items:
            filtered_out = len(death_row_plex_items) - len(items_to_delete)
            logger.info(
                f"Found {len(death_row_plex_items)} items in leaving_soon, "
                f"{len(items_to_delete)} still match deletion criteria"
                + (f" ({filtered_out} protected by thresholds, exclusions, or watch activity since tagging)" if filtered_out > 0 else "")
            )
        else:
            logger.info("No items in leaving_soon (first run or empty death row)")

        # Delete items that are in death row AND still match deletion rules
        for media_item in items_to_delete:
            if media_type == "movie":
                disk_size = media_item.get("sizeOnDisk", 0)
                extra_info = None
            else:
                disk_size = media_item.get("statistics", {}).get("sizeOnDisk", 0)
                total_episodes = media_item.get("statistics", {}).get("episodeFileCount", 0)
                extra_info = f"{total_episodes} episodes"

            saved_space += disk_size

            # Log the deletion
            logger.log_deletion(
                title=media_item["title"],
                size_bytes=disk_size,
                media_type=media_type,
                is_dry_run=is_dry_run,
                extra_info=extra_info,
            )

            if not is_dry_run:
                try:
                    if media_type == "movie":
                        media_instance.del_movie(
                            media_item["id"],
                            delete_files=True,
                            add_exclusion=library.get("add_list_exclusion_on_delete", False),
                        )
                        self.media_cleaner._update_seerr_status(library, media_item, "movie")
                    else:
                        self.media_cleaner.delete_series(media_instance, media_item)
                        self.media_cleaner._update_seerr_status(library, media_item, "tv")
                except Exception as e:
                    logger.error(
                        f"Failed to delete '{media_item['title']}' from "
                        f"{'Radarr' if media_type == 'movie' else 'Sonarr'}: {e}. "
                        "Will retry on next run."
                    )
                    continue

            deleted_items.append(media_item)

        # Get preview candidates for next run (excluding what we just deleted)
        preview_next = library.get("preview_next")
        if preview_next is None:
            preview_next = library.get("max_actions_per_run", 10)

        deleted_ids = {m.get("id") for m in deleted_items}
        preview_candidates = [
            m for m in all_deletion_candidates
            if m.get("id") not in deleted_ids
        ][:preview_next]

        return saved_space, deleted_items, preview_candidates

    def _get_deletion_candidates(self, library, media_instance, plex_library, media_type, all_data=None, limit=None):
        """
        Get items that currently match deletion rules (unified for movies and shows).

        This is used by the death row pattern to determine which items
        should actually be deleted (intersection of death row AND current candidates).

        Args:
            library: Library configuration dict
            media_instance: Radarr or Sonarr instance
            plex_library: Plex library section
            media_type: 'movie' or 'show'
            all_data: All show data from Sonarr (only needed for shows, optional)
            limit: Maximum number of candidates to return (None = no limit)

        Returns:
            List of media dicts that match deletion criteria
        """
        if limit == 0:
            return []

        if media_type == "movie":
            trakt_items = self.media_cleaner.get_trakt_items("movie", library)
            activity = self.media_cleaner.get_movie_activity(library, plex_library)
            media_data = media_instance.get_movies()
            instance_kwargs = {"radarr_instance": media_instance}
        else:
            media_data = self.media_cleaner.filter_shows(library, all_data) if all_data else []
            trakt_items = self.media_cleaner.get_trakt_items("show", library)
            activity = self.media_cleaner.get_show_activity(library, plex_library)
            instance_kwargs = {"sonarr_instance": media_instance}

        candidates = []
        for media_item in self.media_cleaner.process_library_rules(
            library, plex_library, media_data, activity, trakt_items, **instance_kwargs
        ):
            candidates.append(media_item)
            if limit is not None and len(candidates) >= limit:
                break

        return candidates

    def process_radarr(self):
        for name, radarr in self.radarr.items():
            logger.info(f"Processing radarr instance: '{name}'")

            # Get libraries for this instance
            libraries_for_instance = [
                lib for lib in self.config.settings.get("libraries", [])
                if lib.get("radarr") == name
            ]
            total_libraries = len(libraries_for_instance)

            saved_space = 0
            all_preview = []
            for idx, library in enumerate(libraries_for_instance, 1):
                library_name = library.get("name", "Unknown")
                logger.info(f"[{idx}/{total_libraries}] Processing library '{library_name}'")
                library_start = time.time()

                try:
                    leaving_soon_config = library.get("leaving_soon")

                    if leaving_soon_config:
                        # Death row pattern: delete previously tagged items, tag new preview
                        space, deleted, preview = self._process_death_row(
                            library, radarr, "movie"
                        )
                    else:
                        # Normal deletion flow
                        space, deleted, preview = self.media_cleaner.process_library_movies(
                            library, radarr
                        )

                    saved_space += space
                    self.libraries_processed += 1

                    # Track deleted items for notifications
                    for item in deleted:
                        self.run_result.add_deleted(
                            DeletedItem.from_radarr(item, library_name, name)
                        )

                    if leaving_soon_config:
                        # Process leaving_soon feature - tag preview items for next run
                        # Don't add to all_preview as these items are being tagged, not deleted
                        self._process_library_leaving_soon(
                            library, preview, "movie"
                        )
                    else:
                        # Normal flow: preview items will be deleted on next run
                        all_preview.extend(preview)

                    # Log library completion time
                    library_duration = time.time() - library_start
                    logger.info(f"Library '{library_name}' completed in {logger.format_duration(library_duration)}")
                except ConfigurationError as e:
                    logger.error(str(e))
                    self.libraries_failed += 1

            logger.log_freed_space(saved_space, "movie", self.config.settings.get("dry_run", True))

            # Log preview of next scheduled deletions
            self._log_preview(all_preview, "movie")

    def process_sonarr(self):
        for name, sonarr in self.sonarr.items():
            logger.info(f"Processing sonarr instance: '{name}'")
            unfiltered_all_show_data = sonarr.get_series()

            # Get libraries for this instance
            libraries_for_instance = [
                lib for lib in self.config.settings.get("libraries", [])
                if lib.get("sonarr") == name
            ]
            total_libraries = len(libraries_for_instance)

            saved_space = 0
            all_preview = []
            for idx, library in enumerate(libraries_for_instance, 1):
                library_name = library.get("name", "Unknown")
                logger.info(f"[{idx}/{total_libraries}] Processing library '{library_name}'")
                library_start = time.time()

                try:
                    leaving_soon_config = library.get("leaving_soon")

                    if leaving_soon_config:
                        # Death row pattern: delete previously tagged items, tag new preview
                        space, deleted, preview = self._process_death_row(
                            library, sonarr, "show", unfiltered_all_show_data
                        )
                    else:
                        # Normal deletion flow
                        space, deleted, preview = self.media_cleaner.process_library(
                            library, sonarr, unfiltered_all_show_data
                        )

                    saved_space += space
                    self.libraries_processed += 1

                    # Track deleted items for notifications
                    for item in deleted:
                        self.run_result.add_deleted(
                            DeletedItem.from_sonarr(item, library_name, name)
                        )

                    if leaving_soon_config:
                        # Process leaving_soon feature - tag preview items for next run
                        # Don't add to all_preview as these items are being tagged, not deleted
                        self._process_library_leaving_soon(
                            library, preview, "show"
                        )
                    else:
                        # Normal flow: preview items will be deleted on next run
                        all_preview.extend(preview)

                    # Log library completion time
                    library_duration = time.time() - library_start
                    logger.info(f"Library '{library_name}' completed in {logger.format_duration(library_duration)}")
                except ConfigurationError as e:
                    logger.error(str(e))
                    self.libraries_failed += 1

            logger.log_freed_space(saved_space, "show", self.config.settings.get("dry_run", True))

            # Log preview of next scheduled deletions
            self._log_preview(all_preview, "show")

    def _process_library_leaving_soon(self, library, preview, media_type):
        """
        Process leaving_soon feature for a library.

        Implements the "death row" pattern:
        - Tag preview items to collection/labels for warning before next deletion
        - Items that were tagged on the previous run have already been deleted
        - Send leaving_soon notifications if configured

        Args:
            library: Library configuration dict
            preview: List of items that would be deleted next run
            media_type: 'movie' or 'show'
        """
        leaving_soon_config = library.get("leaving_soon")
        if not leaving_soon_config:
            return

        is_dry_run = self.config.settings.get("dry_run", True)

        # In dry_run mode, log what would be tagged but don't actually tag
        if is_dry_run:
            if preview:
                logger.info(
                    "[DRY-RUN] %d items would be added to leaving_soon collection/labels:",
                    len(preview)
                )
                for item in preview:
                    logger.info(
                        "[DRY-RUN]   - %s (%s)",
                        item.get("title", "Unknown"),
                        item.get("year", "Unknown")
                    )
            else:
                logger.info(
                    "[DRY-RUN] No items match deletion criteria for library '%s' - "
                    "leaving_soon collection/labels would be cleared",
                    library.get("name", "Unknown"),
                )
            return

        if not preview:
            logger.debug("No items to tag for leaving_soon")
            # Still update the collection/labels to clear them if needed
            # Fall through to process_leaving_soon with empty list

        # Get the Plex library
        try:
            plex_library = self.media_server.get_library(library.get("name"))
        except Exception as e:
            logger.error(f"Failed to get Plex library '{library.get('name')}': {e}")
            return

        # Process leaving_soon - tag preview items for next run
        self.media_cleaner.process_leaving_soon(
            library, plex_library, preview, media_type
        )

        # Send leaving_soon notifications if configured and there are items
        if preview and self.notifications.is_leaving_soon_enabled():
            self._send_leaving_soon_notification(library, preview, media_type)

    def _send_leaving_soon_notification(self, library, preview, media_type):
        """
        Send leaving_soon notification for preview items.

        Args:
            library: Library configuration dict
            preview: List of items scheduled for deletion
            media_type: 'movie' or 'show'
        """
        # Convert preview items to DeletedItem objects for notification
        library_name = library.get("name", "Unknown")

        # Determine the instance name
        instance_name = library.get("radarr") or library.get("sonarr") or "Unknown"

        items = []
        for item in preview:
            if media_type == "movie":
                items.append(
                    DeletedItem.from_radarr(item, library_name, instance_name)
                )
            else:
                items.append(
                    DeletedItem.from_sonarr(item, library_name, instance_name)
                )

        # Get URLs for template context
        plex_url = self.config.settings.get("plex", {}).get("url")
        seerr_url = self.config.settings.get("seerr", {}).get("url")

        try:
            self.notifications.send_leaving_soon(
                items,
                plex_url=plex_url,
                seerr_url=seerr_url,
            )
        except Exception as e:
            logger.error(f"Failed to send leaving_soon notification: {e}")

    def _log_preview(self, preview_items, media_type):
        """
        Log preview of items that would be deleted on the next run.

        Args:
            preview_items: List of media items from Radarr/Sonarr
            media_type: 'movie' or 'show' for appropriate size extraction
        """
        if not preview_items:
            return

        # Calculate total preview size
        total_size = 0
        for item in preview_items:
            if media_type == "movie":
                total_size += item.get("sizeOnDisk", 0)
            else:  # show
                total_size += item.get("statistics", {}).get("sizeOnDisk", 0)

        # Determine log prefix for dry-run mode
        prefix = "[DRY-RUN] " if self.config.settings.get("dry_run") else ""
        action_word = "Would be deleted" if self.config.settings.get("dry_run") else "Next scheduled deletions"

        logger.info(
            "%s%s (%d items, %s):",
            prefix,
            action_word,
            len(preview_items),
            print_readable_freed_space(total_size),
        )

        # Log each preview item
        for i, item in enumerate(preview_items, 1):
            if media_type == "movie":
                size = item.get("sizeOnDisk", 0)
            else:  # show
                size = item.get("statistics", {}).get("sizeOnDisk", 0)

            logger.info(
                "%s  %d. %s (%s)",
                prefix,
                i,
                item["title"],
                print_readable_freed_space(size),
            )

    def _log_run_summary(self):
        """Log comprehensive run summary at end of execution."""
        separator = "=" * 60

        logger.info(separator)
        logger.info("RUN SUMMARY")
        logger.info(separator)

        # Dry-run mode indicator
        if self.run_result.is_dry_run:
            logger.info("[DRY-RUN MODE] No changes were made")

        # Duration
        if self.run_result.duration_seconds is not None:
            logger.info(f"Duration: {logger.format_duration(self.run_result.duration_seconds)}")

        # Libraries processed
        logger.info(f"Libraries processed: {self.libraries_processed}")
        if self.libraries_failed > 0:
            logger.info(f"Libraries failed: {self.libraries_failed}")

        # Items summary
        total_deleted = len(self.run_result.deleted_items)
        total_preview = len(self.run_result.preview_items)

        if self.run_result.library_stats:
            total_found = self.run_result.total_items_found
            total_unmatched = self.run_result.total_unmatched
            unmatched_str = f" ({total_unmatched} unmatched)" if total_unmatched > 0 else ""
            logger.info(f"Total items found: {total_found}{unmatched_str}")

        logger.info(f"Total items deleted: {total_deleted}")

        if total_preview > 0:
            logger.info(f"Total items previewed: {total_preview}")

        # Space freed
        total_freed = self.run_result.total_freed_bytes
        if total_freed > 0:
            logger.info(f"Total space freed: {logger.format_size(total_freed)}")

        # Per-library statistics (if tracked)
        if self.run_result.library_stats:
            logger.info("-" * 40)
            logger.info("Per-Library Statistics:")
            for stats in self.run_result.library_stats:
                unmatched_info = f", {stats.items_unmatched} unmatched" if stats.items_unmatched > 0 else ""
                logger.info(
                    f"  {stats.name} ({stats.instance_type.title()}): "
                    f"{stats.items_found} found, {stats.items_deleted} deleted{unmatched_info}"
                )

        logger.info(separator)

    def _send_notification(self):
        """Send notification with run results."""
        if self.notifications.is_enabled():
            try:
                self.notifications.send_run_summary(self.run_result)
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")

    def has_fatal_errors(self):
        """Returns True if all libraries failed due to configuration errors."""
        total_libraries = self.libraries_processed + self.libraries_failed
        return total_libraries > 0 and self.libraries_failed == total_libraries


def get_file_contents(file_path):
    try:
        with open(file_path, "r") as file:
            return file.read().strip()
    except FileNotFoundError:
        print(f"File not found: {file_path}")
    except IOError as e:
        print(f"Error reading file {file_path}: {e}")


def main():
    """
    Deleterr application entry point. Parses arguments, configs and
    initializes the application.

    Supports two modes:
    1. Scheduler mode (default): Runs as a long-lived daemon with built-in scheduling.
    2. Single run: Runs once and exits. For external schedulers (Ofelia, cron),
       set `scheduler.enabled: false` or use the --run-once flag.
    """

    locale.setlocale(locale.LC_ALL, "")

    log_level = os.environ.get("LOG_LEVEL", "info").upper()
    logger.init_logger(
        console=True, log_dir="/config/logs", verbose=log_level == "DEBUG"
    )

    logger.info(f"Running version {get_file_contents('/app/commit_tag.txt')}")
    logger.info(f"Log level set to {log_level}")

    parser = argparse.ArgumentParser(description="Deleterr - Automated media cleanup for Plex")
    parser.add_argument(
        "--config",
        "--c",
        default="/config/settings.yaml",
        help="Path to the config file",
    )
    parser.add_argument(
        "--jw-providers", action="store_true", help="Gather JustWatch providers"
    )
    parser.add_argument(
        "--scheduler",
        action="store_true",
        help="Force scheduler mode (overrides config setting)",
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Force single run mode (overrides scheduler config)",
    )

    args, unknown = parser.parse_known_args()

    config = load_config(args.config)
    config.validate()

    # If providers flag is set, gather JustWatch providers and exit
    if args.jw_providers:
        from app.scripts.justwatch_providers import gather_providers

        providers = gather_providers(
            config.settings.get("trakt", {}).get("client_id"),
            config.settings.get("trakt", {}).get("client_secret"),
        )

        print(providers)
        logger.info("# of Trakt Providers: " + str(len(providers)))

        return

    # Determine run mode
    scheduler_config = config.settings.get("scheduler", {})
    scheduler_enabled = scheduler_config.get("enabled", True)

    # CLI flags override config
    if args.run_once:
        scheduler_enabled = False
    elif args.scheduler:
        scheduler_enabled = True

    # Check for another running instance
    if not acquire_instance_lock():
        logger.warning("=" * 60)
        logger.warning("Another deleterr instance is already running!")
        logger.warning("=" * 60)
        if scheduler_enabled:
            logger.warning(
                "The built-in scheduler is enabled by default. "
                "If you're using an external scheduler (Ofelia, cron), either:"
            )
            logger.warning("")
            logger.warning("  1. Remove Ofelia and use the built-in scheduler (recommended)")
            logger.warning("     See: https://rfsbraz.github.io/deleterr/CONFIGURATION#scheduler")
            logger.warning("")
            logger.warning("  2. Or disable the built-in scheduler in settings.yaml:")
            logger.warning("     scheduler:")
            logger.warning("       enabled: false")
        else:
            logger.warning(
                "A previous run may still be in progress. "
                "Wait for it to complete or check for stuck processes."
            )
        logger.warning("Exiting to prevent duplicate runs.")
        sys.exit(1)

    if scheduler_enabled:
        # Run in scheduler mode (long-lived process)
        from app.scheduler import DeleterrScheduler

        logger.info("Starting in scheduler mode")
        scheduler = DeleterrScheduler(config)
        scheduler.start()  # Blocks until shutdown
    else:
        # Run once and exit (for external schedulers like Ofelia or cron)
        logger.info("Running in single-run mode")
        deleterr = Deleterr(config)

        if deleterr.has_fatal_errors():
            hang_on_error(
                "All libraries failed due to configuration errors. "
                "Please check your settings.yaml and fix the errors above."
            )


if __name__ == "__main__":
    main()
