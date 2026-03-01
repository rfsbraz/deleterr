# encoding: utf-8
"""Unit tests for leaving_soon duration parsing and deletion date computation."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.media_cleaner import parse_leaving_soon_duration, compute_deletion_date
from app.schema import LeavingSoonConfig


class TestParseLeavingSoonDuration:
    """Tests for parse_leaving_soon_duration function."""

    def test_parse_days(self):
        """Test parsing day durations."""
        assert parse_leaving_soon_duration("7d") == timedelta(days=7)
        assert parse_leaving_soon_duration("1d") == timedelta(days=1)
        assert parse_leaving_soon_duration("30d") == timedelta(days=30)
        assert parse_leaving_soon_duration("365d") == timedelta(days=365)

    def test_parse_hours(self):
        """Test parsing hour durations."""
        assert parse_leaving_soon_duration("24h") == timedelta(hours=24)
        assert parse_leaving_soon_duration("1h") == timedelta(hours=1)
        assert parse_leaving_soon_duration("48h") == timedelta(hours=48)
        assert parse_leaving_soon_duration("168h") == timedelta(hours=168)

    def test_parse_with_whitespace(self):
        """Test parsing with surrounding whitespace."""
        assert parse_leaving_soon_duration("  7d  ") == timedelta(days=7)
        assert parse_leaving_soon_duration(" 24h ") == timedelta(hours=24)

    def test_parse_case_insensitive(self):
        """Test parsing is case insensitive."""
        assert parse_leaving_soon_duration("7D") == timedelta(days=7)
        assert parse_leaving_soon_duration("24H") == timedelta(hours=24)

    def test_invalid_format_no_unit(self):
        """Test that missing unit raises ValueError."""
        with pytest.raises(ValueError, match="Invalid duration format"):
            parse_leaving_soon_duration("7")

    def test_invalid_format_bad_unit(self):
        """Test that invalid unit raises ValueError."""
        with pytest.raises(ValueError, match="Invalid duration format"):
            parse_leaving_soon_duration("7m")

    def test_invalid_format_text(self):
        """Test that text input raises ValueError."""
        with pytest.raises(ValueError, match="Invalid duration format"):
            parse_leaving_soon_duration("seven days")

    def test_invalid_empty_string(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid duration"):
            parse_leaving_soon_duration("")

    def test_invalid_none(self):
        """Test that None raises ValueError."""
        with pytest.raises(ValueError, match="Invalid duration"):
            parse_leaving_soon_duration(None)

    def test_zero_duration(self):
        """Test that zero duration raises ValueError."""
        with pytest.raises(ValueError, match="Duration must be positive"):
            parse_leaving_soon_duration("0d")


class TestComputeDeletionDate:
    """Tests for compute_deletion_date function."""

    def test_with_duration(self):
        """Test computing deletion date from explicit duration."""
        result = compute_deletion_date(duration_str="7d")
        assert result is not None
        # Should be roughly 7 days from now
        expected = datetime.now() + timedelta(days=7)
        assert abs((result - expected).total_seconds()) < 2

    def test_with_duration_hours(self):
        """Test computing deletion date from hours duration."""
        result = compute_deletion_date(duration_str="24h")
        assert result is not None
        expected = datetime.now() + timedelta(hours=24)
        assert abs((result - expected).total_seconds()) < 2

    def test_with_schedule_preset(self):
        """Test computing deletion date from schedule preset."""
        result = compute_deletion_date(schedule="daily")
        assert result is not None
        # Should be in the future
        assert result > datetime.now()

    def test_with_schedule_cron(self):
        """Test computing deletion date from cron expression."""
        result = compute_deletion_date(schedule="0 3 * * *")
        assert result is not None
        assert result > datetime.now()

    def test_duration_takes_priority_over_schedule(self):
        """Test that explicit duration takes priority over schedule."""
        result = compute_deletion_date(duration_str="7d", schedule="daily")
        assert result is not None
        expected = datetime.now() + timedelta(days=7)
        assert abs((result - expected).total_seconds()) < 2

    def test_with_neither(self):
        """Test that None is returned when neither is provided."""
        result = compute_deletion_date()
        assert result is None

    def test_with_invalid_duration_falls_back_to_schedule(self):
        """Test that invalid duration falls back to schedule."""
        result = compute_deletion_date(duration_str="invalid", schedule="daily")
        assert result is not None
        # Should be from schedule, in the future
        assert result > datetime.now()

    def test_with_invalid_schedule(self):
        """Test that invalid schedule returns None."""
        result = compute_deletion_date(schedule="not-a-cron")
        assert result is None


class TestLeavingSoonConfigDuration:
    """Tests for duration field in LeavingSoonConfig schema."""

    def test_default_duration_is_none(self):
        """Test that duration defaults to None."""
        config = LeavingSoonConfig()
        assert config.duration is None

    def test_with_duration_set(self):
        """Test setting duration value."""
        config = LeavingSoonConfig(duration="7d")
        assert config.duration == "7d"

    def test_with_duration_and_collection(self):
        """Test duration alongside collection config."""
        config = LeavingSoonConfig(
            duration="24h",
            collection={"name": "Leaving Soon"},
        )
        assert config.duration == "24h"
        assert config.collection.name == "Leaving Soon"

    def test_from_dict(self):
        """Test creating config with duration from dictionary."""
        data = {
            "duration": "30d",
            "collection": {"name": "Leaving Soon"},
        }
        config = LeavingSoonConfig(**data)
        assert config.duration == "30d"
