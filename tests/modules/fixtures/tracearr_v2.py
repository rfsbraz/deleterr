"""Schema-accurate Tracearr Public API v2 fixtures.

Shapes follow the official openapi-v2.json from Tracearr v3.2.1
(https://github.com/connorgallopo/Tracearr/releases/download/v3.2.1/openapi-v2.json).
Field names and types are taken from that document; values are invented only
as placeholder data, not as new keys or types.
"""

from copy import deepcopy

SERVER_ID = "5c1a4c1e-0b2d-4f6a-9d3e-2b7c8f9a1d20"
MOVIE_MEDIA_ID = "7d2e1c0b-4a93-4f18-9c6d-1b0e8f7a6543"
SHOW_MEDIA_ID = "11111111-2222-4333-8444-555555555555"
EPISODE_MEDIA_ID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
USER_ID = "0f1e2d3c-4b5a-4678-89ab-0c1d2e3f4a5b"
SERVER_USER_ID = "9a8b7c6d-5e4f-4012-8345-678901234567"

# Official Server example from the v3.2.1 OpenAPI document, plus a second server.
SERVERS_RESPONSE = {
    "data": [
        {
            "server_id": SERVER_ID,
            "server_name": "Attic",
            "status": "up",
            "reason": None,
            "server_type": "plex",
            "historical": False,
            "active_streams": 2,
            "version": "1.41.0",
        },
        {
            "server_id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
            "server_name": "Jellyfin",
            "status": "up",
            "reason": None,
            "server_type": "jellyfin",
            "historical": False,
            "active_streams": 0,
            "version": "10.10.0",
        },
    ],
    "tracearr_version": "3.2.1",
}


def history_user(**overrides):
    user = {
        "id": USER_ID,
        "server_user_id": SERVER_USER_ID,
        "username": "john_doe",
        "thumb_url": None,
        "avatar_url": None,
    }
    user.update(overrides)
    return user


def history_record(**overrides):
    """A complete HistoryRecord with every required field present."""
    record = {
        "id": "bbbbbbbb-cccc-4ddd-8eee-ffffffffffff",
        "server_id": SERVER_ID,
        "server_name": "Attic",
        "server_type": "plex",
        "state": "stopped",
        "media_type": "movie",
        "media_title": "Inception",
        "show_title": None,
        "season_number": None,
        "episode_number": None,
        "year": 2010,
        "artist_name": None,
        "album_name": None,
        "track_number": None,
        "disc_number": None,
        "thumb_path": None,
        "poster_url": None,
        "duration_ms": 7200000,
        "progress_ms": 8500000,
        "total_duration_ms": 8880000,
        "percent_complete": 95.8,
        "started_at": "2026-08-30T20:00:00.000Z",
        "stopped_at": "2026-08-30T22:00:00.000Z",
        "watched": True,
        "segment_count": 1,
        "device": "Apple TV",
        "player": "Plex for Apple TV",
        "product": "Plex for Apple TV",
        "platform": "tvOS",
        "is_transcode": False,
        "video_decision": "directplay",
        "audio_decision": "directplay",
        "bitrate": 8000,
        "source_video_codec": "hevc",
        "source_audio_codec": "aac",
        "source_audio_channels": 6,
        "source_video_width": 1920,
        "source_video_height": 1080,
        "source_video_details": {},
        "source_audio_details": {},
        "stream_video_codec": "hevc",
        "stream_audio_codec": "aac",
        "stream_video_details": {},
        "stream_audio_details": {},
        "transcode_info": {},
        "subtitle_info": {},
        "resolution": "1080p",
        "source_video_codec_display": "HEVC",
        "source_audio_codec_display": "AAC",
        "audio_channels_display": "5.1",
        "stream_video_codec_display": "HEVC",
        "stream_audio_codec_display": "AAC",
        "media_id": MOVIE_MEDIA_ID,
        "show_media_id": None,
        "imdb_id": "tt1375666",
        "tmdb_id": 27205,
        "tvdb_id": None,
        "rating_key": "12345",
        "parent_rating_key": None,
        "grandparent_rating_key": None,
        "library_id": "1",
        "genres": ["Action", "Science Fiction"],
        "reference_id": "bbbbbbbb-cccc-4ddd-8eee-ffffffffffff",
        "user": history_user(),
    }
    record.update(overrides)
    return record


def history_response(records, next_cursor=None, page_size=100):
    return {
        "data": [deepcopy(r) for r in records],
        "meta": {"nextCursor": next_cursor, "pageSize": page_size},
    }


def watchers_response(usernames, media_id=MOVIE_MEDIA_ID, media_type="movie"):
    watchers = []
    for i, name in enumerate(usernames):
        if isinstance(name, dict):
            user = {
                "server_user_id": name.get("server_user_id", SERVER_USER_ID),
                "user_id": name.get("user_id", USER_ID),
                "username": name.get("username"),
                "identity_name": name.get("identity_name"),
            }
        else:
            user = {
                "server_user_id": SERVER_USER_ID,
                "user_id": USER_ID,
                "username": name,
                "identity_name": name,
            }
        watchers.append(
            {
                "user": user,
                "plays": 1,
                "watch_time_ms": 7200000,
                "completion_pct": 96.4,
                "last_watched_day": "2026-08-30",
                "distinct_episodes_watched": None,
            }
        )
    return {
        "media_id": media_id,
        "media_type": media_type,
        "window": "all_time",
        "watchers": watchers,
    }


MOVIE_HISTORY = history_record()

EPISODE_HISTORY = history_record(
    id="cccccccc-dddd-4eee-8fff-000000000000",
    reference_id="cccccccc-dddd-4eee-8fff-000000000000",
    media_type="episode",
    media_title="Pilot",
    show_title="Breaking Bad",
    season_number=1,
    episode_number=1,
    year=2008,
    started_at="2026-07-01T18:00:00.000Z",
    stopped_at="2026-07-01T18:45:00.000Z",
    media_id=EPISODE_MEDIA_ID,
    show_media_id=SHOW_MEDIA_ID,
    imdb_id=None,
    tmdb_id=None,
    tvdb_id=349232,
    rating_key="9001",
    parent_rating_key="9000",
    grandparent_rating_key="456",
    library_id="2",
)
