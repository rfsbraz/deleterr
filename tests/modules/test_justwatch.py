from unittest.mock import MagicMock, patch

import pytest

from app.modules.justwatch import JustWatch


@pytest.mark.unit
class TestJustWatch:
    @patch("app.modules.justwatch._search_justwatch")
    def test_search(self, mock_search):
        # Arrange
        mock_search.return_value = ["result1", "result2", "result3"]
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance._search("test_title")

        # Assert
        mock_search.assert_called_once_with("test_title", "US", "en", 5, False)
        assert result == ["result1", "result2", "result3"]

    @patch("app.modules.justwatch._search_justwatch")
    def test_search_caching(self, mock_search):
        # Arrange
        mock_search.return_value = ["result1", "result2"]
        justwatch_instance = JustWatch("US", "en")

        # Act - call twice with same parameters
        result1 = justwatch_instance._search("test_title")
        result2 = justwatch_instance._search("test_title")

        # Assert - search should only be called once due to caching
        mock_search.assert_called_once_with("test_title", "US", "en", 5, False)
        assert result1 == result2

    @patch("app.modules.justwatch._search_justwatch")
    def test_search_error_handling(self, mock_search):
        # Arrange
        mock_search.side_effect = Exception("API Error")
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance._search("test_title")

        # Assert - should return empty list on error
        assert result == []

    @patch("app.modules.justwatch._search_justwatch")
    def test_clear_cache(self, mock_search):
        # Arrange
        mock_search.return_value = ["result1"]
        justwatch_instance = JustWatch("US", "en")

        # Act - search, clear cache, search again
        justwatch_instance._search("test_title")
        justwatch_instance.clear_cache()
        justwatch_instance._search("test_title")

        # Assert - search should be called twice after cache clear
        assert mock_search.call_count == 2

    @patch.object(JustWatch, "_search")
    def test_search_by_title_and_year_exact_match(self, mock_search):
        # Arrange
        mock_entry1 = MagicMock()
        mock_entry1.title = "title1"
        mock_entry1.release_year = 2001

        mock_entry2 = MagicMock()
        mock_entry2.title = "title2"
        mock_entry2.release_year = 2002

        mock_search.return_value = [mock_entry1, mock_entry2]
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance.search_by_title_and_year("title1", 2001, "movie")

        # Assert
        mock_search.assert_called_once_with("title1")
        assert result == mock_entry1

    @patch.object(JustWatch, "_search")
    def test_search_by_title_and_year_case_insensitive(self, mock_search):
        # Arrange
        mock_entry = MagicMock()
        mock_entry.title = "Title1"
        mock_entry.release_year = 2001

        mock_search.return_value = [mock_entry]
        justwatch_instance = JustWatch("US", "en")

        # Act - search with lowercase
        result = justwatch_instance.search_by_title_and_year("title1", 2001, "movie")

        # Assert
        assert result == mock_entry

    @patch.object(JustWatch, "_search")
    def test_search_by_title_and_year_with_tolerance(self, mock_search):
        # Arrange
        mock_entry = MagicMock()
        mock_entry.title = "title1"
        mock_entry.release_year = 2001

        mock_search.return_value = [mock_entry]
        justwatch_instance = JustWatch("US", "en")

        # Act - search with 1 year difference
        result = justwatch_instance.search_by_title_and_year("title1", 2002, "movie")

        # Assert
        assert result == mock_entry

    @patch.object(JustWatch, "_search")
    def test_search_by_title_and_year_no_match(self, mock_search):
        # Arrange
        mock_entry = MagicMock()
        mock_entry.title = "different_title"
        mock_entry.release_year = 2001

        mock_search.return_value = [mock_entry]
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance.search_by_title_and_year("title1", 2001, "movie")

        # Assert
        assert result is None

    @patch.object(JustWatch, "_search")
    def test_search_by_title_and_year_empty_results(self, mock_search):
        # Arrange
        mock_search.return_value = []
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance.search_by_title_and_year("title1", 2001, "movie")

        # Assert
        assert result is None

    @patch.object(JustWatch, "search_by_title_and_year")
    def test_available_on(self, mock_search_by_title_and_year):
        # Arrange
        mock_package = MagicMock()
        mock_package.technical_name = "netflix"
        mock_offer = MagicMock()
        mock_offer.package = mock_package

        mock_entry = MagicMock()
        mock_entry.offers = [mock_offer]

        mock_search_by_title_and_year.return_value = mock_entry
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance.available_on("title1", 2001, "movie", ["netflix"])

        # Assert
        mock_search_by_title_and_year.assert_called_once_with("title1", 2001, "movie")
        assert result is True

    @patch.object(JustWatch, "search_by_title_and_year")
    def test_available_on_case_insensitive(self, mock_search_by_title_and_year):
        # Arrange
        mock_package = MagicMock()
        mock_package.technical_name = "Netflix"
        mock_offer = MagicMock()
        mock_offer.package = mock_package

        mock_entry = MagicMock()
        mock_entry.offers = [mock_offer]

        mock_search_by_title_and_year.return_value = mock_entry
        justwatch_instance = JustWatch("US", "en")

        # Act - providers in different case
        result = justwatch_instance.available_on("title1", 2001, "movie", ["NETFLIX"])

        # Assert
        assert result is True

    @patch.object(JustWatch, "search_by_title_and_year")
    def test_available_on_false(self, mock_search_by_title_and_year):
        # Arrange
        mock_package = MagicMock()
        mock_package.technical_name = "amazon"
        mock_offer = MagicMock()
        mock_offer.package = mock_package

        mock_entry = MagicMock()
        mock_entry.offers = [mock_offer]

        mock_search_by_title_and_year.return_value = mock_entry
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance.available_on("title1", 2001, "movie", ["netflix"])

        # Assert
        mock_search_by_title_and_year.assert_called_once_with("title1", 2001, "movie")
        assert result is False

    @patch.object(JustWatch, "search_by_title_and_year")
    def test_available_on_any(self, mock_search_by_title_and_year):
        # Arrange
        mock_offer = MagicMock()
        mock_offer.technical_name = "some_provider"

        mock_entry = MagicMock()
        mock_entry.offers = [mock_offer]

        mock_search_by_title_and_year.return_value = mock_entry
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance.available_on("title1", 2001, "movie", ["any"])

        # Assert
        mock_search_by_title_and_year.assert_called_once_with("title1", 2001, "movie")
        assert result is True

    @patch.object(JustWatch, "search_by_title_and_year")
    def test_available_on_any_no_offers(self, mock_search_by_title_and_year):
        # Arrange
        mock_entry = MagicMock()
        mock_entry.offers = []

        mock_search_by_title_and_year.return_value = mock_entry
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance.available_on("title1", 2001, "movie", ["any"])

        # Assert
        assert result is False

    @patch.object(JustWatch, "search_by_title_and_year")
    def test_available_on_no_result(self, mock_search_by_title_and_year):
        # Arrange
        mock_search_by_title_and_year.return_value = None
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance.available_on("title1", 2001, "movie", ["netflix"])

        # Assert
        mock_search_by_title_and_year.assert_called_once_with("title1", 2001, "movie")
        assert result is False

    @patch.object(JustWatch, "available_on")
    def test_is_not_available_on_true(self, mock_available_on):
        # Arrange
        mock_available_on.return_value = False
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance.is_not_available_on(
            "title1", 2001, "movie", ["netflix"]
        )

        # Assert
        mock_available_on.assert_called_once_with(
            "title1", 2001, "movie", ["netflix"]
        )
        assert result is True

    @patch.object(JustWatch, "available_on")
    def test_is_not_available_on_false(self, mock_available_on):
        # Arrange
        mock_available_on.return_value = True
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance.is_not_available_on(
            "title1", 2001, "movie", ["netflix"]
        )

        # Assert
        mock_available_on.assert_called_once_with(
            "title1", 2001, "movie", ["netflix"]
        )
        assert result is False


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

        # Act - use lowercase for case insensitivity test
        result = justwatch_instance.available_on(
            "Better Call Saul", 2015, "show", ["netflix"]
        )

        # Assert
        assert result

    def test_is_not_available_on(self):
        # Arrange
        justwatch_instance = JustWatch("US", "en")

        # Act
        result = justwatch_instance.is_not_available_on(
            "Better Call Saul", 2015, "show", ["disneyplus"]
        )

        # Assert
        assert result
