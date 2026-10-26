import unittest
from unittest.mock import MagicMock, patch

from app import logger


class TestLogger(unittest.TestCase):
    @patch("app.logger.remove_old_handlers", autospec=True)
    @patch("app.logger.configure_logger", autospec=True)
    @patch("app.logger.setup_file_logger", autospec=True)
    @patch("app.logger.setup_console_logger", autospec=True)
    def test_init_logger(
        self,
        mock_setup_console_logger,
        mock_setup_file_logger,
        mock_configure_logger,
        mock_remove_old_handlers,
    ):
        logger.init_logger(console=True, log_dir="log_dir", verbose=True)

        mock_remove_old_handlers.assert_called_once()
        mock_configure_logger.assert_called_once_with(True)
        mock_setup_file_logger.assert_called_once_with("log_dir")
        mock_setup_console_logger.assert_called_once()


class TestSetupFileLoggerMissingDir(unittest.TestCase):
    def test_creates_missing_log_dir(self):
        import logging
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            log_dir = os.path.join(tmp, "config", "logs")
            before = list(logger.logger.handlers)
            try:
                logger.setup_file_logger(log_dir)
                self.assertTrue(os.path.isfile(os.path.join(log_dir, logger.FILENAME)))
            finally:
                for h in list(logger.logger.handlers):
                    if h not in before:
                        h.close()
                        logger.logger.removeHandler(h)


class TestRedactSecrets(unittest.TestCase):
    """Library failure messages go into notifications, so every secret must go (#344)."""

    def test_redacts_query_tokens_url_credentials_and_configured_values(self):
        text = (
            "GET http://radarr.test/api?apikey=radarr-secret failed, "
            "key radarr-secret rejected by http://admin:hunter2@proxy.test/path "
            "and https://discord.test/api/webhooks/1/hook-token"
        )
        redacted = logger.redact_secrets(text, ["radarr-secret", "https://discord.test/api/webhooks/1/hook-token"])

        for secret in ("radarr-secret", "hunter2", "hook-token"):
            self.assertNotIn(secret, redacted)
        self.assertIn("http://admin:[REDACTED]@proxy.test/path", redacted)
        self.assertIn("key [REDACTED] rejected", redacted)

    def test_ignores_empty_and_very_short_values(self):
        self.assertEqual(logger.redact_secrets("a b c", ["", None, "b"]), "a b c")


class TestConfiguredSecrets(unittest.TestCase):
    def test_collects_secret_values_from_nested_settings(self):
        settings = {
            "plex": {"url": "http://plex.test", "token": "plex-token"},
            "radarr": [{"name": "Radarr", "url": "http://r.test", "api_key": "radarr-secret"}],
            "trakt": {"client_id": "trakt-id", "client_secret": "trakt-secret"},
            "notifications": {
                "discord": {"webhook_url": "https://discord.test/api/webhooks/1/hook-token"},
                "telegram": {"bot_token": "1:bot-token", "chat_id": "42"},
                "email": {"smtp_password": "smtp-pass", "smtp_username": "user"},
                "webhook": {"url": "http://hook.test", "headers": {"Authorization": "Bearer abc123"}},
            },
            "libraries": [{"name": "Movies"}],
        }

        secrets = set(logger.configured_secrets(settings))

        self.assertTrue({
            "plex-token", "radarr-secret", "trakt-id", "trakt-secret",
            "https://discord.test/api/webhooks/1/hook-token", "1:bot-token", "smtp-pass", "Bearer abc123",
        } <= secrets)
        self.assertNotIn("Movies", secrets)
        self.assertNotIn("http://plex.test", secrets)


class TestRedactIsIdempotent(unittest.TestCase):
    def test_redacting_twice_leaves_one_marker(self):
        once = logger.redact("http://radarr.test/api?apikey=secret next")
        self.assertEqual(logger.redact(once), "http://radarr.test/api?apikey=[REDACTED] next")
