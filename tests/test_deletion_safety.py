"""Offline safety boundaries over the real cleaner and library error handling (#296)."""

from unittest.mock import MagicMock

import pytest

from app.deleterr import Deleterr
from app.media_cleaner import MediaCleaner
from app.modules.tautulli import Tautulli
from app.modules.mdblist import MdblistError
from app.modules.trakt import TraktError


@pytest.fixture
def safety_library(request, monkeypatch):
    """One synthetic candidate, with network/storage clients replaced at their boundaries."""
    monkeypatch.setattr("requests.sessions.Session.request", MagicMock(side_effect=AssertionError("Network forbidden in safety fixture")))
    kind = request.param
    library = {"name": "Synthetic Library", kind: "fixture", "watch_status": "unwatched"}
    config = MagicMock(settings={"dry_run": False, "libraries": [library]})
    item = {"id": 42, "title": "Synthetic Candidate", "seriesType": "standard", "sizeOnDisk": 100,
            "statistics": {"sizeOnDisk": 100, "episodeFileCount": 1}}
    client = MagicMock()
    client.get_movies.return_value = [item]
    client.get_series.return_value = [item]
    client.get_episode.return_value = [{"id": 51, "episodeFileId": 61}]
    watch = Tautulli.__new__(Tautulli)
    watch.api = MagicMock()
    cleaner = MediaCleaner.__new__(MediaCleaner)
    cleaner.config = config
    cleaner.watch_provider = watch
    cleaner.trakt = MagicMock()
    cleaner.trakt.get_all_items_for_url.return_value = {}
    cleaner.mdblist = MagicMock()
    cleaner.mdblist.get_all_items_for_url.return_value = {}
    cleaner.plex = MagicMock()
    cleaner.plex.library.section.return_value = MagicMock(key="section-1", totalSize=1)
    cleaner.seerr = None
    # Once input safety gates pass, force an actionable candidate. Real processing and
    # deletion methods remain in place, so a missing gate reaches the mocked client.
    cleaner.process_library_rules = MagicMock(return_value=[item])
    run = Deleterr.__new__(Deleterr)
    run.config = config
    run.media_cleaner = cleaner
    run.radarr = {"fixture": client} if kind == "radarr" else {}
    run.sonarr = {"fixture": client} if kind == "sonarr" else {}
    run.run_result = MagicMock()
    run.libraries_processed = 0
    run.libraries_failed = 0
    run.library_failures = []
    return run, cleaner, watch, client, library


def run_library(rig):
    run, _, _, _, library = rig
    getattr(run, "process_radarr" if "radarr" in library else "process_sonarr")()


def deletion_boundaries(client):
    return client.del_movie, client.del_series, client.del_episode_file


@pytest.mark.parametrize("safety_library", ["radarr", "sonarr"], indirect=True)
@pytest.mark.parametrize("pages", [
    [{"data": []}],
    [None],
    [{"error": "unavailable"}],
    ["invalid-response"],
    [{"data": [{"rating_key": "42", "stopped": 1}]}, None],
    [{"data": [{"rating_key": "42", "stopped": 1}]}, {"error": "later-page-failed"}],
], ids=["empty", "failed-first", "error-first", "malformed-first", "partial-none", "partial-error"])
def test_degraded_history_skips_real_library_before_any_deletion(safety_library, pages, assert_no_deletions, monkeypatch):
    run, cleaner, watch, client, _ = safety_library
    watch.api.get_history.side_effect = pages
    error = MagicMock()
    monkeypatch.setattr("app.deleterr.logger.error", error)

    run_library(safety_library)

    assert_no_deletions(*deletion_boundaries(client), run.run_result.add_deleted)
    cleaner.process_library_rules.assert_not_called()
    assert run.libraries_failed == 1
    assert run.libraries_processed == 0
    assert len(run.library_failures) == 1
    assert any("Skipping library 'Synthetic Library'" in str(call) for call in error.call_args_list)
    if len(pages) > 1:
        assert watch.api.get_history.call_count == 2
        assert watch.api.get_history.call_args.kwargs["start"] == 1


@pytest.mark.parametrize("safety_library", ["radarr", "sonarr"], indirect=True)
@pytest.mark.parametrize("service,error_type", [("trakt", TraktError), ("mdblist", MdblistError)])
def test_exclusion_fetch_failure_skips_real_library_before_any_deletion(safety_library, service, error_type, assert_no_deletions):
    run, cleaner, watch, client, library = safety_library
    library["exclude"] = {service: {"lists": ["synthetic-protected-list"]}}
    getattr(cleaner, service).get_all_items_for_url.side_effect = error_type("Synthetic fetch failed")

    run_library(safety_library)

    assert_no_deletions(*deletion_boundaries(client), run.run_result.add_deleted)
    cleaner.process_library_rules.assert_not_called()
    watch.api.get_history.assert_not_called()
    assert run.libraries_failed == 1
    assert run.libraries_processed == 0
    assert "Synthetic fetch failed" in run.library_failures[0][1]


@pytest.mark.parametrize("safety_library", ["radarr", "sonarr"], indirect=True)
def test_fixture_reaches_mocked_deletion_when_all_safety_inputs_are_available(safety_library):
    """Negative control: zero-deletion checks cannot pass because the fixture has no candidates."""
    run, cleaner, watch, client, library = safety_library
    watch.api.get_history.side_effect = [{"data": [{"rating_key": "99", "stopped": 1}]}, {"data": []}]

    run_library(safety_library)

    cleaner.process_library_rules.assert_called_once()
    if "radarr" in library:
        client.del_movie.assert_called_once_with(42, delete_files=True, add_exclusion=False)
    else:
        client.del_episode_file.assert_called_once_with(61)
        client.del_series.assert_called_once_with(42, delete_files=True)
    assert run.libraries_processed == 1
    assert run.libraries_failed == 0


def test_zero_deletion_helper_checks_all_boundaries_and_requires_explicit_mocks(assert_no_deletions):
    first, second = MagicMock(), MagicMock()
    assert_no_deletions(first, second)
    second(42)
    with pytest.raises(AssertionError):
        assert_no_deletions(first, second)
    with pytest.raises(AssertionError):
        assert_no_deletions()
    with pytest.raises(AssertionError):
        assert_no_deletions(object())
