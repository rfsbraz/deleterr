"""Per-library logging must use the same redacted error as run reports."""
from io import StringIO
import logging
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app import logger
from app.deleterr import Deleterr
from app.media_cleaner import ConfigurationError, WatchDataError
from app.modules.mdblist import MdblistError
from app.modules.tautulli import TautulliApiError
from app.modules.trakt import TraktError


@pytest.mark.parametrize("error_type", [
    ConfigurationError, WatchDataError, TautulliApiError, TraktError, MdblistError, RuntimeError,
])
def test_library_failure_redacts_before_logging_or_recording(error_type):
    settings = {
        "radarr": [{"api_key": "synthetic-api-key"}],
        "tautulli": {"api_token": "synthetic-api-token"},
        "notifications": [{
            "password": "synthetic-password",
            "webhook_url": "https://hooks.example.test/opaque/synthetic-hook",
            "headers": {"Authorization": "Bearer synthetic-header"},
        }],
    }
    secrets = list(logger.configured_secrets(settings))
    assert len(secrets) == 5
    raw = "Request failed: " + " | ".join(secrets)
    run = Deleterr.__new__(Deleterr)
    run.config = SimpleNamespace(settings=settings)
    run.libraries_failed = 0
    run.library_failures = []

    # Check the call boundary too, so a future formatter cannot accidentally
    # expose configured values that were left in the raw logging arguments.
    with patch("app.deleterr.logger.error", wraps=logger.error) as emit:
        run._handle_library_failure("Movies", error_type(raw))
    emit.assert_called_once()
    logged = emit.call_args.args[0]
    stored = run.library_failures[0][1]
    assert run.libraries_failed == 1
    assert "Request failed" in logged
    assert stored in logged
    for secret in secrets:
        assert secret not in logged
        assert secret not in stored
    assert stored.count("[REDACTED]") == len(secrets)


@pytest.mark.parametrize("error_type", [ConfigurationError, WatchDataError, TraktError])
def test_actual_log_sink_keeps_context_without_configured_secrets(error_type):
    run = Deleterr.__new__(Deleterr)
    run.config = SimpleNamespace(settings={"api_key": "synthetic-configured-key"})
    run.libraries_failed = 0
    run.library_failures = []
    output = StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(logger.RedactingFormatter("%(levelname)s %(message)s"))
    logger.logger.addHandler(handler)
    try:
        run._handle_library_failure("Movies", error_type("Cannot read history: synthetic-configured-key"))
    finally:
        logger.logger.removeHandler(handler)
        handler.close()
    text = output.getvalue()
    assert "ERROR" in text
    assert "Cannot read history" in text
    assert "[REDACTED]" in text
    assert "synthetic-configured-key" not in text
