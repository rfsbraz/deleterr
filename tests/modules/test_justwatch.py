import unittest
from unittest.mock import MagicMock, patch

from simplejustwatchapi.query import MediaEntry

from app.modules.justwatch import JustWatch


class TestJustWatch(unittest.TestCase):
    @patch("app.modules.justwatch.search")
    def test_search(self, mock_search):
        # Arrange
        mock_search.return_value = ["result1", "result2", "result3"]
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance._search("test_title")

        # Assert
        mock_search.assert_called_once_with("test_title", "US", "en", 5, True)
        self.assertEqual(result, ["result1", "result2", "result3"])

    @patch.object(JustWatch, "_search")
    def test_search_by_title_and_year(self, mock_search):
        # Arrange
        mock_entry1 = MagicMock()
        mock_entry1.title = "title1"
        mock_entry1.release_year = 2001

        mock_entry2 = MagicMock()
        mock_entry2.title = "title2"
        mock_entry2.release_year = 2002

        mock_entry3 = MagicMock()
        mock_entry3.title = "title1"
        mock_entry3.release_year = 2002

        mock_search.return_value = [mock_entry1, mock_entry2, mock_entry3]

        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance.search_by_title_and_year("title1", 2001, "movie")

        # Assert
        mock_search.assert_called_once_with("title1")
        self.assertEqual(
            result,
            [mock_entry1],
        )

    @patch.object(JustWatch, "_search")
    def test_search_by_title_and_year(self, mock_search):
        # Arrange
        mock_entry1 = MagicMock()
        mock_entry1.title = "title1"
        mock_entry1.release_year = 2001

        mock_entry2 = MagicMock()
        mock_entry2.title = "title2"
        mock_entry2.release_year = 2002

        mock_entry3 = MagicMock()
        mock_entry3.title = "title1"
        mock_entry3.release_year = 2001

        mock_search.return_value = [mock_entry1, mock_entry2, mock_entry3]

        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance.search_by_title_and_year("title1", 2001, "movie")

        # Assert
        mock_search.assert_called_once_with("title1")
        self.assertEqual(
            result,
            [mock_entry1, mock_entry3],
        )

    @patch.object(JustWatch, "search_by_title_and_year")
    def test_available_on(self, mock_search_by_title_and_year):
        # Arrange
        mock_entry1 = MagicMock()
        mock_entry1.offers = ["provider1", "provider2"]

        mock_search_by_title_and_year.return_value = mock_entry1
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance.available_on("title1", 2001, "movie", ["provider1"])

        # Assert
        mock_search_by_title_and_year.assert_called_once_with("title1", 2001, "movie")
        self.assertTrue(result)

    @patch.object(JustWatch, "search_by_title_and_year")
    def test_available_on_false(self, mock_search_by_title_and_year):
        # Arrange
        mock_entry1 = MagicMock()
        mock_entry1.offers = ["provider2", "provider3"]

        mock_search_by_title_and_year.return_value = mock_entry1
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance.available_on("title1", 2001, "movie", ["provider1"])

        # Assert
        mock_search_by_title_and_year.assert_called_once_with("title1", 2001, "movie")
        self.assertFalse(result)

    @patch.object(JustWatch, "search_by_title_and_year")
    def test_available_on_any(self, mock_search_by_title_and_year):
        # Arrange
        mock_entry1 = MagicMock()
        mock_entry1.offers = ["provider1", "provider2"]

        mock_search_by_title_and_year.return_value = mock_entry1
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance.available_on("title1", 2001, "movie", ["any"])

        # Assert
        mock_search_by_title_and_year.assert_called_once_with("title1", 2001, "movie")
        self.assertTrue(result)

    @patch.object(JustWatch, "search_by_title_and_year")
    def test_available_on_no_result(self, mock_search_by_title_and_year):
        # Arrange
        mock_search_by_title_and_year.return_value = None
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance.available_on("title1", 2001, "movie", ["provider1"])

        # Assert
        mock_search_by_title_and_year.assert_called_once_with("title1", 2001, "movie")
        self.assertFalse(result)

    @patch.object(JustWatch, "available_on")
    def test_is_not_available_on_true(self, mock_available_on):
        # Arrange
        mock_available_on.return_value = False
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance.is_not_available_on(
            "title1", 2001, "movie", ["provider1"]
        )

        # Assert
        mock_available_on.assert_called_once_with(
            "title1", 2001, "movie", ["provider1"]
        )
        self.assertTrue(result)

    @patch.object(JustWatch, "available_on")
    def test_is_not_available_on_false(self, mock_available_on):
        # Arrange
        mock_available_on.return_value = True
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance.is_not_available_on(
            "title1", 2001, "movie", ["provider1"]
        )

        # Assert
        mock_available_on.assert_called_once_with(
            "title1", 2001, "movie", ["provider1"]
        )
        self.assertFalse(result)
