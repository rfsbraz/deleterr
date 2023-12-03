import pytest
from app.config import Config
from app.constants import VALID_SORT_FIELDS, VALID_SORT_ORDERS, VALID_ACTION_MODES

# Test case for validate_libraries
@pytest.mark.parametrize("library_config, expected_exit_code", [
    (
        {
            "name": "TV Shows",
            "action_mode": "delete",
        },
        True
    ),
    (
        {
            "name": "TV Shows",
            "action_mode": "invalid_mode",
        },
        False  # Expect False as the action_mode is invalid
    ),
])
def test_validate_action_modes(library_config, expected_exit_code):
    validator = Config({"libraries": [library_config]})
    
    with pytest.raises(SystemExit) as exc_info:
        validator.validate_libraries()
    
        assert exc_info.value.code == expected_exit_code

# Test case for validate_libraries
@pytest.mark.parametrize("library_config, expected_exit_code", [
    (
        {
            "name": "TV Shows",
            "action_mode": "delete",
            "sort": {
                "field": "invalid_field",
                "order": "asc"
            }
        },
        1
    ),
    (
        {
            "name": "TV Shows",
            "action_mode": "delete",
            "sort": {
                "field": "title",
                "order": "invalid_order"
            }
        },
        1
    ),
])
def test_invalid_sorting_options(library_config, expected_exit_code):
    validator = Config({"libraries": [library_config]})
    
    with pytest.raises(SystemExit) as exc_info:
        validator.validate_libraries()
    
        assert exc_info.value.code == expected_exit_code

# Test case for validate_libraries
@pytest.mark.parametrize("sort_field", VALID_SORT_FIELDS)
@pytest.mark.parametrize("sort_order", VALID_SORT_ORDERS)
def test_valid_sorting_options(sort_field, sort_order):
    library_config = {
        "name": "TV Shows",
        "action_mode": "delete",
        "sonarr": "test",
        "sort": {
            "field": sort_field,
            "order": sort_order
        }
    }
    
    validator = Config({"libraries": [library_config]})
    assert validator.validate_libraries() == True