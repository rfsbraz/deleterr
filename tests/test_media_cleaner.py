import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
from pyarr.exceptions import PyarrResourceNotFound, PyarrServerError

import app.media_cleaner
from app.config import Config
from app.media_cleaner import (
    DEFAULT_MAX_ACTIONS_PER_RUN,
    MediaCleaner,
    find_watched_data,
    library_meets_disk_space_threshold,
)


@pytest.fixture
def standard_config():
    return MagicMock(
        settings={
            "max_actions_per_run": 10,
            "sonarr": {"api_key": "test_api_key", "url": "http://localhost:8989"},
            "plex": {
                "url": "http://localhost:32400",
                "api_key": "test_api_key",
            },
            "tautulli": {"url": "http://localhost:8181", "api_key": "test_api_key"},
        }
    )


@pytest.fixture
def media_cleaner(standard_config):
    return MediaCleaner(standard_config)


@pytest.fixture(autouse=True)
def mock_plex_server():
    with patch("app.media_cleaner.PlexServer", return_value=MagicMock()) as mock_plex:
        yield mock_plex


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


@patch("app.media_cleaner.library_meets_disk_space_threshold", return_value=True)
@patch("app.media_cleaner._get_config_value", return_value=10)
@patch.object(MediaCleaner, "filter_shows")
@patch.object(MediaCleaner, "get_trakt_items")
@patch.object(MediaCleaner, "get_plex_library")
@patch.object(MediaCleaner, "get_show_activity")
@patch.object(MediaCleaner, "process_shows", return_value=5)
def test_process_library(
    mock_process_shows,
    mock_get_show_activity,
    mock_get_plex_library,
    mock_get_trakt_items,
    mock_filter_shows,
    mock_get_config_value,
    mock_library_meets_disk_space_threshold,
    standard_config,
):
    # Arrange
    library = {"name": "Test Library"}
    sonarr_instance = Mock()
    unfiltered_all_show_data = MagicMock()

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


@patch("app.media_cleaner.library_meets_disk_space_threshold", return_value=False)
@patch.object(MediaCleaner, "process_shows")
def test_process_library_no_threshold(
    mock_process_shows,
    mock_library_meets_disk_space_threshold,
    standard_config,
):
    # Arrange
    library = {"name": "Test Library"}
    sonarr_instance = Mock()
    unfiltered_all_show_data = MagicMock()

    # Act
    media_cleaner = MediaCleaner(standard_config)

    result = media_cleaner.process_library(
        library, sonarr_instance, unfiltered_all_show_data
    )

    # Assert
    mock_library_meets_disk_space_threshold.assert_called_once_with(
        library, sonarr_instance
    )
    mock_process_shows.assert_not_called()
    assert result == 0


@patch.object(MediaCleaner, "process_library_rules", return_value=[MagicMock()])
@patch.object(MediaCleaner, "process_show", return_value=10)
def test_process_shows(mock_process_show, mock_process_library_rules, standard_config):
    # Arrange
    library = {}
    sonarr_instance = MagicMock()
    plex_library = MagicMock()
    all_show_data = MagicMock()
    show_activity = MagicMock()
    trakt_items = MagicMock()
    max_actions_per_run = 1

    media_cleaner = MediaCleaner(standard_config)

    # Act
    result = media_cleaner.process_shows(
        library,
        sonarr_instance,
        plex_library,
        all_show_data,
        show_activity,
        trakt_items,
        max_actions_per_run,
    )

    # Assert
    mock_process_library_rules.assert_called_once_with(
        library, plex_library, all_show_data, show_activity, trakt_items
    )
    mock_process_show.assert_called_once()
    assert result == 10


@patch.object(MediaCleaner, "process_library_rules", return_value=[MagicMock()])
@patch.object(MediaCleaner, "process_show", return_value=10)
@patch("time.sleep")
def test_process_shows_with_delay(
    mock_sleep, mock_process_show, mock_process_library_rules, standard_config
):
    # Arrange
    library = {}
    sonarr_instance = MagicMock()
    plex_library = MagicMock()
    all_show_data = MagicMock()
    show_activity = MagicMock()
    trakt_items = MagicMock()
    max_actions_per_run = 1

    media_cleaner = MediaCleaner(standard_config)
    media_cleaner.config.settings = {"action_delay": 10}

    # Act
    result = media_cleaner.process_shows(
        library,
        sonarr_instance,
        plex_library,
        all_show_data,
        show_activity,
        trakt_items,
        max_actions_per_run,
    )

    # Assert
    mock_process_library_rules.assert_called_once_with(
        library, plex_library, all_show_data, show_activity, trakt_items
    )
    mock_process_show.assert_called_once()
    mock_sleep.assert_called_once_with(10)
    assert result == 10


@patch.object(
    MediaCleaner,
    "process_library_rules",
    return_value=[MagicMock() for _ in range(100)],
)
@patch.object(MediaCleaner, "process_show", return_value=5)
def test_process_shows_max_actions(
    mock_process_show, mock_process_library_rules, standard_config
):
    # Arrange
    library = {}
    sonarr_instance = MagicMock()
    plex_library = MagicMock()
    all_show_data = MagicMock()
    show_activity = MagicMock()
    trakt_items = MagicMock()
    max_actions_per_run = 10

    media_cleaner = MediaCleaner(standard_config)

    # Act
    result = media_cleaner.process_shows(
        library,
        sonarr_instance,
        plex_library,
        all_show_data,
        show_activity,
        trakt_items,
        max_actions_per_run,
    )

    # Assert
    mock_process_library_rules.assert_called_once_with(
        library, plex_library, all_show_data, show_activity, trakt_items
    )
    assert mock_process_show.call_count == 10
    assert result == 10 * 5


@patch.object(MediaCleaner, "delete_show_if_allowed")
def test_process_show_dry_run(mock_delete_show_if_allowed, standard_config):
    # Arrange
    library = {}
    sonarr_instance = MagicMock()
    sonarr_show = {
        "title": "Test Show",
        "statistics": {"sizeOnDisk": 100, "episodeFileCount": 10},
    }
    actions_performed = 0
    max_actions_per_run = 1

    media_cleaner = MediaCleaner(standard_config)
    media_cleaner.config.settings = {"dry_run": True}

    # Act
    result = media_cleaner.process_show(
        library,
        sonarr_instance,
        sonarr_show,
        actions_performed,
        max_actions_per_run,
    )

    # Assert
    mock_delete_show_if_allowed.assert_not_called()
    assert result == 100


@patch.object(MediaCleaner, "delete_show_if_allowed")
def test_process_show_not_dry_run(mock_delete_show_if_allowed, standard_config):
    # Arrange
    library = {}
    sonarr_instance = MagicMock()
    sonarr_show = {
        "title": "Test Show",
        "statistics": {"sizeOnDisk": 100, "episodeFileCount": 10},
    }
    actions_performed = 0
    max_actions_per_run = 1

    media_cleaner_instance = MediaCleaner(standard_config)
    media_cleaner_instance.config.settings = {"dry_run": False}

    # Act
    result = media_cleaner_instance.process_show(
        library,
        sonarr_instance,
        sonarr_show,
        actions_performed,
        max_actions_per_run,
    )

    # Assert
    mock_delete_show_if_allowed.assert_called_once()
    assert result == 100


@patch.object(MediaCleaner, "delete_series")
@patch("builtins.input", return_value="y")
def test_delete_show_if_allowed_interactive_yes(
    mock_input, mock_delete_series, standard_config
):
    # Arrange
    library = {"name": "Test Library"}
    sonarr_instance = MagicMock()
    sonarr_show = {"title": "Test Show"}
    actions_performed = 0
    max_actions_per_run = 1
    disk_size = 100
    total_episodes = 10

    media_cleaner = MediaCleaner(standard_config)
    media_cleaner.config.settings = {"interactive": True}

    # Act
    media_cleaner.delete_show_if_allowed(
        library,
        sonarr_instance,
        sonarr_show,
        actions_performed,
        max_actions_per_run,
        disk_size,
        total_episodes,
    )

    # Assert
    mock_delete_series.assert_called_once_with(sonarr_instance, sonarr_show)
    mock_input.assert_called_once_with()


@patch.object(MediaCleaner, "delete_series")
@patch("builtins.input", return_value="n")
def test_delete_show_if_allowed_not_interactive_yes(
    mock_input, mock_delete_series, standard_config
):
    # Arrange
    library = {"name": "Test Library"}
    sonarr_instance = MagicMock()
    sonarr_show = {"title": "Test Show"}
    actions_performed = 0
    max_actions_per_run = 1
    disk_size = 100
    total_episodes = 10

    media_cleaner = MediaCleaner(standard_config)
    media_cleaner.config.settings = {"interactive": False}

    # Act
    media_cleaner.delete_show_if_allowed(
        library,
        sonarr_instance,
        sonarr_show,
        actions_performed,
        max_actions_per_run,
        disk_size,
        total_episodes,
    )

    # Assert
    mock_delete_series.assert_called_once_with(sonarr_instance, sonarr_show)
    mock_input.assert_not_called()


def test_check_exclusions(mocker, standard_config):
    # Arrange
    library = {"name": "Test Library", "exclude": {}}
    media_data = MagicMock()
    plex_media_item = MagicMock()

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


@pytest.mark.parametrize(
    "media_type, library, expected",
    [
        (
            "movies",
            {"exclude": {"trakt": {"titles": ["test_title"]}}},
            {"titles": ["test_title"]},
        ),
        (
            "shows",
            {"exclude": {"trakt": {"titles": ["test_title"]}}},
            {"titles": ["test_title"]},
        ),
        (
            "movies",
            {},
            {},
        ),
        (
            "shows",
            {},
            {},
        ),
    ],
)
@patch("app.media_cleaner.Trakt")
def test_get_trakt_items_with_exclusions(
    mock_trakt,
    standard_config,
    media_type,
    library,
    expected,
):
    # Arrange
    mock_trakt_instance = mock_trakt.return_value
    mock_trakt_instance.get_all_items_for_url.return_value = []

    media_cleaner_instance = MediaCleaner(standard_config)

    # Act
    media_cleaner_instance.get_trakt_items(media_type, library)

    # Assert
    mock_trakt_instance.get_all_items_for_url.assert_called_once_with(
        media_type, expected
    )


@patch("app.media_cleaner.MediaCleaner.get_trakt_items")
@patch("app.media_cleaner.MediaCleaner.get_plex_library")
@patch("app.media_cleaner.MediaCleaner.get_movie_activity")
@patch("app.media_cleaner.MediaCleaner.process_movies", return_value=10)
@patch("app.media_cleaner._get_config_value", return_value=1)
@patch("app.media_cleaner.library_meets_disk_space_threshold", return_value=True)
def test_process_library_movies(
    mock_library_meets_disk_space_threshold,
    mock_get_config_value,
    mock_process_movies,
    mock_get_movie_activity,
    mock_get_plex_library,
    mock_get_trakt_items,
    standard_config,
):
    # Arrange
    library = {"name": "Test Library"}
    radarr_instance = MagicMock()
    all_movie_data = MagicMock()

    media_cleaner_instance = MediaCleaner(standard_config)

    # Act
    result = media_cleaner_instance.process_library_movies(
        library, radarr_instance
    )

    # Assert
    mock_library_meets_disk_space_threshold.assert_called_once_with(
        library, radarr_instance
    )
    mock_get_config_value.assert_called_once_with(
        library, "max_actions_per_run", app.media_cleaner.DEFAULT_MAX_ACTIONS_PER_RUN
    )
    mock_get_trakt_items.assert_called_once_with("movie", library)
    mock_get_plex_library.assert_called_once_with(library)
    mock_get_movie_activity.assert_called_once_with(
        library, mock_get_plex_library.return_value
    )
    mock_process_movies.assert_called_once()
    assert result == 10


@patch("app.media_cleaner.MediaCleaner.get_trakt_items")
@patch("app.media_cleaner.MediaCleaner.get_plex_library")
@patch("app.media_cleaner.MediaCleaner.get_movie_activity")
@patch("app.media_cleaner.MediaCleaner.process_movies", return_value=10)
@patch("app.media_cleaner._get_config_value", return_value=1)
@patch("app.media_cleaner.library_meets_disk_space_threshold", return_value=False)
def test_process_library_movies_no_space(
    mock_library_meets_disk_space_threshold,
    mock_get_config_value,
    mock_process_movies,
    mock_get_movie_activity,
    mock_get_plex_library,
    mock_get_trakt_items,
    standard_config,
):
    # Arrange
    library = {"name": "Test Library"}
    radarr_instance = MagicMock()
    all_movie_data = MagicMock()

    media_cleaner_instance = MediaCleaner(standard_config)

    # Act
    result = media_cleaner_instance.process_library_movies(
        library, radarr_instance
    )

    # Assert
    mock_library_meets_disk_space_threshold.assert_called_once_with(
        library, radarr_instance
    )
    mock_get_config_value.assert_not_called()
    mock_get_trakt_items.assert_not_called()
    mock_get_plex_library.assert_not_called()
    mock_get_movie_activity.assert_not_called()
    mock_process_movies.assert_not_called()
    assert result == 0


@patch("app.media_cleaner.MediaCleaner.process_library_rules")
@patch("app.media_cleaner.MediaCleaner.process_movie")
@patch("time.sleep")
def test_process_movies(
    mock_sleep,
    mock_process_movie,
    mock_process_library_rules,
    standard_config,
):
    # Arrange
    library = {"name": "Test Library"}
    radarr_instance = MagicMock()
    movies_library = MagicMock()
    movie_activity = MagicMock()
    trakt_movies = MagicMock()
    max_actions_per_run = 2

    mock_process_library_rules.return_value = [MagicMock(), MagicMock(), MagicMock()]
    mock_process_movie.return_value = 100

    media_cleaner_instance = MediaCleaner(standard_config)
    media_cleaner_instance.config.settings = {"action_delay": 1}

    # Act
    result = media_cleaner_instance.process_movies(
        library,
        radarr_instance,
        movies_library,
        movie_activity,
        trakt_movies,
        max_actions_per_run,
    )

    # Assert
    mock_process_library_rules.assert_called_once_with(
        library, movies_library, radarr_instance.get_movies(), movie_activity, trakt_movies, radarr_instance=radarr_instance
    )
    assert mock_process_movie.call_count == max_actions_per_run
    assert mock_sleep.call_count == max_actions_per_run
    assert result == 200


@patch("app.media_cleaner.MediaCleaner.delete_movie_if_allowed")
def test_process_movie_not_dry_run(mock_delete_movie_if_allowed, standard_config):
    # Arrange
    library = {"name": "Test Library"}
    radarr_instance = MagicMock()
    radarr_movie = {"title": "Test Movie", "sizeOnDisk": 100}
    actions_performed = 0
    max_actions_per_run = 1

    media_cleaner_instance = MediaCleaner(standard_config)
    media_cleaner_instance.config.settings = {"dry_run": False}

    # Act
    result = media_cleaner_instance.process_movie(
        library,
        radarr_instance,
        radarr_movie,
        actions_performed,
        max_actions_per_run,
    )

    # Assert
    mock_delete_movie_if_allowed.assert_called_once_with(
        library,
        radarr_instance,
        radarr_movie,
        actions_performed,
        max_actions_per_run,
        radarr_movie["sizeOnDisk"],
    )
    assert result == radarr_movie["sizeOnDisk"]


@patch("app.media_cleaner.MediaCleaner.delete_movie_if_allowed")
def test_process_movie_dry_run(mock_delete_movie_if_allowed, standard_config):
    # Arrange
    library = {"name": "Test Library"}
    radarr_instance = MagicMock()
    radarr_movie = {"title": "Test Movie", "sizeOnDisk": 100}
    actions_performed = 0
    max_actions_per_run = 1

    media_cleaner_instance = MediaCleaner(standard_config)
    media_cleaner_instance.config.settings = {"dry_run": True}

    # Act
    result = media_cleaner_instance.process_movie(
        library,
        radarr_instance,
        radarr_movie,
        actions_performed,
        max_actions_per_run,
    )

    # Assert
    mock_delete_movie_if_allowed.assert_not_called()
    assert result == radarr_movie["sizeOnDisk"]


def test_delete_series_server_error(standard_config):
    # Arrange
    mock_sonarr = MagicMock()
    sonarr_show = {"id": 1, "title": "Test Show"}
    episodes = [
        {"id": 1, "episodeFileId": 1},
        {"id": 2, "episodeFileId": 2},
    ]

    mock_sonarr.get_episode.return_value = episodes
    mock_sonarr.del_episode_file.side_effect = [
        None,
        PyarrServerError("Server Error", {}),
    ]

    media_cleaner_instance = MediaCleaner(standard_config)

    # Act
    media_cleaner_instance.delete_series(mock_sonarr, sonarr_show)

    # Assert
    mock_sonarr.get_episode.assert_called_once_with(sonarr_show["id"], series=True)
    mock_sonarr.upd_episode_monitor.assert_called_once_with(
        [episode["id"] for episode in episodes], False
    )
    assert mock_sonarr.del_episode_file.call_count == 2
    mock_sonarr.del_series.assert_not_called()


def test_delete_series_resource_not_found(standard_config):
    # Arrange
    mock_sonarr = MagicMock()
    sonarr_show = {"id": 1, "title": "Test Show"}
    episodes = [
        {"id": 1, "episodeFileId": 1},
        {"id": 2, "episodeFileId": 2},
    ]

    mock_sonarr.get_episode.return_value = episodes
    mock_sonarr.del_episode_file.side_effect = [
        None,
        PyarrResourceNotFound("Server Error"),
    ]

    media_cleaner_instance = MediaCleaner(standard_config)

    # Act
    media_cleaner_instance.delete_series(mock_sonarr, sonarr_show)

    # Assert
    mock_sonarr.get_episode.assert_called_once_with(sonarr_show["id"], series=True)
    mock_sonarr.upd_episode_monitor.assert_called_once_with(
        [episode["id"] for episode in episodes], False
    )
    assert mock_sonarr.del_episode_file.call_count == 2
    mock_sonarr.del_series.assert_called_once_with(sonarr_show["id"], delete_files=True)


def test_delete_series_no_errors(standard_config):
    # Arrange
    mock_sonarr = MagicMock()
    sonarr_show = {"id": 1, "title": "Test Show"}
    episodes = [
        {"id": 1, "episodeFileId": 1},
        {"id": 2, "episodeFileId": 2},
    ]

    mock_sonarr.get_episode.return_value = episodes

    media_cleaner_instance = MediaCleaner(standard_config)

    # Act
    media_cleaner_instance.delete_series(mock_sonarr, sonarr_show)

    # Assert
    mock_sonarr.get_episode.assert_called_once_with(sonarr_show["id"], series=True)
    mock_sonarr.upd_episode_monitor.assert_called_once_with(
        [episode["id"] for episode in episodes], False
    )
    assert mock_sonarr.del_episode_file.call_count == 2
    mock_sonarr.del_series.assert_called_once_with(sonarr_show["id"], delete_files=True)


@patch("builtins.input", return_value="y")
def test_delete_movie_if_allowed_interactive_yes(mock_input, standard_config):
    # Arrange
    library = {"name": "Test Library"}
    radarr_instance = MagicMock()
    radarr_movie = {"id": 1, "title": "Test Movie"}
    actions_performed = 0
    max_actions_per_run = 1
    disk_size = 100

    media_cleaner_instance = MediaCleaner(standard_config)
    media_cleaner_instance.config.settings = {"interactive": True}

    # Act
    media_cleaner_instance.delete_movie_if_allowed(
        library,
        radarr_instance,
        radarr_movie,
        actions_performed,
        max_actions_per_run,
        disk_size,
    )

    # Assert
    mock_input.assert_called_once()
    radarr_instance.del_movie.assert_called_once_with(
        radarr_movie["id"], delete_files=True, add_exclusion=False
    )


@patch("builtins.input", return_value="n")
def test_delete_movie_if_allowed_interactive_no(mock_input, standard_config):
    # Arrange
    library = {"name": "Test Library"}
    radarr_instance = MagicMock()
    radarr_movie = {"id": 1, "title": "Test Movie"}
    actions_performed = 0
    max_actions_per_run = 1
    disk_size = 100

    media_cleaner_instance = MediaCleaner(standard_config)
    media_cleaner_instance.config.settings = {"interactive": True}

    # Act
    media_cleaner_instance.delete_movie_if_allowed(
        library,
        radarr_instance,
        radarr_movie,
        actions_performed,
        max_actions_per_run,
        disk_size,
    )

    # Assert
    mock_input.assert_called_once()
    radarr_instance.del_movie.assert_not_called()


def test_delete_movie_if_allowed_not_interactive(standard_config):
    # Arrange
    library = {"name": "Test Library"}
    radarr_instance = MagicMock()
    radarr_movie = {"id": 1, "title": "Test Movie"}
    actions_performed = 0
    max_actions_per_run = 1
    disk_size = 100

    media_cleaner_instance = MediaCleaner(standard_config)
    media_cleaner_instance.config.settings = {"interactive": False}

    # Act
    media_cleaner_instance.delete_movie_if_allowed(
        library,
        radarr_instance,
        radarr_movie,
        actions_performed,
        max_actions_per_run,
        disk_size,
    )

    # Assert
    radarr_instance.del_movie.assert_called_once_with(
        radarr_movie["id"], delete_files=True, add_exclusion=False
    )


def test_get_library_config_found(standard_config):
    # Arrange
    config = MagicMock()
    config.config = {"libraries": [{"name": "Test Show", "config": "Test Config"}]}
    show = "Test Show"

    media_cleaner_instance = MediaCleaner(standard_config)

    # Act
    result = media_cleaner_instance.get_library_config(config, show)

    # Assert
    assert result == {"name": "Test Show", "config": "Test Config"}


def test_get_library_config_not_found(standard_config):
    # Arrange
    config = MagicMock()
    config.config = {"libraries": [{"name": "Test Show", "config": "Test Config"}]}
    show = "Nonexistent Show"

    media_cleaner_instance = MediaCleaner(standard_config)

    # Act
    result = media_cleaner_instance.get_library_config(config, show)

    # Assert
    assert result is None


@patch("app.media_cleaner.MediaCleaner.find_by_guid")
def test_get_plex_item_guid(mock_find_by_guid, standard_config):
    # Arrange
    plex_library = MagicMock()
    guid = "test-guid"

    mock_find_by_guid.return_value = "plex_media_item"

    media_cleaner_instance = MediaCleaner(standard_config)

    # Act
    result = media_cleaner_instance.get_plex_item(plex_library, guid=guid)

    # Assert
    mock_find_by_guid.assert_called_once_with(plex_library, guid)
    assert result == "plex_media_item"


@patch("app.media_cleaner.MediaCleaner.find_by_title_and_year")
def test_get_plex_item_title_and_year(mock_find_by_title_and_year, standard_config):
    # Arrange
    plex_library = MagicMock()
    title = "Test Title"
    year = 2022

    mock_find_by_title_and_year.return_value = "plex_media_item"

    media_cleaner_instance = MediaCleaner(standard_config)

    # Act
    result = media_cleaner_instance.get_plex_item(plex_library, title=title, year=year)

    # Assert
    mock_find_by_title_and_year.assert_called_once_with(plex_library, title, year, [])
    assert result == "plex_media_item"


@patch("app.media_cleaner.MediaCleaner.find_by_tvdb_id")
def test_get_plex_item_tvdb_id(mock_find_by_tvdb_id, standard_config):
    # Arrange
    plex_library = MagicMock()
    tvdb_id = "test-tvdb-id"

    mock_find_by_tvdb_id.return_value = "plex_media_item"

    media_cleaner_instance = MediaCleaner(standard_config)

    # Act
    result = media_cleaner_instance.get_plex_item(plex_library, tvdb_id=tvdb_id)

    # Assert
    mock_find_by_tvdb_id.assert_called_once_with(plex_library, tvdb_id)
    assert result == "plex_media_item"


@patch("app.media_cleaner.MediaCleaner.find_by_imdb_id")
def test_get_plex_item_imdb_id(mock_find_by_imdb_id, standard_config):
    # Arrange
    plex_library = MagicMock()
    imdb_id = "test-imdb-id"

    mock_find_by_imdb_id.return_value = "plex_media_item"

    media_cleaner_instance = MediaCleaner(standard_config)

    # Act
    result = media_cleaner_instance.get_plex_item(plex_library, imdb_id=imdb_id)

    # Assert
    mock_find_by_imdb_id.assert_called_once_with(plex_library, imdb_id)
    assert result == "plex_media_item"


def test_get_plex_item_not_found(standard_config):
    # Arrange
    plex_library = MagicMock()

    media_cleaner_instance = MediaCleaner(standard_config)

    # Act
    result = media_cleaner_instance.get_plex_item(plex_library)

    # Assert
    assert result is None


def test_find_by_guid_found(standard_config):
    # Arrange
    plex_library = [
        (["test-guid-1", "test-guid-2"], "plex_media_item_1"),
        (["test-guid-3", "test-guid-4"], "plex_media_item_2"),
    ]
    guid = "test-guid-1"

    media_cleaner_instance = MediaCleaner(standard_config)

    # Act
    result = media_cleaner_instance.find_by_guid(plex_library, guid)

    # Assert
    assert result == "plex_media_item_1"


def test_find_by_guid_not_found(standard_config):
    # Arrange
    plex_library = [
        (["test-guid-1", "test-guid-2"], "plex_media_item_1"),
        (["test-guid-3", "test-guid-4"], "plex_media_item_2"),
    ]
    guid = "nonexistent-guid"

    media_cleaner_instance = MediaCleaner(standard_config)

    # Act
    result = media_cleaner_instance.find_by_guid(plex_library, guid)

    # Assert
    assert result is None


@pytest.mark.parametrize(
    "plex_year, year, expected",
    [
        (None, 2022, True),  # No Plex year
        (2022, None, True),  # No input year
        (2022, 2022, True),  # Exact match
        (2023, 2022, True),  # Plex year is one more than input year
        (2021, 2022, True),  # Plex year is one less than input year
        (2025, 2022, False),  # Plex year is more than two more than input year
        (2020, 2023, False),  # Plex year is more than two less than input year
    ],
)
def test_match_year(standard_config, plex_year, year, expected):
    # Arrange
    plex_media_item = MagicMock()
    plex_media_item.year = plex_year

    media_cleaner_instance = MediaCleaner(standard_config)

    # Act
    result = media_cleaner_instance.match_year(plex_media_item, year)

    # Assert
    assert result == expected


@pytest.mark.parametrize(
    "plex_title, title, year, expected",
    [
        ("Test Title", "Test Title", 2022, True),  # Exact match
        ("test title (2022)", "Test Title", 2022, True),  # Match with year
        ("Different Title", "Test Title", 2022, False),  # No match
    ],
)
def test_match_title_and_year(standard_config, plex_title, title, year, expected):
    # Arrange
    plex_media_item = MagicMock()
    plex_media_item.title = plex_title

    media_cleaner_instance = MediaCleaner(standard_config)

    # Act
    result = media_cleaner_instance.match_title_and_year(plex_media_item, title, year)

    # Assert
    assert result == expected


@pytest.mark.parametrize(
    "plex_titles, title, year, alternate_titles, expected",
    [
        (
            ["Different Title"],
            "Test Title",
            2022,
            ["Alternate Title 1", "Alternate Title 2"],
            None,
        ),  # No match
        (
            ["Test Title"],
            "Test Title",
            2022,
            ["Alternate Title 1", "Alternate Title 2"],
            "plex_media_item",
        ),  # Exact match
        (
            ["Alternate Title 1"],
            "Test Title",
            2022,
            ["Alternate Title 1", "Alternate Title 2"],
            "plex_media_item",
        ),  # Match with alternate title
    ],
)
@patch.object(
    MediaCleaner,
    "match_title_and_year",
    side_effect=lambda x, y, z: x.title == y,
)
@patch.object(MediaCleaner, "match_year", return_value=True)
def test_find_by_title_and_year(
    mock_match_title_and_year,
    mock_match_year,
    standard_config,
    plex_titles,
    title,
    year,
    alternate_titles,
    expected,
):
    # Arrange
    plex_library = [(None, MagicMock(title=plex_title)) for plex_title in plex_titles]

    media_cleaner_instance = MediaCleaner(standard_config)

    # Act
    result = media_cleaner_instance.find_by_title_and_year(
        plex_library, title, year, alternate_titles
    )

    # Assert
    if expected is None:
        assert result is None
    else:
        assert result.title in [title] + alternate_titles


@pytest.mark.parametrize(
    "plex_guids, tvdb_id, expected",
    [
        ([], 1234, None),  # No guids
        (["tvdb://1234"], 1234, "plex_media_item"),  # Exact match
        (["tvdb://5678"], 1234, None),  # No match
    ],
)
def test_find_by_tvdb_id(standard_config, plex_guids, tvdb_id, expected):
    # Arrange
    plex_library = [
        (None, MagicMock(guids=[MagicMock(id=guid) for guid in plex_guids]))
    ]

    media_cleaner_instance = MediaCleaner(standard_config)

    # Act
    result = media_cleaner_instance.find_by_tvdb_id(plex_library, tvdb_id)

    # Assert
    if expected is None:
        assert result is None
    else:
        assert result.guids[0].id == f"tvdb://{tvdb_id}"


@pytest.mark.parametrize(
    "plex_guids, imdb_id, expected",
    [
        ([], 1234, None),  # No guids
        (["imdb://1234"], 1234, "plex_media_item"),  # Exact match
        (["imdb://5678"], 1234, None),  # No match
    ],
)
def test_find_by_imdb_id(standard_config, plex_guids, imdb_id, expected):
    # Arrange
    plex_library = [
        (None, MagicMock(guids=[MagicMock(id=guid) for guid in plex_guids]))
    ]

    media_cleaner_instance = MediaCleaner(standard_config)

    # Act
    result = media_cleaner_instance.find_by_imdb_id(plex_library, imdb_id)

    # Assert
    if expected is None:
        assert result is None
    else:
        assert result.guids[0].id == f"imdb://{imdb_id}"


@pytest.mark.parametrize(
    "watched_status, collections, trakt_movies, added_date, exclusions, expected",
    [
        # All checks pass
        (True, True, True, True, True, True),
        # Each individual check fails
        (False, True, True, True, True, False),  # check_watched_status fails
        (True, False, True, True, True, False),  # check_collections fails
        (True, True, False, True, True, False),  # check_trakt_movies fails
        (True, True, True, False, True, False),  # check_added_date fails
        (True, True, True, True, False, False),  # check_exclusions fails
        # Multiple checks fail
        (
            False,
            False,
            True,
            True,
            True,
            False,
        ),  # check_watched_status and check_collections fail
        (
            False,
            True,
            False,
            True,
            True,
            False,
        ),  # check_watched_status and check_trakt_movies fail
        # All checks fail
        (False, False, False, False, False, False),
    ],
)
def test_is_movie_actionable(
    standard_config,
    watched_status,
    collections,
    trakt_movies,
    added_date,
    exclusions,
    expected,
):
    # Arrange
    media_cleaner_instance = MediaCleaner(standard_config)
    media_cleaner_instance.check_watched_status = MagicMock(return_value=watched_status)
    media_cleaner_instance.check_collections = MagicMock(return_value=collections)
    media_cleaner_instance.check_trakt_movies = MagicMock(return_value=trakt_movies)
    media_cleaner_instance.check_added_date = MagicMock(return_value=added_date)
    media_cleaner_instance.check_exclusions = MagicMock(return_value=exclusions)

    # Act
    result = media_cleaner_instance.is_movie_actionable(
        "library",
        "activity_data",
        "media_data",
        "trakt_movies",
        "plex_media_item",
        "last_watched_threshold",
        "added_at_threshold",
        "apply_last_watch_threshold_to_collections",
    )

    # Assert
    assert result == expected


@pytest.mark.parametrize(
    "watched_data, last_watched_threshold, watch_status, expected",
    [
        # No watched_data and watch_status is "watched"
        (None, 10, "watched", False),
        # watched_data exists and last_watched is less than last_watched_threshold
        ({"last_watched": datetime.now() - timedelta(days=5)}, 10, "unwatched", False),
        # watched_data exists and last_watched is greater than last_watched_threshold
        ({"last_watched": datetime.now() - timedelta(days=15)}, 10, "unwatched", False),
        # No watched_data and watch_status is "unwatched"
        (None, 10, "unwatched", True),
        # watched_data exists, last_watched is less than last_watched_threshold, and watch_status is "watched"
        ({"last_watched": datetime.now() - timedelta(days=5)}, 10, "watched", False),
        # watched_data exists, last_watched is greater than last_watched_threshold, and watch_status is "watched"
        ({"last_watched": datetime.now() - timedelta(days=15)}, 10, "watched", True),
    ],
)
def test_check_watched_status(
    mocker,
    standard_config,
    watched_data,
    last_watched_threshold,
    watch_status,
    expected,
):
    # Arrange
    media_cleaner_instance = MediaCleaner(standard_config)
    mocker.patch("app.media_cleaner.find_watched_data", return_value=watched_data)
    library = {"watch_status": watch_status}
    activity_data = {}
    media_data = {"title": "Test Movie"}
    plex_media_item = MagicMock()

    # Act
    result = media_cleaner_instance.check_watched_status(
        library,
        activity_data,
        media_data,
        plex_media_item,
        last_watched_threshold,
    )

    # Assert
    assert result == expected


@pytest.mark.parametrize(
    "apply_last_watch_threshold, collection_tags, expected",
    [
        (True, ["collection1", "collection3"], False),
        (True, ["collection3", "collection4"], True),
        (False, ["collection1", "collection3"], True),
    ],
)
def test_check_collections(
    apply_last_watch_threshold, collection_tags, expected, standard_config
):
    media_data = {"title": "test_title"}
    plex_media_item = Mock()
    plex_media_item.collections = [Mock(tag=tag) for tag in collection_tags]

    media_cleaner = MediaCleaner(standard_config)
    media_cleaner.watched_collections = {"collection1", "collection2"}

    result = media_cleaner.check_collections(
        apply_last_watch_threshold, media_data, plex_media_item
    )

    assert result == expected


@pytest.mark.parametrize(
    "media_data, trakt_movies, expected",
    [
        ({"title": "movie1", "tvdb_id": "1"}, {"1": {"list": "watched"}}, False),
        ({"title": "movie2", "tmdbId": "2"}, {"2": {"list": "watched"}}, False),
        ({"title": "movie3", "tvdb_id": "3"}, {"4": {"list": "watched"}}, True),
    ],
)
def test_check_trakt_movies(media_data, trakt_movies, expected, media_cleaner):
    result = media_cleaner.check_trakt_movies(media_data, trakt_movies)
    assert result == expected


@pytest.mark.parametrize(
    "added_at_threshold, days_ago, expected",
    [
        # Test case where the media item was added less than the added_at_threshold days ago
        (10, 5, False),
        # Test case where the media item was added more than the added_at_threshold days ago
        (10, 15, True),
        # Test case where added_at_threshold is None, so the result should always be True
        (None, 5, True),
    ],
)
def test_check_added_date(added_at_threshold, days_ago, expected, media_cleaner):
    media_data = {"title": "test_title"}
    plex_media_item = Mock()
    plex_media_item.addedAt = datetime.now() - timedelta(days=days_ago)

    result = media_cleaner.check_added_date(
        media_data, plex_media_item, added_at_threshold
    )

    assert result == expected


def test_process_library_rules(standard_config):
    # Arrange
    media_cleaner_instance = MediaCleaner(standard_config)
    library_config = {
        "last_watched_threshold": 10,
        "added_at_threshold": 10,
        "apply_last_watch_threshold_to_collections": True,
        "sort": {},
    }
    plex_library = MagicMock()
    all_data = [
        {
            "title": "Test Movie",
            "year": 2020,
            "alternateTitles": [],
            "statistics": {"episodeFileCount": 0},
        }
    ]
    activity_data = {}
    trakt_movies = {}
    media_cleaner_instance.get_plex_item = MagicMock(return_value=MagicMock())
    media_cleaner_instance.is_movie_actionable = MagicMock(return_value=True)

    # Act
    result = list(
        media_cleaner_instance.process_library_rules(
            library_config,
            plex_library,
            all_data,
            activity_data,
            trakt_movies,
        )
    )

    # Assert
    assert result == all_data


# JustWatch exclusion tests
class TestCheckExcludedJustWatch:
    def test_no_justwatch_config_returns_true(self, mocker):
        """When no JustWatch config is provided, should not exclude."""
        from app.media_cleaner import check_excluded_justwatch

        media_data = {"title": "Test Movie", "tmdbId": 123}
        plex_media_item = MagicMock()
        plex_media_item.title = "Test Movie"
        plex_media_item.year = 2022
        exclude = {}  # No JustWatch config

        result = check_excluded_justwatch(media_data, plex_media_item, exclude, None)

        assert result is True

    def test_no_justwatch_instance_returns_true(self, mocker):
        """When no JustWatch instance is provided, should not exclude."""
        from app.media_cleaner import check_excluded_justwatch

        media_data = {"title": "Test Movie", "tmdbId": 123}
        plex_media_item = MagicMock()
        plex_media_item.title = "Test Movie"
        plex_media_item.year = 2022
        exclude = {"justwatch": {"country": "US", "available_on": ["netflix"]}}

        result = check_excluded_justwatch(media_data, plex_media_item, exclude, None)

        assert result is True

    def test_available_on_excludes_when_available(self, mocker):
        """When available_on is set and media IS available, should exclude."""
        from app.media_cleaner import check_excluded_justwatch

        media_data = {"title": "Test Movie", "tmdbId": 123, "year": 2022}
        plex_media_item = MagicMock()
        plex_media_item.title = "Test Movie"
        plex_media_item.year = 2022
        exclude = {"justwatch": {"available_on": ["netflix"]}}

        mock_justwatch = MagicMock()
        mock_justwatch.available_on.return_value = True

        result = check_excluded_justwatch(
            media_data, plex_media_item, exclude, mock_justwatch
        )

        mock_justwatch.available_on.assert_called_once_with(
            "Test Movie", 2022, "movie", ["netflix"]
        )
        assert result is False  # Excluded

    def test_available_on_does_not_exclude_when_not_available(self, mocker):
        """When available_on is set but media is NOT available, should not exclude."""
        from app.media_cleaner import check_excluded_justwatch

        media_data = {"title": "Test Movie", "tmdbId": 123, "year": 2022}
        plex_media_item = MagicMock()
        plex_media_item.title = "Test Movie"
        plex_media_item.year = 2022
        exclude = {"justwatch": {"available_on": ["netflix"]}}

        mock_justwatch = MagicMock()
        mock_justwatch.available_on.return_value = False

        result = check_excluded_justwatch(
            media_data, plex_media_item, exclude, mock_justwatch
        )

        assert result is True  # Not excluded

    def test_not_available_on_excludes_when_not_available(self, mocker):
        """When not_available_on is set and media is NOT available, should exclude."""
        from app.media_cleaner import check_excluded_justwatch

        media_data = {"title": "Test Movie", "tmdbId": 123, "year": 2022}
        plex_media_item = MagicMock()
        plex_media_item.title = "Test Movie"
        plex_media_item.year = 2022
        exclude = {"justwatch": {"not_available_on": ["netflix"]}}

        mock_justwatch = MagicMock()
        mock_justwatch.is_not_available_on.return_value = True

        result = check_excluded_justwatch(
            media_data, plex_media_item, exclude, mock_justwatch
        )

        mock_justwatch.is_not_available_on.assert_called_once_with(
            "Test Movie", 2022, "movie", ["netflix"]
        )
        assert result is False  # Excluded

    def test_not_available_on_does_not_exclude_when_available(self, mocker):
        """When not_available_on is set but media IS available, should not exclude."""
        from app.media_cleaner import check_excluded_justwatch

        media_data = {"title": "Test Movie", "tmdbId": 123, "year": 2022}
        plex_media_item = MagicMock()
        plex_media_item.title = "Test Movie"
        plex_media_item.year = 2022
        exclude = {"justwatch": {"not_available_on": ["netflix"]}}

        mock_justwatch = MagicMock()
        mock_justwatch.is_not_available_on.return_value = False

        result = check_excluded_justwatch(
            media_data, plex_media_item, exclude, mock_justwatch
        )

        assert result is True  # Not excluded

    def test_detects_movie_type_from_tmdb_id(self, mocker):
        """Should detect movie type from tmdbId in media_data."""
        from app.media_cleaner import check_excluded_justwatch

        media_data = {"title": "Test Movie", "tmdbId": 123, "year": 2022}
        plex_media_item = MagicMock()
        plex_media_item.title = "Test Movie"
        plex_media_item.year = 2022
        exclude = {"justwatch": {"available_on": ["netflix"]}}

        mock_justwatch = MagicMock()
        mock_justwatch.available_on.return_value = False

        check_excluded_justwatch(media_data, plex_media_item, exclude, mock_justwatch)

        # Should pass "movie" as media_type
        mock_justwatch.available_on.assert_called_once_with(
            "Test Movie", 2022, "movie", ["netflix"]
        )

    def test_detects_show_type_from_tvdb_id(self, mocker):
        """Should detect show type when tmdbId is not present."""
        from app.media_cleaner import check_excluded_justwatch

        media_data = {"title": "Test Show", "tvdbId": 456, "year": 2022}
        plex_media_item = MagicMock()
        plex_media_item.title = "Test Show"
        plex_media_item.year = 2022
        exclude = {"justwatch": {"available_on": ["netflix"]}}

        mock_justwatch = MagicMock()
        mock_justwatch.available_on.return_value = False

        check_excluded_justwatch(media_data, plex_media_item, exclude, mock_justwatch)

        # Should pass "show" as media_type (no tmdbId present)
        mock_justwatch.available_on.assert_called_once_with(
            "Test Show", 2022, "show", ["netflix"]
        )

    def test_uses_plex_title_as_fallback(self, mocker):
        """Should use Plex media item title if media_data title is missing."""
        from app.media_cleaner import check_excluded_justwatch

        media_data = {"tmdbId": 123, "year": 2022}  # No title
        plex_media_item = MagicMock()
        plex_media_item.title = "Plex Title"
        plex_media_item.year = 2022
        exclude = {"justwatch": {"available_on": ["netflix"]}}

        mock_justwatch = MagicMock()
        mock_justwatch.available_on.return_value = False

        check_excluded_justwatch(media_data, plex_media_item, exclude, mock_justwatch)

        # Should use Plex title
        mock_justwatch.available_on.assert_called_once_with(
            "Plex Title", 2022, "movie", ["netflix"]
        )


class TestMediaCleanerGetJustWatchInstance:
    def test_returns_none_when_no_justwatch_config(self, mocker, standard_config):
        """Should return None when no JustWatch exclusion config exists."""
        mocker.patch("app.media_cleaner.PlexServer", return_value=MagicMock())

        media_cleaner = MediaCleaner(standard_config)
        library = {"name": "Test", "exclude": {}}

        result = media_cleaner.get_justwatch_instance(library)

        assert result is None

    def test_returns_none_when_no_country(self, mocker, standard_config):
        """Should return None when country is not configured."""
        mocker.patch("app.media_cleaner.PlexServer", return_value=MagicMock())

        media_cleaner = MediaCleaner(standard_config)
        library = {"name": "Test", "exclude": {"justwatch": {"available_on": ["netflix"]}}}

        result = media_cleaner.get_justwatch_instance(library)

        assert result is None

    def test_creates_instance_with_library_country(self, mocker, standard_config):
        """Should create instance with library-level country setting."""
        mocker.patch("app.media_cleaner.PlexServer", return_value=MagicMock())
        mock_justwatch = mocker.patch("app.media_cleaner.JustWatch")

        media_cleaner = MediaCleaner(standard_config)
        library = {
            "name": "Test",
            "exclude": {"justwatch": {"country": "US", "available_on": ["netflix"]}},
        }

        result = media_cleaner.get_justwatch_instance(library)

        mock_justwatch.assert_called_once_with("US", "en")
        assert result == mock_justwatch.return_value

    def test_creates_instance_with_global_country(self, mocker, standard_config):
        """Should create instance with global country setting."""
        mocker.patch("app.media_cleaner.PlexServer", return_value=MagicMock())
        mock_justwatch = mocker.patch("app.media_cleaner.JustWatch")

        standard_config.settings["justwatch"] = {"country": "GB", "language": "en"}
        media_cleaner = MediaCleaner(standard_config)
        library = {"name": "Test", "exclude": {"justwatch": {"available_on": ["netflix"]}}}

        result = media_cleaner.get_justwatch_instance(library)

        mock_justwatch.assert_called_once_with("GB", "en")
        assert result == mock_justwatch.return_value

    def test_caches_instances_by_country_language(self, mocker, standard_config):
        """Should cache and reuse JustWatch instances by country+language."""
        mocker.patch("app.media_cleaner.PlexServer", return_value=MagicMock())
        mock_justwatch = mocker.patch("app.media_cleaner.JustWatch")

        media_cleaner = MediaCleaner(standard_config)
        library1 = {
            "name": "Movies",
            "exclude": {"justwatch": {"country": "US", "available_on": ["netflix"]}},
        }
        library2 = {
            "name": "TV Shows",
            "exclude": {"justwatch": {"country": "US", "available_on": ["hulu"]}},
        }

        result1 = media_cleaner.get_justwatch_instance(library1)
        result2 = media_cleaner.get_justwatch_instance(library2)

        # Should only create one instance (cached)
        mock_justwatch.assert_called_once_with("US", "en")
        assert result1 == result2


@pytest.mark.unit
class TestCheckExclusionsWithJustWatch:
    """Test JustWatch integration with the full check_exclusions pipeline."""

    def test_check_exclusions_includes_justwatch(self, mocker, standard_config):
        """Test that check_exclusions includes JustWatch check."""
        mocker.patch("app.media_cleaner.PlexServer", return_value=MagicMock())
        mock_justwatch = mocker.patch("app.media_cleaner.JustWatch")

        mock_justwatch_instance = MagicMock()
        mock_justwatch_instance.available_on.return_value = True
        mock_justwatch.return_value = mock_justwatch_instance

        standard_config.settings["justwatch"] = {"country": "US"}
        media_cleaner = MediaCleaner(standard_config)

        plex_item = MagicMock()
        plex_item.title = "Streaming Movie"
        plex_item.year = 2020
        plex_item.genres = [MagicMock(tag="Action")]
        plex_item.collections = []
        plex_item.labels = []
        plex_item.studio = None
        plex_item.directors = []
        plex_item.writers = []
        plex_item.roles = []
        plex_item.producers = []

        media_data = {"title": "Streaming Movie", "year": 2020, "tmdbId": 12345}
        library = {
            "name": "Movies",
            "exclude": {
                "titles": [],
                "genres": [],
                "justwatch": {"available_on": ["netflix"]},
            },
        }

        result = media_cleaner.check_exclusions(library, media_data, plex_item)

        # JustWatch check should have been called
        mock_justwatch_instance.available_on.assert_called_once()
        # Result should be False because movie is on streaming
        assert result is False

    def test_check_exclusions_justwatch_passes_when_not_on_streaming(
        self, mocker, standard_config
    ):
        """Test that movies not on streaming pass the JustWatch check."""
        mocker.patch("app.media_cleaner.PlexServer", return_value=MagicMock())
        mock_justwatch = mocker.patch("app.media_cleaner.JustWatch")

        mock_justwatch_instance = MagicMock()
        mock_justwatch_instance.available_on.return_value = False
        mock_justwatch.return_value = mock_justwatch_instance

        standard_config.settings["justwatch"] = {"country": "US"}
        media_cleaner = MediaCleaner(standard_config)

        plex_item = MagicMock()
        plex_item.title = "Rare Movie"
        plex_item.year = 2020
        plex_item.genres = [MagicMock(tag="Action")]
        plex_item.collections = []
        plex_item.labels = []
        plex_item.studio = None
        plex_item.directors = []
        plex_item.writers = []
        plex_item.roles = []
        plex_item.producers = []

        media_data = {"title": "Rare Movie", "year": 2020, "tmdbId": 99999}
        library = {
            "name": "Movies",
            "exclude": {
                "titles": [],
                "genres": [],
                "justwatch": {"available_on": ["netflix"]},
            },
        }

        result = media_cleaner.check_exclusions(library, media_data, plex_item)

        # Result should be True because movie is NOT on streaming
        assert result is True

    def test_justwatch_combined_with_other_exclusions(self, mocker, standard_config):
        """Test that JustWatch works correctly with other exclusion rules."""
        mocker.patch("app.media_cleaner.PlexServer", return_value=MagicMock())
        mock_justwatch = mocker.patch("app.media_cleaner.JustWatch")

        mock_justwatch_instance = MagicMock()
        mock_justwatch_instance.available_on.return_value = False  # Not on Netflix
        mock_justwatch.return_value = mock_justwatch_instance

        standard_config.settings["justwatch"] = {"country": "US"}
        media_cleaner = MediaCleaner(standard_config)

        # Movie that passes JustWatch but fails genre exclusion
        plex_item = MagicMock()
        plex_item.title = "Horror on Netflix"
        plex_item.year = 2020
        plex_item.genres = [MagicMock(tag="Horror")]  # Excluded genre
        plex_item.collections = []
        plex_item.labels = []
        plex_item.studio = None
        plex_item.directors = []
        plex_item.writers = []
        plex_item.roles = []
        plex_item.producers = []

        media_data = {"title": "Horror on Netflix", "year": 2020, "tmdbId": 11111}
        library = {
            "name": "Movies",
            "exclude": {
                "genres": ["Horror"],  # Excluded
                "justwatch": {"available_on": ["netflix"]},
            },
        }

        result = media_cleaner.check_exclusions(library, media_data, plex_item)

        # Should be False because genre is excluded (even though JustWatch passes)
        assert result is False
