import pytest
from app.modules.trakt import extract_info_from_url

@pytest.mark.parametrize("url, expected_result", [
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
    ("https://trakt.tv/users/johndoe/lists/customlist", ("johndoe", "customlist", None)),
    
    # Test for invalid URL
    ("https://invalid.url", (None, None, None)),
])
def test_extract_info_from_url(url, expected_result):
    assert extract_info_from_url(url) == expected_result