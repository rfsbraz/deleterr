# encoding: utf-8
"""Unit tests for LeavingSoon schema models."""

import pytest
from pydantic import ValidationError

from app.schema import (
    LeavingSoonConfig,
    LeavingSoonCollectionConfig,
    LeavingSoonLabelConfig,
    LibraryConfig,
)


class TestLeavingSoonCollectionConfig:
    """Tests for LeavingSoonCollectionConfig model."""

    def test_default_values(self):
        """Test default values for collection config."""
        config = LeavingSoonCollectionConfig()
        assert config.enabled is False
        assert config.name == "Leaving Soon"
        assert config.clear_on_run is True

    def test_custom_values(self):
        """Test custom values for collection config."""
        config = LeavingSoonCollectionConfig(
            enabled=True,
            name="Expiring Content",
            clear_on_run=False,
        )
        assert config.enabled is True
        assert config.name == "Expiring Content"
        assert config.clear_on_run is False

    def test_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            "enabled": True,
            "name": "Custom Collection",
        }
        config = LeavingSoonCollectionConfig(**data)
        assert config.enabled is True
        assert config.name == "Custom Collection"
        assert config.clear_on_run is True  # default


class TestLeavingSoonLabelConfig:
    """Tests for LeavingSoonLabelConfig model."""

    def test_default_values(self):
        """Test default values for label config."""
        config = LeavingSoonLabelConfig()
        assert config.enabled is False
        assert config.name == "leaving-soon"
        assert config.clear_on_run is True

    def test_custom_values(self):
        """Test custom values for label config."""
        config = LeavingSoonLabelConfig(
            enabled=True,
            name="expiring",
            clear_on_run=False,
        )
        assert config.enabled is True
        assert config.name == "expiring"
        assert config.clear_on_run is False


class TestLeavingSoonConfig:
    """Tests for LeavingSoonConfig model."""

    def test_default_values(self):
        """Test default values for leaving soon config."""
        config = LeavingSoonConfig()
        assert config.enabled is False
        assert config.tagging_only is False
        assert config.collection is None
        assert config.labels is None

    def test_enabled_with_collection(self):
        """Test enabling with collection config."""
        config = LeavingSoonConfig(
            enabled=True,
            collection=LeavingSoonCollectionConfig(enabled=True),
        )
        assert config.enabled is True
        assert config.collection.enabled is True
        assert config.collection.name == "Leaving Soon"

    def test_enabled_with_labels(self):
        """Test enabling with labels config."""
        config = LeavingSoonConfig(
            enabled=True,
            labels=LeavingSoonLabelConfig(enabled=True, name="expiring"),
        )
        assert config.enabled is True
        assert config.labels.enabled is True
        assert config.labels.name == "expiring"

    def test_tagging_only_mode(self):
        """Test tagging_only mode configuration."""
        config = LeavingSoonConfig(
            enabled=True,
            tagging_only=True,
            collection=LeavingSoonCollectionConfig(enabled=True),
        )
        assert config.tagging_only is True

    def test_both_collection_and_labels(self):
        """Test configuring both collection and labels."""
        config = LeavingSoonConfig(
            enabled=True,
            collection=LeavingSoonCollectionConfig(enabled=True),
            labels=LeavingSoonLabelConfig(enabled=True),
        )
        assert config.collection.enabled is True
        assert config.labels.enabled is True

    def test_from_dict(self):
        """Test creating config from nested dictionary."""
        data = {
            "enabled": True,
            "tagging_only": True,
            "collection": {
                "enabled": True,
                "name": "Leaving Soon",
                "clear_on_run": True,
            },
            "labels": {
                "enabled": True,
                "name": "leaving-soon",
            },
        }
        config = LeavingSoonConfig(**data)
        assert config.enabled is True
        assert config.tagging_only is True
        assert config.collection.enabled is True
        assert config.labels.enabled is True


class TestLibraryConfigWithLeavingSoon:
    """Tests for LibraryConfig with leaving_soon field."""

    def test_library_without_leaving_soon(self):
        """Test library config without leaving_soon (backward compatible)."""
        config = LibraryConfig(
            name="Movies",
            radarr="Radarr",
            action_mode="delete",
        )
        assert config.leaving_soon is None

    def test_library_with_leaving_soon_disabled(self):
        """Test library config with leaving_soon disabled."""
        config = LibraryConfig(
            name="Movies",
            radarr="Radarr",
            action_mode="delete",
            leaving_soon=LeavingSoonConfig(enabled=False),
        )
        assert config.leaving_soon is not None
        assert config.leaving_soon.enabled is False

    def test_library_with_leaving_soon_enabled(self):
        """Test library config with leaving_soon enabled."""
        config = LibraryConfig(
            name="Movies",
            radarr="Radarr",
            action_mode="delete",
            leaving_soon=LeavingSoonConfig(
                enabled=True,
                collection=LeavingSoonCollectionConfig(enabled=True),
            ),
        )
        assert config.leaving_soon.enabled is True
        assert config.leaving_soon.collection.enabled is True

    def test_library_with_leaving_soon_from_dict(self):
        """Test library config with leaving_soon from dictionary."""
        data = {
            "name": "Movies",
            "radarr": "Radarr",
            "action_mode": "delete",
            "leaving_soon": {
                "enabled": True,
                "tagging_only": True,
                "collection": {
                    "enabled": True,
                    "name": "Leaving Soon",
                },
            },
        }
        config = LibraryConfig(**data)
        assert config.leaving_soon.enabled is True
        assert config.leaving_soon.tagging_only is True
        assert config.leaving_soon.collection.name == "Leaving Soon"

    def test_library_config_validation_still_works(self):
        """Test that library validation still works with leaving_soon."""
        # Should fail: neither radarr nor sonarr set
        with pytest.raises(ValidationError) as exc_info:
            LibraryConfig(
                name="Movies",
                action_mode="delete",
                leaving_soon=LeavingSoonConfig(enabled=True),
            )
        assert "Either radarr or sonarr must be set" in str(exc_info.value)

    def test_sonarr_library_with_leaving_soon(self):
        """Test Sonarr library config with leaving_soon."""
        config = LibraryConfig(
            name="TV Shows",
            sonarr="Sonarr",
            action_mode="delete",
            series_type="standard",
            leaving_soon=LeavingSoonConfig(
                enabled=True,
                labels=LeavingSoonLabelConfig(enabled=True),
            ),
        )
        assert config.sonarr == "Sonarr"
        assert config.leaving_soon.labels.enabled is True
