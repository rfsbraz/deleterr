"""Startup resilience (#329): long transient retry window, non-zero exit when it
finally gives up, permanent errors still stop for good, and API keys redacted
from every log line."""
import io
import logging
import socket
from unittest.mock import MagicMock, patch

import pytest
import requests

from app import logger as app_logger
from app.config import Config, is_transient_exception
from app.modules.seerr import Seerr


def _config():
    return Config({
        "tautulli": {"url": "http://tautulli:8181", "api_key": "key"},
        "libraries": [{"name": "Movies", "action_mode": "delete", "radarr": "test"}],
        "radarr": [{"name": "test", "url": "http://radarr:7878", "api_key": "key"}],
    })


class _Clock:
    """Fake monotonic clock advanced by time.sleep."""

    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class TestRetryWindow:
    def _run(self, config, outcomes):
        clock = _Clock()
        calls = {"n": 0}

        def fake_validate_config():
            i = calls["n"]
            calls["n"] += 1
            transient, ok = outcomes(i)
            config._last_failure_transient = transient
            return ok

        with patch.object(Config, "validate_config", side_effect=fake_validate_config), \
             patch("app.config.time.sleep", side_effect=clock.sleep), \
             patch("app.config.time.monotonic", side_effect=clock.monotonic):
            config.validate()
        return calls["n"], clock

    def test_keeps_retrying_past_the_old_75s_limit(self):
        # Dependencies come up after about 10 minutes (attempt 9).
        n, clock = self._run(_config(), lambda i: (True, i >= 8))
        assert n == 9
        assert clock.now > 75

    def test_backoff_is_capped_at_five_minutes(self):
        _, clock = self._run(_config(), lambda i: (True, i >= 9))
        assert max(clock.sleeps) == Config.VALIDATION_MAX_DELAY_SECONDS == 300

    def test_gives_up_with_nonzero_exit_after_window(self):
        config = _config()
        with pytest.raises(SystemExit) as exc, patch("app.config.hang_on_error") as hang:
            self._run(config, lambda i: (True, False))
        assert exc.value.code == 1
        hang.assert_not_called()

    def test_total_wait_stays_within_window(self):
        clock = _Clock()
        config = _config()

        def fake_validate_config():
            config._last_failure_transient = True
            return False

        with patch.object(Config, "validate_config", side_effect=fake_validate_config), \
             patch("app.config.time.sleep", side_effect=clock.sleep), \
             patch("app.config.time.monotonic", side_effect=clock.monotonic), \
             pytest.raises(SystemExit):
            config.validate()
        assert clock.now <= Config.VALIDATION_MAX_WAIT_SECONDS

    def test_permanent_error_still_hangs_without_retry(self):
        config = _config()
        with patch("app.config.hang_on_error", side_effect=SystemExit(1)) as hang, \
             pytest.raises(SystemExit):
            self._run(config, lambda i: (False, False))
        hang.assert_called_once()


class TestTransientClassification:
    def _http_error(self, status):
        response = requests.Response()
        response.status_code = status
        return requests.exceptions.HTTPError(f"{status} error", response=response)

    @pytest.mark.parametrize("err", [
        requests.exceptions.ConnectionError("refused"),
        requests.exceptions.ConnectTimeout("timeout"),
        requests.exceptions.ReadTimeout("timeout"),
        socket.gaierror(-2, "Name or service not known"),
        ConnectionRefusedError(111, "Connection refused"),
        TimeoutError("timed out"),
    ])
    def test_connection_errors_are_transient(self, err):
        assert is_transient_exception(err) is True

    @pytest.mark.parametrize("status", [502, 503, 504])
    def test_proxy_gateway_errors_are_transient(self, status):
        assert is_transient_exception(self._http_error(status)) is True

    @pytest.mark.parametrize("status", [400, 401, 403, 404])
    def test_client_errors_are_permanent(self, status):
        assert is_transient_exception(self._http_error(status)) is False

    def test_wrapped_cause_is_detected(self):
        try:
            try:
                raise ConnectionRefusedError(111, "Connection refused")
            except ConnectionRefusedError as inner:
                raise RuntimeError("tautulli call failed") from inner
        except RuntimeError as outer:
            assert is_transient_exception(outer) is True

    @pytest.mark.parametrize("err", [
        requests.exceptions.SSLError("certificate verify failed"),
        requests.exceptions.MissingSchema("Invalid URL 'tautulli:8181': No scheme supplied"),
        requests.exceptions.InvalidSchema("No connection adapters were found for 'ftp://x'"),
        ValueError("bad value"),
    ])
    def test_config_errors_are_permanent(self, err):
        assert is_transient_exception(err) is False

    def test_tautulli_dns_failure_marks_transient(self):
        config = _config()
        mock = MagicMock()
        mock.test_connection.side_effect = requests.exceptions.ConnectionError(
            "HTTPConnectionPool(host='tautulli', port=8181): Max retries exceeded with url: "
            "/api/v2?apikey=SECRET (Caused by NameResolutionError(\"Failed to resolve 'tautulli'\"))"
        )
        with patch("app.config.Tautulli", return_value=mock):
            assert config._validate_tautulli_watch_provider() is False
        assert config._last_failure_transient is True

    def test_tautulli_503_marks_transient(self):
        config = _config()
        mock = MagicMock()
        mock.test_connection.side_effect = self._http_error(503)
        with patch("app.config.Tautulli", return_value=mock):
            assert config._validate_tautulli_watch_provider() is False
        assert config._last_failure_transient is True

    def test_sonarr_503_marks_transient(self):
        # requests.Response is falsy for error statuses; the status must still be read.
        config = _config()
        response = requests.Response()
        response.status_code = 503
        with patch("app.config.requests.get", return_value=response):
            assert config.test_api_connection(
                {"name": "Sonarr", "url": "http://sonarr:8989", "api_key": "k"}
            ) is False
        assert config._last_failure_transient is True

    def test_sonarr_401_is_permanent(self):
        config = _config()
        response = requests.Response()
        response.status_code = 401
        with patch("app.config.requests.get", return_value=response):
            assert config.test_api_connection(
                {"name": "Sonarr", "url": "http://sonarr:8989", "api_key": "k"}
            ) is False
        assert config._last_failure_transient is False


class TestSeerrValidation:
    def _config(self):
        config = _config()
        config.settings["seerr"] = {"url": "http://seerr:5055", "api_key": "k"}
        return config

    def _response(self, status):
        response = requests.Response()
        response.status_code = status
        response._content = b"{}"
        return response

    def test_seerr_401_is_permanent(self):
        config = self._config()
        with patch("app.modules.seerr.requests.request", return_value=self._response(401)):
            assert config.validate_seerr() is False
        assert config._last_failure_transient is False

    def test_seerr_502_is_transient(self):
        config = self._config()
        with patch("app.modules.seerr.requests.request", return_value=self._response(502)):
            assert config.validate_seerr() is False
        assert config._last_failure_transient is True

    def test_seerr_refused_is_transient(self):
        config = self._config()
        with patch("app.modules.seerr.requests.request",
                   side_effect=requests.exceptions.ConnectionError("refused")):
            assert config.validate_seerr() is False
        assert config._last_failure_transient is True

    def test_seerr_records_last_error_kind(self):
        seerr = Seerr("http://seerr:5055", "k")
        with patch("app.modules.seerr.requests.request", return_value=self._response(503)):
            assert seerr.test_connection() is False
        assert seerr.last_error_transient is True


class TestRedaction:
    @pytest.mark.parametrize("text,leaked", [
        ("GET http://sonarr:8989/api?apiKey=abc123 failed", "abc123"),
        ("Max retries exceeded with url: /api/v2?apikey=Zz9&cmd=status", "Zz9"),
        ("url /x?foo=1&APIKEY=Up9", "Up9"),
        ("url /x?api_key=und3r", "und3r"),
        ("url /x?X-Plex-Token=plx9", "plx9"),
        ("'http://t/api/v2?apikey=q1'", "q1"),
    ])
    def test_redact_text(self, text, leaked):
        out = app_logger.redact(text)
        assert leaked not in out
        assert "[REDACTED]" in out

    def test_keeps_other_params(self):
        assert app_logger.redact("/api/v2?apikey=x&cmd=status") == "/api/v2?apikey=[REDACTED]&cmd=status"

    def _capture(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(app_logger.RedactingFormatter("%(name)s %(message)s"))
        return stream, handler

    def test_formatter_redacts_args_and_tracebacks(self):
        stream, handler = self._capture()
        log = logging.getLogger("deleterr.test-redact")
        log.addHandler(handler)
        log.propagate = False
        try:
            log.error("Cannot reach Sonarr: %s", "http://s/api?apiKey=ARGKEY")
            try:
                raise requests.exceptions.ConnectionError("url: /api/v2?apikey=EXCKEY")
            except requests.exceptions.ConnectionError:
                log.exception("failed")
        finally:
            log.removeHandler(handler)
        out = stream.getvalue()
        assert "ARGKEY" not in out and "EXCKEY" not in out
        assert out.count("[REDACTED]") >= 2

    def test_redacts_dict_form(self):
        out = app_logger.redact("params={'apikey': 'dictkey', 'cmd': 'status'}")
        assert "dictkey" not in out

    def test_init_logger_redacts_deleterr_logger(self, tmp_path, capsys):
        app_logger.init_logger(console=True, log_dir=str(tmp_path), verbose=True)
        try:
            app_logger.error("Cannot reach Tautulli at /api/v2?apikey=OURKEY")
        finally:
            app_logger.remove_old_handlers()
        captured = capsys.readouterr()
        out = captured.out + captured.err + (tmp_path / "deleterr.log").read_text()
        assert "OURKEY" not in out
        assert "[REDACTED]" in out

    def test_init_logger_redacts_third_party_loggers_on_root(self, tmp_path):
        # tautulli, urllib3, plexapi and arrapi log through the root logger handlers.
        root = logging.getLogger()
        extra = logging.StreamHandler(io.StringIO())
        extra.setFormatter(logging.Formatter("%(levelname)s:%(message)s"))
        root.addHandler(extra)
        try:
            app_logger.init_logger(console=False, log_dir=False)
            assert root.handlers
            for handler in root.handlers:
                assert isinstance(handler.formatter, app_logger.RedactingFormatter)
            logging.getLogger("tautulli").error("GET /api/v2?apikey=LIBKEY failed")
            out = extra.stream.getvalue()
            assert "LIBKEY" not in out and "[REDACTED]" in out
        finally:
            root.removeHandler(extra)
            app_logger.remove_old_handlers()
