from unittest.mock import MagicMock, patch

import pytest
import requests

from app.modules.mdblist import Mdblist, _process_mdblist_item_list, extract_list_path


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://mdblist.com/lists/username/listname", "username/listname"),
        ("https://mdblist.com/lists/username/listname/", "username/listname"),
        ("https://mdblist.com/lists/user-name/my-list", "user-name/my-list"),
        ("https://mdblist.com/lists/user/list?sort=score", "user/list"),
        ("http://mdblist.com/lists/user/list", "user/list"),
        ("https://mdblist.com/", None),
        ("https://trakt.tv/users/user/lists/mylist", None),
        ("https://example.com", None),
        ("not-a-url", None),
    ],
)
def test_extract_list_path(url, expected):
    assert extract_list_path(url) == expected


@pytest.mark.parametrize("media_type", ["movie", "show"])
def test_get_all_items_for_url_valid_types(media_type):
    mdblist = Mdblist("test_api_key")
    mdblist._fetch_list_items = MagicMock(return_value=[
        {"id": 123, "tvdb_id": 456, "title": "Test Item"}
    ])

    config = {
        "max_items_per_list": 1000,
        "lists": ["https://mdblist.com/lists/user/mylist"],
    }

    result = mdblist.get_all_items_for_url(media_type, config)

    mdblist._fetch_list_items.assert_called_once_with(
        "https://mdblist.com/lists/user/mylist", media_type, 1000
    )
    assert len(result) == 1


def test_get_all_items_for_url_invalid_type():
    mdblist = Mdblist("test_api_key")
    with pytest.raises(ValueError, match="Invalid media type"):
        mdblist.get_all_items_for_url("invalid", {"lists": []})


@patch("app.modules.mdblist.requests.get")
def test_fetch_list_items_pagination(mock_get):
    """Test that pagination works with X-Has-More header."""
    mdblist = Mdblist("test_api_key")

    # First page: has more
    first_response = MagicMock()
    first_response.json.return_value = {
        "movies": [{"id": i, "title": f"Movie {i}"} for i in range(1000)],
        "shows": [],
    }
    first_response.headers = {"X-Has-More": "true"}
    first_response.raise_for_status = MagicMock()

    # Second page: no more
    second_response = MagicMock()
    second_response.json.return_value = {
        "movies": [{"id": 1001, "title": "Movie 1001"}],
        "shows": [],
    }
    second_response.headers = {"X-Has-More": "false"}
    second_response.raise_for_status = MagicMock()

    mock_get.side_effect = [first_response, second_response]

    result = mdblist._fetch_list_items("https://mdblist.com/lists/user/biglist", "movie", 2000)

    assert len(result) == 1001
    assert mock_get.call_count == 2

    # Verify pagination params
    first_call_params = mock_get.call_args_list[0][1]["params"]
    assert first_call_params["offset"] == 0
    assert first_call_params["limit"] == 1000

    second_call_params = mock_get.call_args_list[1][1]["params"]
    assert second_call_params["offset"] == 1000


@patch("app.modules.mdblist.requests.get")
def test_fetch_list_items_max_items(mock_get):
    """Test that max_items_per_list is respected."""
    mdblist = Mdblist("test_api_key")

    response = MagicMock()
    response.json.return_value = {
        "movies": [{"id": i, "title": f"Movie {i}"} for i in range(1000)],
        "shows": [],
    }
    response.headers = {"X-Has-More": "true"}
    response.raise_for_status = MagicMock()

    mock_get.return_value = response

    result = mdblist._fetch_list_items("https://mdblist.com/lists/user/list", "movie", 500)

    assert len(result) == 500
    # Should only make one request since first batch >= max_items
    assert mock_get.call_count == 1


def test_process_mdblist_item_list_movies():
    """Test indexing by tmdb id for movies (API 'id' field)."""
    items = {}
    list_items = [
        {"id": 123, "tvdb_id": 456, "title": "Movie 1"},
        {"id": 789, "tvdb_id": 101, "title": "Movie 2"},
    ]
    url = "https://mdblist.com/lists/user/mylist"

    _process_mdblist_item_list(items, list_items, url, "movie")

    assert 123 in items
    assert 789 in items
    assert items[123]["list"] == url
    assert items[123]["mdblist"]["title"] == "Movie 1"


def test_process_mdblist_item_list_shows():
    """Test indexing by tvdb_id for shows."""
    items = {}
    list_items = [
        {"id": 123, "tvdb_id": 456, "title": "Show 1"},
        {"id": 789, "tvdb_id": 101, "title": "Show 2"},
    ]
    url = "https://mdblist.com/lists/user/mylist"

    _process_mdblist_item_list(items, list_items, url, "show")

    assert 456 in items
    assert 101 in items
    assert items[456]["list"] == url
    assert items[456]["mdblist"]["title"] == "Show 1"


def test_process_mdblist_item_list_missing_id():
    """Test that items without the expected ID are skipped."""
    items = {}
    list_items = [
        {"title": "No IDs"},  # No id or tvdb_id
        {"id": 123, "title": "Has ID"},
    ]
    url = "https://mdblist.com/lists/user/mylist"

    _process_mdblist_item_list(items, list_items, url, "movie")

    assert len(items) == 1
    assert 123 in items


def test_process_mdblist_item_list_show_missing_tvdbid():
    """Test that show items without tvdb_id are skipped."""
    items = {}
    list_items = [
        {"id": 123, "title": "No TVDB ID"},  # Has id but no tvdb_id
        {"id": 456, "tvdb_id": 789, "title": "Has Both"},
    ]
    url = "https://mdblist.com/lists/user/mylist"

    _process_mdblist_item_list(items, list_items, url, "show")

    assert len(items) == 1
    assert 789 in items


@patch("app.modules.mdblist.requests.get")
def test_fetch_list_items_error_handling(mock_get):
    """Test that network errors are handled gracefully."""
    mdblist = Mdblist("test_api_key")

    mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")

    result = mdblist._fetch_list_items("https://mdblist.com/lists/user/list", "movie", 1000)

    assert result == []


@patch("app.modules.mdblist.requests.get")
def test_fetch_list_items_http_error(mock_get):
    """Test that HTTP errors (e.g., rate limiting) are handled gracefully."""
    mdblist = Mdblist("test_api_key")

    response = MagicMock()
    response.raise_for_status.side_effect = requests.exceptions.HTTPError("429 Too Many Requests")
    mock_get.return_value = response

    result = mdblist._fetch_list_items("https://mdblist.com/lists/user/list", "movie", 1000)

    assert result == []


def test_fetch_list_items_invalid_url():
    """Test that invalid URLs return empty list."""
    mdblist = Mdblist("test_api_key")

    result = mdblist._fetch_list_items("https://example.com/not-mdblist", "movie", 1000)

    assert result == []


@patch("app.modules.mdblist.requests.get")
def test_fetch_list_items_empty_response(mock_get):
    """Test that empty API response stops pagination."""
    mdblist = Mdblist("test_api_key")

    response = MagicMock()
    response.json.return_value = {"movies": [], "shows": []}
    response.headers = {"X-Has-More": "false"}
    response.raise_for_status = MagicMock()
    mock_get.return_value = response

    result = mdblist._fetch_list_items("https://mdblist.com/lists/user/list", "movie", 1000)

    assert result == []
    assert mock_get.call_count == 1


def test_process_mdblist_item_list_uses_ids_fallback():
    """Test that nested 'ids.tmdb' field is used as fallback for movies."""
    items = {}
    list_items = [
        {"ids": {"tmdb": 999}, "title": "Movie with nested ids only"},
    ]
    url = "https://mdblist.com/lists/user/mylist"

    _process_mdblist_item_list(items, list_items, url, "movie")

    assert 999 in items


def test_process_mdblist_item_list_shows_uses_ids_fallback():
    """Test that nested 'ids.tvdb' field is used as fallback for shows."""
    items = {}
    list_items = [
        {"ids": {"tvdb": 888}, "title": "Show with nested ids only"},
    ]
    url = "https://mdblist.com/lists/user/mylist"

    _process_mdblist_item_list(items, list_items, url, "show")

    assert 888 in items


@patch("app.modules.mdblist.requests.get")
def test_fetch_list_items_dict_response(mock_get):
    """Test that dict response format (real API) is handled correctly."""
    mdblist = Mdblist("test_api_key")

    response = MagicMock()
    response.json.return_value = {
        "movies": [
            {"id": 917496, "title": "Test Movie", "imdb_id": "tt2049403", "tvdb_id": None},
        ],
        "shows": [
            {"id": 258902, "title": "Test Show", "imdb_id": "tt20782190", "tvdb_id": 421968},
        ],
    }
    response.headers = {"X-Has-More": "false"}
    response.raise_for_status = MagicMock()
    mock_get.return_value = response

    # Fetch movies
    movies = mdblist._fetch_list_items("https://mdblist.com/lists/user/list", "movie", 1000)
    assert len(movies) == 1
    assert movies[0]["id"] == 917496

    # Fetch shows
    mock_get.reset_mock()
    mock_get.return_value = response
    shows = mdblist._fetch_list_items("https://mdblist.com/lists/user/list", "show", 1000)
    assert len(shows) == 1
    assert shows[0]["tvdb_id"] == 421968


@patch("app.modules.mdblist.requests.get")
def test_fetch_list_items_show_pagination(mock_get):
    """Test pagination for shows uses the 'shows' key."""
    mdblist = Mdblist("test_api_key")

    first_response = MagicMock()
    first_response.json.return_value = {
        "movies": [],
        "shows": [{"id": i, "tvdb_id": i + 1000, "title": f"Show {i}"} for i in range(5)],
    }
    first_response.headers = {"X-Has-More": "false"}
    first_response.raise_for_status = MagicMock()

    mock_get.return_value = first_response

    result = mdblist._fetch_list_items("https://mdblist.com/lists/user/list", "show", 1000)

    assert len(result) == 5
    assert result[0]["tvdb_id"] == 1000
