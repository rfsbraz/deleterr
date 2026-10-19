# encoding: utf-8
"""A dry run must never write the leaving_soon state file (#291)."""

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.state import StateManager


@pytest.fixture
def state_file(tmp_path):
    path = tmp_path / ".deleterr_state.json"
    state = {
        "version": 1,
        "leaving_soon": {
            # Tagged long ago, so its duration has elapsed and it would be deleted
            "Movies": {"100": (datetime.now() - timedelta(days=30)).isoformat()},
            # Belongs to another library, must survive any cleanup untouched
            "Shows": {"900": "2026-01-01T00:00:00"},
        },
    }
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return path


@pytest.fixture
def deleterr_instance(state_file):
    from app.deleterr import Deleterr

    d = Deleterr.__new__(Deleterr)
    d.config = MagicMock()
    d.config.settings = {"dry_run": True}
    d.media_server = MagicMock()
    d.media_cleaner = MagicMock()
    d.notifications = MagicMock()
    d.notifications.is_leaving_soon_enabled.return_value = True
    d.state_manager = StateManager(state_file=str(state_file))
    d.run_result = MagicMock()
    return d


def _plex_item(rating_key, title):
    item = MagicMock()
    item.ratingKey = rating_key
    item.title = title
    item.year = 2024
    return item


def test_dry_run_leaves_state_file_byte_identical(deleterr_instance, state_file):
    before = state_file.read_bytes()

    elapsed = _plex_item(100, "Elapsed Movie")
    # On death row in Plex but missing from state (e.g. tagged by an older version)
    untracked = _plex_item(200, "Untracked Movie")
    fresh = _plex_item(300, "Fresh Movie")

    candidates = {
        "tt100": {"id": 1, "title": "Elapsed Movie", "tmdbId": "tt100", "year": 2024, "sizeOnDisk": 1000},
        "tt200": {"id": 2, "title": "Untracked Movie", "tmdbId": "tt200", "year": 2024, "sizeOnDisk": 1000},
        "tt300": {"id": 3, "title": "Fresh Movie", "tmdbId": "tt300", "year": 2024, "sizeOnDisk": 1000},
    }
    plex_by_tmdb = {"tt100": elapsed, "tt200": untracked, "tt300": fresh}

    d = deleterr_instance
    d.media_server.get_library.return_value = MagicMock()
    d.media_server.find_item.side_effect = lambda lib, **kw: plex_by_tmdb.get(kw.get("tmdb_id"))
    d._get_death_row_items = MagicMock(return_value=[elapsed, untracked])
    d._get_deletion_candidates = MagicMock(return_value=list(candidates.values()))
    d._get_universe_ids = MagicMock(return_value=set())
    d._is_universe_member = MagicMock(return_value=True)
    d.media_cleaner.process_leaving_soon.return_value = [untracked, fresh]

    library = {
        "name": "Movies",
        "leaving_soon": {"collection": {"name": "Leaving Soon"}, "duration": "7d"},
    }

    with patch("app.media_cleaner.library_meets_disk_space_threshold", return_value=True):
        _, deleted, preview, _, prior, foreign = d._process_death_row(library, MagicMock(), "movie")
    d._process_library_leaving_soon(
        library, preview or [], "movie", death_row_plex_items=prior, foreign_plex_items=foreign
    )

    # The elapsed item is reported as a would-be deletion, nothing is actually deleted
    assert [m["title"] for m in deleted] == ["Elapsed Movie"]
    assert state_file.read_bytes() == before
