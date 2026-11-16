#!/usr/bin/env python3
"""Check the last-run status file for Docker HEALTHCHECK. Stdlib only."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

DEFAULT_PATH = "/config/.deleterr_last_run.json"
DEFAULT_MULTIPLIER = 2
FAILED_STATUS = "failed"
FRESH_STATUSES = {"success", "partial", "starting"}


def _as_int(value, default=None):
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        return int(value)
    return default


def _parse_dt(value):
    if not value or not isinstance(value, str):
        return None
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _align_tz(parsed, now):
    if parsed.tzinfo is not None and now.tzinfo is None:
        return parsed.replace(tzinfo=None), now
    if parsed.tzinfo is None and now.tzinfo is not None:
        return parsed, now.replace(tzinfo=None)
    return parsed, now


def _load_status(path):
    path = Path(path)
    if not path.is_file():
        return None, f"status file missing: {path}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"status file invalid: {exc}"
    if not isinstance(data, dict):
        return None, "status file invalid: not an object"
    return data, None


def _reference_time(data, status):
    if status in {"success", "partial"}:
        return data.get("last_success_at") or data.get("timestamp")
    return data.get("timestamp")


def _stale_reason(data, status, now, multiplier):
    interval = _as_int(data.get("interval_seconds"))
    if interval is None or interval <= 0:
        return "status file missing a valid interval_seconds"
    parsed = _parse_dt(_reference_time(data, status))
    if parsed is None:
        return "status file missing a valid timestamp"
    parsed, now = _align_tz(parsed, now)
    max_age = interval * multiplier
    age = (now - parsed).total_seconds()
    if age > max_age:
        return f"last run is stale: {age:.0f}s old, limit is {max_age:.0f}s"
    return None


def check(path, now=None, multiplier=None):
    """Return (ok, reason) for a last-run status file."""
    if now is None:
        now = datetime.now()
    if multiplier is None:
        multiplier = DEFAULT_MULTIPLIER
    data, error = _load_status(path)
    if error:
        return False, error
    status = data.get("status")
    if status == FAILED_STATUS:
        return False, f"last run failed: {data.get('error') or 'no error recorded'}"
    if status not in FRESH_STATUSES:
        return False, f"unrecognized status: {status!r}"
    stale = _stale_reason(data, status, now, multiplier)
    if stale:
        return False, stale
    return True, "healthy"


def _multiplier_from_env():
    raw = os.environ.get("DELETERR_HEALTH_MULTIPLIER", str(DEFAULT_MULTIPLIER))
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_MULTIPLIER
    if value <= 0:
        return DEFAULT_MULTIPLIER
    return value


def main(argv=None):
    path = os.environ.get("DELETERR_LAST_RUN_FILE", DEFAULT_PATH)
    ok, reason = check(path, multiplier=_multiplier_from_env())
    if not ok:
        print(reason, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
