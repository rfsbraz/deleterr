"""
Root conftest.py for shared pytest configuration and fixtures.

This module provides:
- Integration test marker registration
- Common fixtures shared across all test types
"""

import pytest


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
