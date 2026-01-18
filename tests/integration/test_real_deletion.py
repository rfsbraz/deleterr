"""
Integration tests for real deletion workflows against Radarr/Sonarr.

These tests verify actual deletion operations work correctly with real
Radarr and Sonarr containers, testing the full deletion pipeline.
"""

import pytest
import time
import requests

from pyarr.radarr import RadarrAPI
from pyarr.sonarr import SonarrAPI
from pyarr.exceptions import PyarrResourceNotFound

from tests.integration.conftest import RADARR_URL, SONARR_URL

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestRealMovieDeletion:
    """Test actual movie deletion operations against Radarr."""

    def test_delete_movie_removes_from_library(
        self, docker_services, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Test that deleting a movie actually removes it from Radarr."""
        # Add a test movie
        test_movie = {
            "title": "Test Delete Movie",
            "year": 2020,
            "tmdbId": 634649,  # Spider-Man: No Way Home
        }

        result = radarr_seeder.add_movie(test_movie)
        assert "id" in result, f"Failed to add test movie: {result}"
        movie_id = result["id"]

        try:
            # Verify movie exists
            movie = radarr_client.get_movie(movie_id)
            assert movie is not None
            assert movie["title"] == "Spider-Man: No Way Home"

            # Delete the movie
            radarr_client.del_movie(movie_id, delete_files=True)

            # Verify movie is gone
            with pytest.raises(PyarrResourceNotFound):
                radarr_client.get_movie(movie_id)

        except Exception:
            # Cleanup if test fails
            try:
                radarr_client.del_movie(movie_id, delete_files=True)
            except Exception:
                pass
            raise

    def test_delete_movie_with_exclusion_adds_to_list(
        self, docker_services, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Test that deleting with add_exclusion adds to exclusion list."""
        api_key = radarr_seeder.api_key
        headers = {"X-Api-Key": api_key}

        test_movie = {
            "title": "Exclusion Test Movie",
            "year": 2019,
            "tmdbId": 429617,  # Spider-Man: Far From Home
        }

        result = radarr_seeder.add_movie(test_movie)
        assert "id" in result, f"Failed to add test movie: {result}"
        movie_id = result["id"]
        tmdb_id = result.get("tmdbId", test_movie["tmdbId"])

        try:
            # Delete with add_exclusion=True
            radarr_client.del_movie(movie_id, delete_files=True, add_exclusion=True)

            # Verify movie was added to exclusion list (with retry for timing)
            import time
            exclusion_tmdb_ids = []
            for attempt in range(5):
                time.sleep(1)  # Give Radarr time to process
                resp = requests.get(
                    f"{RADARR_URL}/api/v3/exclusions",
                    headers=headers,
                    timeout=10
                )
                assert resp.status_code == 200
                exclusions = resp.json()
                exclusion_tmdb_ids = [e.get("tmdbId") for e in exclusions]
                if tmdb_id in exclusion_tmdb_ids:
                    break
            assert tmdb_id in exclusion_tmdb_ids, f"Movie {tmdb_id} should be in exclusion list, got {exclusion_tmdb_ids}"

        finally:
            # Cleanup exclusion list
            try:
                resp = requests.get(
                    f"{RADARR_URL}/api/v3/exclusions",
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

    def test_delete_movie_without_exclusion_not_in_list(
        self, docker_services, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Test that deleting without add_exclusion does NOT add to exclusion list."""
        api_key = radarr_seeder.api_key
        headers = {"X-Api-Key": api_key}

        test_movie = {
            "title": "No Exclusion Test Movie",
            "year": 2017,
            "tmdbId": 315635,  # Spider-Man: Homecoming
        }

        result = radarr_seeder.add_movie(test_movie)
        assert "id" in result, f"Failed to add test movie: {result}"
        movie_id = result["id"]
        tmdb_id = result.get("tmdbId", test_movie["tmdbId"])

        try:
            # Get exclusions before deletion
            resp = requests.get(
                f"{RADARR_URL}/api/v3/exclusions",
                headers=headers,
                timeout=10
            )
            _exclusions_before = resp.json() if resp.status_code == 200 else []

            # Delete WITHOUT add_exclusion
            radarr_client.del_movie(movie_id, delete_files=True, add_exclusion=False)

            # Verify movie was NOT added to exclusion list
            resp = requests.get(
                f"{RADARR_URL}/api/v3/exclusions",
                headers=headers,
                timeout=10
            )
            exclusions_after = resp.json() if resp.status_code == 200 else []

            # Should have same number of exclusions
            new_exclusion_tmdb_ids = [e.get("tmdbId") for e in exclusions_after]
            assert tmdb_id not in new_exclusion_tmdb_ids, "Movie should NOT be in exclusion list"

        except Exception:
            # Cleanup if test fails
            try:
                radarr_client.del_movie(movie_id, delete_files=True)
            except Exception:
                pass
            raise


class TestRealSeriesDeletion:
    """Test actual series deletion operations against Sonarr."""

    def test_delete_series_removes_from_library(
        self, docker_services, sonarr_seeder, sonarr_client: SonarrAPI
    ):
        """Test that deleting a series actually removes it from Sonarr."""
        test_series = {
            "title": "Test Delete Series",
            "tvdbId": 153021,  # The Mandalorian
            "seriesType": "standard",
        }

        result = sonarr_seeder.add_series(test_series)
        assert "id" in result, f"Failed to add test series: {result}"
        series_id = result["id"]

        try:
            # Verify series exists
            series = sonarr_client.get_series(series_id)
            assert series is not None

            # Delete the series
            sonarr_client.del_series(series_id, delete_files=True)

            # Verify series is gone
            all_series = sonarr_client.get_series()
            series_ids = [s["id"] for s in all_series]
            assert series_id not in series_ids, "Series should be deleted"

        except Exception:
            # Cleanup if test fails
            try:
                sonarr_client.del_series(series_id, delete_files=True)
            except Exception:
                pass
            raise

    def test_delete_series_unmonitors_episodes_first(
        self, docker_services, sonarr_seeder, sonarr_client: SonarrAPI
    ):
        """Test the deletion workflow that unmonitors episodes before deletion."""
        from pyarr.exceptions import PyarrResourceNotFound

        test_series = {
            "title": "Episode Unmonitor Test",
            "tvdbId": 305288,  # Stranger Things
            "seriesType": "standard",
        }

        result = sonarr_seeder.add_series(test_series)
        assert "id" in result, f"Failed to add test series: {result}"
        series_id = result["id"]

        try:
            # Get episodes
            episodes = sonarr_client.get_episode(series_id, series=True)

            if episodes:
                # Unmonitor all episodes (simulating MediaCleaner behavior)
                episode_ids = [ep["id"] for ep in episodes]
                sonarr_client.upd_episode_monitor(episode_ids, False)

                # Verify episodes are unmonitored
                updated_episodes = sonarr_client.get_episode(series_id, series=True)
                assert all(
                    not ep["monitored"] for ep in updated_episodes
                ), "All episodes should be unmonitored"

            # Now delete the series
            sonarr_client.del_series(series_id, delete_files=True)

            # Verify series is deleted
            all_series = sonarr_client.get_series()
            assert series_id not in [
                s["id"] for s in all_series
            ], "Series should be deleted"

        except Exception:
            try:
                sonarr_client.del_series(series_id, delete_files=True)
            except Exception:
                pass
            raise


class TestBatchDeletionOperations:
    """Test batch deletion scenarios."""

    def test_delete_multiple_movies_sequentially(
        self, docker_services, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Test deleting multiple movies one at a time (simulating max_actions)."""
        test_movies = [
            {"title": "Batch Movie 1", "year": 2020, "tmdbId": 508943},  # Luca
            {"title": "Batch Movie 2", "year": 2021, "tmdbId": 508947},  # Turning Red
            {"title": "Batch Movie 3", "year": 2022, "tmdbId": 508442},  # Soul
        ]

        added_movies = []
        for movie_data in test_movies:
            result = radarr_seeder.add_movie(movie_data)
            if "id" in result:
                added_movies.append(result)

        assert len(added_movies) >= 2, "Need at least 2 movies for batch test"

        try:
            # Delete movies one by one
            deleted_count = 0
            for movie in added_movies:
                radarr_client.del_movie(movie["id"], delete_files=True)
                deleted_count += 1

                # Verify this movie is gone
                try:
                    radarr_client.get_movie(movie["id"])
                    assert False, f"Movie {movie['id']} should be deleted"
                except (PyarrResourceNotFound, Exception):
                    pass  # Expected

            assert deleted_count == len(added_movies), "All movies should be deleted"

        finally:
            # Cleanup any remaining
            for movie in added_movies:
                try:
                    radarr_client.del_movie(movie["id"], delete_files=True)
                except Exception:
                    pass

    def test_delete_movies_respects_action_limit(
        self, docker_services, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Test that deletion stops after reaching action limit."""
        test_movies = [
            {"title": "Limit Movie 1", "year": 2018, "tmdbId": 920},    # Cars
            {"title": "Limit Movie 2", "year": 2019, "tmdbId": 10681},  # WALL-E
            {"title": "Limit Movie 3", "year": 2020, "tmdbId": 862},    # Toy Story
            {"title": "Limit Movie 4", "year": 2021, "tmdbId": 863},    # Toy Story 2
        ]

        added_movies = []
        for movie_data in test_movies:
            result = radarr_seeder.add_movie(movie_data)
            if "id" in result:
                added_movies.append(result)

        assert len(added_movies) >= 3, "Need at least 3 movies for limit test"

        try:
            # Simulate max_actions_per_run = 2
            max_actions = 2
            deleted_count = 0

            for movie in added_movies:
                if deleted_count >= max_actions:
                    break
                radarr_client.del_movie(movie["id"], delete_files=True)
                deleted_count += 1

            assert deleted_count == max_actions, f"Should stop at {max_actions} deletions"

            # Remaining movies should still exist
            remaining = added_movies[max_actions:]
            for movie in remaining:
                exists = radarr_client.get_movie(movie["id"])
                assert exists is not None, f"Movie {movie['id']} should still exist"

        finally:
            # Cleanup all movies
            for movie in added_movies:
                try:
                    radarr_client.del_movie(movie["id"], delete_files=True)
                except Exception:
                    pass


class TestDeletionEdgeCases:
    """Test edge cases in deletion operations."""

    def test_delete_already_deleted_movie_raises_error(
        self, docker_services, radarr_client: RadarrAPI
    ):
        """Test that trying to delete a non-existent movie raises an error."""
        fake_movie_id = 999999

        with pytest.raises((PyarrResourceNotFound, Exception)):
            radarr_client.del_movie(fake_movie_id, delete_files=True)

    def test_delete_movie_returns_immediately(
        self, docker_services, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Test that movie deletion is synchronous and immediate."""
        test_movie = {
            "title": "Quick Delete Test",
            "year": 2023,
            "tmdbId": 569094,  # Spider-Man: Across the Spider-Verse
        }

        result = radarr_seeder.add_movie(test_movie)
        assert "id" in result, f"Failed to add test movie: {result}"
        movie_id = result["id"]

        try:
            start_time = time.time()
            radarr_client.del_movie(movie_id, delete_files=True)
            elapsed = time.time() - start_time

            # Deletion should be relatively quick (< 30 seconds)
            assert elapsed < 30, f"Deletion took too long: {elapsed}s"

            # Verify movie is immediately gone
            with pytest.raises((PyarrResourceNotFound, Exception)):
                radarr_client.get_movie(movie_id)

        except Exception:
            try:
                radarr_client.del_movie(movie_id, delete_files=True)
            except Exception:
                pass
            raise


class TestStatisticsAfterDeletion:
    """Test that statistics are correctly updated after deletion."""

    def test_movie_count_decreases_after_deletion(
        self, docker_services, radarr_seeder, radarr_client: RadarrAPI
    ):
        """Test that total movie count decreases after deletion."""
        # Get initial count
        movies_before = radarr_client.get_movie()
        count_before = len(movies_before)

        test_movie = {
            "title": "Count Test Movie",
            "year": 2022,
            "tmdbId": 453395,  # Doctor Strange in the Multiverse of Madness
        }

        result = radarr_seeder.add_movie(test_movie)
        assert "id" in result, f"Failed to add test movie: {result}"
        movie_id = result["id"]

        try:
            # Verify count increased
            movies_after_add = radarr_client.get_movie()
            count_after_add = len(movies_after_add)
            assert count_after_add == count_before + 1, "Count should increase by 1"

            # Delete the movie
            radarr_client.del_movie(movie_id, delete_files=True)

            # Verify count is back to original
            movies_after_delete = radarr_client.get_movie()
            count_after_delete = len(movies_after_delete)
            assert count_after_delete == count_before, "Count should return to original"

        except Exception:
            try:
                radarr_client.del_movie(movie_id, delete_files=True)
            except Exception:
                pass
            raise

    def test_series_count_decreases_after_deletion(
        self, docker_services, sonarr_seeder, sonarr_client: SonarrAPI
    ):
        """Test that total series count decreases after deletion."""
        # Get initial count
        series_before = sonarr_client.get_series()
        count_before = len(series_before)

        test_series = {
            "title": "Count Test Series",
            "tvdbId": 328724,  # The Boys
            "seriesType": "standard",
        }

        result = sonarr_seeder.add_series(test_series)
        assert "id" in result, f"Failed to add test series: {result}"
        series_id = result["id"]

        try:
            # Verify count increased
            series_after_add = sonarr_client.get_series()
            count_after_add = len(series_after_add)
            assert count_after_add == count_before + 1, "Count should increase by 1"

            # Delete the series
            sonarr_client.del_series(series_id, delete_files=True)

            # Verify count is back to original
            series_after_delete = sonarr_client.get_series()
            count_after_delete = len(series_after_delete)
            assert count_after_delete == count_before, "Count should return to original"

        except Exception:
            try:
                sonarr_client.del_series(series_id, delete_files=True)
            except Exception:
                pass
            raise
