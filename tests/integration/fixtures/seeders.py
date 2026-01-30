"""
Data seeders for integration testing.

These utilities populate Radarr, Sonarr, and the mock Plex server
with test data for integration tests.
"""

import requests
import time
from typing import Dict, List, Optional

# Retry configuration for external API operations
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds between retries


class ServiceSeeder:
    """Base class for service seeders."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json"
        }

    def wait_for_ready(self, timeout: int = 120) -> bool:
        """Wait for the service to be ready."""
        raise NotImplementedError


class RadarrSeeder(ServiceSeeder):
    """Seeds Radarr with test movie data via API."""

    def wait_for_ready(self, timeout: int = 120) -> bool:
        """Wait for Radarr to be ready and accepting API requests."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                resp = requests.get(
                    f"{self.base_url}/api/v3/system/status",
                    headers=self.headers,
                    timeout=5
                )
                if resp.status_code == 200:
                    return True
            except requests.RequestException:
                # Service may not be ready yet; retry loop continues
                pass
            time.sleep(2)
        return False

    def get_api_key(self) -> Optional[str]:
        """Try to get API key from Radarr (for first-time setup)."""
        try:
            # Radarr generates API key on first start
            # Try accessing without auth to get redirected to setup
            resp = requests.get(f"{self.base_url}/initialize.js", timeout=5)
            if resp.status_code == 200:
                # Parse API key from response if available
                pass
        except requests.RequestException:
            # Service may not be accessible; return None
            pass
        return None

    def setup_root_folder(self, path: str = "/movies") -> Dict:
        """Create root folder for movies."""
        # Check if root folder exists
        try:
            resp = requests.get(
                f"{self.base_url}/api/v3/rootfolder",
                headers=self.headers,
                timeout=10
            )
            if resp.status_code == 200:
                folders = resp.json()
                for folder in folders:
                    if folder.get("path") == path:
                        print(f"Root folder already exists: {path}")
                        return folder
        except requests.RequestException as e:
            print(f"Error checking root folders: {e}")

        # Create root folder with retry logic
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.post(
                    f"{self.base_url}/api/v3/rootfolder",
                    headers=self.headers,
                    json={"path": path},
                    timeout=10
                )
                result = resp.json()
                if resp.status_code in (200, 201):
                    print(f"Successfully created root folder: {path}")
                    return result
                else:
                    print(f"Attempt {attempt + 1}/{MAX_RETRIES} failed to create root folder {path}: {resp.status_code} - {result}")
            except requests.RequestException as e:
                print(f"Attempt {attempt + 1}/{MAX_RETRIES} request error creating root folder {path}: {e}")

            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)

        print(f"Failed to create root folder {path} after {MAX_RETRIES} attempts")
        return {"error": f"Failed to create root folder {path}"}

    def get_quality_profiles(self) -> List[Dict]:
        """Get available quality profiles."""
        resp = requests.get(
            f"{self.base_url}/api/v3/qualityprofile",
            headers=self.headers,
            timeout=10
        )
        return resp.json()

    def add_movie(self, movie_data: Dict) -> Dict:
        """Add a movie to Radarr (unmonitored, no download) with retry logic."""
        # Ensure root folder exists before adding movie
        root_folder_path = movie_data.get("rootFolderPath", "/movies")
        self.setup_root_folder(root_folder_path)

        # Get quality profile if not specified
        quality_profile_id = movie_data.get("qualityProfileId")
        if not quality_profile_id:
            profiles = self.get_quality_profiles()
            if profiles:
                quality_profile_id = profiles[0]["id"]
            else:
                quality_profile_id = 1

        payload = {
            "title": movie_data["title"],
            "year": movie_data["year"],
            "tmdbId": movie_data["tmdbId"],
            "qualityProfileId": quality_profile_id,
            "rootFolderPath": root_folder_path,
            "monitored": False,
            "addOptions": {"searchForMovie": False}
        }

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.post(
                    f"{self.base_url}/api/v3/movie",
                    headers=self.headers,
                    json=payload,
                    timeout=60  # Longer timeout for TMDb lookup
                )
                result = resp.json()

                if resp.status_code in (200, 201):
                    print(f"Successfully added movie: {movie_data['title']}")
                    return result

                # Check if movie already exists
                if resp.status_code == 400:
                    error_msg = str(result)
                    if "already been added" in error_msg.lower() or "already exists" in error_msg.lower():
                        print(f"Movie already exists: {movie_data['title']}")
                        # Try to find and return existing movie
                        movies = self.get_movies()
                        for m in movies:
                            if m.get("tmdbId") == movie_data["tmdbId"]:
                                return m

                last_error = f"{resp.status_code} - {result}"
                print(f"Attempt {attempt + 1}/{MAX_RETRIES} failed to add movie {movie_data['title']}: {last_error}")

            except requests.RequestException as e:
                last_error = str(e)
                print(f"Attempt {attempt + 1}/{MAX_RETRIES} request error for {movie_data['title']}: {e}")

            if attempt < MAX_RETRIES - 1:
                print(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)

        print(f"Failed to add movie {movie_data['title']} after {MAX_RETRIES} attempts: {last_error}")
        return {"error": last_error}

    def get_movies(self) -> List[Dict]:
        """Get all movies from Radarr."""
        resp = requests.get(
            f"{self.base_url}/api/v3/movie",
            headers=self.headers,
            timeout=30
        )
        return resp.json()

    def delete_movie(self, movie_id: int, delete_files: bool = True) -> None:
        """Delete a movie from Radarr."""
        requests.delete(
            f"{self.base_url}/api/v3/movie/{movie_id}",
            headers=self.headers,
            params={"deleteFiles": delete_files},
            timeout=30
        )

    def seed_test_movies(self, movies: List[Dict]) -> List[Dict]:
        """Seed multiple movies and return their Radarr data."""
        results = []
        for movie in movies:
            try:
                result = self.add_movie(movie)
                if "id" in result:
                    results.append(result)
            except Exception as e:
                print(f"Failed to seed movie {movie.get('title')}: {e}")
        return results

    def cleanup_all(self) -> None:
        """Remove all movies from Radarr."""
        movies = self.get_movies()
        for movie in movies:
            try:
                self.delete_movie(movie["id"])
            except Exception:
                # Best-effort cleanup; continue with remaining items
                pass

    def get_tags(self) -> List[Dict]:
        """Get all tags from Radarr."""
        resp = requests.get(
            f"{self.base_url}/api/v3/tag",
            headers=self.headers,
            timeout=10
        )
        return resp.json()

    def create_tag(self, label: str) -> Dict:
        """Create a new tag in Radarr."""
        # Check if tag already exists
        existing_tags = self.get_tags()
        for tag in existing_tags:
            if tag.get("label", "").lower() == label.lower():
                return tag

        resp = requests.post(
            f"{self.base_url}/api/v3/tag",
            headers=self.headers,
            json={"label": label},
            timeout=10
        )
        return resp.json()

    def add_tag_to_movie(self, movie_id: int, tag_id: int) -> Dict:
        """Add a tag to a movie."""
        # Get current movie data
        resp = requests.get(
            f"{self.base_url}/api/v3/movie/{movie_id}",
            headers=self.headers,
            timeout=10
        )
        movie = resp.json()

        # Add tag if not already present
        if tag_id not in movie.get("tags", []):
            movie["tags"] = movie.get("tags", []) + [tag_id]
            resp = requests.put(
                f"{self.base_url}/api/v3/movie/{movie_id}",
                headers=self.headers,
                json=movie,
                timeout=10
            )
            return resp.json()
        return movie

    def update_movie_monitored(self, movie_id: int, monitored: bool) -> Dict:
        """Update the monitored status of a movie."""
        resp = requests.get(
            f"{self.base_url}/api/v3/movie/{movie_id}",
            headers=self.headers,
            timeout=10
        )
        movie = resp.json()
        movie["monitored"] = monitored
        resp = requests.put(
            f"{self.base_url}/api/v3/movie/{movie_id}",
            headers=self.headers,
            json=movie,
            timeout=10
        )
        return resp.json()


class SonarrSeeder(ServiceSeeder):
    """Seeds Sonarr with test TV show data via API."""

    def wait_for_ready(self, timeout: int = 120) -> bool:
        """Wait for Sonarr to be ready."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                resp = requests.get(
                    f"{self.base_url}/api/v3/system/status",
                    headers=self.headers,
                    timeout=5
                )
                if resp.status_code == 200:
                    return True
            except requests.RequestException:
                # Service may not be ready yet; retry loop continues
                pass
            time.sleep(2)
        return False

    def setup_root_folder(self, path: str = "/tv") -> Dict:
        """Create root folder for TV shows."""
        # Check if root folder exists
        try:
            resp = requests.get(
                f"{self.base_url}/api/v3/rootfolder",
                headers=self.headers,
                timeout=10
            )
            if resp.status_code == 200:
                folders = resp.json()
                for folder in folders:
                    if folder.get("path") == path:
                        print(f"Root folder already exists: {path}")
                        return folder
        except requests.RequestException as e:
            print(f"Error checking root folders: {e}")

        # Create root folder with retry logic
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.post(
                    f"{self.base_url}/api/v3/rootfolder",
                    headers=self.headers,
                    json={"path": path},
                    timeout=10
                )
                result = resp.json()
                if resp.status_code in (200, 201):
                    print(f"Successfully created root folder: {path}")
                    return result
                else:
                    print(f"Attempt {attempt + 1}/{MAX_RETRIES} failed to create root folder {path}: {resp.status_code} - {result}")
            except requests.RequestException as e:
                print(f"Attempt {attempt + 1}/{MAX_RETRIES} request error creating root folder {path}: {e}")

            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)

        print(f"Failed to create root folder {path} after {MAX_RETRIES} attempts")
        return {"error": f"Failed to create root folder {path}"}

    def get_quality_profiles(self) -> List[Dict]:
        """Get available quality profiles."""
        resp = requests.get(
            f"{self.base_url}/api/v3/qualityprofile",
            headers=self.headers,
            timeout=10
        )
        return resp.json()

    def add_series(self, series_data: Dict) -> Dict:
        """Add a TV series to Sonarr with retry logic."""
        # Ensure root folder exists before adding series
        root_folder_path = series_data.get("rootFolderPath", "/tv")
        self.setup_root_folder(root_folder_path)

        # Get quality profile if not specified
        quality_profile_id = series_data.get("qualityProfileId")
        if not quality_profile_id:
            profiles = self.get_quality_profiles()
            if profiles:
                quality_profile_id = profiles[0]["id"]
            else:
                quality_profile_id = 1

        payload = {
            "title": series_data["title"],
            "tvdbId": series_data["tvdbId"],
            "qualityProfileId": quality_profile_id,
            "rootFolderPath": series_data.get("rootFolderPath", "/tv"),
            "seriesType": series_data.get("seriesType", "standard"),
            "seasonFolder": True,
            "monitored": False,
            "addOptions": {"searchForMissingEpisodes": False}
        }

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.post(
                    f"{self.base_url}/api/v3/series",
                    headers=self.headers,
                    json=payload,
                    timeout=60  # Longer timeout for TVDB lookup
                )
                result = resp.json()

                if resp.status_code in (200, 201):
                    print(f"Successfully added series: {series_data['title']}")
                    return result

                # Check if series already exists
                if resp.status_code == 400:
                    error_msg = str(result)
                    if "already been added" in error_msg.lower() or "already exists" in error_msg.lower():
                        print(f"Series already exists: {series_data['title']}")
                        # Try to find and return existing series
                        series_list = self.get_series()
                        for s in series_list:
                            if s.get("tvdbId") == series_data["tvdbId"]:
                                return s

                last_error = f"{resp.status_code} - {result}"
                print(f"Attempt {attempt + 1}/{MAX_RETRIES} failed to add series {series_data['title']}: {last_error}")

            except requests.RequestException as e:
                last_error = str(e)
                print(f"Attempt {attempt + 1}/{MAX_RETRIES} request error for {series_data['title']}: {e}")

            if attempt < MAX_RETRIES - 1:
                print(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)

        print(f"Failed to add series {series_data['title']} after {MAX_RETRIES} attempts: {last_error}")
        return {"error": last_error}

    def get_series(self) -> List[Dict]:
        """Get all series from Sonarr."""
        resp = requests.get(
            f"{self.base_url}/api/v3/series",
            headers=self.headers,
            timeout=30
        )
        return resp.json()

    def delete_series(self, series_id: int, delete_files: bool = True) -> None:
        """Delete a series from Sonarr."""
        requests.delete(
            f"{self.base_url}/api/v3/series/{series_id}",
            headers=self.headers,
            params={"deleteFiles": delete_files},
            timeout=30
        )

    def seed_test_series(self, series_list: List[Dict]) -> List[Dict]:
        """Seed multiple TV series and return their Sonarr data."""
        results = []
        for series in series_list:
            try:
                result = self.add_series(series)
                if "id" in result:
                    results.append(result)
            except Exception as e:
                print(f"Failed to seed series {series.get('title')}: {e}")
        return results

    def cleanup_all(self) -> None:
        """Remove all series from Sonarr."""
        series_list = self.get_series()
        for series in series_list:
            try:
                self.delete_series(series["id"])
            except Exception:
                # Best-effort cleanup; continue with remaining items
                pass

    def get_tags(self) -> List[Dict]:
        """Get all tags from Sonarr."""
        resp = requests.get(
            f"{self.base_url}/api/v3/tag",
            headers=self.headers,
            timeout=10
        )
        return resp.json()

    def create_tag(self, label: str) -> Dict:
        """Create a new tag in Sonarr."""
        # Check if tag already exists
        existing_tags = self.get_tags()
        for tag in existing_tags:
            if tag.get("label", "").lower() == label.lower():
                return tag

        resp = requests.post(
            f"{self.base_url}/api/v3/tag",
            headers=self.headers,
            json={"label": label},
            timeout=10
        )
        return resp.json()

    def add_tag_to_series(self, series_id: int, tag_id: int) -> Dict:
        """Add a tag to a series."""
        return self.add_tags_to_series(series_id, [tag_id])

    def add_tags_to_series(self, series_id: int, tag_ids: List[int]) -> Dict:
        """Add multiple tags to a series using the series editor endpoint.

        Uses the /api/v3/series/editor endpoint with applyTags: "add"
        which is the recommended approach for tag operations.
        """
        # Use the series editor endpoint with applyTags
        payload = {
            "seriesIds": [series_id],
            "tags": tag_ids,
            "applyTags": "add"
        }

        print(f"Adding tags {tag_ids} to series {series_id}")
        print(f"Payload: {payload}")

        resp = requests.put(
            f"{self.base_url}/api/v3/series/editor",
            headers=self.headers,
            json=payload,
            timeout=10
        )

        print(f"Series editor response: {resp.status_code}")
        if resp.text:
            print(f"Response body: {resp.text[:500]}")

        # Sonarr may return 202 (Accepted) for async processing
        # Poll until the tags are confirmed or timeout
        max_attempts = 10
        for attempt in range(max_attempts):
            resp = requests.get(
                f"{self.base_url}/api/v3/series/{series_id}",
                headers=self.headers,
                timeout=10
            )
            series = resp.json()
            current_tags = set(series.get("tags", []))
            if all(tag_id in current_tags for tag_id in tag_ids):
                print(f"Tags confirmed after {attempt + 1} attempts: {series.get('tags', [])}")
                return series
            time.sleep(0.5)

        print(f"Tags not confirmed after {max_attempts} attempts: {series.get('tags', [])}")
        return series

    def update_series_monitored(
        self, series_id: int, monitored: bool, series: Optional[Dict] = None
    ) -> Dict:
        """Update the monitored status of a series using direct PUT.

        Uses the /api/v3/series/{id} endpoint with the full series object,
        which is more reliable for persisting monitored status changes.

        Args:
            series_id: The ID of the series to update.
            monitored: The new monitored status.
            series: Optional series object to use. If not provided, fetches fresh.
                    Pass this to avoid race conditions when tags were just added.
        """
        if series is None:
            # Get current series
            resp = requests.get(
                f"{self.base_url}/api/v3/series/{series_id}",
                headers=self.headers,
                timeout=10
            )
            series = resp.json()
        else:
            # Use a copy to avoid modifying the original
            series = dict(series)

        # Capture expected tags from input series to verify they persist
        expected_tags = set(series.get("tags", []))

        # Update monitored field
        series["monitored"] = monitored

        # PUT the full series back
        resp = requests.put(
            f"{self.base_url}/api/v3/series/{series_id}",
            headers=self.headers,
            json=series,
            timeout=10
        )

        # Sonarr may return 202 (Accepted) for async processing
        # Poll until both monitored status AND tags are confirmed
        max_attempts = 10
        for attempt in range(max_attempts):
            resp = requests.get(
                f"{self.base_url}/api/v3/series/{series_id}",
                headers=self.headers,
                timeout=10
            )
            result = resp.json()
            result_tags = set(result.get("tags", []))
            monitored_ok = result.get("monitored") == monitored
            tags_ok = expected_tags.issubset(result_tags) if expected_tags else True

            if monitored_ok and tags_ok:
                return result
            time.sleep(0.5)

        # Return last result even if not matching (let test fail with clear state)
        return result


class PlexMockSeeder:
    """Seeds the mock Plex server with test data."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')

    def wait_for_ready(self, timeout: int = 60) -> bool:
        """Wait for mock Plex to be ready."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                resp = requests.get(f"{self.base_url}/health", timeout=5)
                if resp.status_code == 200:
                    return True
            except requests.RequestException:
                # Service may not be ready yet; retry loop continues
                pass
            time.sleep(1)
        return False

    def reset(self) -> None:
        """Reset all data in mock Plex."""
        requests.post(f"{self.base_url}/api/reset", timeout=10)

    def add_movie(self, movie_data: Dict) -> Dict:
        """Add a movie to mock Plex."""
        resp = requests.post(
            f"{self.base_url}/api/add_movie",
            json=movie_data,
            timeout=10
        )
        return resp.json()

    def add_series(self, series_data: Dict) -> Dict:
        """Add a TV series to mock Plex."""
        resp = requests.post(
            f"{self.base_url}/api/add_series",
            json=series_data,
            timeout=10
        )
        return resp.json()


class TautulliSeeder:
    """Seeds Tautulli with watch history data."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key

    def wait_for_ready(self, timeout: int = 120) -> bool:
        """Wait for Tautulli to be ready."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                resp = requests.get(
                    f"{self.base_url}/api/v2",
                    params={"apikey": self.api_key, "cmd": "status"},
                    timeout=5
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("response", {}).get("result") == "success":
                        return True
            except requests.RequestException:
                # Service may not be ready yet; retry loop continues
                pass
            time.sleep(2)
        return False

    def test_connection(self) -> bool:
        """Test if Tautulli is accessible."""
        try:
            resp = requests.get(
                f"{self.base_url}/api/v2",
                params={"apikey": self.api_key, "cmd": "status"},
                timeout=10
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False
