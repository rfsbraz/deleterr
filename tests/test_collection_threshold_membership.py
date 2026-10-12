"""Collection last-watched threshold must use full collection membership (#321).

Plex library listings return partial items, so ``item.collections`` can be
missing or truncated. Membership is built once per library run from the
library's collections instead.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.media_cleaner import MediaCleaner


@pytest.fixture
def media_cleaner():
    config = MagicMock(settings={"plex": {"url": "http://plex", "token": "t"}})
    with patch("app.media_cleaner.PlexServer"), \
            patch("app.modules.plex_watch_provider.PlexServer"):
        yield MediaCleaner(config)


def _plex_item(rating_key, title):
    # Partial listing item: no collection tags (as Plex often returns)
    return MagicMock(
        guid=f"plex://movie/{rating_key}", guids=[], ratingKey=rating_key,
        title=title, year=2001, collections=[], genres=[], labels=[],
        studio=None, addedAt=datetime(2015, 1, 1),
    )


def _collection(title, items):
    collection = MagicMock(title=title)
    collection.items.return_value = items
    return collection


def _radarr_movie(title):
    return {"title": title, "year": 2001, "alternateTitles": [], "movieFileId": 1,
            "sizeOnDisk": 1, "path": f"/movies/{title}"}


LIBRARY = {
    "name": "Movies",
    "radarr": "Radarr",
    "last_watched_threshold": 30,
    "apply_last_watch_threshold_to_collections": True,
}


def _setup(media_cleaner, collections=None, collections_error=None):
    watched = _plex_item(1, "Castle in the Sky")
    candidate = _plex_item(2, "Spirited Away")
    plex_library = MagicMock(key=1, totalSize=2)
    plex_library.all.return_value = [watched, candidate]
    if collections_error:
        plex_library.collections.side_effect = collections_error
    else:
        plex_library.collections.return_value = (
            collections if collections is not None
            else [_collection("Studio Ghibli", [watched, candidate])]
        )
    media_cleaner.get_plex_library = MagicMock(return_value=plex_library)
    media_cleaner.watch_provider = MagicMock()
    media_cleaner.watch_provider.get_activity.return_value = {
        "plex://movie/1": {
            "last_watched": datetime.now() - timedelta(days=5),
            "title": "Castle in the Sky", "year": 2001,
        }
    }
    radarr = MagicMock()
    radarr.get_movies.return_value = [
        _radarr_movie("Castle in the Sky"), _radarr_movie("Spirited Away"),
    ]
    return plex_library, radarr


def _titles(candidates):
    return [c["title"] for c in candidates]


def test_watched_collection_protects_candidate(media_cleaner):
    """--free-up path: a recently watched collection member protects the rest."""
    plex_library, radarr = _setup(media_cleaner)

    candidates = media_cleaner.get_ordered_candidates(LIBRARY, radarr, "movie")

    assert _titles(candidates) == []


def test_unrelated_collection_does_not_protect(media_cleaner):
    plex_library, radarr = _setup(media_cleaner)
    watched, candidate = plex_library.all.return_value
    plex_library.collections.return_value = [
        _collection("Studio Ghibli", [watched]),
        _collection("Other", [candidate]),
    ]

    candidates = media_cleaner.get_ordered_candidates(LIBRARY, radarr, "movie")

    assert _titles(candidates) == ["Spirited Away"]


def test_scheduled_run_uses_membership(media_cleaner):
    """Scheduled runs share process_library_rules with --free-up."""
    plex_library, radarr = _setup(media_cleaner)

    candidates = list(media_cleaner.process_library_rules(
        LIBRARY, plex_library, radarr.get_movies(),
        media_cleaner.watch_provider.get_activity(1), {}, radarr_instance=radarr,
    ))

    assert _titles(candidates) == []


def test_collections_fetched_once_per_library_run(media_cleaner):
    plex_library, radarr = _setup(media_cleaner)

    media_cleaner.get_ordered_candidates(LIBRARY, radarr, "movie")

    plex_library.collections.assert_called_once()
    for collection in plex_library.collections.return_value:
        collection.items.assert_called_once()
    for item in plex_library.all.return_value:
        item.reload.assert_not_called()


def test_collections_fetch_failure_fails_safe(media_cleaner):
    plex_library, radarr = _setup(media_cleaner, collections_error=Exception("Plex down"))

    with patch("app.media_cleaner.logger") as mock_logger:
        candidates = media_cleaner.get_ordered_candidates(LIBRARY, radarr, "movie")

    assert _titles(candidates) == []
    assert mock_logger.warning.called


def test_collections_not_fetched_when_feature_disabled(media_cleaner):
    plex_library, radarr = _setup(media_cleaner)
    library = dict(LIBRARY, apply_last_watch_threshold_to_collections=False)

    candidates = media_cleaner.get_ordered_candidates(library, radarr, "movie")

    plex_library.collections.assert_not_called()
    assert _titles(candidates) == ["Spirited Away"]
