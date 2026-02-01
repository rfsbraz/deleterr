# encoding: utf-8

import argparse
import locale
import os
import sys

from app.modules.radarr import DRadarr
from app.modules.sonarr import DSonarr
from app.modules.plex import PlexMediaServer

from app import logger
from app.config import hang_on_error, load_config
from app.media_cleaner import ConfigurationError, MediaCleaner
from app.modules.notifications import NotificationManager, RunResult, DeletedItem
from app.utils import print_readable_freed_space


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
        self.run_result = RunResult(is_dry_run=config.settings.get("dry_run", True))

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
                    logger.warning(f"Error getting items from collection '{collection_name}': {e}")

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
                logger.debug(f"Error looking up movie by TMDB ID: {e}")

        # Try IMDB ID
        if guids.get("imdb_id"):
            try:
                movies = radarr_instance.get_movie(guids["imdb_id"])
                if movies:
                    return movies[0]
            except Exception:
                pass

        logger.warning(
            f"Could not find '{plex_item.title}' in Radarr (TMDB: {guids.get('tmdb_id')}, IMDB: {guids.get('imdb_id')})"
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
                logger.debug(f"Error looking up show by TVDB ID: {e}")

        # Try IMDB ID
        if guids.get("imdb_id"):
            try:
                # Sonarr doesn't have direct IMDB lookup, search all series
                all_series = sonarr_instance.get_series()
                for series in all_series:
                    if series.get("imdbId") == guids["imdb_id"]:
                        return series
            except Exception:
                pass

        logger.warning(
            f"Could not find '{plex_item.title}' in Sonarr (TVDB: {guids.get('tvdb_id')}, IMDB: {guids.get('imdb_id')})"
        )
        return None

    def _process_radarr_death_row(self, library, radarr_instance):
        """
        Process movies using the death row pattern.

        The death row collection is NOT the source of truth for deletions.
        We delete items that BOTH:
        1. Currently match deletion rules (watched, past threshold, not excluded, etc.)
        2. Were previously tagged in the death row collection/labels

        This ensures items watched since being tagged won't be deleted.

        Args:
            library: Library configuration dict
            radarr_instance: Radarr instance

        Returns:
            tuple: (saved_space, deleted_items, preview_candidates)
        """
        from app.media_cleaner import library_meets_disk_space_threshold

        if not library_meets_disk_space_threshold(library, radarr_instance):
            return 0, [], []

        library_name = library.get("name", "Unknown")
        logger.info("Processing library '%s' with leaving_soon (death row pattern)", library_name)

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
        all_deletion_candidates = self._get_all_deletion_candidates_movies(
            library, radarr_instance, plex_library
        )

        # Build a map of Plex ratingKey -> Radarr movie for candidates
        candidate_by_plex_key = {}
        for radarr_movie in all_deletion_candidates:
            plex_item = self.media_server.find_item(
                plex_library,
                tmdb_id=radarr_movie.get("tmdbId"),
                imdb_id=radarr_movie.get("imdbId"),
                title=radarr_movie.get("title"),
                year=radarr_movie.get("year"),
            )
            if plex_item:
                candidate_by_plex_key[plex_item.ratingKey] = radarr_movie

        # Items to delete = intersection of death row AND current candidates
        items_to_delete = []
        for plex_key in death_row_keys:
            if plex_key in candidate_by_plex_key:
                items_to_delete.append(candidate_by_plex_key[plex_key])

        saved_space = 0
        deleted_items = []
        is_dry_run = self.config.settings.get("dry_run", True)

        if death_row_plex_items:
            logger.info(
                "Found %d items in leaving_soon, %d still match deletion criteria",
                len(death_row_plex_items),
                len(items_to_delete)
            )
        else:
            logger.info("No items in leaving_soon (first run or empty death row)")

        # Delete items that are in death row AND still match deletion rules
        for radarr_movie in items_to_delete:
            disk_size = radarr_movie.get("sizeOnDisk", 0)
            saved_space += disk_size

            if is_dry_run:
                logger.info(
                    "[DRY-RUN] Would have deleted movie '%s' from death row (%s)",
                    radarr_movie["title"],
                    print_readable_freed_space(disk_size),
                )
            else:
                logger.info(
                    "Deleting movie '%s' from death row (%s)",
                    radarr_movie["title"],
                    print_readable_freed_space(disk_size),
                )
                radarr_instance.del_movie(
                    radarr_movie["id"],
                    delete_files=True,
                    add_exclusion=library.get("add_list_exclusion_on_delete", False),
                )
                # Update Overseerr status if configured
                self.media_cleaner._update_overseerr_status(library, radarr_movie, "movie")

            deleted_items.append(radarr_movie)

        # Get preview candidates for next run (excluding what we just deleted)
        preview_next = library.get("preview_next")
        if preview_next is None:
            preview_next = library.get("max_actions_per_run", 10)

        # Preview = candidates that weren't deleted, limited to preview_next
        deleted_ids = {m.get("id") for m in deleted_items}
        preview_candidates = [
            m for m in all_deletion_candidates
            if m.get("id") not in deleted_ids
        ][:preview_next]

        return saved_space, deleted_items, preview_candidates

    def _process_sonarr_death_row(self, library, sonarr_instance, unfiltered_all_show_data):
        """
        Process shows using the death row pattern.

        The death row collection is NOT the source of truth for deletions.
        We delete items that BOTH:
        1. Currently match deletion rules (watched, past threshold, not excluded, etc.)
        2. Were previously tagged in the death row collection/labels

        This ensures items watched since being tagged won't be deleted.

        Args:
            library: Library configuration dict
            sonarr_instance: Sonarr instance
            unfiltered_all_show_data: All shows from Sonarr

        Returns:
            tuple: (saved_space, deleted_items, preview_candidates)
        """
        from app.media_cleaner import library_meets_disk_space_threshold

        if not library_meets_disk_space_threshold(library, sonarr_instance):
            return 0, [], []

        library_name = library.get("name", "Unknown")
        logger.info("Processing library '%s' with leaving_soon (death row pattern)", library_name)

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
        all_deletion_candidates = self._get_all_deletion_candidates_shows(
            library, sonarr_instance, plex_library, unfiltered_all_show_data
        )

        # Build a map of Plex ratingKey -> Sonarr show for candidates
        candidate_by_plex_key = {}
        for sonarr_show in all_deletion_candidates:
            plex_item = self.media_server.find_item(
                plex_library,
                tvdb_id=sonarr_show.get("tvdbId"),
                imdb_id=sonarr_show.get("imdbId"),
                title=sonarr_show.get("title"),
            )
            if plex_item:
                candidate_by_plex_key[plex_item.ratingKey] = sonarr_show

        # Items to delete = intersection of death row AND current candidates
        items_to_delete = []
        for plex_key in death_row_keys:
            if plex_key in candidate_by_plex_key:
                items_to_delete.append(candidate_by_plex_key[plex_key])

        saved_space = 0
        deleted_items = []
        is_dry_run = self.config.settings.get("dry_run", True)

        if death_row_plex_items:
            logger.info(
                "Found %d items in leaving_soon, %d still match deletion criteria",
                len(death_row_plex_items),
                len(items_to_delete)
            )
        else:
            logger.info("No items in leaving_soon (first run or empty death row)")

        # Delete items that are in death row AND still match deletion rules
        for sonarr_show in items_to_delete:
            disk_size = sonarr_show.get("statistics", {}).get("sizeOnDisk", 0)
            total_episodes = sonarr_show.get("statistics", {}).get("episodeFileCount", 0)
            saved_space += disk_size

            if is_dry_run:
                logger.info(
                    "[DRY-RUN] Would have deleted show '%s' from death row (%s - %s episodes)",
                    sonarr_show["title"],
                    print_readable_freed_space(disk_size),
                    total_episodes,
                )
            else:
                logger.info(
                    "Deleting show '%s' from death row (%s - %s episodes)",
                    sonarr_show["title"],
                    print_readable_freed_space(disk_size),
                    total_episodes,
                )
                self.media_cleaner.delete_series(sonarr_instance, sonarr_show)
                # Update Overseerr status if configured
                self.media_cleaner._update_overseerr_status(library, sonarr_show, "tv")

            deleted_items.append(sonarr_show)

        # Get preview candidates for next run (excluding what we just deleted)
        preview_next = library.get("preview_next")
        if preview_next is None:
            preview_next = library.get("max_actions_per_run", 10)

        # Preview = candidates that weren't deleted, limited to preview_next
        deleted_ids = {s.get("id") for s in deleted_items}
        preview_candidates = [
            s for s in all_deletion_candidates
            if s.get("id") not in deleted_ids
        ][:preview_next]

        return saved_space, deleted_items, preview_candidates

    def _get_all_deletion_candidates_movies(self, library, radarr_instance, plex_library):
        """
        Get ALL movies that currently match deletion rules.

        This is used by the death row pattern to determine which items
        should actually be deleted (intersection of death row AND current candidates).

        Args:
            library: Library configuration dict
            radarr_instance: Radarr instance
            plex_library: Plex library section

        Returns:
            List of all Radarr movie dicts that match deletion criteria
        """
        trakt_movies = self.media_cleaner.get_trakt_items("movie", library)
        movie_activity = self.media_cleaner.get_movie_activity(library, plex_library)
        all_movie_data = radarr_instance.get_movies()

        candidates = []
        for radarr_movie in self.media_cleaner.process_library_rules(
            library, plex_library, all_movie_data, movie_activity, trakt_movies,
            radarr_instance=radarr_instance
        ):
            candidates.append(radarr_movie)

        return candidates

    def _get_all_deletion_candidates_shows(self, library, sonarr_instance, plex_library, unfiltered_all_show_data):
        """
        Get ALL shows that currently match deletion rules.

        This is used by the death row pattern to determine which items
        should actually be deleted (intersection of death row AND current candidates).

        Args:
            library: Library configuration dict
            sonarr_instance: Sonarr instance
            plex_library: Plex library section
            unfiltered_all_show_data: All shows from Sonarr

        Returns:
            List of all Sonarr show dicts that match deletion criteria
        """
        all_show_data = self.media_cleaner.filter_shows(library, unfiltered_all_show_data)
        trakt_items = self.media_cleaner.get_trakt_items("show", library)
        show_activity = self.media_cleaner.get_show_activity(library, plex_library)

        candidates = []
        for sonarr_show in self.media_cleaner.process_library_rules(
            library, plex_library, all_show_data, show_activity, trakt_items,
            sonarr_instance=sonarr_instance
        ):
            candidates.append(sonarr_show)

        return candidates

    def _get_preview_candidates_movies(self, library, radarr_instance, plex_library, preview_limit):
        """
        Get preview candidates for movies (items to be tagged for next run).

        Uses the existing rule-based logic but only returns preview candidates.

        Args:
            library: Library configuration dict
            radarr_instance: Radarr instance
            plex_library: Plex library section
            preview_limit: Maximum number of preview items to return

        Returns:
            List of Radarr movie dicts
        """
        if preview_limit == 0:
            return []

        trakt_movies = self.media_cleaner.get_trakt_items("movie", library)
        movie_activity = self.media_cleaner.get_movie_activity(library, plex_library)
        all_movie_data = radarr_instance.get_movies()

        preview_candidates = []
        for radarr_movie in self.media_cleaner.process_library_rules(
            library, plex_library, all_movie_data, movie_activity, trakt_movies,
            radarr_instance=radarr_instance
        ):
            if len(preview_candidates) >= preview_limit:
                break
            preview_candidates.append(radarr_movie)

        return preview_candidates

    def _get_preview_candidates_shows(self, library, sonarr_instance, plex_library, unfiltered_all_show_data, preview_limit):
        """
        Get preview candidates for shows (items to be tagged for next run).

        Uses the existing rule-based logic but only returns preview candidates.

        Args:
            library: Library configuration dict
            sonarr_instance: Sonarr instance
            plex_library: Plex library section
            unfiltered_all_show_data: All shows from Sonarr
            preview_limit: Maximum number of preview items to return

        Returns:
            List of Sonarr show dicts
        """
        if preview_limit == 0:
            return []

        all_show_data = self.media_cleaner.filter_shows(library, unfiltered_all_show_data)
        trakt_items = self.media_cleaner.get_trakt_items("show", library)
        show_activity = self.media_cleaner.get_show_activity(library, plex_library)

        preview_candidates = []
        for sonarr_show in self.media_cleaner.process_library_rules(
            library, plex_library, all_show_data, show_activity, trakt_items,
            sonarr_instance=sonarr_instance
        ):
            if len(preview_candidates) >= preview_limit:
                break
            preview_candidates.append(sonarr_show)

        return preview_candidates

    def process_radarr(self):
        for name, radarr in self.radarr.items():
            logger.info("Processing radarr instance: '%s'", name)

            saved_space = 0
            all_preview = []
            for library in self.config.settings.get("libraries", []):
                if library.get("radarr") == name:
                    try:
                        leaving_soon_config = library.get("leaving_soon")

                        if leaving_soon_config:
                            # Death row pattern: delete previously tagged items, tag new preview
                            space, deleted, preview = self._process_radarr_death_row(
                                library, radarr
                            )
                        else:
                            # Normal deletion flow
                            space, deleted, preview = self.media_cleaner.process_library_movies(
                                library, radarr
                            )

                        saved_space += space
                        all_preview.extend(preview)
                        self.libraries_processed += 1

                        # Track deleted items for notifications
                        library_name = library.get("name", "Unknown")
                        for item in deleted:
                            self.run_result.add_deleted(
                                DeletedItem.from_radarr(item, library_name, name)
                            )

                        # Process leaving_soon feature - tag preview items for next run
                        self._process_library_leaving_soon(
                            library, preview, "movie"
                        )
                    except ConfigurationError as e:
                        logger.error(str(e))
                        self.libraries_failed += 1

            if self.config.settings.get("dry_run"):
                logger.info(
                    "[DRY-RUN] Would have freed %s of space by deleting movies",
                    print_readable_freed_space(saved_space),
                )
            else:
                logger.info(
                    "Freed %s of space by deleting movies",
                    print_readable_freed_space(saved_space),
                )

            # Log preview of next scheduled deletions
            self._log_preview(all_preview, "movie")

    def process_sonarr(self):
        for name, sonarr in self.sonarr.items():
            logger.info("Processing sonarr instance: '%s'", name)
            unfiltered_all_show_data = sonarr.get_series()

            saved_space = 0
            all_preview = []
            for library in self.config.settings.get("libraries", []):
                if library.get("sonarr") == name:
                    try:
                        leaving_soon_config = library.get("leaving_soon")

                        if leaving_soon_config:
                            # Death row pattern: delete previously tagged items, tag new preview
                            space, deleted, preview = self._process_sonarr_death_row(
                                library, sonarr, unfiltered_all_show_data
                            )
                        else:
                            # Normal deletion flow
                            space, deleted, preview = self.media_cleaner.process_library(
                                library, sonarr, unfiltered_all_show_data
                            )

                        saved_space += space
                        all_preview.extend(preview)
                        self.libraries_processed += 1

                        # Track deleted items for notifications
                        library_name = library.get("name", "Unknown")
                        for item in deleted:
                            self.run_result.add_deleted(
                                DeletedItem.from_sonarr(item, library_name, name)
                            )

                        # Process leaving_soon feature - tag preview items for next run
                        self._process_library_leaving_soon(
                            library, preview, "show"
                        )
                    except ConfigurationError as e:
                        logger.error(str(e))
                        self.libraries_failed += 1

            if self.config.settings.get("dry_run"):
                logger.info(
                    "[DRY-RUN] Would have freed %s of space by deleting shows",
                    print_readable_freed_space(saved_space),
                )
            else:
                logger.info(
                    "Freed %s of space by deleting shows",
                    print_readable_freed_space(saved_space),
                )

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

        # In dry_run mode, skip tagging to avoid confusion
        if is_dry_run:
            logger.debug(
                "Skipping leaving_soon tagging in dry-run mode "
                "(collection/labels won't be updated)"
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
        overseerr_url = self.config.settings.get("overseerr", {}).get("url")

        try:
            self.notifications.send_leaving_soon(
                items,
                plex_url=plex_url,
                overseerr_url=overseerr_url,
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
    1. Single run (default): Runs once and exits. Use with external schedulers (Ofelia, cron).
    2. Scheduler mode: Runs as a long-lived process with built-in scheduling.
       Enable via `scheduler.enabled: true` in settings.yaml.
    """

    locale.setlocale(locale.LC_ALL, "")

    log_level = os.environ.get("LOG_LEVEL", "info").upper()
    logger.init_logger(
        console=True, log_dir="/config/logs", verbose=log_level == "DEBUG"
    )

    logger.info("Running version %s", get_file_contents("/app/commit_tag.txt"))
    logger.info("Log level set to %s", log_level)

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
    scheduler_enabled = scheduler_config.get("enabled", False)

    # CLI flags override config
    if args.run_once:
        scheduler_enabled = False
    elif args.scheduler:
        scheduler_enabled = True

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
