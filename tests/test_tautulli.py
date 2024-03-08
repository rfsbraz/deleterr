from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from app.modules.tautulli import Tautulli, filter_by_most_recent


@pytest.mark.parametrize(
    "data,key,sort_key,expected",
    [
        (
            [
                {"id": 1, "stopped": 5},
                {"id": 2, "stopped": 4},
                {"id": 1, "stopped": 6},
                {"id": 2, "stopped": 3},
            ],
            "id",
            "stopped",
            [{"id": 1, "stopped": 6}, {"id": 2, "stopped": 4}],
        )
    ],
)
def test_filter_by_most_recent(data, key, sort_key, expected):
    result = filter_by_most_recent(data, key, sort_key)
    assert result == expected


@patch("app.config.Config", Mock())
@patch("app.modules.tautulli.RawAPI", Mock())
@pytest.mark.parametrize(
    "library_config,expected_days",
    [
        ({"last_watched_threshold": 5, "added_at_threshold": 30}, 30),
        ({"last_watched_threshold": 20, "added_at_threshold": 10}, 20),
        ({"last_watched_threshold": 11, "added_at_threshold": 11}, 11),
    ],
)
def test_calculate_min_date(library_config, expected_days):
    expected = datetime.now() - timedelta(days=expected_days)

    with patch("tautulli.RawAPI", Mock()):
        tautulli = Tautulli("url", "api_key")

        result = tautulli._calculate_min_date(library_config)
        assert result.date() == expected.date()
