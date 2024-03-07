import unittest
from unittest.mock import patch, MagicMock
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
