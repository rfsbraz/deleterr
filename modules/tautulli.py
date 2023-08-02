# enconding: utf-8

from tautulli import RawAPI
import logging
import datetime
import json
import logger


class Tautulli:
    def __init__(self, config):
        self.config = config
        self.api = RawAPI(
            config.get("tautulli", "url"), config.get("tautulli", "api_key")
        )
   