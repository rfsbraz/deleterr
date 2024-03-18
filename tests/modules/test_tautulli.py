from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.modules.tautulli import HISTORY_PAGE_SIZE, Tautulli, filter_by_most_recent


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


def test_determine_key():
    # Arrange
    tautulli_instance = Tautulli("id", "secret")

    # Act and Assert
    # Test with grandparent_rating_key
    result = tautulli_instance._determine_key([{"grandparent_rating_key": "123"}])
    assert result == "grandparent_rating_key"

    # Test without grandparent_rating_key
    result = tautulli_instance._determine_key([{}])
    assert result == "rating_key"


@patch(
    "app.modules.tautulli.RawAPI",
    return_value=MagicMock(
        get_history=MagicMock(side_effect=[{"data": ["item1", "item2"]}, {"data": []}])
    ),
)
def test_fetch_history_data(mock_api):
    # Arrange
    tautulli_instance = Tautulli("id", "secret")
    section = "test_section"
    min_date = "2022-01-01"

    # Act
    result = tautulli_instance._fetch_history_data(section, min_date)

    # Assert
    assert result == ["item1", "item2"]

    mock_api.return_value.get_history.assert_any_call(
        section_id=section,
        order_column="date",
        order_direction="asc",
        start=0,
        after=min_date,
        length=HISTORY_PAGE_SIZE,
        include_activity=1,
    )
    mock_api.return_value.get_history.assert_any_call(
        section_id=section,
        order_column="date",
        order_direction="asc",
        start=2,
        after=min_date,
        length=HISTORY_PAGE_SIZE,
        include_activity=1,
    )


@patch.object(Tautulli, "_calculate_min_date", return_value="2022-01-01")
@patch.object(
    Tautulli,
    "_fetch_history_data",
    return_value=[{"rating_key": "123", "stopped": "2022-01-02"}],
)
@patch.object(Tautulli, "_determine_key", return_value="rating_key")
@patch.object(Tautulli, "_prepare_activity_entry", return_value="prepared_entry")
def test_get_activity(
    mock_prepare_activity_entry,
    mock_determine_key,
    mock_fetch_history_data,
    mock_calculate_min_date,
):
    # Arrange
    tautulli_instance = Tautulli("id", "secret")
    tautulli_instance.api = MagicMock(
        get_metadata=MagicMock(return_value={"guid": "guid"})
    )
    library_config = {}
    section = "section"

    # Act
    result = tautulli_instance.get_activity(library_config, section)

    # Assert
    assert result == {"guid": "prepared_entry"}
    mock_calculate_min_date.assert_called_once_with(library_config)
    mock_fetch_history_data.assert_called_once_with(section, "2022-01-01")
    mock_determine_key.assert_called_once_with(
        [{"rating_key": "123", "stopped": "2022-01-02"}]
    )
    mock_prepare_activity_entry.assert_called_once_with(
        {"rating_key": "123", "stopped": "2022-01-02"}, {"guid": "guid"}
    )
