# encoding: utf-8

import logging
import locale
import time
import os

from datetime import datetime, timedelta
from config import Config
from pyarr.exceptions import (
    PyarrMissingArgument,
    PyarrRecordNotFound,
    PyarrResourceNotFound,
)
from pyarr.sonarr import SonarrAPI
from pyarr.radarr import RadarrAPI
from modules.tautulli import Tautulli
import logger
from plexapi.server import PlexServer
from plexapi.exceptions import NotFound
from modules.trakt import Trakt
from utils import print_readable_freed_space

logging.basicConfig()

DEFAULT_MAX_ACTIONS_PER_RUN = 10
DEFAULT_SONARR_SERIES_TYPE = "standard"

class Deleterr:
    def __init__(self, config):
        self.config = config

        # Setup connections
        self.tautulli = Tautulli(config)
        self.plex = PlexServer(config.get("plex", "url"), config.get("plex", "token"), timeout=120)
        self.sonarr = {connection['name']: SonarrAPI(connection["url"],connection["api_key"]) for connection in config.config.get("sonarr", [])}
        self.radarr = {connection['name']: RadarrAPI(connection["url"],connection["api_key"]) for connection in config.config.get("radarr", [])}
        self.trakt = Trakt(config)
        self.watched_collections = set()

        self.process_sonarr()
        self.process_radarr()

    def process_sonarr(self):
        for name, sonarr in self.sonarr.items():
            logger.info("Processing sonarr instance: '%s'", name)
            unfiltered_all_show_data = sonarr.get_series()
        
            saved_space = 0
            for library in self.config.config.get("libraries", []):
                if library.get("sonarr") == name:
                    all_show_data = [show for show in unfiltered_all_show_data if show['seriesType'] == library.get("series_type", DEFAULT_SONARR_SERIES_TYPE)]
                    logger.info("Instance has %s items to process", len(all_show_data))

                    max_actions_per_run = _get_config_value(library, "max_actions_per_run", DEFAULT_MAX_ACTIONS_PER_RUN)

                    logger.info("Processing library '%s'", library.get("name"))

                    trakt_items = self.trakt.get_all_shows_for_url(library.get("exclude", {}).get("trakt", {}))
                    logger.info("Got %s trakt items to exclude", len(trakt_items))

                    plex_library = self.plex.library.section(library.get("name"))
                    logger.info("Got %s items in plex library", plex_library.totalSize)

                    show_activity = self.tautulli.get_activity(library, plex_library.key)
                    logger.info("Got %s items in tautulli activity", len(show_activity))

                    actions_performed = 0
                    for sonarr_show in self.process_library_rules(library, plex_library, all_show_data, show_activity, trakt_items):
                        if max_actions_per_run and actions_performed >= max_actions_per_run:
                            logger.info(f"Reached max actions per run ({max_actions_per_run}), stopping")
                            break
                        if not self.config.get("dry_run"):
                            logger.info("Deleting show '%s' from sonarr instance  '%s'", sonarr_show['title'], name)
                            if self.config.get("interactive"):
                                logger.info("Would you like to delete show '%s' from sonarr instance '%s'? (y/n)", sonarr_show['title'], name)
                                if input().lower() == 'y':
                                    sonarr.del_series(sonarr_show['id'], delete_files=True)
                            else:
                                sonarr.del_series(sonarr_show['id'], delete_files=True)
                        else:
                            logger.info("[DRY-RUN] Would have deleted show '%s' from sonarr instance '%s'", sonarr_show['title'], name)
                        
                        saved_space += sonarr_show.get('statistics', {}).get('sizeOnDisk', 0)
                        actions_performed += 1

                        if self.config.config.get('action_delay'):
                            # sleep in seconds
                            time.sleep(self.config.config.get('action_delay'))
                    
                    logger.info("Freed %s of space by deleting %s shows", print_readable_freed_space(saved_space), actions_performed)

    def process_radarr(self):
        for name, radarr in self.radarr.items():
            logger.info("Processing radarr instance: '%s'", name)
            all_movie_data = radarr.get_movie()
            
            logger.info("[%s] Got %s movies to process", name, len(all_movie_data))

            saved_space = 0
            for library in self.config.config.get("libraries", []):
                if library.get("radarr") == name:
                    max_actions_per_run = _get_config_value(library, "max_actions_per_run", DEFAULT_MAX_ACTIONS_PER_RUN)

                    logger.info("Processing library '%s'", library.get("name"))

                    trakt_movies = self.trakt.get_all_movies_for_url(library.get("exclude", {}).get("trakt", {}))
                    logger.info("Got %s trakt movies to exclude", len(trakt_movies))

                    movies_library = self.plex.library.section(library.get("name"))
                    logger.info("Got %s movies in plex library", movies_library.totalSize)

                    movie_activity = self.tautulli.get_activity(library, movies_library.key)
                    logger.info("Got %s movies in tautulli activity", len(movie_activity))
                    
                    actions_performed = 0
                    for radarr_movie in self.process_library_rules(library, movies_library, all_movie_data, movie_activity, trakt_movies):
                        if max_actions_per_run and actions_performed >= max_actions_per_run:
                            logger.info(f"Reached max actions per run ({max_actions_per_run}), stopping")
                            break
                        if not self.config.get("dry_run"):
                            logger.info("Deleting movie '%s' from radarr instance  '%s'", radarr_movie['title'], name)
                            if self.config.get("interactive"):
                                logger.info("Would you like to delete movie '%s' from radarr instance '%s'? (y/n)", radarr_movie['title'], name)
                                if input().lower() == 'y':
                                    radarr.del_movie(radarr_movie['id'], delete_files=True)
                            else:
                                radarr.del_movie(radarr_movie['id'], delete_files=True)
                        else:
                            logger.info("[DRY-RUN] Would have deleted movie '%s' from radarr instance '%s'", radarr_movie['title'], name)
                        
                        saved_space += radarr_movie.get('sizeOnDisk', 0)
                        actions_performed += 1

                        if self.config.config.get('action_delay'):
                            # sleep in seconds
                            time.sleep(self.config.config.get('action_delay'))

                    logger.info("Freed %s of space by deleting %s movies", print_readable_freed_space(saved_space), actions_performed)

            if not self.config.get("dry_run"):
                if self.config.get("interactive"):
                    logger.info("Would you like to refresh plex library '%s'? (y/n)", movies_library.title)
                    if input().lower() == 'y':
                        movies_library.refresh()
                    logger.info("Would you like to refresh tautulli library '%s'? (y/n)", movies_library.title)
                    if input().lower() == 'y':
                        self.tautulli.refresh_library(movies_library.key)
                else:
                    if self.config.get("plex_library_scan_after_actions"):
                        movies_library.refresh()
                    if self.config.get("tautulli_library_scan_after_actions"):
                        self.tautulli.refresh_library(movies_library.key)
            else:
                logger.info("[DRY-RUN] Would have updated plex library")
                logger.info("[DRY-RUN] Would have updated tautulli library")
                

    def get_library_config(self, config, show):
        return next((library for library in config.config.get("libraries", []) if library.get("name") == show), None)
    
    def get_plex_item(self, plex_library, guid=None, title=None, year=None, alternate_titles=[], imdbId=None, tvdbId=None, teste=None):
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
                if t.lower() == plex_media_item.title.lower() or f"{t.lower()} ({year})" == plex_media_item.title.lower():
                    if year and plex_media_item.year and plex_media_item.year != year:
                        if (abs(plex_media_item.year - year)) <= 1:
                            return plex_media_item
                    else:
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
                    
    def process_library_rules(self, library_config, plex_library, all_data, activity_data, trakt_movies):
        # get the time thresholds from the config
        last_watched_threshold = library_config.get('last_watched_threshold', None)
        added_at_threshold = library_config.get('added_at_threshold', None)
        apply_last_watch_threshold_to_collections = library_config.get('apply_last_watch_threshold_to_collections', False)
        
        plex_guid_item_pair = [([plex_media_item.guid] + [g.id for g in plex_media_item.guids], plex_media_item) for plex_media_item in plex_library.all()]
        if apply_last_watch_threshold_to_collections:
            logger.debug(f"Gathering collection watched status")
            for guid, watched_data in activity_data.items():
                plex_media_item = self.get_plex_item(plex_guid_item_pair, guid=guid)
                if plex_media_item is None:
                    continue
                last_watched = (datetime.now() - watched_data['last_watched']).days
                if plex_media_item.collections and last_watched_threshold and last_watched < last_watched_threshold:
                    logger.debug(f"{watched_data['title']} watched {last_watched} days ago, adding collection {plex_media_item.collections} to watched collections")
                    self.watched_collections = self.watched_collections | set([c.tag for c in plex_media_item.collections])
        
        unmatched = 0
        for media_data in all_data:
            plex_media_item = self.get_plex_item(plex_guid_item_pair, title=media_data['title'], year=media_data['year'], alternate_titles=[t['title'] for t in media_data['alternateTitles']], imdbId=media_data.get('imdbId'), tvdbId=media_data.get('tvdbId'), teste=media_data)
            if plex_media_item is None:
                if media_data.get('statistics', {}).get('episodeFileCount', 0) == 0:
                    logger.debug(f"{media_data['title']} ({media_data['year']}) not found in Plex, but has no episodes, skipping")
                    continue
                else:
                    logger.warning(f"UNMATCHED: {media_data['title']} ({media_data['year']}) not found in Plex.")
                    unmatched += 1
                    continue
            if not self.is_movie_actionable(library_config, activity_data, media_data, trakt_movies, plex_media_item, last_watched_threshold, added_at_threshold, apply_last_watch_threshold_to_collections):
                continue
            
            yield media_data
            
        logger.info(f"Found {len(all_data)} items, {unmatched} unmatched")

    def is_movie_actionable(self, library, activity_data, media_data, trakt_movies, plex_media_item, last_watched_threshold, added_at_threshold, apply_last_watch_threshold_to_collections):          
        watched_data = find_watched_data(plex_media_item, activity_data)
        if watched_data:
            last_watched = (datetime.now() - watched_data['last_watched']).days
            if last_watched_threshold and last_watched < last_watched_threshold:
                logger.debug(f"{media_data['title']} watched {last_watched} days ago, skipping")
                return False
            
        if apply_last_watch_threshold_to_collections:
            already_watched = self.watched_collections.intersection(set([c.tag for c in plex_media_item.collections]))
            if already_watched:
                logger.debug(f"{media_data['title']} has watched collections ({already_watched}), skipping")
                return False
        
        # Check if the movie tmdb id is in the trakt watched list
        if media_data.get('tvdbId', media_data.get('tmdbId')) in trakt_movies:
            logger.debug(f"{media_data['title']} found in trakt watched list {trakt_movies[media_data.get('tvdbId', media_data.get('tmdbId'))]['list']}, skipping")
            return False

        # Days since added
        date_added = (datetime.now() - plex_media_item.addedAt).days
        if added_at_threshold and date_added < added_at_threshold:
            logger.debug(f"{media_data['title']} added {date_added} days ago, skipping")
            return False

        # Exclusions
        exclude = library.get('exclude', {})
        if exclude:
            for title in exclude.get('titles', []):
                if title.lower() == plex_media_item.title.lower():
                    logger.debug(f"{media_data['title']} has excluded title {title}, skipping")
                    return False
                
            for genre in exclude.get('genres', []):
                if genre.lower() in (g.tag.lower() for g in plex_media_item.genres):
                    logger.debug(f"{media_data['title']} has excluded genre {genre}, skipping")
                    return False

            for collection in exclude.get('collections', []):
                if collection.lower() in (g.tag.lower() for g in plex_media_item.collections):
                    logger.debug(f"{media_data['title']} has excluded collection {collection}, skipping")
                    return False
                
            if exclude.get('release_years', 0):
                if plex_media_item.year >= datetime.now().year - exclude.get('release_years'):
                    logger.debug(f"{media_data['title']} ({plex_media_item.year}) was released within the threshold years ({datetime.now().year} - {exclude.get('release_years', 0)} = {datetime.now().year - exclude.get('release_years', 0)}), skipping")
                    return False

            for producer in exclude.get('producers', []):
                if producer.lower() in (g.tag.lower() for g in plex_media_item.producers):
                    logger.debug(f"{media_data['title']} has excluded producer {producer}, skipping")
                    return False
            
            for director in exclude.get('directors', []):
                if director.lower() in (g.tag.lower() for g in plex_media_item.directors):
                    logger.debug(f"{media_data['title']} has excluded director {director}, skipping")
                    return False

            for writer in exclude.get('writers', []):
                if writer.lower() in (g.tag.lower() for g in plex_media_item.writers):
                    logger.debug(f"{media_data['title']} has excluded writer {writer}, skipping")
                    return False

            for actor in exclude.get('actors', []):
                if actor.lower() in (g.tag.lower() for g in plex_media_item.roles):
                    logger.debug(f"{media_data['title']} has excluded actor {actor}, skipping")
                    return False

            if plex_media_item.studio and plex_media_item.studio.lower() in exclude.get('studios', []):
                logger.debug(f"{media_data['title']} has excluded studio {plex_media_item.studio}, skipping")
                return False
        
        return True

def find_watched_data(plex_media_item, activity_data):
    resp = activity_data.get(plex_media_item.guid)

    if resp:
        return resp
    
    for guid, history in activity_data.items():
        # Check if any guid cmatches
        if guid in plex_media_item.guid:
            return history

        if history['title'] == plex_media_item.title:
            if history['year'] and plex_media_item.year and plex_media_item.year != history['year']:
                if (abs(plex_media_item.year - history['year'])) <= 1:
                    return history
                
    return None

def _get_config_value(config, key, default=None):
        if key in config:
            return config[key]
        else:
            return default
        
def main():
    """
    Deleterr application entry point. Parses arguments, configs and
    initializes the application.
    """
    locale.setlocale(locale.LC_ALL, "")

    log_level = os.environ.get('LOG_LEVEL', 'info').upper()
    logger.initLogger(console=True, log_dir="/config/logs", verbose=log_level == "DEBUG")
    
    config = Config('/config/settings.yaml')
    deleterr = Deleterr(config)

if __name__ == "__main__":
    main()

