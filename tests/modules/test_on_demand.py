"""
Unit tests for the on-demand emergency cleanup mode (``--free-up``).

These verify the cross-library, per-disk, round-robin algorithm in
``app/on_demand.py`` in isolation: disk target building, path->disk mapping,
candidate gathering order, stopping exactly at the target, per-disk accounting,
round-robin across libraries, dry-run behavior, drift correction, and graceful
handling of an unreachable target.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.on_demand import (
    OnDemandCleaner,
    is_subpath,
    map_path_to_disk,
    item_size,
    normalize_path,
)


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #

class TestPathHelpers:
    def test_normalize_path_strips_trailing_slash(self):
        assert normalize_path("/data/") == "/data"
        assert normalize_path("/data") == "/data"
        assert normalize_path("/") == "/"

    def test_is_subpath_matches_on_segment_boundaries(self):
        assert is_subpath("/data/media/x", "/data") is True
        assert is_subpath("/data", "/data") is True
        # /data2 must NOT be treated as living under /data
        assert is_subpath("/data2/x", "/data") is False
        assert is_subpath("/other", "/data") is False

    def test_is_subpath_root_matches_everything(self):
        assert is_subpath("/anything/here", "/") is True

    def test_map_path_to_disk_longest_prefix(self):
        disks = ["/data", "/data/media"]
        assert map_path_to_disk("/data/media/movies/X", disks) == "/data/media"
        assert map_path_to_disk("/data/other/Y", disks) == "/data"
        assert map_path_to_disk("/mnt/z", disks) is None
        assert map_path_to_disk(None, disks) is None

    def test_item_size(self):
        assert item_size({"sizeOnDisk": 500}, "movie") == 500
        assert item_size({"statistics": {"sizeOnDisk": 700}}, "show") == 700
        assert item_size({}, "movie") == 0
        assert item_size({}, "show") == 0


# --------------------------------------------------------------------------- #
# Cleaner fixture (heavy deps mocked out)
# --------------------------------------------------------------------------- #

@pytest.fixture
def cleaner():
    """An OnDemandCleaner with all external dependencies mocked."""
    config = MagicMock()
    config.settings = {
        "dry_run": False,
        "libraries": [],
        "sonarr": [],
        "radarr": [],
        "plex": {"url": "http://plex", "token": "t"},
    }

    with patch("app.on_demand.PlexMediaServer", return_value=MagicMock()), \
         patch("app.on_demand.MediaCleaner", return_value=MagicMock()), \
         patch("app.on_demand.NotificationManager", return_value=MagicMock()):
        c = OnDemandCleaner(config)

    c.notifications.is_enabled.return_value = False
    return c


def _movie(title, path, size):
    return {"title": title, "path": path, "sizeOnDisk": size, "year": 2000}


def _library_queue(name, instance_key, media_type, items, cleaner):
    """Build a per-library queue entry as _gather_candidates would."""
    library = {"name": name, ("radarr" if media_type == "movie" else "sonarr"): instance_key}
    return {
        "library": library,
        "instance": MagicMock(),
        "media_type": media_type,
        "queue": list(items),
    }


# --------------------------------------------------------------------------- #
# Disk target building
# --------------------------------------------------------------------------- #

class TestBuildDiskTargets:
    def test_keeps_under_target_and_dedupes_same_mount(self, cleaner):
        radarr = MagicMock()
        radarr.get_disk_space.return_value = [
            {"path": "/data", "freeSpace": 100},
            {"path": "/movies", "freeSpace": 5000},
        ]
        sonarr = MagicMock()
        # Same physical mount /data reported again - must be deduped.
        sonarr.get_disk_space.return_value = [{"path": "/data", "freeSpace": 100}]
        cleaner.radarr = {"R": radarr}
        cleaner.sonarr = {"S": sonarr}

        disks = cleaner._build_disk_targets(target_bytes=1000, free_up_path=None)

        assert [d["path"] for d in disks] == ["/data"]  # /movies is above target
        assert disks[0]["deficit"] == 900
        # First instance that reported /data wins (dedupe keeps one).
        assert disks[0]["instance"] is radarr

    def test_free_up_path_restricts_to_one_mount(self, cleaner):
        radarr = MagicMock()
        radarr.get_disk_space.return_value = [
            {"path": "/data", "freeSpace": 100},
            {"path": "/movies", "freeSpace": 100},
        ]
        cleaner.radarr = {"R": radarr}
        cleaner.sonarr = {}

        disks = cleaner._build_disk_targets(target_bytes=1000, free_up_path="/data")

        assert [d["path"] for d in disks] == ["/data"]

    def test_no_under_target_disks_returns_empty(self, cleaner):
        radarr = MagicMock()
        radarr.get_disk_space.return_value = [{"path": "/data", "freeSpace": 9000}]
        cleaner.radarr = {"R": radarr}
        cleaner.sonarr = {}

        assert cleaner._build_disk_targets(target_bytes=1000, free_up_path=None) == []


# --------------------------------------------------------------------------- #
# Candidate gathering
# --------------------------------------------------------------------------- #

class TestGatherCandidates:
    def test_buckets_candidates_per_disk_in_config_order(self, cleaner):
        radarr = MagicMock()
        sonarr = MagicMock()
        sonarr.get_series.return_value = []
        cleaner.radarr = {"R": radarr}
        cleaner.sonarr = {"S": sonarr}
        cleaner.config.settings["libraries"] = [
            {"name": "Movies", "radarr": "R"},
            {"name": "Shows", "sonarr": "S"},
        ]

        def fake_candidates(library, instance, media_type, all_data):
            if media_type == "movie":
                return [_movie("A", "/data/movies/A", 100)]
            return [{"title": "S1", "path": "/data/tv/S1", "statistics": {"sizeOnDisk": 200}}]

        cleaner.media_cleaner.get_ordered_candidates.side_effect = fake_candidates

        disk = {"path": "/data", "free_space": 0, "target": 1000,
                "deficit": 1000, "libraries": [], "instance": radarr}
        cleaner._gather_candidates([disk], target_bytes=1000)

        # Both libraries mapped onto /data, in config order (Movies then Shows).
        assert [q["library"]["name"] for q in disk["libraries"]] == ["Movies", "Shows"]
        assert cleaner.libraries_processed == 2

    def test_candidates_on_other_disks_are_dropped(self, cleaner):
        radarr = MagicMock()
        cleaner.radarr = {"R": radarr}
        cleaner.sonarr = {}
        cleaner.config.settings["libraries"] = [{"name": "Movies", "radarr": "R"}]
        cleaner.media_cleaner.get_ordered_candidates.return_value = [
            _movie("OnDisk", "/data/movies/OnDisk", 100),
            _movie("Elsewhere", "/other/movies/Elsewhere", 100),
        ]

        disk = {"path": "/data", "free_space": 0, "target": 1000,
                "deficit": 1000, "libraries": [], "instance": radarr}
        cleaner._gather_candidates([disk], target_bytes=1000)

        titles = [i["title"] for q in disk["libraries"] for i in q["queue"]]
        assert titles == ["OnDisk"]


# --------------------------------------------------------------------------- #
# Round-robin deletion
# --------------------------------------------------------------------------- #

class TestProcessDisk:
    def _disk(self, cleaner, free_space, target, libraries):
        return {
            "path": "/data",
            "free_space": free_space,
            "target": target,
            "deficit": target - free_space,
            "freed": 0,
            "final_free": free_space,
            "instance": MagicMock(),
            "libraries": libraries,
        }

    def test_round_robin_order_and_stops_at_target(self, cleaner):
        libA = _library_queue("A", "R", "movie",
                              [_movie("a1", "/data/a1", 100),
                               _movie("a2", "/data/a2", 100),
                               _movie("a3", "/data/a3", 100)], cleaner)
        libB = _library_queue("B", "R", "movie",
                              [_movie("b1", "/data/b1", 100),
                               _movie("b2", "/data/b2", 100)], cleaner)
        disk = self._disk(cleaner, free_space=0, target=500, libraries=[libA, libB])

        cleaner._process_disk(disk)

        deleted = [d.title for d in cleaner.run_result.deleted_items]
        # A, B, A, B, A -> exactly 500 freed, then stop.
        assert deleted == ["a1", "b1", "a2", "b2", "a3"]
        assert disk["freed"] == 500
        assert disk["final_free"] == 500

    def test_stops_immediately_when_target_met_midway(self, cleaner):
        libA = _library_queue("A", "R", "movie",
                              [_movie("a1", "/data/a1", 100),
                               _movie("a2", "/data/a2", 100),
                               _movie("a3", "/data/a3", 100)], cleaner)
        libB = _library_queue("B", "R", "movie",
                              [_movie("b1", "/data/b1", 100),
                               _movie("b2", "/data/b2", 100)], cleaner)
        disk = self._disk(cleaner, free_space=0, target=250, libraries=[libA, libB])

        cleaner._process_disk(disk)

        deleted = [d.title for d in cleaner.run_result.deleted_items]
        assert deleted == ["a1", "b1", "a2"]  # 300 >= 250, stop
        # Untouched candidates remain queued.
        assert [i["title"] for i in libA["queue"]] == ["a3"]
        assert [i["title"] for i in libB["queue"]] == ["b2"]

    def test_actually_calls_delete_when_not_dry_run(self, cleaner):
        cleaner.is_dry_run = False
        entry = _library_queue("A", "R", "movie", [_movie("a1", "/data/a1", 1000)], cleaner)
        disk = self._disk(cleaner, free_space=0, target=500, libraries=[entry])

        cleaner._process_disk(disk)

        cleaner.media_cleaner.delete_movie_if_allowed.assert_called_once()

    def test_dry_run_deletes_nothing_but_accounts_space(self, cleaner):
        cleaner.is_dry_run = True
        entry = _library_queue("A", "R", "movie",
                              [_movie("a1", "/data/a1", 300),
                               _movie("a2", "/data/a2", 300)], cleaner)
        disk = self._disk(cleaner, free_space=0, target=500, libraries=[entry])

        cleaner._process_disk(disk)

        cleaner.media_cleaner.delete_movie_if_allowed.assert_not_called()
        assert disk["freed"] == 600  # both counted optimistically
        assert len(cleaner.run_result.deleted_items) == 2

    def test_unreachable_target_warns_and_frees_what_it_can(self, cleaner):
        entry = _library_queue("A", "R", "movie",
                              [_movie("a1", "/data/a1", 100),
                               _movie("a2", "/data/a2", 100),
                               _movie("a3", "/data/a3", 100)], cleaner)
        disk = self._disk(cleaner, free_space=0, target=1000, libraries=[entry])

        cleaner._process_disk(disk)

        assert disk["freed"] == 300
        assert disk["final_free"] == 300  # below target, but no infinite loop
        assert len(cleaner.run_result.deleted_items) == 3

    def test_series_deletion_skip_not_counted(self, cleaner):
        cleaner.is_dry_run = False
        # delete_series returns False (e.g. episode file in use) -> not counted.
        cleaner.media_cleaner.delete_series.return_value = False
        entry = {
            "library": {"name": "TV", "sonarr": "S"},
            "instance": MagicMock(),
            "media_type": "show",
            "queue": [{"title": "S1", "path": "/data/tv/S1",
                       "statistics": {"sizeOnDisk": 400}}],
        }
        disk = self._disk(cleaner, free_space=0, target=300, libraries=[entry])

        cleaner._process_disk(disk)

        assert disk["freed"] == 0
        assert cleaner.run_result.deleted_items == []

    def test_drift_correction_requeries_free_space(self, cleaner):
        cleaner.is_dry_run = False
        instance = MagicMock()
        # After the 10th deletion the disk really has plenty free.
        instance.get_disk_space.return_value = [{"path": "/data", "freeSpace": 2100}]
        items = [_movie(f"m{i}", f"/data/m{i}", 100) for i in range(15)]
        entry = {
            "library": {"name": "Movies", "radarr": "R"},
            "instance": MagicMock(),
            "media_type": "movie",
            "queue": items,
        }
        disk = self._disk(cleaner, free_space=0, target=2000, libraries=[entry])
        disk["instance"] = instance

        cleaner._process_disk(disk)

        # Optimistic sum after 10 deletions is 1000; the re-query bumps free space
        # to 2100 >= 2000, so we stop at 10 rather than exhausting all 15.
        instance.get_disk_space.assert_called()
        assert len(cleaner.run_result.deleted_items) == 10
        assert disk["final_free"] == 2100


# --------------------------------------------------------------------------- #
# End-to-end run wiring
# --------------------------------------------------------------------------- #

class TestRun:
    def test_run_no_disks_short_circuits(self, cleaner):
        cleaner._build_disk_targets = MagicMock(return_value=[])
        cleaner._gather_candidates = MagicMock()

        cleaner.run(target_bytes=1000)

        cleaner._gather_candidates.assert_not_called()
        assert cleaner.run_result.end_time is not None

    def test_run_processes_each_disk(self, cleaner):
        disk1 = {"path": "/data", "target": 1000, "deficit": 1000,
                 "free_space": 0, "final_free": 0, "freed": 0, "libraries": []}
        disk2 = {"path": "/media", "target": 1000, "deficit": 1000,
                 "free_space": 0, "final_free": 0, "freed": 0, "libraries": []}
        cleaner._build_disk_targets = MagicMock(return_value=[disk1, disk2])
        cleaner._gather_candidates = MagicMock()
        cleaner._process_disk = MagicMock()

        cleaner.run(target_bytes=1000, free_up_path="/x")

        assert cleaner._process_disk.call_count == 2
        cleaner._build_disk_targets.assert_called_once_with(1000, "/x")
