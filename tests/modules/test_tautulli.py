from datetime import datetime
from unittest.mock import MagicMock, patch

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


@patch("app.modules.tautulli.RawAPI", MagicMock())
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

    # Act
    result = tautulli_instance._fetch_history_data(section)

    # Assert
    assert result == ["item1", "item2"]

    mock_api.return_value.get_history.assert_any_call(
        section_id=section,
        order_column="date",
        order_direction="asc",
        start=0,
        length=HISTORY_PAGE_SIZE,
        include_activity=1,
    )
    mock_api.return_value.get_history.assert_any_call(
        section_id=section,
        order_column="date",
        order_direction="asc",
        start=2,
        length=HISTORY_PAGE_SIZE,
        include_activity=1,
    )


@patch("app.modules.tautulli.RawAPI", MagicMock())
@patch.object(
    Tautulli,
    "_fetch_history_data",
    return_value=[{"rating_key": "123", "stopped": 1641081600, "guid": "plex://movie/abc123", "title": "Test Movie", "year": 2022}],
)
def test_get_activity(mock_fetch_history_data):
    """Test that get_activity extracts data directly from history without metadata calls."""
    # Arrange
    tautulli_instance = Tautulli("id", "secret")
    section = "section"

    # Act
    result = tautulli_instance.get_activity(section)

    # Assert - verify data extracted directly from history response
    assert "plex://movie/abc123" in result
    assert result["plex://movie/abc123"]["title"] == "Test Movie"
    assert result["plex://movie/abc123"]["year"] == 2022
    mock_fetch_history_data.assert_called_once_with(section)


@patch("app.modules.tautulli.RawAPI", MagicMock())
@patch.object(
    Tautulli,
    "_fetch_history_data",
    return_value=[{"grandparent_rating_key": "123", "stopped": 1641081600, "guid": "plex://show/abc123", "grandparent_title": "Test Show", "title": "Episode 1", "year": 2022}],
)
def test_get_activity_tv_show(mock_fetch_history_data):
    """Test that get_activity uses grandparent_title for TV shows."""
    # Arrange
    tautulli_instance = Tautulli("id", "secret")
    section = "section"

    # Act
    result = tautulli_instance.get_activity(section)

    # Assert - verify grandparent_title is used for TV shows
    assert "plex://show/abc123" in result
    assert result["plex://show/abc123"]["title"] == "Test Show"  # Uses grandparent_title


@patch("app.modules.tautulli.RawAPI", MagicMock())
@patch.object(Tautulli, "_fetch_history_data", return_value=[])
def test_get_activity_without_tautulli_items(mock_fetch_history_data):
    """Test that get_activity returns empty dict when no history data."""
    # Arrange
    tautulli_instance = Tautulli("id", "secret")
    section = "section"

    # Act
    result = tautulli_instance.get_activity(section)

    # Assert
    assert result == {}
    mock_fetch_history_data.assert_called_once_with(section)


@patch("app.modules.tautulli.RawAPI", MagicMock())
@patch.object(
    Tautulli,
    "_fetch_history_data",
    return_value=[{"rating_key": "123", "stopped": 1641081600, "title": "Test Movie", "year": 2022}],  # Missing guid
)
def test_get_activity_skips_entries_without_guid(mock_fetch_history_data):
    """Test that entries without guid are skipped."""
    # Arrange
    tautulli_instance = Tautulli("id", "secret")
    section = "section"

    # Act
    result = tautulli_instance.get_activity(section)

    # Assert - no entries added without guid
    assert result == {}


@patch("app.modules.tautulli.RawAPI", MagicMock())
def test_prepare_activity_entry_movie():
    """Test _prepare_activity_entry extracts correct data for movies."""
    tautulli_instance = Tautulli("id", "secret")

    entry = {
        "stopped": 1641081600,  # 2022-01-02 00:00:00 UTC
        "title": "Test Movie",
        "year": 2022,
    }

    result = tautulli_instance._prepare_activity_entry(entry)

    assert result["title"] == "Test Movie"
    assert result["year"] == 2022
    assert result["last_watched"] == datetime.fromtimestamp(1641081600)


@patch("app.modules.tautulli.RawAPI", MagicMock())
def test_prepare_activity_entry_tv_show():
    """Test _prepare_activity_entry uses grandparent_title for TV shows."""
    tautulli_instance = Tautulli("id", "secret")

    entry = {
        "stopped": 1641081600,
        "grandparent_title": "Breaking Bad",  # Series name
        "title": "Pilot",  # Episode name
        "year": 2008,
    }

    result = tautulli_instance._prepare_activity_entry(entry)

    # Should use grandparent_title (series name), not episode title
    assert result["title"] == "Breaking Bad"
    assert result["year"] == 2008


@patch("app.modules.tautulli.RawAPI", MagicMock())
def test_prepare_activity_entry_missing_year():
    """Test _prepare_activity_entry handles missing year gracefully."""
    tautulli_instance = Tautulli("id", "secret")

    entry = {
        "stopped": 1641081600,
        "title": "Test Movie",
        # year is missing
    }

    result = tautulli_instance._prepare_activity_entry(entry)

    assert result["title"] == "Test Movie"
    assert result["year"] == 0  # Should default to 0
