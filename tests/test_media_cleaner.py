import unittest
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
from plexapi.server import PlexServer

import app.media_cleaner
from app.config import Config
from app.media_cleaner import (
    DEFAULT_MAX_ACTIONS_PER_RUN,
    MediaCleaner,
    find_watched_data,
    library_meets_disk_space_threshold,
)
from app.modules import tautulli, trakt


@pytest.fixture
def standard_config():
    return MagicMock(
        settings={
            "max_actions_per_run": 10,
            "library": {
                "name": "Test Library",
                "exclude": {},
                "max_age_days": 30,
                "max_size_gb": 500,
                "min_disk_space_gb": 100,
            },
            "sonarr": {"api_key": "test_api_key", "url": "http://localhost:8989"},
            "plex": {
                "url": "http://localhost:32400",
                "api_key": "test_api_key",
            },
            "tautulli": {"url": "http://localhost:8181", "api_key": "test_api_key"},
        }
    )


class TestLibraryMeetsDiskSpaceThreshold(unittest.TestCase):
    def setUp(self):
        self.pyarr = Mock()
        self.library = {
            "disk_size_threshold": [{"path": "/data/media/local", "threshold": "1TB"}],
            "name": "Test Library",
        }

    def test_meets_threshold(self):
        self.pyarr.get_disk_space.return_value = [
            {"path": "/data/media/local", "freeSpace": 500000000000}  # 500GB
        ]
        self.assertTrue(library_meets_disk_space_threshold(self.library, self.pyarr))

    def test_does_not_meet_threshold(self):
        self.pyarr.get_disk_space.return_value = [
            {"path": "/data/media/local", "freeSpace": 2000000000000}  # 2TB
        ]
        self.assertFalse(library_meets_disk_space_threshold(self.library, self.pyarr))

    def test_folder_not_found(self):
        self.pyarr.get_disk_space.return_value = [
            {"path": "/data/media/other", "freeSpace": 500000000000}
        ]
        self.assertFalse(library_meets_disk_space_threshold(self.library, self.pyarr))

    def test_unset_disk_size_threshold(self):
        del self.library["disk_size_threshold"]
        self.assertTrue(library_meets_disk_space_threshold(self.library, self.pyarr))


class TestFindWatchedData(unittest.TestCase):
    def setUp(self):
        self.activity_data = {
            "guid1": {"title": "Title1", "year": 2000},
            "guid2": {"title": "Title2", "year": 2001},
            "guid3": {"title": "Title3", "year": 2002},
        }

    def test_guid_in_activity_data(self):
        plex_media_item = Mock()
        plex_media_item.guid = "guid1"
        plex_media_item.title = "Title1"
        plex_media_item.year = 2000
        self.assertEqual(
            find_watched_data(plex_media_item, self.activity_data),
            self.activity_data["guid1"],
        )

    def test_guid_in_guid(self):
        plex_media_item = Mock()
        plex_media_item.guid = "guid1"
        plex_media_item.title = "Title4"
        plex_media_item.year = 2003
        self.assertEqual(
            find_watched_data(plex_media_item, self.activity_data),
            self.activity_data["guid1"],
        )

    def test_title_match(self):
        plex_media_item = Mock()
        plex_media_item.guid = "guid2"
        plex_media_item.title = "Title2"
        plex_media_item.year = 2001
        self.assertEqual(
            find_watched_data(plex_media_item, self.activity_data),
            self.activity_data["guid2"],
        )

    def test_year_difference_less_than_one(self):
        plex_media_item = Mock()
        plex_media_item.guid = "guid4"
        plex_media_item.title = "Title3"
        plex_media_item.year = 2003
        self.assertEqual(
            find_watched_data(plex_media_item, self.activity_data),
            self.activity_data["guid3"],
        )

    def test_no_match(self):
        plex_media_item = Mock()
        plex_media_item.guid = "guid4"
        plex_media_item.title = "Title4"
        plex_media_item.year = 2004
        self.assertIsNone(find_watched_data(plex_media_item, self.activity_data))


def test_process_library(mocker, standard_config):
    # Arrange
    library = {"name": "Test Library"}
    sonarr_instance = Mock()
    unfiltered_all_show_data = MagicMock()

    mocker.patch.object(trakt.Trakt, "test_connection")
    mocker.patch.object(Config, "test_api_connection")
    mocker.patch.object(tautulli.Tautulli, "test_connection")

    # Mock plex server constructor
    mocker.patch("app.media_cleaner.PlexServer", return_value=MagicMock())

    mock_library_meets_disk_space_threshold = mocker.patch(
        "app.media_cleaner.library_meets_disk_space_threshold", return_value=True
    )
    mock_get_config_value = mocker.patch(
        "app.media_cleaner._get_config_value", return_value=10
    )
    mock_filter_shows = mocker.patch.object(
        MediaCleaner, "filter_shows", return_value=MagicMock()
    )
    mock_get_trakt_items = mocker.patch.object(
        MediaCleaner, "get_trakt_items", return_value=MagicMock()
    )
    mock_get_plex_library = mocker.patch.object(
        MediaCleaner, "get_plex_library", return_value=MagicMock(totalSize=20)
    )
    mock_get_show_activity = mocker.patch.object(
        MediaCleaner, "get_show_activity", return_value=MagicMock()
    )
    mock_process_shows = mocker.patch.object(
        MediaCleaner, "process_shows", return_value=5
    )

    mock_logger = mocker.patch("app.media_cleaner.logger")

    # Act
    media_cleaner = MediaCleaner(standard_config)

    result = media_cleaner.process_library(
        library, sonarr_instance, unfiltered_all_show_data
    )

    # Assert
    mock_library_meets_disk_space_threshold.assert_called_once_with(
        library, sonarr_instance
    )
    mock_get_config_value.assert_called_once_with(
        library, "max_actions_per_run", DEFAULT_MAX_ACTIONS_PER_RUN
    )
    mock_filter_shows.assert_called_once_with(library, unfiltered_all_show_data)
    mock_get_trakt_items.assert_called_once_with("show", library)
    mock_get_plex_library.assert_called_once_with(library)
    mock_get_show_activity.assert_called_once_with(
        library, mock_get_plex_library.return_value
    )
    mock_process_shows.assert_called_once_with(
        library,
        sonarr_instance,
        mock_get_plex_library.return_value,
        mock_filter_shows.return_value,
        mock_get_show_activity.return_value,
        mock_get_trakt_items.return_value,
        mock_get_config_value.return_value,
    )
    assert result == 5


def test_check_exclusions(mocker, standard_config):
    # Arrange
    library = {"name": "Test Library", "exclude": {}}
    media_data = MagicMock()
    plex_media_item = MagicMock()

    mocker.patch.object(trakt.Trakt, "test_connection")
    mocker.patch.object(Config, "test_api_connection")
    mocker.patch.object(tautulli.Tautulli, "test_connection")

    # Mock plex server constructor
    mocker.patch("app.media_cleaner.PlexServer", return_value=MagicMock())

    mock_check_excluded_titles = mocker.patch("app.media_cleaner.check_excluded_titles")
    mock_check_excluded_genres = mocker.patch("app.media_cleaner.check_excluded_genres")
    mock_check_excluded_collections = mocker.patch(
        "app.media_cleaner.check_excluded_collections"
    )
    mock_check_excluded_labels = mocker.patch("app.media_cleaner.check_excluded_labels")
    mock_check_excluded_release_years = mocker.patch(
        "app.media_cleaner.check_excluded_release_years"
    )
    mock_check_excluded_studios = mocker.patch(
        "app.media_cleaner.check_excluded_studios"
    )
    mock_check_excluded_producers = mocker.patch(
        "app.media_cleaner.check_excluded_producers"
    )
    mock_check_excluded_directors = mocker.patch(
        "app.media_cleaner.check_excluded_directors"
    )
    mock_check_excluded_writers = mocker.patch(
        "app.media_cleaner.check_excluded_writers"
    )
    mock_check_excluded_actors = mocker.patch("app.media_cleaner.check_excluded_actors")

    # Act
    media_cleaner = MediaCleaner(standard_config)
    media_cleaner.check_exclusions(library, media_data, plex_media_item)

    # Assert
    mock_check_excluded_titles.assert_called_once_with(
        media_data, plex_media_item, library.get("exclude")
    )
    mock_check_excluded_genres.assert_called_once_with(
        media_data, plex_media_item, library.get("exclude")
    )
    mock_check_excluded_collections.assert_called_once_with(
        media_data, plex_media_item, library.get("exclude")
    )
    mock_check_excluded_labels.assert_called_once_with(
        media_data, plex_media_item, library.get("exclude")
    )
    mock_check_excluded_release_years.assert_called_once_with(
        media_data, plex_media_item, library.get("exclude")
    )
    mock_check_excluded_studios.assert_called_once_with(
        media_data, plex_media_item, library.get("exclude")
    )
    mock_check_excluded_producers.assert_called_once_with(
        media_data, plex_media_item, library.get("exclude")
    )
    mock_check_excluded_directors.assert_called_once_with(
        media_data, plex_media_item, library.get("exclude")
    )
    mock_check_excluded_writers.assert_called_once_with(
        media_data, plex_media_item, library.get("exclude")
    )
    mock_check_excluded_actors.assert_called_once_with(
        media_data, plex_media_item, library.get("exclude")
    )


def test_check_excluded_titles(mocker):
    # Arrange
    media_data = {"title": "Test Title"}
    plex_media_item = MagicMock()
    plex_media_item.title = "Test Title"
    exclude = {"titles": ["Test Title"]}

    mock_logger = mocker.patch("app.media_cleaner.logger")

    # Act
    result = app.media_cleaner.check_excluded_titles(
        media_data, plex_media_item, exclude
    )

    # Assert
    mock_logger.debug.assert_called_once_with(
        f"{media_data['title']} has excluded title {exclude['titles'][0]}, skipping"
    )
    assert result is False


def test_check_excluded_genres(mocker):
    # Arrange
    media_data = {"title": "Test Title"}
    plex_media_item = MagicMock()
    plex_media_item.genres = [MagicMock(tag="Test Genre")]
    exclude = {"genres": ["Test Genre"]}

    mock_logger = mocker.patch("app.media_cleaner.logger")

    # Act
    result = app.media_cleaner.check_excluded_genres(
        media_data, plex_media_item, exclude
    )

    # Assert
    mock_logger.debug.assert_called_once_with(
        f"{media_data['title']} has excluded genre {exclude['genres'][0]}, skipping"
    )
    assert result is False


def test_check_excluded_collections(mocker):
    # Arrange
    media_data = {"title": "Test Title"}
    plex_media_item = MagicMock()
    plex_media_item.collections = [MagicMock(tag="Test collection")]
    exclude = {"collections": ["Test collection"]}

    mock_logger = mocker.patch("app.media_cleaner.logger")

    # Act
    result = app.media_cleaner.check_excluded_collections(
        media_data, plex_media_item, exclude
    )

    # Assert
    mock_logger.debug.assert_called_once_with(
        f"{media_data['title']} has excluded collection {exclude['collections'][0]}, skipping"
    )
    assert result is False


def test_check_excluded_labels(mocker):
    # Arrange
    media_data = {"title": "Test Title"}
    plex_media_item = MagicMock()
    plex_media_item.labels = [MagicMock(tag="Test label")]
    exclude = {"plex_labels": ["Test label"]}

    mock_logger = mocker.patch("app.media_cleaner.logger")

    # Act
    result = app.media_cleaner.check_excluded_labels(
        media_data, plex_media_item, exclude
    )

    # Assert
    mock_logger.debug.assert_called_once_with(
        f"{media_data['title']} has excluded label {exclude['plex_labels'][0]}, skipping"
    )
    assert result is False


def test_check_excluded_release_years(mocker):
    # Arrange
    media_data = {"title": "Test Title"}
    plex_media_item = MagicMock()
    plex_media_item.year = datetime.now().year
    exclude = {"release_years": 1}

    mock_logger = mocker.patch("app.media_cleaner.logger")

    # Act
    result = app.media_cleaner.check_excluded_release_years(
        media_data, plex_media_item, exclude
    )

    # Assert
    mock_logger.debug.assert_called_once_with(
        f"{media_data['title']} ({plex_media_item.year}) was released within the threshold years ({datetime.now().year} - {exclude.get('release_years', 0)} = {datetime.now().year - exclude.get('release_years', 0)}), skipping"
    )
    assert result is False


def test_check_excluded_studios(mocker):
    # Arrange
    media_data = {"title": "Test Title"}
    plex_media_item = MagicMock()
    plex_media_item.studio = "Test Studio"
    exclude = {"studios": ["test studio"]}

    mock_logger = mocker.patch("app.media_cleaner.logger")

    # Act
    result = app.media_cleaner.check_excluded_studios(
        media_data, plex_media_item, exclude
    )

    # Assert
    mock_logger.debug.assert_called_once_with(
        f"{media_data['title']} has excluded studio {plex_media_item.studio}, skipping"
    )
    assert result is False


def test_check_excluded_producers(mocker):
    # Arrange
    media_data = {"title": "Test Title"}
    plex_media_item = MagicMock()
    plex_media_item.producers = [MagicMock(tag="Test Producer")]
    exclude = {"producers": ["Test Producer"]}

    mock_logger = mocker.patch("app.media_cleaner.logger")

    # Act
    result = app.media_cleaner.check_excluded_producers(
        media_data, plex_media_item, exclude
    )

    # Assert
    mock_logger.debug.assert_called_once_with(
        f"{media_data['title']} [{plex_media_item}] has excluded producer {exclude['producers'][0]}, skipping"
    )
    assert result is False


def test_check_excluded_directors(mocker):
    # Arrange
    media_data = {"title": "Test Title"}
    plex_media_item = MagicMock()
    plex_media_item.directors = [MagicMock(tag="Test director")]
    exclude = {"directors": ["Test director"]}

    mock_logger = mocker.patch("app.media_cleaner.logger")

    # Act
    result = app.media_cleaner.check_excluded_directors(
        media_data, plex_media_item, exclude
    )

    # Assert
    mock_logger.debug.assert_called_once_with(
        f"{media_data['title']} [{plex_media_item}] has excluded director {exclude['directors'][0]}, skipping"
    )
    assert result is False


def test_check_excluded_writers(mocker):
    # Arrange
    media_data = {"title": "Test Title"}
    plex_media_item = MagicMock()
    plex_media_item.writers = [MagicMock(tag="Test writer")]
    exclude = {"writers": ["Test writer"]}

    mock_logger = mocker.patch("app.media_cleaner.logger")

    # Act
    result = app.media_cleaner.check_excluded_writers(
        media_data, plex_media_item, exclude
    )

    # Assert
    mock_logger.debug.assert_called_once_with(
        f"{media_data['title']} [{plex_media_item}] has excluded writer {exclude['writers'][0]}, skipping"
    )
    assert result is False


def test_check_excluded_actors(mocker):
    # Arrange
    media_data = {"title": "Test Title"}
    plex_media_item = MagicMock()
    plex_media_item.roles = [MagicMock(tag="Test actor")]
    exclude = {"actors": ["Test actor"]}

    mock_logger = mocker.patch("app.media_cleaner.logger")

    # Act
    result = app.media_cleaner.check_excluded_actors(
        media_data, plex_media_item, exclude
    )

    # Assert
    mock_logger.debug.assert_called_once_with(
        f"{media_data['title']} [{plex_media_item}] has excluded actor {exclude['actors'][0]}, skipping"
    )
    assert result is False
