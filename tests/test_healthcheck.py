# encoding: utf-8
"""Healthcheck for the last-run status file (#294)."""

import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HEALTHCHECK_PATH = ROOT / "scripts" / "healthcheck.py"


def load_healthcheck():
    spec = importlib.util.spec_from_file_location("deleterr_healthcheck", HEALTHCHECK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def healthcheck():
    return load_healthcheck()


def _write(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _stamp(now, **fields):
    data = {
        "status": "success",
        "timestamp": now.isoformat(),
        "error": None,
        "interval_seconds": 3600,
        "last_success_at": now.isoformat(),
        "libraries_processed": 1,
        "libraries_failed": 0,
        "items_deleted": 0,
        "items_tagged": 0,
    }
    data.update(fields)
    return data


class TestHealthcheckScript:
    def test_fresh_success_is_healthy(self, healthcheck, tmp_path):
        now = datetime(2026, 11, 16, 9, 0, 0)
        path = tmp_path / "last_run.json"
        _write(path, _stamp(now))
        ok, reason = healthcheck.check(path, now=now, multiplier=2)
        assert ok is True
        assert reason == "healthy"

    def test_starting_within_the_window_is_healthy(self, healthcheck, tmp_path):
        now = datetime(2026, 11, 16, 9, 0, 0)
        started = now - timedelta(hours=1)
        path = tmp_path / "last_run.json"
        _write(
            path,
            _stamp(
                started,
                status="starting",
                last_success_at=None,
                libraries_processed=0,
            ),
        )
        ok, reason = healthcheck.check(path, now=now, multiplier=2)
        assert ok is True
        assert reason == "healthy"

    def test_missing_file_is_unhealthy(self, healthcheck, tmp_path):
        ok, reason = healthcheck.check(tmp_path / "missing.json", now=datetime(2026, 11, 16), multiplier=2)
        assert ok is False
        assert "missing" in reason.lower() or "not found" in reason.lower()

    def test_failed_status_is_unhealthy(self, healthcheck, tmp_path):
        now = datetime(2026, 11, 16, 9, 0, 0)
        path = tmp_path / "last_run.json"
        _write(path, _stamp(now, status="failed", error="boom", last_success_at=now.isoformat()))
        ok, reason = healthcheck.check(path, now=now, multiplier=2)
        assert ok is False
        assert "failed" in reason.lower()

    def test_stale_success_is_unhealthy(self, healthcheck, tmp_path):
        now = datetime(2026, 11, 16, 9, 0, 0)
        stale = now - timedelta(hours=3)
        path = tmp_path / "last_run.json"
        _write(path, _stamp(stale, interval_seconds=3600))
        ok, reason = healthcheck.check(path, now=now, multiplier=2)
        assert ok is False
        assert "stale" in reason.lower() or "older" in reason.lower()

    def test_success_just_inside_the_window_is_healthy(self, healthcheck, tmp_path):
        now = datetime(2026, 11, 16, 9, 0, 0)
        recent = now - timedelta(hours=2) + timedelta(seconds=1)
        path = tmp_path / "last_run.json"
        _write(path, _stamp(recent, interval_seconds=3600))
        ok, reason = healthcheck.check(path, now=now, multiplier=2)
        assert ok is True
        assert reason == "healthy"

    def test_starting_past_the_window_is_unhealthy(self, healthcheck, tmp_path):
        now = datetime(2026, 11, 16, 9, 0, 0)
        started = now - timedelta(hours=3)
        path = tmp_path / "last_run.json"
        _write(
            path,
            _stamp(started, status="starting", last_success_at=None, interval_seconds=3600),
        )
        ok, reason = healthcheck.check(path, now=now, multiplier=2)
        assert ok is False

    def test_invalid_json_is_unhealthy(self, healthcheck, tmp_path):
        path = tmp_path / "last_run.json"
        path.write_text("{not-json", encoding="utf-8")
        ok, reason = healthcheck.check(path, now=datetime(2026, 11, 16), multiplier=2)
        assert ok is False
        assert "invalid" in reason.lower() or "json" in reason.lower()

    def test_main_exits_one_when_unhealthy(self, healthcheck, tmp_path, monkeypatch):
        path = tmp_path / "last_run.json"
        monkeypatch.setenv("DELETERR_LAST_RUN_FILE", str(path))
        assert healthcheck.main() == 1


    def test_starting_with_a_stale_last_success_is_unhealthy(self, healthcheck, tmp_path):
        now = datetime(2026, 11, 16, 9, 0, 0)
        stale = now - timedelta(hours=3)
        started = now - timedelta(minutes=1)
        path = tmp_path / "last_run.json"
        _write(
            path,
            _stamp(
                started,
                status="starting",
                last_success_at=stale.isoformat(),
                interval_seconds=3600,
            ),
        )
        ok, reason = healthcheck.check(path, now=now, multiplier=2)
        assert ok is False
        assert "stale" in reason.lower()

    def test_main_can_be_disabled_with_an_environment_variable(self, healthcheck, tmp_path, monkeypatch):
        monkeypatch.setenv("DELETERR_LAST_RUN_FILE", str(tmp_path / "missing.json"))
        monkeypatch.setenv("DELETERR_HEALTHCHECK", "0")
        assert healthcheck.main() == 0
