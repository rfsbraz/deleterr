# encoding: utf-8
"""
Bootstrap script for Plex integration testing.

This script:
1. Creates stub media files for Plex to scan
2. Waits for Plex to be ready
3. Creates library sections
4. Triggers library scans
5. Waits for scanning to complete

Based on python-plexapi's bootstrap approach.
"""

import base64
import os
import shutil
import time
from pathlib import Path
from typing import Optional

import requests

# Minimal valid MP4 file that Plex can scan
# Generated with: ffmpeg -f lavfi -i color=c=black:s=64x64:d=1 -c:v libx264 -t 1 stub.mp4
# Then base64 encoded. This is a 1-second black video at 64x64 resolution.
STUB_VIDEO_B64 = (
    "AAAAGGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDEAAAAIZnJlZQAAAmttZGF0AAACXwYF//9b"
    "3EXpvebZSLeWLNgg2SPu73gyNjQgLSBjb3JlIDE2NCAtIEguMjY0L01QRUctNCBBVkMgY29kZWMg"
    "LSBDb3B5bGVmdCAyMDAzLTIwMjMgLSBodHRwOi8vd3d3LnZpZGVvbGFuLm9yZy94MjY0Lmh0bWwg"
    "LSBvcHRpb25zOiBjYWJhYz0xIHJlZj0zIGRlYmxvY2s9MTowOjAgYW5hbHlzZT0weDM6MHgxMTMg"
    "bWU9aGV4IHN1Ym1lPTcgcHN5PTEgcHN5X3JkPTEuMDA6MC4wMCBtaXhlZF9yZWY9MSBtZV9yYW5n"
    "ZT0xNiBjaHJvbWFfbWU9MSB0cmVsbGlzPTEgOHg4ZGN0PTEgY3FtPTAgZGVhZHpvbmU9MjEsMTEg"
    "ZmFzdF9wc2tpcD0xIGNocm9tYV9xcF9vZmZzZXQ9LTIgdGhyZWFkcz0xMiBsb29rYWhlYWRfdGhy"
    "ZWFkcz0yIHNsaWNlZF90aHJlYWRzPTAgbnI9MCBkZWNpbWF0ZT0xIGludGVybGFjZWQ9MCBibHVy"
    "YXlfY29tcGF0PTAgY29uc3RyYWluZWRfaW50cmE9MCBiZnJhbWVzPTMgYl9weXJhbWlkPTIgYl9h"
    "ZGFwdD0xIGJfYmlhcz0wIGRpcmVjdD0xIHdlaWdodGI9MSBvcGVuX2dvcD0wIHdlaWdodHA9MiBr"
    "ZXlpbnQ9MjUwIGtleWludF9taW49MjUgc2NlbmVjdXQ9NDAgaW50cmFfcmVmcmVzaD0wIHJjX2xv"
    "b2thaGVhZD00MCByYz1jcmYgbWJ0cmVlPTEgY3JmPTIzLjAgcWNvbXA9MC42MCBxcG1pbj0wIHFw"
    "bWF4PTY5IHFwc3RlcD00IGlwX3JhdGlvPTEuNDAgYXE9MToxLjAAgAAAAwRBniBsQz32AAAAAAAA"
    "AAAAAAAeQZokbEFf/rUqgAAAAwAAAwAAAwAAJLAAAAMAAAMAAAMAU0GaQWxBP/61KoAAAAMAAAAA"
    "AAAAAAAAAAAAAGxtdmhkAAAAAAAAAAAAAAAAAAAD6AAAAGQAAQAAAQAAAAAAAAAAAAAAAAEAAdJt"
    "b292AAAAbG12aGQAAAAAAAAAAAAAAAAAAAPoAAAAZAABAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAB"
    "AAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAA"
    "AGR0cmFrAAAAXHRraGQAAAADAAAAAAAAAAAAAAABAAAAAAAABGQAAAAAAAAAAAAAAAAAAAAAAAEA"
    "AAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAQAAAAAAQAAAAEAAAAAA"
    "AR5tZGlhAAAAIG1kaGQAAAAAAAAAAAAAAAAAAKxEAAAQAFXEAAAAAAAtaGRscgAAAAAAAAAAdmlk"
    "ZQAAAAAAAAAAAAAAAFZpZGVvSGFuZGxlcgAAAADJbWluZgAAABR2bWhkAAAAAQAAAAAAAAAAACRk"
    "aW5mAAAAHGRyZWYAAAAAAAAAAQAAAAx1cmwgAAAAAQAAAIlzdGJsAAAAZXN0c2QAAAAAAAAAAQAA"
    "AFVhdmMxAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAEAAQABIAAAASAAAAAAAAAABAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGP//AAAAH2F2Y0MBZAAK/+EAGGdkAAqs2UCQL/lgLUCc"
    "gQAAAwADAAADAAfQ8UJZYAEABWjr7sMgAAAAGHN0dHMAAAAAAAAAAQAAAAIAAAABAAAAFHN0c3MA"
    "AAAAAAAAAQAAAAEAAAAcc3RzYwAAAAAAAAABAAAAAQAAAAIAAAABAAAAHHN0c3oAAAAAAAAAAAIA"
    "AAJfAAAAAwAAABRzdGNvAAAAAAAAAAEAAAAw"
)

# Test media content - IDs match JustWatch cache for integration testing
# Movies use TMDB IDs, TV shows use TVDB IDs
MOVIES = [
    # Matches JustWatch cache - available on Max
    {"title": "The Matrix", "year": 1999, "tmdb_id": 603, "imdb_id": "tt0133093"},
    # Matches JustWatch cache - available on Max
    {"title": "Dune", "year": 2021, "tmdb_id": 438631, "imdb_id": "tt1160419"},
    # Matches JustWatch cache - available on Criterion Channel
    {"title": "The Seventh Seal", "year": 1957, "tmdb_id": 490, "imdb_id": "tt0050976"},
    # Matches JustWatch cache - no streaming offers (for deletion candidate tests)
    {"title": "Test Movie", "year": 2020, "tmdb_id": 999999, "imdb_id": "tt9999999"},
    # Not in cache - will require API call or be treated as unknown
    {"title": "Recently Added Movie", "year": 2023, "tmdb_id": 553},
]

TV_SHOWS = [
    {
        # Matches JustWatch cache - Breaking Bad on Netflix
        "title": "Breaking Bad",
        "year": 2008,
        "tvdb_id": 81189,
        "imdb_id": "tt0903747",
        "seasons": {1: 7, 2: 13},  # Partial seasons for faster tests
    },
    {
        # Matches JustWatch cache - Better Call Saul on Netflix/AMC+
        "title": "Better Call Saul",
        "year": 2015,
        "tvdb_id": 8,
        "imdb_id": "tt3032476",
        "seasons": {1: 10},
    },
    {
        # Not in cache - for deletion candidate tests
        "title": "Unknown Show",
        "year": 2020,
        "tvdb_id": 999999,
        "seasons": {1: 6},
    },
]


def get_stub_video() -> bytes:
    """Decode and return the stub video file."""
    return base64.b64decode(STUB_VIDEO_B64.replace("\n", ""))


def create_stub_file(path: Path) -> None:
    """Create a stub video file at the given path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(get_stub_video())


def setup_movies(media_path: Path) -> int:
    """Create movie stub files."""
    movies_path = media_path / "movies"
    movies_path.mkdir(parents=True, exist_ok=True)

    count = 0
    for movie in MOVIES:
        filename = f"{movie['title']} ({movie['year']}).mp4"
        filepath = movies_path / filename
        if not filepath.exists():
            create_stub_file(filepath)
            print(f"  Created: {filename}")
        count += 1

    return count


def setup_tvshows(media_path: Path) -> int:
    """Create TV show stub files."""
    tvshows_path = media_path / "tvshows"
    tvshows_path.mkdir(parents=True, exist_ok=True)

    count = 0
    for show in TV_SHOWS:
        show_path = tvshows_path / show["title"]
        show_path.mkdir(parents=True, exist_ok=True)

        for season, episodes in show["seasons"].items():
            season_path = show_path / f"Season {season:02d}"
            season_path.mkdir(parents=True, exist_ok=True)

            for episode in range(1, episodes + 1):
                filename = f"{show['title']} - S{season:02d}E{episode:02d}.mp4"
                filepath = season_path / filename
                if not filepath.exists():
                    create_stub_file(filepath)
                count += 1

    return count


def setup_media(media_path: Path) -> dict:
    """Set up all media files."""
    print("Setting up media files...")
    movie_count = setup_movies(media_path)
    print(f"  Movies: {movie_count}")

    show_count = setup_tvshows(media_path)
    print(f"  TV Show episodes: {show_count}")

    return {"movies": movie_count, "shows": show_count}


def wait_for_plex(plex_url: str, timeout: int = 120) -> bool:
    """Wait for Plex to be ready."""
    print(f"Waiting for Plex at {plex_url}...")
    start = time.time()

    while time.time() - start < timeout:
        try:
            resp = requests.get(f"{plex_url}/identity", timeout=5)
            if resp.status_code == 200:
                print("  Plex is ready!")
                return True
        except requests.RequestException:
            pass
        time.sleep(2)

    return False


def get_plex_token(plex_url: str) -> Optional[str]:
    """Get a token for an unclaimed Plex server."""
    # For unclaimed servers, we can use any token
    # The server will accept requests without authentication
    try:
        resp = requests.get(f"{plex_url}/identity", timeout=5)
        if resp.status_code == 200:
            # Unclaimed server, no token needed
            return ""
    except requests.RequestException:
        pass
    return None


def create_library(
    plex_url: str,
    token: str,
    name: str,
    library_type: str,
    location: str,
    scanner: str = "",
    agent: str = "",
    retries: int = 3,
) -> bool:
    """Create a library section in Plex with retry logic."""
    headers = {"X-Plex-Token": token} if token else {}

    # Get scanner and agent defaults
    if library_type == "movie":
        scanner = scanner or "Plex Movie"
        agent = agent or "tv.plex.agents.movie"
    elif library_type == "show":
        scanner = scanner or "Plex TV Series"
        agent = agent or "tv.plex.agents.series"

    params = {
        "name": name,
        "type": library_type,
        "agent": agent,
        "scanner": scanner,
        "language": "en-US",
        "location": location,
    }

    for attempt in range(retries):
        try:
            resp = requests.post(
                f"{plex_url}/library/sections",
                params=params,
                headers=headers,
                timeout=30,
            )
            if resp.status_code in (200, 201):
                print(f"  Created library: {name}")
                return True
            else:
                print(f"  Attempt {attempt + 1}/{retries}: Failed to create library {name}: {resp.status_code}")
                print(f"    Response: {resp.text[:200]}")
                if attempt < retries - 1:
                    time.sleep(5)  # Wait before retry
        except requests.RequestException as e:
            print(f"  Attempt {attempt + 1}/{retries}: Error creating library {name}: {e}")
            if attempt < retries - 1:
                time.sleep(5)

    return False


def get_library_sections(plex_url: str, token: str) -> list:
    """Get existing library sections."""
    headers = {"X-Plex-Token": token} if token else {}

    try:
        resp = requests.get(
            f"{plex_url}/library/sections",
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 200:
            # Parse XML response
            import xml.etree.ElementTree as ET

            root = ET.fromstring(resp.text)
            sections = []
            for directory in root.findall(".//Directory"):
                sections.append(
                    {
                        "key": directory.get("key"),
                        "title": directory.get("title"),
                        "type": directory.get("type"),
                    }
                )
            return sections
    except Exception as e:
        print(f"  Error getting sections: {e}")

    return []


def scan_library(plex_url: str, token: str, section_key: str) -> bool:
    """Trigger a library scan."""
    headers = {"X-Plex-Token": token} if token else {}

    try:
        resp = requests.get(
            f"{plex_url}/library/sections/{section_key}/refresh",
            headers=headers,
            timeout=10,
        )
        return resp.status_code == 200
    except requests.RequestException:
        return False


def wait_for_scan_complete(
    plex_url: str, token: str, section_key: str, timeout: int = 120
) -> bool:
    """Wait for library scan to complete."""
    headers = {"X-Plex-Token": token} if token else {}
    start = time.time()

    while time.time() - start < timeout:
        try:
            resp = requests.get(
                f"{plex_url}/library/sections/{section_key}/all",
                headers=headers,
                timeout=10,
            )
            if resp.status_code == 200:
                # Check if we have items
                import xml.etree.ElementTree as ET

                root = ET.fromstring(resp.text)
                size = int(root.get("size", 0))
                if size > 0:
                    return True
        except Exception:
            pass
        time.sleep(2)

    return False


def bootstrap_plex(
    plex_url: str = "http://localhost:32400",
    media_path: Optional[Path] = None,
    container_media_path: str = "/data/media",
) -> dict:
    """
    Bootstrap Plex for integration testing.

    Args:
        plex_url: URL of the Plex server
        media_path: Local path to media files (for setup)
        container_media_path: Path to media inside the container

    Returns:
        Dict with token and section info
    """
    result = {"success": False, "token": "", "sections": []}

    # Set up media files if path provided
    if media_path:
        setup_media(media_path)

    # Wait for Plex to be ready
    if not wait_for_plex(plex_url):
        print("ERROR: Plex did not start in time")
        return result

    # Give Plex a moment to fully initialize after responding to /identity
    print("Waiting for Plex to fully initialize...")
    time.sleep(10)

    # Get token (for unclaimed server, this is empty)
    token = get_plex_token(plex_url) or ""
    result["token"] = token

    # Check existing sections
    existing = get_library_sections(plex_url, token)
    existing_names = {s["title"] for s in existing}
    print(f"Existing libraries: {existing_names}")

    # Create Movies library if not exists
    if "Movies" not in existing_names:
        if not create_library(
            plex_url,
            token,
            "Movies",
            "movie",
            f"{container_media_path}/movies",
        ):
            print("WARNING: Failed to create Movies library")

    # Create TV Shows library if not exists
    if "TV Shows" not in existing_names:
        if not create_library(
            plex_url,
            token,
            "TV Shows",
            "show",
            f"{container_media_path}/tvshows",
        ):
            print("WARNING: Failed to create TV Shows library")

    # Get updated sections
    sections = get_library_sections(plex_url, token)
    result["sections"] = sections

    # Scan all libraries
    print("Scanning libraries...")
    for section in sections:
        print(f"  Scanning {section['title']}...")
        scan_library(plex_url, token, section["key"])

    # Wait for scans to complete
    print("Waiting for scans to complete...")
    for section in sections:
        if wait_for_scan_complete(plex_url, token, section["key"]):
            print(f"  {section['title']}: done")
        else:
            print(f"  {section['title']}: timeout (may still be scanning)")

    result["success"] = True
    return result


def main():
    """Run bootstrap from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="Bootstrap Plex for testing")
    parser.add_argument(
        "--plex-url",
        default="http://localhost:32400",
        help="Plex server URL",
    )
    parser.add_argument(
        "--media-path",
        type=Path,
        default=Path(__file__).parent.parent / "seed_data" / "media",
        help="Path to media files",
    )
    parser.add_argument(
        "--container-media-path",
        default="/data/media",
        help="Media path inside container",
    )
    parser.add_argument(
        "--skip-media-setup",
        action="store_true",
        help="Skip creating media files",
    )

    args = parser.parse_args()

    media_path = None if args.skip_media_setup else args.media_path

    result = bootstrap_plex(
        plex_url=args.plex_url,
        media_path=media_path,
        container_media_path=args.container_media_path,
    )

    if result["success"]:
        print("\nPlex bootstrap complete!")
        print(f"  Token: {result['token'] or '(none - unclaimed server)'}")
        print(f"  Sections: {len(result['sections'])}")
        for section in result["sections"]:
            print(f"    - {section['title']} (key={section['key']})")
    else:
        print("\nPlex bootstrap FAILED")
        exit(1)


if __name__ == "__main__":
    main()
