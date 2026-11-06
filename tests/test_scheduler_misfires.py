"""Exercise delayed cleanups with APScheduler's real in-memory job store."""
from datetime import datetime, timedelta, timezone
from threading import Event
from unittest.mock import MagicMock, patch

import pytest
from apscheduler.events import EVENT_JOB_MAX_INSTANCES, JobSubmissionEvent
from apscheduler.schedulers.background import BackgroundScheduler

from app.scheduler import DeleterrScheduler


@pytest.fixture
def scheduler_clock():
    engine = BackgroundScheduler(timezone="UTC")
    engine.start(paused=True)
    config = MagicMock()
    config.settings = {"scheduler": {"schedule": "weekly", "run_on_startup": False}}
    with patch("app.scheduler.BlockingScheduler", return_value=engine), patch.object(
        DeleterrScheduler, "_setup_signal_handlers"
    ):
        wrapper = DeleterrScheduler(config)
    ran = Event()
    notified = Event()
    wrapper._run_deleterr = MagicMock(side_effect=ran.set)
    wrapper._record_last_run = MagicMock()
    wrapper._notify_failure = MagicMock(side_effect=lambda _: notified.set())
    try:
        yield engine, wrapper, ran, notified
    finally:
        engine.shutdown(wait=True)


def add_cleanup(engine, wrapper):
    # The test engine already runs paused; production uses BlockingScheduler.
    with patch.object(engine, "start"):
        wrapper.start()
    return engine.get_job("deleterr_cleanup")


def test_delayed_weekly_cleanup_runs_instead_of_being_dropped(scheduler_clock):
    engine, wrapper, ran, notified = scheduler_clock
    job = add_cleanup(engine, wrapper)
    job.modify(next_run_time=datetime.now(timezone.utc) - timedelta(minutes=2))
    engine.resume()
    assert ran.wait(5), "a cleanup delayed beyond the old one-second grace was dropped"
    assert wrapper._run_deleterr.call_count == 1
    assert not notified.is_set()


def test_several_overdue_runs_are_coalesced_without_replaying_each(scheduler_clock):
    engine, wrapper, ran, _ = scheduler_clock
    wrapper.scheduler_config["schedule"] = "hourly"
    job = add_cleanup(engine, wrapper)
    job.modify(next_run_time=datetime.now(timezone.utc) - timedelta(hours=3))
    engine.resume()
    assert ran.wait(5)
    engine.pause()
    assert wrapper._run_deleterr.call_count == 1
    assert job.coalesce is True
    assert job.max_instances == 1


def test_expired_cleanup_reports_failure_without_running(scheduler_clock):
    engine, wrapper, ran, notified = scheduler_clock
    job = add_cleanup(engine, wrapper)
    overdue = datetime.now(timezone.utc) - timedelta(hours=7)
    job.reschedule("date", run_date=overdue)
    engine.resume()
    assert notified.wait(5), "APScheduler's missed-job event was not surfaced"
    assert not ran.is_set()
    wrapper._notify_failure.assert_called_once()
    status, message = wrapper._record_last_run.call_args.args
    assert status == "failed"
    assert "6-hour" in message
    assert overdue.isoformat() in message


def test_overlapping_run_is_reported_and_unrelated_jobs_are_ignored(scheduler_clock):
    _, wrapper, ran, _ = scheduler_clock
    when = datetime.now(timezone.utc)
    wrapper._handle_missed_run(JobSubmissionEvent(
        EVENT_JOB_MAX_INSTANCES, "unrelated", "default", [when]
    ))
    wrapper._notify_failure.assert_not_called()
    wrapper._handle_missed_run(JobSubmissionEvent(
        EVENT_JOB_MAX_INSTANCES, "deleterr_cleanup", "default", [when]
    ))
    wrapper._notify_failure.assert_called_once()
    assert "another cleanup is still running" in wrapper._notify_failure.call_args.args[0]
    assert not ran.is_set()
