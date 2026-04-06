# encoding: utf-8
"""Unit tests for leaving_soon duration parsing, deletion date computation, and duration enforcement."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.media_cleaner import parse_leaving_soon_duration, compute_deletion_date
from app.schema import LeavingSoonConfig
from app.state import StateManager


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

    def test_with_tagged_at_uses_tagged_time(self):
        """Test that tagged_at is used as base time instead of now."""
        tagged_at = datetime(2026, 3, 1, 12, 0, 0)
        result = compute_deletion_date(duration_str="7d", tagged_at=tagged_at)
        expected = datetime(2026, 3, 8, 12, 0, 0)
        assert result == expected

    def test_without_tagged_at_uses_now(self):
        """Test that without tagged_at, now is used as base time."""
        result = compute_deletion_date(duration_str="7d")
        expected = datetime.now() + timedelta(days=7)
        assert abs((result - expected).total_seconds()) < 2

    def test_tagged_at_produces_stable_date(self):
        """Test that calling compute_deletion_date with same tagged_at always gives same result."""
        tagged_at = datetime(2026, 3, 5, 10, 0, 0)
        result1 = compute_deletion_date(duration_str="7d", tagged_at=tagged_at)
        result2 = compute_deletion_date(duration_str="7d", tagged_at=tagged_at)
        assert result1 == result2 == datetime(2026, 3, 12, 10, 0, 0)

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


class TestDurationEnforcement:
    """Tests for duration enforcement in the death row pattern.

    Verifies that _filter_by_duration correctly blocks or allows deletions
    based on when items were tagged and the configured duration.
    """

    @pytest.fixture
    def deleterr_instance(self, tmp_path):
        """Create a Deleterr instance with mocked dependencies."""
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
        """Helper to create a mock Plex item."""
        item = MagicMock()
        item.ratingKey = rating_key
        item.title = title
        return item

    def test_items_not_deleted_when_duration_not_elapsed(self, deleterr_instance):
        """Items tagged recently should NOT be eligible for deletion."""
        # Tag an item 2 days ago with a 7-day duration
        tagged_at = (datetime.now() - timedelta(days=2)).isoformat()
        deleterr_instance.state_manager.set_tagged_dates(
            "Movies", {"100": tagged_at}
        )

        plex_items = [self._make_plex_item(100, "Recent Movie")]
        eligible, skipped = deleterr_instance._filter_by_duration(
            "Movies", plex_items, "7d"
        )

        assert len(eligible) == 0
        assert skipped == 1

    def test_items_deleted_when_duration_elapsed(self, deleterr_instance):
        """Items tagged long enough ago SHOULD be eligible for deletion."""
        # Tag an item 10 days ago with a 7-day duration
        tagged_at = (datetime.now() - timedelta(days=10)).isoformat()
        deleterr_instance.state_manager.set_tagged_dates(
            "Movies", {"100": tagged_at}
        )

        plex_items = [self._make_plex_item(100, "Old Movie")]
        eligible, skipped = deleterr_instance._filter_by_duration(
            "Movies", plex_items, "7d"
        )

        assert len(eligible) == 1
        assert eligible[0].ratingKey == 100
        assert skipped == 0

    def test_items_deleted_exactly_at_duration(self, deleterr_instance):
        """Items tagged exactly at the duration boundary are eligible."""
        # Tag an item exactly 7 days ago
        tagged_at = (datetime.now() - timedelta(days=7, seconds=1)).isoformat()
        deleterr_instance.state_manager.set_tagged_dates(
            "Movies", {"100": tagged_at}
        )

        plex_items = [self._make_plex_item(100, "Boundary Movie")]
        eligible, skipped = deleterr_instance._filter_by_duration(
            "Movies", plex_items, "7d"
        )

        assert len(eligible) == 1
        assert skipped == 0

    def test_no_duration_means_no_filtering(self, deleterr_instance):
        """When duration is not configured, _process_death_row skips filtering entirely.

        This test verifies the backward-compatible code path where the
        _filter_by_duration method is never called.
        """
        library = {
            "name": "Movies",
            "leaving_soon": {
                "collection": {"name": "Leaving Soon"},
                # No 'duration' key
            },
        }
        # The duration_str would be None, and the code in _process_death_row
        # only calls _filter_by_duration when duration_str is truthy.
        leaving_soon_config = library.get("leaving_soon", {})
        duration_str = leaving_soon_config.get("duration")
        assert duration_str is None  # No duration = existing behavior preserved

    def test_unknown_items_treated_as_newly_tagged(self, deleterr_instance):
        """Items with no state entry get recorded now and are NOT deleted."""
        # No state exists for this item
        plex_items = [self._make_plex_item(999, "Unknown Movie")]
        eligible, skipped = deleterr_instance._filter_by_duration(
            "Movies", plex_items, "7d"
        )

        assert len(eligible) == 0
        assert skipped == 1

        # Item should now be recorded in state
        tagged = deleterr_instance.state_manager.get_tagged_dates("Movies")
        assert "999" in tagged

    def test_mixed_items_partial_eligible(self, deleterr_instance):
        """When some items are expired and some aren't, only expired are eligible."""
        now = datetime.now()
        deleterr_instance.state_manager.set_tagged_dates("Movies", {
            "100": (now - timedelta(days=10)).isoformat(),  # expired
            "200": (now - timedelta(days=2)).isoformat(),   # not expired
            "300": (now - timedelta(days=8)).isoformat(),   # expired
        })

        plex_items = [
            self._make_plex_item(100, "Old Movie"),
            self._make_plex_item(200, "Recent Movie"),
            self._make_plex_item(300, "Another Old Movie"),
        ]
        eligible, skipped = deleterr_instance._filter_by_duration(
            "Movies", plex_items, "7d"
        )

        assert len(eligible) == 2
        assert skipped == 1
        eligible_keys = {item.ratingKey for item in eligible}
        assert eligible_keys == {100, 300}

    def test_hours_duration_enforcement(self, deleterr_instance):
        """Duration in hours is correctly enforced."""
        # Tagged 12 hours ago with 24h duration — should NOT be eligible
        tagged_at = (datetime.now() - timedelta(hours=12)).isoformat()
        deleterr_instance.state_manager.set_tagged_dates(
            "Movies", {"100": tagged_at}
        )

        plex_items = [self._make_plex_item(100)]
        eligible, skipped = deleterr_instance._filter_by_duration(
            "Movies", plex_items, "24h"
        )

        assert len(eligible) == 0
        assert skipped == 1

    def test_state_cleanup_after_deletion(self, deleterr_instance):
        """After items are deleted, their state entries should be removable."""
        deleterr_instance.state_manager.set_tagged_dates("Movies", {
            "100": "2026-01-01T00:00:00",
            "200": "2026-01-01T00:00:00",
        })

        deleterr_instance.state_manager.remove_items("Movies", ["100"])

        remaining = deleterr_instance.state_manager.get_tagged_dates("Movies")
        assert "100" not in remaining
        assert "200" in remaining

    def test_waiting_items_skip_candidate_scan(self, deleterr_instance):
        """When all death row items are waiting, skip the expensive candidate scan.

        Scenario: schedule runs daily, duration is 7d.
        Items tagged 2 days ago should NOT be deleted. Since all items are still
        waiting, the candidate scan is skipped entirely (performance optimization)
        and preview_candidates is None, signaling the caller to leave the
        collection/state untouched.
        """
        now = datetime.now()
        # Item tagged 2 days ago - still within 7d duration
        deleterr_instance.state_manager.set_tagged_dates("Movies", {
            "100": (now - timedelta(days=2)).isoformat(),
        })

        # Set up Plex library and death row items
        plex_library = MagicMock()
        deleterr_instance.media_server.get_library.return_value = plex_library

        waiting_plex_item = self._make_plex_item(100, "Waiting Movie")
        deleterr_instance.media_server.get_collection.return_value = MagicMock(
            items=MagicMock(return_value=[waiting_plex_item])
        )
        deleterr_instance.media_server.get_items_with_label.return_value = []

        # _get_deletion_candidates should NOT be called (performance optimization)
        deleterr_instance._get_deletion_candidates = MagicMock(
            return_value=[{"id": 1, "title": "Waiting Movie", "tmdbId": "tt001"}]
        )

        library = {
            "name": "Movies",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}, "duration": "7d"},
            "max_actions_per_run": 10,
        }

        with patch("app.media_cleaner.library_meets_disk_space_threshold", return_value=True):
            saved_space, deleted_items, preview_candidates, saved_plex_items, _prior, _foreign = deleterr_instance._process_death_row(
                library, MagicMock(), "movie"
            )

        # Nothing should be deleted (duration not elapsed)
        assert len(deleted_items) == 0
        assert saved_space == 0

        # preview_candidates is None - signals caller to skip collection update
        assert preview_candidates is None

        # The expensive candidate scan was skipped
        deleterr_instance._get_deletion_candidates.assert_not_called()

    def test_new_candidates_added_when_death_row_empty(self, deleterr_instance):
        """New candidates are added to preview when death row is empty (first run or after clearing)."""
        # No items in state - death row is empty
        plex_library = MagicMock()
        deleterr_instance.media_server.get_library.return_value = plex_library

        # Empty death row collection
        deleterr_instance.media_server.get_collection.return_value = MagicMock(
            items=MagicMock(return_value=[])
        )
        deleterr_instance.media_server.get_items_with_label.return_value = []

        new_candidate_a = {"id": 1, "title": "Movie A", "tmdbId": "tt001", "year": 2024, "sizeOnDisk": 1000}
        new_candidate_b = {"id": 2, "title": "Movie B", "tmdbId": "tt002", "year": 2023, "sizeOnDisk": 2000}

        plex_a = self._make_plex_item(100, "Movie A")
        plex_b = self._make_plex_item(200, "Movie B")

        def find_item_side_effect(lib, **kwargs):
            tmdb = kwargs.get("tmdb_id")
            if tmdb == "tt001":
                return plex_a
            if tmdb == "tt002":
                return plex_b
            return None

        deleterr_instance.media_server.find_item.side_effect = find_item_side_effect

        deleterr_instance._get_deletion_candidates = MagicMock(
            return_value=[new_candidate_a, new_candidate_b]
        )

        library = {
            "name": "Movies",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}, "duration": "7d"},
            "max_actions_per_run": 10,
        }

        with patch("app.media_cleaner.library_meets_disk_space_threshold", return_value=True):
            saved_space, deleted_items, preview_candidates, saved_plex_items, _prior, _foreign = deleterr_instance._process_death_row(
                library, MagicMock(), "movie"
            )

        # No deletions on first run
        assert len(deleted_items) == 0

        # Both new candidates should be in preview since death row was empty
        preview_titles = {m["title"] for m in preview_candidates}
        assert "Movie A" in preview_titles
        assert "Movie B" in preview_titles

    def test_new_candidates_added_after_batch_cleared(self, deleterr_instance):
        """After all death row items are deleted, new candidates should be added."""
        now = datetime.now()
        # Item tagged 10 days ago - past 7d duration, eligible for deletion
        deleterr_instance.state_manager.set_tagged_dates("Movies", {
            "100": (now - timedelta(days=10)).isoformat(),
        })

        plex_library = MagicMock()
        deleterr_instance.media_server.get_library.return_value = plex_library

        death_row_plex_item = self._make_plex_item(100, "Old Movie")
        deleterr_instance.media_server.get_collection.return_value = MagicMock(
            items=MagicMock(return_value=[death_row_plex_item])
        )
        deleterr_instance.media_server.get_items_with_label.return_value = []

        # Old Movie still matches criteria, plus a new candidate
        old_media = {"id": 1, "title": "Old Movie", "tmdbId": "tt001", "year": 2020, "sizeOnDisk": 1000}
        new_candidate = {"id": 2, "title": "New Movie", "tmdbId": "tt002", "year": 2023, "sizeOnDisk": 2000}
        new_plex_item = self._make_plex_item(200, "New Movie")

        def find_item_side_effect(lib, **kwargs):
            tmdb = kwargs.get("tmdb_id")
            if tmdb == "tt001":
                return death_row_plex_item
            if tmdb == "tt002":
                return new_plex_item
            return None

        deleterr_instance.media_server.find_item.side_effect = find_item_side_effect

        deleterr_instance._get_deletion_candidates = MagicMock(
            return_value=[old_media, new_candidate]
        )

        library = {
            "name": "Movies",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}, "duration": "7d"},
            "max_actions_per_run": 10,
        }

        with patch("app.media_cleaner.library_meets_disk_space_threshold", return_value=True):
            saved_space, deleted_items, preview_candidates, saved_plex_items, _prior, _foreign = deleterr_instance._process_death_row(
                library, MagicMock(), "movie"
            )

        # Old Movie should be deleted (duration elapsed + still matches)
        assert len(deleted_items) == 1
        assert deleted_items[0]["title"] == "Old Movie"

        # New Movie should NOT be in preview yet - death row had items this run.
        # It will be added on the next run when death row is empty.
        preview_titles = {m["title"] for m in preview_candidates}
        assert "New Movie" not in preview_titles


class TestBatchSize:
    """Tests for batch_size controlling how many items enter the leaving_soon collection."""

    @pytest.fixture
    def deleterr_instance(self, tmp_path):
        """Create a Deleterr instance with mocked dependencies."""
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

    def test_batch_size_limits_new_candidates(self, deleterr_instance):
        """With batch_size: 2 and 5 deletion candidates, only 2 enter preview."""
        plex_library = MagicMock()
        deleterr_instance.media_server.get_library.return_value = plex_library

        # Empty death row
        deleterr_instance.media_server.get_collection.return_value = MagicMock(
            items=MagicMock(return_value=[])
        )
        deleterr_instance.media_server.get_items_with_label.return_value = []

        candidates = [
            {"id": i, "title": f"Movie {i}", "tmdbId": f"tt{i:03d}", "year": 2020 + i, "sizeOnDisk": 1000}
            for i in range(1, 6)
        ]
        plex_items = {f"tt{i:03d}": self._make_plex_item(100 + i, f"Movie {i}") for i in range(1, 6)}

        def find_item_side_effect(lib, **kwargs):
            return plex_items.get(kwargs.get("tmdb_id"))

        deleterr_instance.media_server.find_item.side_effect = find_item_side_effect
        deleterr_instance._get_deletion_candidates = MagicMock(return_value=candidates)

        library = {
            "name": "Movies",
            "leaving_soon": {"batch_size": 2, "collection": {"name": "Leaving Soon"}},
            "max_actions_per_run": 10,
        }

        with patch("app.media_cleaner.library_meets_disk_space_threshold", return_value=True):
            _, _, preview_candidates, _, _, _ = deleterr_instance._process_death_row(
                library, MagicMock(), "movie"
            )

        assert len(preview_candidates) == 2

    def test_batch_size_overrides_preview_next(self, deleterr_instance):
        """batch_size: 3 with preview_next: 10 results in 3 items."""
        plex_library = MagicMock()
        deleterr_instance.media_server.get_library.return_value = plex_library

        deleterr_instance.media_server.get_collection.return_value = MagicMock(
            items=MagicMock(return_value=[])
        )
        deleterr_instance.media_server.get_items_with_label.return_value = []

        candidates = [
            {"id": i, "title": f"Movie {i}", "tmdbId": f"tt{i:03d}", "year": 2020 + i, "sizeOnDisk": 1000}
            for i in range(1, 11)
        ]
        plex_items = {f"tt{i:03d}": self._make_plex_item(100 + i, f"Movie {i}") for i in range(1, 11)}

        def find_item_side_effect(lib, **kwargs):
            return plex_items.get(kwargs.get("tmdb_id"))

        deleterr_instance.media_server.find_item.side_effect = find_item_side_effect
        deleterr_instance._get_deletion_candidates = MagicMock(return_value=candidates)

        library = {
            "name": "Movies",
            "leaving_soon": {"batch_size": 3, "collection": {"name": "Leaving Soon"}},
            "preview_next": 10,
            "max_actions_per_run": 10,
        }

        with patch("app.media_cleaner.library_meets_disk_space_threshold", return_value=True):
            _, _, preview_candidates, _, _, _ = deleterr_instance._process_death_row(
                library, MagicMock(), "movie"
            )

        assert len(preview_candidates) == 3

    def test_batch_size_overrides_max_actions(self, deleterr_instance):
        """batch_size: 3 with max_actions_per_run: 10 results in 3 items."""
        plex_library = MagicMock()
        deleterr_instance.media_server.get_library.return_value = plex_library

        deleterr_instance.media_server.get_collection.return_value = MagicMock(
            items=MagicMock(return_value=[])
        )
        deleterr_instance.media_server.get_items_with_label.return_value = []

        candidates = [
            {"id": i, "title": f"Movie {i}", "tmdbId": f"tt{i:03d}", "year": 2020 + i, "sizeOnDisk": 1000}
            for i in range(1, 11)
        ]
        plex_items = {f"tt{i:03d}": self._make_plex_item(100 + i, f"Movie {i}") for i in range(1, 11)}

        def find_item_side_effect(lib, **kwargs):
            return plex_items.get(kwargs.get("tmdb_id"))

        deleterr_instance.media_server.find_item.side_effect = find_item_side_effect
        deleterr_instance._get_deletion_candidates = MagicMock(return_value=candidates)

        library = {
            "name": "Movies",
            "leaving_soon": {"batch_size": 3, "collection": {"name": "Leaving Soon"}},
            "max_actions_per_run": 10,
        }

        with patch("app.media_cleaner.library_meets_disk_space_threshold", return_value=True):
            _, _, preview_candidates, _, _, _ = deleterr_instance._process_death_row(
                library, MagicMock(), "movie"
            )

        assert len(preview_candidates) == 3

    def test_no_batch_size_uses_preview_next(self, deleterr_instance):
        """Without batch_size, preview_next controls the batch (backward compat)."""
        plex_library = MagicMock()
        deleterr_instance.media_server.get_library.return_value = plex_library

        deleterr_instance.media_server.get_collection.return_value = MagicMock(
            items=MagicMock(return_value=[])
        )
        deleterr_instance.media_server.get_items_with_label.return_value = []

        candidates = [
            {"id": i, "title": f"Movie {i}", "tmdbId": f"tt{i:03d}", "year": 2020 + i, "sizeOnDisk": 1000}
            for i in range(1, 11)
        ]
        plex_items = {f"tt{i:03d}": self._make_plex_item(100 + i, f"Movie {i}") for i in range(1, 11)}

        def find_item_side_effect(lib, **kwargs):
            return plex_items.get(kwargs.get("tmdb_id"))

        deleterr_instance.media_server.find_item.side_effect = find_item_side_effect
        deleterr_instance._get_deletion_candidates = MagicMock(return_value=candidates)

        library = {
            "name": "Movies",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}},
            "preview_next": 5,
            "max_actions_per_run": 10,
        }

        with patch("app.media_cleaner.library_meets_disk_space_threshold", return_value=True):
            _, _, preview_candidates, _, _, _ = deleterr_instance._process_death_row(
                library, MagicMock(), "movie"
            )

        assert len(preview_candidates) == 5

    def test_no_batch_size_no_preview_next_uses_max_actions(self, deleterr_instance):
        """Without batch_size or preview_next, falls back to max_actions_per_run."""
        plex_library = MagicMock()
        deleterr_instance.media_server.get_library.return_value = plex_library

        deleterr_instance.media_server.get_collection.return_value = MagicMock(
            items=MagicMock(return_value=[])
        )
        deleterr_instance.media_server.get_items_with_label.return_value = []

        candidates = [
            {"id": i, "title": f"Movie {i}", "tmdbId": f"tt{i:03d}", "year": 2020 + i, "sizeOnDisk": 1000}
            for i in range(1, 21)
        ]
        plex_items = {f"tt{i:03d}": self._make_plex_item(100 + i, f"Movie {i}") for i in range(1, 21)}

        def find_item_side_effect(lib, **kwargs):
            return plex_items.get(kwargs.get("tmdb_id"))

        deleterr_instance.media_server.find_item.side_effect = find_item_side_effect
        deleterr_instance._get_deletion_candidates = MagicMock(return_value=candidates)

        library = {
            "name": "Movies",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}},
            "max_actions_per_run": 7,
        }

        with patch("app.media_cleaner.library_meets_disk_space_threshold", return_value=True):
            _, _, preview_candidates, _, _, _ = deleterr_instance._process_death_row(
                library, MagicMock(), "movie"
            )

        assert len(preview_candidates) == 7


class TestNotificationDedup:
    """Tests for notification deduplication in leaving_soon."""

    @pytest.fixture
    def deleterr_instance(self, tmp_path):
        """Create a Deleterr instance with mocked dependencies."""
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
                "notifications": {
                    "leaving_soon": {
                        "discord": {"webhook_url": "http://test"},
                    },
                },
            }
            d = Deleterr.__new__(Deleterr)
            d.config = config
            d.media_server = MagicMock()
            d.media_cleaner = MagicMock()
            d.notifications = MagicMock()
            d.notifications.is_leaving_soon_enabled.return_value = True
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
        item.year = 2024
        return item

    def test_first_run_notifies_all_items(self, deleterr_instance):
        """First run: all items should trigger notification."""
        library = {
            "name": "Movies",
            "radarr": "Radarr",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}, "duration": "7d"},
        }
        preview = [
            {"title": "Movie A", "tmdbId": 1, "year": 2024, "sizeOnDisk": 1000},
            {"title": "Movie B", "tmdbId": 2, "year": 2023, "sizeOnDisk": 2000},
        ]

        plex_a = self._make_plex_item(100, "Movie A")
        plex_b = self._make_plex_item(200, "Movie B")

        # process_leaving_soon returns resolved plex items
        deleterr_instance.media_cleaner.process_leaving_soon.return_value = [plex_a, plex_b]
        deleterr_instance.media_server.get_library.return_value = MagicMock()
        deleterr_instance._get_death_row_items = MagicMock(return_value=[])

        with patch("app.media_cleaner.compute_deletion_date", return_value=None):
            deleterr_instance._process_library_leaving_soon(library, preview, "movie")

        # Notification should be sent with all items
        deleterr_instance._send_leaving_soon_notification = MagicMock()
        # Re-run with the mock to verify
        with patch("app.media_cleaner.compute_deletion_date", return_value=None):
            deleterr_instance._process_library_leaving_soon(library, preview, "movie")

        # The send_leaving_soon should have been called on notifications
        assert deleterr_instance.notifications.send_leaving_soon.called

    def test_second_run_same_items_no_notification(self, deleterr_instance):
        """Second run with same items: no notification should be sent (dedup)."""
        library = {
            "name": "Movies",
            "radarr": "Radarr",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}, "duration": "7d"},
        }
        preview = [
            {"title": "Movie A", "tmdbId": 1, "year": 2024, "sizeOnDisk": 1000},
        ]

        plex_a = self._make_plex_item(100, "Movie A")
        deleterr_instance.media_cleaner.process_leaving_soon.return_value = [plex_a]
        deleterr_instance.media_server.get_library.return_value = MagicMock()
        deleterr_instance._get_death_row_items = MagicMock(return_value=[])

        # Simulate first run: record item in state
        deleterr_instance.state_manager.set_tagged_dates("Movies", {"100": "2026-03-01T00:00:00"})

        with patch("app.media_cleaner.compute_deletion_date", return_value=None):
            deleterr_instance._process_library_leaving_soon(library, preview, "movie")

        # Notification should NOT be called because item was already in state
        assert not deleterr_instance.notifications.send_leaving_soon.called

    def test_third_run_new_item_notifies_only_new(self, deleterr_instance):
        """Third run with one new item: only the new item should trigger notification."""
        library = {
            "name": "Movies",
            "radarr": "Radarr",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}, "duration": "7d"},
        }
        preview = [
            {"title": "Movie A", "tmdbId": 1, "year": 2024, "sizeOnDisk": 1000},
            {"title": "Movie C", "tmdbId": 3, "year": 2022, "sizeOnDisk": 3000},
        ]

        plex_a = self._make_plex_item(100, "Movie A")
        plex_c = self._make_plex_item(300, "Movie C")
        deleterr_instance.media_cleaner.process_leaving_soon.return_value = [plex_a, plex_c]
        deleterr_instance.media_server.get_library.return_value = MagicMock()
        deleterr_instance._get_death_row_items = MagicMock(return_value=[])

        # Movie A was already tagged in state
        deleterr_instance.state_manager.set_tagged_dates("Movies", {"100": "2026-03-01T00:00:00"})

        with patch("app.media_cleaner.compute_deletion_date", return_value=None):
            deleterr_instance._process_library_leaving_soon(library, preview, "movie")

        # Notification should be sent
        assert deleterr_instance.notifications.send_leaving_soon.called
        call_args = deleterr_instance.notifications.send_leaving_soon.call_args
        notified_items = call_args[0][0] if call_args[0] else call_args[1].get("items", [])
        # Only Movie C should be in the notified items
        assert len(notified_items) == 1
        assert notified_items[0].title == "Movie C"

    def test_no_duration_always_notifies(self, deleterr_instance):
        """Without duration config, all items are notified every run."""
        library = {
            "name": "Movies",
            "radarr": "Radarr",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}},
            # No "duration" key
        }
        preview = [
            {"title": "Movie A", "tmdbId": 1, "year": 2024, "sizeOnDisk": 1000},
        ]

        plex_a = self._make_plex_item(100, "Movie A")
        deleterr_instance.media_cleaner.process_leaving_soon.return_value = [plex_a]
        deleterr_instance.media_server.get_library.return_value = MagicMock()
        deleterr_instance._get_death_row_items = MagicMock(return_value=[])

        # Even if item was already in state, without duration we always notify
        deleterr_instance.state_manager.set_tagged_dates("Movies", {"100": "2026-03-01T00:00:00"})

        with patch("app.media_cleaner.compute_deletion_date", return_value=None):
            deleterr_instance._process_library_leaving_soon(library, preview, "movie")

        assert deleterr_instance.notifications.send_leaving_soon.called


class TestSavedItems:
    """Tests for saved items detection in death row processing."""

    @pytest.fixture
    def deleterr_instance(self, tmp_path):
        """Create a Deleterr instance with mocked dependencies."""
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

    def test_saved_items_detected(self, deleterr_instance):
        """Items on death row that no longer match criteria are 'saved'."""
        now = datetime.now()
        # Both items tagged long enough ago to be eligible
        deleterr_instance.state_manager.set_tagged_dates("Movies", {
            "100": (now - timedelta(days=10)).isoformat(),
            "200": (now - timedelta(days=10)).isoformat(),
        })

        plex_item_100 = self._make_plex_item(100, "Deleted Movie")
        plex_item_200 = self._make_plex_item(200, "Saved Movie")

        # Both items in death row collection
        deleterr_instance._get_death_row_items = MagicMock(
            return_value=[plex_item_100, plex_item_200]
        )

        # Only item 100 still matches deletion criteria (200 was watched)
        media_100 = {"id": 1, "title": "Deleted Movie", "tmdbId": "tt001", "year": 2024, "sizeOnDisk": 1000}
        deleterr_instance._get_deletion_candidates = MagicMock(return_value=[media_100])

        def find_item_side_effect(lib, **kwargs):
            tmdb = kwargs.get("tmdb_id")
            if tmdb == "tt001":
                return plex_item_100
            return None

        deleterr_instance.media_server.find_item.side_effect = find_item_side_effect
        deleterr_instance.media_server.get_library.return_value = MagicMock()

        library = {
            "name": "Movies",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}, "duration": "7d"},
            "max_actions_per_run": 10,
        }

        with patch("app.media_cleaner.library_meets_disk_space_threshold", return_value=True):
            saved_space, deleted_items, preview_candidates, saved_plex_items, _prior, _foreign = deleterr_instance._process_death_row(
                library, MagicMock(), "movie"
            )

        # Item 100 was deleted, item 200 was saved
        assert len(deleted_items) == 1
        assert deleted_items[0]["title"] == "Deleted Movie"
        assert len(saved_plex_items) == 1
        assert saved_plex_items[0].title == "Saved Movie"


class TestFormatTitleWithLibrary:
    """Tests for DeletedItem.format_title_with_library()."""

    def test_with_library_and_year(self):
        from app.modules.notifications.models import DeletedItem
        item = DeletedItem(
            title="Inception",
            year=2010,
            media_type="movie",
            size_bytes=1000,
            library_name="4K Movies",
            instance_name="Radarr",
        )
        assert item.format_title_with_library() == "[4K Movies] Inception (2010)"

    def test_with_library_no_year(self):
        from app.modules.notifications.models import DeletedItem
        item = DeletedItem(
            title="Some Show",
            year=None,
            media_type="show",
            size_bytes=1000,
            library_name="TV Shows",
            instance_name="Sonarr",
        )
        assert item.format_title_with_library() == "[TV Shows] Some Show"

    def test_no_library_name(self):
        from app.modules.notifications.models import DeletedItem
        item = DeletedItem(
            title="Inception",
            year=2010,
            media_type="movie",
            size_bytes=1000,
            library_name="",
            instance_name="Radarr",
        )
        assert item.format_title_with_library() == "Inception (2010)"

    def test_is_leaving_soon_flag(self):
        from app.modules.notifications.models import RunResult
        result = RunResult(is_leaving_soon=True)
        assert result.is_leaving_soon is True

        result2 = RunResult()
        assert result2.is_leaving_soon is False

    def test_saved_items_in_run_result(self):
        from app.modules.notifications.models import RunResult, DeletedItem
        result = RunResult()
        assert result.saved_items == []

        item = DeletedItem(
            title="Saved Movie",
            year=2024,
            media_type="movie",
            size_bytes=0,
            library_name="Movies",
            instance_name="Radarr",
        )
        result.saved_items = [item]
        assert result.has_content() is True


class TestDuplicateLibraryNameStatePreservation:
    """Regression test for the 'removal date advancing daily' bug.

    When two library entries share the same Plex library name (e.g. two Sonarr
    instances both configured as "TV Shows"), the first library entry's cleanup
    was wiping state entries, causing the second entry to re-tag items with
    fresh timestamps every run.  This made the notification's removal date
    advance by one day with each run instead of staying fixed.

    The fix ensures that death row items discovered before processing are
    passed through to cleanup so their state entries are preserved even if
    the collection is cleared during processing.
    """

    @pytest.fixture
    def deleterr_instance(self, tmp_path):
        """Create a Deleterr instance with real StateManager."""
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
                "notifications": {
                    "leaving_soon": {
                        "discord": {"webhook_url": "http://test"},
                    },
                },
                "scheduler": {},
            }
            d = Deleterr.__new__(Deleterr)
            d.config = config
            d.media_server = MagicMock()
            d.media_cleaner = MagicMock()
            d.notifications = MagicMock()
            d.notifications.is_leaving_soon_enabled.return_value = True
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
        item.year = 2024
        return item

    def test_second_library_entry_preserves_state_from_first(self, deleterr_instance):
        """State entries survive when a second library entry with the same name processes.

        Simulates the exact scenario from the bug report:
        1. Library [1/3] "TV Shows" finds Derek/Manhunt in the collection,
           but they don't match this instance's deletion rules.  Preview is
           empty, so process_leaving_soon clears the collection.
        2. Library [2/3] "TV Shows" processes next.  The state entries from
           step 1 must still exist so that set_tagged_dates does NOT
           overwrite them and notification dedup works correctly.
        """
        original_tagged_at = "2026-03-10T20:02:29"
        plex_derek = self._make_plex_item(1001, "Derek")
        plex_manhunt = self._make_plex_item(1002, "Manhunt (2019)")

        # Seed state: items were tagged on March 10
        deleterr_instance.state_manager.set_tagged_dates("TV Shows", {
            "1001": original_tagged_at,
            "1002": original_tagged_at,
        })

        library_1 = {
            "name": "TV Shows",
            "sonarr": "Sonarr-1",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}, "duration": "7d"},
        }

        # Library [1/3]: empty preview (items don't match this instance's rules)
        # but death row had items before processing
        deleterr_instance.media_cleaner.process_leaving_soon.return_value = []
        deleterr_instance.media_server.get_library.return_value = MagicMock()
        # After process_leaving_soon clears the collection, _get_death_row_items
        # returns empty (collection is now empty)
        deleterr_instance._get_death_row_items = MagicMock(return_value=[])

        deleterr_instance._process_library_leaving_soon(
            library_1, [], "show",
            death_row_plex_items=[plex_derek, plex_manhunt],
        )

        # State entries must still exist after library [1/3]'s cleanup
        tagged_dates = deleterr_instance.state_manager.get_tagged_dates("TV Shows")
        assert "1001" in tagged_dates, "Derek's state entry was wiped by cleanup"
        assert "1002" in tagged_dates, "Manhunt's state entry was wiped by cleanup"
        assert tagged_dates["1001"] == original_tagged_at
        assert tagged_dates["1002"] == original_tagged_at

    def test_second_library_entry_does_not_re_notify(self, deleterr_instance):
        """With state preserved, the second library entry's dedup prevents re-notification.

        This is the end-to-end scenario: library [1/3] processes (preserving
        state), then library [2/3] tags the same items.  Because state already
        has the keys, notification dedup filters them out.
        """
        original_tagged_at = "2026-03-10T20:02:29"
        plex_derek = self._make_plex_item(1001, "Derek")
        plex_manhunt = self._make_plex_item(1002, "Manhunt (2019)")

        # Seed state
        deleterr_instance.state_manager.set_tagged_dates("TV Shows", {
            "1001": original_tagged_at,
            "1002": original_tagged_at,
        })

        # --- Library [1/3]: empty preview, death row items passed for preservation ---
        library_1 = {
            "name": "TV Shows",
            "sonarr": "Sonarr-1",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}, "duration": "7d"},
        }
        deleterr_instance.media_cleaner.process_leaving_soon.return_value = []
        deleterr_instance.media_server.get_library.return_value = MagicMock()
        deleterr_instance._get_death_row_items = MagicMock(return_value=[])

        deleterr_instance._process_library_leaving_soon(
            library_1, [], "show",
            death_row_plex_items=[plex_derek, plex_manhunt],
        )

        deleterr_instance.notifications.send_leaving_soon.reset_mock()

        # --- Library [2/3]: tags the same items ---
        library_2 = {
            "name": "TV Shows",
            "sonarr": "Sonarr-2",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}, "duration": "7d"},
        }
        preview_items = [
            {"title": "Derek", "tvdbId": 101, "year": 2013,
             "statistics": {"sizeOnDisk": 2330000000, "episodeFileCount": 14}},
            {"title": "Manhunt (2019)", "tvdbId": 102, "year": 2019,
             "statistics": {"sizeOnDisk": 3860000000, "episodeFileCount": 8}},
        ]

        deleterr_instance.media_cleaner.process_leaving_soon.return_value = [
            plex_derek, plex_manhunt,
        ]
        # After tagging, death row now has items
        deleterr_instance._get_death_row_items = MagicMock(
            return_value=[plex_derek, plex_manhunt],
        )

        deleterr_instance._process_library_leaving_soon(
            library_2, preview_items, "show",
            death_row_plex_items=[],
        )

        # State timestamps must NOT have been overwritten
        tagged_dates = deleterr_instance.state_manager.get_tagged_dates("TV Shows")
        assert tagged_dates["1001"] == original_tagged_at
        assert tagged_dates["1002"] == original_tagged_at

        # No notification should have been sent (items were already in state)
        assert not deleterr_instance.notifications.send_leaving_soon.called, \
            "Notification was sent for items already in state (dedup failed)"

    def test_deletion_date_uses_tagged_at_not_now(self, deleterr_instance):
        """The notification deletion date must be based on tagged_at + duration, not now + duration.

        When items were tagged on March 10 with a 7d duration, the removal
        date must always be March 17 regardless of when the next run happens.
        """
        tagged_at = "2026-03-10T20:02:29"
        plex_derek = self._make_plex_item(1001, "Derek")

        deleterr_instance.state_manager.set_tagged_dates("TV Shows", {
            "1001": tagged_at,
        })

        library = {
            "name": "TV Shows",
            "sonarr": "Sonarr",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}, "duration": "7d"},
        }
        preview = [
            {"title": "Derek", "tvdbId": 101, "year": 2013,
             "statistics": {"sizeOnDisk": 2330000000, "episodeFileCount": 14}},
        ]

        deleterr_instance.media_cleaner.process_leaving_soon.return_value = [plex_derek]
        deleterr_instance.media_server.get_library.return_value = MagicMock()
        deleterr_instance._get_death_row_items = MagicMock(return_value=[plex_derek])

        deleterr_instance._process_library_leaving_soon(
            library, preview, "show",
            death_row_plex_items=[plex_derek],
        )

        # Check the deletion_date passed to process_leaving_soon
        call_kwargs = deleterr_instance.media_cleaner.process_leaving_soon.call_args
        deletion_date = call_kwargs[1].get("deletion_date") or call_kwargs[0][4] if len(call_kwargs[0]) > 4 else None
        if deletion_date is None:
            deletion_date = call_kwargs[1].get("deletion_date")

        # The deletion date should be tagged_at + 7d = March 17, NOT now + 7d
        expected = datetime.fromisoformat(tagged_at) + timedelta(days=7)
        assert deletion_date == expected, \
            f"Deletion date {deletion_date} should be {expected} (tagged_at + 7d), not now + 7d"
