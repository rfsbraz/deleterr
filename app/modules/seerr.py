# encoding: utf-8

import requests

from app import logger

# Request status constants from Seerr/Overseerr API
REQUEST_STATUS_PENDING = 1
REQUEST_STATUS_APPROVED = 2
REQUEST_STATUS_DECLINED = 3

# Media status constants from Seerr/Overseerr API
MEDIA_STATUS_DELETED = 6


class Seerr:
    """
    Client for interacting with the Seerr API.

    Compatible with both Seerr and Overseerr (they share the same API).

    Provides functionality for:
    - Fetching request data to exclude/include media based on user requests
    - Updating media status after deletion to make it requestable again
    """

    def __init__(self, url, api_key, ssl_verify=True):
        """
        Initialize Seerr client.

        Args:
            url: Base URL of the Seerr/Overseerr server
            api_key: API key for authentication
            ssl_verify: Whether to verify SSL certificates
        """
        self.url = url.rstrip("/") if url else None
        self.api_key = api_key
        self.ssl_verify = ssl_verify
        self._requests_cache = {}  # {tmdb_id: request_data}
        self._media_cache = {}  # {tmdb_id: media_data}
        self._users_cache = {}  # {user_id: user_data}

    def _make_request(self, method, endpoint, **kwargs):
        """
        Make an authenticated request to the Seerr API.

        Args:
            method: HTTP method (get, post, put, delete)
            endpoint: API endpoint path (without /api/v1 prefix)
            **kwargs: Additional arguments passed to requests

        Returns:
            Response JSON or None on error
        """
        if not self.url or not self.api_key:
            logger.warning("Seerr not configured (missing URL or API key)")
            return None

        headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
        }

        url = f"{self.url}/api/v1{endpoint}"

        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                verify=self.ssl_verify,
                timeout=30,
                **kwargs,
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Cannot reach Seerr at {self.url}: Connection refused or host unreachable")
            logger.debug(f"Connection error details: {e}")
            return None
        except requests.exceptions.Timeout as e:
            logger.warning(f"Seerr request to {endpoint} timed out after 30s")
            logger.debug(f"Timeout details: {e}")
            return None
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else "unknown"
            if status_code == 401:
                logger.warning(f"Seerr API authentication failed (HTTP 401): Check your API key")
            elif status_code == 403:
                logger.warning(f"Seerr API access denied (HTTP 403): API key may lack permissions")
            elif status_code == 404:
                logger.debug(f"Seerr resource not found (HTTP 404): {endpoint}")
            elif status_code >= 500:
                logger.warning(f"Seerr server error (HTTP {status_code}) on {endpoint}")
            else:
                logger.warning(f"Seerr API error (HTTP {status_code}) on {endpoint}: {e}")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"Seerr API request failed: {e}")
            return None

    def test_connection(self):
        """
        Test the connection to Seerr.

        Returns:
            True if connection is successful, False otherwise
        """
        result = self._make_request("get", "/status")
        if result is not None:
            logger.debug(
                f"Connected to Seerr v{result.get('version', 'unknown')}"
            )
            return True
        return False

    def get_all_requests(self, status=None):
        """
        Fetch all requests from Seerr.

        Args:
            status: Optional status filter (1=pending, 2=approved, 3=declined)

        Returns:
            Dict mapping TMDB ID to request data, or empty dict on error
        """
        if self._requests_cache:
            return self._requests_cache

        requests_data = {}
        page = 1
        page_size = 100

        while True:
            params = {
                "take": page_size,
                "skip": (page - 1) * page_size,
            }
            if status:
                params["filter"] = status

            result = self._make_request("get", "/request", params=params)
            if result is None:
                logger.warning("Failed to fetch requests from Seerr")
                break

            results = result.get("results", [])
            if not results:
                break

            for request in results:
                media = request.get("media", {})
                tmdb_id = media.get("tmdbId")
                if tmdb_id:
                    # Store the request data indexed by TMDB ID
                    # If multiple requests exist for the same media, keep the most recent
                    if tmdb_id not in requests_data:
                        requests_data[tmdb_id] = {
                            "request_id": request.get("id"),
                            "status": request.get("status"),
                            "media_type": request.get("type"),
                            "requested_by": request.get("requestedBy", {}),
                            "created_at": request.get("createdAt"),
                            "media_id": media.get("id"),
                        }

            # Check if we've fetched all pages
            page_info = result.get("pageInfo", {})
            total_pages = page_info.get("pages", 1)
            if page >= total_pages:
                break
            page += 1

        self._requests_cache = requests_data
        logger.debug(f"Fetched {len(requests_data)} unique media requests from Seerr")
        return requests_data

    def _get_user_info(self, user_id):
        """
        Get user information by ID.

        Args:
            user_id: User ID to look up

        Returns:
            User data dict or None
        """
        if user_id in self._users_cache:
            return self._users_cache[user_id]

        result = self._make_request("get", f"/user/{user_id}")
        if result:
            self._users_cache[user_id] = result
        return result

    def is_requested(self, tmdb_id, include_pending=True):
        """
        Check if media has any request in Seerr.

        Args:
            tmdb_id: TMDB ID of the media
            include_pending: Whether to include pending (not yet approved) requests

        Returns:
            True if the media has a request, False otherwise
        """
        requests_data = self.get_all_requests()
        request = requests_data.get(tmdb_id)

        if not request:
            return False

        # If we're not including pending requests, check status
        if not include_pending and request.get("status") == REQUEST_STATUS_PENDING:
            return False

        return True

    def is_requested_by(self, tmdb_id, users, include_pending=True):
        """
        Check if media was requested by specific users.

        Args:
            tmdb_id: TMDB ID of the media
            users: List of usernames or emails to check
            include_pending: Whether to include pending requests

        Returns:
            True if the media was requested by one of the specified users
        """
        if not users:
            return self.is_requested(tmdb_id, include_pending)

        requests_data = self.get_all_requests()
        request = requests_data.get(tmdb_id)

        if not request:
            return False

        # If we're not including pending requests, check status
        if not include_pending and request.get("status") == REQUEST_STATUS_PENDING:
            return False

        # Check if the requester matches any of the specified users
        requested_by = request.get("requested_by", {})
        requester_username = requested_by.get("username", "").lower()
        requester_email = requested_by.get("email", "").lower()
        requester_plex_username = requested_by.get("plexUsername", "").lower()

        users_lower = [u.lower() for u in users]

        return (
            requester_username in users_lower
            or requester_email in users_lower
            or requester_plex_username in users_lower
        )

    def get_request_status(self, tmdb_id):
        """
        Get the request status for a media item.

        Args:
            tmdb_id: TMDB ID of the media

        Returns:
            Request status (1=pending, 2=approved, 3=declined) or None if not requested
        """
        requests_data = self.get_all_requests()
        request = requests_data.get(tmdb_id)
        return request.get("status") if request else None

    def get_request_data(self, tmdb_id):
        """
        Get full request data for a media item.

        Args:
            tmdb_id: TMDB ID of the media

        Returns:
            Request data dict or None if not requested.
            Dict includes: request_id, status, media_type, requested_by, created_at, media_id
        """
        requests_data = self.get_all_requests()
        return requests_data.get(tmdb_id)

    def _get_media_id(self, tmdb_id, media_type):
        """
        Get the Seerr internal media ID for a TMDB ID.

        Args:
            tmdb_id: TMDB ID of the media
            media_type: 'movie' or 'tv'

        Returns:
            Seerr media ID or None
        """
        # First check if we have it from the requests cache
        requests_data = self.get_all_requests()
        request = requests_data.get(tmdb_id)
        if request and request.get("media_id"):
            return request.get("media_id")

        # Otherwise, look it up via the media endpoint
        endpoint_type = "movie" if media_type == "movie" else "tv"
        result = self._make_request("get", f"/{endpoint_type}/{tmdb_id}")
        if result:
            media_info = result.get("mediaInfo")
            if media_info:
                return media_info.get("id")

        return None

    def mark_as_deleted(self, tmdb_id, media_type):
        """
        Update media status in Seerr after deletion.

        This marks the media as deleted, which allows it to be requested again.

        Args:
            tmdb_id: TMDB ID of the media
            media_type: 'movie' or 'tv'/'show'

        Returns:
            True if successful, False otherwise
        """
        # Normalize media type
        if media_type in ("tv", "show"):
            media_type = "tv"

        media_id = self._get_media_id(tmdb_id, media_type)
        if not media_id:
            logger.debug(
                f"Media not found in Seerr (TMDB: {tmdb_id}) - may not have been requested via Seerr"
            )
            return False

        # Delete the media entry to reset its status
        # This is the recommended way to make media requestable again
        result = self._make_request("delete", f"/media/{media_id}")
        if result is not None:
            logger.debug(
                f"Updated Seerr status for media ID {media_id} (TMDB: {tmdb_id})"
            )
            # Clear caches since state has changed
            self.clear_cache()
            return True

        logger.warning(
            f"Could not update Seerr status for TMDB {tmdb_id} (media_id: {media_id}). "
            "The item will remain marked as 'available' in Seerr."
        )
        return False

    def clear_cache(self):
        """Clear all cached data."""
        self._requests_cache = {}
        self._media_cache = {}
        logger.debug("Seerr cache cleared")


# Backward compatibility alias
Overseerr = Seerr
