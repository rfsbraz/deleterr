# encoding: utf-8
"""Unit tests for StateManager."""

import json
import os

import pytest

from app.state import StateManager, STATE_VERSION


@pytest.fixture
def state_file(tmp_path):
    """Provide a temporary state file path."""
    return str(tmp_path / ".deleterr_state.json")


@pytest.fixture
def state_manager(state_file):
    """Create a StateManager with a temp file."""
    return StateManager(state_file=state_file)


class TestStateManagerLoadSave:
    """Tests for load/save operations."""

    def test_load_missing_file_returns_empty(self, state_manager):
        """Loading when file doesn't exist returns empty state."""
        state = state_manager.load()
        assert state == {"version": STATE_VERSION, "leaving_soon": {}}

    def test_save_and_load_roundtrip(self, state_manager):
        """Data survives a save/load cycle."""
        state = {
            "version": STATE_VERSION,
            "leaving_soon": {
                "Movies": {
                    "12345": "2026-03-01T13:27:49",
                    "12346": "2026-03-01T13:27:49",
                }
            },
        }
        state_manager.save(state)
        loaded = state_manager.load()
        assert loaded == state

    def test_load_corrupt_json_returns_empty(self, state_file, state_manager):
        """Corrupt JSON file returns empty state."""
        with open(state_file, "w") as f:
            f.write("{not valid json")
        state = state_manager.load()
        assert state == {"version": STATE_VERSION, "leaving_soon": {}}

    def test_load_wrong_version_returns_empty(self, state_file, state_manager):
        """State file with wrong version returns empty state."""
        with open(state_file, "w") as f:
            json.dump({"version": 999, "leaving_soon": {}}, f)
        state = state_manager.load()
        assert state == {"version": STATE_VERSION, "leaving_soon": {}}

    def test_load_non_dict_returns_empty(self, state_file, state_manager):
        """State file with non-dict content returns empty state."""
        with open(state_file, "w") as f:
            json.dump([1, 2, 3], f)
        state = state_manager.load()
        assert state == {"version": STATE_VERSION, "leaving_soon": {}}

    def test_atomic_write_no_partial_file(self, state_file, state_manager):
        """Save creates file atomically — file is complete or absent."""
        state = {
            "version": STATE_VERSION,
            "leaving_soon": {"Movies": {"123": "2026-03-01T00:00:00"}},
        }
        state_manager.save(state)

        # File should exist and be valid JSON
        with open(state_file, "r") as f:
            data = json.load(f)
        assert data == state


class TestStateManagerTaggedDates:
    """Tests for get/set tagged dates."""

    def test_get_tagged_dates_empty(self, state_manager):
        """Returns empty dict for unknown library."""
        assert state_manager.get_tagged_dates("Movies") == {}

    def test_set_and_get_tagged_dates(self, state_manager):
        """Set tagged dates and retrieve them."""
        items = {"12345": "2026-03-01T13:27:49", "12346": "2026-03-01T13:28:00"}
        state_manager.set_tagged_dates("Movies", items)

        result = state_manager.get_tagged_dates("Movies")
        assert result == items

    def test_set_tagged_dates_preserves_existing(self, state_manager):
        """Existing tagged dates are not overwritten by new calls."""
        state_manager.set_tagged_dates("Movies", {"123": "2026-03-01T00:00:00"})
        state_manager.set_tagged_dates("Movies", {"123": "2026-03-08T00:00:00", "456": "2026-03-08T00:00:00"})

        result = state_manager.get_tagged_dates("Movies")
        # Original date for key "123" should be preserved
        assert result["123"] == "2026-03-01T00:00:00"
        # New key should be added
        assert result["456"] == "2026-03-08T00:00:00"

    def test_set_tagged_dates_multiple_libraries(self, state_manager):
        """Different libraries have independent state."""
        state_manager.set_tagged_dates("Movies", {"100": "2026-03-01T00:00:00"})
        state_manager.set_tagged_dates("Anime", {"200": "2026-03-02T00:00:00"})

        assert state_manager.get_tagged_dates("Movies") == {"100": "2026-03-01T00:00:00"}
        assert state_manager.get_tagged_dates("Anime") == {"200": "2026-03-02T00:00:00"}

    def test_set_tagged_dates_converts_key_to_string(self, state_manager):
        """Rating keys passed as int are stored as string."""
        state_manager.set_tagged_dates("Movies", {12345: "2026-03-01T00:00:00"})
        result = state_manager.get_tagged_dates("Movies")
        assert "12345" in result


class TestStateManagerRemoveItems:
    """Tests for removing items from state."""

    def test_remove_items(self, state_manager):
        """Remove specific items from a library."""
        state_manager.set_tagged_dates(
            "Movies",
            {"100": "2026-03-01T00:00:00", "200": "2026-03-01T00:00:00", "300": "2026-03-01T00:00:00"},
        )
        state_manager.remove_items("Movies", ["100", "300"])

        result = state_manager.get_tagged_dates("Movies")
        assert result == {"200": "2026-03-01T00:00:00"}

    def test_remove_items_empty_list(self, state_manager):
        """Removing empty list is a no-op."""
        state_manager.set_tagged_dates("Movies", {"100": "2026-03-01T00:00:00"})
        state_manager.remove_items("Movies", [])
        assert state_manager.get_tagged_dates("Movies") == {"100": "2026-03-01T00:00:00"}

    def test_remove_items_unknown_library(self, state_manager):
        """Removing from non-existent library is a no-op."""
        state_manager.remove_items("NonExistent", ["100"])
        # Should not raise

    def test_remove_all_items_cleans_library(self, state_manager):
        """Removing all items from a library cleans up the entry."""
        state_manager.set_tagged_dates("Movies", {"100": "2026-03-01T00:00:00"})
        state_manager.remove_items("Movies", ["100"])

        state = state_manager.load()
        assert "Movies" not in state.get("leaving_soon", {})


class TestStateManagerCleanup:
    """Tests for cleanup_library."""

    def test_cleanup_removes_stale_entries(self, state_manager):
        """Entries not in active set are removed."""
        state_manager.set_tagged_dates(
            "Movies",
            {"100": "2026-03-01T00:00:00", "200": "2026-03-01T00:00:00", "300": "2026-03-01T00:00:00"},
        )
        state_manager.cleanup_library("Movies", active_rating_keys={"200"})

        result = state_manager.get_tagged_dates("Movies")
        assert result == {"200": "2026-03-01T00:00:00"}

    def test_cleanup_empty_library_is_noop(self, state_manager):
        """Cleanup on library with no state is a no-op."""
        state_manager.cleanup_library("Movies", active_rating_keys=set())

    def test_cleanup_accepts_int_keys(self, state_manager):
        """Active keys can be int or str."""
        state_manager.set_tagged_dates("Movies", {"100": "2026-03-01T00:00:00"})
        state_manager.cleanup_library("Movies", active_rating_keys={100})

        result = state_manager.get_tagged_dates("Movies")
        assert result == {"100": "2026-03-01T00:00:00"}
