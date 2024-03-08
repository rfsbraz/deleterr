import unittest
from unittest.mock import patch, MagicMock
from app.deleterr import main


class TestConfigPath(unittest.TestCase):
    @patch("app.deleterr.load_config")
    @patch("app.deleterr.Deleterr")
    @patch("app.deleterr.logger")
    def test_default_config_path(self, mock_logger, mock_deleterr, mock_load_config):
        # Arrange
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config

        # Act
        main()

        # Assert
        mock_load_config.assert_called_once_with("/config/settings.yaml")
        mock_config.validate.assert_called_once()
        mock_deleterr.assert_called_once_with(mock_config)
