import requests
import time

from app import logger
from app.utils import print_readable_freed_space, parse_size_to_bytes
from datetime import datetime, timedelta
from plexapi.exceptions import NotFound
from plexapi.server import PlexServer
from app.modules.trakt import Trakt
from app.modules.tautulli import Tautulli

DEFAULT_MAX_ACTIONS_PER_RUN = 10
DEFAULT_SONARR_SERIES_TYPE = "standard"


class MediaCleaner:
    def __init__(self, config):
        self.config = config

        # Setup connections
        self.tautulli = Tautulli(
            config.settings.get("tautulli").get("url"),
            config.settings.get("tautulli").get("api_key"),
        )

        self.trakt = Trakt(
            config.settings.get("trakt", {}).get("client_id"),
            config.settings.get("trakt", {}).get("client_secret"),
        )

        # Disable SSL verification to support required secure connections
        # Certificates are not always valid for local connections
        session = requests.Session()
        session.verify = False

        self.plex = PlexServer(
            config.settings.get("plex").get("url"),
            config.settings.get("plex").get("token"),
            timeout=120,
            session=session,
        )

    def get_trakt_items(self, media_type, library):
        return self.trakt.get_all_items_for_url(
            media_type, library.get("exclude", {}).get("trakt", {})
        )

    def get_plex_library(self, library):
        return self.plex.library.section(library.get("name"))

    def get_show_activity(self, library, plex_library):
        return self.tautulli.get_activity(library, plex_library.key)

    def get_movie_activity(self, library, movies_library):
        return self.tautulli.get_activity(library, movies_library.key)

    def filter_shows(self, library, unfiltered_all_show_data):
        return [
            show
            for show in unfiltered_all_show_data
            if show["seriesType"]
            == library.get("series_type", DEFAULT_SONARR_SERIES_TYPE)
        ]

    def process_library(self, library, sonarr_instance, unfiltered_all_show_data):
        if not library_meets_disk_space_threshold(library, sonarr_instance):
            return 0

        all_show_data = self.filter_shows(library, unfiltered_all_show_data)
        logger.info("Instance has %s items to process", len(all_show_data))

        max_actions_per_run = _get_config_value(
            library, "max_actions_per_run", DEFAULT_MAX_ACTIONS_PER_RUN
        )

        logger.info("Processing library '%s'", library.get("name"))

        trakt_items = self.get_trakt_items("show", library)
        logger.info("Got %s trakt items to exclude", len(trakt_items))

        plex_library = self.get_plex_library(library)
        logger.info("Got %s items in plex library", plex_library.totalSize)

        show_activity = self.get_show_activity(library, plex_library)
        logger.info("Got %s items in tautulli activity", len(show_activity))

        return self.process_shows(
            library,
            sonarr_instance,
            plex_library,
            all_show_data,
            show_activity,
            trakt_items,
            max_actions_per_run,
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
    ):
        saved_space = 0
        actions_performed = 0
        for sonarr_show in self.process_library_rules(
            library, plex_library, all_show_data, show_activity, trakt_items
        ):
            if max_actions_per_run and actions_performed >= max_actions_per_run:
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
            actions_performed += 1

            if self.config.settings.get("action_delay"):
                # sleep in seconds
                time.sleep(self.config.settings.get("action_delay"))

        return saved_space

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

        if not self.config.settings.get("dry_run"):
            self.delete_show_if_allowed(
                library,
                sonarr_instance,
                sonarr_show,
                actions_performed,
                max_actions_per_run,
                disk_size,
                total_episodes,
            )
        else:
            logger.info(
                "[DRY-RUN] [%s/%s] Would have deleted show '%s' from sonarr instance '%s'  (%s - %s episodes) ",
                actions_performed,
                max_actions_per_run,
                sonarr_show["title"],
                library.get("name"),
                print_readable_freed_space(disk_size),
                total_episodes,
            )

        return disk_size

    def delete_show_if_allowed(
        self,
        library,
        sonarr_instance,
        sonarr_show,
        actions_performed,
        max_actions_per_run,
        disk_size,
        total_episodes,
    ):
        logger.info(
            "[%s/%s] Deleting show '%s' from sonarr instance  '%s' (%s - %s episodes)",
            actions_performed,
            max_actions_per_run,
            sonarr_show["title"],
            library.get("name"),
            print_readable_freed_space(disk_size),
            total_episodes,
        )
        if self.config.settings.get("interactive"):
            logger.info(
                "Would you like to delete show '%s' from sonarr instance '%s'? (y/n)",
                sonarr_show["title"],
                library.get("name"),
            )
            if input().lower() == "y":
                self.delete_series(sonarr_instance, sonarr_show)
        else:
            self.delete_series(sonarr_instance, sonarr_show)

    def process_library_movies(self, library, radarr_instance, all_movie_data):
        if not library_meets_disk_space_threshold(library, radarr_instance):
            return 0

        max_actions_per_run = _get_config_value(
            library, "max_actions_per_run", DEFAULT_MAX_ACTIONS_PER_RUN
        )

        logger.info("Processing library '%s'", library.get("name"))

        trakt_movies = self.get_trakt_items("movie", library)
        movies_library = self.get_plex_library(library)
        movie_activity = self.get_movie_activity(library, movies_library)

        return self.process_movies(
            library,
            radarr_instance,
            movies_library,
            all_movie_data,
            movie_activity,
            trakt_movies,
            max_actions_per_run,
        )

    def process_movies(
        self,
        library,
        radarr_instance,
        movies_library,
        all_movie_data,
        movie_activity,
        trakt_movies,
        max_actions_per_run,
    ):
        saved_space = 0
        actions_performed = 0
        for radarr_movie in self.process_library_rules(
            library, movies_library, all_movie_data, movie_activity, trakt_movies
        ):
            if max_actions_per_run and actions_performed >= max_actions_per_run:
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
            actions_performed += 1

            if self.config.settings.get("action_delay"):
                # sleep in seconds
                time.sleep(self.config.settings.get("action_delay"))

        return saved_space

    def process_movie(
        self,
        library,
        radarr_instance,
        radarr_movie,
        actions_performed,
        max_actions_per_run,
    ):
        disk_size = radarr_movie.get("sizeOnDisk", 0)

        if not self.config.settings.get("dry_run"):
            self.delete_movie_if_allowed(
                library,
                radarr_instance,
                radarr_movie,
                actions_performed,
                max_actions_per_run,
                disk_size,
            )
        else:
            logger.info(
                "[DRY-RUN] [%s/%s] Would have deleted movie '%s' from radarr instance '%s' (%s)",
                actions_performed,
                max_actions_per_run,
                radarr_movie["title"],
                library.get("name"),
                print_readable_freed_space(disk_size),
            )

        return disk_size

    def delete_movie_if_allowed(
        self,
        library,
        radarr_instance,
        radarr_movie,
        actions_performed,
        max_actions_per_run,
        disk_size,
    ):
        logger.info(
            "[%s/%s] Deleting movie '%s' from radarr instance  '%s' (%s)",
            actions_performed,
            max_actions_per_run,
            radarr_movie["title"],
            library.get("name"),
            print_readable_freed_space(disk_size),
        )
        if self.config.settings.get("interactive"):
            logger.info(
                "Would you like to delete movie '%s' from radarr instance '%s'? (y/n)",
                radarr_movie["title"],
                library.get("name"),
            )
            if input().lower() == "y":
                radarr_instance.del_movie(radarr_movie["id"], delete_files=True)
        else:
            radarr_instance.del_movie(radarr_movie["id"], delete_files=True)

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
        alternate_titles=[],
        imdb_id=None,
        tvdb_id=None,
    ):
        if guid:
            plex_media_item = self.find_by_guid(plex_library, guid)
            if plex_media_item:
                return plex_media_item

        plex_media_item = self.find_by_title_and_year(
            plex_library, title, year, alternate_titles
        )
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

        return None

    def find_by_guid(self, plex_library, guid):
        for guids, plex_media_item in plex_library:
            for plex_guid in guids:
                if guid in plex_guid:
                    return plex_media_item
        logger.debug(f"{guid} not found in Plex")
        return None

    def match_title_and_year(self, plex_media_item, title, year):
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
            or (abs(plex_media_item.year - year)) <= 1
        ):
            return True
        return False

    def find_by_title_and_year(self, plex_library, title, year, alternate_titles):
        for _, plex_media_item in plex_library:
            for t in [title] + alternate_titles:
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

    def process_library_rules(
        self, library_config, plex_library, all_data, activity_data, trakt_movies
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
        if apply_last_watch_threshold_to_collections:
            logger.debug("Gathering collection watched status")
            for guid, watched_data in activity_data.items():
                plex_media_item = self.get_plex_item(plex_guid_item_pair, guid=guid)
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
        for media_data in sort_media(all_data, library_config.get("sort", {})):
            plex_media_item = self.get_plex_item(
                plex_guid_item_pair,
                title=media_data["title"],
                year=media_data["year"],
                alternate_titles=[t["title"] for t in media_data["alternateTitles"]],
                imdb_id=media_data.get("imdb_id"),
                tvdb_id=media_data.get("tvdb_id"),
            )
            if plex_media_item is None:
                if media_data.get("statistics", {}).get("episodeFileCount", 0) == 0:
                    logger.debug(
                        f"{media_data['title']} ({media_data['year']}) not found in Plex, but has no episodes, skipping"
                    )
                else:
                    logger.warning(
                        f"UNMATCHED: {media_data['title']} ({media_data['year']}) not found in Plex."
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

        if not self.check_trakt_movies(media_data, trakt_movies):
            return False

        if not self.check_added_date(media_data, plex_media_item, added_at_threshold):
            return False

        if not self.check_exclusions(library, media_data, plex_media_item):
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

    def check_exclusions(self, library, media_data, plex_media_item):
        exclude = library.get("exclude", {})
        exclusion_checks = [
            self.check_excluded_titles,
            self.check_excluded_genres,
            self.check_excluded_collections,
            self.check_excluded_labels,
            self.check_excluded_release_years,
            self.check_excluded_studios,
            self.check_excluded_producers,
            self.check_excluded_directors,
            self.check_excluded_writers,
            self.check_excluded_actors,
        ]

        return all(
            check(media_data, plex_media_item, exclude) for check in exclusion_checks
        )

    def check_excluded_titles(self, media_data, plex_media_item, exclude):
        for title in exclude.get("titles", []):
            if title.lower() == plex_media_item.title.lower():
                logger.debug(
                    f"{media_data['title']} has excluded title {title}, skipping"
                )
                return False
        return True

    def check_excluded_genres(self, media_data, plex_media_item, exclude):
        for genre in exclude.get("genres", []):
            if genre.lower() in (g.tag.lower() for g in plex_media_item.genres):
                logger.debug(
                    f"{media_data['title']} has excluded genre {genre}, skipping"
                )
                return False
        return True

    def check_excluded_collections(self, media_data, plex_media_item, exclude):
        for collection in exclude.get("collections", []):
            if collection.lower() in (
                g.tag.lower() for g in plex_media_item.collections
            ):
                logger.debug(
                    f"{media_data['title']} has excluded collection {collection}, skipping"
                )
                return False
        return True

    def check_excluded_labels(self, media_data, plex_media_item, exclude):
        for label in exclude.get("plex_labels", []):
            if label.lower() in (g.tag.lower() for g in plex_media_item.labels):
                logger.debug(
                    f"{media_data['title']} has excluded label {label}, skipping"
                )
                return False
        return True

    def check_excluded_release_years(self, media_data, plex_media_item, exclude):
        if (
            exclude.get("release_years", 0)
            and plex_media_item.year
            and plex_media_item.year
            >= datetime.now().year - exclude.get("release_years")
        ):
            logger.debug(
                f"{media_data['title']} ({plex_media_item.year}) was released within the threshold years ({datetime.now().year} - {exclude.get('release_years', 0)} = {datetime.now().year - exclude.get('release_years', 0)}), skipping"
            )
            return False
        return True

    def check_excluded_studios(self, media_data, plex_media_item, exclude):
        if plex_media_item.studio and plex_media_item.studio.lower() in exclude.get(
            "studios", []
        ):
            logger.debug(
                f"{media_data['title']} has excluded studio {plex_media_item.studio}, skipping"
            )
            return False
        return True

    def check_excluded_producers(self, media_data, plex_media_item, exclude):
        for producer in exclude.get("producers", []):
            if producer.lower() in (g.tag.lower() for g in plex_media_item.producers):
                logger.debug(
                    f"{media_data['title']} [{plex_media_item}] has excluded producer {producer}, skipping"
                )
                return False
        return True

    def check_excluded_directors(self, media_data, plex_media_item, exclude):
        for director in exclude.get("directors", []):
            if director.lower() in (g.tag.lower() for g in plex_media_item.directors):
                logger.debug(
                    f"{media_data['title']} [{plex_media_item}] has excluded director {director}, skipping"
                )
                return False
        return True

    def check_excluded_writers(self, media_data, plex_media_item, exclude):
        for writer in exclude.get("writers", []):
            if writer.lower() in (g.tag.lower() for g in plex_media_item.writers):
                logger.debug(
                    f"{media_data['title']} [{plex_media_item}] has excluded writer {writer}, skipping"
                )
                return False
        return True

    def check_excluded_actors(self, media_data, plex_media_item, exclude):
        for actor in exclude.get("actors", []):
            if actor.lower() in (g.tag.lower() for g in plex_media_item.roles):
                logger.debug(
                    f"{media_data['title']} [{plex_media_item}] has excluded actor {actor}, skipping"
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


def sort_media(media_list, sort_config):
    sort_field = sort_config.get("field", "title")
    sort_order = sort_config.get("order", "asc")

    logger.debug(f"Sorting media by {sort_field} {sort_order}")

    sort_key = get_sort_key_function(sort_field)

    sorted_media = sorted(media_list, key=sort_key, reverse=(sort_order == "desc"))
    return sorted_media


def get_sort_key_function(sort_field):
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
    }

    return sort_key_functions.get(sort_field, sort_key_functions["title"])


def get_rating(media_item):
    ratings = media_item.get("ratings", {})
    return (
        ratings.get("imdb", {}).get("value", 0)
        or ratings.get("tmdb", {}).get("value", 0)
        or ratings.get("value", 0)
    )


def _get_config_value(config, key, default=None):
    return config[key] if key in config else default


def library_meets_disk_space_threshold(library, pyarr):
    for item in library.get("disk_size_threshold", []):
        path = item.get("path")
        threshold = item.get("threshold")
        disk_space = pyarr.get_disk_space()
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
            logger.error(
                f"Could not find folder '{path}' in server instance. Skipping library '{library.get('name')}'"
            )
            return False
    return True
