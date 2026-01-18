"""
Script to create a pre-populated Tautulli database for integration tests.

Run this script to generate tautulli.db with test watch history data.
"""

import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "tautulli.db")


def create_database():
    """Create Tautulli database with test data."""
    # Remove existing database
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create minimal required tables
    # session_history stores watch events
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS session_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started INTEGER,
            stopped INTEGER,
            rating_key TEXT,
            parent_rating_key TEXT,
            grandparent_rating_key TEXT,
            media_type TEXT,
            user_id INTEGER DEFAULT 1,
            user TEXT DEFAULT 'TestUser',
            friendly_name TEXT DEFAULT 'TestUser',
            title TEXT,
            parent_title TEXT,
            grandparent_title TEXT,
            year INTEGER,
            section_id INTEGER DEFAULT 1
        )
    """)

    # session_history_metadata stores item metadata
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS session_history_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rating_key TEXT UNIQUE,
            parent_rating_key TEXT,
            grandparent_rating_key TEXT,
            guid TEXT,
            title TEXT,
            parent_title TEXT,
            grandparent_title TEXT,
            year INTEGER,
            media_type TEXT
        )
    """)

    # Calculate timestamps
    now = datetime.now()
    old_watch = now - timedelta(days=180)
    recent_watch = now - timedelta(days=10)

    # Insert watch history entries
    history_entries = [
        # Old unwatched movie - no entry (never watched)

        # Recently watched movie (rating_key 1002)
        {
            "started": int(recent_watch.timestamp()),
            "stopped": int((recent_watch + timedelta(hours=2)).timestamp()),
            "rating_key": "1002",
            "media_type": "movie",
            "title": "Recently Watched Movie",
            "year": 2021,
            "section_id": 1
        },

        # Old watched movie (rating_key 1005) - watched long ago
        {
            "started": int(old_watch.timestamp()),
            "stopped": int((old_watch + timedelta(hours=2)).timestamp()),
            "rating_key": "1005",
            "media_type": "movie",
            "title": "Old Watched Movie",
            "year": 2018,
            "section_id": 1
        },

        # Recently watched show (rating_key 2002)
        {
            "started": int(recent_watch.timestamp()),
            "stopped": int((recent_watch + timedelta(minutes=45)).timestamp()),
            "rating_key": "2002",
            "grandparent_rating_key": "2002",
            "media_type": "episode",
            "title": "Episode 1",
            "grandparent_title": "Recently Watched Show",
            "year": 2019,
            "section_id": 2
        },

        # Old watched show (rating_key 2005) - watched long ago
        {
            "started": int(old_watch.timestamp()),
            "stopped": int((old_watch + timedelta(minutes=45)).timestamp()),
            "rating_key": "2005",
            "grandparent_rating_key": "2005",
            "media_type": "episode",
            "title": "Episode 1",
            "grandparent_title": "Old Watched Show",
            "year": 2017,
            "section_id": 2
        },
    ]

    for entry in history_entries:
        cursor.execute("""
            INSERT INTO session_history
            (started, stopped, rating_key, parent_rating_key, grandparent_rating_key,
             media_type, title, parent_title, grandparent_title, year, section_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry["started"],
            entry["stopped"],
            entry["rating_key"],
            entry.get("parent_rating_key", ""),
            entry.get("grandparent_rating_key", ""),
            entry["media_type"],
            entry["title"],
            entry.get("parent_title", ""),
            entry.get("grandparent_title", ""),
            entry["year"],
            entry["section_id"]
        ))

    # Insert metadata entries
    metadata_entries = [
        {
            "rating_key": "1001",
            "guid": "plex://movie/1001",
            "title": "Old Unwatched Movie",
            "year": 2020,
            "media_type": "movie"
        },
        {
            "rating_key": "1002",
            "guid": "plex://movie/1002",
            "title": "Recently Watched Movie",
            "year": 2021,
            "media_type": "movie"
        },
        {
            "rating_key": "1003",
            "guid": "plex://movie/1003",
            "title": "Movie In Excluded Collection",
            "year": 2019,
            "media_type": "movie"
        },
        {
            "rating_key": "1004",
            "guid": "plex://movie/1004",
            "title": "Recently Added Movie",
            "year": 2023,
            "media_type": "movie"
        },
        {
            "rating_key": "2001",
            "guid": "plex://show/2001",
            "title": "Old Unwatched Show",
            "year": 2018,
            "media_type": "show"
        },
        {
            "rating_key": "2002",
            "guid": "plex://show/2002",
            "title": "Recently Watched Show",
            "year": 2019,
            "media_type": "show"
        },
        {
            "rating_key": "2003",
            "guid": "plex://show/2003",
            "title": "Anime Series",
            "year": 2020,
            "media_type": "show"
        },
    ]

    for entry in metadata_entries:
        cursor.execute("""
            INSERT INTO session_history_metadata
            (rating_key, parent_rating_key, grandparent_rating_key, guid, title,
             parent_title, grandparent_title, year, media_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry["rating_key"],
            entry.get("parent_rating_key", ""),
            entry.get("grandparent_rating_key", ""),
            entry["guid"],
            entry["title"],
            entry.get("parent_title", ""),
            entry.get("grandparent_title", ""),
            entry["year"],
            entry["media_type"]
        ))

    conn.commit()
    conn.close()

    print(f"Created Tautulli database at: {DB_PATH}")


if __name__ == "__main__":
    create_database()
