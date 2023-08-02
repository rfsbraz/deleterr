import logging
import locale
import argparse

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

logging.basicConfig()

class Deleterr:
    def __init__(self, config):
        self.config = config
        self.tautulli = Tautulli(config)
        self.tvshows = self.get_library_config(config, "TV Shows")

    def get_library_config(self, config, show):
        return next((library for library in config.config.get("libraries", []) if library.get("name") == show), None)
    

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
    
    config = Config('config/settings.yaml')
    logger.info(config.config)
    deleterr = Deleterr(config)

if __name__ == "__main__":
    main()

