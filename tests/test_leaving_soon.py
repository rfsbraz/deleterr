# encoding: utf-8
"""Unit tests for leaving_soon feature in MediaCleaner and notifications."""

import pytest
from unittest.mock import MagicMock, patch, call

from app.media_cleaner import MediaCleaner
from app.modules.notifications.models import DeletedItem


@pytest.fixture
def standard_config():
    """Create a standard test configuration."""
    return MagicMock(
        settings={
            "dry_run": False,
            "sonarr": {"api_key": "test_api_key", "url": "http://localhost:8989"},
            "plex": {"url": "http://localhost:32400", "token": "test_token"},
            "tautulli": {"url": "http://localhost:8181", "api_key": "test_api_key"},
        }
    )


@pytest.fixture
def mock_media_server():
    """Create a mock media server."""
    return MagicMock()


@pytest.fixture(autouse=True)
def mock_plex_server():
    """Mock PlexServer to avoid real connections."""
    with patch("app.media_cleaner.PlexServer", return_value=MagicMock()):
        yield


@pytest.fixture
def media_cleaner(standard_config, mock_media_server):
    """Create MediaCleaner with mocked dependencies."""
    return MediaCleaner(standard_config, media_server=mock_media_server)


class TestProcessLeavingSoon:
    """Tests for process_leaving_soon method."""

    def test_skips_when_no_config(self, media_cleaner, mock_media_server):
        """Test that processing is skipped when leaving_soon config is missing."""
        library_config = {"name": "Movies"}
        plex_library = MagicMock()
        items_to_tag = [{"title": "Movie 1"}]

        media_cleaner.process_leaving_soon(library_config, plex_library, items_to_tag, "movie")

        mock_media_server.find_item.assert_not_called()

    def test_skips_when_no_media_server(self, standard_config):
        """Test that processing is skipped when media_server is not configured."""
        cleaner = MediaCleaner(standard_config, media_server=None)
        library_config = {
            "name": "Movies",
            "leaving_soon": {
                "collection": {"name": "Leaving Soon"},
            },
        }

        # Should not raise, just log warning
        cleaner.process_leaving_soon(library_config, MagicMock(), [], "movie")

    def test_finds_plex_items_for_movies(self, media_cleaner, mock_media_server):
        """Test that Plex items are found for movie candidates."""
        library_config = {
            "name": "Movies",
            "leaving_soon": {
                "collection": {"name": "Leaving Soon"},
            },
        }
        plex_library = MagicMock()
        mock_plex_item = MagicMock()
        mock_media_server.find_item.return_value = mock_plex_item
        mock_media_server.get_or_create_collection.return_value = MagicMock()

        items_to_tag = [
            {"title": "Movie 1", "year": 2020, "tmdbId": 550, "imdbId": "tt0137523"},
        ]

        media_cleaner.process_leaving_soon(library_config, plex_library, items_to_tag, "movie")

        mock_media_server.find_item.assert_called_once_with(
            plex_library,
            tmdb_id=550,
            tvdb_id=None,
            imdb_id="tt0137523",
            title="Movie 1",
            year=2020,
        )

    def test_finds_plex_items_for_shows(self, media_cleaner, mock_media_server):
        """Test that Plex items are found for show candidates."""
        library_config = {
            "name": "TV Shows",
            "leaving_soon": {
                "collection": {"name": "Leaving Soon"},
            },
        }
        plex_library = MagicMock()
        mock_plex_item = MagicMock()
        mock_media_server.find_item.return_value = mock_plex_item
        mock_media_server.get_or_create_collection.return_value = MagicMock()

        items_to_tag = [
            {"title": "Show 1", "year": 2018, "tvdbId": 81189, "imdbId": "tt1234567"},
        ]

        media_cleaner.process_leaving_soon(library_config, plex_library, items_to_tag, "show")

        mock_media_server.find_item.assert_called_once_with(
            plex_library,
            tmdb_id=None,
            tvdb_id=81189,
            imdb_id="tt1234567",
            title="Show 1",
            year=2018,
        )

    def test_updates_collection_when_configured(self, media_cleaner, mock_media_server):
        """Test that collection is updated when collection config is present."""
        library_config = {
            "name": "Movies",
            "leaving_soon": {
                "collection": {"name": "Leaving Soon"},
            },
        }
        plex_library = MagicMock()
        mock_plex_item = MagicMock()
        mock_collection = MagicMock()
        mock_media_server.find_item.return_value = mock_plex_item
        mock_media_server.get_or_create_collection.return_value = mock_collection

        items_to_tag = [{"title": "Movie 1", "year": 2020}]

        media_cleaner.process_leaving_soon(library_config, plex_library, items_to_tag, "movie")

        mock_media_server.get_or_create_collection.assert_called_once_with(
            plex_library, "Leaving Soon", items=[mock_plex_item]
        )
        mock_media_server.set_collection_items.assert_called_once_with(
            mock_collection, [mock_plex_item]
        )

    def test_updates_labels_when_configured(self, media_cleaner, mock_media_server):
        """Test that labels are updated when labels config is present."""
        library_config = {
            "name": "Movies",
            "leaving_soon": {
                "labels": {"name": "leaving-soon"},
            },
        }
        plex_library = MagicMock()
        mock_plex_item = MagicMock()
        mock_plex_item.ratingKey = "1001"
        mock_plex_item.labels = []
        mock_media_server.find_item.return_value = mock_plex_item
        mock_media_server.get_items_with_label.return_value = []

        items_to_tag = [{"title": "Movie 1", "year": 2020}]

        media_cleaner.process_leaving_soon(library_config, plex_library, items_to_tag, "movie")

        mock_media_server.add_label.assert_called_once_with(mock_plex_item, "leaving-soon")

    def test_clears_old_labels(self, media_cleaner, mock_media_server):
        """Test that old labels are removed when items are no longer in preview."""
        library_config = {
            "name": "Movies",
            "leaving_soon": {
                "labels": {"name": "leaving-soon"},
            },
        }
        plex_library = MagicMock()

        # Current item to tag
        mock_plex_item = MagicMock()
        mock_plex_item.ratingKey = "1001"
        mock_plex_item.labels = []

        # Old item that had the label but is no longer in the list
        old_labeled_item = MagicMock()
        old_labeled_item.ratingKey = "9999"

        mock_media_server.find_item.return_value = mock_plex_item
        mock_media_server.get_items_with_label.return_value = [old_labeled_item]

        items_to_tag = [{"title": "Movie 1", "year": 2020}]

        media_cleaner.process_leaving_soon(library_config, plex_library, items_to_tag, "movie")

        # Should remove label from old item
        mock_media_server.remove_label.assert_called_once_with(old_labeled_item, "leaving-soon")
        # Should add label to new item
        mock_media_server.add_label.assert_called_once_with(mock_plex_item, "leaving-soon")

    def test_handles_missing_plex_items(self, media_cleaner, mock_media_server):
        """Test that missing Plex items are handled gracefully."""
        library_config = {
            "name": "Movies",
            "leaving_soon": {
                "collection": {"name": "Leaving Soon"},
            },
        }
        plex_library = MagicMock()
        mock_media_server.find_item.return_value = None
        mock_media_server.get_or_create_collection.return_value = MagicMock()

        items_to_tag = [{"title": "Missing Movie", "year": 2020}]

        # Should not raise
        media_cleaner.process_leaving_soon(library_config, plex_library, items_to_tag, "movie")

        # Collection should be updated with empty list
        mock_media_server.set_collection_items.assert_called_once()

    def test_does_not_skip_label_if_already_present(self, media_cleaner, mock_media_server):
        """Test that labels are not re-added if already present."""
        library_config = {
            "name": "Movies",
            "leaving_soon": {
                "labels": {"name": "leaving-soon"},
            },
        }
        plex_library = MagicMock()

        mock_label = MagicMock()
        mock_label.tag = "leaving-soon"
        mock_plex_item = MagicMock()
        mock_plex_item.ratingKey = "1001"
        mock_plex_item.labels = [mock_label]

        mock_media_server.find_item.return_value = mock_plex_item
        mock_media_server.get_items_with_label.return_value = []

        items_to_tag = [{"title": "Movie 1", "year": 2020}]

        media_cleaner.process_leaving_soon(library_config, plex_library, items_to_tag, "movie")

        # Should not add label since it's already present
        mock_media_server.add_label.assert_not_called()

    def test_uses_default_collection_name(self, media_cleaner, mock_media_server):
        """Test that default collection name is used when not specified."""
        library_config = {
            "name": "Movies",
            "leaving_soon": {
                # Collection config present but name not specified - uses default
                "collection": {},
            },
        }
        plex_library = MagicMock()
        mock_media_server.find_item.return_value = None
        mock_media_server.get_or_create_collection.return_value = MagicMock()

        media_cleaner.process_leaving_soon(library_config, plex_library, [], "movie")

        mock_media_server.get_or_create_collection.assert_called_once_with(
            plex_library, "Leaving Soon", items=None
        )

    def test_uses_default_label_name(self, media_cleaner, mock_media_server):
        """Test that default label name is used when not specified."""
        library_config = {
            "name": "Movies",
            "leaving_soon": {
                # Labels config present but name not specified - uses default
                "labels": {},
            },
        }
        plex_library = MagicMock()
        mock_plex_item = MagicMock()
        mock_plex_item.ratingKey = "1001"
        mock_plex_item.labels = []
        mock_media_server.find_item.return_value = mock_plex_item
        mock_media_server.get_items_with_label.return_value = []

        items_to_tag = [{"title": "Movie 1", "year": 2020}]

        media_cleaner.process_leaving_soon(library_config, plex_library, items_to_tag, "movie")

        mock_media_server.add_label.assert_called_once_with(mock_plex_item, "leaving-soon")


class TestDeathRowPattern:
    """Tests for death row pattern in media cleaner."""

    @pytest.fixture
    def media_cleaner_with_server(self, standard_config, mock_media_server):
        """Create MediaCleaner with mocked media server."""
        return MediaCleaner(standard_config, media_server=mock_media_server)

    def test_process_multiple_items(self, media_cleaner_with_server, mock_media_server):
        """Test processing multiple preview items."""
        library_config = {
            "name": "Movies",
            "leaving_soon": {
                "collection": {"name": "Leaving Soon"},
            },
        }
        plex_library = MagicMock()

        # Create multiple mock items
        mock_items = []
        for i in range(3):
            item = MagicMock()
            item.ratingKey = str(1000 + i)
            mock_items.append(item)

        mock_media_server.find_item.side_effect = mock_items
        mock_collection = MagicMock()
        mock_media_server.get_or_create_collection.return_value = mock_collection

        items_to_tag = [
            {"title": f"Movie {i}", "year": 2020 + i, "tmdbId": 550 + i}
            for i in range(3)
        ]

        media_cleaner_with_server.process_leaving_soon(
            library_config, plex_library, items_to_tag, "movie"
        )

        # Should find all items
        assert mock_media_server.find_item.call_count == 3
        # Should update collection with all items
        mock_media_server.set_collection_items.assert_called_once_with(
            mock_collection, mock_items
        )

    def test_empty_items_clears_collection(self, media_cleaner_with_server, mock_media_server):
        """Test that empty items list clears the collection."""
        library_config = {
            "name": "Movies",
            "leaving_soon": {
                "collection": {"name": "Leaving Soon"},
            },
        }
        plex_library = MagicMock()
        mock_collection = MagicMock()
        mock_media_server.get_or_create_collection.return_value = mock_collection

        media_cleaner_with_server.process_leaving_soon(
            library_config, plex_library, [], "movie"
        )

        # Should update collection with empty list
        mock_media_server.set_collection_items.assert_called_once_with(
            mock_collection, []
        )

    def test_both_collection_and_labels(self, media_cleaner_with_server, mock_media_server):
        """Test that both collection and labels are updated when configured."""
        library_config = {
            "name": "Movies",
            "leaving_soon": {
                "collection": {"name": "Leaving Soon"},
                "labels": {"name": "leaving-soon"},
            },
        }
        plex_library = MagicMock()
        mock_plex_item = MagicMock()
        mock_plex_item.ratingKey = "1001"
        mock_plex_item.labels = []

        mock_media_server.find_item.return_value = mock_plex_item
        mock_media_server.get_or_create_collection.return_value = MagicMock()
        mock_media_server.get_items_with_label.return_value = []

        items_to_tag = [{"title": "Movie 1", "year": 2020}]

        media_cleaner_with_server.process_leaving_soon(
            library_config, plex_library, items_to_tag, "movie"
        )

        # Both should be called
        mock_media_server.get_or_create_collection.assert_called_once()
        mock_media_server.add_label.assert_called_once()


class TestMovieAndShowDeletion:
    """Tests for movie and show deletion (no tagging_only mode anymore)."""

    @pytest.fixture
    def media_cleaner_non_dry_run(self, mock_media_server):
        """Create MediaCleaner with dry_run=False."""
        config = MagicMock(
            settings={
                "dry_run": False,
                "action_delay": 0,
                "plex": {"url": "http://localhost:32400", "token": "test"},
                "tautulli": {"url": "http://localhost:8181", "api_key": "test"},
            }
        )
        return MediaCleaner(config, media_server=mock_media_server)

    def test_process_movie_deletes(self, media_cleaner_non_dry_run):
        """Test that movies are deleted when not in dry_run mode."""
        library = {
            "name": "Movies",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}},
        }
        radarr_instance = MagicMock()
        radarr_movie = {"id": 1, "title": "Test Movie", "sizeOnDisk": 1000000000}

        media_cleaner_non_dry_run.process_movie(
            library, radarr_instance, radarr_movie, 0, 10
        )

        # Should call delete
        radarr_instance.del_movie.assert_called_once()

    def test_process_movie_without_leaving_soon_deletes(self, media_cleaner_non_dry_run):
        """Test that movies are deleted when leaving_soon is not configured."""
        library = {"name": "Movies"}
        radarr_instance = MagicMock()
        radarr_movie = {"id": 1, "title": "Test Movie", "sizeOnDisk": 1000000000}

        media_cleaner_non_dry_run.process_movie(
            library, radarr_instance, radarr_movie, 0, 10
        )

        # Should call delete
        radarr_instance.del_movie.assert_called_once()

    def test_process_movie_dry_run_does_not_delete(self, mock_media_server):
        """Test that movies are not deleted in dry_run mode."""
        config = MagicMock(
            settings={
                "dry_run": True,
                "action_delay": 0,
                "plex": {"url": "http://localhost:32400", "token": "test"},
                "tautulli": {"url": "http://localhost:8181", "api_key": "test"},
            }
        )
        cleaner = MediaCleaner(config, media_server=mock_media_server)

        library = {"name": "Movies"}
        radarr_instance = MagicMock()
        radarr_movie = {"id": 1, "title": "Test Movie", "sizeOnDisk": 1000000000}

        cleaner.process_movie(library, radarr_instance, radarr_movie, 0, 10)

        # Should NOT call delete
        radarr_instance.del_movie.assert_not_called()


class TestDeathRowIntersectionLogic:
    """Tests for the intersection logic in Deleterr death row processing.

    The critical behavior is:
    - Items in death row that STILL match deletion rules → DELETE
    - Items in death row that NO LONGER match rules (user watched them) → DON'T DELETE
    - Items NOT in death row but match rules → DON'T DELETE (add to preview for next run)
    """

    @pytest.fixture
    def mock_config(self):
        """Create a mock config for Deleterr."""
        return MagicMock(
            settings={
                "dry_run": False,
                "plex": {"url": "http://localhost:32400", "token": "test_token"},
                "radarr": [{"name": "radarr", "url": "http://localhost:7878", "api_key": "test"}],
                "sonarr": [{"name": "sonarr", "url": "http://localhost:8989", "api_key": "test"}],
                "libraries": [],
                "ssl_verify": False,
            }
        )

    @pytest.fixture
    def deleterr_instance(self, mock_config):
        """Create a Deleterr instance with mocked dependencies."""
        with patch("app.deleterr.PlexMediaServer") as mock_plex_class, \
             patch("app.deleterr.MediaCleaner") as mock_cleaner_class, \
             patch("app.deleterr.NotificationManager"), \
             patch("app.deleterr.DRadarr"), \
             patch("app.deleterr.DSonarr"), \
             patch.object(mock_config, "settings", mock_config.settings):

            # Prevent __init__ from running process_radarr/process_sonarr
            from app.deleterr import Deleterr

            # Create instance without running __init__ logic
            instance = object.__new__(Deleterr)
            instance.config = mock_config
            instance.media_server = MagicMock()
            instance.media_cleaner = MagicMock()
            instance.notifications = MagicMock()
            instance.run_result = MagicMock()
            instance.radarr = {}
            instance.sonarr = {}
            instance.libraries_processed = 0
            instance.libraries_failed = 0

            return instance

    def test_movie_in_death_row_and_matches_rules_is_deleted(self, deleterr_instance):
        """Test that a movie in death row that still matches rules gets deleted."""
        library = {
            "name": "Movies",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}},
            "preview_next": 5,
        }

        # Movie A is in death row AND matches current rules
        plex_item_a = MagicMock()
        plex_item_a.ratingKey = 1001

        radarr_movie_a = {
            "id": 101,
            "title": "Movie A",
            "tmdbId": 550,
            "imdbId": "tt0137523",
            "year": 2020,
            "sizeOnDisk": 1000000000,
        }

        radarr_instance = MagicMock()
        plex_library = MagicMock()

        # Setup mocks
        deleterr_instance.media_server.get_library.return_value = plex_library
        deleterr_instance.media_server.get_collection.return_value = MagicMock()

        # Death row contains Movie A
        deleterr_instance._get_death_row_items = MagicMock(return_value=[plex_item_a])

        # Current candidates also contains Movie A (still matches rules)
        deleterr_instance._get_deletion_candidates = MagicMock(
            return_value=[radarr_movie_a]
        )

        # find_item returns plex_item_a for Movie A
        deleterr_instance.media_server.find_item.return_value = plex_item_a

        with patch("app.media_cleaner.library_meets_disk_space_threshold", return_value=True):
            saved_space, deleted, preview = deleterr_instance._process_death_row(
                library, radarr_instance, "movie"
            )

        # Movie A should be deleted (in death row AND matches rules)
        assert len(deleted) == 1
        assert deleted[0]["title"] == "Movie A"
        radarr_instance.del_movie.assert_called_once()

    def test_movie_in_death_row_but_no_longer_matches_is_not_deleted(self, deleterr_instance):
        """Test that a movie in death row that no longer matches rules is NOT deleted."""
        library = {
            "name": "Movies",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}},
            "preview_next": 5,
        }

        # Movie B is in death row but user watched it (no longer matches)
        plex_item_b = MagicMock()
        plex_item_b.ratingKey = 1002

        radarr_instance = MagicMock()
        plex_library = MagicMock()

        # Setup mocks
        deleterr_instance.media_server.get_library.return_value = plex_library
        deleterr_instance.media_server.get_collection.return_value = MagicMock()

        # Death row contains Movie B
        deleterr_instance._get_death_row_items = MagicMock(return_value=[plex_item_b])

        # Current candidates is EMPTY (Movie B was watched, no longer matches)
        deleterr_instance._get_deletion_candidates = MagicMock(return_value=[])

        with patch("app.media_cleaner.library_meets_disk_space_threshold", return_value=True):
            saved_space, deleted, preview = deleterr_instance._process_death_row(
                library, radarr_instance, "movie"
            )

        # Movie B should NOT be deleted (in death row but doesn't match rules anymore)
        assert len(deleted) == 0
        radarr_instance.del_movie.assert_not_called()

    def test_movie_matches_rules_but_not_in_death_row_goes_to_preview(self, deleterr_instance):
        """Test that a movie matching rules but not in death row goes to preview, not deleted."""
        library = {
            "name": "Movies",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}},
            "preview_next": 5,
        }

        # Movie C matches rules but was never in death row (new candidate)
        plex_item_c = MagicMock()
        plex_item_c.ratingKey = 1003

        radarr_movie_c = {
            "id": 103,
            "title": "Movie C",
            "tmdbId": 552,
            "imdbId": "tt0137525",
            "year": 2021,
            "sizeOnDisk": 2000000000,
        }

        radarr_instance = MagicMock()
        plex_library = MagicMock()

        # Setup mocks
        deleterr_instance.media_server.get_library.return_value = plex_library
        deleterr_instance.media_server.get_collection.return_value = MagicMock()

        # Death row is EMPTY (first run or no items tagged)
        deleterr_instance._get_death_row_items = MagicMock(return_value=[])

        # Current candidates contains Movie C
        deleterr_instance._get_deletion_candidates = MagicMock(
            return_value=[radarr_movie_c]
        )

        deleterr_instance.media_server.find_item.return_value = plex_item_c

        with patch("app.media_cleaner.library_meets_disk_space_threshold", return_value=True):
            saved_space, deleted, preview = deleterr_instance._process_death_row(
                library, radarr_instance, "movie"
            )

        # Movie C should NOT be deleted (not in death row)
        assert len(deleted) == 0
        radarr_instance.del_movie.assert_not_called()

        # Movie C should be in preview for next run
        assert len(preview) == 1
        assert preview[0]["title"] == "Movie C"

    def test_mixed_scenario_only_intersection_deleted(self, deleterr_instance):
        """Test mixed scenario: some items match, some don't, some are new."""
        library = {
            "name": "Movies",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}},
            "preview_next": 10,
        }

        # Movie A: in death row AND matches rules → DELETE
        plex_item_a = MagicMock()
        plex_item_a.ratingKey = 1001
        radarr_movie_a = {"id": 101, "title": "Movie A", "tmdbId": 550, "sizeOnDisk": 1000}

        # Movie B: in death row but was watched → DON'T DELETE
        plex_item_b = MagicMock()
        plex_item_b.ratingKey = 1002

        # Movie C: matches rules but new (not in death row) → DON'T DELETE, goes to preview
        plex_item_c = MagicMock()
        plex_item_c.ratingKey = 1003
        radarr_movie_c = {"id": 103, "title": "Movie C", "tmdbId": 552, "sizeOnDisk": 2000}

        radarr_instance = MagicMock()
        plex_library = MagicMock()

        deleterr_instance.media_server.get_library.return_value = plex_library
        deleterr_instance.media_server.get_collection.return_value = MagicMock()

        # Death row contains A and B
        deleterr_instance._get_death_row_items = MagicMock(return_value=[plex_item_a, plex_item_b])

        # Current candidates contains A and C (B was watched, no longer matches)
        deleterr_instance._get_deletion_candidates = MagicMock(
            return_value=[radarr_movie_a, radarr_movie_c]
        )

        # find_item maps movies to plex items
        def find_item_side_effect(lib, tmdb_id=None, imdb_id=None, title=None, year=None):
            if tmdb_id == 550:
                return plex_item_a
            elif tmdb_id == 552:
                return plex_item_c
            return None

        deleterr_instance.media_server.find_item.side_effect = find_item_side_effect

        with patch("app.media_cleaner.library_meets_disk_space_threshold", return_value=True):
            saved_space, deleted, preview = deleterr_instance._process_death_row(
                library, radarr_instance, "movie"
            )

        # Only Movie A should be deleted (intersection of death row AND current candidates)
        assert len(deleted) == 1
        assert deleted[0]["title"] == "Movie A"

        # Movie C should be in preview (matches rules but wasn't in death row)
        assert len(preview) == 1
        assert preview[0]["title"] == "Movie C"

        # Only one deletion call
        radarr_instance.del_movie.assert_called_once()

    def test_show_intersection_logic_works_same_as_movies(self, deleterr_instance):
        """Test that show intersection logic works the same as movies."""
        library = {
            "name": "TV Shows",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}},
            "preview_next": 5,
        }

        # Show A: in death row AND matches rules → DELETE
        plex_item_a = MagicMock()
        plex_item_a.ratingKey = 2001
        sonarr_show_a = {
            "id": 201,
            "title": "Show A",
            "tvdbId": 81189,
            "imdbId": "tt1234567",
            "statistics": {"sizeOnDisk": 5000000000, "episodeFileCount": 10},
        }

        # Show B: in death row but was watched → DON'T DELETE
        plex_item_b = MagicMock()
        plex_item_b.ratingKey = 2002

        sonarr_instance = MagicMock()
        plex_library = MagicMock()
        unfiltered_all_show_data = []

        deleterr_instance.media_server.get_library.return_value = plex_library
        deleterr_instance.media_server.get_collection.return_value = MagicMock()

        # Death row contains A and B
        deleterr_instance._get_death_row_items = MagicMock(return_value=[plex_item_a, plex_item_b])

        # Current candidates contains only A (B was watched)
        deleterr_instance._get_deletion_candidates = MagicMock(
            return_value=[sonarr_show_a]
        )

        # find_item returns plex_item_a for Show A
        deleterr_instance.media_server.find_item.return_value = plex_item_a

        with patch("app.media_cleaner.library_meets_disk_space_threshold", return_value=True):
            saved_space, deleted, preview = deleterr_instance._process_death_row(
                library, sonarr_instance, "show", unfiltered_all_show_data
            )

        # Only Show A should be deleted
        assert len(deleted) == 1
        assert deleted[0]["title"] == "Show A"

        # Show B is NOT deleted (no longer matches rules)
        deleterr_instance.media_cleaner.delete_series.assert_called_once()


class TestLeavingSoonNotifications:
    """Tests for leaving_soon notification functionality."""

    @pytest.fixture
    def mock_notification_manager(self):
        """Create a mock notification manager."""
        manager = MagicMock()
        manager.is_leaving_soon_enabled.return_value = True
        return manager

    @pytest.fixture
    def mock_config(self):
        """Create a mock config."""
        return MagicMock(
            settings={
                "dry_run": False,
                "plex": {"url": "http://localhost:32400", "token": "test_token"},
                "overseerr": {"url": "http://localhost:5055", "api_key": "test_key"},
                "radarr": [{"name": "Radarr", "url": "http://localhost:7878", "api_key": "test"}],
                "sonarr": [],
                "libraries": [],
                "ssl_verify": False,
            }
        )

    @pytest.fixture
    def deleterr_with_notifications(self, mock_config, mock_notification_manager):
        """Create a Deleterr instance with mocked notification manager."""
        with patch("app.deleterr.PlexMediaServer") as mock_plex_class, \
             patch("app.deleterr.MediaCleaner") as mock_cleaner_class, \
             patch("app.deleterr.NotificationManager") as mock_nm_class, \
             patch("app.deleterr.DRadarr"), \
             patch("app.deleterr.DSonarr"):

            mock_nm_class.return_value = mock_notification_manager

            from app.deleterr import Deleterr

            # Create instance without running __init__ logic
            instance = object.__new__(Deleterr)
            instance.config = mock_config
            instance.media_server = MagicMock()
            instance.media_cleaner = MagicMock()
            instance.notifications = mock_notification_manager
            instance.run_result = MagicMock()
            instance.radarr = {}
            instance.sonarr = {}
            instance.libraries_processed = 0
            instance.libraries_failed = 0

            return instance

    def test_send_leaving_soon_notification_called_when_enabled(
        self, deleterr_with_notifications, mock_notification_manager
    ):
        """Test that leaving_soon notification is sent when enabled and items exist."""
        library = {
            "name": "Movies",
            "radarr": "Radarr",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}},
        }
        preview = [
            {"title": "Movie 1", "year": 2020, "tmdbId": 550, "sizeOnDisk": 1000000000},
        ]

        # Mock get_library to succeed
        deleterr_with_notifications.media_server.get_library.return_value = MagicMock()

        deleterr_with_notifications._process_library_leaving_soon(library, preview, "movie")

        # Should have called send_leaving_soon
        mock_notification_manager.send_leaving_soon.assert_called_once()

        # Verify the call arguments
        call_args = mock_notification_manager.send_leaving_soon.call_args
        items = call_args[0][0]  # First positional argument
        assert len(items) == 1
        assert items[0].title == "Movie 1"

        # Verify context was passed
        kwargs = call_args[1]
        assert kwargs["plex_url"] == "http://localhost:32400"
        assert kwargs["overseerr_url"] == "http://localhost:5055"

    def test_send_leaving_soon_notification_not_called_when_disabled(
        self, deleterr_with_notifications, mock_notification_manager
    ):
        """Test that leaving_soon notification is not sent when disabled."""
        mock_notification_manager.is_leaving_soon_enabled.return_value = False

        library = {
            "name": "Movies",
            "radarr": "Radarr",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}},
        }
        preview = [
            {"title": "Movie 1", "year": 2020, "tmdbId": 550, "sizeOnDisk": 1000000000},
        ]

        deleterr_with_notifications.media_server.get_library.return_value = MagicMock()

        deleterr_with_notifications._process_library_leaving_soon(library, preview, "movie")

        # Should NOT have called send_leaving_soon
        mock_notification_manager.send_leaving_soon.assert_not_called()

    def test_send_leaving_soon_notification_not_called_when_no_preview(
        self, deleterr_with_notifications, mock_notification_manager
    ):
        """Test that leaving_soon notification is not sent when preview is empty."""
        library = {
            "name": "Movies",
            "radarr": "Radarr",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}},
        }
        preview = []

        deleterr_with_notifications.media_server.get_library.return_value = MagicMock()

        deleterr_with_notifications._process_library_leaving_soon(library, preview, "movie")

        # Should NOT have called send_leaving_soon (no items)
        mock_notification_manager.send_leaving_soon.assert_not_called()

    def test_send_leaving_soon_notification_skipped_in_dry_run(
        self, deleterr_with_notifications, mock_notification_manager
    ):
        """Test that leaving_soon notification is skipped in dry-run mode."""
        deleterr_with_notifications.config.settings["dry_run"] = True

        library = {
            "name": "Movies",
            "radarr": "Radarr",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}},
        }
        preview = [
            {"title": "Movie 1", "year": 2020, "tmdbId": 550, "sizeOnDisk": 1000000000},
        ]

        deleterr_with_notifications._process_library_leaving_soon(library, preview, "movie")

        # Should NOT have called send_leaving_soon (dry-run mode)
        mock_notification_manager.send_leaving_soon.assert_not_called()

    def test_send_leaving_soon_notification_for_shows(
        self, deleterr_with_notifications, mock_notification_manager
    ):
        """Test that leaving_soon notification works for TV shows."""
        library = {
            "name": "TV Shows",
            "sonarr": "Sonarr",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}},
        }
        preview = [
            {
                "title": "Show 1",
                "year": 2019,
                "tvdbId": 81189,
                "statistics": {"sizeOnDisk": 5000000000},
            },
        ]

        deleterr_with_notifications.media_server.get_library.return_value = MagicMock()

        deleterr_with_notifications._process_library_leaving_soon(library, preview, "show")

        # Should have called send_leaving_soon
        mock_notification_manager.send_leaving_soon.assert_called_once()

        # Verify it was created as a show
        call_args = mock_notification_manager.send_leaving_soon.call_args
        items = call_args[0][0]
        assert len(items) == 1
        assert items[0].title == "Show 1"
        assert items[0].media_type == "show"


class TestLeavingSoonPreviewDoesNotDuplicate:
    """Tests ensuring leaving_soon preview items don't appear in 'would be deleted' list.

    The critical behavior: when leaving_soon is enabled, items to be tagged should
    ONLY appear in the "would be added to leaving_soon" log, NOT in the
    "Would be deleted" log. These are mutually exclusive states.
    """

    @pytest.fixture
    def mock_config(self):
        """Create a mock config for Deleterr."""
        return MagicMock(
            settings={
                "dry_run": True,  # Dry run to see logs
                "plex": {"url": "http://localhost:32400", "token": "test_token"},
                "radarr": [{"name": "Radarr", "url": "http://localhost:7878", "api_key": "test"}],
                "sonarr": [{"name": "Sonarr", "url": "http://localhost:8989", "api_key": "test"}],
                "libraries": [],
                "ssl_verify": False,
            }
        )

    @pytest.fixture
    def deleterr_instance(self, mock_config):
        """Create a Deleterr instance with mocked dependencies."""
        with patch("app.deleterr.PlexMediaServer"), \
             patch("app.deleterr.MediaCleaner"), \
             patch("app.deleterr.NotificationManager"), \
             patch("app.deleterr.DRadarr"), \
             patch("app.deleterr.DSonarr"):

            from app.deleterr import Deleterr

            # Create instance without running __init__ logic
            instance = object.__new__(Deleterr)
            instance.config = mock_config
            instance.media_server = MagicMock()
            instance.media_cleaner = MagicMock()
            instance.notifications = MagicMock()
            instance.run_result = MagicMock()
            instance.radarr = {"Radarr": MagicMock()}
            instance.sonarr = {"Sonarr": MagicMock()}
            instance.libraries_processed = 0
            instance.libraries_failed = 0

            return instance

    def test_leaving_soon_preview_not_in_deletion_preview_movies(self, mock_config, deleterr_instance):
        """Test that movie items being tagged for leaving_soon don't appear in deletion preview.

        This test verifies the fix for the bug where items showed up in BOTH:
        - "[DRY-RUN] 2 items would be added to leaving_soon collection/labels"
        - "[DRY-RUN] Would be deleted (2 items, ...)"

        With leaving_soon enabled, items should ONLY appear in the first list.
        """
        # Configure a library with leaving_soon enabled
        library_with_leaving_soon = {
            "name": "Movies",
            "radarr": "Radarr",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}},
            "preview_next": 5,
        }
        mock_config.settings["libraries"] = [library_with_leaving_soon]

        # Preview items that would be tagged for leaving_soon
        preview_items = [
            {"id": 1, "title": "Movie A", "year": 2020, "tmdbId": 550, "sizeOnDisk": 1000000000},
            {"id": 2, "title": "Movie B", "year": 2021, "tmdbId": 551, "sizeOnDisk": 2000000000},
        ]

        # Mock _process_death_row to return preview items
        deleterr_instance._process_death_row = MagicMock(
            return_value=(0, [], preview_items)  # saved_space=0, deleted=[], preview=items
        )

        # Track what _log_preview receives
        log_preview_calls = []
        original_log_preview = deleterr_instance._log_preview

        def tracking_log_preview(items, media_type):
            log_preview_calls.append(items)

        deleterr_instance._log_preview = tracking_log_preview

        # Mock _process_library_leaving_soon to do nothing
        deleterr_instance._process_library_leaving_soon = MagicMock()

        # Run process_radarr
        deleterr_instance.process_radarr()

        # _log_preview should be called with an EMPTY list for leaving_soon libraries
        # because preview items are for tagging, not for "would be deleted"
        assert len(log_preview_calls) == 1, "Expected _log_preview to be called once"
        assert log_preview_calls[0] == [], \
            f"Expected empty preview list for leaving_soon library, got {len(log_preview_calls[0])} items: " \
            f"{[i.get('title') for i in log_preview_calls[0]]}"

    def test_leaving_soon_preview_not_in_deletion_preview_shows(self, mock_config, deleterr_instance):
        """Test that show items being tagged for leaving_soon don't appear in deletion preview."""
        # Configure a library with leaving_soon enabled
        library_with_leaving_soon = {
            "name": "TV Shows",
            "sonarr": "Sonarr",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}},
            "preview_next": 5,
        }
        mock_config.settings["libraries"] = [library_with_leaving_soon]

        # Preview items that would be tagged for leaving_soon
        preview_items = [
            {"id": 1, "title": "Show A", "year": 2020, "tvdbId": 81189,
             "statistics": {"sizeOnDisk": 5000000000, "episodeFileCount": 10}},
        ]

        # Mock _process_death_row to return preview items
        deleterr_instance._process_death_row = MagicMock(
            return_value=(0, [], preview_items)  # saved_space=0, deleted=[], preview=items
        )

        # Track what _log_preview receives
        log_preview_calls = []

        def tracking_log_preview(items, media_type):
            log_preview_calls.append(items)

        deleterr_instance._log_preview = tracking_log_preview

        # Mock _process_library_leaving_soon to do nothing
        deleterr_instance._process_library_leaving_soon = MagicMock()

        # Mock get_series to return empty (we're testing the logic flow, not series processing)
        deleterr_instance.sonarr["Sonarr"].get_series.return_value = []

        # Run process_sonarr
        deleterr_instance.process_sonarr()

        # _log_preview should be called with an EMPTY list for leaving_soon libraries
        assert len(log_preview_calls) == 1, "Expected _log_preview to be called once"
        assert log_preview_calls[0] == [], \
            f"Expected empty preview list for leaving_soon library, got {len(log_preview_calls[0])} items"

    def test_normal_library_still_shows_deletion_preview(self, mock_config, deleterr_instance):
        """Test that libraries WITHOUT leaving_soon still show deletion preview correctly."""
        # Configure a library WITHOUT leaving_soon
        library_without_leaving_soon = {
            "name": "Movies",
            "radarr": "Radarr",
            # No leaving_soon config
        }
        mock_config.settings["libraries"] = [library_without_leaving_soon]

        # Preview items that would be deleted (no leaving_soon = immediate deletion candidates)
        preview_items = [
            {"id": 1, "title": "Movie A", "year": 2020, "tmdbId": 550, "sizeOnDisk": 1000000000},
        ]

        # Mock process_library_movies to return preview items
        deleterr_instance.media_cleaner.process_library_movies = MagicMock(
            return_value=(0, [], preview_items)  # saved_space=0, deleted=[], preview=items
        )

        # Track what _log_preview receives
        log_preview_calls = []

        def tracking_log_preview(items, media_type):
            log_preview_calls.append(items)

        deleterr_instance._log_preview = tracking_log_preview

        # Run process_radarr
        deleterr_instance.process_radarr()

        # _log_preview should be called WITH the preview items (normal library behavior)
        assert len(log_preview_calls) == 1, "Expected _log_preview to be called once"
        assert len(log_preview_calls[0]) == 1, \
            f"Expected preview list with 1 item for normal library, got {len(log_preview_calls[0])}"
        assert log_preview_calls[0][0]["title"] == "Movie A"

    def test_mixed_libraries_separate_preview_correctly(self, mock_config, deleterr_instance):
        """Test that mixed libraries (some with leaving_soon, some without) preview correctly."""
        # One library with leaving_soon, one without
        mock_config.settings["libraries"] = [
            {
                "name": "Movies",
                "radarr": "Radarr",
                "leaving_soon": {"collection": {"name": "Leaving Soon"}},
            },
            {
                "name": "Kids Movies",
                "radarr": "Radarr",
                # No leaving_soon - normal deletion flow
            },
        ]

        # leaving_soon library returns items for tagging
        leaving_soon_preview = [
            {"id": 1, "title": "Movie for Tagging", "sizeOnDisk": 1000},
        ]

        # Normal library returns items for deletion
        normal_preview = [
            {"id": 2, "title": "Movie for Deletion", "sizeOnDisk": 2000},
        ]

        call_count = [0]

        def mock_death_row(*args):
            return (0, [], leaving_soon_preview)

        def mock_normal(*args):
            return (0, [], normal_preview)

        deleterr_instance._process_death_row = mock_death_row
        deleterr_instance.media_cleaner.process_library_movies = mock_normal
        deleterr_instance._process_library_leaving_soon = MagicMock()

        # Track what _log_preview receives
        log_preview_calls = []

        def tracking_log_preview(items, media_type):
            log_preview_calls.append([i.get("title") for i in items])

        deleterr_instance._log_preview = tracking_log_preview

        # Run process_radarr
        deleterr_instance.process_radarr()

        # _log_preview should only contain items from the normal library
        assert len(log_preview_calls) == 1
        assert "Movie for Deletion" in log_preview_calls[0], \
            f"Expected normal library preview, got: {log_preview_calls[0]}"
        assert "Movie for Tagging" not in log_preview_calls[0], \
            f"leaving_soon preview should not appear in deletion preview: {log_preview_calls[0]}"


class TestThresholdNotMetClearsDeathRow:
    """Tests for death row clearing when disk threshold is not met.

    When disk has sufficient free space (threshold not met), the death row
    collection/labels should be cleared. This ensures users don't see stale
    "Leaving Soon" items when no deletions are pending.
    """

    @pytest.fixture
    def mock_config(self):
        """Create a mock config for Deleterr."""
        return MagicMock(
            settings={
                "dry_run": False,
                "plex": {"url": "http://localhost:32400", "token": "test_token"},
                "radarr": [{"name": "Radarr", "url": "http://localhost:7878", "api_key": "test"}],
                "sonarr": [],
                "libraries": [],
                "ssl_verify": False,
            }
        )

    @pytest.fixture
    def deleterr_instance(self, mock_config):
        """Create a Deleterr instance with mocked dependencies."""
        with patch("app.deleterr.PlexMediaServer"), \
             patch("app.deleterr.MediaCleaner"), \
             patch("app.deleterr.NotificationManager"), \
             patch("app.deleterr.DRadarr"), \
             patch("app.deleterr.DSonarr"):

            from app.deleterr import Deleterr

            instance = object.__new__(Deleterr)
            instance.config = mock_config
            instance.media_server = MagicMock()
            instance.media_cleaner = MagicMock()
            instance.notifications = MagicMock()
            instance.run_result = MagicMock()
            instance.radarr = {"Radarr": MagicMock()}
            instance.sonarr = {}
            instance.libraries_processed = 0
            instance.libraries_failed = 0

            return instance

    def test_threshold_not_met_clears_collection(self, deleterr_instance, mock_config):
        """Verify collection is cleared when disk threshold is not met (non-dry-run).

        When library_meets_disk_space_threshold returns False:
        - _process_death_row returns (0, [], [])
        - _process_library_leaving_soon is called with empty preview
        - process_leaving_soon clears the collection
        """
        library = {
            "name": "Movies",
            "radarr": "Radarr",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}},
        }
        mock_config.settings["libraries"] = [library]

        # Threshold NOT met (disk has space) - returns (0, [], [])
        with patch("app.media_cleaner.library_meets_disk_space_threshold", return_value=False):
            from app.deleterr import Deleterr
            # Call the actual method
            saved_space, deleted, preview = deleterr_instance._process_death_row(
                library, deleterr_instance.radarr["Radarr"], "movie"
            )

        # Should return empty results
        assert saved_space == 0
        assert deleted == []
        assert preview == []

    def test_threshold_not_met_clears_labels(self, media_cleaner, mock_media_server):
        """Verify labels are cleared when threshold not met (non-dry-run).

        When process_leaving_soon is called with empty plex_items:
        - Existing labels should be removed from all items
        - No new labels should be added
        """
        library_config = {
            "name": "Movies",
            "leaving_soon": {"labels": {"name": "leaving-soon"}},
        }
        plex_library = MagicMock()

        # Existing items with the label (simulating stale death row)
        old_item_1 = MagicMock()
        old_item_1.ratingKey = "1001"
        old_item_2 = MagicMock()
        old_item_2.ratingKey = "1002"

        mock_media_server.get_items_with_label.return_value = [old_item_1, old_item_2]

        # Call with empty list (clearing death row)
        media_cleaner.process_leaving_soon(library_config, plex_library, [], "movie")

        # Should remove labels from both old items
        assert mock_media_server.remove_label.call_count == 2
        mock_media_server.remove_label.assert_any_call(old_item_1, "leaving-soon")
        mock_media_server.remove_label.assert_any_call(old_item_2, "leaving-soon")

        # Should NOT add any new labels
        mock_media_server.add_label.assert_not_called()

    def test_threshold_not_met_logs_correctly_dry_run(self, deleterr_instance, mock_config, caplog):
        """Verify INFO-level log appears in dry-run mode when threshold not met.

        In dry-run mode, users should see an INFO log indicating that the
        collection/labels WOULD be cleared.
        """
        import logging

        mock_config.settings["dry_run"] = True

        library = {
            "name": "Movies",
            "radarr": "Radarr",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}},
        }

        # Empty preview (threshold not met scenario)
        preview = []

        deleterr_instance.media_server.get_library.return_value = MagicMock()

        with caplog.at_level(logging.INFO):
            deleterr_instance._process_library_leaving_soon(library, preview, "movie")

        # Should log INFO about clearing
        assert any(
            "[DRY-RUN]" in record.message and "would be cleared" in record.message
            for record in caplog.records
        ), f"Expected dry-run clearing log, got: {[r.message for r in caplog.records]}"

    def test_threshold_not_met_no_modify_in_dry_run(self, deleterr_instance, mock_config):
        """Verify collection/labels are NOT modified in dry-run mode.

        In dry-run mode, even when threshold is not met, the collection
        and labels should remain unchanged.
        """
        mock_config.settings["dry_run"] = True

        library = {
            "name": "Movies",
            "radarr": "Radarr",
            "leaving_soon": {
                "collection": {"name": "Leaving Soon"},
                "labels": {"name": "leaving-soon"},
            },
        }

        # Empty preview (threshold not met scenario)
        preview = []

        deleterr_instance._process_library_leaving_soon(library, preview, "movie")

        # In dry-run, process_leaving_soon should NOT be called
        deleterr_instance.media_cleaner.process_leaving_soon.assert_not_called()

    def test_threshold_not_met_logs_library_name(self, deleterr_instance, mock_config, caplog):
        """Verify log includes library name when threshold not met."""
        import logging

        library = {
            "name": "My Movies Library",
            "radarr": "Radarr",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}},
        }

        with patch("app.media_cleaner.library_meets_disk_space_threshold", return_value=False):
            with caplog.at_level(logging.INFO):
                deleterr_instance._process_death_row(
                    library, deleterr_instance.radarr["Radarr"], "movie"
                )

        # Should log with library name
        assert any(
            "My Movies Library" in record.message
            for record in caplog.records
        ), f"Expected library name in log, got: {[r.message for r in caplog.records]}"


class TestCollectionCreationEdgeCases:
    """Tests for collection creation edge cases (empty items, recreation)."""

    def test_collection_creation_with_items(self, media_cleaner, mock_media_server):
        """Test creating a new collection with items works."""
        library_config = {
            "name": "Movies",
            "leaving_soon": {
                "collection": {"name": "Leaving Soon"},
            },
        }
        plex_library = MagicMock()
        mock_plex_item = MagicMock()
        mock_collection = MagicMock()
        mock_media_server.find_item.return_value = mock_plex_item
        mock_media_server.get_or_create_collection.return_value = mock_collection

        items_to_tag = [{"title": "Movie 1", "year": 2020}]

        media_cleaner.process_leaving_soon(library_config, plex_library, items_to_tag, "movie")

        mock_media_server.get_or_create_collection.assert_called_once()
        mock_media_server.set_collection_items.assert_called_once()

    def test_collection_not_created_when_no_items(self, media_cleaner, mock_media_server):
        """Test that no collection is created when there are no items and collection doesn't exist."""
        library_config = {
            "name": "Movies",
            "leaving_soon": {
                "collection": {"name": "Leaving Soon"},
            },
        }
        plex_library = MagicMock()
        # Simulate: collection doesn't exist, no items to create with → returns None
        mock_media_server.get_or_create_collection.return_value = None

        media_cleaner.process_leaving_soon(library_config, plex_library, [], "movie")

        mock_media_server.get_or_create_collection.assert_called_once()
        # set_collection_items should NOT be called since collection is None
        mock_media_server.set_collection_items.assert_not_called()

    def test_existing_collection_cleared_when_no_items(self, media_cleaner, mock_media_server):
        """Test that an existing collection is cleared when there are no items to tag."""
        library_config = {
            "name": "Movies",
            "leaving_soon": {
                "collection": {"name": "Leaving Soon"},
            },
        }
        plex_library = MagicMock()
        mock_collection = MagicMock()
        # Simulate: collection exists but no items
        mock_media_server.get_or_create_collection.return_value = mock_collection

        media_cleaner.process_leaving_soon(library_config, plex_library, [], "movie")

        # Should clear the existing collection
        mock_media_server.set_collection_items.assert_called_once_with(mock_collection, [])


class TestDeathRowLogging:
    """Tests for enhanced death row logging."""

    @pytest.fixture
    def mock_config(self):
        return MagicMock(
            settings={
                "dry_run": False,
                "plex": {"url": "http://localhost:32400", "token": "test_token"},
                "radarr": [{"name": "Radarr", "url": "http://localhost:7878", "api_key": "test"}],
                "sonarr": [],
                "libraries": [],
                "ssl_verify": False,
            }
        )

    @pytest.fixture
    def deleterr_instance(self, mock_config):
        with patch("app.deleterr.PlexMediaServer"), \
             patch("app.deleterr.MediaCleaner"), \
             patch("app.deleterr.NotificationManager"), \
             patch("app.deleterr.DRadarr"), \
             patch("app.deleterr.DSonarr"):

            from app.deleterr import Deleterr

            instance = object.__new__(Deleterr)
            instance.config = mock_config
            instance.media_server = MagicMock()
            instance.media_cleaner = MagicMock()
            instance.notifications = MagicMock()
            instance.run_result = MagicMock()
            instance.radarr = {"Radarr": MagicMock()}
            instance.sonarr = {}
            instance.libraries_processed = 0
            instance.libraries_failed = 0

            return instance

    def test_death_row_logging_shows_filtered_count(self, deleterr_instance, caplog):
        """Verify enhanced logging shows why items were filtered out."""
        import logging

        library = {
            "name": "Movies",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}},
            "preview_next": 5,
        }

        # 3 items in death row
        plex_items = [MagicMock(ratingKey=i) for i in range(3)]

        # Only 1 still matches deletion rules (2 filtered out)
        radarr_movie = {"id": 1, "title": "Movie A", "tmdbId": 550, "sizeOnDisk": 1000}

        deleterr_instance.media_server.get_library.return_value = MagicMock()
        deleterr_instance.media_server.get_collection.return_value = MagicMock()
        deleterr_instance._get_death_row_items = MagicMock(return_value=plex_items)
        deleterr_instance._get_deletion_candidates = MagicMock(return_value=[radarr_movie])

        plex_item_match = MagicMock(ratingKey=0)
        deleterr_instance.media_server.find_item.return_value = plex_item_match

        with patch("app.media_cleaner.library_meets_disk_space_threshold", return_value=True):
            with caplog.at_level(logging.INFO):
                deleterr_instance._process_death_row(
                    library, deleterr_instance.radarr["Radarr"], "movie"
                )

        assert any(
            "protected by thresholds, exclusions, or watch activity" in record.message
            for record in caplog.records
        ), f"Expected enhanced logging about filtered items, got: {[r.message for r in caplog.records]}"

    def test_death_row_logging_no_filtered_message_when_all_match(self, deleterr_instance, caplog):
        """Verify no 'protected' message when all death row items still match."""
        import logging

        library = {
            "name": "Movies",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}},
            "preview_next": 5,
        }

        # 1 item in death row, 1 still matches
        plex_item = MagicMock(ratingKey=1001)
        radarr_movie = {"id": 1, "title": "Movie A", "tmdbId": 550, "sizeOnDisk": 1000}

        deleterr_instance.media_server.get_library.return_value = MagicMock()
        deleterr_instance.media_server.get_collection.return_value = MagicMock()
        deleterr_instance._get_death_row_items = MagicMock(return_value=[plex_item])
        deleterr_instance._get_deletion_candidates = MagicMock(return_value=[radarr_movie])
        deleterr_instance.media_server.find_item.return_value = plex_item

        with patch("app.media_cleaner.library_meets_disk_space_threshold", return_value=True):
            with caplog.at_level(logging.INFO):
                deleterr_instance._process_death_row(
                    library, deleterr_instance.radarr["Radarr"], "movie"
                )

        assert not any(
            "protected by" in record.message
            for record in caplog.records
        ), f"Should not show 'protected' message when all items match, got: {[r.message for r in caplog.records]}"


class TestDeathRowDeletionErrorHandling:
    """Tests for error handling during death row deletions.

    Ensures that when a deletion fails (network error, API error, etc.),
    the loop continues processing remaining items instead of crashing.
    See: https://github.com/rfsbraz/deleterr/issues/227
    """

    @pytest.fixture
    def mock_config(self):
        return MagicMock(
            settings={
                "dry_run": False,
                "plex": {"url": "http://localhost:32400", "token": "test_token"},
                "radarr": [{"name": "Radarr", "url": "http://localhost:7878", "api_key": "test"}],
                "sonarr": [{"name": "Sonarr", "url": "http://localhost:8989", "api_key": "test"}],
                "libraries": [],
                "ssl_verify": False,
            }
        )

    @pytest.fixture
    def deleterr_instance(self, mock_config):
        with patch("app.deleterr.PlexMediaServer"), \
             patch("app.deleterr.MediaCleaner"), \
             patch("app.deleterr.NotificationManager"), \
             patch("app.deleterr.DRadarr"), \
             patch("app.deleterr.DSonarr"):

            from app.deleterr import Deleterr

            instance = object.__new__(Deleterr)
            instance.config = mock_config
            instance.media_server = MagicMock()
            instance.media_cleaner = MagicMock()
            instance.notifications = MagicMock()
            instance.run_result = MagicMock()
            instance.radarr = {"Radarr": MagicMock()}
            instance.sonarr = {"Sonarr": MagicMock()}
            instance.libraries_processed = 0
            instance.libraries_failed = 0

            return instance

    def test_movie_deletion_failure_continues_to_next(self, deleterr_instance):
        """When del_movie() raises for one movie, remaining movies are still processed."""
        library = {
            "name": "Movies",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}},
            "preview_next": 5,
        }

        plex_item_a = MagicMock(ratingKey=1001)
        plex_item_b = MagicMock(ratingKey=1002)

        radarr_movie_a = {"id": 101, "title": "Movie A", "tmdbId": 550, "sizeOnDisk": 1000}
        radarr_movie_b = {"id": 102, "title": "Movie B", "tmdbId": 551, "sizeOnDisk": 2000}

        radarr_instance = deleterr_instance.radarr["Radarr"]
        # First call raises, second succeeds
        radarr_instance.del_movie.side_effect = [Exception("Connection timeout"), None]

        deleterr_instance.media_server.get_library.return_value = MagicMock()
        deleterr_instance.media_server.get_collection.return_value = MagicMock()
        deleterr_instance._get_death_row_items = MagicMock(
            return_value=[plex_item_a, plex_item_b]
        )
        deleterr_instance._get_deletion_candidates = MagicMock(
            return_value=[radarr_movie_a, radarr_movie_b]
        )

        def find_item_side_effect(lib, tmdb_id=None, imdb_id=None, title=None, year=None):
            if tmdb_id == 550:
                return plex_item_a
            elif tmdb_id == 551:
                return plex_item_b
            return None

        deleterr_instance.media_server.find_item.side_effect = find_item_side_effect

        with patch("app.media_cleaner.library_meets_disk_space_threshold", return_value=True):
            saved_space, deleted, preview = deleterr_instance._process_death_row(
                library, radarr_instance, "movie"
            )

        # Both movies should have been attempted
        assert radarr_instance.del_movie.call_count == 2
        # Only Movie B should be in deleted (Movie A failed)
        assert len(deleted) == 1
        assert deleted[0]["title"] == "Movie B"

    def test_movie_deletion_failure_not_in_deleted_items(self, deleterr_instance):
        """A movie that fails deletion is NOT counted as deleted."""
        library = {
            "name": "Movies",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}},
            "preview_next": 5,
        }

        plex_item = MagicMock(ratingKey=1001)
        radarr_movie = {"id": 101, "title": "Failing Movie", "tmdbId": 550, "sizeOnDisk": 1000}

        radarr_instance = deleterr_instance.radarr["Radarr"]
        radarr_instance.del_movie.side_effect = Exception("API error 500")

        deleterr_instance.media_server.get_library.return_value = MagicMock()
        deleterr_instance.media_server.get_collection.return_value = MagicMock()
        deleterr_instance._get_death_row_items = MagicMock(return_value=[plex_item])
        deleterr_instance._get_deletion_candidates = MagicMock(return_value=[radarr_movie])
        deleterr_instance.media_server.find_item.return_value = plex_item

        with patch("app.media_cleaner.library_meets_disk_space_threshold", return_value=True):
            saved_space, deleted, preview = deleterr_instance._process_death_row(
                library, radarr_instance, "movie"
            )

        # Failed movie should NOT be in deleted items
        assert len(deleted) == 0

    def test_movie_deletion_failure_logged(self, deleterr_instance, caplog):
        """Error is logged with movie title when deletion fails."""
        import logging

        library = {
            "name": "Movies",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}},
            "preview_next": 5,
        }

        plex_item = MagicMock(ratingKey=1001)
        radarr_movie = {"id": 101, "title": "Broken Movie", "tmdbId": 550, "sizeOnDisk": 1000}

        radarr_instance = deleterr_instance.radarr["Radarr"]
        radarr_instance.del_movie.side_effect = Exception("Network unreachable")

        deleterr_instance.media_server.get_library.return_value = MagicMock()
        deleterr_instance.media_server.get_collection.return_value = MagicMock()
        deleterr_instance._get_death_row_items = MagicMock(return_value=[plex_item])
        deleterr_instance._get_deletion_candidates = MagicMock(return_value=[radarr_movie])
        deleterr_instance.media_server.find_item.return_value = plex_item

        with patch("app.media_cleaner.library_meets_disk_space_threshold", return_value=True):
            with caplog.at_level(logging.ERROR):
                deleterr_instance._process_death_row(
                    library, radarr_instance, "movie"
                )

        assert any(
            "Broken Movie" in record.message
            and "Radarr" in record.message
            and "Network unreachable" in record.message
            for record in caplog.records
        ), f"Expected error log with movie title and error, got: {[r.message for r in caplog.records]}"

    def test_show_deletion_failure_continues(self, deleterr_instance):
        """When delete_series() raises for one show, remaining shows are still processed."""
        library = {
            "name": "TV Shows",
            "leaving_soon": {"collection": {"name": "Leaving Soon"}},
            "preview_next": 5,
        }

        plex_item_a = MagicMock(ratingKey=2001)
        plex_item_b = MagicMock(ratingKey=2002)

        sonarr_show_a = {
            "id": 201, "title": "Show A", "tvdbId": 81189,
            "statistics": {"sizeOnDisk": 5000, "episodeFileCount": 10},
        }
        sonarr_show_b = {
            "id": 202, "title": "Show B", "tvdbId": 81190,
            "statistics": {"sizeOnDisk": 3000, "episodeFileCount": 5},
        }

        sonarr_instance = deleterr_instance.sonarr["Sonarr"]
        # First call raises, second succeeds
        deleterr_instance.media_cleaner.delete_series.side_effect = [
            Exception("Sonarr API timeout"), None
        ]

        deleterr_instance.media_server.get_library.return_value = MagicMock()
        deleterr_instance.media_server.get_collection.return_value = MagicMock()
        deleterr_instance._get_death_row_items = MagicMock(
            return_value=[plex_item_a, plex_item_b]
        )
        deleterr_instance._get_deletion_candidates = MagicMock(
            return_value=[sonarr_show_a, sonarr_show_b]
        )

        def find_item_side_effect(lib, tmdb_id=None, tvdb_id=None, imdb_id=None, title=None, year=None):
            if tvdb_id == 81189:
                return plex_item_a
            elif tvdb_id == 81190:
                return plex_item_b
            return None

        deleterr_instance.media_server.find_item.side_effect = find_item_side_effect

        with patch("app.media_cleaner.library_meets_disk_space_threshold", return_value=True):
            saved_space, deleted, preview = deleterr_instance._process_death_row(
                library, sonarr_instance, "show"
            )

        # Both shows should have been attempted
        assert deleterr_instance.media_cleaner.delete_series.call_count == 2
        # Only Show B should be in deleted (Show A failed)
        assert len(deleted) == 1
        assert deleted[0]["title"] == "Show B"
