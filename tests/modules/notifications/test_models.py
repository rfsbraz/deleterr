# encoding: utf-8
"""Tests for notification data models."""

import pytest

from app.modules.notifications.models import DeletedItem, RunResult


@pytest.mark.unit
class TestDeletedItem:
    """Tests for DeletedItem dataclass."""

    def test_basic_creation(self):
        """Test basic DeletedItem creation."""
        item = DeletedItem(
            title="The Matrix",
            year=1999,
            media_type="movie",
            size_bytes=1024 * 1024 * 1024 * 8,  # 8 GB
            library_name="Movies",
            instance_name="Radarr",
        )

        assert item.title == "The Matrix"
        assert item.year == 1999
        assert item.media_type == "movie"
        assert item.size_bytes == 8589934592
        assert item.library_name == "Movies"
        assert item.instance_name == "Radarr"

    def test_format_title_with_year(self):
        """Test title formatting with year."""
        item = DeletedItem(
            title="The Matrix",
            year=1999,
            media_type="movie",
            size_bytes=0,
            library_name="Movies",
            instance_name="Radarr",
        )

        assert item.format_title() == "The Matrix (1999)"

    def test_format_title_without_year(self):
        """Test title formatting without year."""
        item = DeletedItem(
            title="Breaking Bad",
            year=None,
            media_type="show",
            size_bytes=0,
            library_name="TV Shows",
            instance_name="Sonarr",
        )

        assert item.format_title() == "Breaking Bad"

    def test_from_radarr(self):
        """Test creating DeletedItem from Radarr data."""
        radarr_data = {
            "title": "Inception",
            "year": 2010,
            "sizeOnDisk": 15000000000,
        }

        item = DeletedItem.from_radarr(radarr_data, "Movies", "Radarr")

        assert item.title == "Inception"
        assert item.year == 2010
        assert item.media_type == "movie"
        assert item.size_bytes == 15000000000
        assert item.library_name == "Movies"
        assert item.instance_name == "Radarr"

    def test_from_radarr_missing_fields(self):
        """Test creating DeletedItem from Radarr data with missing fields."""
        radarr_data = {}

        item = DeletedItem.from_radarr(radarr_data, "Movies", "Radarr")

        assert item.title == "Unknown"
        assert item.year is None
        assert item.size_bytes == 0

    def test_from_sonarr(self):
        """Test creating DeletedItem from Sonarr data."""
        sonarr_data = {
            "title": "Breaking Bad",
            "year": 2008,
            "statistics": {
                "sizeOnDisk": 50000000000,
            },
        }

        item = DeletedItem.from_sonarr(sonarr_data, "TV Shows", "Sonarr")

        assert item.title == "Breaking Bad"
        assert item.year == 2008
        assert item.media_type == "show"
        assert item.size_bytes == 50000000000
        assert item.library_name == "TV Shows"
        assert item.instance_name == "Sonarr"

    def test_from_sonarr_missing_statistics(self):
        """Test creating DeletedItem from Sonarr data without statistics."""
        sonarr_data = {
            "title": "The Office",
            "year": 2005,
        }

        item = DeletedItem.from_sonarr(sonarr_data, "TV Shows", "Sonarr")

        assert item.title == "The Office"
        assert item.size_bytes == 0


@pytest.mark.unit
class TestRunResult:
    """Tests for RunResult dataclass."""

    def test_default_creation(self):
        """Test default RunResult creation."""
        result = RunResult()

        assert result.is_dry_run is True
        assert result.deleted_items == []
        assert result.preview_items == []
        assert result.total_freed_bytes == 0
        assert result.total_preview_bytes == 0

    def test_with_dry_run_false(self):
        """Test RunResult with dry_run=False."""
        result = RunResult(is_dry_run=False)

        assert result.is_dry_run is False

    def test_add_deleted(self):
        """Test adding deleted items."""
        result = RunResult()
        item = DeletedItem(
            title="Movie",
            year=2020,
            media_type="movie",
            size_bytes=1000,
            library_name="Movies",
            instance_name="Radarr",
        )

        result.add_deleted(item)

        assert len(result.deleted_items) == 1
        assert result.deleted_items[0] == item

    def test_add_preview(self):
        """Test adding preview items."""
        result = RunResult()
        item = DeletedItem(
            title="Show",
            year=2020,
            media_type="show",
            size_bytes=2000,
            library_name="TV Shows",
            instance_name="Sonarr",
        )

        result.add_preview(item)

        assert len(result.preview_items) == 1
        assert result.preview_items[0] == item

    def test_total_freed_bytes(self):
        """Test total freed bytes calculation."""
        result = RunResult()
        result.add_deleted(DeletedItem("M1", 2020, "movie", 1000, "Movies", "Radarr"))
        result.add_deleted(DeletedItem("M2", 2021, "movie", 2000, "Movies", "Radarr"))
        result.add_deleted(DeletedItem("S1", 2020, "show", 500, "TV", "Sonarr"))

        assert result.total_freed_bytes == 3500

    def test_total_preview_bytes(self):
        """Test total preview bytes calculation."""
        result = RunResult()
        result.add_preview(DeletedItem("M1", 2020, "movie", 1000, "Movies", "Radarr"))
        result.add_preview(DeletedItem("S1", 2020, "show", 500, "TV", "Sonarr"))

        assert result.total_preview_bytes == 1500

    def test_deleted_movies(self):
        """Test filtering deleted movies."""
        result = RunResult()
        result.add_deleted(DeletedItem("M1", 2020, "movie", 1000, "Movies", "Radarr"))
        result.add_deleted(DeletedItem("S1", 2020, "show", 500, "TV", "Sonarr"))
        result.add_deleted(DeletedItem("M2", 2021, "movie", 2000, "Movies", "Radarr"))

        movies = result.deleted_movies

        assert len(movies) == 2
        assert all(m.media_type == "movie" for m in movies)

    def test_deleted_shows(self):
        """Test filtering deleted shows."""
        result = RunResult()
        result.add_deleted(DeletedItem("M1", 2020, "movie", 1000, "Movies", "Radarr"))
        result.add_deleted(DeletedItem("S1", 2020, "show", 500, "TV", "Sonarr"))
        result.add_deleted(DeletedItem("S2", 2021, "show", 700, "TV", "Sonarr"))

        shows = result.deleted_shows

        assert len(shows) == 2
        assert all(s.media_type == "show" for s in shows)

    def test_preview_movies(self):
        """Test filtering preview movies."""
        result = RunResult()
        result.add_preview(DeletedItem("M1", 2020, "movie", 1000, "Movies", "Radarr"))
        result.add_preview(DeletedItem("S1", 2020, "show", 500, "TV", "Sonarr"))

        movies = result.preview_movies

        assert len(movies) == 1
        assert movies[0].media_type == "movie"

    def test_preview_shows(self):
        """Test filtering preview shows."""
        result = RunResult()
        result.add_preview(DeletedItem("M1", 2020, "movie", 1000, "Movies", "Radarr"))
        result.add_preview(DeletedItem("S1", 2020, "show", 500, "TV", "Sonarr"))

        shows = result.preview_shows

        assert len(shows) == 1
        assert shows[0].media_type == "show"

    def test_has_content_empty(self):
        """Test has_content returns False for empty result."""
        result = RunResult()

        assert result.has_content() is False

    def test_has_content_with_deleted(self):
        """Test has_content returns True with deleted items."""
        result = RunResult()
        result.add_deleted(DeletedItem("M1", 2020, "movie", 1000, "Movies", "Radarr"))

        assert result.has_content() is True

    def test_has_content_with_preview(self):
        """Test has_content returns True with preview items."""
        result = RunResult()
        result.add_preview(DeletedItem("M1", 2020, "movie", 1000, "Movies", "Radarr"))

        assert result.has_content() is True
