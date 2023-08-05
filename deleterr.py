import logging
import locale
import argparse
import time

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

logging.basicConfig()

class Deleterr:
    def __init__(self, config):
        self.config = config

        # Setup connections
        self.tautulli = Tautulli(config)
        self.plex = PlexServer(config.get("plex", "url"), config.get("plex", "token"))
        self.sonarr = {connection['name']: SonarrAPI(connection["url"],connection["api_key"]) for connection in config.config.get("sonarr", [])}
        self.radarr = {connection['name']: RadarrAPI(connection["url"],connection["api_key"]) for connection in config.config.get("radarr", [])}

        self.process_radarr()

    def process_radarr(self):
        movie_activity = self.tautulli.get_last_movie_activity()

        for name, radarr in self.radarr.items():
            logger.info("Processing radarr instance: '%s'", name)
            all_movie_data = radarr.get_movie()
            
            logger.debug("[%s] Got %s movies to process", name, len(all_movie_data))

            for library in self.config.config.get("libraries", []):
                movies_library = self.plex.library.section("Movies")

                if library.get("radarr") == name:
                    logger.info("Processing library '%s'", library.get("name"))
                    movies_needing_action = self.apply_library_rules(library, movies_library, all_movie_data, movie_activity)
                    for radarr_movie in movies_needing_action:
                        logger.info("Deleting movie '%s' from radarr instance  '%s'", radarr_movie['title'], name)
                        if not self.config.get("dry_run"):
                            radarr.del_movie(radarr_movie['id'])
                        else:
                            logger.info("[DRY-RUN] Would have deleted  movie '%s' from radarr instance  '%s'", radarr_movie['title'], name)
            
            if not self.config.get("dry_run"):
                movies_library.update()
                self.tautulli.refresh_library(movies_library.key)
            else:
                logger.info("[DRY-RUN] Would have updated plex library")
                logger.info("[DRY-RUN] Would have updated tautulli library")
                

    def get_library_config(self, config, show):
        return next((library for library in config.config.get("libraries", []) if library.get("name") == show), None)
    

    def apply_library_rules(self, library_config, plex_library, all_data, activity_data):
        # get the time thresholds from the config
        last_watched_days = library_config.get('last_watched_days', None)
        last_added_days = library_config.get('last_added_days', None)
        
        # store the shows that need action
        shows_needing_action = []

        for movie_data in all_data:

            for title in [movie_data['title']] + [t['title'] for t in movie_data['alternateTitles']]:
                try:
                    plex_movie = plex_library.get(title, year=movie_data['year'])
                except NotFound:
                    continue
            if plex_movie is None:
                logger.error(f"Movie {movie_data['title']} ({movie_data['year']}) not found in Plex: {movie_data}")
                exit(1)

            if not is_movie_actionable(library_config, activity_data, movie_data, plex_movie, last_watched_days, last_added_days):
                continue
            
            shows_needing_action.append(movie_data)

            if library_config.get('max_actions_per_run') and len(shows_needing_action) >= library_config.get('max_actions_per_run'):
                logger.debug(f"Reached max actions per run ({library_config.get('max_actions_per_run')}), stopping")
                break

        logger.debug(f"Found {len(shows_needing_action)} movies needing action")
        return shows_needing_action

def is_movie_actionable(library, activity_data, movie_data, plex_movie, last_watched_days, last_added_days):
    # get the current time
    now = datetime.now()

    # Days since last watched
    date_added = (now - plex_movie.addedAt).days
    
    if last_added_days and date_added < last_added_days:
        logger.debug(f"Movie {movie_data['title']} added {date_added} days ago, skipping")
        return False

    # Exclusions
    exclude = library.get('exclude', {})
    if exclude:
        for genre in exclude.get('genres', []):
            if genre.lower() in (g.tag.lower() for g in plex_movie.genres):
                logger.debug(f"Movie {movie_data['title']} has excluded genre {genre}, skipping")
                return False

        for collection in exclude.get('collections', []):
            if collection.lower() in (g.tag.lower() for g in plex_movie.collections):
                logger.debug(f"Movie {movie_data['title']} has excluded collection {collection}, skipping")
                return False
        
        if exclude.get('release_years', 0):
            if plex_movie.year >= datetime.now().year - exclude.get('release_years'):
                logger.debug(f"Movie {movie_data['title']} ({plex_movie.year}) was released within the threshold years ({datetime.now().year} - {exclude.get('release_years', 0)} = {datetime.now().year - exclude.get('release_years', 0)}), skipping")
                return False

        for producer in exclude.get('producers', []):
            if producer.lower() in (g.tag.lower() for g in plex_movie.producers):
                logger.debug(f"Movie {movie_data['title']} has excluded producer {producer}, skipping")
                return False
        
        for director in exclude.get('directors', []):
            if director.lower() in (g.tag.lower() for g in plex_movie.directors):
                logger.debug(f"Movie {movie_data['title']} has excluded director {director}, skipping")
                return False

        for writer in exclude.get('writers', []):
            if writer.lower() in (g.tag.lower() for g in plex_movie.writers):
                logger.debug(f"Movie {movie_data['title']} has excluded writer {writer}, skipping")
                return False

        for actor in exclude.get('actors', []):
            if actor.lower() in (g.tag.lower() for g in plex_movie.roles):
                logger.debug(f"Movie {movie_data['title']} has excluded actor {actor}, skipping")
                return False

        if plex_movie.studio and plex_movie.studio.lower() in exclude.get('studios', []):
            logger.debug(f"Movie {movie_data['title']} has excluded studio {plex_movie.studio}, skipping")
            return False


    watched_data = find_watched_data(movie_data, activity_data)
    if watched_data:
        last_watched = (now - watched_data['last_watched']).days
        if last_watched_days and last_watched < last_watched_days:
            logger.debug(f"Movie {movie_data['title']} watched {last_watched} days ago, skipping")
            return False
    
    return True

def find_watched_data(movie_data, activity_data):
    for watched_data in activity_data:
        if watched_data['guid'] == movie_data['tmdbId']:
            return watched_data
        if watched_data['title'] == movie_data['title'] and watched_data['year'] == movie_data['year']:
            return watched_data
    return None

def main():
    """
    Deleterr application entry point. Parses arguments, configs and
    initializes the application.
    """
    locale.setlocale(locale.LC_ALL, "")

    # Set up and gather command line arguments
    parser = argparse.ArgumentParser(
        description='A Python based monitoring and tracking tool for Plex Media Server.')

    parser.add_argument(
        '-v', '--verbose', action='store_true', help='Increase console logging verbosity')
    parser.add_argument(
        '-q', '--quiet', action='store_true', help='Turn off console logging')
    parser.add_argument(
        '-d', '--dry-run', action='store_true', default=True, help='Do not perform any actions when running')
    
    args = parser.parse_args()

    logger.initLogger(console=not args.quiet, log_dir="logs", verbose=args.verbose)
    
    config = Config('config/settings.yaml', args)
    logger.info(config.config)
    deleterr = Deleterr(config)

if __name__ == "__main__":
    main()

