"""
Root conftest.py for shared pytest configuration and fixtures.

This module provides:
- Integration test marker registration
- Common fixtures shared across all test types
"""

import os

import pytest


# JustWatch proxy URL for integration tests
JUSTWATCH_PROXY_URL = os.getenv("JUSTWATCH_PROXY_URL", "http://localhost:8888")


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (require Docker services)"
    )
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow-running"
    )


def pytest_collection_modifyitems(config, items):
    """
    Modify test collection to skip integration tests by default.

    Integration tests are only run when explicitly requested with -m integration.
    """
    # Check if integration marker is being explicitly selected
    markexpr = config.getoption("-m", default="")

    if "integration" not in markexpr:
        # Skip integration tests if not explicitly requested
        skip_integration = pytest.mark.skip(
            reason="Integration tests require -m integration flag"
        )
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)


@pytest.fixture(scope="session", autouse=True)
def setup_justwatch_proxy_for_integration(request):
    """
    Auto-use fixture that sets up the JustWatch proxy URL for integration tests.

    This ensures the JustWatch module uses the caching proxy instead of
    hitting the real API during integration tests.
    """
    # Only set up proxy if running integration tests
    markexpr = request.config.getoption("-m", default="")
    if "integration" in markexpr:
        os.environ["JUSTWATCH_API_URL"] = f"{JUSTWATCH_PROXY_URL}/graphql"
        print(f"\nJustWatch proxy enabled: {JUSTWATCH_PROXY_URL}/graphql")
