import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.modules.plex_watch_provider import PlexWatchProvider
from app.modules.watch_provider import WatchDataProvider


@pytest.fixture
def mock_plex_server():
    with patch("app.modules.plex_watch_provider.PlexServer") as mock_cls:
        mock_server = MagicMock()
        mock_cls.return_value = mock_server
        yield mock_server


@pytest.fixture
def provider(mock_plex_server):
    return PlexWatchProvider("http://localhost:32400", "test_token")


class TestPlexWatchProviderProtocol:
    def test_plex_satisfies_protocol(self, provider):
        """PlexWatchProvider instance is recognized as a WatchDataProvider."""
        assert isinstance(provider, WatchDataProvider)


class TestTestConnection:
    def test_test_connection(self, provider, mock_plex_server):
        """test_connection calls plex.library.sections()."""
        provider.test_connection()
        mock_plex_server.library.sections.assert_called_once()


class TestRefreshLibrary:
    def test_refresh_library(self, provider, mock_plex_server):
        """refresh_library calls sectionByID().refresh()."""
        provider.refresh_library("1")
        mock_plex_server.library.sectionByID.assert_called_once_with(1)
        mock_plex_server.library.sectionByID.return_value.refresh.assert_called_once()


class TestGetActivity:
    def _make_movie_item(self, guid, rating_key, title, year, viewed_at):
        item = MagicMock()
        item.type = "movie"
        item.guid = guid
        item.ratingKey = rating_key
        item.title = title
        item.year = year
        item.viewedAt = viewed_at
        return item

    def _make_episode_item(
        self, guid, grandparent_rating_key, grandparent_title, year, viewed_at
    ):
        item = MagicMock()
        item.type = "episode"
        item.guid = guid
        item.grandparentRatingKey = grandparent_rating_key
        item.grandparentTitle = grandparent_title
        item.grandparentYear = year
        item.year = year
        item.viewedAt = viewed_at
        return item

    def test_get_activity_movies(self, provider, mock_plex_server):
        """Movie history is keyed by GUID and ratingKey."""
        viewed = datetime(2024, 6, 15, 12, 0, 0)
        movie = self._make_movie_item(
            "plex://movie/abc", 100, "Test Movie", 2020, viewed
        )
        mock_plex_server.history.return_value = [movie]

        result = provider.get_activity("1")

        assert "plex://movie/abc" in result
        assert "100" in result
        assert result["plex://movie/abc"]["title"] == "Test Movie"
        assert result["plex://movie/abc"]["year"] == 2020

    def test_get_activity_tv_shows(self, provider, mock_plex_server):
        """Episode history is keyed by GUID and grandparentRatingKey."""
        viewed = datetime(2024, 6, 15, 12, 0, 0)
        episode = self._make_episode_item(
            "plex://episode/xyz", 200, "Test Show", 2019, viewed
        )
        mock_plex_server.history.return_value = [episode]

        result = provider.get_activity("1")

        assert "plex://episode/xyz" in result
        assert "200" in result
        assert result["200"]["title"] == "Test Show"
        assert result["200"]["year"] == 2019

    def test_get_activity_keeps_most_recent(self, provider, mock_plex_server):
        """When the same key appears multiple times, keep the most recent."""
        older = datetime(2024, 1, 1, 0, 0, 0)
        newer = datetime(2024, 6, 15, 12, 0, 0)

        movie_old = self._make_movie_item(
            "plex://movie/abc", 100, "Test Movie", 2020, older
        )
        movie_new = self._make_movie_item(
            "plex://movie/abc", 100, "Test Movie", 2020, newer
        )
        mock_plex_server.history.return_value = [movie_old, movie_new]

        result = provider.get_activity("1")

        expected_ts = int(newer.timestamp())
        assert result["plex://movie/abc"]["last_watched"] == expected_ts

    def test_get_activity_empty(self, provider, mock_plex_server):
        """Empty history returns empty dict."""
        mock_plex_server.history.return_value = []

        result = provider.get_activity("1")

        assert result == {}


class TestHasUserWatched:
    def _setup_accounts(self, mock_plex_server, accounts):
        """Set up mock system accounts."""
        mock_accounts = []
        for name, account_id in accounts:
            account = MagicMock()
            account.name = name
            account.id = account_id
            mock_accounts.append(account)
        mock_plex_server.systemAccounts.return_value = mock_accounts

    def test_has_user_watched_found(self, provider, mock_plex_server):
        """Returns True when user has watched the item."""
        self._setup_accounts(mock_plex_server, [("testuser", 42)])
        mock_plex_server.history.return_value = [MagicMock()]

        result = provider.has_user_watched("1", "100", None, "testuser")

        assert result is True
        mock_plex_server.history.assert_called_once_with(
            librarySectionID=1,
            ratingKey=100,
            accountID=42,
            maxresults=1,
        )

    def test_has_user_watched_not_found(self, provider, mock_plex_server):
        """Returns False when user has not watched the item."""
        self._setup_accounts(mock_plex_server, [("testuser", 42)])
        mock_plex_server.history.return_value = []

        result = provider.has_user_watched("1", "100", None, "testuser")

        assert result is False

    def test_has_user_watched_unknown_user(self, provider, mock_plex_server):
        """Returns False for unknown username."""
        self._setup_accounts(mock_plex_server, [("otheruser", 99)])

        result = provider.has_user_watched("1", "100", None, "unknown_user")

        assert result is False

    def test_has_user_watched_uses_grandparent_key(self, provider, mock_plex_server):
        """Uses grandparent_rating_key for TV shows."""
        self._setup_accounts(mock_plex_server, [("testuser", 42)])
        mock_plex_server.history.return_value = [MagicMock()]

        provider.has_user_watched("1", "100", "200", "testuser")

        mock_plex_server.history.assert_called_once_with(
            librarySectionID=1,
            ratingKey=200,
            accountID=42,
            maxresults=1,
        )

    def test_has_user_watched_empty_user(self, provider, mock_plex_server):
        """Returns False for empty user string."""
        result = provider.has_user_watched("1", "100", None, "")
        assert result is False

    def test_has_user_watched_no_key(self, provider, mock_plex_server):
        """Returns False when both rating_key and grandparent_rating_key are None."""
        result = provider.has_user_watched("1", None, None, "testuser")
        assert result is False
