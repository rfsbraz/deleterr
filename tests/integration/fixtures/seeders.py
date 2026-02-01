"""
Data seeders for integration testing.

These utilities populate Radarr and Sonarr with test data for integration tests.
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

    def wait_for_series_refresh(self, series_id: int, timeout: int = 30) -> bool:
        """Wait for the RefreshSeries command to complete for a given series.

        When a series is added, Sonarr triggers a background RefreshSeries command.
        Updates to the series (tags, monitored, etc.) may not work reliably until
        this command completes.
        """
        start = time.time()
        while time.time() - start < timeout:
            try:
                resp = requests.get(
                    f"{self.base_url}/api/v3/command",
                    headers=self.headers,
                    timeout=10
                )
                commands = resp.json()

                # Look for RefreshSeries command for this series
                found_pending = False
                for cmd in commands:
                    if cmd.get("commandName") == "Refresh Series":
                        body = cmd.get("body", {})
                        if series_id in body.get("seriesIds", []):
                            if cmd.get("status") == "completed":
                                return True
                            elif cmd.get("status") in ["queued", "started"]:
                                found_pending = True
                                break

                if not found_pending:
                    # No pending command found - assume complete
                    return True

            except requests.RequestException:
                pass

            time.sleep(0.3)

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
                    # Wait for background RefreshSeries command to complete
                    # This is required for subsequent updates (tags, monitored) to work
                    series_id = result.get("id")
                    if series_id:
                        self.wait_for_series_refresh(series_id)
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
        which is the most reliable approach for tag operations in Sonarr.
        """
        # Get current series to check existing tags
        resp = requests.get(
            f"{self.base_url}/api/v3/series/{series_id}",
            headers=self.headers,
            timeout=10
        )
        series = resp.json()

        # Calculate which tags need to be added
        current_tags = set(series.get("tags", []))
        tags_to_add = set(tag_ids)
        all_tags = list(current_tags | tags_to_add)

        print(f"Adding tags {tag_ids} to series {series_id}")
        print(f"Current tags: {list(current_tags)}, Target tags: {all_tags}")

        # Use series/editor endpoint with "replace" to set exact tags
        payload = {
            "seriesIds": [series_id],
            "tags": all_tags,
            "applyTags": "replace"
        }

        resp = requests.put(
            f"{self.base_url}/api/v3/series/editor",
            headers=self.headers,
            json=payload,
            timeout=10
        )

        print(f"Series editor response: {resp.status_code}")

        # Poll until the tags are confirmed or timeout
        max_attempts = 15
        for attempt in range(max_attempts):
            resp = requests.get(
                f"{self.base_url}/api/v3/series/{series_id}",
                headers=self.headers,
                timeout=10
            )
            result = resp.json()
            result_tags = set(result.get("tags", []))
            if tags_to_add.issubset(result_tags):
                print(f"Tags confirmed after {attempt + 1} attempts: {result.get('tags', [])}")
                return result
            time.sleep(0.5)

        print(f"Tags not confirmed after {max_attempts} attempts: {result.get('tags', [])}")
        return result

    def update_series_monitored(
        self, series_id: int, monitored: bool, series: Optional[Dict] = None
    ) -> Dict:
        """Update the monitored status of a series using the series/editor endpoint.

        Uses the /api/v3/series/editor endpoint which is more reliable
        for updating monitored status than the direct PUT endpoint.

        Args:
            series_id: The ID of the series to update.
            monitored: The new monitored status.
            series: Optional series object to use (for preserving tags).
                    If not provided, fetches fresh.
        """
        if series is None:
            # Get current series to capture tags
            resp = requests.get(
                f"{self.base_url}/api/v3/series/{series_id}",
                headers=self.headers,
                timeout=10
            )
            series = resp.json()

        # Capture current tags to preserve them
        current_tags = list(series.get("tags", []))

        # Use series/editor endpoint which is more reliable
        payload = {
            "seriesIds": [series_id],
            "monitored": monitored,
        }

        # Only include tags if there are any to preserve
        if current_tags:
            payload["tags"] = current_tags
            payload["applyTags"] = "replace"

        print(f"Updating series {series_id} monitored={monitored}")

        resp = requests.put(
            f"{self.base_url}/api/v3/series/editor",
            headers=self.headers,
            json=payload,
            timeout=10
        )

        print(f"Series editor response: {resp.status_code}")

        # Poll until monitored status is confirmed
        max_attempts = 15
        for attempt in range(max_attempts):
            resp = requests.get(
                f"{self.base_url}/api/v3/series/{series_id}",
                headers=self.headers,
                timeout=10
            )
            result = resp.json()
            if result.get("monitored") == monitored:
                print(f"Monitored status confirmed after {attempt + 1} attempts")
                return result
            time.sleep(0.5)

        print(f"Monitored status not confirmed after {max_attempts} attempts: {result.get('monitored')}")
        return result

    def _reapply_tags_and_monitored(
        self, series_id: int, tag_ids: List[int], monitored: bool
    ) -> Dict:
        """Re-apply tags and monitored status using the series/editor endpoint.

        The /api/v3/series/{id} PUT endpoint doesn't reliably preserve tags,
        so this method uses the dedicated /api/v3/series/editor endpoint
        which supports both tags and monitored in a single atomic operation.
        """
        payload = {
            "seriesIds": [series_id],
            "tags": tag_ids,
            "applyTags": "replace",  # Use replace to ensure exact tags
            "monitored": monitored,
        }

        print(f"Re-applying tags {tag_ids} and monitored={monitored} to series {series_id}")

        resp = requests.put(
            f"{self.base_url}/api/v3/series/editor",
            headers=self.headers,
            json=payload,
            timeout=10
        )

        # Poll until both tags and monitored are confirmed
        max_attempts = 10
        for attempt in range(max_attempts):
            resp = requests.get(
                f"{self.base_url}/api/v3/series/{series_id}",
                headers=self.headers,
                timeout=10
            )
            result = resp.json()
            tags_ok = set(tag_ids).issubset(set(result.get("tags", [])))
            monitored_ok = result.get("monitored") == monitored
            if tags_ok and monitored_ok:
                print(f"Tags and monitored re-applied successfully after {attempt + 1} attempts")
                return result
            time.sleep(0.5)

        print(f"Warning: State may not be correct. Tags: {result.get('tags', [])}, Monitored: {result.get('monitored')}")
        return result


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
