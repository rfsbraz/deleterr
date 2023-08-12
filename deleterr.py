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
from modules.trakt import Trakt

logging.basicConfig()

class Deleterr:
    def __init__(self, config):
        self.config = config

        # Setup connections
        self.tautulli = Tautulli(config)
        self.plex = PlexServer(config.get("plex", "url"), config.get("plex", "token"), timeout=120)
        self.sonarr = {connection['name']: SonarrAPI(connection["url"],connection["api_key"]) for connection in config.config.get("sonarr", [])}
        self.radarr = {connection['name']: RadarrAPI(connection["url"],connection["api_key"]) for connection in config.config.get("radarr", [])}
        self.trakt = Trakt(config)
        self.plex_movie_map = self.plex_show_map = {}
        self.watched_collections = set()

        self.process_radarr()

    def process_radarr(self):
        for name, radarr in self.radarr.items():
            logger.info("Processing radarr instance: '%s'", name)
            all_movie_data = radarr.get_movie()
            
            logger.debug("[%s] Got %s movies to process", name, len(all_movie_data))

            for library in self.config.config.get("libraries", []):
                trakt_movies = self.trakt.get_all_movies_for_url(library.get("exclude", {}).get("trakt_lists", []))

                movies_library = self.plex.library.section("Movies")
                movie_activity = self.tautulli.get_last_movie_activity(library, movies_library.key)

                

                if library.get("radarr") == name:
                    logger.info("Processing library '%s'", library.get("name"))
                    movies_needing_action = self.apply_library_rules(library, movies_library, all_movie_data, movie_activity, trakt_movies)
                    for radarr_movie in movies_needing_action:
                        logger.info("Deleting movie '%s' from radarr instance  '%s'", radarr_movie['title'], name)
                        if not self.config.get("dry_run"):
                            if self.config.get("interactive"):
                                logger.info("Would you like to delete movie '%s' from radarr instance '%s'? (y/n)", radarr_movie['title'], name)
                                if input().lower() == 'y':
                                    radarr.del_movie(radarr_movie['id'], delete_files=True)
                            else:
                                radarr.del_movie(radarr_movie['id'], delete_files=True)
                        else:
                            logger.info("[DRY-RUN] Would have deleted  movie '%s' from radarr instance  '%s'", radarr_movie['title'], name)
            
            if not self.config.get("dry_run"):
                if self.config.get("interactive"):
                    logger.info("Would you like to refresh plex library '%s'? (y/n)", movies_library.title)
                    if input().lower() == 'y':
                        movies_library.refresh()
                    logger.info("Would you like to refresh tautulli library '%s'? (y/n)", movies_library.title)
                    if input().lower() == 'y':
                        self.tautulli.refresh_library(movies_library.key)
                else:
                    movies_library.refresh()
                    self.tautulli.refresh_library(movies_library.key)
            else:
                logger.info("[DRY-RUN] Would have updated plex library")
                logger.info("[DRY-RUN] Would have updated tautulli library")
                

    def get_library_config(self, config, show):
        return next((library for library in config.config.get("libraries", []) if library.get("name") == show), None)
    
    def get_plex_item(self, plex_library, title, year, alternate_titles=[]):
        if f"{title} ({year})" in self.plex_movie_map:
            return self.plex_movie_map[f"{title} ({year})"]
        
        # Plex may pick some different titles sometimes, and since we can't only fetch by title, we need to check all of them
        for title in [title] + alternate_titles:
            try:
                pl_movie = plex_library.get(title, year=year)
                self.plex_movie_map[f"{title} ({year})"] = pl_movie
                return pl_movie
            except NotFound:
                continue
                
    def apply_library_rules(self, library_config, plex_library, all_data, activity_data, trakt_movies):
        # get the time thresholds from the config
        last_watched_threshold = library_config.get('last_watched_threshold', None)
        added_at_threshold = library_config.get('added_at_threshold', None)
        apply_last_watch_threshold_to_collections = library_config.get('apply_last_watch_threshold_to_collections', False)
        
        if apply_last_watch_threshold_to_collections:
            logger.debug(f"Gathering collection watched status")
            for watched_data in activity_data:
                plex_movie = self.get_plex_item(plex_library, watched_data['title'], watched_data['year'])
                if plex_movie is None:
                    logger.error(f"Movie {watched_data['title']} ({watched_data['year']}) not found in Plex: {watched_data}")
                    continue
                last_watched = (datetime.now() - watched_data['last_watched']).days
                if last_watched_threshold and last_watched < last_watched_threshold:
                    logger.debug(f"Movie {watched_data['title']} watched {last_watched} days ago, adding collection {plex_movie.collections} to watched collections")
                    self.watched_collections = self.watched_collections | set([c.tag for c in plex_movie.collections])
        # store the shows that need action
        shows_needing_action = []
        
        for movie_data in all_data:
            plex_movie = self.get_plex_item(plex_library, movie_data['title'], movie_data['year'], [t['title'] for t in movie_data['alternateTitles']])
            if plex_movie is None:
                logger.warning(f"Movie {movie_data['title']} ({movie_data['year']}) not found in Plex, probably a mismatch in the release year metadata")
                continue

            if not self.is_movie_actionable(library_config, activity_data, movie_data, trakt_movies, plex_movie, last_watched_threshold, added_at_threshold, apply_last_watch_threshold_to_collections):
                continue
            
            shows_needing_action.append(movie_data)

            if library_config.get('max_actions_per_run') and len(shows_needing_action) >= library_config.get('max_actions_per_run'):
                logger.debug(f"Reached max actions per run ({library_config.get('max_actions_per_run')}), stopping")
                break

        logger.debug(f"Found {len(shows_needing_action)} movies needing action")
        return shows_needing_action

    def is_movie_actionable(self, library, activity_data, movie_data, trakt_movies, plex_movie, last_watched_threshold, added_at_threshold, apply_last_watch_threshold_to_collections):          
        watched_data = find_watched_data(movie_data, activity_data)
        if watched_data:
            last_watched = (datetime.now() - watched_data['last_watched']).days
            if last_watched_threshold and last_watched < last_watched_threshold:
                logger.debug(f"Movie {movie_data['title']} watched {last_watched} days ago, skipping")
                return False
            
        if apply_last_watch_threshold_to_collections:
            already_watched = self.watched_collections.intersection(set([c.tag for c in plex_movie.collections]))
            if already_watched:
                logger.debug(f"Movie {movie_data['title']} has watched collections ({already_watched}), skipping")
                return False
        
        # Check if the movie tmdb id is in the trakt watched list
        if movie_data['tmdbId'] in trakt_movies:
            logger.debug(f"Movie {movie_data['title']} found in trakt watched list {trakt_movies[movie_data['tmdbId']]['list']}, skipping")
            return False

        # Days since added
        date_added = (datetime.now() - plex_movie.addedAt).days
        if added_at_threshold and date_added < added_at_threshold:
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
        '-d', '--dry-run', action='store_true', help='Do not perform any actions when running')
    parser.add_argument(
        '-i', '--interactive', action='store_true', help='Run in interactive mode')
    
    args = parser.parse_args()

    logger.initLogger(console=not args.quiet, log_dir="logs", verbose=args.verbose)
    
    config = Config('config/settings.yaml', args)
    logger.info(config.config)
    deleterr = Deleterr(config)

if __name__ == "__main__":
    main()

