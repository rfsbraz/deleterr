from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from app.media_cleaner import sort_media, get_plex_item_for_sort
from app.schema import SortConfig


@pytest.fixture
def media_list():
    return [
        {
            "sortTitle": "B",
            "title": "B Movie",
            "sizeOnDisk": 5000,
            "year": 2020,
            "runtime": 120,
            "added": "2023-01-01",
            "ratings": {"imdb": {"value": 8}},
            "statistics": {"seasonCount": 2, "totalEpisodeCount": 25},
            "tmdbId": 1001,
        },
        {
            "sortTitle": "A",
            "title": "A Movie",
            "sizeOnDisk": 2000,
            "year": 2019,
            "runtime": 110,
            "added": "2023-01-02",
            "ratings": {"tmdb": {"value": 7}},
            "statistics": {"seasonCount": 3, "totalEpisodeCount": 30},
            "tmdbId": 1002,
        },
        {
            "sortTitle": "C",
            "title": "C Movie",
            "sizeOnDisk": 3000,
            "year": 2021,
            "runtime": 115,
            "added": "2023-01-03",
            "ratings": {"value": 9},
            "statistics": {"seasonCount": 1, "totalEpisodeCount": 20},
            "tmdbId": 1003,
        },
        {
            "sortTitle": "D",
            "title": "D Movie",
            "sizeOnDisk": 1000,
            "year": 2018,
            "runtime": 125,
            "added": "2023-01-04",
            "ratings": {"imdb": {"value": 6}},
            "statistics": {"seasonCount": 5, "totalEpisodeCount": 50},
            "tmdbId": 1004,
        },
        {
            "sortTitle": "E",
            "title": "E Movie",
            "sizeOnDisk": 6000,
            "year": 2022,
            "runtime": 130,
            "added": "2023-01-05",
            "ratings": {"value": 10},
            "statistics": {"seasonCount": 4, "totalEpisodeCount": 40},
            "tmdbId": 1005,
        },
    ]


@pytest.mark.parametrize(
    "sort_field, sort_order, expected_order",
    [
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
    ],
)
def test_sort_media(media_list, sort_field, sort_order, expected_order):
    sort_config = {"field": sort_field, "order": sort_order}
    sorted_list = sort_media(media_list, sort_config)
    actual_order = [item["sortTitle"] for item in sorted_list]
    assert actual_order == expected_order


# Tests for secondary/multi-level sorting
class TestMultiLevelSort:
    """Tests for comma-separated multi-level sorting."""

    def test_secondary_sort_same_order(self):
        """Test sorting by two fields with same order (desc)."""
        # Items with same year to test secondary sort
        media = [
            {"sortTitle": "A", "title": "A", "year": 2020, "sizeOnDisk": 1000, "tmdbId": 1},
            {"sortTitle": "B", "title": "B", "year": 2020, "sizeOnDisk": 3000, "tmdbId": 2},
            {"sortTitle": "C", "title": "C", "year": 2019, "sizeOnDisk": 2000, "tmdbId": 3},
            {"sortTitle": "D", "title": "D", "year": 2020, "sizeOnDisk": 2000, "tmdbId": 4},
        ]
        # Sort by year desc, then size desc
        sort_config = {"field": "release_year,size", "order": "desc"}
        sorted_list = sort_media(media, sort_config)
        titles = [item["sortTitle"] for item in sorted_list]
        # 2020 items first (B=3000, D=2000, A=1000), then 2019 (C=2000)
        assert titles == ["B", "D", "A", "C"]

    def test_secondary_sort_mixed_orders(self):
        """Test sorting by two fields with different orders (desc, asc)."""
        media = [
            {"sortTitle": "A", "title": "A", "year": 2020, "sizeOnDisk": 1000, "tmdbId": 1},
            {"sortTitle": "B", "title": "B", "year": 2020, "sizeOnDisk": 3000, "tmdbId": 2},
            {"sortTitle": "C", "title": "C", "year": 2019, "sizeOnDisk": 2000, "tmdbId": 3},
            {"sortTitle": "D", "title": "D", "year": 2020, "sizeOnDisk": 2000, "tmdbId": 4},
        ]
        # Sort by year desc, then size asc
        sort_config = {"field": "release_year,size", "order": "desc,asc"}
        sorted_list = sort_media(media, sort_config)
        titles = [item["sortTitle"] for item in sorted_list]
        # 2020 items first (A=1000, D=2000, B=3000), then 2019 (C=2000)
        assert titles == ["A", "D", "B", "C"]

    def test_single_order_applied_to_multiple_fields(self):
        """Test that a single order is applied to all fields when only one is given."""
        media = [
            {"sortTitle": "A", "title": "A", "year": 2020, "sizeOnDisk": 1000, "tmdbId": 1},
            {"sortTitle": "B", "title": "B", "year": 2020, "sizeOnDisk": 3000, "tmdbId": 2},
            {"sortTitle": "C", "title": "C", "year": 2019, "sizeOnDisk": 2000, "tmdbId": 3},
        ]
        # Sort by year asc, then size asc (single 'asc' applies to both)
        sort_config = {"field": "release_year,size", "order": "asc"}
        sorted_list = sort_media(media, sort_config)
        titles = [item["sortTitle"] for item in sorted_list]
        # 2019 first (C), then 2020 by size (A=1000, B=3000)
        assert titles == ["C", "A", "B"]

    def test_three_level_sort(self):
        """Test sorting by three fields."""
        media = [
            {"sortTitle": "A", "title": "A", "year": 2020, "runtime": 120, "sizeOnDisk": 1000, "tmdbId": 1},
            {"sortTitle": "B", "title": "B", "year": 2020, "runtime": 120, "sizeOnDisk": 2000, "tmdbId": 2},
            {"sortTitle": "C", "title": "C", "year": 2020, "runtime": 100, "sizeOnDisk": 3000, "tmdbId": 3},
            {"sortTitle": "D", "title": "D", "year": 2019, "runtime": 120, "sizeOnDisk": 1000, "tmdbId": 4},
        ]
        # Sort by year desc, runtime desc, size asc
        sort_config = {"field": "release_year,runtime,size", "order": "desc,desc,asc"}
        sorted_list = sort_media(media, sort_config)
        titles = [item["sortTitle"] for item in sorted_list]
        # 2020 first: runtime 120 (A=1000, B=2000), runtime 100 (C=3000)
        # Then 2019: D
        assert titles == ["A", "B", "C", "D"]


# Tests for last_watched sort field
class TestLastWatchedSort:
    """Tests for the last_watched sort field."""

    @pytest.fixture
    def plex_items_and_activity(self):
        """Create mock Plex items and activity data for testing."""
        # Create mock Plex items
        plex_item_a = Mock()
        plex_item_a.guid = "plex://movie/a"
        plex_item_a.guids = [Mock(id="tmdb://1001")]
        plex_item_a.title = "A Movie"
        plex_item_a.year = 2020

        plex_item_b = Mock()
        plex_item_b.guid = "plex://movie/b"
        plex_item_b.guids = [Mock(id="tmdb://1002")]
        plex_item_b.title = "B Movie"
        plex_item_b.year = 2019

        plex_item_c = Mock()
        plex_item_c.guid = "plex://movie/c"
        plex_item_c.guids = [Mock(id="tmdb://1003")]
        plex_item_c.title = "C Movie"
        plex_item_c.year = 2021

        # Create GUID-item pairs (format used by the actual code)
        plex_guid_item_pair = [
            (["plex://movie/a", "tmdb://1001"], plex_item_a),
            (["plex://movie/b", "tmdb://1002"], plex_item_b),
            (["plex://movie/c", "tmdb://1003"], plex_item_c),
        ]

        # Activity data: A watched 10 days ago, B watched 30 days ago, C never watched
        activity_data = {
            "plex://movie/a": {
                "title": "A Movie",
                "year": 2020,
                "last_watched": datetime.now() - timedelta(days=10),
            },
            "plex://movie/b": {
                "title": "B Movie",
                "year": 2019,
                "last_watched": datetime.now() - timedelta(days=30),
            },
        }

        media_list = [
            {"sortTitle": "A", "title": "A Movie", "year": 2020, "tmdbId": 1001, "sizeOnDisk": 1000},
            {"sortTitle": "B", "title": "B Movie", "year": 2019, "tmdbId": 1002, "sizeOnDisk": 2000},
            {"sortTitle": "C", "title": "C Movie", "year": 2021, "tmdbId": 1003, "sizeOnDisk": 3000},
        ]

        return media_list, activity_data, plex_guid_item_pair

    def test_last_watched_desc_unwatched_first(self, plex_items_and_activity):
        """Test that unwatched items come first with desc order."""
        media_list, activity_data, plex_guid_item_pair = plex_items_and_activity

        sort_config = {"field": "last_watched", "order": "desc"}
        sorted_list = sort_media(media_list, sort_config, activity_data, plex_guid_item_pair)
        titles = [item["sortTitle"] for item in sorted_list]

        # C is unwatched - unwatched ALWAYS come first regardless of order
        # desc order among watched: 30 > 10, so B before A
        assert titles == ["C", "B", "A"]

    def test_last_watched_asc_unwatched_still_first(self, plex_items_and_activity):
        """Test that unwatched items STILL come first even with asc order.

        This is intentional behavior: unwatched items should be prioritized
        for deletion before recently-watched items, regardless of order setting.
        The order setting only affects how watched items are sorted among themselves.
        """
        media_list, activity_data, plex_guid_item_pair = plex_items_and_activity

        sort_config = {"field": "last_watched", "order": "asc"}
        sorted_list = sort_media(media_list, sort_config, activity_data, plex_guid_item_pair)
        titles = [item["sortTitle"] for item in sorted_list]

        # C is unwatched - unwatched ALWAYS come first regardless of order
        # asc order among watched: 10 < 30, so A before B
        assert titles == ["C", "A", "B"]

    def test_last_watched_with_secondary_sort(self, plex_items_and_activity):
        """Test last_watched combined with secondary sort field."""
        # Add another unwatched item to test secondary sort among unwatched
        media_list, activity_data, plex_guid_item_pair = plex_items_and_activity

        # Add D: unwatched, larger size
        plex_item_d = Mock()
        plex_item_d.guid = "plex://movie/d"
        plex_item_d.guids = [Mock(id="tmdb://1004")]
        plex_item_d.title = "D Movie"
        plex_item_d.year = 2022

        plex_guid_item_pair.append((["plex://movie/d", "tmdb://1004"], plex_item_d))
        media_list.append({
            "sortTitle": "D", "title": "D Movie", "year": 2022,
            "tmdbId": 1004, "sizeOnDisk": 5000
        })

        # Sort by last_watched desc, then size desc
        sort_config = {"field": "last_watched,size", "order": "desc"}
        sorted_list = sort_media(media_list, sort_config, activity_data, plex_guid_item_pair)
        titles = [item["sortTitle"] for item in sorted_list]

        # Both C and D are unwatched (infinity), so they tie on last_watched
        # Secondary sort by size desc: D=5000 > C=3000
        # Then B=30 days, A=10 days
        assert titles == ["D", "C", "B", "A"]

    def test_last_watched_without_activity_data(self):
        """Test last_watched gracefully handles missing activity data."""
        media_list = [
            {"sortTitle": "A", "title": "A", "year": 2020, "tmdbId": 1001, "sizeOnDisk": 3000},
            {"sortTitle": "B", "title": "B", "year": 2019, "tmdbId": 1002, "sizeOnDisk": 1000},
        ]

        # Without activity data, all items should be treated as unwatched (infinity)
        # So secondary sort (or title) should determine order
        sort_config = {"field": "last_watched,size", "order": "desc"}
        sorted_list = sort_media(media_list, sort_config, None, None)
        titles = [item["sortTitle"] for item in sorted_list]

        # All have infinity days, so sorted by size desc: A=3000 > B=1000
        assert titles == ["A", "B"]


# Tests for SortConfig validation
class TestSortConfigValidation:
    """Tests for SortConfig schema validation."""

    def test_valid_single_field(self):
        """Test that single valid field passes validation."""
        config = SortConfig(field="title", order="asc")
        assert config.field == "title"
        assert config.order == "asc"

    def test_valid_last_watched_field(self):
        """Test that last_watched is a valid sort field."""
        config = SortConfig(field="last_watched", order="desc")
        assert config.field == "last_watched"

    def test_valid_comma_separated_fields(self):
        """Test that comma-separated fields pass validation."""
        config = SortConfig(field="last_watched,size", order="desc,asc")
        assert config.field == "last_watched,size"
        assert config.order == "desc,asc"

    def test_invalid_field_raises_error(self):
        """Test that invalid field raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            SortConfig(field="invalid_field", order="asc")
        assert "Invalid sort field: invalid_field" in str(exc_info.value)

    def test_invalid_order_raises_error(self):
        """Test that invalid order raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            SortConfig(field="title", order="invalid")
        assert "Invalid sort order: invalid" in str(exc_info.value)

    def test_invalid_field_in_list_raises_error(self):
        """Test that invalid field in comma-separated list raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            SortConfig(field="title,bogus,size", order="desc")
        assert "Invalid sort field: bogus" in str(exc_info.value)

    def test_whitespace_handling(self):
        """Test that whitespace around fields/orders is trimmed."""
        config = SortConfig(field=" last_watched , size ", order=" desc , asc ")
        # Validation should pass (whitespace is trimmed)
        assert "last_watched" in config.field
        assert "size" in config.field


# Tests for get_plex_item_for_sort helper
class TestGetPlexItemForSort:
    """Tests for the get_plex_item_for_sort helper function."""

    def test_match_by_tmdb_id(self):
        """Test matching by TMDB ID."""
        plex_item = Mock()
        plex_item.title = "Some Movie"
        plex_item.year = 2020

        plex_guid_item_pair = [
            (["plex://movie/1", "tmdb://12345"], plex_item),
        ]
        media_data = {"title": "Different Title", "year": 2019, "tmdbId": 12345}

        result = get_plex_item_for_sort(media_data, plex_guid_item_pair)
        assert result == plex_item

    def test_match_by_imdb_id(self):
        """Test matching by IMDB ID."""
        plex_item = Mock()
        plex_item.title = "Some Movie"
        plex_item.year = 2020

        plex_guid_item_pair = [
            (["plex://movie/1", "imdb://tt1234567"], plex_item),
        ]
        media_data = {"title": "Different Title", "year": 2019, "imdbId": "tt1234567"}

        result = get_plex_item_for_sort(media_data, plex_guid_item_pair)
        assert result == plex_item

    def test_match_by_tvdb_id(self):
        """Test matching by TVDB ID."""
        plex_item = Mock()
        plex_item.title = "Some Show"
        plex_item.year = 2020

        plex_guid_item_pair = [
            (["plex://show/1", "tvdb://98765"], plex_item),
        ]
        media_data = {"title": "Different Title", "year": 2019, "tvdbId": 98765}

        result = get_plex_item_for_sort(media_data, plex_guid_item_pair)
        assert result == plex_item

    def test_fallback_to_title_year_match(self):
        """Test fallback to title+year matching when no GUID match."""
        plex_item = Mock()
        plex_item.title = "The Movie"
        plex_item.year = 2020

        plex_guid_item_pair = [
            (["plex://movie/1", "tmdb://99999"], plex_item),
        ]
        # No matching IDs, but title and year match
        media_data = {"title": "the movie", "year": 2020}

        result = get_plex_item_for_sort(media_data, plex_guid_item_pair)
        assert result == plex_item

    def test_title_year_match_with_tolerance(self):
        """Test title+year matching allows 2 year tolerance."""
        plex_item = Mock()
        plex_item.title = "The Movie"
        plex_item.year = 2020

        plex_guid_item_pair = [
            (["plex://movie/1", "tmdb://99999"], plex_item),
        ]
        # Year is off by 1, should still match
        media_data = {"title": "the movie", "year": 2021}

        result = get_plex_item_for_sort(media_data, plex_guid_item_pair)
        assert result == plex_item

    def test_no_match_returns_none(self):
        """Test that no match returns None."""
        plex_item = Mock()
        plex_item.title = "Different Movie"
        plex_item.year = 2015

        plex_guid_item_pair = [
            (["plex://movie/1", "tmdb://99999"], plex_item),
        ]
        media_data = {"title": "Some Other Movie", "year": 2020, "tmdbId": 11111}

        result = get_plex_item_for_sort(media_data, plex_guid_item_pair)
        assert result is None
