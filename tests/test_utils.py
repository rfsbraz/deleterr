import pytest

from app.utils import parse_size_to_bytes, print_readable_freed_space, validate_units


@pytest.mark.parametrize(
    "input_size, expected_output",
    [
        (500, "500.00 B"),
        (1024, "1.00 KB"),
        (1048576, "1.00 MB"),  # 1024 * 1024
        (1073741824, "1.00 GB"),  # 1024 * 1024 * 1024
        (1099511627776, "1.00 TB"),  # 1024 * 1024 * 1024 * 1024
        (1125899906842624, "1.00 PB"),  # 1024^5
    ],
)
def test_print_readable_freed_space(input_size, expected_output):
    result = print_readable_freed_space(input_size)
    assert (
        result == expected_output
    ), f"For {input_size}, expected {expected_output} but got {result}"


@pytest.mark.parametrize(
    "input_size, expected_output",
    [
        ("2TB", 2199023255552),
        ("2.00TB", 2199023255552),
        ("5.6GB", 6012954214),
        ("1GB", 1073741824),
        ("1 GB", 1073741824),
        ("1.00 GB", 1073741824),
        ("230MB", 241172480),
        ("1B", 1),
        ("0KB", 0),
    ],
)
def test_parse_size_to_bytes(input_size, expected_output):
    result = parse_size_to_bytes(input_size)
    assert (
        result == expected_output
    ), f"For {input_size}, expected {expected_output} but got {result}"


def test_validate_units_invalid():
    with pytest.raises(ValueError):
        validate_units("10T")


@pytest.mark.parametrize(
    "input_string",
    [
        "10B",
        "20KB",
        "30MB",
        "40GB",
        "50 TB",
        "60 PB",
        "60 EB",
    ],
)
def test_validate_units_valid(input_string):
    try:
        validate_units(input_string)
    except ValueError:
        pytest.fail("Unexpected ValueError ..")
