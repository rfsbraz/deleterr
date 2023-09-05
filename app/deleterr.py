# encoding: utf-8

import logging
import locale
import time
import os
import yaml
import sys

from datetime import datetime, timedelta
from pyarr.sonarr import SonarrAPI
from pyarr.radarr import RadarrAPI
from app.modules.tautulli import Tautulli
from app.modules.trakt import Trakt
from app import logger
from plexapi.server import PlexServer
from plexapi.exceptions import NotFound
from app.utils import print_readable_freed_space
from app.config import load_config
from pyarr.exceptions import PyarrResourceNotFound, PyarrServerError

logging.basicConfig()

DEFAULT_MAX_ACTIONS_PER_RUN = 10
DEFAULT_SONARR_SERIES_TYPE = "standard"

class Deleterr:
    def __init__(self, config):
        self.config = config

        # Setup connections
        self.tautulli = Tautulli(
            config.settings.get("tautulli").get("url"),
            config.settings.get("tautulli").get("api_key"),
        )
        self.plex = PlexServer(
            config.settings.get("plex").get("url"),
            config.settings.get("plex").get("token"),
            timeout=120,
        )
        self.sonarr = {
            connection["name"]: SonarrAPI(connection["url"], connection["api_key"])
            for connection in config.settings.get("sonarr", [])
        }
        self.radarr = {
            connection["name"]: RadarrAPI(connection["url"], connection["api_key"])
            for connection in config.settings.get("radarr", [])
        }
        self.trakt = Trakt(
            config.settings.get("trakt", {}).get("client_id"),
            config.settings.get("trakt", {}).get("client_secret"),
        )
        self.watched_collections = set()

        self.process_sonarr()
        self.process_radarr()

    def delete_series(self, sonarr, sonarr_show):
        ## PyArr doesn't support deleting the series files, so we need to do it manually
        episodes = sonarr.get_episode(sonarr_show["id"], series=True)

        # Mark all episodes as unmonitored so they don't get re-downloaded while we're deleting them
        sonarr.upd_episode_monitor([episode["id"] for episode in episodes], False)

        # delete the files
        skip_deleting_show = False
        for episode in episodes:
            try:
                if episode["episodeFileId"] != 0:
                    sonarr.del_episode_file(episode["episodeFileId"])
            except PyarrResourceNotFound as e:
                # If the episode file doesn't exist, it's probably because it was already deleted by sonarr
                # Sometimes happens for multi-episode files
                logger.debug(
                    f"Failed to delete episode file {episode['episodeFileId']} for show {sonarr_show['id']} ({sonarr_show['title']}): {e}"
                )
            except PyarrServerError as e:
                # If the episode file is still in use, we can't delete the show
                logger.error(
                    f"Failed to delete episode file {episode['episodeFileId']} for show {sonarr_show['id']} ({sonarr_show['title']}): {e}"
                )
                skip_deleting_show = True
                break

        # delete the series
        if not skip_deleting_show:
            sonarr.del_series(sonarr_show["id"], delete_files=True)
        else:
            logger.info(
                f"Skipping deleting show {sonarr_show['id']} ({sonarr_show['title']}) due to errors deleting episode files. It will be deleted on the next run."
            )

    def process_sonarr(self):
        for name, sonarr in self.sonarr.items():
            logger.info("Processing sonarr instance: '%s'", name)
            unfiltered_all_show_data = sonarr.get_series()

            saved_space = 0
            for library in self.config.settings.get("libraries", []):
                if library.get("sonarr") == name:
                    all_show_data = [
                        show
                        for show in unfiltered_all_show_data
                        if show["seriesType"]
                        == library.get("series_type", DEFAULT_SONARR_SERIES_TYPE)
                    ]
                    logger.info("Instance has %s items to process", len(all_show_data))

                    max_actions_per_run = _get_config_value(
                        library, "max_actions_per_run", DEFAULT_MAX_ACTIONS_PER_RUN
                    )

                    logger.info("Processing library '%s'", library.get("name"))

                    trakt_items = self.trakt.get_all_shows_for_url(
                        library.get("exclude", {}).get("trakt", {})
                    )
                    logger.info("Got %s trakt items to exclude", len(trakt_items))

                    plex_library = self.plex.library.section(library.get("name"))
                    logger.info("Got %s items in plex library", plex_library.totalSize)

                    show_activity = self.tautulli.get_activity(
                        library, plex_library.key
                    )
                    logger.info("Got %s items in tautulli activity", len(show_activity))

                    actions_performed = 0
                    for sonarr_show in self.process_library_rules(
                        library, plex_library, all_show_data, show_activity, trakt_items
                    ):
                        import pdb

                        pdb.set_trace()
                        disk_size = sonarr_show.get("statistics", {}).get(
                            "sizeOnDisk", 0
                        )
                        total_episodes = sonarr_show.get("statistics", {}).get(
                            "episodeFileCount", 0
                        )

                        if (
                            max_actions_per_run
                            and actions_performed >= max_actions_per_run
                        ):
                            logger.info(
                                f"Reached max actions per run ({max_actions_per_run}), stopping"
                            )
                            break
                        if not self.config.settings.get("dry_run"):
                            logger.info(
                                "[%s/%s] Deleting show '%s' from sonarr instance  '%s' (%s - %s episodes)",
                                actions_performed,
                                max_actions_per_run,
                                sonarr_show["title"],
                                name,
                                print_readable_freed_space(disk_size),
                                total_episodes,
                            )
                            if self.config.settings.get("interactive"):
                                logger.info(
                                    "Would you like to delete show '%s' from sonarr instance '%s'? (y/n)",
                                    sonarr_show["title"],
                                    name,
                                )
                                if input().lower() == "y":
                                    self.delete_series(sonarr, sonarr_show)
                            else:
                                self.delete_series(sonarr, sonarr_show)
                        else:
                            logger.info(
                                "[DRY-RUN] [%s/%s] Would have deleted show '%s' from sonarr instance '%s'  (%s - %s episodes) ",
                                actions_performed,
                                max_actions_per_run,
                                sonarr_show["title"],
                                name,
                                print_readable_freed_space(disk_size),
                                total_episodes,
                            )

                        saved_space += disk_size
                        actions_performed += 1

                        if self.config.settings.get("action_delay"):
                            # sleep in seconds
                            time.sleep(self.config.settings.get("action_delay"))

                    logger.info(
                        "Freed %s of space by deleting %s shows",
                        print_readable_freed_space(saved_space),
                        actions_performed,
                    )

    def process_radarr(self):
        for name, radarr in self.radarr.items():
            logger.info("Processing radarr instance: '%s'", name)
            all_movie_data = radarr.get_movie()

            logger.info("[%s] Got %s movies to process", name, len(all_movie_data))

            saved_space = 0
            for library in self.config.settings.get("libraries", []):
                if library.get("radarr") == name:
                    max_actions_per_run = _get_config_value(
                        library, "max_actions_per_run", DEFAULT_MAX_ACTIONS_PER_RUN
                    )

                    logger.info("Processing library '%s'", library.get("name"))

                    trakt_movies = self.trakt.get_all_movies_for_url(
                        library.get("exclude", {}).get("trakt", {})
                    )
                    logger.info("Got %s trakt movies to exclude", len(trakt_movies))

                    movies_library = self.plex.library.section(library.get("name"))
                    logger.info(
                        "Got %s movies in plex library", movies_library.totalSize
                    )

                    movie_activity = self.tautulli.get_activity(
                        library, movies_library.key
                    )
                    logger.info(
                        "Got %s movies in tautulli activity", len(movie_activity)
                    )

                    actions_performed = 0
                    for radarr_movie in self.process_library_rules(
                        library,
                        movies_library,
                        all_movie_data,
                        movie_activity,
                        trakt_movies,
                    ):
                        disk_size = radarr_movie.get("sizeOnDisk", 0)

                        if (
                            max_actions_per_run
                            and actions_performed >= max_actions_per_run
                        ):
                            logger.info(
                                f"Reached max actions per run ({max_actions_per_run}), stopping"
                            )
                            break
                        if not self.config.settings.get("dry_run"):
                            logger.info(
                                "[%s/%s] Deleting movie '%s' from radarr instance  '%s' (%s)",
                                actions_performed,
                                max_actions_per_run,
                                radarr_movie["title"],
                                name,
                                print_readable_freed_space(disk_size),
                            )
                            if self.config.settings.get("interactive"):
                                logger.info(
                                    "Would you like to delete movie '%s' from radarr instance '%s'? (y/n)",
                                    radarr_movie["title"],
                                    name,
                                )
                                if input().lower() == "y":
                                    radarr.del_movie(
                                        radarr_movie["id"], delete_files=True
                                    )
                            else:
                                radarr.del_movie(radarr_movie["id"], delete_files=True)
                        else:
                            logger.info(
                                "[DRY-RUN] [%s/%s] Would have deleted movie '%s' from radarr instance '%s' (%s)",
                                actions_performed,
                                max_actions_per_run,
                                radarr_movie["title"],
                                name,
                                print_readable_freed_space(disk_size),
                            )

                        saved_space += disk_size
                        actions_performed += 1

                        if self.config.settings.get("action_delay"):
                            # sleep in seconds
                            time.sleep(self.config.settings.get("action_delay"))

                    logger.info(
                        "Freed %s of space by deleting %s movies",
                        print_readable_freed_space(saved_space),
                        actions_performed,
                    )

            if self.config.settings.get("dry_run"):
                logger.info("[DRY-RUN] Would have updated plex library")
                logger.info("[DRY-RUN] Would have updated tautulli library")

            elif self.config.settings.get("interactive"):
                logger.info(
                    "Would you like to refresh plex library '%s'? (y/n)",
                    movies_library.title,
                )
                if input().lower() == "y":
                    movies_library.refresh()
                logger.info(
                    "Would you like to refresh tautulli library '%s'? (y/n)",
                    movies_library.title,
                )
                if input().lower() == "y":
                    self.tautulli.refresh_library(movies_library.key)
            else:
                if self.config.settings.get("plex_library_scan_after_actions"):
                    movies_library.refresh()
                if self.config.settings.get("tautulli_library_scan_after_actions"):
                    self.tautulli.refresh_library(movies_library.key)

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
        imdbId=None,
        tvdbId=None,
        teste=None,
    ):
        if guid:
            for guids, plex_media_item in plex_library:
                # Check if any guid cmatches
                for plex_guid in guids:
                    if guid in plex_guid:
                        return plex_media_item
            logger.debug(f"{guid} not found in Plex")

        # Plex may pick some different titles sometimes, and since we can't only fetch by title, we need to check all of them
        for _, plex_media_item in plex_library:
            # Check if any title matches
            for t in [title] + alternate_titles:
                if (
                    t.lower() == plex_media_item.title.lower()
                    or f"{t.lower()} ({year})" == plex_media_item.title.lower()
                ):
                    if (
                        not year
                        or not plex_media_item.year
                        or plex_media_item.year == year
                    ):
                        return plex_media_item

                    if (abs(plex_media_item.year - year)) <= 1:
                        return plex_media_item
            # Check tvdbId is in any of the guids
            if tvdbId:
                for guid in plex_media_item.guids:
                    if f"tvdb://{tvdbId}" in guid.id:
                        return plex_media_item
            if imdbId:
                for guid in plex_media_item.guids:
                    if f"imdb://{imdbId}" in guid.id:
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
                    and last_watched_threshold
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
                imdbId=media_data.get("imdbId"),
                tvdbId=media_data.get("tvdbId"),
                teste=media_data,
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
        if watched_data := find_watched_data(plex_media_item, activity_data):
            last_watched = (datetime.now() - watched_data["last_watched"]).days
            if last_watched_threshold and last_watched < last_watched_threshold:
                logger.debug(
                    f"{media_data['title']} watched {last_watched} days ago, skipping"
                )
                return False

        if apply_last_watch_threshold_to_collections:
            if already_watched := self.watched_collections.intersection(
                {c.tag for c in plex_media_item.collections}
            ):
                logger.debug(
                    f"{media_data['title']} has watched collections ({already_watched}), skipping"
                )
                return False

        # Check if the movie tmdb id is in the trakt watched list
        if media_data.get("tvdbId", media_data.get("tmdbId")) in trakt_movies:
            logger.debug(
                f"{media_data['title']} found in trakt watched list {trakt_movies[media_data.get('tvdbId', media_data.get('tmdbId'))]['list']}, skipping"
            )
            return False

        # Days since added
        date_added = (datetime.now() - plex_media_item.addedAt).days
        if added_at_threshold and date_added < added_at_threshold:
            logger.debug(f"{media_data['title']} added {date_added} days ago, skipping")
            return False

        if exclude := library.get("exclude", {}):
            for title in exclude.get("titles", []):
                if title.lower() == plex_media_item.title.lower():
                    logger.debug(
                        f"{media_data['title']} has excluded title {title}, skipping"
                    )
                    return False

            for genre in exclude.get("genres", []):
                if genre.lower() in (g.tag.lower() for g in plex_media_item.genres):
                    logger.debug(
                        f"{media_data['title']} has excluded genre {genre}, skipping"
                    )
                    return False

            for collection in exclude.get("collections", []):
                if collection.lower() in (
                    g.tag.lower() for g in plex_media_item.collections
                ):
                    logger.debug(
                        f"{media_data['title']} has excluded collection {collection}, skipping"
                    )
                    return False

            if exclude.get("release_years", 0):
                if (
                    plex_media_item.year
                    and plex_media_item.year
                    >= datetime.now().year - exclude.get("release_years")
                ):
                    logger.debug(
                        f"{media_data['title']} ({plex_media_item.year}) was released within the threshold years ({datetime.now().year} - {exclude.get('release_years', 0)} = {datetime.now().year - exclude.get('release_years', 0)}), skipping"
                    )
                    return False

            if plex_media_item.studio and plex_media_item.studio.lower() in exclude.get(
                "studios", []
            ):
                logger.debug(
                    f"{media_data['title']} has excluded studio {plex_media_item.studio}, skipping"
                )
                return False

            # Producers, directors, writers, actors are only available for shows per episode, so we need to check each episode
            if hasattr(plex_media_item, "episodes"):
                for episode in plex_media_item.episodes():
                    for producer in exclude.get("producers", []):
                        if producer.lower() in (
                            g.tag.lower() for g in episode.producers
                        ):
                            logger.debug(
                                f"{media_data['title']} [{episode}] has excluded producer {producer}, skipping"
                            )
                            return False

                    for director in exclude.get("directors", []):
                        if director.lower() in (
                            g.tag.lower() for g in episode.directors
                        ):
                            logger.debug(
                                f"{media_data['title']} [{episode}] has excluded director {director}, skipping"
                            )
                            return False

                    for writer in exclude.get("writers", []):
                        if writer.lower() in (g.tag.lower() for g in episode.writers):
                            logger.debug(
                                f"{media_data['title']} [{episode}] has excluded writer {writer}, skipping"
                            )
                            return False

                    for actor in exclude.get("actors", []):
                        if actor.lower() in (g.tag.lower() for g in episode.roles):
                            logger.debug(
                                f"{media_data['title']} [{episode}] has excluded actor {actor}, skipping"
                            )
                            return False
            else:
                for producer in exclude.get("producers", []):
                    if producer.lower() in (
                        g.tag.lower() for g in plex_media_item.producers
                    ):
                        logger.debug(
                            f"{media_data['title']} [{plex_media_item}] has excluded producer {producer}, skipping"
                        )
                        return False

                for director in exclude.get("directors", []):
                    if director.lower() in (
                        g.tag.lower() for g in plex_media_item.directors
                    ):
                        logger.debug(
                            f"{media_data['title']} [{plex_media_item}] has excluded director {director}, skipping"
                        )
                        return False

                for writer in exclude.get("writers", []):
                    if writer.lower() in (
                        g.tag.lower() for g in plex_media_item.writers
                    ):
                        logger.debug(
                            f"{media_data['title']} [{plex_media_item}] has excluded writer {writer}, skipping"
                        )
                        return False

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
        # Check if any guid cmatches
        if guid in plex_media_item.guid:
            return history

        if history["title"] == plex_media_item.title:
            if (
                history["year"]
                and plex_media_item.year
                and plex_media_item.year != history["year"]
            ):
                if (abs(plex_media_item.year - history["year"])) <= 1:
                    return history

    return None


def _get_config_value(config, key, default=None):
    return config[key] if key in config else default


def sort_media(media_list, sort_config):
    sort_field = sort_config.get("field", "title")
    sort_order = sort_config.get("order", "asc")

    logger.debug(f"Sorting media by {sort_field} {sort_order}")

    def sort_key(media_item):
        if sort_field == "title":
            return media_item.get("sortTitle")
        elif sort_field == "size":
            return media_item.get("sizeOnDisk") or media_item.get("statistics", {}).get(
                "sizeOnDisk"
            )
        elif sort_field == "release_year":
            return media_item.get("year")
        elif sort_field == "runtime":
            return media_item.get("runtime")
        elif sort_field == "added_date":
            return media_item.get("added")
        elif sort_field == "rating":
            ratings = media_item.get("ratings", {})
            return (
                ratings.get("imdb", {}).get("value")
                or ratings.get("tmdb", {}).get("value")
                or ratings.get("value")
            )
        elif sort_field == "seasons":
            return media_item.get("statistics", {}).get("seasonCount") or 1
        elif sort_field == "episodes":
            return media_item.get("statistics", {}).get("totalEpisodeCount") or 1
        else:
            return media_item.get(
                "sortTitle"
            )  # Default to sorting by title if the field is not recognized

    sorted_media = sorted(media_list, key=sort_key, reverse=(sort_order == "desc"))
    return sorted_media


def main():
    """
    Deleterr application entry point. Parses arguments, configs and
    initializes the application.
    """
    locale.setlocale(locale.LC_ALL, "")

    log_level = os.environ.get("LOG_LEVEL", "info").upper()
    logger.initLogger(
        console=True, log_dir="/config/logs", verbose=log_level == "DEBUG"
    )
    
    config = load_config("/config/settings.yaml")
    config.validate()

    Deleterr(config)


if __name__ == "__main__":
    main()
