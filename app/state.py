# encoding: utf-8
"""State persistence for tracking when items were tagged to leaving soon."""

import json
import os
import tempfile
from datetime import datetime

from app import logger

STATE_FILE = "/config/.deleterr_state.json"
STATE_VERSION = 1


class StateManager:
    """Manages persistent state for leaving soon tagged timestamps.

    State file format:
    {
        "version": 1,
        "leaving_soon": {
            "Movies": {
                "12345": "2026-03-01T13:27:49",
                "12346": "2026-03-01T13:27:49"
            }
        }
    }
    """

    def __init__(self, state_file=STATE_FILE):
        self._state_file = state_file

    def load(self) -> dict:
        """Load state from file, return empty state if missing or corrupt."""
        try:
            with open(self._state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or data.get("version") != STATE_VERSION:
                logger.warning(
                    "State file has unexpected format or version, starting fresh"
                )
                return self._empty_state()
            return data
        except FileNotFoundError:
            return self._empty_state()
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read state file '%s': %s. Starting fresh.", self._state_file, e)
            return self._empty_state()

    def save(self, state: dict):
        """Atomically save state to file (write to temp, then rename)."""
        state_dir = os.path.dirname(self._state_file)
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=state_dir, prefix=".deleterr_state_", suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=2)
                os.replace(tmp_path, self._state_file)
            except Exception:
                # Clean up temp file on failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except OSError as e:
            logger.error("Failed to save state file '%s': %s", self._state_file, e)

    def get_tagged_dates(self, library_name: str) -> dict:
        """Get {rating_key: iso_timestamp} for a library.

        Returns:
            Dict mapping rating key (str) to ISO timestamp string.
        """
        state = self.load()
        return state.get("leaving_soon", {}).get(library_name, {})

    def set_tagged_dates(self, library_name: str, items: dict):
        """Set tagged dates for a library, merging with existing entries.

        Args:
            library_name: Plex library name
            items: Dict mapping rating key (str) to ISO timestamp string.
                   New keys are added; existing keys are NOT overwritten
                   (preserves the original tagged date).
        """
        state = self.load()
        leaving_soon = state.setdefault("leaving_soon", {})
        existing = leaving_soon.setdefault(library_name, {})

        for key, ts in items.items():
            key_str = str(key)
            if key_str not in existing:
                existing[key_str] = ts

        self.save(state)

    def remove_items(self, library_name: str, rating_keys: list):
        """Remove items from state (e.g., after deletion).

        Args:
            library_name: Plex library name
            rating_keys: List of rating keys to remove
        """
        if not rating_keys:
            return

        state = self.load()
        library_data = state.get("leaving_soon", {}).get(library_name, {})
        if not library_data:
            return

        for key in rating_keys:
            library_data.pop(str(key), None)

        # Clean up empty library entries
        if not library_data:
            state.get("leaving_soon", {}).pop(library_name, None)

        self.save(state)

    def cleanup_library(self, library_name: str, active_rating_keys: set):
        """Remove stale entries that are no longer in any collection.

        Args:
            library_name: Plex library name
            active_rating_keys: Set of rating keys that are currently tagged.
                                Any keys not in this set will be removed.
        """
        state = self.load()
        library_data = state.get("leaving_soon", {}).get(library_name, {})
        if not library_data:
            return

        active_str_keys = {str(k) for k in active_rating_keys}
        stale_keys = [k for k in library_data if k not in active_str_keys]

        if stale_keys:
            for key in stale_keys:
                del library_data[key]
            if not library_data:
                state.get("leaving_soon", {}).pop(library_name, None)
            self.save(state)
            logger.debug(
                "Cleaned up %d stale entries from state for library '%s'",
                len(stale_keys),
                library_name,
            )

    @staticmethod
    def _empty_state():
        return {"version": STATE_VERSION, "leaving_soon": {}}
