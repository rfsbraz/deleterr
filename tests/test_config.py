import pytest

from app.config import Config
from app.constants import VALID_ACTION_MODES, VALID_SORT_FIELDS, VALID_SORT_ORDERS


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
