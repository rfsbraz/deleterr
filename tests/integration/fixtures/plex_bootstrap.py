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

# Minimal valid MP4 file (silent, 1 frame, ~1KB)
# This is a base64-encoded minimal valid MP4 that Plex can scan
STUB_VIDEO_B64 = """
AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDEAAAAIZnJlZQAAAu1tZGF0AAACoAYF//+c
3EXpvebZSLeWLNgg2SPu73gyNjQgLSBjb3JlIDE2NCByMzA5NSBiYWVlNDAwIC0gSC4yNjQvTVBF
Ry00IEFWQyBjb2RlYyAtIENvcHlsZWZ0IDIwMDMtMjAyMiAtIGh0dHA6Ly93d3cudmlkZW9sYW4u
b3JnL3gyNjQuaHRtbCAtIG9wdGlvbnM6IGNhYmFjPTEgcmVmPTMgZGVibG9jaz0xOjA6MCBhbmFs
eXNlPTB4MzoweDExMyBtZT1oZXggc3VibWU9NyBwc3k9MSBwc3lfcmQ9MS4wMDowLjAwIG1peGVk
X3JlZj0xIG1lX3JhbmdlPTE2IGNocm9tYV9tZT0xIHRyZWxsaXM9MSA4eDhkY3Q9MSBjcW09MCBk
ZWFkem9uZT0yMSwxMSBmYXN0X3Bza2lwPTEgY2hyb21hX3FwX29mZnNldD0tMiB0aHJlYWRzPTEy
IGxvb2thaGVhZF90aHJlYWRzPTIgc2xpY2VkX3RocmVhZHM9MCBucj0wIGRlY2ltYXRlPTEgaW50
ZXJsYWNlZD0wIGJsdXJheV9jb21wYXQ9MCBjb25zdHJhaW5lZF9pbnRyYT0wIGJmcmFtZXM9MyBi
X3B5cmFtaWQ9MiBiX2FkYXB0PTEgYl9iaWFzPTAgZGlyZWN0PTEgd2VpZ2h0Yj0xIG9wZW5fZ29w
PTAgd2VpZ2h0cD0yIGtleWludD0yNTAga2V5aW50X21pbj0yNSBzY2VuZWN1dD00MCBpbnRyYV9y
ZWZyZXNoPTAgcmNfbG9va2FoZWFkPTQwIHJjPWNyZiBtYnRyZWU9MSBjcmY9MjMuMCBxY29tcD0w
LjYwIHFwbWluPTAgcXBtYXg9NjkgcXBzdGVwPTQgaXBfcmF0aW89MS40MCBhcT0xOjEuMDAAgAAA
AARBniRsQ/8AAAMDAAADABhQwA0QAAADAAIAAAADAAMAAP/hABhnZW5lcmF0ZWQgYnkgZmZtcGVn
AAAACGxhdmM1OS4xOAAAAQNtb292AAAAbG12aGQAAAAAAAAAAAAAAAAAAAPoAAAAZAABAAABAAAB
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACAAAABkbWV0YQAAACFoZGxyAAAAAAAA
AABtZGlyYXBwbAAAAAAAAAAAAAAAAC1pbHN0AAAAJal0b28AAAAdZGF0YQAAAAEAAAAATGF2ZjU5
LjI3LjEwMAAAAAP4bW9vdgAAAGxtdmhkAAAAAAAAAAAAAAAAAAAD6AAAAGQAAQAAAQAAAAAAAAAe
AAAAAQAAAAEAAAABAAAAEGJpbmQAAAAIYnNpZQAAAAAAAAFmdHJhawAAAFx0a2hkAAAAAwAAAAAA
AAAAAAAAAQAAAAAAAAAZAAAAAAAAAAAAAAAAAAAAAQAAAAABAAAAAAAAAAAAAAAAAAADAAAAAAT//
wAAAR5tZGlhAAAAIG1kaGQAAAAAAAAAAAAAAAAAAKxEAAAQAFXEAAAAAAAtaGRscgAAAAAAAAAA
dmlkZQAAAAAAAAAAAAAAAFZpZGVvSGFuZGxlcgAAAAEJbWluZgAAABR2bWhkAAAAAQAAAAAAAAAA
AAEoZGluZgAAABxkcmVmAAAAAAAAAAEAAAAMdXJsIAAAAAEAAADJc3RibAAAAJVzdHNkAAAAAAAA
AAEAAACFYXZjMQAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAABAACAAJhGAgAAtAAAAGP//AAAAHWF2
Y0MBZAAK/+EAGWdkAAqs2UCgL/lgLUCcgQAAAwADAAADAAfQ8UJZYAEABWjr7sMgAAAAGHN0dHMA
AAABAAAAAgAAAQAAAAAcc3RzcwAAAAAAAAABAAAAAQAAABRzdHNjAAAAAAAAAAAAAAQc3R0cwAA
AAIAAAACAAABAAAAAAHxc3R6AAAAAAAAAAAAAAACAAACYQAAAA0AAAAUc3RjbwAAAAAAAAABAAAA
MAAAAA==
"""

# Test media content
MOVIES = [
    {"title": "Old Unwatched Movie", "year": 2020, "tmdb_id": 550},
    {"title": "Recently Watched Movie", "year": 2021, "tmdb_id": 551},
    {"title": "Movie In Excluded Collection", "year": 2019, "tmdb_id": 552},
    {"title": "Recently Added Movie", "year": 2023, "tmdb_id": 553},
    {"title": "Protected Movie", "year": 2022, "tmdb_id": 554},
]

TV_SHOWS = [
    {
        "title": "Old Unwatched Show",
        "year": 2018,
        "tvdb_id": 81189,
        "seasons": {1: 10, 2: 10},
    },
    {
        "title": "Recently Watched Show",
        "year": 2019,
        "tvdb_id": 81190,
        "seasons": {1: 8},
    },
    {
        "title": "Continuing Show",
        "year": 2020,
        "tvdb_id": 81191,
        "seasons": {1: 12, 2: 12, 3: 6},
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
) -> bool:
    """Create a library section in Plex."""
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
            print(f"  Failed to create library {name}: {resp.status_code}")
            print(f"    Response: {resp.text[:200]}")
            return False
    except requests.RequestException as e:
        print(f"  Error creating library {name}: {e}")
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

    # Get token (for unclaimed server, this is empty)
    token = get_plex_token(plex_url) or ""
    result["token"] = token

    # Check existing sections
    existing = get_library_sections(plex_url, token)
    existing_names = {s["title"] for s in existing}

    # Create Movies library if not exists
    if "Movies" not in existing_names:
        create_library(
            plex_url,
            token,
            "Movies",
            "movie",
            f"{container_media_path}/movies",
        )

    # Create TV Shows library if not exists
    if "TV Shows" not in existing_names:
        create_library(
            plex_url,
            token,
            "TV Shows",
            "show",
            f"{container_media_path}/tvshows",
        )

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
