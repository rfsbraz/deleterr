import pytest

from app.config import Config
from app.constants import (
    SETTINGS_PER_ACTION,
    SETTINGS_PER_INSTANCE,
    VALID_ACTION_MODES,
    VALID_INSTANCE_TYPES,
    VALID_SORT_FIELDS,
    VALID_SORT_ORDERS,
)


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
