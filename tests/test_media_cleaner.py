import unittest

from app.media_cleaner import (
    find_watched_data,
    library_meets_disk_space_threshold,
    MediaCleaner,
    DEFAULT_MAX_ACTIONS_PER_RUN,
)
from unittest.mock import Mock, patch, MagicMock


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


class TestMediaCleaner(unittest.TestCase):
    @patch("app.media_cleaner.logger")
    @patch.object(MediaCleaner, "process_shows")
    @patch.object(MediaCleaner, "get_show_activity")
    @patch.object(MediaCleaner, "get_plex_library")
    @patch.object(MediaCleaner, "get_trakt_items")
    @patch.object(MediaCleaner, "filter_shows")
    @patch("app.media_cleaner._get_config_value")
    @patch("app.media_cleaner.library_meets_disk_space_threshold")
    def test_process_library(
        self,
        mock_library_meets_disk_space_threshold,
        mock_get_config_value,
        mock_filter_shows,
        mock_get_trakt_items,
        mock_get_plex_library,
        mock_get_show_activity,
        mock_process_shows,
        mock_logger,
    ):
        # Arrange
        media_cleaner = MediaCleaner({})
        library = {"name": "Test Library"}
        sonarr_instance = Mock()
        unfiltered_all_show_data = MagicMock()

        mock_library_meets_disk_space_threshold.return_value = True
        mock_get_config_value.return_value = 10
        mock_filter_shows.return_value = MagicMock()

        mock_get_trakt_items.return_value = MagicMock()
        mock_get_plex_library.return_value = MagicMock(totalSize=20)
        mock_get_show_activity.return_value = MagicMock()
        mock_process_shows.return_value = 5

        # Act
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
        self.assertEqual(result, 5)


if __name__ == "__main__":
    unittest.main()
