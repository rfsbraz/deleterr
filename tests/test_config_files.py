import os
import unittest
from unittest.mock import patch

from app.config import Config
from app.deleterr import load_config
from app.modules import tautulli, trakt, radarr


class TestConfigFiles(unittest.TestCase):
    @patch.object(trakt.Trakt, "test_connection")
    @patch.object(Config, "test_api_connection")
    @patch.object(tautulli.Tautulli, "test_connection")
    @patch("app.modules.radarr.RadarrAPI")
    def validate(
        self,
        filename,
        mock_trakt_test_connection,
        mock_arr_test_connection,
        mock_tautulli_test_connection,
        mock_radarr_api,
    ):
        config = load_config(filename)
        config.validate()


# Get the directory of the current script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Use it to build the path to the config directory
config_dir = os.path.join(script_dir, "./configs/")

teste = os.listdir(config_dir)

for filename in sorted(os.listdir(config_dir)):
    if filename.endswith(".yaml"):
        full_filename = os.path.join(config_dir, filename)

        def ch(filename):
            return lambda self: self.validate(filename)

        setattr(TestConfigFiles, "test_%s" % (filename), ch(full_filename))
