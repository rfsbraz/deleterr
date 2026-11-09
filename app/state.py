# encoding: utf-8
"""State persistence for tracking when items were tagged to leaving soon."""

import json
import os
import shutil
import tempfile
from datetime import datetime

from app import logger

STATE_FILE = "/config/.deleterr_state.json"
STATE_VERSION = 1

# One function per old version, upgrading its state dict to the next version. Bumping
# STATE_VERSION needs an entry here, or old files are set aside and timers restart.
MIGRATIONS = {}


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
        self._backup_file = state_file + ".bak"
        self._rejected = []

    def load(self) -> dict:
        """Load state from file, falling back to the backup, then to empty state.

        Old versions are migrated. Loading never changes files on disk (dry runs
        read state too). A file that could not be used is copied aside by the next
        save, before it is replaced.
        """
        rejected = []
        for path in (self._state_file, self._backup_file):
            try:
                data = self._read(path)
            except FileNotFoundError:
                continue
            except (ValueError, OSError) as e:
                logger.warning("Failed to read state file '%s': %s", path, e)
                rejected.append(path)
                continue
            self._rejected = rejected
            if path == self._backup_file:
                logger.warning("Recovered state from backup '%s'", path)
            return data
        self._rejected = rejected
        if rejected:
            logger.error(
                "State file '%s' could not be used and was reset; leaving soon timers "
                "restart and notifications may be sent again. The unreadable file is "
                "kept as '<name>.reset-<date>' on the next save.",
                self._state_file,
            )
        return self._empty_state()

    def _read(self, path: str) -> dict:
        """Read and migrate one state file. Raises ValueError if it cannot be used."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not isinstance(data.get("version"), int):
            raise ValueError("unexpected format")
        version = data["version"]
        if version > STATE_VERSION:
            raise ValueError(f"version {version} is newer than {STATE_VERSION}")
        while version < STATE_VERSION:
            if version not in MIGRATIONS:
                raise ValueError(f"no migration from version {version}")
            data = MIGRATIONS[version](data)
            version += 1
            data["version"] = version
        return data

    def save(self, state: dict):
        """Atomically save state to file and to its backup (write to temp, then rename)."""
        try:
            self._keep_rejected()
            self._write(self._state_file, state)
            self._write(self._backup_file, state)
        except OSError as e:
            logger.error("Failed to save state file '%s': %s", self._state_file, e)

    def _keep_rejected(self):
        """Copy files the last load could not use aside, before they are replaced."""
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        for path in self._rejected:
            if os.path.exists(path):
                kept = f"{path}.reset-{stamp}"
                shutil.copy2(path, kept)
                logger.warning("Kept unreadable state file as '%s'", kept)
        self._rejected = []

    def _write(self, path: str, state: dict):
        fd, tmp_path = tempfile.mkstemp(
            dir=os.path.dirname(path), prefix=".deleterr_state_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            os.replace(tmp_path, path)
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

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
