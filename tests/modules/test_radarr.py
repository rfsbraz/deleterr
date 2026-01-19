import pytest
from unittest.mock import MagicMock
from app.modules.radarr import DRadarr

@pytest.fixture
def dradarr():
    radarr = DRadarr("TestRadarr", "http://localhost:7878", "API_KEY")
    radarr.instance = MagicMock()
    return radarr

def test_get_movies(dradarr):
    dradarr.instance.get_movie.return_value = [{"title": "Test Movie"}]
    movies = dradarr.get_movies()
    assert movies == [{"title": "Test Movie"}]
    dradarr.instance.get_movie.assert_called_once()

def test_get_movie(dradarr):
    dradarr.instance.get_movie.return_value = {"title": "Test Movie"}
    movie = dradarr.get_movie(1)
    assert movie == {"title": "Test Movie"}
    dradarr.instance.get_movie.assert_called_once_with(1, tmdb=True)

def test_get_tags(dradarr):
    dradarr.instance.get_tag.return_value = [{"id": 1, "label": "Test Tag"}]
    tags = dradarr.get_tags()
    assert tags == [{"id": 1, "label": "Test Tag"}]
    dradarr.instance.get_tag.assert_called_once()

def test_get_quality_profiles(dradarr):
    dradarr.instance.get_quality_profile.return_value = [{"id": 1, "name": "Test Profile"}]
    profiles = dradarr.get_quality_profiles()
    assert profiles == [{"id": 1, "name": "Test Profile"}]
    dradarr.instance.get_quality_profile.assert_called_once()

def test_check_movie_has_tags(dradarr):
    dradarr.instance.get_tag.return_value = [{"id": 1, "label": "Test Tag"}]
    movie = {"tags": [1]}
    result = dradarr.check_movie_has_tags(movie, ["Test Tag"])
    assert result

def test_check_movie_has_quality_profiles(dradarr):
    dradarr.instance.get_quality_profile.return_value = [{"id": 1, "name": "Test Profile"}]
    movie = {"qualityProfileId": 1}
    result = dradarr.check_movie_has_quality_profiles(movie, ["Test Profile"])
    assert result

def test_get_disk_space(dradarr):
    dradarr.instance.get_diskspace.return_value = [{"path": "/mnt", "freeSpace": 1000000}]
    disk_space = dradarr.get_disk_space()
    assert disk_space == [{"path": "/mnt", "freeSpace": 1000000}]
    dradarr.instance.get_diskspace.assert_called_once()

def test_validate_connection_success(dradarr):
    dradarr.instance.get_health.return_value = True
    result = dradarr.validate_connection()
    assert result
    dradarr.instance.get_health.assert_called_once()

def test_validate_connection_failure(dradarr, monkeypatch):
    def mock_get_health():
        raise Exception("Connection error")
    monkeypatch.setattr(dradarr.instance, "get_health", mock_get_health)
    result = dradarr.validate_connection()
    assert not result


# Edge case tests for check_movie_has_tags
def test_check_movie_has_tags_no_match(dradarr):
    """Test when movie has tags but none match the filter."""
    dradarr.instance.get_tag.return_value = [
        {"id": 1, "label": "Tag1"},
        {"id": 2, "label": "Tag2"},
    ]
    movie = {"tags": [1]}  # Movie has Tag1
    result = dradarr.check_movie_has_tags(movie, ["Tag3"])  # Filter for Tag3
    assert not result


def test_check_movie_has_tags_empty_movie_tags(dradarr):
    """Test when movie has no tags."""
    dradarr.instance.get_tag.return_value = [{"id": 1, "label": "Test Tag"}]
    movie = {"tags": []}
    result = dradarr.check_movie_has_tags(movie, ["Test Tag"])
    assert not result


def test_check_movie_has_tags_missing_tags_key(dradarr):
    """Test when movie doesn't have a tags key."""
    dradarr.instance.get_tag.return_value = [{"id": 1, "label": "Test Tag"}]
    movie = {}  # No tags key at all
    result = dradarr.check_movie_has_tags(movie, ["Test Tag"])
    assert not result


def test_check_movie_has_tags_empty_filter(dradarr):
    """Test when filter list is empty."""
    dradarr.instance.get_tag.return_value = [{"id": 1, "label": "Test Tag"}]
    movie = {"tags": [1]}
    result = dradarr.check_movie_has_tags(movie, [])
    assert not result


def test_check_movie_has_tags_multiple_matches(dradarr):
    """Test when movie has multiple matching tags."""
    dradarr.instance.get_tag.return_value = [
        {"id": 1, "label": "Tag1"},
        {"id": 2, "label": "Tag2"},
        {"id": 3, "label": "Tag3"},
    ]
    movie = {"tags": [1, 2]}  # Movie has Tag1 and Tag2
    result = dradarr.check_movie_has_tags(movie, ["Tag1", "Tag2"])
    assert result


def test_check_movie_has_tags_partial_match(dradarr):
    """Test when movie has only some of the filtered tags."""
    dradarr.instance.get_tag.return_value = [
        {"id": 1, "label": "Tag1"},
        {"id": 2, "label": "Tag2"},
    ]
    movie = {"tags": [1]}  # Movie only has Tag1
    result = dradarr.check_movie_has_tags(movie, ["Tag1", "Tag2"])  # Filter wants both
    assert result  # Should match if ANY tag matches


# Edge case tests for check_movie_has_quality_profiles
def test_check_movie_has_quality_profiles_no_match(dradarr):
    """Test when movie quality profile doesn't match filter."""
    dradarr.instance.get_quality_profile.return_value = [
        {"id": 1, "name": "Profile1"},
        {"id": 2, "name": "Profile2"},
    ]
    movie = {"qualityProfileId": 1}
    result = dradarr.check_movie_has_quality_profiles(movie, ["Profile3"])
    assert not result


def test_check_movie_has_quality_profiles_empty_filter(dradarr):
    """Test when filter list is empty."""
    dradarr.instance.get_quality_profile.return_value = [{"id": 1, "name": "Profile1"}]
    movie = {"qualityProfileId": 1}
    result = dradarr.check_movie_has_quality_profiles(movie, [])
    assert not result


def test_check_movie_has_quality_profiles_missing_key(dradarr):
    """Test when movie doesn't have qualityProfileId."""
    dradarr.instance.get_quality_profile.return_value = [{"id": 1, "name": "Profile1"}]
    movie = {}  # No qualityProfileId
    result = dradarr.check_movie_has_quality_profiles(movie, ["Profile1"])
    assert not result


def test_check_movie_has_quality_profiles_multiple_filters(dradarr):
    """Test when filtering for multiple quality profiles."""
    dradarr.instance.get_quality_profile.return_value = [
        {"id": 1, "name": "Profile1"},
        {"id": 2, "name": "Profile2"},
    ]
    movie = {"qualityProfileId": 2}
    result = dradarr.check_movie_has_quality_profiles(movie, ["Profile1", "Profile2"])
    assert result


# Caching tests
def test_get_tags_caching(dradarr):
    """Test that tags are cached after first call."""
    dradarr.instance.get_tag.return_value = [{"id": 1, "label": "Test Tag"}]

    # First call should fetch from API
    tags1 = dradarr.get_tags()
    # Second call should use cache
    tags2 = dradarr.get_tags()

    assert tags1 == tags2
    # API should only be called once
    assert dradarr.instance.get_tag.call_count == 1


def test_get_quality_profiles_caching(dradarr):
    """Test that quality profiles are cached after first call."""
    dradarr.instance.get_quality_profile.return_value = [{"id": 1, "name": "Test Profile"}]

    # First call should fetch from API
    profiles1 = dradarr.get_quality_profiles()
    # Second call should use cache
    profiles2 = dradarr.get_quality_profiles()

    assert profiles1 == profiles2
    # API should only be called once
    assert dradarr.instance.get_quality_profile.call_count == 1


def test_check_movie_has_tags_case_insensitive(dradarr):
    """Test that tag matching is case-insensitive."""
    dradarr.instance.get_tag.return_value = [
        {"id": 1, "label": "4K-Protection"},
        {"id": 2, "label": "keep"},
    ]
    movie = {"tags": [1, 2]}

    # Test various case combinations
    assert dradarr.check_movie_has_tags(movie, ["4k-protection"])  # lowercase
    assert dradarr.check_movie_has_tags(movie, ["4K-PROTECTION"])  # uppercase
    assert dradarr.check_movie_has_tags(movie, ["KEEP"])  # uppercase
    assert dradarr.check_movie_has_tags(movie, ["Keep"])  # mixed case