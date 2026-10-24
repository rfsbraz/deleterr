import logging
import os
from unittest.mock import patch

import pytest

from app.config import Config, load_config

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _settings(**overrides):
    settings = {
        "plex": {"url": "http://localhost:32400", "token": "TOKEN"},
        "radarr": [{"name": "Radarr", "url": "http://localhost:7878", "api_key": "KEY"}],
        "libraries": [
            {
                "name": "Movies",
                "radarr": "Radarr",
                "action_mode": "delete",
                "sort": {"field": "size", "order": "desc"},
                "exclude": {"titles": ["Heat"], "radarr": {"tags": ["keep"]}},
            }
        ],
    }
    settings.update(overrides)
    return settings


def _validate(settings, caplog):
    """Run startup validation and return the logged errors.

    Connection checks are stubbed to fail so a test that reaches them would
    also fail: unknown keys must stop startup before any network call.
    """
    config = Config(settings)
    with patch("app.config.hang_on_error", side_effect=SystemExit(1)), \
         patch.object(Config, "validate_config", return_value=True) as validate_config, \
         caplog.at_level(logging.ERROR, logger="deleterr"):
        try:
            config.validate()
            exited = False
        except SystemExit:
            exited = True
    errors = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    return exited, errors, validate_config


def test_valid_config_passes(caplog):
    exited, errors, validate_config = _validate(_settings(), caplog)
    assert not exited, errors
    validate_config.assert_called_once()


def test_unknown_top_level_key_fails(caplog):
    exited, errors, validate_config = _validate(_settings(dryrun=True), caplog)
    assert exited
    validate_config.assert_not_called()
    assert any("'dryrun'" in e and "did you mean 'dry_run'" in e for e in errors), errors


def test_unknown_key_in_library_list_item_names_full_path(caplog):
    settings = _settings()
    settings["libraries"][0]["sort"]["fieldd"] = "size"
    exited, errors, _ = _validate(settings, caplog)
    assert exited
    assert any("libraries[0].sort.fieldd" in e and "did you mean 'field'" in e for e in errors), errors


def test_misspelled_exclude_block_fails(caplog):
    settings = _settings()
    settings["libraries"][0]["excludes"] = settings["libraries"][0].pop("exclude")
    exited, errors, _ = _validate(settings, caplog)
    assert exited
    assert any("libraries[0].excludes" in e and "did you mean 'exclude'" in e for e in errors), errors


def test_unknown_key_in_second_library_and_nested_exclusion(caplog):
    settings = _settings()
    second = dict(settings["libraries"][0], name="Movies 4K")
    second["exclude"] = {"radarr": {"tagz": ["keep"]}}
    settings["libraries"].append(second)
    exited, errors, _ = _validate(settings, caplog)
    assert exited
    assert any("libraries[1].exclude.radarr.tagz" in e for e in errors), errors


def test_unknown_key_in_service_list_item(caplog):
    settings = _settings()
    settings["radarr"][0]["apikey"] = "KEY"
    exited, errors, _ = _validate(settings, caplog)
    assert exited
    assert any("radarr[0].apikey" in e and "did you mean 'api_key'" in e for e in errors), errors


def test_every_unknown_key_is_reported(caplog):
    settings = _settings(dryrun=True)
    settings["libraries"][0]["last_watch_threshold"] = 30
    exited, errors, _ = _validate(settings, caplog)
    assert exited
    joined = "\n".join(errors)
    assert "'dryrun'" in joined
    assert "libraries[0].last_watch_threshold" in joined
    assert "did you mean 'last_watched_threshold'" in joined


def test_unrelated_key_gets_no_suggestion(caplog):
    settings = _settings()
    settings["libraries"][0]["exclude"]["banana"] = ["x"]
    exited, errors, _ = _validate(settings, caplog)
    assert exited
    matching = [e for e in errors if "libraries[0].exclude.banana" in e]
    assert matching, errors
    assert not any("did you mean" in e for e in matching), matching


@pytest.mark.parametrize("key", ["exclude", "leaving_soon", "sort"])
def test_library_key_at_root_points_under_libraries(key, caplog):
    exited, errors, _ = _validate(_settings(**{key: {}}), caplog)
    assert exited
    assert any("did you mean" in e and f"'libraries[].{key}'" in e for e in errors), errors


def test_unsupported_exclude_tags_points_to_plex_labels(caplog):
    settings = _settings()
    settings["libraries"][0]["exclude"]["tags"] = ["keep"]
    exited, errors, _ = _validate(settings, caplog)
    assert exited
    assert any(
        "libraries[0].exclude.tags" in e
        and "'plex_labels'" in e
        and "'libraries[0].exclude.radarr.tags'" in e
        for e in errors
    ), errors


def test_free_form_mappings_are_not_checked(caplog):
    settings = _settings(
        notifications={"webhook": {"url": "http://x", "headers": {"X-Anything": "1"}}},
        seerr={"url": "http://localhost:5055", "api_key": "KEY"},
    )
    settings["libraries"][0]["exclude"]["seerr"] = {
        "protect_unwatched_requesters": {"user_mapping": {"someone": "else"}}
    }
    exited, errors, _ = _validate(settings, caplog)
    assert not exited, errors


def test_deprecated_overseerr_keys_still_accepted(caplog):
    settings = _settings(overseerr={"url": "http://localhost:5055", "api_key": "KEY"})
    settings["libraries"][0]["exclude"]["overseerr"] = {"mode": "exclude"}
    exited, errors, _ = _validate(settings, caplog)
    assert not exited, errors


@pytest.mark.parametrize(
    "path",
    [
        os.path.join(REPO_ROOT, "config", "settings.yaml.example"),
        *sorted(
            os.path.join(REPO_ROOT, "tests", "configs", name)
            for name in os.listdir(os.path.join(REPO_ROOT, "tests", "configs"))
            if name.endswith(".yaml")
        ),
    ],
    ids=os.path.basename,
)
def test_bundled_configs_have_no_unknown_keys(path, caplog):
    config = load_config(path)
    exited, errors, _ = _validate(config.settings, caplog)
    assert not exited, errors
