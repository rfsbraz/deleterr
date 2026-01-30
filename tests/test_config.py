import os
from io import StringIO
from unittest.mock import patch

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
