import os
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
import yaml

from app.config import Config, load_yaml
from app.constants import (
    SETTINGS_PER_ACTION,
    SETTINGS_PER_INSTANCE,
    VALID_ACTION_MODES,
    VALID_INSTANCE_TYPES,
    VALID_SORT_FIELDS,
    VALID_SORT_ORDERS,
)


@pytest.fixture(autouse=True)
def mock_hang_on_error():
    """Mock hang_on_error to raise SystemExit instead of hanging forever.

    This is needed because the production code hangs to prevent Docker
    restart loops, but tests need the old exit behavior.
    """
    def raise_exit(msg):
        raise SystemExit(1)

    with patch("app.config.hang_on_error", side_effect=raise_exit):
        yield


# Test case for validate_libraries
@pytest.mark.parametrize(
    "library_config",
    [
        {
            "name": "TV Shows",
            "action_mode": "delete",
            "sonarr": "test",
        }
    ],
)
def test_validate_valid_action_modes(library_config):
    sonarr_config = [
        {"name": "test", "url": "http://localhost:8989", "api_key": "API_KEY"}
    ]
    validator = Config({"libraries": [library_config], "sonarr": sonarr_config})

    assert validator.validate_libraries()


def test_validate_invalid_action_modes():
    sonarr_config = [
        {"name": "test", "url": "http://localhost:8989", "api_key": "API_KEY"}
    ]
    library_config = {
        "name": "TV Shows",
        "action_mode": "invalid_mode",
        "sonarr": "test",
    }
    validator = Config({"libraries": [library_config], "sonarr": sonarr_config})

    with pytest.raises(SystemExit):
        validator.validate_libraries()


# Test case for validate_libraries
@pytest.mark.parametrize(
    "library_config",
    [
        (
            {
                "name": "TV Shows",
                "action_mode": "delete",
                "sort": {"field": "invalid_field", "order": "asc"},
            }
        ),
        (
            {
                "name": "TV Shows",
                "action_mode": "delete",
                "sort": {"field": "title", "order": "invalid_order"},
            }
        ),
    ],
)
def test_invalid_sorting_options(library_config):
    validator = Config({"libraries": [library_config]})

    with pytest.raises(SystemExit):
        validator.validate_libraries()


@pytest.mark.parametrize("action_mode", VALID_ACTION_MODES)
@pytest.mark.parametrize("setting", SETTINGS_PER_ACTION.keys())
@pytest.mark.parametrize("instance", VALID_INSTANCE_TYPES)
def test_settings_per_instance_and_action_mode(action_mode, setting, instance):
    library_config = {
        "name": "TV Shows",
        "action_mode": action_mode,
        instance: "test",
        setting: True,
    }

    instance_config = [
        {"name": "test", "url": "http://localhost:8989", "api_key": "API_KEY"}
    ]

    validator = Config({"libraries": [library_config], instance: instance_config})

    if (
        # If the setting is valid for the action mode or the action mode is not specified
        (setting in SETTINGS_PER_ACTION and action_mode in SETTINGS_PER_ACTION[setting])
        or (setting not in SETTINGS_PER_ACTION)
    ) and (
        (
            # And if the setting is valid for the instance
            setting in SETTINGS_PER_INSTANCE
            and instance in SETTINGS_PER_INSTANCE[setting]
        )
        # Or the instance is not specified
        or (setting not in SETTINGS_PER_INSTANCE)
    ):
        # Then the validation should pass
        assert validator.validate_libraries() == True
    else:
        # Otherwise, the validation should fail
        with pytest.raises(SystemExit):
            validator.validate_libraries()


# Test case for validate_libraries
@pytest.mark.parametrize("sort_field", VALID_SORT_FIELDS)
@pytest.mark.parametrize("sort_order", VALID_SORT_ORDERS)
def test_valid_sorting_options(sort_field, sort_order):
    library_config = {
        "name": "TV Shows",
        "action_mode": "delete",
        "sonarr": "test",
        "sort": {"field": sort_field, "order": sort_order},
    }

    sonarr_config = [
        {"name": "test", "url": "http://localhost:8989", "api_key": "API_KEY"}
    ]

    validator = Config({"libraries": [library_config], "sonarr": sonarr_config})
    assert validator.validate_libraries() == True


# Test cases for JustWatch validation
class TestJustWatchValidation:
    def test_valid_justwatch_available_on(self):
        library_config = {
            "name": "Movies",
            "action_mode": "delete",
            "radarr": "test",
            "exclude": {
                "justwatch": {
                    "country": "US",
                    "available_on": ["netflix", "amazon"],
                }
            },
        }
        radarr_config = [
            {"name": "test", "url": "http://localhost:7878", "api_key": "API_KEY"}
        ]
        validator = Config({"libraries": [library_config], "radarr": radarr_config})
        assert validator.validate_libraries() == True

    def test_valid_justwatch_not_available_on(self):
        library_config = {
            "name": "Movies",
            "action_mode": "delete",
            "radarr": "test",
            "exclude": {
                "justwatch": {
                    "country": "US",
                    "not_available_on": ["netflix"],
                }
            },
        }
        radarr_config = [
            {"name": "test", "url": "http://localhost:7878", "api_key": "API_KEY"}
        ]
        validator = Config({"libraries": [library_config], "radarr": radarr_config})
        assert validator.validate_libraries() == True

    def test_valid_justwatch_with_global_country(self):
        library_config = {
            "name": "Movies",
            "action_mode": "delete",
            "radarr": "test",
            "exclude": {
                "justwatch": {
                    "available_on": ["netflix"],
                }
            },
        }
        radarr_config = [
            {"name": "test", "url": "http://localhost:7878", "api_key": "API_KEY"}
        ]
        # Global JustWatch config provides the country
        validator = Config({
            "libraries": [library_config],
            "radarr": radarr_config,
            "justwatch": {"country": "US"},
        })
        assert validator.validate_libraries() == True

    def test_invalid_justwatch_mutually_exclusive_modes(self):
        library_config = {
            "name": "Movies",
            "action_mode": "delete",
            "radarr": "test",
            "exclude": {
                "justwatch": {
                    "country": "US",
                    "available_on": ["netflix"],
                    "not_available_on": ["amazon"],  # Both modes - invalid
                }
            },
        }
        radarr_config = [
            {"name": "test", "url": "http://localhost:7878", "api_key": "API_KEY"}
        ]
        validator = Config({"libraries": [library_config], "radarr": radarr_config})

        with pytest.raises(SystemExit):
            validator.validate_libraries()

    def test_invalid_justwatch_missing_country(self):
        library_config = {
            "name": "Movies",
            "action_mode": "delete",
            "radarr": "test",
            "exclude": {
                "justwatch": {
                    "available_on": ["netflix"],
                    # Missing country - invalid
                }
            },
        }
        radarr_config = [
            {"name": "test", "url": "http://localhost:7878", "api_key": "API_KEY"}
        ]
        # No global JustWatch config either
        validator = Config({"libraries": [library_config], "radarr": radarr_config})

        with pytest.raises(SystemExit):
            validator.validate_libraries()

    def test_invalid_justwatch_providers_not_list(self):
        library_config = {
            "name": "Movies",
            "action_mode": "delete",
            "radarr": "test",
            "exclude": {
                "justwatch": {
                    "country": "US",
                    "available_on": "netflix",  # Should be a list, not a string
                }
            },
        }
        radarr_config = [
            {"name": "test", "url": "http://localhost:7878", "api_key": "API_KEY"}
        ]
        validator = Config({"libraries": [library_config], "radarr": radarr_config})

        with pytest.raises(SystemExit):
            validator.validate_libraries()

    def test_no_justwatch_config_is_valid(self):
        """Libraries without JustWatch config should still be valid."""
        library_config = {
            "name": "Movies",
            "action_mode": "delete",
            "radarr": "test",
        }
        radarr_config = [
            {"name": "test", "url": "http://localhost:7878", "api_key": "API_KEY"}
        ]
        validator = Config({"libraries": [library_config], "radarr": radarr_config})
        assert validator.validate_libraries() == True


# Test cases for preview_next schema validation
class TestPreviewNextSchema:
    """Tests for preview_next configuration field."""

    def test_preview_next_default_is_none(self):
        """preview_next defaults to None (inherit from max_actions)."""
        from app.schema import LibraryConfig

        config = LibraryConfig(name="Test", action_mode="delete", radarr="test")
        assert config.preview_next is None

    def test_preview_next_accepts_positive_int(self):
        """preview_next accepts positive integers."""
        from app.schema import LibraryConfig

        config = LibraryConfig(name="Test", action_mode="delete", radarr="test", preview_next=10)
        assert config.preview_next == 10

    def test_preview_next_accepts_zero(self):
        """preview_next accepts 0 to disable preview."""
        from app.schema import LibraryConfig

        config = LibraryConfig(name="Test", action_mode="delete", radarr="test", preview_next=0)
        assert config.preview_next == 0

    def test_preview_next_rejects_negative(self):
        """preview_next rejects negative values."""
        from app.schema import LibraryConfig
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LibraryConfig(name="Test", action_mode="delete", radarr="test", preview_next=-1)


# Test cases for env_constructor
def test_env_constructor_with_existing_variable():
    """Test that env_constructor returns the value when the environment variable exists."""
    test_env_var = "TEST_VAR_EXISTS"
    test_env_value = "test_value_123"
    os.environ[test_env_var] = test_env_value
    
    yaml_content = f"""
test_key: !env {test_env_var}
"""
    
    try:
        config = load_yaml(StringIO(yaml_content))
        
        assert config.settings['test_key'] == test_env_value
    finally:
        del os.environ[test_env_var]


def test_env_constructor_with_missing_variable():
    """Test that env_constructor raises ValueError when the environment variable doesn't exist."""
    test_env_var = "TEST_VAR_MISSING"

    if test_env_var in os.environ:
        del os.environ[test_env_var]

    yaml_content = f"""
test_key: !env {test_env_var}
"""

    with pytest.raises(ValueError):
        load_yaml(StringIO(yaml_content))


class TestRootLevelKeyValidation:
    """Tests for warning when library-level keys are placed at root level."""

    def test_warns_on_root_level_exclude(self, caplog):
        """Verify WARNING is logged when 'exclude' is at root level."""
        import logging

        config = Config({
            "exclude": {"titles": ["The Fifth Element"]},
            "libraries": [],
        })

        with caplog.at_level(logging.WARNING):
            config.validate_root_level_keys()

        assert any(
            "'exclude' found at root level" in record.message
            and "IGNORED" in record.message
            for record in caplog.records
        ), f"Expected root-level exclude warning, got: {[r.message for r in caplog.records]}"

    def test_warns_on_root_level_leaving_soon(self, caplog):
        """Verify WARNING is logged when 'leaving_soon' is at root level."""
        import logging

        config = Config({
            "leaving_soon": {"collection": {"name": "Leaving Soon"}},
            "libraries": [],
        })

        with caplog.at_level(logging.WARNING):
            config.validate_root_level_keys()

        assert any(
            "'leaving_soon' found at root level" in record.message
            for record in caplog.records
        ), f"Expected root-level leaving_soon warning, got: {[r.message for r in caplog.records]}"

    def test_warns_on_root_level_sort(self, caplog):
        """Verify WARNING is logged when 'sort' is at root level."""
        import logging

        config = Config({
            "sort": {"field": "title", "order": "asc"},
            "libraries": [],
        })

        with caplog.at_level(logging.WARNING):
            config.validate_root_level_keys()

        assert any(
            "'sort' found at root level" in record.message
            for record in caplog.records
        ), f"Expected root-level sort warning, got: {[r.message for r in caplog.records]}"

    def test_no_warning_when_exclude_under_library(self, caplog):
        """Verify no false positives when exclude is correctly under library."""
        import logging

        config = Config({
            "libraries": [
                {
                    "name": "Movies",
                    "action_mode": "delete",
                    "radarr": "test",
                    "exclude": {"titles": ["The Fifth Element"]},
                }
            ],
            "radarr": [{"name": "test", "url": "http://localhost:7878", "api_key": "API_KEY"}],
        })

        with caplog.at_level(logging.WARNING):
            config.validate_root_level_keys()

        assert not any(
            "found at root level" in record.message
            for record in caplog.records
        ), f"Should not warn when exclude is under library, got: {[r.message for r in caplog.records]}"

    def test_warns_on_multiple_root_level_keys(self, caplog):
        """Verify warnings for multiple misplaced keys."""
        import logging

        config = Config({
            "exclude": {"titles": ["Movie"]},
            "leaving_soon": {"collection": {"name": "LS"}},
            "sort": {"field": "title"},
            "libraries": [],
        })

        with caplog.at_level(logging.WARNING):
            config.validate_root_level_keys()

        warning_messages = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_messages) == 3, \
            f"Expected 3 warnings for 3 misplaced keys, got {len(warning_messages)}: {warning_messages}"


class TestTransientRetryBehavior:
    """Validation should retry transient connection errors so deleterr
    self-heals when dependencies come up after it during stack boot, but must
    fail fast on permanent errors and never restart-loop after exhausted retries.
    """

    def _build_config(self):
        return Config({
            "tautulli": {"url": "http://tautulli:8181", "api_key": "key"},
            "libraries": [
                {"name": "Movies", "action_mode": "delete", "radarr": "test"}
            ],
            "radarr": [
                {"name": "test", "url": "http://radarr:7878", "api_key": "key"}
            ],
        })

    def test_transient_failures_retry_then_succeed(self):
        config = self._build_config()
        config.VALIDATION_BASE_DELAY_SECONDS = 0
        config.VALIDATION_MAX_DELAY_SECONDS = 0

        # First two attempts fail transiently, third succeeds
        attempts = {"n": 0}

        def fake_validate_config():
            attempts["n"] += 1
            if attempts["n"] < 3:
                config._last_failure_transient = True
                return False
            return True

        with patch.object(Config, "validate_config", side_effect=fake_validate_config), \
             patch("app.config.time.sleep") as mock_sleep:
            config.validate()

        assert attempts["n"] == 3
        # Slept between attempts 1->2 and 2->3
        assert mock_sleep.call_count == 2

    def test_permanent_failure_does_not_retry(self):
        config = self._build_config()

        attempts = {"n": 0}

        def fake_validate_config():
            attempts["n"] += 1
            config._last_failure_transient = False
            return False

        with patch.object(Config, "validate_config", side_effect=fake_validate_config), \
             patch("app.config.time.sleep") as mock_sleep:
            with pytest.raises(SystemExit):
                config.validate()

        assert attempts["n"] == 1
        mock_sleep.assert_not_called()

    def test_exhausted_transient_retries_eventually_hangs(self):
        config = self._build_config()
        config.VALIDATION_BASE_DELAY_SECONDS = 0
        config.VALIDATION_MAX_DELAY_SECONDS = 0

        def fake_validate_config():
            config._last_failure_transient = True
            return False

        with patch.object(Config, "validate_config", side_effect=fake_validate_config), \
             patch("app.config.time.sleep"):
            with pytest.raises(SystemExit):
                config.validate()

    def test_tautulli_connection_refused_marks_transient(self):
        config = self._build_config()

        def raise_connection_refused():
            raise Exception(
                "HTTPConnectionPool(host='tautulli', port=8181): Max retries exceeded "
                "with url: /api/v2 (Caused by NewConnectionError('Connection refused'))"
            )

        mock_tautulli = MagicMock()
        mock_tautulli.test_connection.side_effect = raise_connection_refused

        with patch("app.config.Tautulli", return_value=mock_tautulli):
            assert config._validate_tautulli_watch_provider() is False

        assert config._last_failure_transient is True

    def test_tautulli_auth_failure_does_not_mark_transient(self):
        config = self._build_config()

        def raise_unauthorized():
            raise Exception("HTTP 401 Unauthorized: invalid API key")

        mock_tautulli = MagicMock()
        mock_tautulli.test_connection.side_effect = raise_unauthorized

        with patch("app.config.Tautulli", return_value=mock_tautulli):
            assert config._validate_tautulli_watch_provider() is False

        assert config._last_failure_transient is False

    def test_radarr_connection_refused_marks_transient(self):
        from app.config import test_radarr_connection
        import requests as req

        config = self._build_config()
        connection = {
            "name": "Radarr",
            "url": "http://radarr:7878",
            "api_key": "key",
        }

        with patch("app.config.requests.get", side_effect=req.exceptions.ConnectionError("refused")):
            assert test_radarr_connection(connection, config=config) is False

        assert config._last_failure_transient is True

    def test_radarr_401_does_not_mark_transient(self):
        from app.config import test_radarr_connection
        import requests as req

        config = self._build_config()
        connection = {
            "name": "Radarr",
            "url": "http://radarr:7878",
            "api_key": "key",
        }

        response = MagicMock()
        response.status_code = 401
        response.raise_for_status.side_effect = req.exceptions.HTTPError(response=response)

        with patch("app.config.requests.get", return_value=response):
            assert test_radarr_connection(connection, config=config) is False

        assert config._last_failure_transient is False

    def test_sonarr_connection_refused_marks_transient(self):
        import requests as req

        config = self._build_config()
        connection = {
            "name": "Sonarr",
            "url": "http://sonarr:8989",
            "api_key": "key",
        }

        with patch("app.config.requests.get", side_effect=req.exceptions.ConnectionError("refused")):
            assert config.test_api_connection(connection) is False

        assert config._last_failure_transient is True
