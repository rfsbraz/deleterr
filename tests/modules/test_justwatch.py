from unittest.mock import MagicMock, patch

import pytest

from app.modules.justwatch import JustWatch


@pytest.mark.unit
class TestJustWatch:
    @patch("app.modules.justwatch.search")
    def test_search(self, mock_search):
        # Arrange
        mock_search.return_value = ["result1", "result2", "result3"]
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance._search("test_title")

        # Assert
        mock_search.assert_called_once_with("test_title", "US", "en", 5, False)
        assert result == ["result1", "result2", "result3"]

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
        assert result == mock_entry1

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
        assert result == mock_entry1

    @patch.object(JustWatch, "search_by_title_and_year")
    def test_available_on(self, mock_search_by_title_and_year):
        # Arrange
        mock_offer = MagicMock()
        mock_offer.package.technical_name = "provider1"

        mock_entry1 = MagicMock()
        mock_entry1.offers = [mock_offer]

        mock_search_by_title_and_year.return_value = mock_entry1
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance.available_on("title1", 2001, "movie", ["provider1"])

        # Assert
        mock_search_by_title_and_year.assert_called_once_with("title1", 2001, "movie")
        assert result

    @patch.object(JustWatch, "search_by_title_and_year")
    def test_available_on_false(self, mock_search_by_title_and_year):
        # Arrange
        mock_offer = MagicMock()
        mock_offer.package.technical_name = "provider2"

        mock_entry1 = MagicMock()
        mock_entry1.offers = [mock_offer]

        mock_search_by_title_and_year.return_value = mock_entry1
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance.available_on("title1", 2001, "movie", ["provider1"])

        # Assert
        mock_search_by_title_and_year.assert_called_once_with("title1", 2001, "movie")
        assert not result

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
        assert result

    @patch.object(JustWatch, "search_by_title_and_year")
    def test_available_on_no_result(self, mock_search_by_title_and_year):
        # Arrange
        mock_search_by_title_and_year.return_value = None
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance.available_on("title1", 2001, "movie", ["provider1"])

        # Assert
        mock_search_by_title_and_year.assert_called_once_with("title1", 2001, "movie")
        assert not result

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
        assert result

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
        assert not result


@pytest.mark.integration
class TestJustWatchIntegration:
    def test_search(self):
        # Arrange
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance._search("Better Call Saul")

        # Assert
        assert isinstance(result, list)

        assert result

    def test_search_by_title_and_year(self):
        # Arrange
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance.search_by_title_and_year(
            "Better Call Saul", 2015, "show"
        )

        # Assert that the object exists
        assert result

    def test_available_on(self):
        # Arrange
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance.available_on(
            "Better Call Saul", 2015, "show", ["Netflix"]
        )

        # Assert
        assert result

    def test_is_not_available_on(self):
        # Arrange
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance.is_not_available_on(
            "Better Call Saul", 2015, "show", ["Disney+"]
        )

        # Assert
        assert result
