import pytest
from ..utils import print_readable_freed_space

@pytest.mark.parametrize("input_size, expected_output", [
    (500, "500.00 Bytes"),
    (1024, "1.00 KB"),
    (1048576, "1.00 MB"),          # 1024 * 1024
    (1073741824, "1.00 GB"),       # 1024 * 1024 * 1024
    (1099511627776, "1.00 TB"),    # 1024 * 1024 * 1024 * 1024
    (1125899906842624, "1.00 PB")  # 1024^5
])
def test_print_readable_freed_space(input_size, expected_output):
    result = print_readable_freed_space(input_size)
    assert result == expected_output, f"For {input_size}, expected {expected_output} but got {result}"
