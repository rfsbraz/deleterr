from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.modules.overseerr import (
    Overseerr,
    REQUEST_STATUS_PENDING,
    REQUEST_STATUS_APPROVED,
)


@pytest.mark.unit
class TestOverseerr:
    def test_init(self):
        """Test Overseerr initialization."""
        overseerr = Overseerr("http://localhost:5055", "test_api_key")

        assert overseerr.url == "http://localhost:5055"
        assert overseerr.api_key == "test_api_key"
        assert overseerr.ssl_verify is True
        assert overseerr._requests_cache == {}

    def test_init_url_trailing_slash(self):
        """Test that trailing slash is removed from URL."""
        overseerr = Overseerr("http://localhost:5055/", "test_api_key")

        assert overseerr.url == "http://localhost:5055"

    def test_init_none_url(self):
        """Test initialization with None URL."""
        overseerr = Overseerr(None, "test_api_key")

        assert overseerr.url is None

    @patch("app.modules.overseerr.requests.request")
    def test_test_connection_success(self, mock_request):
        """Test successful connection test."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"version": "1.33.0"}
        mock_response.content = b'{"version": "1.33.0"}'
        mock_request.return_value = mock_response

        overseerr = Overseerr("http://localhost:5055", "test_api_key")
        result = overseerr.test_connection()

        assert result is True
        mock_request.assert_called_once_with(
            "get",
            "http://localhost:5055/api/v1/status",
            headers={
                "X-Api-Key": "test_api_key",
                "Content-Type": "application/json",
            },
            verify=True,
            timeout=30,
        )

    @patch("app.modules.overseerr.requests.request")
    def test_test_connection_failure(self, mock_request):
        """Test failed connection test."""
        import requests as req
        mock_request.side_effect = req.exceptions.RequestException("Connection error")

        overseerr = Overseerr("http://localhost:5055", "test_api_key")
        result = overseerr.test_connection()

        assert result is False

    def test_test_connection_no_url(self):
        """Test connection test with no URL configured."""
        overseerr = Overseerr(None, "test_api_key")
        result = overseerr.test_connection()

        assert result is False

    @patch("app.modules.overseerr.requests.request")
    def test_get_all_requests(self, mock_request):
        """Test fetching all requests."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "id": 1,
                    "status": REQUEST_STATUS_APPROVED,
                    "type": "movie",
                    "media": {"id": 100, "tmdbId": 550},
                    "requestedBy": {"username": "testuser", "email": "test@example.com"},
                    "createdAt": "2024-01-01T00:00:00Z",
                },
                {
                    "id": 2,
                    "status": REQUEST_STATUS_PENDING,
                    "type": "movie",
                    "media": {"id": 101, "tmdbId": 551},
                    "requestedBy": {"username": "otheruser", "email": "other@example.com"},
                    "createdAt": "2024-01-02T00:00:00Z",
                },
            ],
            "pageInfo": {"pages": 1},
        }
        mock_response.content = b'{"results": []}'
        mock_request.return_value = mock_response

        overseerr = Overseerr("http://localhost:5055", "test_api_key")
        requests_data = overseerr.get_all_requests()

        assert 550 in requests_data
        assert 551 in requests_data
        assert requests_data[550]["status"] == REQUEST_STATUS_APPROVED
        assert requests_data[551]["status"] == REQUEST_STATUS_PENDING

    @patch("app.modules.overseerr.requests.request")
    def test_get_all_requests_caching(self, mock_request):
        """Test that requests are cached."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "id": 1,
                    "status": REQUEST_STATUS_APPROVED,
                    "type": "movie",
                    "media": {"id": 100, "tmdbId": 550},
                    "requestedBy": {},
                    "createdAt": "2024-01-01T00:00:00Z",
                },
            ],
            "pageInfo": {"pages": 1},
        }
        mock_response.content = b'{"results": []}'
        mock_request.return_value = mock_response

        overseerr = Overseerr("http://localhost:5055", "test_api_key")

        # First call
        overseerr.get_all_requests()
        # Second call - should use cache
        overseerr.get_all_requests()

        # API should only be called once due to caching
        assert mock_request.call_count == 1

    @patch.object(Overseerr, "get_all_requests")
    def test_is_requested_true(self, mock_get_requests):
        """Test is_requested returns True when media is requested."""
        mock_get_requests.return_value = {
            550: {"status": REQUEST_STATUS_APPROVED}
        }

        overseerr = Overseerr("http://localhost:5055", "test_api_key")
        result = overseerr.is_requested(550)

        assert result is True

    @patch.object(Overseerr, "get_all_requests")
    def test_is_requested_false(self, mock_get_requests):
        """Test is_requested returns False when media is not requested."""
        mock_get_requests.return_value = {}

        overseerr = Overseerr("http://localhost:5055", "test_api_key")
        result = overseerr.is_requested(550)

        assert result is False

    @patch.object(Overseerr, "get_all_requests")
    def test_is_requested_exclude_pending(self, mock_get_requests):
        """Test is_requested with include_pending=False."""
        mock_get_requests.return_value = {
            550: {"status": REQUEST_STATUS_PENDING}
        }

        overseerr = Overseerr("http://localhost:5055", "test_api_key")

        # With include_pending=True (default)
        assert overseerr.is_requested(550, include_pending=True) is True

        # With include_pending=False
        assert overseerr.is_requested(550, include_pending=False) is False

    @patch.object(Overseerr, "get_all_requests")
    def test_is_requested_by_username(self, mock_get_requests):
        """Test is_requested_by with username match."""
        mock_get_requests.return_value = {
            550: {
                "status": REQUEST_STATUS_APPROVED,
                "requested_by": {"username": "testuser", "email": "test@example.com"},
            }
        }

        overseerr = Overseerr("http://localhost:5055", "test_api_key")

        # Match by username
        assert overseerr.is_requested_by(550, ["testuser"]) is True
        # Case insensitive
        assert overseerr.is_requested_by(550, ["TESTUSER"]) is True
        # No match
        assert overseerr.is_requested_by(550, ["otheruser"]) is False

    @patch.object(Overseerr, "get_all_requests")
    def test_is_requested_by_email(self, mock_get_requests):
        """Test is_requested_by with email match."""
        mock_get_requests.return_value = {
            550: {
                "status": REQUEST_STATUS_APPROVED,
                "requested_by": {"username": "testuser", "email": "test@example.com"},
            }
        }

        overseerr = Overseerr("http://localhost:5055", "test_api_key")

        # Match by email
        assert overseerr.is_requested_by(550, ["test@example.com"]) is True

    @patch.object(Overseerr, "get_all_requests")
    def test_is_requested_by_plex_username(self, mock_get_requests):
        """Test is_requested_by with Plex username match."""
        mock_get_requests.return_value = {
            550: {
                "status": REQUEST_STATUS_APPROVED,
                "requested_by": {
                    "username": "testuser",
                    "email": "test@example.com",
                    "plexUsername": "PlexUser",
                },
            }
        }

        overseerr = Overseerr("http://localhost:5055", "test_api_key")

        # Match by Plex username
        assert overseerr.is_requested_by(550, ["plexuser"]) is True

    @patch.object(Overseerr, "get_all_requests")
    def test_is_requested_by_no_users(self, mock_get_requests):
        """Test is_requested_by with no users falls back to is_requested."""
        mock_get_requests.return_value = {
            550: {"status": REQUEST_STATUS_APPROVED}
        }

        overseerr = Overseerr("http://localhost:5055", "test_api_key")

        # Empty users list should check any request
        assert overseerr.is_requested_by(550, []) is True
        assert overseerr.is_requested_by(550, None) is True

    @patch.object(Overseerr, "get_all_requests")
    def test_is_requested_by_exclude_pending(self, mock_get_requests):
        """Test is_requested_by with include_pending=False."""
        mock_get_requests.return_value = {
            550: {
                "status": REQUEST_STATUS_PENDING,
                "requested_by": {"username": "testuser", "email": "test@example.com"},
            }
        }

        overseerr = Overseerr("http://localhost:5055", "test_api_key")

        # With include_pending=True (default)
        assert overseerr.is_requested_by(550, ["testuser"], include_pending=True) is True

        # With include_pending=False
        assert overseerr.is_requested_by(550, ["testuser"], include_pending=False) is False

    @patch.object(Overseerr, "get_all_requests")
    def test_get_request_status(self, mock_get_requests):
        """Test getting request status."""
        mock_get_requests.return_value = {
            550: {"status": REQUEST_STATUS_APPROVED}
        }

        overseerr = Overseerr("http://localhost:5055", "test_api_key")

        assert overseerr.get_request_status(550) == REQUEST_STATUS_APPROVED
        assert overseerr.get_request_status(999) is None

    @patch.object(Overseerr, "get_all_requests")
    def test_get_request_data(self, mock_get_requests):
        """Test getting full request data."""
        request_data = {
            "request_id": 1,
            "status": REQUEST_STATUS_APPROVED,
            "media_type": "movie",
            "requested_by": {"username": "testuser"},
            "created_at": "2024-01-01T00:00:00Z",
            "media_id": 100,
        }
        mock_get_requests.return_value = {550: request_data}

        overseerr = Overseerr("http://localhost:5055", "test_api_key")

        result = overseerr.get_request_data(550)
        assert result == request_data

        # Non-existent media
        assert overseerr.get_request_data(999) is None

    @patch("app.modules.overseerr.requests.request")
    @patch.object(Overseerr, "get_all_requests")
    def test_mark_as_deleted_success(self, mock_get_requests, mock_request):
        """Test successful mark_as_deleted."""
        mock_get_requests.return_value = {
            550: {"media_id": 100}
        }
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.content = b'{}'
        mock_request.return_value = mock_response

        overseerr = Overseerr("http://localhost:5055", "test_api_key")
        result = overseerr.mark_as_deleted(550, "movie")

        assert result is True
        # Verify the DELETE request was made
        calls = mock_request.call_args_list
        delete_call = [c for c in calls if c[0][0] == "delete"]
        assert len(delete_call) == 1
        assert "/media/100" in delete_call[0][0][1]

    @patch("app.modules.overseerr.requests.request")
    @patch.object(Overseerr, "get_all_requests")
    def test_mark_as_deleted_no_media_id(self, mock_get_requests, mock_request):
        """Test mark_as_deleted when media ID not found."""
        mock_get_requests.return_value = {}

        # Mock the movie lookup to also fail
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.content = b'{}'
        mock_request.return_value = mock_response

        overseerr = Overseerr("http://localhost:5055", "test_api_key")
        result = overseerr.mark_as_deleted(999, "movie")

        assert result is False

    @patch.object(Overseerr, "get_all_requests")
    def test_clear_cache(self, mock_get_requests):
        """Test cache clearing."""
        mock_get_requests.return_value = {550: {}}

        overseerr = Overseerr("http://localhost:5055", "test_api_key")

        # Populate cache
        overseerr._requests_cache = {550: {}}
        overseerr._media_cache = {550: {}}

        # Clear cache
        overseerr.clear_cache()

        assert overseerr._requests_cache == {}
        assert overseerr._media_cache == {}


@pytest.mark.unit
class TestCheckExcludedOverseerr:
    """Test the check_excluded_overseerr function."""

    def test_no_config(self):
        """Test with no overseerr config."""
        from app.media_cleaner import check_excluded_overseerr

        media_data = {"title": "Test Movie", "tmdbId": 550}
        plex_item = MagicMock()
        exclude = {}

        result = check_excluded_overseerr(media_data, plex_item, exclude, None)

        assert result is True

    def test_no_overseerr_instance(self):
        """Test with config but no overseerr instance."""
        from app.media_cleaner import check_excluded_overseerr

        media_data = {"title": "Test Movie", "tmdbId": 550}
        plex_item = MagicMock()
        exclude = {"overseerr": {"mode": "exclude"}}

        result = check_excluded_overseerr(media_data, plex_item, exclude, None)

        assert result is True

    def test_no_tmdb_id(self):
        """Test with no TMDB ID in media data."""
        from app.media_cleaner import check_excluded_overseerr

        media_data = {"title": "Test Movie"}
        plex_item = MagicMock()
        exclude = {"overseerr": {"mode": "exclude"}}
        overseerr = MagicMock()

        result = check_excluded_overseerr(media_data, plex_item, exclude, overseerr)

        assert result is True

    def test_exclude_mode_requested(self):
        """Test exclude mode with requested media."""
        from app.media_cleaner import check_excluded_overseerr

        media_data = {"title": "Test Movie", "tmdbId": 550}
        plex_item = MagicMock()
        exclude = {"overseerr": {"mode": "exclude"}}
        overseerr = MagicMock()
        overseerr.is_requested.return_value = True
        overseerr.get_request_data.return_value = {"status": REQUEST_STATUS_APPROVED}

        result = check_excluded_overseerr(media_data, plex_item, exclude, overseerr)

        assert result is False  # Should be excluded (skipped)

    def test_exclude_mode_not_requested(self):
        """Test exclude mode with non-requested media."""
        from app.media_cleaner import check_excluded_overseerr

        media_data = {"title": "Test Movie", "tmdbId": 550}
        plex_item = MagicMock()
        exclude = {"overseerr": {"mode": "exclude"}}
        overseerr = MagicMock()
        overseerr.is_requested.return_value = False
        overseerr.get_request_data.return_value = None

        result = check_excluded_overseerr(media_data, plex_item, exclude, overseerr)

        assert result is True  # Should NOT be excluded (actionable)

    def test_include_only_mode_requested(self):
        """Test include_only mode with requested media."""
        from app.media_cleaner import check_excluded_overseerr

        media_data = {"title": "Test Movie", "tmdbId": 550}
        plex_item = MagicMock()
        exclude = {"overseerr": {"mode": "include_only"}}
        overseerr = MagicMock()
        overseerr.is_requested.return_value = True
        overseerr.get_request_data.return_value = {"status": REQUEST_STATUS_APPROVED}

        result = check_excluded_overseerr(media_data, plex_item, exclude, overseerr)

        assert result is True  # Should NOT be excluded (actionable)

    def test_include_only_mode_not_requested(self):
        """Test include_only mode with non-requested media."""
        from app.media_cleaner import check_excluded_overseerr

        media_data = {"title": "Test Movie", "tmdbId": 550}
        plex_item = MagicMock()
        exclude = {"overseerr": {"mode": "include_only"}}
        overseerr = MagicMock()
        overseerr.is_requested.return_value = False
        overseerr.get_request_data.return_value = None

        result = check_excluded_overseerr(media_data, plex_item, exclude, overseerr)

        assert result is False  # Should be excluded (skipped)

    def test_exclude_mode_with_users(self):
        """Test exclude mode with specific users."""
        from app.media_cleaner import check_excluded_overseerr

        media_data = {"title": "Test Movie", "tmdbId": 550}
        plex_item = MagicMock()
        exclude = {"overseerr": {"mode": "exclude", "users": ["testuser"]}}
        overseerr = MagicMock()
        overseerr.is_requested_by.return_value = True
        overseerr.get_request_data.return_value = {"status": REQUEST_STATUS_APPROVED}

        result = check_excluded_overseerr(media_data, plex_item, exclude, overseerr)

        assert result is False  # Should be excluded
        overseerr.is_requested_by.assert_called_once_with(550, ["testuser"], True)

    def test_include_pending_false(self):
        """Test with include_pending=False."""
        from app.media_cleaner import check_excluded_overseerr

        media_data = {"title": "Test Movie", "tmdbId": 550}
        plex_item = MagicMock()
        exclude = {"overseerr": {"mode": "exclude", "include_pending": False}}
        overseerr = MagicMock()
        overseerr.is_requested.return_value = True
        overseerr.get_request_data.return_value = {"status": REQUEST_STATUS_APPROVED}

        result = check_excluded_overseerr(media_data, plex_item, exclude, overseerr)

        overseerr.is_requested.assert_called_once_with(550, False)

    def test_request_status_filter_approved_only(self):
        """Test filtering by request status (approved only)."""
        from app.media_cleaner import check_excluded_overseerr

        media_data = {"title": "Test Movie", "tmdbId": 550}
        plex_item = MagicMock()
        exclude = {"overseerr": {"mode": "exclude", "request_status": ["approved"]}}
        overseerr = MagicMock()
        overseerr.is_requested.return_value = True
        overseerr.get_request_data.return_value = {"status": REQUEST_STATUS_APPROVED}

        result = check_excluded_overseerr(media_data, plex_item, exclude, overseerr)

        # Should be excluded because it's approved
        assert result is False

    def test_request_status_filter_no_match(self):
        """Test filtering by request status that doesn't match."""
        from app.media_cleaner import check_excluded_overseerr

        media_data = {"title": "Test Movie", "tmdbId": 550}
        plex_item = MagicMock()
        exclude = {"overseerr": {"mode": "exclude", "request_status": ["approved"]}}
        overseerr = MagicMock()
        overseerr.is_requested.return_value = True
        overseerr.get_request_data.return_value = {"status": REQUEST_STATUS_PENDING}

        result = check_excluded_overseerr(media_data, plex_item, exclude, overseerr)

        # Should NOT be excluded because it's pending, not approved
        assert result is True

    def test_min_request_age_days_old_request(self):
        """Test filtering by minimum request age with old request."""
        from app.media_cleaner import check_excluded_overseerr
        from datetime import datetime, timedelta, timezone

        media_data = {"title": "Test Movie", "tmdbId": 550}
        plex_item = MagicMock()
        exclude = {"overseerr": {"mode": "include_only", "min_request_age_days": 30}}
        overseerr = MagicMock()

        # Request is 60 days old (older than 30 day threshold)
        old_date = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        overseerr.get_request_data.return_value = {
            "created_at": old_date,
            "status": REQUEST_STATUS_APPROVED,
        }
        overseerr.is_requested.return_value = True

        result = check_excluded_overseerr(media_data, plex_item, exclude, overseerr)

        # Should be actionable (request is old enough for include_only mode)
        assert result is True

    def test_min_request_age_days_recent_request(self):
        """Test filtering by minimum request age with recent request."""
        from app.media_cleaner import check_excluded_overseerr
        from datetime import datetime, timedelta, timezone

        media_data = {"title": "Test Movie", "tmdbId": 550}
        plex_item = MagicMock()
        exclude = {"overseerr": {"mode": "include_only", "min_request_age_days": 30}}
        overseerr = MagicMock()

        # Request is 10 days old (not older than 30 day threshold)
        recent_date = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        overseerr.get_request_data.return_value = {
            "created_at": recent_date,
            "status": REQUEST_STATUS_APPROVED,
        }
        overseerr.is_requested.return_value = True

        result = check_excluded_overseerr(media_data, plex_item, exclude, overseerr)

        # Should NOT be actionable (request is too recent for include_only mode)
        assert result is False

    def test_request_status_and_min_age_combined(self):
        """Test combining request_status and min_request_age_days filters."""
        from app.media_cleaner import check_excluded_overseerr
        from datetime import datetime, timedelta, timezone

        media_data = {"title": "Test Movie", "tmdbId": 550}
        plex_item = MagicMock()
        exclude = {
            "overseerr": {
                "mode": "include_only",
                "request_status": ["approved"],
                "min_request_age_days": 30,
            }
        }
        overseerr = MagicMock()

        # Request is approved and 60 days old - should match both filters
        old_date = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        overseerr.get_request_data.return_value = {
            "created_at": old_date,
            "status": REQUEST_STATUS_APPROVED,
        }
        overseerr.is_requested.return_value = True

        result = check_excluded_overseerr(media_data, plex_item, exclude, overseerr)

        # Should be actionable (approved AND old enough)
        assert result is True


@pytest.mark.unit
class TestUpdateOverseerrStatus:
    """Test the _update_overseerr_status method in MediaCleaner."""

    def test_update_status_disabled(self):
        """Test that status update is skipped when update_status is False."""
        with patch("app.media_cleaner.Tautulli"), \
             patch("app.media_cleaner.PlexServer"), \
             patch("app.media_cleaner.Trakt"):
            from app.media_cleaner import MediaCleaner

            mock_config = MagicMock()
            mock_config.settings = {
                "tautulli": {"url": "http://localhost", "api_key": "key"},
                "plex": {"url": "http://localhost", "token": "token"},
                "overseerr": {"url": "http://localhost:5055", "api_key": "key"},
            }

            cleaner = MediaCleaner(mock_config)
            cleaner.overseerr = MagicMock()

            library = {"exclude": {"overseerr": {"update_status": False}}}
            media_data = {"title": "Test Movie", "tmdbId": 550}

            cleaner._update_overseerr_status(library, media_data, "movie")

            # mark_as_deleted should NOT be called
            cleaner.overseerr.mark_as_deleted.assert_not_called()

    def test_update_status_enabled(self):
        """Test that status update is called when update_status is True."""
        with patch("app.media_cleaner.Tautulli"), \
             patch("app.media_cleaner.PlexServer"), \
             patch("app.media_cleaner.Trakt"):
            from app.media_cleaner import MediaCleaner

            mock_config = MagicMock()
            mock_config.settings = {
                "tautulli": {"url": "http://localhost", "api_key": "key"},
                "plex": {"url": "http://localhost", "token": "token"},
                "overseerr": {"url": "http://localhost:5055", "api_key": "key"},
            }

            cleaner = MediaCleaner(mock_config)
            cleaner.overseerr = MagicMock()
            cleaner.overseerr.mark_as_deleted.return_value = True

            library = {"exclude": {"overseerr": {"update_status": True}}}
            media_data = {"title": "Test Movie", "tmdbId": 550}

            cleaner._update_overseerr_status(library, media_data, "movie")

            cleaner.overseerr.mark_as_deleted.assert_called_once_with(550, "movie")

    def test_update_status_no_tmdb_id(self):
        """Test that status update is skipped when media has no TMDB ID."""
        with patch("app.media_cleaner.Tautulli"), \
             patch("app.media_cleaner.PlexServer"), \
             patch("app.media_cleaner.Trakt"):
            from app.media_cleaner import MediaCleaner

            mock_config = MagicMock()
            mock_config.settings = {
                "tautulli": {"url": "http://localhost", "api_key": "key"},
                "plex": {"url": "http://localhost", "token": "token"},
                "overseerr": {"url": "http://localhost:5055", "api_key": "key"},
            }

            cleaner = MediaCleaner(mock_config)
            cleaner.overseerr = MagicMock()

            library = {"exclude": {"overseerr": {"update_status": True}}}
            media_data = {"title": "Test Movie"}  # No tmdbId

            cleaner._update_overseerr_status(library, media_data, "movie")

            cleaner.overseerr.mark_as_deleted.assert_not_called()

    def test_update_status_no_overseerr_instance(self):
        """Test that status update is skipped when Overseerr is not configured."""
        with patch("app.media_cleaner.Tautulli"), \
             patch("app.media_cleaner.PlexServer"), \
             patch("app.media_cleaner.Trakt"):
            from app.media_cleaner import MediaCleaner

            mock_config = MagicMock()
            mock_config.settings = {
                "tautulli": {"url": "http://localhost", "api_key": "key"},
                "plex": {"url": "http://localhost", "token": "token"},
            }

            cleaner = MediaCleaner(mock_config)
            # overseerr should be None when not configured

            library = {"exclude": {"overseerr": {"update_status": True}}}
            media_data = {"title": "Test Movie", "tmdbId": 550}

            # Should not raise an exception
            cleaner._update_overseerr_status(library, media_data, "movie")

    def test_update_status_handles_failure(self):
        """Test that status update handles API failures gracefully."""
        with patch("app.media_cleaner.Tautulli"), \
             patch("app.media_cleaner.PlexServer"), \
             patch("app.media_cleaner.Trakt"):
            from app.media_cleaner import MediaCleaner

            mock_config = MagicMock()
            mock_config.settings = {
                "tautulli": {"url": "http://localhost", "api_key": "key"},
                "plex": {"url": "http://localhost", "token": "token"},
                "overseerr": {"url": "http://localhost:5055", "api_key": "key"},
            }

            cleaner = MediaCleaner(mock_config)
            cleaner.overseerr = MagicMock()
            cleaner.overseerr.mark_as_deleted.return_value = False  # Simulate failure

            library = {"exclude": {"overseerr": {"update_status": True}}}
            media_data = {"title": "Test Movie", "tmdbId": 550}

            # Should not raise an exception
            cleaner._update_overseerr_status(library, media_data, "movie")

            cleaner.overseerr.mark_as_deleted.assert_called_once()

    def test_update_status_handles_exception(self):
        """Test that status update handles exceptions gracefully."""
        with patch("app.media_cleaner.Tautulli"), \
             patch("app.media_cleaner.PlexServer"), \
             patch("app.media_cleaner.Trakt"):
            from app.media_cleaner import MediaCleaner

            mock_config = MagicMock()
            mock_config.settings = {
                "tautulli": {"url": "http://localhost", "api_key": "key"},
                "plex": {"url": "http://localhost", "token": "token"},
                "overseerr": {"url": "http://localhost:5055", "api_key": "key"},
            }

            cleaner = MediaCleaner(mock_config)
            cleaner.overseerr = MagicMock()
            cleaner.overseerr.mark_as_deleted.side_effect = Exception("API Error")

            library = {"exclude": {"overseerr": {"update_status": True}}}
            media_data = {"title": "Test Movie", "tmdbId": 550}

            # Should not raise an exception - handled gracefully
            cleaner._update_overseerr_status(library, media_data, "movie")


@pytest.mark.unit
class TestResolveTautulliUsername:
    """Test the _resolve_tautulli_username helper function."""

    def test_manual_mapping_by_username(self):
        """Manual mapping matches by Overseerr username."""
        from app.media_cleaner import _resolve_tautulli_username

        request_data = {
            "requested_by": {"username": "john", "plexUsername": "john_plex", "email": "john@test.com"}
        }
        result = _resolve_tautulli_username(request_data, {"john": "john_tautulli"})
        assert result == "john_tautulli"

    def test_manual_mapping_by_email(self):
        """Manual mapping matches by email."""
        from app.media_cleaner import _resolve_tautulli_username

        request_data = {
            "requested_by": {"username": "john", "plexUsername": "", "email": "john@test.com"}
        }
        result = _resolve_tautulli_username(request_data, {"john@test.com": "john_tautulli"})
        assert result == "john_tautulli"

    def test_manual_mapping_by_plex_username(self):
        """Manual mapping matches by plexUsername."""
        from app.media_cleaner import _resolve_tautulli_username

        request_data = {
            "requested_by": {"username": "john", "plexUsername": "john_plex", "email": ""}
        }
        result = _resolve_tautulli_username(request_data, {"john_plex": "john_tautulli"})
        assert result == "john_tautulli"

    def test_manual_mapping_case_insensitive(self):
        """Manual mapping is case-insensitive."""
        from app.media_cleaner import _resolve_tautulli_username

        request_data = {
            "requested_by": {"username": "John", "plexUsername": "", "email": ""}
        }
        result = _resolve_tautulli_username(request_data, {"john": "john_tautulli"})
        assert result == "john_tautulli"

    def test_auto_match_via_plex_username(self):
        """Auto-matches via plexUsername when no manual mapping."""
        from app.media_cleaner import _resolve_tautulli_username

        request_data = {
            "requested_by": {"username": "john", "plexUsername": "john_plex", "email": ""}
        }
        result = _resolve_tautulli_username(request_data, {})
        assert result == "john_plex"

    def test_fallback_to_overseerr_username(self):
        """Falls back to Overseerr username when no plexUsername."""
        from app.media_cleaner import _resolve_tautulli_username

        request_data = {
            "requested_by": {"username": "john", "plexUsername": "", "email": ""}
        }
        result = _resolve_tautulli_username(request_data, {})
        assert result == "john"

    def test_no_match_returns_none(self):
        """Returns None when no identifiers available."""
        from app.media_cleaner import _resolve_tautulli_username

        request_data = {
            "requested_by": {"username": "", "plexUsername": "", "email": ""}
        }
        result = _resolve_tautulli_username(request_data, {})
        assert result is None

    def test_no_requested_by(self):
        """Returns None when no requested_by data."""
        from app.media_cleaner import _resolve_tautulli_username

        result = _resolve_tautulli_username({}, {})
        assert result is None


@pytest.mark.unit
class TestCheckExcludedOverseerrRequesterWatch:
    """Test the check_excluded_overseerr_requester_watch function."""

    def test_no_config_returns_true(self):
        """No config means not excluded (actionable)."""
        from app.media_cleaner import check_excluded_overseerr_requester_watch

        result = check_excluded_overseerr_requester_watch(
            {"title": "Test", "tmdbId": 550}, MagicMock(), {}, MagicMock(), MagicMock(), "1"
        )
        assert result is True

    def test_disabled_returns_true(self):
        """Disabled feature returns True (actionable)."""
        from app.media_cleaner import check_excluded_overseerr_requester_watch

        exclude = {"overseerr": {"protect_unwatched_requesters": {"enabled": False}}}
        result = check_excluded_overseerr_requester_watch(
            {"title": "Test", "tmdbId": 550}, MagicMock(), exclude, MagicMock(), MagicMock(), "1"
        )
        assert result is True

    def test_no_overseerr_instance_returns_true(self):
        """No Overseerr instance returns True (actionable)."""
        from app.media_cleaner import check_excluded_overseerr_requester_watch

        exclude = {"overseerr": {"protect_unwatched_requesters": {"enabled": True}}}
        result = check_excluded_overseerr_requester_watch(
            {"title": "Test", "tmdbId": 550}, MagicMock(), exclude, None, MagicMock(), "1"
        )
        assert result is True

    def test_no_tautulli_instance_returns_true(self):
        """No Tautulli instance returns True (actionable)."""
        from app.media_cleaner import check_excluded_overseerr_requester_watch

        exclude = {"overseerr": {"protect_unwatched_requesters": {"enabled": True}}}
        result = check_excluded_overseerr_requester_watch(
            {"title": "Test", "tmdbId": 550}, MagicMock(), exclude, MagicMock(), None, "1"
        )
        assert result is True

    def test_no_tmdb_id_returns_true(self):
        """No TMDB ID returns True (actionable)."""
        from app.media_cleaner import check_excluded_overseerr_requester_watch

        exclude = {"overseerr": {"protect_unwatched_requesters": {"enabled": True}}}
        result = check_excluded_overseerr_requester_watch(
            {"title": "Test"}, MagicMock(), exclude, MagicMock(), MagicMock(), "1"
        )
        assert result is True

    def test_no_request_returns_true(self):
        """No request in Overseerr returns True (actionable)."""
        from app.media_cleaner import check_excluded_overseerr_requester_watch

        exclude = {"overseerr": {"protect_unwatched_requesters": {"enabled": True}}}
        overseerr = MagicMock()
        overseerr.get_request_data.return_value = None

        result = check_excluded_overseerr_requester_watch(
            {"title": "Test", "tmdbId": 550}, MagicMock(), exclude, overseerr, MagicMock(), "1"
        )
        assert result is True

    def test_grace_period_protects(self):
        """Request within grace period is protected (returns False)."""
        from app.media_cleaner import check_excluded_overseerr_requester_watch

        exclude = {"overseerr": {"protect_unwatched_requesters": {
            "enabled": True, "min_request_age_days": 90
        }}}
        overseerr = MagicMock()
        recent_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        overseerr.get_request_data.return_value = {
            "created_at": recent_date,
            "requested_by": {"username": "testuser", "plexUsername": "testuser"},
        }

        result = check_excluded_overseerr_requester_watch(
            {"title": "Test", "tmdbId": 550}, MagicMock(), exclude, overseerr, MagicMock(), "1"
        )
        assert result is False  # Protected

    def test_max_protection_allows_deletion(self):
        """Request older than max_protection_days allows deletion (returns True)."""
        from app.media_cleaner import check_excluded_overseerr_requester_watch

        exclude = {"overseerr": {"protect_unwatched_requesters": {
            "enabled": True, "max_protection_days": 365
        }}}
        overseerr = MagicMock()
        old_date = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
        overseerr.get_request_data.return_value = {
            "created_at": old_date,
            "requested_by": {"username": "testuser", "plexUsername": "testuser"},
        }

        result = check_excluded_overseerr_requester_watch(
            {"title": "Test", "tmdbId": 550}, MagicMock(), exclude, overseerr, MagicMock(), "1"
        )
        assert result is True  # Allow deletion

    def test_unwatched_requester_protected(self):
        """Unwatched by requester is protected (returns False)."""
        from app.media_cleaner import check_excluded_overseerr_requester_watch

        exclude = {"overseerr": {"protect_unwatched_requesters": {"enabled": True}}}
        overseerr = MagicMock()
        old_date = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        overseerr.get_request_data.return_value = {
            "created_at": old_date,
            "requested_by": {"username": "testuser", "plexUsername": "testuser"},
        }
        tautulli = MagicMock()
        tautulli.has_user_watched.return_value = False

        plex_item = MagicMock()
        plex_item.ratingKey = 123
        plex_item.grandparentRatingKey = None

        result = check_excluded_overseerr_requester_watch(
            {"title": "Test Movie", "tmdbId": 550}, plex_item, exclude, overseerr, tautulli, "1"
        )
        assert result is False  # Protected

    def test_watched_requester_allows_deletion(self):
        """Watched by requester allows deletion (returns True)."""
        from app.media_cleaner import check_excluded_overseerr_requester_watch

        exclude = {"overseerr": {"protect_unwatched_requesters": {"enabled": True}}}
        overseerr = MagicMock()
        old_date = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        overseerr.get_request_data.return_value = {
            "created_at": old_date,
            "requested_by": {"username": "testuser", "plexUsername": "testuser"},
        }
        tautulli = MagicMock()
        tautulli.has_user_watched.return_value = True

        plex_item = MagicMock()
        plex_item.ratingKey = 123
        plex_item.grandparentRatingKey = None

        result = check_excluded_overseerr_requester_watch(
            {"title": "Test Movie", "tmdbId": 550}, plex_item, exclude, overseerr, tautulli, "1"
        )
        assert result is True  # Allow deletion

    def test_manual_user_mapping_works(self):
        """Manual user_mapping is used for Tautulli lookup."""
        from app.media_cleaner import check_excluded_overseerr_requester_watch

        exclude = {"overseerr": {"protect_unwatched_requesters": {
            "enabled": True,
            "user_mapping": {"overseerr_user": "tautulli_user"},
        }}}
        overseerr = MagicMock()
        old_date = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        overseerr.get_request_data.return_value = {
            "created_at": old_date,
            "requested_by": {"username": "overseerr_user", "plexUsername": "", "email": ""},
        }
        tautulli = MagicMock()
        tautulli.has_user_watched.return_value = True

        plex_item = MagicMock()
        plex_item.ratingKey = 123
        plex_item.grandparentRatingKey = None

        result = check_excluded_overseerr_requester_watch(
            {"title": "Test Movie", "tmdbId": 550}, plex_item, exclude, overseerr, tautulli, "1"
        )

        # Verify Tautulli was called with the mapped username
        tautulli.has_user_watched.assert_called_once()
        call_kwargs = tautulli.has_user_watched.call_args
        assert call_kwargs[1]["user"] == "tautulli_user" or call_kwargs[0][3] == "tautulli_user" if call_kwargs[0] else call_kwargs[1]["user"] == "tautulli_user"

    def test_plex_username_auto_match(self):
        """plexUsername is used as auto-match for Tautulli."""
        from app.media_cleaner import check_excluded_overseerr_requester_watch

        exclude = {"overseerr": {"protect_unwatched_requesters": {"enabled": True}}}
        overseerr = MagicMock()
        old_date = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        overseerr.get_request_data.return_value = {
            "created_at": old_date,
            "requested_by": {"username": "overseerr_name", "plexUsername": "plex_name", "email": ""},
        }
        tautulli = MagicMock()
        tautulli.has_user_watched.return_value = False

        plex_item = MagicMock()
        plex_item.ratingKey = 123
        plex_item.grandparentRatingKey = None

        check_excluded_overseerr_requester_watch(
            {"title": "Test", "tmdbId": 550}, plex_item, exclude, overseerr, tautulli, "1"
        )

        # Should use plexUsername, not overseerr username
        call_kwargs = tautulli.has_user_watched.call_args[1]
        assert call_kwargs["user"] == "plex_name"

    def test_unmappable_user_protected_by_default(self):
        """Unmappable user is protected by default (returns False)."""
        from app.media_cleaner import check_excluded_overseerr_requester_watch

        exclude = {"overseerr": {"protect_unwatched_requesters": {"enabled": True}}}
        overseerr = MagicMock()
        old_date = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        overseerr.get_request_data.return_value = {
            "created_at": old_date,
            "requested_by": {"username": "", "plexUsername": "", "email": ""},
        }
        tautulli = MagicMock()

        result = check_excluded_overseerr_requester_watch(
            {"title": "Test", "tmdbId": 550}, MagicMock(), exclude, overseerr, tautulli, "1"
        )
        assert result is False  # Protected
        tautulli.has_user_watched.assert_not_called()

    def test_tv_show_uses_grandparent_key(self):
        """TV shows use statistics-based detection for grandparent key."""
        from app.media_cleaner import check_excluded_overseerr_requester_watch

        exclude = {"overseerr": {"protect_unwatched_requesters": {"enabled": True}}}
        overseerr = MagicMock()
        old_date = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        overseerr.get_request_data.return_value = {
            "created_at": old_date,
            "requested_by": {"username": "testuser", "plexUsername": "testuser"},
        }
        tautulli = MagicMock()
        tautulli.has_user_watched.return_value = True

        plex_item = MagicMock()
        plex_item.ratingKey = 456
        plex_item.grandparentRatingKey = None

        # Sonarr data has "statistics" field indicating TV show
        media_data = {"title": "Test Show", "tmdbId": 550, "statistics": {"episodeFileCount": 10}}

        check_excluded_overseerr_requester_watch(
            media_data, plex_item, exclude, overseerr, tautulli, "1"
        )

        # Should use grandparent_rating_key for TV shows
        call_kwargs = tautulli.has_user_watched.call_args[1]
        assert call_kwargs["grandparent_rating_key"] == "456"
        assert call_kwargs["rating_key"] is None
