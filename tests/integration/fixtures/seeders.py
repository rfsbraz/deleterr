"""
Data seeders for integration testing.

These utilities populate Radarr, Sonarr, and the mock Plex server
with test data for integration tests.
"""

import requests
import time
from typing import Dict, List, Optional, Any


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
            pass
        return None

    def setup_root_folder(self, path: str = "/movies") -> Dict:
        """Create root folder for movies."""
        # Check if root folder exists
        resp = requests.get(
            f"{self.base_url}/api/v3/rootfolder",
            headers=self.headers,
            timeout=10
        )
        if resp.status_code == 200:
            folders = resp.json()
            for folder in folders:
                if folder.get("path") == path:
                    return folder

        # Create root folder
        resp = requests.post(
            f"{self.base_url}/api/v3/rootfolder",
            headers=self.headers,
            json={"path": path},
            timeout=10
        )
        return resp.json()

    def get_quality_profiles(self) -> List[Dict]:
        """Get available quality profiles."""
        resp = requests.get(
            f"{self.base_url}/api/v3/qualityprofile",
            headers=self.headers,
            timeout=10
        )
        return resp.json()

    def add_movie(self, movie_data: Dict) -> Dict:
        """Add a movie to Radarr (unmonitored, no download)."""
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
            "rootFolderPath": movie_data.get("rootFolderPath", "/movies"),
            "monitored": False,
            "addOptions": {"searchForMovie": False}
        }

        resp = requests.post(
            f"{self.base_url}/api/v3/movie",
            headers=self.headers,
            json=payload,
            timeout=30
        )
        return resp.json()

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
                pass


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
                pass
            time.sleep(2)
        return False

    def setup_root_folder(self, path: str = "/tv") -> Dict:
        """Create root folder for TV shows."""
        # Check if root folder exists
        resp = requests.get(
            f"{self.base_url}/api/v3/rootfolder",
            headers=self.headers,
            timeout=10
        )
        if resp.status_code == 200:
            folders = resp.json()
            for folder in folders:
                if folder.get("path") == path:
                    return folder

        # Create root folder
        resp = requests.post(
            f"{self.base_url}/api/v3/rootfolder",
            headers=self.headers,
            json={"path": path},
            timeout=10
        )
        return resp.json()

    def get_quality_profiles(self) -> List[Dict]:
        """Get available quality profiles."""
        resp = requests.get(
            f"{self.base_url}/api/v3/qualityprofile",
            headers=self.headers,
            timeout=10
        )
        return resp.json()

    def add_series(self, series_data: Dict) -> Dict:
        """Add a TV series to Sonarr."""
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

        resp = requests.post(
            f"{self.base_url}/api/v3/series",
            headers=self.headers,
            json=payload,
            timeout=30
        )
        return resp.json()

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
                pass


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
