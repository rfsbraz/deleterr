import unittest
from unittest.mock import MagicMock, patch

import pytest

from app.deleterr import Deleterr, main


@pytest.fixture
def deleterr():
    with patch("app.deleterr.MediaCleaner", return_value=MagicMock()):
        yield Deleterr(MagicMock())


class TestConfigPath(unittest.TestCase):
    @patch("app.deleterr.load_config")
    @patch("app.deleterr.Deleterr")
    @patch("app.deleterr.logger")
    def test_default_config_path(self, mock_logger, mock_deleterr, mock_load_config):
        # Arrange
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config

        # Act
        main()

        # Assert
        mock_load_config.assert_called_once_with("/config/settings.yaml")
        mock_config.validate.assert_called_once()
        mock_deleterr.assert_called_once_with(mock_config)


@patch("app.deleterr.SonarrAPI")
@patch("app.deleterr.RadarrAPI")
def test_process_radarr(radarr_mock, sonarr_mock, deleterr):
    # Arrange
    deleterr.radarr = {
        "Radarr1": MagicMock(
            get_movie=MagicMock(return_value=[{"title": "Test Movie"}])
        ),
    }
    deleterr.config.settings = {
        "libraries": [{"radarr": "Radarr1"}],
    }
    deleterr.media_cleaner.process_library_movies = MagicMock(return_value=1000)

    # Act
    deleterr.process_radarr()

    # Assert
    deleterr.media_cleaner.process_library_movies.assert_called_once_with(
        {"radarr": "Radarr1"},
        deleterr.radarr["Radarr1"],
        [{"title": "Test Movie"}],
    )


@patch("app.deleterr.SonarrAPI")
@patch("app.deleterr.RadarrAPI")
def test_process_sonarr(radarr_mock, sonarr_mock, deleterr):
    # Arrange
    deleterr.sonarr = {
        "Sonarr1": MagicMock(
            get_series=MagicMock(return_value=[{"title": "Test Movie"}])
        ),
    }
    deleterr.config.settings = {
        "libraries": [{"sonarr": "Sonarr1"}],
    }
    deleterr.media_cleaner.process_library = MagicMock(return_value=1000)

    # Act
    deleterr.process_sonarr()

    # Assert
    deleterr.media_cleaner.process_library.assert_called_once_with(
        {"sonarr": "Sonarr1"},
        deleterr.sonarr["Sonarr1"],
        [{"title": "Test Movie"}],
    )
