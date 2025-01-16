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