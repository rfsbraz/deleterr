"""String exclusions must match regardless of case on either side (#320)."""

from unittest.mock import MagicMock

import pytest

from app.media_cleaner import check_excluded_studios

MEDIA = {"title": "Spirited Away"}


@pytest.mark.parametrize(
    "plex_studio, configured",
    [
        ("Studio Ghibli", ["Studio Ghibli"]),
        ("Studio Ghibli", ["studio ghibli"]),
        ("studio ghibli", ["Studio Ghibli"]),
        ("STUDIO GHIBLI", ["A24", "Studio Ghibli"]),
    ],
)
def test_studio_exclusion_ignores_case(plex_studio, configured):
    item = MagicMock(studio=plex_studio)
    assert check_excluded_studios(MEDIA, item, {"studios": configured}) is False


def test_other_studio_not_excluded():
    item = MagicMock(studio="Toho")
    assert check_excluded_studios(MEDIA, item, {"studios": ["Studio Ghibli"]}) is True


@pytest.mark.parametrize("studio", [None, ""])
def test_missing_studio_not_excluded(studio):
    item = MagicMock(studio=studio)
    assert check_excluded_studios(MEDIA, item, {"studios": ["Studio Ghibli"]}) is True


def test_no_studio_exclusions_configured():
    item = MagicMock(studio="Studio Ghibli")
    assert check_excluded_studios(MEDIA, item, {}) is True


def _tag(name):
    tag = MagicMock()
    tag.tag = name
    return tag


@pytest.mark.parametrize(
    "check_name, exclude_key, attr",
    [
        ("check_excluded_genres", "genres", "genres"),
        ("check_excluded_collections", "collections", "collections"),
        ("check_excluded_labels", "plex_labels", "labels"),
        ("check_excluded_producers", "producers", "producers"),
        ("check_excluded_directors", "directors", "directors"),
        ("check_excluded_writers", "writers", "writers"),
        ("check_excluded_actors", "actors", "roles"),
    ],
)
@pytest.mark.parametrize("plex_value, configured", [("Hayao Miyazaki", "hayao MIYAZAKI"), ("hayao miyazaki", "Hayao Miyazaki")])
def test_tag_exclusions_ignore_case(check_name, exclude_key, attr, plex_value, configured):
    import app.media_cleaner as mc

    item = MagicMock()
    setattr(item, attr, [_tag(plex_value)])
    assert getattr(mc, check_name)(MEDIA, item, {exclude_key: [configured]}) is False


def test_title_exclusion_ignores_case():
    from app.media_cleaner import check_excluded_titles

    item = MagicMock(title="spirited away")
    assert check_excluded_titles(MEDIA, item, {"titles": ["Spirited Away"]}) is False
