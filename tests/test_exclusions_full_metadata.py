"""Exclusions must use full Plex metadata, not partial listing items (#317)."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.media_cleaner import MediaCleaner


@pytest.fixture
def media_cleaner():
    config = MagicMock(settings={"plex": {"url": "http://plex", "token": "t"}})
    with patch("app.media_cleaner.PlexServer"), \
            patch("app.modules.plex_watch_provider.PlexServer"):
        yield MediaCleaner(config)


def _tag(name):
    tag = MagicMock()
    tag.tag = name
    return tag


def _partial_plex_item(partial_genres, full_genres, **full_tags):
    """A Plex item as returned by library listings: partial tags until reload()."""
    item = MagicMock(
        title="Spirited Away", year=2001, guid="plex://movie/sa", guids=[],
        ratingKey=1, studio=None, addedAt=datetime(2015, 1, 1),
    )
    item.genres = [_tag(g) for g in partial_genres]
    for attr in ("collections", "labels", "producers", "directors", "writers", "roles"):
        setattr(item, attr, [])
    state = {"partial": True}
    item.isPartialObject.side_effect = lambda: state["partial"]

    def reload():
        state["partial"] = False
        item.genres = [_tag(g) for g in full_genres]
        for attr, values in full_tags.items():
            setattr(item, attr, [_tag(v) for v in values])
        return item

    item.reload.side_effect = reload
    return item


class TestExclusionsUseFullPlexMetadata:
    """Exclusions must not miss tags truncated in partial Plex listings (#317)."""

    media_data = {"title": "Spirited Away", "year": 2001}

    def test_genre_beyond_partial_listing_excludes(self, media_cleaner):
        item = _partial_plex_item(["Animation", "Adventure"], ["Animation", "Adventure", "Family"])
        library = {"exclude": {"genres": ["Family"]}}

        assert media_cleaner.check_exclusions(library, self.media_data, item) is False
        item.reload.assert_called_once()

    @pytest.mark.parametrize(
        "exclude_key, attr",
        [
            ("collections", "collections"),
            ("plex_labels", "labels"),
            ("producers", "producers"),
            ("directors", "directors"),
            ("writers", "writers"),
            ("actors", "roles"),
        ],
    )
    def test_other_tag_exclusions_use_full_item(self, media_cleaner, exclude_key, attr):
        item = _partial_plex_item([], [], **{attr: ["Keep Me"]})
        library = {"exclude": {exclude_key: ["Keep Me"]}}

        assert media_cleaner.check_exclusions(library, self.media_data, item) is False

    def test_no_reload_without_tag_exclusions(self, media_cleaner):
        item = _partial_plex_item(["Animation"], ["Animation", "Family"])
        library = {"exclude": {"titles": ["Other"], "release_years": 0}}

        assert media_cleaner.check_exclusions(library, self.media_data, item) is True
        item.reload.assert_not_called()

    def test_no_reload_when_partial_tags_already_match(self, media_cleaner):
        item = _partial_plex_item(["Animation"], ["Animation", "Family"])
        library = {"exclude": {"genres": ["Animation"]}}

        assert media_cleaner.check_exclusions(library, self.media_data, item) is False
        item.reload.assert_not_called()

    def test_reloads_at_most_once_per_item(self, media_cleaner):
        item = _partial_plex_item(["Animation"], ["Animation", "Family"])
        library = {"exclude": {"genres": ["Horror"]}}

        assert media_cleaner.check_exclusions(library, self.media_data, item) is True
        assert media_cleaner.check_exclusions(library, self.media_data, item) is True
        item.reload.assert_called_once()

    def test_reload_failure_fails_safe(self, media_cleaner):
        item = _partial_plex_item(["Animation"], ["Animation", "Family"])
        item.reload.side_effect = Exception("Plex unavailable")
        library = {"exclude": {"genres": ["Family"]}}

        assert media_cleaner.check_exclusions(library, self.media_data, item) is False

    def test_free_up_candidates_respect_full_genres(self, media_cleaner):
        """get_ordered_candidates (--free-up) runs the same exclusion checks."""
        item = _partial_plex_item(["Animation", "Adventure"], ["Animation", "Adventure", "Family"])
        plex_library = MagicMock(key=1, totalSize=1)
        plex_library.all.return_value = [item]
        media_cleaner.get_plex_library = MagicMock(return_value=plex_library)
        media_cleaner.watch_provider = MagicMock()
        media_cleaner.watch_provider.get_activity.return_value = {}
        radarr = MagicMock()
        radarr.get_movies.return_value = [{
            "title": "Spirited Away", "year": 2001, "alternateTitles": [],
            "tmdbId": 129, "movieFileId": 1, "sizeOnDisk": 1, "path": "/movies/sa",
        }]
        library = {"name": "Movies", "radarr": "Radarr", "exclude": {"genres": ["Family"]}}

        assert media_cleaner.get_ordered_candidates(library, radarr, "movie") == []
