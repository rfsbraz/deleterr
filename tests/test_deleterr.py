import unittest
from unittest.mock import Mock
from app.deleterr import library_meets_disk_space_threshold, find_watched_data


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
