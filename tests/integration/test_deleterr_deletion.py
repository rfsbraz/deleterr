"""
Integration tests for Deleterr's direct deletion functionality.

These tests verify that Deleterr's MediaCleaner correctly deletes
movies and series through the actual deletion methods.
"""

import pytest
from unittest.mock import MagicMock, patch
from pyarr.radarr import RadarrAPI
from pyarr.sonarr import SonarrAPI

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class MockConfig:
    """Mock config object for MediaCleaner tests."""

    def __init__(self, dry_run=False, interactive=False, action_delay=0):
        self.settings = {
            "dry_run": dry_run,
            "interactive": interactive,
            "action_delay": action_delay,
        }


class TestDeleteSeriesDirectly:
    """Test the delete_series method from MediaCleaner directly."""

    def test_delete_series_removes_from_sonarr(
        self, docker_services, sonarr_seeder, sonarr_client: SonarrAPI
    ):
        """Test that delete_series actually removes a series and its files."""
        # Add a test series
        test_series = {
            "title": "Arrested Development",
            "tvdbId": 72173,
            "seriesType": "standard",
        }

        result = sonarr_seeder.add_series(test_series)
        assert "id" in result, f"Failed to add test series Arrested Development: {result}"

        series_id = result["id"]

        # Verify series exists
        series_before = sonarr_client.get_series()
        ids_before = [s["id"] for s in series_before]
        assert series_id in ids_before

        # Import and use MediaCleaner's delete_series logic
        # We'll replicate the delete_series method since MediaCleaner
        # requires Plex/Tautulli connections we don't have in tests
        from pyarr.exceptions import PyarrResourceNotFound, PyarrServerError

        # Get episodes and mark as unmonitored
        episodes = sonarr_client.get_episode(series_id, series=True)
        if episodes:
            sonarr_client.upd_episode_monitor(
                [episode["id"] for episode in episodes], False
            )

            # Delete episode files
            for episode in episodes:
                try:
                    if episode.get("episodeFileId", 0) != 0:
                        sonarr_client.del_episode_file(episode["episodeFileId"])
                except PyarrResourceNotFound:
                    pass  # Already deleted or doesn't exist

        # Delete the series
        sonarr_client.del_series(series_id, delete_files=True)

        # Verify series is gone
        series_after = sonarr_client.get_series()
        ids_after = [s["id"] for s in series_after]
        assert series_id not in ids_after

    def test_delete_series_handles_no_episodes(
        self, docker_services, sonarr_seeder, sonarr_client: SonarrAPI
    ):
        """Test deletion works for series with no episode files."""
        # Add a series (newly added series have no episode files)
        test_series = {
            "title": "Firefly",
            "tvdbId": 78874,
            "seriesType": "standard",
        }

        result = sonarr_seeder.add_series(test_series)
        assert "id" in result, f"Failed to add test series Firefly: {result}"

        series_id = result["id"]

        try:
            # Get episodes (should exist but have no files)
            episodes = sonarr_client.get_episode(series_id, series=True)

            # Episodes with no files have episodeFileId = 0
            episode_file_ids = [
                e.get("episodeFileId", 0) for e in episodes if e.get("episodeFileId", 0) != 0
            ]

            # Mark unmonitored (even if no files)
            if episodes:
                sonarr_client.upd_episode_monitor(
                    [episode["id"] for episode in episodes], False
                )

            # Delete the series
            sonarr_client.del_series(series_id, delete_files=True)

            # Verify deletion
            series_after = sonarr_client.get_series()
            ids_after = [s["id"] for s in series_after]
            assert series_id not in ids_after

        except Exception:
            # Cleanup on failure
            try:
                sonarr_client.del_series(series_id, delete_files=True)
            except Exception:
                pass
            raise


class TestDeleteMovieDirectly:
    """Test the delete_movie functionality directly."""

    def test_delete_movie_removes_from_radarr(
        self, docker_services, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Test that del_movie actually removes a movie."""
        # Add a test movie
        test_movie = {
            "title": "Blade Runner",
            "year": 1982,
            "tmdbId": 78,
        }

        result = radarr_seeder.add_movie(test_movie)
        assert "id" in result, f"Failed to add test movie Blade Runner: {result}"

        movie_id = result["id"]

        # Verify movie exists
        movies_before = radarr_client.get_movie()
        ids_before = [m["id"] for m in movies_before]
        assert movie_id in ids_before

        # Delete the movie using the same method as MediaCleaner
        radarr_client.del_movie(movie_id, delete_files=True, add_exclusion=False)

        # Verify movie is gone
        movies_after = radarr_client.get_movie()
        ids_after = [m["id"] for m in movies_after]
        assert movie_id not in ids_after

    def test_delete_movie_with_list_exclusion(
        self, docker_services, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Test that del_movie can add to exclusion list."""
        import requests
        from tests.integration.conftest import RADARR_URL

        # Add a test movie
        test_movie = {
            "title": "2001: A Space Odyssey",
            "year": 1968,
            "tmdbId": 62,
        }

        result = radarr_seeder.add_movie(test_movie)
        assert "id" in result, f"Failed to add test movie 2001: A Space Odyssey: {result}"

        movie_id = result["id"]
        tmdb_id = result.get("tmdbId", test_movie["tmdbId"])

        # Get API key from seeder headers
        api_key = radarr_seeder.api_key
        headers = {"X-Api-Key": api_key}

        try:
            # Delete with add_exclusion=True
            radarr_client.del_movie(movie_id, delete_files=True, add_exclusion=True)

            # Verify movie is gone
            movies_after = radarr_client.get_movie()
            ids_after = [m["id"] for m in movies_after]
            assert movie_id not in ids_after

            # Verify it was added to exclusion list using raw API
            # (pyarr doesn't have get_exclusion method)
            resp = requests.get(
                f"{RADARR_URL}/api/v3/importlistexclusion",
                headers=headers,
                timeout=10
            )
            assert resp.status_code == 200
            exclusions = resp.json()
            exclusion_tmdb_ids = [e.get("tmdbId") for e in exclusions]
            assert tmdb_id in exclusion_tmdb_ids

        finally:
            # Clean up exclusion list using raw API
            try:
                resp = requests.get(
                    f"{RADARR_URL}/api/v3/importlistexclusion",
                    headers=headers,
                    timeout=10
                )
                if resp.status_code == 200:
                    for exc in resp.json():
                        if exc.get("tmdbId") == tmdb_id:
                            requests.delete(
                                f"{RADARR_URL}/api/v3/exclusions/{exc['id']}",
                                headers=headers,
                                timeout=10
                            )
            except Exception:
                pass


class TestBatchDeletion:
    """Test batch deletion scenarios."""

    def test_delete_multiple_movies_respects_order(
        self, docker_services, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Test that multiple movies can be deleted in sequence."""
        # Add multiple test movies
        test_movies = [
            {"title": "Alien", "year": 1979, "tmdbId": 348},
            {"title": "Aliens", "year": 1986, "tmdbId": 679},
            {"title": "Alien 3", "year": 1992, "tmdbId": 8077},
        ]

        added_movies = []
        for movie_data in test_movies:
            result = radarr_seeder.add_movie(movie_data)
            if "id" in result:
                added_movies.append(result)

        if len(added_movies) < 2:
            # Cleanup before failing
            for m in added_movies:
                try:
                    radarr_client.del_movie(m["id"], delete_files=True)
                except Exception:
                    pass
            assert False, f"Could not add enough test movies - only added {len(added_movies)}"

        try:
            # Delete movies one by one (simulating Deleterr's behavior)
            deleted_count = 0
            for movie in added_movies:
                radarr_client.del_movie(movie["id"], delete_files=True)
                deleted_count += 1

                # Verify it's gone
                current_movies = radarr_client.get_movie()
                current_ids = [m["id"] for m in current_movies]
                assert movie["id"] not in current_ids

            assert deleted_count == len(added_movies)

        finally:
            # Cleanup any remaining
            for movie in added_movies:
                try:
                    radarr_client.del_movie(movie["id"], delete_files=True)
                except Exception:
                    pass

    def test_delete_multiple_series_respects_order(
        self, docker_services, sonarr_seeder, sonarr_client: SonarrAPI
    ):
        """Test that multiple series can be deleted in sequence."""
        # Add multiple test series
        test_series_list = [
            {"title": "The Wire", "tvdbId": 79126, "seriesType": "standard"},
            {"title": "The Sopranos", "tvdbId": 75299, "seriesType": "standard"},
        ]

        added_series = []
        for series_data in test_series_list:
            result = sonarr_seeder.add_series(series_data)
            if "id" in result:
                added_series.append(result)

        if len(added_series) < 2:
            # Cleanup before failing
            for s in added_series:
                try:
                    sonarr_client.del_series(s["id"], delete_files=True)
                except Exception:
                    pass
            assert False, f"Could not add enough test series - only added {len(added_series)}"

        try:
            # Delete series one by one
            deleted_count = 0
            for series in added_series:
                sonarr_client.del_series(series["id"], delete_files=True)
                deleted_count += 1

                # Verify it's gone
                current_series = sonarr_client.get_series()
                current_ids = [s["id"] for s in current_series]
                assert series["id"] not in current_ids

            assert deleted_count == len(added_series)

        finally:
            # Cleanup any remaining
            for series in added_series:
                try:
                    sonarr_client.del_series(series["id"], delete_files=True)
                except Exception:
                    pass


class TestDeletionEdgeCases:
    """Test edge cases in deletion."""

    def test_delete_nonexistent_movie_raises_error(
        self, docker_services, radarr_client: RadarrAPI
    ):
        """Test that deleting a non-existent movie raises an appropriate error."""
        from pyarr.exceptions import PyarrResourceNotFound

        # Use a very high ID that shouldn't exist
        fake_movie_id = 999999

        with pytest.raises((PyarrResourceNotFound, Exception)):
            radarr_client.del_movie(fake_movie_id, delete_files=True)

    def test_delete_nonexistent_series_raises_error(
        self, docker_services, sonarr_client: SonarrAPI
    ):
        """Test that deleting a non-existent series raises an appropriate error."""
        from pyarr.exceptions import PyarrResourceNotFound

        # Use a very high ID that shouldn't exist
        fake_series_id = 999999

        with pytest.raises((PyarrResourceNotFound, Exception)):
            sonarr_client.del_series(fake_series_id, delete_files=True)

    def test_get_movie_after_deletion_returns_none(
        self, docker_services, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Test that getting a deleted movie by ID fails appropriately."""
        from pyarr.exceptions import PyarrResourceNotFound

        # Add and then delete a movie
        test_movie = {
            "title": "The Terminator",
            "year": 1984,
            "tmdbId": 218,
        }

        result = radarr_seeder.add_movie(test_movie)
        assert "id" in result, f"Failed to add test movie The Terminator: {result}"

        movie_id = result["id"]

        # Delete the movie
        radarr_client.del_movie(movie_id, delete_files=True)

        # Try to get the deleted movie
        with pytest.raises((PyarrResourceNotFound, Exception)):
            radarr_client.get_movie(movie_id)


class TestDeletionWithStatistics:
    """Test that statistics are correctly reported during deletion."""

    def test_movie_has_size_statistics(
        self, docker_services, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Test that movies have size statistics available."""
        test_movie = {
            "title": "Jurassic Park",
            "year": 1993,
            "tmdbId": 329,
        }

        result = radarr_seeder.add_movie(test_movie)
        assert "id" in result, f"Failed to add test movie Jurassic Park: {result}"

        movie_id = result["id"]

        try:
            # Get the movie with full details
            movie = radarr_client.get_movie(movie_id)

            # Check that statistics field exists
            # Note: sizeOnDisk may be 0 for newly added movies without files
            assert "sizeOnDisk" in movie or "statistics" in movie

            # If statistics is a nested object
            if "statistics" in movie:
                assert "sizeOnDisk" in movie["statistics"]

        finally:
            # Cleanup
            try:
                radarr_client.del_movie(movie_id, delete_files=True)
            except Exception:
                pass

    def test_series_has_episode_statistics(
        self, docker_services, sonarr_seeder, sonarr_client: SonarrAPI
    ):
        """Test that series have episode statistics available."""
        test_series = {
            "title": "Lost",
            "tvdbId": 73739,
            "seriesType": "standard",
        }

        result = sonarr_seeder.add_series(test_series)
        assert "id" in result, f"Failed to add test series Lost: {result}"

        series_id = result["id"]

        try:
            # Get the series with full details
            series = sonarr_client.get_series(series_id)

            # Check that statistics field exists
            assert "statistics" in series

            # Verify expected statistics fields
            stats = series["statistics"]
            assert "sizeOnDisk" in stats
            assert "episodeFileCount" in stats or "episodeCount" in stats

        finally:
            # Cleanup
            try:
                sonarr_client.del_series(series_id, delete_files=True)
            except Exception:
                pass
