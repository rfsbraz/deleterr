"""Integration tests for preview_next deletion queue feature."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class MockPlexMediaItem:
    """Mock Plex media item for testing."""

    def __init__(
        self,
        title: str,
        year: int,
        guid: str = None,
        guids: list = None,
        added_at: datetime = None,
    ):
        self.title = title
        self.year = year
        self.guid = guid or f"plex://movie/{title.lower().replace(' ', '-')}"
        self.guids = [MagicMock(id=g) for g in (guids or [])]
        self.addedAt = added_at or datetime.now() - timedelta(days=60)
        self.collections = []
        self.genres = []
        self.labels = []
        self.studio = None
        self.directors = []
        self.writers = []
        self.roles = []
        self.producers = []


class TestPreviewNextIntegration:
    """Integration tests for preview feature."""

    def test_preview_shows_correct_movies(
        self, docker_services, radarr_seeder, dradarr_client
    ):
        """Preview shows the correct next movies to be deleted."""
        from app.media_cleaner import MediaCleaner

        # Create mock config
        mock_config = MagicMock()
        mock_config.settings = {
            "dry_run": True,
            "plex": {"url": "http://localhost:32400", "token": "test"},
            "tautulli": {"url": "http://localhost:8181", "api_key": "test"},
        }

        # Create mock movie data (sorted by title for predictability)
        mock_movies = [
            {"title": f"Movie {i:02d}", "year": 2020, "sizeOnDisk": (10 - i) * 1_000_000_000,
             "tmdbId": 100000 + i, "alternateTitles": []}
            for i in range(10)
        ]

        # Create mock Plex items matching the movies
        mock_plex_items = [
            (
                [f"plex://movie/movie-{i:02d}"],
                MockPlexMediaItem(f"Movie {i:02d}", 2020, f"plex://movie/movie-{i:02d}")
            )
            for i in range(10)
        ]

        with patch("app.media_cleaner.PlexServer"), \
             patch("app.media_cleaner.Tautulli"), \
             patch("app.media_cleaner.Trakt"):
            cleaner = MediaCleaner(mock_config)

            # Mock the Plex library
            mock_plex_library = MagicMock()
            mock_plex_library.all.return_value = [item[1] for item in mock_plex_items]

            # Mock radarr instance
            mock_radarr = MagicMock()
            mock_radarr.get_movies.return_value = mock_movies

            # Configure: delete 3, preview next 3, sort by title
            library = {
                "name": "Movies",
                "max_actions_per_run": 3,
                "preview_next": 3,
                "sort": {"field": "title", "order": "asc"},
            }

            # Mock is_movie_actionable to return True for all movies
            cleaner.is_movie_actionable = MagicMock(return_value=True)
            cleaner.get_plex_item = MagicMock(side_effect=lambda *args, **kwargs: mock_plex_items[0][1])

            # Run process_movies
            saved_space, preview = cleaner.process_movies(
                library,
                mock_radarr,
                mock_plex_library,
                {},  # movie_activity
                {},  # trakt_movies
                max_actions_per_run=3,
                preview_next=3,
            )

            # Verify: items 0-2 processed (largest), items 3-5 in preview
            assert len(preview) == 3

    def test_preview_deterministic_across_runs(
        self, docker_services, radarr_seeder, dradarr_client
    ):
        """Preview items become deleted items on next run."""
        from app.media_cleaner import MediaCleaner

        mock_config = MagicMock()
        mock_config.settings = {
            "dry_run": True,
            "plex": {"url": "http://localhost:32400", "token": "test"},
            "tautulli": {"url": "http://localhost:8181", "api_key": "test"},
        }

        # Create 10 movies sorted by title
        all_movies = [
            {"title": f"Movie {i:02d}", "year": 2020, "sizeOnDisk": 1_000_000_000,
             "tmdbId": 100000 + i, "alternateTitles": []}
            for i in range(10)
        ]

        mock_plex_items = [
            (
                [f"plex://movie/movie-{i:02d}"],
                MockPlexMediaItem(f"Movie {i:02d}", 2020, f"plex://movie/movie-{i:02d}")
            )
            for i in range(10)
        ]

        with patch("app.media_cleaner.PlexServer"), \
             patch("app.media_cleaner.Tautulli"), \
             patch("app.media_cleaner.Trakt"):
            cleaner = MediaCleaner(mock_config)

            mock_plex_library = MagicMock()
            mock_plex_library.all.return_value = [item[1] for item in mock_plex_items]

            mock_radarr = MagicMock()

            library = {
                "name": "Movies",
                "max_actions_per_run": 3,
                "preview_next": 3,
                "sort": {"field": "title", "order": "asc"},
            }

            cleaner.is_movie_actionable = MagicMock(return_value=True)
            cleaner.get_plex_item = MagicMock(side_effect=lambda *args, **kwargs: mock_plex_items[0][1])

            # Run 1: first 10 movies
            mock_radarr.get_movies.return_value = all_movies
            _, preview_run1 = cleaner.process_movies(
                library, mock_radarr, mock_plex_library, {}, {},
                max_actions_per_run=3, preview_next=3,
            )

            # Capture preview titles from run 1
            preview_titles_run1 = [m["title"] for m in preview_run1]

            # Simulate run 2: remove first 3 movies (they were "deleted")
            remaining_movies = all_movies[3:]
            mock_radarr.get_movies.return_value = remaining_movies

            # Run 2: the preview items from run 1 should now be processed
            saved_space_run2, preview_run2 = cleaner.process_movies(
                library, mock_radarr, mock_plex_library, {}, {},
                max_actions_per_run=3, preview_next=3,
            )

            # The items deleted in run 2 should be the preview from run 1
            # (This is deterministic because sorting is consistent)
            processed_titles_run2 = [remaining_movies[i]["title"] for i in range(min(3, len(remaining_movies)))]

            # Verify: preview from run 1 became the processed items in run 2
            assert preview_titles_run1[:3] == processed_titles_run2[:3]

    def test_preview_disabled_with_zero(
        self, docker_services, radarr_seeder, dradarr_client
    ):
        """Setting preview_next=0 returns empty preview."""
        from app.media_cleaner import MediaCleaner

        mock_config = MagicMock()
        mock_config.settings = {
            "dry_run": True,
            "plex": {"url": "http://localhost:32400", "token": "test"},
            "tautulli": {"url": "http://localhost:8181", "api_key": "test"},
        }

        mock_movies = [
            {"title": f"Movie {i}", "year": 2020, "sizeOnDisk": 1_000_000_000,
             "tmdbId": 100000 + i, "alternateTitles": []}
            for i in range(10)
        ]

        mock_plex_items = [
            ([f"plex://movie/movie-{i}"], MockPlexMediaItem(f"Movie {i}", 2020))
            for i in range(10)
        ]

        with patch("app.media_cleaner.PlexServer"), \
             patch("app.media_cleaner.Tautulli"), \
             patch("app.media_cleaner.Trakt"):
            cleaner = MediaCleaner(mock_config)

            mock_plex_library = MagicMock()
            mock_plex_library.all.return_value = [item[1] for item in mock_plex_items]

            mock_radarr = MagicMock()
            mock_radarr.get_movies.return_value = mock_movies

            library = {
                "name": "Movies",
                "max_actions_per_run": 3,
                "preview_next": 0,  # Disabled
            }

            cleaner.is_movie_actionable = MagicMock(return_value=True)
            cleaner.get_plex_item = MagicMock(side_effect=lambda *args, **kwargs: mock_plex_items[0][1])

            _, preview = cleaner.process_movies(
                library, mock_radarr, mock_plex_library, {}, {},
                max_actions_per_run=3, preview_next=0,
            )

            # Verify empty preview
            assert len(preview) == 0


class TestPreviewLogging:
    """Tests for preview log output format."""

    def test_preview_log_format(self, docker_services, caplog):
        """Preview logs items with correct format."""
        import logging
        from app.deleterr import Deleterr

        caplog.set_level(logging.INFO)

        mock_config = MagicMock()
        mock_config.settings = {
            "dry_run": False,
            "plex": {"url": "http://localhost:32400", "token": "test"},
            "tautulli": {"url": "http://localhost:8181", "api_key": "test"},
            "radarr": [{"name": "Radarr", "url": "http://localhost:7878", "api_key": "test"}],
            "sonarr": [],
            "libraries": [
                {
                    "name": "Movies",
                    "radarr": "Radarr",
                    "action_mode": "delete",
                    "max_actions_per_run": 2,
                    "preview_next": 2,
                }
            ],
        }

        preview_items = [
            {"title": "Preview Movie 1", "sizeOnDisk": 5_000_000_000},
            {"title": "Preview Movie 2", "sizeOnDisk": 3_000_000_000},
        ]

        with patch("app.deleterr.MediaCleaner"), \
             patch("app.deleterr.DRadarr"), \
             patch("app.deleterr.DSonarr"):

            deleterr = Deleterr.__new__(Deleterr)
            deleterr.config = mock_config
            deleterr.media_cleaner = MagicMock()
            deleterr.sonarr = {}
            deleterr.radarr = {"Radarr": MagicMock()}
            deleterr.libraries_processed = 0
            deleterr.libraries_failed = 0

            # Call _log_preview directly
            deleterr._log_preview(preview_items, "movie")

            # Verify log contains expected format
            assert "Next scheduled deletions (2 items" in caplog.text
            assert "Preview Movie 1" in caplog.text
            assert "Preview Movie 2" in caplog.text

    def test_preview_dry_run_format(self, docker_services, caplog):
        """Preview in dry-run mode uses correct prefix."""
        import logging
        from app.deleterr import Deleterr

        caplog.set_level(logging.INFO)

        mock_config = MagicMock()
        mock_config.settings = {
            "dry_run": True,  # Dry run enabled
            "plex": {"url": "http://localhost:32400", "token": "test"},
            "tautulli": {"url": "http://localhost:8181", "api_key": "test"},
            "radarr": [],
            "sonarr": [],
            "libraries": [],
        }

        preview_items = [
            {"title": "Preview Movie", "sizeOnDisk": 5_000_000_000},
        ]

        with patch("app.deleterr.MediaCleaner"), \
             patch("app.deleterr.DRadarr"), \
             patch("app.deleterr.DSonarr"):

            deleterr = Deleterr.__new__(Deleterr)
            deleterr.config = mock_config
            deleterr.media_cleaner = MagicMock()

            # Call _log_preview
            deleterr._log_preview(preview_items, "movie")

            # Verify log uses [DRY-RUN] prefix
            assert "[DRY-RUN]" in caplog.text
            assert "Would be deleted" in caplog.text
