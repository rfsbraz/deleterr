import pytest
from unittest.mock import patch, Mock
from ..modules.tautulli import Tautulli, filter_by_most_recent
from datetime import datetime

@pytest.mark.parametrize("data,key,sort_key,expected", [
    (
        [{'id': 1, 'stopped': 5}, {'id': 2, 'stopped': 4}, {'id': 1, 'stopped': 6}, {'id': 2, 'stopped': 3}],
        'id', 'stopped',
        [{'id': 1, 'stopped': 6}, {'id': 2, 'stopped': 4}]
    )
])
def test_filter_by_most_recent(data, key, sort_key, expected):
    result = filter_by_most_recent(data, key, sort_key)
    assert result == expected