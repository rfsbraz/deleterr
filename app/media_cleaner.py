import re
import time
import unicodedata
from datetime import datetime

import requests
from plexapi.server import PlexServer
from pyarr.exceptions import PyarrResourceNotFound, PyarrServerError

from app import logger
from app.modules.justwatch import JustWatch
from app.modules.overseerr import Overseerr
from app.modules.tautulli import Tautulli
from app.modules.trakt import Trakt
from app.utils import parse_size_to_bytes, print_readable_freed_space

DEFAULT_MAX_ACTIONS_PER_RUN = 10
DEFAULT_SONARR_SERIES_TYPE = "standard"


def normalize_title(title: str) -> str:
    """
    Normalize a title for matching purposes.

    Handles common variations in titles:
    - Strips punctuation (colons, dashes, apostrophes, etc.)
    - Normalizes whitespace
    - Handles articles ("The", "A", "An") at end of title (e.g., "Title, The" -> "the title")
    - Converts to lowercase
    - Normalizes unicode characters (accents, etc.)

    Args:
        title: The title to normalize

    Returns:
        Normalized title string for comparison
    """
    if not title:
        return ""

    # Normalize unicode characters (é -> e, ñ -> n, etc.)
    normalized = unicodedata.normalize("NFKD", title)
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))

    # Convert to lowercase
    normalized = normalized.lower()

    # Handle "Title, The" -> "the title" pattern (article at end of string only)
    # Must match at end of string to avoid false positives like ", and" in middle
    if normalized.endswith(", the"):
        normalized = "the " + normalized[:-5]
    elif normalized.endswith(", a"):
        normalized = "a " + normalized[:-3]
    elif normalized.endswith(", an"):
        normalized = "an " + normalized[:-4]

    # Remove punctuation (keep alphanumeric and spaces)
    normalized = re.sub(r"[^\w\s]", " ", normalized)

    # Normalize whitespace (multiple spaces -> single space, trim)
    normalized = " ".join(normalized.split())

    return normalized


class PlexLibraryIndex:
    """
    Index for O(1) lookups of Plex media items by various identifiers.

    Instead of iterating through the entire library for each lookup (O(n*m)),
    this class builds dictionaries once and provides O(1) lookups thereafter.
    """

    def __init__(self, plex_guid_item_pair):
        """
        Build indices from plex_guid_item_pair list.

        Args:
            plex_guid_item_pair: List of (guids, plex_media_item) tuples
        """
        self.by_tmdb_id = {}
        self.by_tvdb_id = {}
        self.by_imdb_id = {}
        self.by_guid = {}
        self.by_title_year = {}  # Key: (lowercase_title, year)
        self.by_normalized_title_year = {}  # Key: (normalized_title, year) for fuzzy matching
        self.by_filename = {}  # Key: normalized filename (without path/extension)
        self._plex_guid_item_pair = plex_guid_item_pair

        self._build_indices()

    def _normalize_imdb_id(self, imdb_id: str) -> str:
        """Normalize IMDB ID to include 'tt' prefix."""
        if not imdb_id:
            return ""
        imdb_id = str(imdb_id).strip()
        if imdb_id.startswith("tt"):
            return imdb_id
        # Add tt prefix if it's just digits
        if imdb_id.isdigit():
            return f"tt{imdb_id}"
        return imdb_id

    def _extract_filename(self, plex_media_item) -> str:
        """Extract normalized filename from Plex media item."""
        try:
            # Get the first media part's file path
            for media in getattr(plex_media_item, 'media', []):
                for part in getattr(media, 'parts', []):
                    if hasattr(part, 'file') and part.file:
                        # Extract just the filename, normalize it
                        import os
                        filename = os.path.basename(part.file)
                        # Remove extension and normalize
                        name_without_ext = os.path.splitext(filename)[0]
                        return normalize_title(name_without_ext)
        except Exception:
            pass
        return ""

    def _build_indices(self):
        """Build all lookup indices in a single pass through the library."""
        for guids, plex_media_item in self._plex_guid_item_pair:
            # Index by each GUID
            for guid in guids:
                self.by_guid[guid] = plex_media_item

                # Extract and index specific ID types
                if "tmdb://" in guid:
                    tmdb_id = guid.split("tmdb://")[-1].split("?")[0]
                    self.by_tmdb_id[tmdb_id] = plex_media_item
                elif "tvdb://" in guid:
                    tvdb_id = guid.split("tvdb://")[-1].split("?")[0]
                    self.by_tvdb_id[tvdb_id] = plex_media_item
                elif "imdb://" in guid:
                    imdb_id = guid.split("imdb://")[-1].split("?")[0]
                    # Store both with and without tt prefix for flexible matching
                    normalized_imdb = self._normalize_imdb_id(imdb_id)
                    self.by_imdb_id[imdb_id] = plex_media_item
                    if normalized_imdb != imdb_id:
                        self.by_imdb_id[normalized_imdb] = plex_media_item

            # Index by title + year (exact lowercase match)
            if plex_media_item.title and plex_media_item.year:
                key = (plex_media_item.title.lower(), plex_media_item.year)
                if key not in self.by_title_year:
                    self.by_title_year[key] = plex_media_item

                # Also index by normalized title for fuzzy matching
                normalized_key = (normalize_title(plex_media_item.title), plex_media_item.year)
                if normalized_key not in self.by_normalized_title_year:
                    self.by_normalized_title_year[normalized_key] = plex_media_item

            # Index by filename for file-based matching
            filename = self._extract_filename(plex_media_item)
            if filename and filename not in self.by_filename:
                self.by_filename[filename] = plex_media_item

    def find_by_tmdb_id(self, tmdb_id):
        """Find item by TMDB ID. O(1) lookup."""
        return self.by_tmdb_id.get(str(tmdb_id))

    def find_by_tvdb_id(self, tvdb_id):
        """Find item by TVDB ID. O(1) lookup."""
        return self.by_tvdb_id.get(str(tvdb_id))

    def find_by_imdb_id(self, imdb_id):
        """Find item by IMDB ID. O(1) lookup. Handles both with/without 'tt' prefix."""
        if not imdb_id:
            return None
        imdb_str = str(imdb_id)
        # Try exact match first
        result = self.by_imdb_id.get(imdb_str)
        if result:
            return result
        # Try normalized version (with tt prefix)
        normalized = self._normalize_imdb_id(imdb_str)
        return self.by_imdb_id.get(normalized)

    def find_by_filename(self, path_or_filename):
        """Find item by filename. O(1) lookup after normalization."""
        if not path_or_filename:
            return None
        import os
        # Extract just the filename if a full path is provided
        filename = os.path.basename(path_or_filename)
        # Remove extension and normalize
        name_without_ext = os.path.splitext(filename)[0]
        normalized = normalize_title(name_without_ext)
        return self.by_filename.get(normalized)

    def find_by_guid(self, guid):
        """Find item by GUID. O(1) lookup."""
        # Direct lookup first
        if guid in self.by_guid:
            return self.by_guid[guid]

        # Check if guid is contained in any stored guid
        for stored_guid, item in self.by_guid.items():
            if guid in stored_guid:
                return item
        return None

    def find_by_title_and_year(self, title, year, alternate_titles=None, original_title=None):
        """
        Find item by title and year. O(1) for exact match, falls back to normalized matching.

        Matching strategy (in order):
        1. Exact lowercase title + year match
        2. Exact lowercase title + year with ±2 year tolerance
        3. Title with year in parentheses pattern
        4. Normalized title matching (strips punctuation, handles articles)
        5. Normalized title with ±2 year tolerance

        Args:
            title: Primary title to search for
            year: Release year
            alternate_titles: List of alternate titles to try
            original_title: Original language title (e.g., for foreign films)

        Returns:
            Plex media item or None
        """
        if alternate_titles is None:
            alternate_titles = []

        # Build list of all titles to try (includes original title if provided)
        # Filter out None values to prevent AttributeError on .lower()
        all_titles = [t for t in [title] + alternate_titles if t is not None]
        if original_title and original_title not in all_titles:
            all_titles.append(original_title)

        # Phase 1: Try exact lowercase matching
        for t in all_titles:
            if year:
                # Exact match
                key = (t.lower(), year)
                if key in self.by_title_year:
                    return self.by_title_year[key]

                # Allow 2 years difference
                for year_offset in [-1, 1, -2, 2]:
                    key = (t.lower(), year + year_offset)
                    if key in self.by_title_year:
                        return self.by_title_year[key]

            # Try title with year in parentheses
            title_with_year = f"{t.lower()} ({year})"
            for (stored_title, stored_year), item in self.by_title_year.items():
                if stored_title == title_with_year:
                    return item

        # Phase 2: Try normalized title matching (handles punctuation, articles, etc.)
        for t in all_titles:
            normalized_t = normalize_title(t)
            if year:
                # Exact normalized match
                key = (normalized_t, year)
                if key in self.by_normalized_title_year:
                    logger.debug(f"Matched '{t}' via normalized title: '{normalized_t}'")
                    return self.by_normalized_title_year[key]

                # Allow 2 years difference with normalized title
                for year_offset in [-1, 1, -2, 2]:
                    key = (normalized_t, year + year_offset)
                    if key in self.by_normalized_title_year:
                        logger.debug(
                            f"Matched '{t}' via normalized title with year offset: "
                            f"'{normalized_t}' (year {year} -> {year + year_offset})"
                        )
                        return self.by_normalized_title_year[key]

        return None

    def get_plex_guid_item_pair(self):
        """Return the original plex_guid_item_pair for backward compatibility."""
        return self._plex_guid_item_pair


class MediaCleaner:
    def __init__(self, config, media_server=None):
        self.config = config
        self.media_server = media_server

        self.watched_collections = set()
        self._justwatch_instances = {}  # Cache for JustWatch instances per country

        # Setup connections
        # SSL verification is disabled by default for self-signed certificates
        # Set ssl_verify: true in config for secure connections
        ssl_verify = config.settings.get("ssl_verify", False)

        self.tautulli = Tautulli(
            config.settings.get("tautulli").get("url"),
            config.settings.get("tautulli").get("api_key"),
            ssl_verify=ssl_verify,
        )

        self.trakt = Trakt(
            config.settings.get("trakt", {}).get("client_id"),
            config.settings.get("trakt", {}).get("client_secret"),
        )

        # Initialize Overseerr if configured
        overseerr_config = config.settings.get("overseerr", {})
        if overseerr_config.get("url") and overseerr_config.get("api_key"):
            self.overseerr = Overseerr(
                overseerr_config.get("url"),
                overseerr_config.get("api_key"),
                ssl_verify=ssl_verify,
            )
        else:
            self.overseerr = None

        # Configure session with SSL verification setting
        session = requests.Session()
        session.verify = ssl_verify

        self.plex = PlexServer(
            config.settings.get("plex").get("url"),
            config.settings.get("plex").get("token"),
            timeout=120,
            session=session,
        )

    def get_justwatch_instance(self, library):
        """
        Get or create a JustWatch instance for the given library.

        Returns None if JustWatch is not configured for this library.
        """
        jw_config = library.get("exclude", {}).get("justwatch", {})
        if not jw_config:
            return None

        # Get country from library config or global config
        global_jw = self.config.settings.get("justwatch", {})
        country = jw_config.get("country") or global_jw.get("country")
        language = jw_config.get("language") or global_jw.get("language", "en")

        if not country:
            return None

        # Cache JustWatch instances by country+language
        cache_key = f"{country}:{language}"
        if cache_key not in self._justwatch_instances:
            logger.debug(f"Creating JustWatch instance for {country}/{language}")
            self._justwatch_instances[cache_key] = JustWatch(country, language)

        return self._justwatch_instances[cache_key]

    def get_trakt_items(self, media_type, library):
        return self.trakt.get_all_items_for_url(
            media_type, library.get("exclude", {}).get("trakt", {})
        )

    def get_plex_library(self, library):
        return self.plex.library.section(library.get("name"))

    def get_show_activity(self, library, plex_library):
        return self.tautulli.get_activity(plex_library.key)

    def get_movie_activity(self, library, movies_library):
        return self.tautulli.get_activity(movies_library.key)

    def filter_shows(self, library, unfiltered_all_show_data):
        return [
            show
            for show in unfiltered_all_show_data
            if show["seriesType"]
               == library.get("series_type", DEFAULT_SONARR_SERIES_TYPE)
        ]

    def process_library(self, library, sonarr_instance, unfiltered_all_show_data):
        """
        Process a Sonarr library.

        Returns:
            tuple: (saved_space, deleted_items, preview_candidates) where:
                - saved_space: bytes freed by deletions
                - deleted_items: list of show data that was deleted
                - preview_candidates: list of shows that would be deleted next
        """
        if not library_meets_disk_space_threshold(library, sonarr_instance):
            return 0, [], []

        all_show_data = self.filter_shows(library, unfiltered_all_show_data)
        logger.info(
            f"Instance has {len(all_show_data)} items to process of type "
            f"'{library.get('series_type', DEFAULT_SONARR_SERIES_TYPE)}'"
        )

        if not all_show_data:
            return 0, [], []

        max_actions_per_run = _get_config_value(
            library, "max_actions_per_run", DEFAULT_MAX_ACTIONS_PER_RUN
        )

        # Determine preview limit: explicit value, or default to max_actions_per_run
        preview_next = library.get("preview_next")
        if preview_next is None:
            preview_next = max_actions_per_run or 0

        library_name = library.get('name')
        logger.debug(f"Fetching Plex library '{library_name}'...")
        plex_library = self.get_plex_library(library)
        logger.info(f"Plex library loaded ({plex_library.totalSize} items)")

        trakt_items = self.get_trakt_items("show", library)
        logger.info(f"Got {len(trakt_items)} trakt items to exclude")

        show_activity = self.get_show_activity(library, plex_library)
        logger.info(f"Got {len(show_activity)} items in tautulli activity")

        return self.process_shows(
            library,
            sonarr_instance,
            plex_library,
            all_show_data,
            show_activity,
            trakt_items,
            max_actions_per_run,
            preview_next,
        )

    def process_shows(
            self,
            library,
            sonarr_instance,
            plex_library,
            all_show_data,
            show_activity,
            trakt_items,
            max_actions_per_run,
            preview_next=0,
    ):
        """
        Process shows for deletion.

        Returns:
            tuple: (saved_space, deleted_items, preview_candidates)
        """
        saved_space = 0
        actions_performed = 0
        deleted_items = []
        preview_candidates = []

        for sonarr_show in self.process_library_rules(
                library, plex_library, all_show_data, show_activity, trakt_items, sonarr_instance=sonarr_instance
        ):
            if max_actions_per_run and actions_performed >= max_actions_per_run:
                # Continue collecting preview candidates after hitting the limit
                if preview_next > 0 and len(preview_candidates) < preview_next:
                    preview_candidates.append(sonarr_show)
                    continue
                # Stop once we have enough preview candidates (or preview is disabled)
                if len(preview_candidates) >= preview_next:
                    break
                logger.info(
                    f"Reached max actions per run ({max_actions_per_run}), stopping"
                )
                break

            saved_space += self.process_show(
                library,
                sonarr_instance,
                sonarr_show,
                actions_performed,
                max_actions_per_run,
            )
            deleted_items.append(sonarr_show)
            actions_performed += 1

            if self.config.settings.get("action_delay"):
                # sleep in seconds
                time.sleep(self.config.settings.get("action_delay"))

        return saved_space, deleted_items, preview_candidates

    def process_show(
            self,
            library,
            sonarr_instance,
            sonarr_show,
            actions_performed,
            max_actions_per_run,
    ):
        disk_size = sonarr_show.get("statistics", {}).get("sizeOnDisk", 0)
        total_episodes = sonarr_show.get("statistics", {}).get("episodeFileCount", 0)

        is_dry_run = self.config.settings.get("dry_run")

        logger.log_deletion(
            title=sonarr_show["title"],
            size_bytes=disk_size,
            media_type="show",
            is_dry_run=is_dry_run,
            action_num=actions_performed,
            max_actions=max_actions_per_run,
            extra_info=f"{total_episodes} episodes",
        )

        if not is_dry_run:
            self.delete_show_if_allowed(
                library,
                sonarr_instance,
                sonarr_show,
            )

        return disk_size

    def delete_show_if_allowed(
            self,
            library,
            sonarr_instance,
            sonarr_show,
    ):
        self.delete_series(sonarr_instance, sonarr_show)

        # Update Overseerr status after successful deletion
        self._update_overseerr_status(library, sonarr_show, "tv")

    def process_library_movies(self, library, radarr_instance):
        """
        Process a Radarr library.

        Returns:
            tuple: (saved_space, deleted_items, preview_candidates) where:
                - saved_space: bytes freed by deletions
                - deleted_items: list of movie data that was deleted
                - preview_candidates: list of movies that would be deleted next
        """
        if not library_meets_disk_space_threshold(library, radarr_instance):
            return 0, [], []

        max_actions_per_run = _get_config_value(
            library, "max_actions_per_run", DEFAULT_MAX_ACTIONS_PER_RUN
        )

        # Determine preview limit: explicit value, or default to max_actions_per_run
        preview_next = library.get("preview_next")
        if preview_next is None:
            preview_next = max_actions_per_run or 0

        library_name = library.get('name')
        logger.debug(f"Fetching Plex library '{library_name}'...")
        movies_library = self.get_plex_library(library)
        logger.info(f"Plex library loaded ({movies_library.totalSize} items)")

        trakt_movies = self.get_trakt_items("movie", library)
        movie_activity = self.get_movie_activity(library, movies_library)

        return self.process_movies(
            library,
            radarr_instance,
            movies_library,
            movie_activity,
            trakt_movies,
            max_actions_per_run,
            preview_next,
        )

    def process_movies(
            self,
            library,
            radarr_instance,
            movies_library,
            movie_activity,
            trakt_movies,
            max_actions_per_run,
            preview_next=0,
    ):
        """
        Process movies for deletion.

        Returns:
            tuple: (saved_space, deleted_items, preview_candidates)
        """
        saved_space = 0
        actions_performed = 0
        deleted_items = []
        preview_candidates = []

        all_movie_data = radarr_instance.get_movies()

        for radarr_movie in self.process_library_rules(
                library, movies_library, all_movie_data, movie_activity, trakt_movies, radarr_instance=radarr_instance
        ):
            if max_actions_per_run and actions_performed >= max_actions_per_run:
                # Continue collecting preview candidates after hitting the limit
                if preview_next > 0 and len(preview_candidates) < preview_next:
                    preview_candidates.append(radarr_movie)
                    continue
                # Stop once we have enough preview candidates (or preview is disabled)
                if len(preview_candidates) >= preview_next:
                    break
                logger.info(
                    f"Reached max actions per run ({max_actions_per_run}), stopping"
                )
                break

            saved_space += self.process_movie(
                library,
                radarr_instance,
                radarr_movie,
                actions_performed,
                max_actions_per_run,
            )
            deleted_items.append(radarr_movie)
            actions_performed += 1

            if self.config.settings.get("action_delay"):
                # sleep in seconds
                time.sleep(self.config.settings.get("action_delay"))

        return saved_space, deleted_items, preview_candidates

    def process_movie(
            self,
            library,
            radarr_instance,
            radarr_movie,
            actions_performed,
            max_actions_per_run,
    ):
        disk_size = radarr_movie.get("sizeOnDisk", 0)

        is_dry_run = self.config.settings.get("dry_run")

        logger.log_deletion(
            title=radarr_movie["title"],
            size_bytes=disk_size,
            media_type="movie",
            is_dry_run=is_dry_run,
            action_num=actions_performed,
            max_actions=max_actions_per_run,
        )

        if not is_dry_run:
            self.delete_movie_if_allowed(
                library,
                radarr_instance,
                radarr_movie,
            )

        return disk_size

    def delete_series(self, sonarr, sonarr_show):
        # PyArr doesn't support deleting the series files, so we need to do it manually
        episodes = sonarr.get_episode(sonarr_show["id"], series=True)

        # Mark all episodes as unmonitored so they don't get re-downloaded while we're deleting them
        sonarr.upd_episode_monitor([episode["id"] for episode in episodes], False)

        # delete the files
        skip_deleting_show = False
        for episode in episodes:
            try:
                if episode["episodeFileId"] != 0:
                    sonarr.del_episode_file(episode["episodeFileId"])
            except PyarrResourceNotFound:
                # If the episode file doesn't exist, it's probably because it was already deleted by sonarr
                # Sometimes happens for multi-episode files - this is expected and not an error
                logger.debug(
                    f"Episode file already deleted for '{sonarr_show['title']}' (file ID: {episode['episodeFileId']})"
                )
            except PyarrServerError as e:
                # If the episode file is still in use or another server error, we can't delete the show
                error_msg = str(e).lower()
                if "in use" in error_msg or "locked" in error_msg:
                    logger.error(
                        f"Cannot delete '{sonarr_show['title']}': Episode file is in use (being played or downloaded). "
                        "Will retry on next run."
                    )
                else:
                    logger.error(
                        f"Sonarr error deleting episode file for '{sonarr_show['title']}': {e}. "
                        "Check Sonarr logs for details. Will retry on next run."
                    )
                skip_deleting_show = True
                break

        # delete the series
        if not skip_deleting_show:
            sonarr.del_series(sonarr_show["id"], delete_files=True)
        else:
            logger.warning(
                f"Skipping deletion of '{sonarr_show['title']}' - will be deleted on the next run"
            )

    def delete_movie_if_allowed(
            self,
            library,
            radarr_instance,
            radarr_movie,
    ):
        radarr_instance.del_movie(
            radarr_movie["id"],
            delete_files=True,
            add_exclusion=library.get("add_list_exclusion_on_delete", False),
        )

        # Update Overseerr status after successful deletion
        self._update_overseerr_status(library, radarr_movie, "movie")

    def _update_overseerr_status(self, library, media_data, media_type):
        """
        Update Overseerr status after deletion if configured.

        Args:
            library: Library configuration
            media_data: Media data from Sonarr/Radarr
            media_type: 'movie' or 'tv'
        """
        overseerr_config = library.get("exclude", {}).get("overseerr", {})
        if not overseerr_config.get("update_status") or not self.overseerr:
            return

        tmdb_id = media_data.get("tmdbId")
        if not tmdb_id:
            logger.debug(
                f"Cannot update Overseerr status for '{media_data.get('title')}': no TMDB ID"
            )
            return

        try:
            if self.overseerr.mark_as_deleted(tmdb_id, media_type):
                logger.info(
                    f"Updated Overseerr status for '{media_data.get('title')}' (TMDB: {tmdb_id})"
                )
            else:
                logger.debug(
                    f"Could not update Overseerr status for '{media_data.get('title')}' - "
                    "may not have been requested via Overseerr"
                )
        except Exception as e:
            logger.warning(
                f"Overseerr status update failed for '{media_data.get('title')}': {e}. "
                "The item will still be deleted but will remain marked as 'available' in Overseerr."
            )

    def get_death_row_items(self, library_config, plex_library):
        """
        Get items that were tagged for deletion on previous run ("death row" items).

        These items were in the leaving_soon collection/had the label from the previous run,
        meaning they've had their warning period and should now be deleted.

        Args:
            library_config: Library configuration dict
            plex_library: Plex library section

        Returns:
            List of Plex media items that should be deleted
        """
        leaving_soon_config = library_config.get("leaving_soon")
        if not leaving_soon_config or not self.media_server:
            return []

        items_to_delete = []
        seen_keys = set()

        # Get items from collection (presence of config = enabled)
        collection_config = leaving_soon_config.get("collection")
        if collection_config:
            collection_name = collection_config.get("name", "Leaving Soon")
            try:
                collection = plex_library.collection(collection_name)
                for item in collection.items():
                    if item.ratingKey not in seen_keys:
                        items_to_delete.append(item)
                        seen_keys.add(item.ratingKey)
            except Exception:
                # Collection doesn't exist (first run) - this is expected
                pass

        # Get items with label (presence of config = enabled)
        labels_config = leaving_soon_config.get("labels")
        if labels_config:
            label_name = labels_config.get("name", "leaving-soon")
            labeled_items = self.media_server.get_items_with_label(plex_library, label_name)
            for item in labeled_items:
                if item.ratingKey not in seen_keys:
                    items_to_delete.append(item)
                    seen_keys.add(item.ratingKey)

        return items_to_delete

    def process_leaving_soon(self, library_config, plex_library, items_to_tag, media_type):
        """
        Update leaving soon collection and labels for preview items.

        This is called AFTER deletions to tag new preview candidates for the next run.

        Args:
            library_config: Library configuration dict
            plex_library: Plex library section
            items_to_tag: List of media items from Radarr/Sonarr to tag
            media_type: 'movie' or 'show'
        """
        leaving_soon_config = library_config.get("leaving_soon")
        if not leaving_soon_config:
            return

        if not self.media_server:
            logger.warning("Media server not configured, cannot process leaving_soon")
            return

        library_name = library_config.get("name", "Unknown")

        # Find Plex items for the preview candidates
        plex_items = []
        for item in items_to_tag:
            plex_item = self.media_server.find_item(
                plex_library,
                tmdb_id=item.get("tmdbId"),
                tvdb_id=item.get("tvdbId"),
                imdb_id=item.get("imdbId"),
                title=item.get("title"),
                year=item.get("year"),
            )
            if plex_item:
                plex_items.append(plex_item)
            else:
                logger.debug(
                    f"Could not find '{item.get('title')}' ({item.get('year')}) in Plex for leaving_soon"
                )

        logger.info(
            f"Processing leaving_soon for library '{library_name}': {len(plex_items)} items to tag"
        )

        # Update collection (presence of config = enabled)
        collection_config = leaving_soon_config.get("collection")
        if collection_config is not None:
            self._update_leaving_soon_collection(
                plex_library, plex_items, collection_config
            )

        # Update labels (presence of config = enabled)
        labels_config = leaving_soon_config.get("labels")
        if labels_config is not None:
            self._update_leaving_soon_labels(
                plex_library, plex_items, labels_config
            )

    def _update_leaving_soon_collection(self, plex_library, plex_items, collection_config):
        """
        Update the leaving soon collection with the given items.

        Args:
            plex_library: Plex library section
            plex_items: List of Plex media items to add to collection
            collection_config: Collection configuration dict
        """
        collection_name = collection_config.get("name", "Leaving Soon")
        promote_home = collection_config.get("promote_home", True)
        promote_shared = collection_config.get("promote_shared", True)

        try:
            collection = self.media_server.get_or_create_collection(
                plex_library, collection_name
            )
            self.media_server.set_collection_items(collection, plex_items)

            # Set visibility on home screens (shared users by default)
            self.media_server.set_collection_visibility(
                collection, home=promote_home, shared=promote_shared
            )

            if plex_items:
                logger.info(
                    f"Updated collection '{collection_name}' with {len(plex_items)} items"
                )
            else:
                logger.info(f"Cleared collection '{collection_name}' (no items to tag)")
        except Exception as e:
            logger.error(
                f"Failed to update leaving_soon collection '{collection_name}': {e}. "
                "Users will not see updated leaving_soon notifications in Plex."
            )

    def _update_leaving_soon_labels(self, plex_library, plex_items, labels_config):
        """
        Update leaving soon labels on media items.

        Clears all existing labels and adds them to the new preview items.
        This is part of the death row pattern where items are tagged, then deleted next run.

        Args:
            plex_library: Plex library section
            plex_items: List of Plex media items to label
            labels_config: Labels configuration dict
        """
        label_name = labels_config.get("name", "leaving-soon")

        # Build set of item keys for quick lookup
        current_item_keys = {item.ratingKey for item in plex_items}

        # Clear all existing labels first (items that had the label were already deleted)
        existing_labeled = self.media_server.get_items_with_label(
            plex_library, label_name
        )
        removed_count = 0
        for item in existing_labeled:
            if item.ratingKey not in current_item_keys:
                self.media_server.remove_label(item, label_name)
                logger.debug(f"Removed label '{label_name}' from '{item.title}'")
                removed_count += 1

        # Add labels to current preview items
        for item in plex_items:
            # Check if item already has the label
            existing_labels = [l.tag.lower() for l in item.labels]
            if label_name.lower() not in existing_labels:
                self.media_server.add_label(item, label_name)
                logger.debug(f"Added label '{label_name}' to '{item.title}'")

        if plex_items:
            logger.info(f"Updated labels: {len(plex_items)} items now have '{label_name}'")
        else:
            if removed_count > 0:
                logger.info(f"Cleared '{label_name}' label from {removed_count} items")
            else:
                logger.debug(f"No items had '{label_name}' label to clear")

    def get_library_config(self, config, show):
        return next(
            (
                library
                for library in config.config.get("libraries", [])
                if library.get("name") == show
            ),
            None,
        )

    def get_plex_item(
        self,
        plex_library,
        guid=None,
        title=None,
        year=None,
        alternate_titles=None,
        imdb_id=None,
        tvdb_id=None,
        tmdb_id=None,
        index=None,
        original_title=None,
        path=None,
    ):
        """
        Find a Plex media item using various identifiers.

        Args:
            plex_library: Either a list of (guids, plex_media_item) tuples or a PlexLibraryIndex
            guid: Plex GUID to search for
            title: Title to search for
            year: Release year
            alternate_titles: List of alternate titles
            imdb_id: IMDB ID
            tvdb_id: TVDB ID
            tmdb_id: TMDB ID
            index: Optional PlexLibraryIndex for O(1) lookups
            original_title: Original language title (e.g., for foreign films)
            path: File path from Radarr/Sonarr for filename matching as last resort

        Returns:
            Plex media item or None
        """
        if alternate_titles is None:
            alternate_titles = []

        # Use index for O(1) lookups if available
        if index is not None:
            return self._get_plex_item_indexed(
                index, guid, title, year, alternate_titles, imdb_id, tvdb_id, tmdb_id, original_title, path
            )

        # Fallback to O(n) iteration-based lookups
        if guid:
            plex_media_item = self.find_by_guid(plex_library, guid)
            if plex_media_item:
                return plex_media_item

        if tvdb_id:
            plex_media_item = self.find_by_tvdb_id(plex_library, tvdb_id)
            if plex_media_item:
                return plex_media_item

        if imdb_id:
            plex_media_item = self.find_by_imdb_id(plex_library, imdb_id)
            if plex_media_item:
                return plex_media_item

        if tmdb_id:
            plex_media_item = self.find_by_tmdb_id(plex_library, tmdb_id)
            if plex_media_item:
                return plex_media_item

        plex_media_item = self.find_by_title_and_year(
            plex_library, title, year, alternate_titles
        )

        return plex_media_item

    def _get_plex_item_indexed(
        self, index, guid, title, year, alternate_titles, imdb_id, tvdb_id, tmdb_id, original_title=None, path=None
    ):
        """
        Find a Plex media item using the PlexLibraryIndex for O(1) lookups.

        Matching order:
        1. GUID (direct Plex identifier)
        2. TVDB ID (for TV shows)
        3. IMDB ID (normalized to handle tt prefix)
        4. TMDB ID
        5. Title + year (exact, then normalized for fuzzy matching)
        6. Filename (if path provided, as last resort)
        """
        if guid:
            plex_media_item = index.find_by_guid(guid)
            if plex_media_item:
                return plex_media_item

        if tvdb_id:
            plex_media_item = index.find_by_tvdb_id(tvdb_id)
            if plex_media_item:
                return plex_media_item

        if imdb_id:
            plex_media_item = index.find_by_imdb_id(imdb_id)
            if plex_media_item:
                return plex_media_item

        if tmdb_id:
            plex_media_item = index.find_by_tmdb_id(tmdb_id)
            if plex_media_item:
                return plex_media_item

        plex_media_item = index.find_by_title_and_year(title, year, alternate_titles, original_title)
        if plex_media_item:
            return plex_media_item

        # Last resort: try to match by filename
        if path:
            plex_media_item = index.find_by_filename(path)
            if plex_media_item:
                logger.debug(f"Matched '{title}' via filename from path: {path}")
                return plex_media_item

        return None

    def find_by_guid(self, plex_library, guid):
        for guids, plex_media_item in plex_library:
            for plex_guid in guids:
                if guid in plex_guid:
                    return plex_media_item
        logger.debug(f"{guid} not found in Plex")
        return None

    def match_title_and_year(self, plex_media_item, title, year):
        if not title:
            return False
        if (
                title.lower() == plex_media_item.title.lower()
                or f"{title.lower()} ({year})" == plex_media_item.title.lower()
        ):
            return True
        return False

    def match_year(self, plex_media_item, year):
        if (
                not year
                or not plex_media_item.year
                or plex_media_item.year == year
                or (abs(plex_media_item.year - year)) <= 2  # Allow 2 years of difference in the release date
        ):
            return True
        return False

    def find_by_title_and_year(self, plex_library, title, year, alternate_titles):
        # Filter out None values to prevent AttributeError
        all_titles = [t for t in [title] + alternate_titles if t is not None]
        for _, plex_media_item in plex_library:
            for t in all_titles:
                if self.match_title_and_year(
                        plex_media_item, t, year
                ) and self.match_year(plex_media_item, year):
                    return plex_media_item
        return None

    def find_by_tvdb_id(self, plex_library, tvdb_id):
        for _, plex_media_item in plex_library:
            for guid in plex_media_item.guids:
                if f"tvdb://{tvdb_id}" in guid.id:
                    return plex_media_item
        return None

    def find_by_imdb_id(self, plex_library, imdb_id):
        for _, plex_media_item in plex_library:
            for guid in plex_media_item.guids:
                if f"imdb://{imdb_id}" in guid.id:
                    return plex_media_item
        return None

    def find_by_tmdb_id(self, plex_library, tmdb_id):
        for _, plex_media_item in plex_library:
            for guid in plex_media_item.guids:
                if f"tmdb://{tmdb_id}" in guid.id:
                    return plex_media_item
        return None

    def process_library_rules(
            self, library_config, plex_library, all_data, activity_data, trakt_movies, radarr_instance=None, sonarr_instance=None
    ):
        # get the time thresholds from the config
        last_watched_threshold = library_config.get("last_watched_threshold", None)
        added_at_threshold = library_config.get("added_at_threshold", None)
        apply_last_watch_threshold_to_collections = library_config.get(
            "apply_last_watch_threshold_to_collections", False
        )

        plex_guid_item_pair = [
            (
                [plex_media_item.guid] + [g.id for g in plex_media_item.guids],
                plex_media_item,
            )
            for plex_media_item in plex_library.all()
        ]

        # Build index once for O(1) lookups instead of O(n) iterations per item
        plex_index = PlexLibraryIndex(plex_guid_item_pair)
        logger.debug(
            f"Built Plex library index: {len(plex_index.by_tmdb_id)} TMDB, "
            f"{len(plex_index.by_tvdb_id)} TVDB, {len(plex_index.by_imdb_id)} IMDB, "
            f"{len(plex_index.by_title_year)} title+year, "
            f"{len(plex_index.by_normalized_title_year)} normalized, "
            f"{len(plex_index.by_filename)} filename entries"
        )

        if apply_last_watch_threshold_to_collections:
            logger.debug("Gathering collection watched status")
            for guid, watched_data in activity_data.items():
                plex_media_item = self.get_plex_item(plex_guid_item_pair, guid=guid, index=plex_index)
                if plex_media_item is None:
                    continue
                last_watched = (datetime.now() - watched_data["last_watched"]).days
                if (
                        plex_media_item.collections
                        and last_watched_threshold is not None
                        and last_watched < last_watched_threshold
                ):
                    logger.debug(
                        f"{watched_data['title']} watched {last_watched} days ago, adding collection {plex_media_item.collections} to watched collections"
                    )
                    self.watched_collections = self.watched_collections | {
                        c.tag for c in plex_media_item.collections
                    }

        unmatched = 0
        for media_data in sort_media(all_data, library_config.get("sort", {}), activity_data, plex_guid_item_pair):
            plex_media_item = self.get_plex_item(
                plex_guid_item_pair,
                title=media_data["title"],
                year=media_data["year"],
                alternate_titles=[t["title"] for t in media_data["alternateTitles"]],
                imdb_id=media_data.get("imdbId"),
                tvdb_id=media_data.get("tvdbId"),
                tmdb_id=media_data.get("tmdbId"),
                index=plex_index,
                original_title=media_data.get("originalTitle"),
                path=media_data.get("path"),  # Used for filename matching as last resort
            )

            if plex_media_item is None:
                if not media_data.get("movieFileId", {}) and media_data.get("statistics", {}).get("episodeFileCount", 0) == 0:
                    logger.debug(
                        f"{media_data['title']} ({media_data['year']}) not found in Plex, but has no episodes, skipping"
                    )
                else:
                    # Build debug info for unmatched items
                    ids_tried = []
                    if media_data.get("tmdbId"):
                        ids_tried.append(f"TMDB:{media_data['tmdbId']}")
                    if media_data.get("imdbId"):
                        ids_tried.append(f"IMDB:{media_data['imdbId']}")
                    if media_data.get("tvdbId"):
                        ids_tried.append(f"TVDB:{media_data['tvdbId']}")

                    logger.warning(
                        f"UNMATCHED: {media_data['title']} ({media_data['year']}) not found in Plex. "
                        f"IDs tried: {', '.join(ids_tried) if ids_tried else 'none'}. "
                        f"Normalized title: '{normalize_title(media_data['title'])}'"
                    )
                    unmatched += 1
                continue
            if not self.is_movie_actionable(
                    library_config,
                    activity_data,
                    media_data,
                    trakt_movies,
                    plex_media_item,
                    last_watched_threshold,
                    added_at_threshold,
                    apply_last_watch_threshold_to_collections,
                    radarr_instance,
                    sonarr_instance
            ):
                continue

            yield media_data

        logger.info(f"Found {len(all_data)} items, {unmatched} unmatched")

    def is_movie_actionable(
            self,
            library,
            activity_data,
            media_data,
            trakt_movies,
            plex_media_item,
            last_watched_threshold,
            added_at_threshold,
            apply_last_watch_threshold_to_collections,
            radarr_instance=None,
            sonarr_instance=None
    ):
        if not self.check_watched_status(
                library,
                activity_data,
                media_data,
                plex_media_item,
                last_watched_threshold,
        ):
            return False

        if not self.check_collections(
                apply_last_watch_threshold_to_collections,
                media_data,
                plex_media_item,
        ):
            return False

        if not self.check_exclusions(library, media_data, plex_media_item, radarr_instance, sonarr_instance):
            return False

        if not self.check_added_date(media_data, plex_media_item, added_at_threshold):
            return False

        if not self.check_trakt_movies(media_data, trakt_movies):
            return False

        return True

    def check_watched_status(
            self,
            library,
            activity_data,
            media_data,
            plex_media_item,
            last_watched_threshold,
    ):
        if watched_data := find_watched_data(plex_media_item, activity_data):
            last_watched = (datetime.now() - watched_data["last_watched"]).days
            if last_watched_threshold and last_watched < last_watched_threshold:
                logger.debug(
                    f"{media_data['title']} watched {last_watched} days ago, skipping"
                )
                return False
            if library.get("watch_status") == "unwatched":
                logger.debug(f"{media_data['title']} watched, skipping")
                return False
        elif library.get("watch_status") == "watched":
            logger.debug(f"{media_data['title']} not watched, skipping")
            return False

        return True

    def check_collections(
            self,
            apply_last_watch_threshold_to_collections,
            media_data,
            plex_media_item,
    ):
        if apply_last_watch_threshold_to_collections:
            if already_watched := self.watched_collections.intersection(
                    {c.tag for c in plex_media_item.collections}
            ):
                logger.debug(
                    f"{media_data['title']} has watched collections ({already_watched}), skipping"
                )
                return False

        return True

    def check_trakt_movies(self, media_data, trakt_movies):
        if media_data.get("tvdb_id", media_data.get("tmdbId")) in trakt_movies:
            logger.debug(
                f"{media_data['title']} found in trakt watched list {trakt_movies[media_data.get('tvdb_id', media_data.get('tmdbId'))]['list']}, skipping"
            )
            return False

        return True

    def check_added_date(self, media_data, plex_media_item, added_at_threshold):
        date_added = (datetime.now() - plex_media_item.addedAt).days
        if added_at_threshold and date_added < added_at_threshold:
            logger.debug(f"{media_data['title']} added {date_added} days ago, skipping")
            return False

        return True

    def check_exclusions(self, library, media_data, plex_media_item, radarr_instance=None, sonarr_instance=None):
        exclude = library.get("exclude", {})
        exclusion_checks = [
            lambda m, pmi, e: check_excluded_radarr_fields(m, pmi, e, radarr_instance),
            lambda m, pmi, e: check_excluded_sonarr_fields(m, pmi, e, sonarr_instance),
            lambda m, pmi, e: check_excluded_titles(m, pmi, e),
            lambda m, pmi, e: check_excluded_genres(m, pmi, e),
            lambda m, pmi, e: check_excluded_collections(m, pmi, e),
            lambda m, pmi, e: check_excluded_labels(m, pmi, e),
            lambda m, pmi, e: check_excluded_release_years(m, pmi, e),
            lambda m, pmi, e: check_excluded_studios(m, pmi, e),
            lambda m, pmi, e: check_excluded_producers(m, pmi, e),
            lambda m, pmi, e: check_excluded_directors(m, pmi, e),
            lambda m, pmi, e: check_excluded_writers(m, pmi, e),
            lambda m, pmi, e: check_excluded_actors(m, pmi, e),
        ]

        if not all(
            check(media_data, plex_media_item, exclude) for check in exclusion_checks
        ):
            return False

        # JustWatch exclusion check (requires justwatch_instance)
        justwatch_instance = self.get_justwatch_instance(library)
        if not check_excluded_justwatch(
            media_data, plex_media_item, exclude, justwatch_instance
        ):
            return False

        # Overseerr exclusion check (requires overseerr instance)
        if not check_excluded_overseerr(
            media_data, plex_media_item, exclude, self.overseerr
        ):
            return False

        return True


def check_excluded_radarr_fields(media_data, plex_media_item, exclude, radarr_instance):
    """
    Check if a movie should be excluded based on Radarr-specific fields.

    Args:
        media_data: Media data from Radarr (already contains full movie data from get_movies())
        plex_media_item: Plex media item
        exclude: Exclusion configuration from library
        radarr_instance: Radarr instance (may be None if not configured)

    Returns:
        True if media should NOT be excluded (i.e., is actionable)
        False if media should be excluded (i.e., skip this media)
    """
    radarr_exclusions = exclude.get("radarr", {})

    if not radarr_exclusions or not radarr_instance:
        return True

    # For movies, media_data already contains the movie data from Radarr's get_movies()
    # We use this directly rather than fetching again (same pattern as check_excluded_sonarr_fields)
    radarr_media_item = media_data

    if 'monitored' in radarr_exclusions and radarr_exclusions.get("monitored") == radarr_media_item.get("monitored"):
        logger.debug(f"{media_data['title']} has excluded radarr monitored status, skipping")
        return False

    if (radarr_exclusions.get('quality_profiles')
            and radarr_instance.check_movie_has_quality_profiles(
                radarr_media_item,
                radarr_exclusions.get('quality_profiles')
            )
    ):
        logger.debug(f"{media_data['title']} has excluded radarr quality profiles, skipping")
        return False

    if radarr_exclusions.get('tags') and radarr_instance.check_movie_has_tags(radarr_media_item,
                                                                              radarr_exclusions.get('tags')):
        logger.debug(f"{media_data['title']} has excluded radarr tags, skipping")
        return False

    if radarr_exclusions.get('paths'):
        for path in radarr_exclusions.get('paths'):
            if path in radarr_media_item.get('path', ''):
                logger.debug(f"{media_data['title']} has excluded radarr path, skipping")
                return False

    return True


def check_excluded_sonarr_fields(media_data, plex_media_item, exclude, sonarr_instance):
    """
    Check if a TV show should be excluded based on Sonarr-specific fields.

    Args:
        media_data: Media data from Sonarr
        plex_media_item: Plex media item
        exclude: Exclusion configuration from library
        sonarr_instance: DSonarr instance (may be None if not configured)

    Returns:
        True if media should NOT be excluded (i.e., is actionable)
        False if media should be excluded (i.e., skip this media)
    """
    sonarr_exclusions = exclude.get("sonarr", {})

    if not sonarr_exclusions or not sonarr_instance:
        return True

    # For TV shows, media_data already contains the series data from Sonarr
    # We use this directly rather than fetching again
    sonarr_media_item = media_data

    # Check status exclusion
    if sonarr_exclusions.get('status'):
        series_status = sonarr_media_item.get("status", "").lower()
        excluded_statuses = [s.lower() for s in sonarr_exclusions.get('status')]
        if series_status in excluded_statuses:
            logger.debug(f"{media_data['title']} has excluded sonarr status '{series_status}', skipping")
            return False

    # Check monitored exclusion
    if 'monitored' in sonarr_exclusions and sonarr_exclusions.get("monitored") == sonarr_media_item.get("monitored"):
        logger.debug(f"{media_data['title']} has excluded sonarr monitored status, skipping")
        return False

    # Check quality profiles exclusion
    if (sonarr_exclusions.get('quality_profiles')
            and sonarr_instance.check_series_has_quality_profiles(
                sonarr_media_item,
                sonarr_exclusions.get('quality_profiles')
            )
    ):
        logger.debug(f"{media_data['title']} has excluded sonarr quality profiles, skipping")
        return False

    # Check tags exclusion
    if sonarr_exclusions.get('tags') and sonarr_instance.check_series_has_tags(
            sonarr_media_item,
            sonarr_exclusions.get('tags')
    ):
        logger.debug(f"{media_data['title']} has excluded sonarr tags, skipping")
        return False

    # Check paths exclusion
    if sonarr_exclusions.get('paths'):
        for path in sonarr_exclusions.get('paths'):
            if path in sonarr_media_item.get('path', ''):
                logger.debug(f"{media_data['title']} has excluded sonarr path, skipping")
                return False

    return True


def check_excluded_titles(media_data, plex_media_item, exclude):
    for title in exclude.get("titles", []):
        if title.lower() == plex_media_item.title.lower():
            logger.debug(f"{media_data['title']} has excluded title {title}, skipping")
            return False
    return True


def check_excluded_genres(media_data, plex_media_item, exclude):
    for genre in exclude.get("genres", []):
        if genre.lower() in (g.tag.lower() for g in plex_media_item.genres):
            logger.debug(f"{media_data['title']} has excluded genre {genre}, skipping")
            return False
    return True


def check_excluded_collections(media_data, plex_media_item, exclude):
    for collection in exclude.get("collections", []):
        if collection.lower() in (g.tag.lower() for g in plex_media_item.collections):
            logger.debug(
                f"{media_data['title']} has excluded collection {collection}, skipping"
            )
            return False
    return True


def check_excluded_labels(media_data, plex_media_item, exclude):
    for label in exclude.get("plex_labels", []):
        if label.lower() in (g.tag.lower() for g in plex_media_item.labels):
            logger.debug(f"{media_data['title']} has excluded label {label}, skipping")
            return False
    return True


def check_excluded_release_years(media_data, plex_media_item, exclude):
    if (
            exclude.get("release_years", 0)
            and plex_media_item.year
            and plex_media_item.year >= datetime.now().year - exclude.get("release_years")
    ):
        logger.debug(
            f"{media_data['title']} ({plex_media_item.year}) was released within the threshold years ({datetime.now().year} - {exclude.get('release_years', 0)} = {datetime.now().year - exclude.get('release_years', 0)}), skipping"
        )
        return False
    return True


def check_excluded_studios(media_data, plex_media_item, exclude):
    if plex_media_item.studio and plex_media_item.studio.lower() in exclude.get(
            "studios", []
    ):
        logger.debug(
            f"{media_data['title']} has excluded studio {plex_media_item.studio}, skipping"
        )
        return False
    return True


def check_excluded_producers(media_data, plex_media_item, exclude):
    for producer in exclude.get("producers", []):
        if producer.lower() in (g.tag.lower() for g in plex_media_item.producers):
            logger.debug(
                f"{media_data['title']} [{plex_media_item}] has excluded producer {producer}, skipping"
            )
            return False
    return True


def check_excluded_directors(media_data, plex_media_item, exclude):
    for director in exclude.get("directors", []):
        if director.lower() in (g.tag.lower() for g in plex_media_item.directors):
            logger.debug(
                f"{media_data['title']} [{plex_media_item}] has excluded director {director}, skipping"
            )
            return False
    return True


def check_excluded_writers(media_data, plex_media_item, exclude):
    for writer in exclude.get("writers", []):
        if writer.lower() in (g.tag.lower() for g in plex_media_item.writers):
            logger.debug(
                f"{media_data['title']} [{plex_media_item}] has excluded writer {writer}, skipping"
            )
            return False
    return True


def check_excluded_actors(media_data, plex_media_item, exclude):
    for actor in exclude.get("actors", []):
        if actor.lower() in (g.tag.lower() for g in plex_media_item.roles):
            logger.debug(
                f"{media_data['title']} [{plex_media_item}] has excluded actor {actor}, skipping"
            )
            return False
    return True


def check_excluded_justwatch(media_data, plex_media_item, exclude, justwatch_instance):
    """
    Check if media should be excluded based on JustWatch streaming availability.

    Args:
        media_data: Media data from Sonarr/Radarr
        plex_media_item: Plex media item
        exclude: Exclusion configuration from library
        justwatch_instance: JustWatch instance (may be None if not configured)

    Returns:
        True if media should NOT be excluded (i.e., is actionable)
        False if media should be excluded (i.e., skip this media)
    """
    jw_config = exclude.get("justwatch", {})

    if not jw_config or not justwatch_instance:
        return True

    title = media_data.get("title") or plex_media_item.title
    year = media_data.get("year") or plex_media_item.year
    # Determine media type based on data structure
    media_type = "movie" if "tmdbId" in media_data else "show"

    # Check available_on mode (exclude if available on specified providers)
    if providers := jw_config.get("available_on"):
        if justwatch_instance.available_on(title, year, media_type, providers):
            logger.debug(
                f"{title} is available on streaming service(s) {providers}, skipping"
            )
            return False

    # Check not_available_on mode (exclude if NOT available on specified providers)
    if providers := jw_config.get("not_available_on"):
        if justwatch_instance.is_not_available_on(title, year, media_type, providers):
            logger.debug(
                f"{title} is not available on streaming service(s) {providers}, skipping"
            )
            return False

    return True


def check_excluded_overseerr(media_data, plex_media_item, exclude, overseerr_instance):
    """
    Check if media should be excluded/included based on Overseerr requests.

    Args:
        media_data: Media data from Sonarr/Radarr
        plex_media_item: Plex media item
        exclude: Exclusion configuration from library
        overseerr_instance: Overseerr instance (may be None if not configured)

    Returns:
        True if media should NOT be excluded (i.e., is actionable)
        False if media should be excluded (i.e., skip this media)
    """
    from app.modules.overseerr import (
        REQUEST_STATUS_PENDING,
        REQUEST_STATUS_APPROVED,
        REQUEST_STATUS_DECLINED,
    )

    overseerr_config = exclude.get("overseerr", {})

    if not overseerr_config or not overseerr_instance:
        return True

    tmdb_id = media_data.get("tmdbId")
    if not tmdb_id:
        logger.debug(
            f"'{media_data.get('title')}' has no TMDB ID, cannot check Overseerr requests"
        )
        return True

    mode = overseerr_config.get("mode", "exclude")
    users = overseerr_config.get("users")
    include_pending = overseerr_config.get("include_pending", True)
    request_status_filter = overseerr_config.get("request_status")
    min_request_age_days = overseerr_config.get("min_request_age_days")

    # Map status names to constants
    status_name_map = {
        "pending": REQUEST_STATUS_PENDING,
        "approved": REQUEST_STATUS_APPROVED,
        "declined": REQUEST_STATUS_DECLINED,
    }

    # Get request data for advanced filtering
    request_data = overseerr_instance.get_request_data(tmdb_id)

    # Basic request check (considering users and include_pending)
    if users:
        is_requested = overseerr_instance.is_requested_by(tmdb_id, users, include_pending)
    else:
        is_requested = overseerr_instance.is_requested(tmdb_id, include_pending)

    # Apply request_status filter if specified
    if is_requested and request_status_filter and request_data:
        # Convert status filter to numeric values
        allowed_statuses = [
            status_name_map.get(s.lower())
            for s in request_status_filter
            if s.lower() in status_name_map
        ]
        if allowed_statuses:
            current_status = request_data.get("status")
            if current_status not in allowed_statuses:
                # Request exists but doesn't match status filter
                is_requested = False
                logger.debug(
                    f"'{media_data.get('title')}' request status doesn't match filter {request_status_filter}, treating as not requested"
                )

    # Apply min_request_age_days filter if specified
    if is_requested and min_request_age_days and request_data:
        created_at = request_data.get("created_at")
        if created_at:
            try:
                # Parse ISO format date string
                request_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                age_days = (datetime.now(request_date.tzinfo) - request_date).days
                if age_days < min_request_age_days:
                    # Request is too recent
                    is_requested = False
                    logger.debug(
                        f"'{media_data.get('title')}' request is only {age_days} days old (min: {min_request_age_days}), treating as not requested"
                    )
            except (ValueError, TypeError) as e:
                logger.debug(f"Could not parse request date for '{media_data.get('title')}': {e}")

    if mode == "exclude":
        # Exclude mode: skip requested items (don't delete them)
        if is_requested:
            logger.debug(
                f"'{media_data.get('title')}' has Overseerr request, skipping"
            )
            return False
    elif mode == "include_only":
        # Include-only mode: ONLY delete items that were requested
        if not is_requested:
            logger.debug(
                f"'{media_data.get('title')}' not requested via Overseerr, skipping"
            )
            return False

    return True


def find_watched_data(plex_media_item, activity_data):
    if resp := activity_data.get(plex_media_item.guid):
        return resp

    for guid, history in activity_data.items():
        if guid_matches(plex_media_item, guid) or title_and_year_match(
                plex_media_item, history
        ):
            return history

    return None


def guid_matches(plex_media_item, guid):
    return guid in plex_media_item.guid


def title_and_year_match(plex_media_item, history):
    return (
            history["title"] == plex_media_item.title
            and history["year"]
            and plex_media_item.year
            and plex_media_item.year != history["year"]
            and (abs(plex_media_item.year - history["year"])) <= 1
    )


def sort_media(media_list, sort_config, activity_data=None, plex_guid_item_pair=None):
    """Sort media by one or more fields with configurable order per field.

    Special handling for 'last_watched' field:
    - Unwatched items (inf) ALWAYS come first, regardless of order setting
    - The order setting only affects how watched items are sorted among themselves
    - This ensures unwatched content is prioritized for deletion before recently-watched content
    """
    from functools import cmp_to_key

    field_str = sort_config.get("field", "title")
    order_str = sort_config.get("order", "asc")

    fields = [f.strip() for f in field_str.split(",")]
    orders = [o.strip() for o in order_str.split(",")]

    # Extend orders to match fields length (reuse last order)
    while len(orders) < len(fields):
        orders.append(orders[-1])

    logger.debug(f"Sorting media by {fields} with orders {orders}")

    def compare_items(a, b):
        """Compare two media items using multi-level sort criteria."""
        for field, order in zip(fields, orders):
            key_func = get_sort_key_function(field, activity_data, plex_guid_item_pair)
            val_a = key_func(a)
            val_b = key_func(b)

            if val_a == val_b:
                continue

            # Handle None values - push to end
            if val_a is None:
                return 1 if order == "asc" else -1
            if val_b is None:
                return -1 if order == "asc" else 1

            # Special handling for last_watched: unwatched items (inf) ALWAYS come first
            # This ensures unwatched content is deleted before watched content, regardless
            # of the order setting. The order only affects sorting among watched items.
            if field == "last_watched":
                a_unwatched = val_a == float('inf')
                b_unwatched = val_b == float('inf')
                if a_unwatched and not b_unwatched:
                    return -1  # Unwatched 'a' comes first
                if b_unwatched and not a_unwatched:
                    return 1   # Unwatched 'b' comes first
                # Both watched or both unwatched - apply normal order

            # Compare values
            if val_a < val_b:
                return -1 if order == "asc" else 1
            else:
                return 1 if order == "asc" else -1

        return 0

    return sorted(media_list, key=cmp_to_key(compare_items))


def get_sort_key_function(sort_field, activity_data=None, plex_guid_item_pair=None):
    """Get the sort key function for a given field."""

    def get_last_watched_days(media_item):
        """Return days since last watched, or infinity for unwatched items."""
        if activity_data is None or plex_guid_item_pair is None:
            return float('inf')

        plex_item = get_plex_item_for_sort(media_item, plex_guid_item_pair)
        if plex_item is None:
            return float('inf')

        watched_data = find_watched_data(plex_item, activity_data)
        if watched_data is None:
            return float('inf')

        return (datetime.now() - watched_data["last_watched"]).days

    sort_key_functions = {
        "title": lambda media_item: media_item.get("sortTitle", ""),
        "size": lambda media_item: media_item.get("sizeOnDisk")
                                   or media_item.get("statistics", {}).get("sizeOnDisk", 0),
        "release_year": lambda media_item: media_item.get("year", 0),
        "runtime": lambda media_item: media_item.get("runtime", 0),
        "added_date": lambda media_item: media_item.get("added", ""),
        "rating": lambda media_item: get_rating(media_item),
        "seasons": lambda media_item: media_item.get("statistics", {}).get(
            "seasonCount", 1
        ),
        "episodes": lambda media_item: media_item.get("statistics", {}).get(
            "totalEpisodeCount", 1
        ),
        "last_watched": get_last_watched_days,
    }

    return sort_key_functions.get(sort_field, sort_key_functions["title"])


def get_plex_item_for_sort(media_data, plex_guid_item_pair):
    """Lightweight Plex item lookup for sorting purposes."""
    for plex_guid, plex_item in plex_guid_item_pair:
        # Try GUID-based matching (most reliable)
        if media_data.get("imdbId") and f"imdb://{media_data['imdbId']}" in plex_guid:
            return plex_item
        if media_data.get("tmdbId") and f"tmdb://{media_data['tmdbId']}" in plex_guid:
            return plex_item
        if media_data.get("tvdbId") and f"tvdb://{media_data['tvdbId']}" in plex_guid:
            return plex_item

    # Fallback to title+year matching
    media_title = media_data.get("title")
    if media_title:
        for plex_guid, plex_item in plex_guid_item_pair:
            if (plex_item.title.lower() == media_title.lower()
                and media_data.get("year")
                and plex_item.year
                and abs(plex_item.year - media_data["year"]) <= 2):
                return plex_item

    return None


def get_rating(media_item):
    ratings = media_item.get("ratings", {})
    return (
            ratings.get("imdb", {}).get("value", 0)
            or ratings.get("tmdb", {}).get("value", 0)
            or ratings.get("value", 0)
    )


def _get_config_value(config, key, default=None):
    return config[key] if key in config else default


class ConfigurationError(Exception):
    """Raised when there's a configuration error that prevents processing."""
    pass


def library_meets_disk_space_threshold(library, dpyarr_instance):
    for item in library.get("disk_size_threshold", []):
        path = item.get("path")
        threshold = item.get("threshold")
        disk_space = dpyarr_instance.get_disk_space()
        folder_found = False
        for folder in disk_space:
            if folder["path"] == path:
                folder_found = True
                free_space = folder["freeSpace"]
                logger.debug(
                    f"Free space for '{path}': {print_readable_freed_space(free_space)} (threshold: {threshold})"
                )
                if free_space > parse_size_to_bytes(threshold):
                    logger.info(
                        f"Skipping library '{library.get('name')}' as free space is above threshold ({print_readable_freed_space(free_space)} > {threshold})"
                    )
                    return False
        if not folder_found:
            raise ConfigurationError(
                f"Could not find folder '{path}' in server instance for library '{library.get('name')}'. "
                f"Check that the path matches a root folder in your Radarr/Sonarr settings."
            )
    return True
