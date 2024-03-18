from unittest.mock import MagicMock, Mock, patch

import pytest
import trakt

from app.modules.trakt import Trakt, _process_trakt_item_list, extract_info_from_url


@pytest.fixture
def trakt_instance_and_mock():
    with patch("trakt.Trakt") as trakt_mock:
        yield Trakt("trakt_id", "trakt_secret"), trakt_mock


@pytest.mark.parametrize(
    "url, expected_result",
    [
        # Test for movie action with period pattern
        ("https://trakt.tv/movies/watched/yearly", (None, "watched", "yearly")),
        ("https://trakt.tv/shows/collected/weekly", (None, "collected", "weekly")),
        # Test for movie pattern
        ("https://trakt.tv/movies/trending", (None, "trending", None)),
        ("https://trakt.tv/shows/popular", (None, "popular", None)),
        # Test for user watchlist pattern
        ("https://trakt.tv/users/johndoe/watchlist", ("johndoe", "watchlist", None)),
        # Test for user list pattern
        ("https://trakt.tv/users/johndoe/favorites", ("johndoe", "favorites", None)),
        # Test for user custom list
        (
            "https://trakt.tv/users/johndoe/lists/customlist",
            ("johndoe", "customlist", None),
        ),
        # Test for invalid URL
        ("https://invalid.url", (None, None, None)),
    ],
)
def test_extract_info_from_url(url, expected_result):
    assert extract_info_from_url(url) == expected_result


def test__get_all_items_for_url(trakt_instance_and_mock):
    trakt_instance, _ = trakt_instance_and_mock

    # Arrange
    trakt_instance._get_all_items_for_url = MagicMock(
        return_value=[{"title": "Test Movie"}]
    )
    trakt_config = {
        "max_items_per_list": 50,
        "lists": ["https://trakt.tv/shows/trending", "https://trakt.tv/shows/popular"],
    }

    # Act and Assert
    # Test with valid media type
    result = trakt_instance.get_all_items_for_url("movie", trakt_config)
    assert result == [{"title": "Test Movie"}]
    trakt_instance._get_all_items_for_url.assert_called_once_with("movie", trakt_config)

    # Test with invalid media type
    with pytest.raises(ValueError) as excinfo:
        trakt_instance.get_all_items_for_url("invalid", trakt_config)
    assert str(excinfo.value) == "Invalid media type. Expected 'movie' or 'show'."


@patch(
    "app.modules.trakt.extract_info_from_url",
    return_value=("username", "listname", "recurrence"),
)
@patch("app.modules.trakt._process_trakt_item_list")
@patch.object(Trakt, "_fetch_list_items", return_value=[{"title": "Test Movie"}])
def test_get_all_items_for_url(
    mock_fetch_list, mock_process_list, mock_extract_info, trakt_instance_and_mock
):
    trakt_instance, _ = trakt_instance_and_mock

    # Arrange
    trakt_config = {
        "max_items_per_list": 100,
        "lists": ["https://trakt.tv/users/username/lists/listname"],
    }

    # Act
    result = trakt_instance._get_all_items_for_url("movie", trakt_config)

    # Assert
    mock_extract_info.assert_called_once_with(
        "https://trakt.tv/users/username/lists/listname"
    )
    mock_fetch_list.assert_called_once_with(
        "movie", "username", "listname", "recurrence", 100
    )
    mock_process_list.assert_called_once()


@patch.object(
    Trakt, "_fetch_user_list_items", return_value=[{"title": "User List Movie"}]
)
@patch.object(
    Trakt,
    "_fetch_recurrent_list_items",
    return_value=[{"title": "Recurrent List Movie"}],
)
@patch.object(
    Trakt, "_fetch_general_list_items", return_value=[{"title": "General List Movie"}]
)
def test_fetch_list_items(
    mock_general, mock_recurrent, mock_user, trakt_instance_and_mock
):
    trakt_instance, _ = trakt_instance_and_mock

    # Act and Assert
    # Test with username and listname
    result = trakt_instance._fetch_list_items(
        "movie", "username", "listname", None, 100
    )
    assert result == [{"title": "User List Movie"}]
    mock_user.assert_called_once_with("movie", "username", "listname", 100)

    # Test with listname and recurrence
    result = trakt_instance._fetch_list_items(
        "movie", None, "listname", "recurrence", 100
    )
    assert result == [{"title": "Recurrent List Movie"}]
    mock_recurrent.assert_called_once_with("movie", "listname")

    # Test with only listname
    result = trakt_instance._fetch_list_items("movie", None, "listname", None, 100)
    assert result == [{"title": "General List Movie"}]
    mock_general.assert_called_once_with("movie", "listname", 100)

    # Test with no username, listname, or recurrence
    result = trakt_instance._fetch_list_items("movie", None, None, None, 100)
    assert result == []


def test_process_trakt_item_list():
    # Arrange
    items = {}
    list_items = [MagicMock(get_key=MagicMock(side_effect=[1]))]
    url = "https://trakt.tv/users/username/lists/listname"
    key = "movie"

    # Act
    _process_trakt_item_list(items, list_items, url, key)

    # Assert
    assert items == {1: {"trakt": list_items[0], "list": url}}


def test_process_trakt_item_list_TypeError():
    # Arrange
    items = {}
    list_items = [MagicMock(get_key=MagicMock(side_effect=TypeError("Test Error")))]
    url = "https://trakt.tv/users/username/lists/listname"
    key = "movie"

    # Act
    _process_trakt_item_list(items, list_items, url, key)

    # Assert
    assert items == {}


@pytest.mark.parametrize("media_type", ["movie", "show"])
def test__fetch_general_list_items(media_type, trakt_instance_and_mock):
    trakt_instance, trakt_mock = trakt_instance_and_mock

    # Act and Assert
    # Test with popular
    result = trakt_instance._fetch_general_list_items(media_type, "popular", 100)
    assert result == trakt_mock["{media_type}s"].popular.return_value
    trakt_mock["{media_type}s"].popular.assert_called_once_with(
        exceptions=True, per_page=100
    )

    # Test with trending
    result = trakt_instance._fetch_general_list_items(media_type, "trending", 100)
    assert result == trakt_mock["{media_type}s"].trending.return_value
    trakt_mock["{media_type}s"].trending.assert_called_once_with(
        exceptions=True, per_page=100
    )

    # Test with other list
    result = trakt_instance._fetch_general_list_items(media_type, "other", 100)
    assert result == []
