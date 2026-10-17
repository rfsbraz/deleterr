# encoding: utf-8
"""Tests for how the remaining leave period is rendered in the death row log.

A leave period of "7d" that still has a few minutes left used to be logged as
"0h remaining", which reads like the item is already due for deletion. The
remainder must keep minute resolution below the hour.
"""

import logging
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.deleterr import format_remaining_duration
from app.state import StateManager


class TestFormatRemainingDuration:
    """Unit tests for format_remaining_duration."""

    def test_minutes_only(self):
        assert format_remaining_duration(timedelta(minutes=7)) == "7m"

    def test_one_minute(self):
        assert format_remaining_duration(timedelta(minutes=1)) == "1m"

    def test_hours_and_minutes(self):
        assert format_remaining_duration(timedelta(hours=5, minutes=42)) == "5h 42m"

    def test_days_and_hours(self):
        assert format_remaining_duration(timedelta(days=6, hours=3)) == "6d 3h"

    def test_less_than_a_minute(self):
        assert format_remaining_duration(timedelta(seconds=30)) == "less than a minute"

    def test_negative_is_clamped(self):
        assert format_remaining_duration(timedelta(minutes=-5)) == "less than a minute"

    def test_sub_hour_remainder_is_not_rendered_as_zero_hours(self):
        # The regression: 7 minutes left used to come out as "0h".
        assert "0h" != format_remaining_duration(timedelta(minutes=7))


class TestFilterByDurationLogging:
    """End-to-end check that _filter_by_duration logs the true remainder."""

    @pytest.fixture
    def deleterr_instance(self, tmp_path):
        state_file = str(tmp_path / ".deleterr_state.json")

        with patch("app.deleterr.MediaCleaner", return_value=MagicMock()), \
             patch("app.deleterr.PlexMediaServer", return_value=MagicMock()), \
             patch("app.deleterr.NotificationManager", return_value=MagicMock()):
            from app.deleterr import Deleterr
            config = MagicMock()
            config.settings = {
                "dry_run": False,
                "plex": {"url": "http://localhost:32400", "token": "test"},
                "sonarr": [],
                "radarr": [],
            }
            d = Deleterr.__new__(Deleterr)
            d.config = config
            d.media_server = MagicMock()
            d.media_cleaner = MagicMock()
            d.notifications = MagicMock()
            d.state_manager = StateManager(state_file=state_file)
            d.run_result = MagicMock()
            d.sonarr = {}
            d.radarr = {}
            d.libraries_processed = 0
            d.libraries_failed = 0
            return d

    def _make_plex_item(self, rating_key, title="Test Item"):
        item = MagicMock()
        item.ratingKey = rating_key
        item.title = title
        return item

    def test_logs_minutes_for_sub_hour_remainder(self, deleterr_instance, caplog):
        # Tagged 6d 23h 53m ago with a 7d duration -> 7 minutes left.
        tagged_at = (datetime.now() - timedelta(days=7) + timedelta(minutes=7)).isoformat()
        deleterr_instance.state_manager.set_tagged_dates("Movies", {"100": tagged_at})

        plex_items = [self._make_plex_item(100, "Almost Due Movie")]

        with caplog.at_level(logging.INFO, logger="deleterr"):
            eligible, skipped = deleterr_instance._filter_by_duration(
                "Movies", plex_items, "7d"
            )

        assert eligible == []
        assert skipped == 1
        assert "remaining, skipped" in caplog.text
        assert "0h remaining" not in caplog.text
        # The remainder should be expressed in minutes (7m or 6m depending on
        # the sub-second drift between tag time and the check).
        assert ("7m remaining" in caplog.text) or ("6m remaining" in caplog.text)

    def test_logs_hours_and_minutes_for_multi_hour_remainder(
        self, deleterr_instance, caplog
    ):
        tagged_at = (datetime.now() - timedelta(days=7) + timedelta(hours=5, minutes=30)).isoformat()
        deleterr_instance.state_manager.set_tagged_dates("Movies", {"200": tagged_at})

        plex_items = [self._make_plex_item(200, "Due Later Movie")]

        with caplog.at_level(logging.INFO, logger="deleterr"):
            eligible, skipped = deleterr_instance._filter_by_duration(
                "Movies", plex_items, "7d"
            )

        assert eligible == []
        assert skipped == 1
        assert "h " in caplog.text and "remaining, skipped" in caplog.text
