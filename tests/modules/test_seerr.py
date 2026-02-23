from unittest.mock import MagicMock, patch

import pytest

from app.modules.seerr import (
    Seerr,
    REQUEST_STATUS_PENDING,
    REQUEST_STATUS_APPROVED,
)


@pytest.mark.unit
class TestSeerr:
    def test_init(self):
        """Test Seerr initialization."""
        seerr = Seerr("http://localhost:5055", "test_api_key")

        assert seerr.url == "http://localhost:5055"
        assert seerr.api_key == "test_api_key"
        assert seerr.ssl_verify is True
        assert seerr._requests_cache == {}

    def test_init_url_trailing_slash(self):
        """Test that trailing slash is removed from URL."""
        seerr = Seerr("http://localhost:5055/", "test_api_key")

        assert seerr.url == "http://localhost:5055"

    def test_init_none_url(self):
        """Test initialization with None URL."""
        seerr = Seerr(None, "test_api_key")

        assert seerr.url is None

    @patch("app.modules.seerr.requests.request")
    def test_test_connection_success(self, mock_request):
        """Test successful connection test."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"version": "1.33.0"}
        mock_response.content = b'{"version": "1.33.0"}'
        mock_request.return_value = mock_response

        seerr = Seerr("http://localhost:5055", "test_api_key")
        result = seerr.test_connection()

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

    @patch("app.modules.seerr.requests.request")
    def test_test_connection_failure(self, mock_request):
        """Test failed connection test."""
        import requests as req
        mock_request.side_effect = req.exceptions.RequestException("Connection error")

        seerr = Seerr("http://localhost:5055", "test_api_key")
        result = seerr.test_connection()

        assert result is False

    def test_test_connection_no_url(self):
        """Test connection test with no URL configured."""
        seerr = Seerr(None, "test_api_key")
        result = seerr.test_connection()

        assert result is False

    @patch("app.modules.seerr.requests.request")
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

        seerr = Seerr("http://localhost:5055", "test_api_key")
        requests_data = seerr.get_all_requests()

        assert 550 in requests_data
        assert 551 in requests_data
        assert requests_data[550]["status"] == REQUEST_STATUS_APPROVED
        assert requests_data[551]["status"] == REQUEST_STATUS_PENDING

    @patch("app.modules.seerr.requests.request")
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

        seerr = Seerr("http://localhost:5055", "test_api_key")

        # First call
        seerr.get_all_requests()
        # Second call - should use cache
        seerr.get_all_requests()

        # API should only be called once due to caching
        assert mock_request.call_count == 1

    @patch.object(Seerr, "get_all_requests")
    def test_is_requested_true(self, mock_get_requests):
        """Test is_requested returns True when media is requested."""
        mock_get_requests.return_value = {
            550: {"status": REQUEST_STATUS_APPROVED}
        }

        seerr = Seerr("http://localhost:5055", "test_api_key")
        result = seerr.is_requested(550)

        assert result is True

    @patch.object(Seerr, "get_all_requests")
    def test_is_requested_false(self, mock_get_requests):
        """Test is_requested returns False when media is not requested."""
        mock_get_requests.return_value = {}

        seerr = Seerr("http://localhost:5055", "test_api_key")
        result = seerr.is_requested(550)

        assert result is False

    @patch.object(Seerr, "get_all_requests")
    def test_is_requested_exclude_pending(self, mock_get_requests):
        """Test is_requested with include_pending=False."""
        mock_get_requests.return_value = {
            550: {"status": REQUEST_STATUS_PENDING}
        }

        seerr = Seerr("http://localhost:5055", "test_api_key")

        # With include_pending=True (default)
        assert seerr.is_requested(550, include_pending=True) is True

        # With include_pending=False
        assert seerr.is_requested(550, include_pending=False) is False

    @patch.object(Seerr, "get_all_requests")
    def test_is_requested_by_username(self, mock_get_requests):
        """Test is_requested_by with username match."""
        mock_get_requests.return_value = {
            550: {
                "status": REQUEST_STATUS_APPROVED,
                "requested_by": {"username": "testuser", "email": "test@example.com"},
            }
        }

        seerr = Seerr("http://localhost:5055", "test_api_key")

        # Match by username
        assert seerr.is_requested_by(550, ["testuser"]) is True
        # Case insensitive
        assert seerr.is_requested_by(550, ["TESTUSER"]) is True
        # No match
        assert seerr.is_requested_by(550, ["otheruser"]) is False

    @patch.object(Seerr, "get_all_requests")
    def test_is_requested_by_email(self, mock_get_requests):
        """Test is_requested_by with email match."""
        mock_get_requests.return_value = {
            550: {
                "status": REQUEST_STATUS_APPROVED,
                "requested_by": {"username": "testuser", "email": "test@example.com"},
            }
        }

        seerr = Seerr("http://localhost:5055", "test_api_key")

        # Match by email
        assert seerr.is_requested_by(550, ["test@example.com"]) is True

    @patch.object(Seerr, "get_all_requests")
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

        seerr = Seerr("http://localhost:5055", "test_api_key")

        # Match by Plex username
        assert seerr.is_requested_by(550, ["plexuser"]) is True

    @patch.object(Seerr, "get_all_requests")
    def test_is_requested_by_no_users(self, mock_get_requests):
        """Test is_requested_by with no users falls back to is_requested."""
        mock_get_requests.return_value = {
            550: {"status": REQUEST_STATUS_APPROVED}
        }

        seerr = Seerr("http://localhost:5055", "test_api_key")

        # Empty users list should check any request
        assert seerr.is_requested_by(550, []) is True
        assert seerr.is_requested_by(550, None) is True

    @patch.object(Seerr, "get_all_requests")
    def test_is_requested_by_exclude_pending(self, mock_get_requests):
        """Test is_requested_by with include_pending=False."""
        mock_get_requests.return_value = {
            550: {
                "status": REQUEST_STATUS_PENDING,
                "requested_by": {"username": "testuser", "email": "test@example.com"},
            }
        }

        seerr = Seerr("http://localhost:5055", "test_api_key")

        # With include_pending=True (default)
        assert seerr.is_requested_by(550, ["testuser"], include_pending=True) is True

        # With include_pending=False
        assert seerr.is_requested_by(550, ["testuser"], include_pending=False) is False

    @patch.object(Seerr, "get_all_requests")
    def test_get_request_status(self, mock_get_requests):
        """Test getting request status."""
        mock_get_requests.return_value = {
            550: {"status": REQUEST_STATUS_APPROVED}
        }

        seerr = Seerr("http://localhost:5055", "test_api_key")

        assert seerr.get_request_status(550) == REQUEST_STATUS_APPROVED
        assert seerr.get_request_status(999) is None

    @patch.object(Seerr, "get_all_requests")
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

        seerr = Seerr("http://localhost:5055", "test_api_key")

        result = seerr.get_request_data(550)
        assert result == request_data

        # Non-existent media
        assert seerr.get_request_data(999) is None

    @patch("app.modules.seerr.requests.request")
    @patch.object(Seerr, "get_all_requests")
    def test_mark_as_deleted_success(self, mock_get_requests, mock_request):
        """Test successful mark_as_deleted."""
        mock_get_requests.return_value = {
            550: {"media_id": 100}
        }
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.content = b'{}'
        mock_request.return_value = mock_response

        seerr = Seerr("http://localhost:5055", "test_api_key")
        result = seerr.mark_as_deleted(550, "movie")

        assert result is True
        # Verify the DELETE request was made
        calls = mock_request.call_args_list
        delete_call = [c for c in calls if c[0][0] == "delete"]
        assert len(delete_call) == 1
        assert "/media/100" in delete_call[0][0][1]

    @patch("app.modules.seerr.requests.request")
    @patch.object(Seerr, "get_all_requests")
    def test_mark_as_deleted_no_media_id(self, mock_get_requests, mock_request):
        """Test mark_as_deleted when media ID not found."""
        mock_get_requests.return_value = {}

        # Mock the movie lookup to also fail
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.content = b'{}'
        mock_request.return_value = mock_response

        seerr = Seerr("http://localhost:5055", "test_api_key")
        result = seerr.mark_as_deleted(999, "movie")

        assert result is False

    @patch.object(Seerr, "get_all_requests")
    def test_clear_cache(self, mock_get_requests):
        """Test cache clearing."""
        mock_get_requests.return_value = {550: {}}

        seerr = Seerr("http://localhost:5055", "test_api_key")

        # Populate cache
        seerr._requests_cache = {550: {}}
        seerr._media_cache = {550: {}}

        # Clear cache
        seerr.clear_cache()

        assert seerr._requests_cache == {}
        assert seerr._media_cache == {}

    def test_backward_compat_alias(self):
        """Test that Overseerr is an alias for Seerr."""
        from app.modules.seerr import Overseerr

        assert Overseerr is Seerr


@pytest.mark.unit
class TestCheckExcludedSeerr:
    """Test the check_excluded_seerr function."""

    def test_no_config(self):
        """Test with no seerr config."""
        from app.media_cleaner import check_excluded_seerr

        media_data = {"title": "Test Movie", "tmdbId": 550}
        plex_item = MagicMock()
        exclude = {}

        result = check_excluded_seerr(media_data, plex_item, exclude, None)

        assert result is True

    def test_no_seerr_instance(self):
        """Test with config but no seerr instance."""
        from app.media_cleaner import check_excluded_seerr

        media_data = {"title": "Test Movie", "tmdbId": 550}
        plex_item = MagicMock()
        exclude = {"seerr": {"mode": "exclude"}}

        result = check_excluded_seerr(media_data, plex_item, exclude, None)

        assert result is True

    def test_no_tmdb_id(self):
        """Test with no TMDB ID in media data."""
        from app.media_cleaner import check_excluded_seerr

        media_data = {"title": "Test Movie"}
        plex_item = MagicMock()
        exclude = {"seerr": {"mode": "exclude"}}
        seerr = MagicMock()

        result = check_excluded_seerr(media_data, plex_item, exclude, seerr)

        assert result is True

    def test_exclude_mode_requested(self):
        """Test exclude mode with requested media."""
        from app.media_cleaner import check_excluded_seerr

        media_data = {"title": "Test Movie", "tmdbId": 550}
        plex_item = MagicMock()
        exclude = {"seerr": {"mode": "exclude"}}
        seerr = MagicMock()
        seerr.is_requested.return_value = True
        seerr.get_request_data.return_value = {"status": REQUEST_STATUS_APPROVED}

        result = check_excluded_seerr(media_data, plex_item, exclude, seerr)

        assert result is False  # Should be excluded (skipped)

    def test_exclude_mode_not_requested(self):
        """Test exclude mode with non-requested media."""
        from app.media_cleaner import check_excluded_seerr

        media_data = {"title": "Test Movie", "tmdbId": 550}
        plex_item = MagicMock()
        exclude = {"seerr": {"mode": "exclude"}}
        seerr = MagicMock()
        seerr.is_requested.return_value = False
        seerr.get_request_data.return_value = None

        result = check_excluded_seerr(media_data, plex_item, exclude, seerr)

        assert result is True  # Should NOT be excluded (actionable)

    def test_include_only_mode_requested(self):
        """Test include_only mode with requested media."""
        from app.media_cleaner import check_excluded_seerr

        media_data = {"title": "Test Movie", "tmdbId": 550}
        plex_item = MagicMock()
        exclude = {"seerr": {"mode": "include_only"}}
        seerr = MagicMock()
        seerr.is_requested.return_value = True
        seerr.get_request_data.return_value = {"status": REQUEST_STATUS_APPROVED}

        result = check_excluded_seerr(media_data, plex_item, exclude, seerr)

        assert result is True  # Should NOT be excluded (actionable)

    def test_include_only_mode_not_requested(self):
        """Test include_only mode with non-requested media."""
        from app.media_cleaner import check_excluded_seerr

        media_data = {"title": "Test Movie", "tmdbId": 550}
        plex_item = MagicMock()
        exclude = {"seerr": {"mode": "include_only"}}
        seerr = MagicMock()
        seerr.is_requested.return_value = False
        seerr.get_request_data.return_value = None

        result = check_excluded_seerr(media_data, plex_item, exclude, seerr)

        assert result is False  # Should be excluded (skipped)

    def test_exclude_mode_with_users(self):
        """Test exclude mode with specific users."""
        from app.media_cleaner import check_excluded_seerr

        media_data = {"title": "Test Movie", "tmdbId": 550}
        plex_item = MagicMock()
        exclude = {"seerr": {"mode": "exclude", "users": ["testuser"]}}
        seerr = MagicMock()
        seerr.is_requested_by.return_value = True
        seerr.get_request_data.return_value = {"status": REQUEST_STATUS_APPROVED}

        result = check_excluded_seerr(media_data, plex_item, exclude, seerr)

        assert result is False  # Should be excluded
        seerr.is_requested_by.assert_called_once_with(550, ["testuser"], True)

    def test_include_pending_false(self):
        """Test with include_pending=False."""
        from app.media_cleaner import check_excluded_seerr

        media_data = {"title": "Test Movie", "tmdbId": 550}
        plex_item = MagicMock()
        exclude = {"seerr": {"mode": "exclude", "include_pending": False}}
        seerr = MagicMock()
        seerr.is_requested.return_value = True
        seerr.get_request_data.return_value = {"status": REQUEST_STATUS_APPROVED}

        result = check_excluded_seerr(media_data, plex_item, exclude, seerr)

        seerr.is_requested.assert_called_once_with(550, False)

    def test_request_status_filter_approved_only(self):
        """Test filtering by request status (approved only)."""
        from app.media_cleaner import check_excluded_seerr

        media_data = {"title": "Test Movie", "tmdbId": 550}
        plex_item = MagicMock()
        exclude = {"seerr": {"mode": "exclude", "request_status": ["approved"]}}
        seerr = MagicMock()
        seerr.is_requested.return_value = True
        seerr.get_request_data.return_value = {"status": REQUEST_STATUS_APPROVED}

        result = check_excluded_seerr(media_data, plex_item, exclude, seerr)

        # Should be excluded because it's approved
        assert result is False

    def test_request_status_filter_no_match(self):
        """Test filtering by request status that doesn't match."""
        from app.media_cleaner import check_excluded_seerr

        media_data = {"title": "Test Movie", "tmdbId": 550}
        plex_item = MagicMock()
        exclude = {"seerr": {"mode": "exclude", "request_status": ["approved"]}}
        seerr = MagicMock()
        seerr.is_requested.return_value = True
        seerr.get_request_data.return_value = {"status": REQUEST_STATUS_PENDING}

        result = check_excluded_seerr(media_data, plex_item, exclude, seerr)

        # Should NOT be excluded because it's pending, not approved
        assert result is True

    def test_min_request_age_days_old_request(self):
        """Test filtering by minimum request age with old request."""
        from app.media_cleaner import check_excluded_seerr
        from datetime import datetime, timedelta, timezone

        media_data = {"title": "Test Movie", "tmdbId": 550}
        plex_item = MagicMock()
        exclude = {"seerr": {"mode": "include_only", "min_request_age_days": 30}}
        seerr = MagicMock()

        # Request is 60 days old (older than 30 day threshold)
        old_date = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        seerr.get_request_data.return_value = {
            "created_at": old_date,
            "status": REQUEST_STATUS_APPROVED,
        }
        seerr.is_requested.return_value = True

        result = check_excluded_seerr(media_data, plex_item, exclude, seerr)

        # Should be actionable (request is old enough for include_only mode)
        assert result is True

    def test_min_request_age_days_recent_request(self):
        """Test filtering by minimum request age with recent request."""
        from app.media_cleaner import check_excluded_seerr
        from datetime import datetime, timedelta, timezone

        media_data = {"title": "Test Movie", "tmdbId": 550}
        plex_item = MagicMock()
        exclude = {"seerr": {"mode": "include_only", "min_request_age_days": 30}}
        seerr = MagicMock()

        # Request is 10 days old (not older than 30 day threshold)
        recent_date = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        seerr.get_request_data.return_value = {
            "created_at": recent_date,
            "status": REQUEST_STATUS_APPROVED,
        }
        seerr.is_requested.return_value = True

        result = check_excluded_seerr(media_data, plex_item, exclude, seerr)

        # Should NOT be actionable (request is too recent for include_only mode)
        assert result is False

    def test_request_status_and_min_age_combined(self):
        """Test combining request_status and min_request_age_days filters."""
        from app.media_cleaner import check_excluded_seerr
        from datetime import datetime, timedelta, timezone

        media_data = {"title": "Test Movie", "tmdbId": 550}
        plex_item = MagicMock()
        exclude = {
            "seerr": {
                "mode": "include_only",
                "request_status": ["approved"],
                "min_request_age_days": 30,
            }
        }
        seerr = MagicMock()

        # Request is approved and 60 days old - should match both filters
        old_date = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        seerr.get_request_data.return_value = {
            "created_at": old_date,
            "status": REQUEST_STATUS_APPROVED,
        }
        seerr.is_requested.return_value = True

        result = check_excluded_seerr(media_data, plex_item, exclude, seerr)

        # Should be actionable (approved AND old enough)
        assert result is True


@pytest.mark.unit
class TestUpdateSeerrStatus:
    """Test the _update_seerr_status method in MediaCleaner."""

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
                "seerr": {"url": "http://localhost:5055", "api_key": "key"},
            }

            cleaner = MediaCleaner(mock_config)
            cleaner.seerr = MagicMock()

            library = {"exclude": {"seerr": {"update_status": False}}}
            media_data = {"title": "Test Movie", "tmdbId": 550}

            cleaner._update_seerr_status(library, media_data, "movie")

            # mark_as_deleted should NOT be called
            cleaner.seerr.mark_as_deleted.assert_not_called()

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
                "seerr": {"url": "http://localhost:5055", "api_key": "key"},
            }

            cleaner = MediaCleaner(mock_config)
            cleaner.seerr = MagicMock()
            cleaner.seerr.mark_as_deleted.return_value = True

            library = {"exclude": {"seerr": {"update_status": True}}}
            media_data = {"title": "Test Movie", "tmdbId": 550}

            cleaner._update_seerr_status(library, media_data, "movie")

            cleaner.seerr.mark_as_deleted.assert_called_once_with(550, "movie")

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
                "seerr": {"url": "http://localhost:5055", "api_key": "key"},
            }

            cleaner = MediaCleaner(mock_config)
            cleaner.seerr = MagicMock()

            library = {"exclude": {"seerr": {"update_status": True}}}
            media_data = {"title": "Test Movie"}  # No tmdbId

            cleaner._update_seerr_status(library, media_data, "movie")

            cleaner.seerr.mark_as_deleted.assert_not_called()

    def test_update_status_no_seerr_instance(self):
        """Test that status update is skipped when Seerr is not configured."""
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
            # seerr should be None when not configured

            library = {"exclude": {"seerr": {"update_status": True}}}
            media_data = {"title": "Test Movie", "tmdbId": 550}

            # Should not raise an exception
            cleaner._update_seerr_status(library, media_data, "movie")

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
                "seerr": {"url": "http://localhost:5055", "api_key": "key"},
            }

            cleaner = MediaCleaner(mock_config)
            cleaner.seerr = MagicMock()
            cleaner.seerr.mark_as_deleted.return_value = False  # Simulate failure

            library = {"exclude": {"seerr": {"update_status": True}}}
            media_data = {"title": "Test Movie", "tmdbId": 550}

            # Should not raise an exception
            cleaner._update_seerr_status(library, media_data, "movie")

            cleaner.seerr.mark_as_deleted.assert_called_once()

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
                "seerr": {"url": "http://localhost:5055", "api_key": "key"},
            }

            cleaner = MediaCleaner(mock_config)
            cleaner.seerr = MagicMock()
            cleaner.seerr.mark_as_deleted.side_effect = Exception("API Error")

            library = {"exclude": {"seerr": {"update_status": True}}}
            media_data = {"title": "Test Movie", "tmdbId": 550}

            # Should not raise an exception - handled gracefully
            cleaner._update_seerr_status(library, media_data, "movie")
