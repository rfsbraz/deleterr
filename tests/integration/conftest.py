"""
pytest fixtures for integration tests.

This module provides fixtures for:
- Docker container lifecycle management
- API clients for Radarr, Sonarr, Tautulli
- Test data seeding and cleanup
"""

import os
import re
import subprocess
import time
import json
import pytest
import requests
from pathlib import Path
from typing import Generator

from pyarr.radarr import RadarrAPI
from pyarr.sonarr import SonarrAPI

from app.modules.radarr import DRadarr
from app.modules.sonarr import DSonarr

from tests.integration.fixtures.seeders import (
    RadarrSeeder,
    SonarrSeeder,
    PlexMockSeeder,
    TautulliSeeder,
)

# Directory containing docker-compose file
INTEGRATION_DIR = Path(__file__).parent
COMPOSE_FILE = INTEGRATION_DIR / "docker-compose.integration.yml"

# Service URLs
RADARR_URL = os.getenv("RADARR_URL", "http://localhost:7878")
SONARR_URL = os.getenv("SONARR_URL", "http://localhost:8989")
TAUTULLI_URL = os.getenv("TAUTULLI_URL", "http://localhost:8181")
PLEX_MOCK_URL = os.getenv("PLEX_MOCK_URL", "http://localhost:32400")
WEBHOOK_RECEIVER_URL = os.getenv("WEBHOOK_RECEIVER_URL", "http://localhost:8080")
JUSTWATCH_PROXY_URL = os.getenv("JUSTWATCH_PROXY_URL", "http://localhost:8888")

# API Keys - these will be extracted from the containers after startup
# or can be pre-set via environment variables
RADARR_API_KEY = os.getenv("RADARR_API_KEY", "")
SONARR_API_KEY = os.getenv("SONARR_API_KEY", "")
TAUTULLI_API_KEY = os.getenv("TAUTULLI_API_KEY", "")
PLEX_TOKEN = os.getenv("PLEX_TOKEN", "test-plex-token")

# Timeouts
STARTUP_TIMEOUT = 180  # seconds to wait for services


def docker_compose_up():
    """Start all test containers."""
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d", "--build"],
        check=True,
        cwd=str(INTEGRATION_DIR),
    )


def docker_compose_down():
    """Stop and remove all test containers."""
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "down", "-v", "--remove-orphans"],
        check=False,  # Don't fail if already down
        cwd=str(INTEGRATION_DIR),
    )


def get_container_api_key(container_name: str, config_path: str) -> str:
    """Extract API key from a container's config file."""
    try:
        result = subprocess.run(
            ["docker", "exec", container_name, "cat", config_path],
            capture_output=True,
            text=True,
            check=True,
        )
        # Parse XML config to extract ApiKey
        match = re.search(r"<ApiKey>([^<]+)</ApiKey>", result.stdout)
        if match:
            return match.group(1)
    except (subprocess.CalledProcessError, Exception):
        # API key extraction is best-effort; return empty string on failure
        pass
    return ""


def _verify_service_api_ready(url: str, api_key: str, timeout: int = 30) -> bool:
    """
    Verify a service's API is fully ready by checking system status endpoint.

    This is more reliable than just checking /ping, as the API may respond
    to ping before the database and internal state are fully initialized.
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(
                f"{url}/api/v3/system/status",
                headers={"X-Api-Key": api_key},
                timeout=5
            )
            if resp.status_code == 200:
                return True
        except requests.RequestException:
            # Transient connection errors during startup; retry loop continues
            pass
        time.sleep(2)
    return False


def wait_for_services(timeout: int = STARTUP_TIMEOUT) -> dict:
    """
    Wait for all services to be healthy and extract API keys.

    Returns dict with API keys for each service.
    """
    api_keys = {
        "radarr": RADARR_API_KEY,
        "sonarr": SONARR_API_KEY,
        "tautulli": TAUTULLI_API_KEY,
    }

    start = time.time()

    # Wait for Plex mock first (it's fastest)
    plex_ready = False
    while time.time() - start < timeout and not plex_ready:
        try:
            resp = requests.get(f"{PLEX_MOCK_URL}/health", timeout=5)
            if resp.status_code == 200:
                plex_ready = True
        except requests.RequestException:
            # Service may not be ready yet; retry loop continues
            pass
        if not plex_ready:
            time.sleep(2)

    if not plex_ready:
        raise RuntimeError("Plex mock did not start in time")

    # Wait for Radarr
    radarr_ready = False
    while time.time() - start < timeout and not radarr_ready:
        try:
            # Try ping endpoint (no auth required)
            resp = requests.get(f"{RADARR_URL}/ping", timeout=5)
            if resp.status_code == 200:
                # Extract API key if not set
                if not api_keys["radarr"]:
                    api_keys["radarr"] = get_container_api_key(
                        "deleterr-test-radarr", "/config/config.xml"
                    )
                # Verify API is fully ready (not just responding to ping)
                if api_keys["radarr"] and _verify_service_api_ready(
                    RADARR_URL, api_keys["radarr"], timeout=30
                ):
                    radarr_ready = True
        except requests.RequestException:
            # Service may not be ready yet; retry loop continues
            pass
        if not radarr_ready:
            time.sleep(2)

    if not radarr_ready:
        raise RuntimeError("Radarr did not start in time or API is not ready")

    # Wait for Sonarr
    sonarr_ready = False
    while time.time() - start < timeout and not sonarr_ready:
        try:
            resp = requests.get(f"{SONARR_URL}/ping", timeout=5)
            if resp.status_code == 200:
                if not api_keys["sonarr"]:
                    api_keys["sonarr"] = get_container_api_key(
                        "deleterr-test-sonarr", "/config/config.xml"
                    )
                # Verify API is fully ready (not just responding to ping)
                if api_keys["sonarr"] and _verify_service_api_ready(
                    SONARR_URL, api_keys["sonarr"], timeout=30
                ):
                    sonarr_ready = True
        except requests.RequestException:
            # Service may not be ready yet; retry loop continues
            pass
        if not sonarr_ready:
            time.sleep(2)

    if not sonarr_ready:
        raise RuntimeError("Sonarr did not start in time or API is not ready")

    # Wait for Tautulli
    tautulli_ready = False
    while time.time() - start < timeout and not tautulli_ready:
        try:
            resp = requests.get(f"{TAUTULLI_URL}/status", timeout=5)
            if resp.status_code == 200:
                tautulli_ready = True
                # Extract Tautulli API key from config
                if not api_keys["tautulli"]:
                    result = subprocess.run(
                        ["docker", "exec", "deleterr-test-tautulli",
                         "cat", "/config/config.ini"],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0:
                        match = re.search(r"api_key\s*=\s*(\S+)", result.stdout)
                        if match:
                            api_keys["tautulli"] = match.group(1)
        except requests.RequestException:
            # Service may not be ready yet; retry loop continues
            pass
        if not tautulli_ready:
            time.sleep(2)

    if not tautulli_ready:
        raise RuntimeError("Tautulli did not start in time")

    # Wait for Webhook receiver (fastest startup)
    webhook_ready = False
    while time.time() - start < timeout and not webhook_ready:
        try:
            resp = requests.get(f"{WEBHOOK_RECEIVER_URL}/health", timeout=5)
            if resp.status_code == 200:
                webhook_ready = True
        except requests.RequestException:
            # Service may not be ready yet; retry loop continues
            pass
        if not webhook_ready:
            time.sleep(2)

    if not webhook_ready:
        raise RuntimeError("Webhook receiver did not start in time")

    # Wait for JustWatch proxy
    justwatch_ready = False
    while time.time() - start < timeout and not justwatch_ready:
        try:
            resp = requests.get(f"{JUSTWATCH_PROXY_URL}/health", timeout=5)
            if resp.status_code == 200:
                justwatch_ready = True
        except requests.RequestException:
            # Service may not be ready yet; retry loop continues
            pass
        if not justwatch_ready:
            time.sleep(2)

    if not justwatch_ready:
        raise RuntimeError("JustWatch proxy did not start in time")

    return api_keys


@pytest.fixture(scope="session")
def docker_services() -> Generator[dict, None, None]:
    """
    Session-scoped fixture that manages Docker container lifecycle.

    Starts containers before tests, extracts API keys, tears down after.
    Returns dict with API keys.
    """
    # Set JustWatch API URL to use the proxy
    os.environ["JUSTWATCH_API_URL"] = f"{JUSTWATCH_PROXY_URL}/graphql"

    # Check if we should use external services (already running)
    if os.getenv("USE_EXTERNAL_SERVICES", "false").lower() == "true":
        yield {
            "radarr": RADARR_API_KEY,
            "sonarr": SONARR_API_KEY,
            "tautulli": TAUTULLI_API_KEY,
        }
        return

    # Start containers
    print("\nStarting Docker containers...")
    docker_compose_up()

    try:
        # Wait for services and get API keys
        print("Waiting for services to be ready...")
        api_keys = wait_for_services()
        print(f"Services ready. API keys extracted.")
        print(f"JustWatch proxy URL: {JUSTWATCH_PROXY_URL}")

        yield api_keys

    finally:
        # Cleanup
        print("\nStopping Docker containers...")
        docker_compose_down()


@pytest.fixture(scope="session")
def radarr_api_key(docker_services) -> str:
    """Get Radarr API key."""
    return docker_services["radarr"]


@pytest.fixture(scope="session")
def sonarr_api_key(docker_services) -> str:
    """Get Sonarr API key."""
    return docker_services["sonarr"]


@pytest.fixture(scope="session")
def tautulli_api_key(docker_services) -> str:
    """Get Tautulli API key."""
    return docker_services["tautulli"]


@pytest.fixture(scope="session")
def radarr_client(radarr_api_key) -> RadarrAPI:
    """Provides a configured Radarr API client."""
    return RadarrAPI(RADARR_URL, radarr_api_key)


@pytest.fixture(scope="session")
def sonarr_client(sonarr_api_key) -> SonarrAPI:
    """Provides a configured Sonarr API client."""
    return SonarrAPI(SONARR_URL, sonarr_api_key)


@pytest.fixture(scope="session")
def dradarr_client(radarr_api_key) -> DRadarr:
    """Provides a configured DRadarr wrapper client.

    This tests the application's wrapper class, not pyarr directly.
    """
    return DRadarr("TestRadarr", RADARR_URL, radarr_api_key)


@pytest.fixture(scope="session")
def dsonarr_client(sonarr_api_key) -> DSonarr:
    """Provides a configured DSonarr wrapper client.

    This tests the application's wrapper class, not pyarr directly.
    """
    return DSonarr("TestSonarr", SONARR_URL, sonarr_api_key)


@pytest.fixture(scope="session")
def radarr_seeder(radarr_api_key) -> RadarrSeeder:
    """Provides a Radarr data seeder."""
    seeder = RadarrSeeder(RADARR_URL, radarr_api_key)
    return seeder


@pytest.fixture(scope="session")
def sonarr_seeder(sonarr_api_key) -> SonarrSeeder:
    """Provides a Sonarr data seeder."""
    seeder = SonarrSeeder(SONARR_URL, sonarr_api_key)
    return seeder


@pytest.fixture(scope="session")
def plex_mock_seeder(docker_services) -> PlexMockSeeder:
    """Provides a mock Plex data seeder."""
    seeder = PlexMockSeeder(PLEX_MOCK_URL)
    return seeder


@pytest.fixture(scope="session")
def tautulli_seeder(tautulli_api_key) -> TautulliSeeder:
    """Provides a Tautulli seeder."""
    seeder = TautulliSeeder(TAUTULLI_URL, tautulli_api_key)
    return seeder


@pytest.fixture(scope="session")
def seeded_radarr(radarr_seeder, radarr_client) -> Generator[RadarrAPI, None, None]:
    """
    Provides a Radarr instance with seeded test data.
    Cleans up data after tests.
    """
    seed_file = INTEGRATION_DIR / "seed_data" / "radarr" / "movies.json"
    with open(seed_file) as f:
        test_data = json.load(f)

    # Setup root folder
    print("\nSetting up Radarr root folder...")
    root_result = radarr_seeder.setup_root_folder("/movies")
    print(f"Root folder result: {root_result}")

    # Fail fast if root folder setup failed
    if "error" in root_result:
        pytest.fail(f"Failed to setup Radarr root folder: {root_result['error']}")

    # Seed movies
    print(f"Seeding {len(test_data['test_movies'])} movies...")
    seeded_movies = radarr_seeder.seed_test_movies(test_data["test_movies"])
    print(f"Successfully seeded {len(seeded_movies)} movies")

    if not seeded_movies:
        pytest.fail("Failed to seed any movies - check Radarr API connectivity")

    yield radarr_client

    # Cleanup: delete all seeded movies
    for movie in seeded_movies:
        try:
            radarr_client.del_movie(movie["id"], delete_files=True)
        except Exception:
            # Best-effort cleanup; don't fail tests on cleanup errors
            pass


@pytest.fixture(scope="session")
def seeded_sonarr(sonarr_seeder, sonarr_client) -> Generator[SonarrAPI, None, None]:
    """
    Provides a Sonarr instance with seeded test data.
    Cleans up data after tests.
    """
    seed_file = INTEGRATION_DIR / "seed_data" / "sonarr" / "series.json"
    with open(seed_file) as f:
        test_data = json.load(f)

    # Setup root folder
    print("\nSetting up Sonarr root folder...")
    root_result = sonarr_seeder.setup_root_folder("/tv")
    print(f"Root folder result: {root_result}")

    # Fail fast if root folder setup failed
    if "error" in root_result:
        pytest.fail(f"Failed to setup Sonarr root folder: {root_result['error']}")

    # Seed series
    print(f"Seeding {len(test_data['test_series'])} series...")
    seeded_series = sonarr_seeder.seed_test_series(test_data["test_series"])
    print(f"Successfully seeded {len(seeded_series)} series")

    if not seeded_series:
        pytest.fail("Failed to seed any series - check Sonarr API connectivity")

    yield sonarr_client

    # Cleanup: delete all seeded series
    for series in seeded_series:
        try:
            sonarr_client.del_series(series["id"], delete_files=True)
        except Exception:
            # Best-effort cleanup; don't fail tests on cleanup errors
            pass


@pytest.fixture
def integration_config(docker_services):
    """
    Provides a test configuration dict matching the app's expected format.
    """
    return {
        "dry_run": True,  # Default to dry run for safety
        "action_delay": 0,
        "plex": {
            "url": PLEX_MOCK_URL,
            "token": PLEX_TOKEN
        },
        "tautulli": {
            "url": TAUTULLI_URL,
            "api_key": docker_services["tautulli"]
        },
        "sonarr": [
            {
                "name": "Sonarr",
                "url": SONARR_URL,
                "api_key": docker_services["sonarr"]
            }
        ],
        "radarr": [
            {
                "name": "Radarr",
                "url": RADARR_URL,
                "api_key": docker_services["radarr"]
            }
        ],
        "libraries": [
            {
                "name": "Movies",
                "radarr": "Radarr",
                "action_mode": "delete",
                "last_watched_threshold": 30,
                "added_at_threshold": 7,
                "max_actions_per_run": 10
            },
            {
                "name": "TV Shows",
                "sonarr": "Sonarr",
                "action_mode": "delete",
                "series_type": "standard",
                "last_watched_threshold": 30,
                "added_at_threshold": 7,
                "max_actions_per_run": 10
            }
        ]
    }


# Webhook receiver fixtures


@pytest.fixture(scope="session")
def webhook_receiver_url(docker_services) -> str:
    """URL for the webhook receiver service."""
    return WEBHOOK_RECEIVER_URL


@pytest.fixture
def clean_webhook_receiver(webhook_receiver_url):
    """
    Reset webhook receiver before each test for isolation.

    Clears captured webhooks before and after each test.
    """
    requests.post(f"{webhook_receiver_url}/api/reset", timeout=5)
    yield webhook_receiver_url
    requests.post(f"{webhook_receiver_url}/api/reset", timeout=5)


@pytest.fixture
def webhook_helper(clean_webhook_receiver):
    """
    Helper class for webhook verification in tests.

    Provides methods to retrieve and verify captured webhooks.
    """
    class WebhookHelper:
        def __init__(self, base_url: str):
            self.base_url = base_url

        def get_all_webhooks(self) -> list:
            """Get all captured webhooks."""
            resp = requests.get(f"{self.base_url}/api/webhooks", timeout=5)
            resp.raise_for_status()
            return resp.json().get("webhooks", [])

        def get_latest_webhook(self) -> dict:
            """Get the most recently captured webhook."""
            resp = requests.get(f"{self.base_url}/api/webhooks/latest", timeout=5)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()

        def get_webhook_count(self) -> int:
            """Get count of captured webhooks."""
            resp = requests.get(f"{self.base_url}/api/webhooks/count", timeout=5)
            resp.raise_for_status()
            return resp.json().get("count", 0)

        def get_webhooks_by_path(self, path: str) -> list:
            """Get all webhooks captured at a specific path."""
            resp = requests.get(
                f"{self.base_url}/api/webhooks/by-path/{path.lstrip('/')}",
                timeout=5
            )
            resp.raise_for_status()
            return resp.json().get("webhooks", [])

        def wait_for_webhook(self, timeout: float = 5.0, poll_interval: float = 0.1) -> dict:
            """Wait for a webhook to be received."""
            import time
            start = time.time()
            while time.time() - start < timeout:
                webhook = self.get_latest_webhook()
                if webhook:
                    return webhook
                time.sleep(poll_interval)
            return None

        def reset(self) -> None:
            """Reset all captured webhooks."""
            requests.post(f"{self.base_url}/api/reset", timeout=5)

    return WebhookHelper(clean_webhook_receiver)
