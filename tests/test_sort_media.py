import pytest
from app.deleterr import sort_media 

@pytest.fixture
def media_list():
    return [
        {"sortTitle": "B", "sizeOnDisk": 5000, "year": 2020, "runtime": 120, "added": "2023-01-01", "ratings": {"imdb": {"value": 8}}, "statistics": {"seasonCount": 2, "totalEpisodeCount": 25}},
        {"sortTitle": "A", "sizeOnDisk": 2000, "year": 2019, "runtime": 110, "added": "2023-01-02", "ratings": {"tmdb": {"value": 7}}, "statistics": {"seasonCount": 3, "totalEpisodeCount": 30}},
        {"sortTitle": "C", "sizeOnDisk": 3000, "year": 2021, "runtime": 115, "added": "2023-01-03", "ratings": {"value": 9}, "statistics": {"seasonCount": 1, "totalEpisodeCount": 20}},
        {"sortTitle": "D", "sizeOnDisk": 1000, "year": 2018, "runtime": 125, "added": "2023-01-04", "ratings": {"imdb": {"value": 6}}, "statistics": {"seasonCount": 5, "totalEpisodeCount": 50}},
        {"sortTitle": "E", "sizeOnDisk": 6000, "year": 2022, "runtime": 130, "added": "2023-01-05", "ratings": {"value": 10}, "statistics": {"seasonCount": 4, "totalEpisodeCount": 40}},
    ]

@pytest.mark.parametrize("sort_field, sort_order, expected_order", [
    ("title", "asc", ["A", "B", "C", "D", "E"]),
    ("title", "desc", ["E", "D", "C", "B", "A"]),
    ("size", "asc", ["D", "A", "C", "B", "E"]),
    ("size", "desc", ["E", "B", "C", "A", "D"]),
    ("release_year", "asc", ["D", "A", "B", "C", "E"]),
    ("release_year", "desc", ["E", "C", "B", "A", "D"]),
    ("runtime", "asc", ["A", "C", "B", "D", "E"]),
    ("runtime", "desc", ["E", "D", "B", "C", "A"]),
    ("added_date", "asc", ["B", "A", "C", "D", "E"]),
    ("added_date", "desc", ["E", "D", "C", "A", "B"]),
    ("rating", "asc", ["D", "A", "B", "C", "E"]),
    ("rating", "desc", ["E", "C", "B", "A", "D"]),
    ("seasons", "asc", ["C", "B", "A", "E", "D"]),
    ("seasons", "desc", ["D", "E", "A", "B", "C"]),
    ("episodes", "asc", ["C", "B", "A", "E", "D"]),
    ("episodes", "desc", ["D", "E", "A", "B", "C"]),
])
def test_sort_media(media_list, sort_field, sort_order, expected_order):
    sort_config = {"field": sort_field, "order": sort_order}
    sorted_list = sort_media(media_list, sort_config)
    actual_order = [item["sortTitle"] for item in sorted_list]
    assert actual_order == expected_order