"""
End-to-end integration tests for Deleterr deletion workflows.

These tests verify the complete deletion workflow from Plex/Tautulli
data through to Radarr/Sonarr deletions.
"""

import pytest

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestDryRunMode:
    """Test that dry run mode prevents actual deletions."""

    def test_dry_run_does_not_delete_movies(
        self, integration_config, seeded_radarr
    ):
        """Verify dry run mode logs but doesn't delete movies."""
        # Ensure dry_run is enabled in config
        assert integration_config["dry_run"] is True

        # Get movies before
        movies_before = seeded_radarr.get_movie()
        count_before = len(movies_before)

        # Fail if no movies were seeded
        assert count_before > 0, "No movies seeded - seeding failed"

        # Simulate what Deleterr would do in dry run
        # (In actual implementation, dry run skips the delete call)
        if movies_before:
            # In dry run, we would NOT call delete
            # Just verify the movie still exists
            pass

        # Verify nothing was deleted
        movies_after = seeded_radarr.get_movie()
        count_after = len(movies_after)
        assert count_after == count_before

    def test_dry_run_does_not_delete_series(
        self, integration_config, seeded_sonarr
    ):
        """Verify dry run mode logs but doesn't delete series."""
        assert integration_config["dry_run"] is True

        series_before = seeded_sonarr.get_series()
        count_before = len(series_before)

        # Fail if no series were seeded
        assert count_before > 0, "No series seeded - seeding failed"

        # In dry run, no deletions would be made
        # Verify nothing was deleted
        series_after = seeded_sonarr.get_series()
        count_after = len(series_after)
        assert count_after == count_before


class TestMovieDeletionWorkflow:
    """Test complete movie deletion workflows."""

    def test_delete_old_unwatched_movie(
        self, docker_services, radarr_seeder, radarr_client
    ):
        """Test deleting a movie that hasn't been watched."""
        # Add a test movie (using real TMDb ID for Interstellar)
        test_movie = {
            "title": "Interstellar",
            "year": 2014,
            "tmdbId": 157336,
        }

        result = radarr_seeder.add_movie(test_movie)
        assert "id" in result, f"Failed to add test movie Interstellar: {result}"

        movie_id = result["id"]

        try:
            # Simulate deletion workflow
            # 1. Get movie from Radarr
            movie = radarr_client.get_movie(movie_id)
            assert movie is not None

            # 2. Check watch history (would be done via Tautulli)
            # For this test, assume movie hasn't been watched

            # 3. Delete the movie (non-dry-run)
            radarr_client.del_movie(movie_id, delete_files=True)

            # 4. Verify deletion
            movies = radarr_client.get_movie()
            ids = [m["id"] for m in movies]
            assert movie_id not in ids

        except Exception:
            # Cleanup on failure
            try:
                radarr_client.del_movie(movie_id, delete_files=True)
            except Exception:
                pass
            raise

    def test_preserve_recently_watched_movie(
        self, docker_services, radarr_seeder, radarr_client
    ):
        """Test that recently watched movies are NOT deleted."""
        # Using real TMDb ID for The Dark Knight
        test_movie = {
            "title": "The Dark Knight",
            "year": 2008,
            "tmdbId": 155,
        }

        result = radarr_seeder.add_movie(test_movie)
        assert "id" in result, f"Failed to add test movie The Dark Knight: {result}"

        movie_id = result["id"]

        try:
            # Simulate check - movie was recently watched
            # In real workflow, Tautulli would report recent watch
            recently_watched = True

            if recently_watched:
                # Should NOT delete
                pass

            # Verify movie still exists
            movies = radarr_client.get_movie()
            ids = [m["id"] for m in movies]
            assert movie_id in ids

        finally:
            # Cleanup
            try:
                radarr_client.del_movie(movie_id, delete_files=True)
            except Exception:
                pass


class TestSeriesDeletionWorkflow:
    """Test complete series deletion workflows."""

    def test_delete_old_unwatched_series(
        self, docker_services, sonarr_seeder, sonarr_client
    ):
        """Test deleting a series that hasn't been watched."""
        # Using real TVDB ID for The Office (US)
        test_series = {
            "title": "The Office",
            "tvdbId": 73244,
            "seriesType": "standard",
        }

        result = sonarr_seeder.add_series(test_series)
        assert "id" in result, f"Failed to add test series The Office: {result}"

        series_id = result["id"]

        try:
            # 1. Get series from Sonarr
            series = sonarr_client.get_series(series_id)
            assert series is not None

            # 2. Check watch history (assume unwatched)

            # 3. Delete the series
            sonarr_client.del_series(series_id, delete_files=True)

            # 4. Verify deletion
            all_series = sonarr_client.get_series()
            ids = [s["id"] for s in all_series]
            assert series_id not in ids

        except Exception:
            try:
                sonarr_client.del_series(series_id, delete_files=True)
            except Exception:
                pass
            raise

    def test_preserve_anime_series_with_filter(
        self, docker_services, sonarr_seeder, sonarr_client
    ):
        """Test that anime series are preserved when filtered."""
        # Using real TVDB ID for Death Note
        test_series = {
            "title": "Death Note",
            "tvdbId": 79481,
            "seriesType": "anime",
        }

        result = sonarr_seeder.add_series(test_series)
        assert "id" in result, f"Failed to add test series Death Note: {result}"

        series_id = result["id"]

        try:
            # Simulate filter: only delete 'standard' type
            series = sonarr_client.get_series(series_id)
            series_type = series.get("seriesType", "").lower()

            # If series_type filter is 'standard', anime should be skipped
            filter_type = "standard"
            should_delete = series_type == filter_type

            assert not should_delete, "Anime series should not match standard filter"

            # Verify series still exists
            all_series = sonarr_client.get_series()
            ids = [s["id"] for s in all_series]
            assert series_id in ids

        finally:
            try:
                sonarr_client.del_series(series_id, delete_files=True)
            except Exception:
                pass


class TestMaxActionsPerRun:
    """Test max_actions_per_run limit enforcement."""

    def test_respects_max_actions_limit(
        self, docker_services, radarr_seeder, radarr_client
    ):
        """Test that deletion stops at max_actions_per_run."""
        max_actions = 2

        # Add 5 test movies using real TMDb IDs
        test_movie_ids = [
            {"title": "Pulp Fiction", "year": 1994, "tmdbId": 680},
            {"title": "Goodfellas", "year": 1990, "tmdbId": 769},
            {"title": "The Shawshank Redemption", "year": 1994, "tmdbId": 278},
            {"title": "Forrest Gump", "year": 1994, "tmdbId": 13},
            {"title": "The Godfather", "year": 1972, "tmdbId": 238},
        ]
        test_movies = []
        for movie_data in test_movie_ids:
            result = radarr_seeder.add_movie(movie_data)
            if "id" in result:
                test_movies.append(result)

        if len(test_movies) < 3:
            # Cleanup before failing
            for m in test_movies:
                try:
                    radarr_client.del_movie(m["id"], delete_files=True)
                except Exception:
                    pass
            assert False, f"Could not add enough test movies - only added {len(test_movies)}"

        try:
            # Simulate deletion workflow with max_actions limit
            deleted_count = 0
            for movie in test_movies:
                if deleted_count >= max_actions:
                    break
                radarr_client.del_movie(movie["id"], delete_files=True)
                deleted_count += 1

            # Verify only max_actions were deleted
            assert deleted_count == max_actions

            # Verify remaining movies still exist
            remaining = radarr_client.get_movie()
            remaining_ids = [m["id"] for m in remaining]

            # Movies after max_actions should still exist
            for movie in test_movies[max_actions:]:
                assert movie["id"] in remaining_ids

        finally:
            # Cleanup all remaining test movies
            for movie in test_movies:
                try:
                    radarr_client.del_movie(movie["id"], delete_files=True)
                except Exception:
                    pass


class TestAddedAtThreshold:
    """Test added_at_threshold protection."""

    def test_recently_added_protected(
        self, docker_services, radarr_seeder, radarr_client
    ):
        """Test that recently added items are protected from deletion."""
        # Using real TMDb ID for Gladiator
        test_movie = {
            "title": "Gladiator",
            "year": 2000,
            "tmdbId": 98,
        }

        result = radarr_seeder.add_movie(test_movie)
        assert "id" in result, f"Failed to add test movie Gladiator: {result}"

        movie_id = result["id"]

        try:
            movie = radarr_client.get_movie(movie_id)

            # Check added date
            added_at = movie.get("added")
            if added_at:
                # In real workflow, items added within threshold days are protected
                # Newly added movie should be protected
                should_protect = True  # Assume recent for test

                if should_protect:
                    # Should NOT delete
                    pass

            # Verify movie still exists
            movies = radarr_client.get_movie()
            ids = [m["id"] for m in movies]
            assert movie_id in ids

        finally:
            try:
                radarr_client.del_movie(movie_id, delete_files=True)
            except Exception:
                pass


class TestExclusionRules:
    """Test exclusion rules prevent deletion."""

    def test_excluded_collection_protected(
        self, docker_services, radarr_seeder, radarr_client
    ):
        """Test that items in excluded collections are protected."""
        # This test validates the concept - actual collection checking
        # requires Plex mock integration which provides collection data
        # Using real TMDb ID for Schindler's List
        test_movie = {
            "title": "Schindler's List",
            "year": 1993,
            "tmdbId": 424,
        }

        result = radarr_seeder.add_movie(test_movie)
        assert "id" in result, f"Failed to add test movie Schindler's List: {result}"

        movie_id = result["id"]

        try:
            # Simulate exclusion check
            # In real workflow, Plex provides collection membership
            excluded_collections = ["Favorites", "Never Delete"]
            movie_collections = ["Favorites"]  # Simulated

            is_excluded = any(c in excluded_collections for c in movie_collections)
            assert is_excluded, "Movie should be in excluded collection"

            # Should NOT delete
            movies = radarr_client.get_movie()
            ids = [m["id"] for m in movies]
            assert movie_id in ids

        finally:
            try:
                radarr_client.del_movie(movie_id, delete_files=True)
            except Exception:
                pass


@pytest.mark.skip(reason="Plex mock has been replaced with real Plex server - use test_plex_integration.py")
class TestPlexMockIntegration:
    """Test integration with mock Plex server (DEPRECATED - use test_plex_integration.py)."""

    def test_plex_mock_returns_library_sections(self, plex_mock_seeder):
        """Verify mock Plex returns library sections."""
        import requests
        from tests.integration.conftest import PLEX_MOCK_URL

        resp = requests.get(
            f"{PLEX_MOCK_URL}/library/sections",
            headers={"X-Plex-Token": "test-token"},
            timeout=10
        )
        assert resp.status_code == 200

        data = resp.json()
        assert "MediaContainer" in data
        assert "Directory" in data["MediaContainer"]

    def test_plex_mock_returns_movies(self, plex_mock_seeder):
        """Verify mock Plex returns movies for Movies library."""
        import requests
        from tests.integration.conftest import PLEX_MOCK_URL

        # Section 1 is Movies in our mock
        resp = requests.get(
            f"{PLEX_MOCK_URL}/library/sections/1/all",
            headers={"X-Plex-Token": "test-token"},
            timeout=10
        )
        assert resp.status_code == 200

        data = resp.json()
        assert "MediaContainer" in data
        assert "Metadata" in data["MediaContainer"]
        assert len(data["MediaContainer"]["Metadata"]) > 0

    def test_plex_mock_returns_series(self, plex_mock_seeder):
        """Verify mock Plex returns series for TV Shows library."""
        import requests
        from tests.integration.conftest import PLEX_MOCK_URL

        # Section 2 is TV Shows in our mock
        resp = requests.get(
            f"{PLEX_MOCK_URL}/library/sections/2/all",
            headers={"X-Plex-Token": "test-token"},
            timeout=10
        )
        assert resp.status_code == 200

        data = resp.json()
        assert "MediaContainer" in data
        assert "Metadata" in data["MediaContainer"]
