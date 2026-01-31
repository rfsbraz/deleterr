"""
Mock Plex server for integration testing.

This Flask app simulates the Plex API responses needed by Deleterr,
allowing integration tests to run without a real Plex server.
"""

from flask import Flask, jsonify, request
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import uuid
import os

app = Flask(__name__)

# In-memory storage for test data
_libraries: Dict[str, List[Dict]] = {
    "Movies": [],
    "TV Shows": []
}
_collections: Dict[str, Dict[str, List[str]]] = {
    "Movies": {},  # collection_name -> [rating_keys]
    "TV Shows": {},
}
_section_map = {"Movies": 1, "TV Shows": 2}


def reset_data():
    """Reset all test data."""
    global _libraries, _collections
    _libraries = {
        "Movies": [],
        "TV Shows": []
    }
    _collections = {
        "Movies": {},
        "TV Shows": {},
    }


def add_movie(
    title: str,
    year: int,
    tmdb_id: Optional[int] = None,
    imdb_id: Optional[str] = None,
    added_at: Optional[datetime] = None,
    last_viewed_at: Optional[datetime] = None,
    collections: Optional[List[str]] = None,
    genres: Optional[List[str]] = None,
    labels: Optional[List[str]] = None,
    studio: Optional[str] = None,
    directors: Optional[List[str]] = None,
    writers: Optional[List[str]] = None,
    actors: Optional[List[str]] = None,
    producers: Optional[List[str]] = None,
    rating_key: Optional[str] = None,
) -> Dict:
    """Add a mock movie to the library."""
    movie = {
        "ratingKey": rating_key or str(uuid.uuid4().int)[:8],
        "guid": f"plex://movie/{uuid.uuid4()}",
        "guids": [],
        "title": title,
        "year": year,
        "addedAt": int((added_at or datetime.now()).timestamp()),
        "lastViewedAt": int(last_viewed_at.timestamp()) if last_viewed_at else None,
        "collections": [{"tag": c} for c in (collections or [])],
        "genres": [{"tag": g} for g in (genres or [])],
        "labels": [{"tag": l} for l in (labels or [])],
        "studio": studio,
        "directors": [{"tag": d} for d in (directors or [])],
        "writers": [{"tag": w} for w in (writers or [])],
        "roles": [{"tag": a} for a in (actors or [])],
        "producers": [{"tag": p} for p in (producers or [])]
    }

    if tmdb_id:
        movie["guids"].append({"id": f"tmdb://{tmdb_id}"})
    if imdb_id:
        movie["guids"].append({"id": f"imdb://{imdb_id}"})

    _libraries["Movies"].append(movie)
    return movie


def add_series(
    title: str,
    year: int,
    tvdb_id: Optional[int] = None,
    imdb_id: Optional[str] = None,
    added_at: Optional[datetime] = None,
    last_viewed_at: Optional[datetime] = None,
    collections: Optional[List[str]] = None,
    genres: Optional[List[str]] = None,
    labels: Optional[List[str]] = None,
    studio: Optional[str] = None,
    rating_key: Optional[str] = None,
) -> Dict:
    """Add a mock TV series to the library."""
    series = {
        "ratingKey": rating_key or str(uuid.uuid4().int)[:8],
        "guid": f"plex://show/{uuid.uuid4()}",
        "guids": [],
        "title": title,
        "year": year,
        "addedAt": int((added_at or datetime.now()).timestamp()),
        "lastViewedAt": int(last_viewed_at.timestamp()) if last_viewed_at else None,
        "collections": [{"tag": c} for c in (collections or [])],
        "genres": [{"tag": g} for g in (genres or [])],
        "labels": [{"tag": l} for l in (labels or [])],
        "studio": studio,
        "directors": [],
        "writers": [],
        "roles": [],
        "producers": []
    }

    if tvdb_id:
        series["guids"].append({"id": f"tvdb://{tvdb_id}"})
    if imdb_id:
        series["guids"].append({"id": f"imdb://{imdb_id}"})

    _libraries["TV Shows"].append(series)
    return series


# Flask routes

@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy"})


@app.route('/identity')
def identity():
    """Plex server identity."""
    return jsonify({
        "MediaContainer": {
            "machineIdentifier": "test-plex-server",
            "version": "1.0.0"
        }
    })


@app.route('/library/sections')
def sections():
    """List library sections."""
    return jsonify({
        "MediaContainer": {
            "Directory": [
                {"key": "1", "title": "Movies", "type": "movie"},
                {"key": "2", "title": "TV Shows", "type": "show"}
            ]
        }
    })


@app.route('/library/sections/<int:section_id>/all')
def section_all(section_id: int):
    """Get all items in a library section."""
    section_name = "Movies" if section_id == 1 else "TV Shows"
    items = _libraries.get(section_name, [])

    return jsonify({
        "MediaContainer": {
            "size": len(items),
            "Metadata": items
        }
    })


@app.route('/library/metadata/<rating_key>')
def metadata(rating_key: str):
    """Get metadata for a specific item."""
    for library in _libraries.values():
        for item in library:
            if item["ratingKey"] == rating_key:
                return jsonify({
                    "MediaContainer": {
                        "Metadata": [item]
                    }
                })

    return jsonify({"error": "Not found"}), 404


@app.route('/api/reset', methods=['POST'])
def api_reset():
    """Reset all test data (for test isolation)."""
    reset_data()
    return jsonify({"status": "reset"})


@app.route('/api/add_movie', methods=['POST'])
def api_add_movie():
    """Add a movie via API (for test setup)."""
    data = request.json
    movie = add_movie(
        title=data["title"],
        year=data["year"],
        tmdb_id=data.get("tmdb_id"),
        imdb_id=data.get("imdb_id"),
        added_at=datetime.fromisoformat(data["added_at"]) if data.get("added_at") else None,
        last_viewed_at=datetime.fromisoformat(data["last_viewed_at"]) if data.get("last_viewed_at") else None,
        collections=data.get("collections"),
        genres=data.get("genres"),
        labels=data.get("labels"),
        studio=data.get("studio"),
        directors=data.get("directors"),
        writers=data.get("writers"),
        actors=data.get("actors"),
        producers=data.get("producers"),
        rating_key=data.get("rating_key"),
    )
    return jsonify(movie)


@app.route('/api/add_series', methods=['POST'])
def api_add_series():
    """Add a TV series via API (for test setup)."""
    data = request.json
    series = add_series(
        title=data["title"],
        year=data["year"],
        tvdb_id=data.get("tvdb_id"),
        imdb_id=data.get("imdb_id"),
        added_at=datetime.fromisoformat(data["added_at"]) if data.get("added_at") else None,
        last_viewed_at=datetime.fromisoformat(data["last_viewed_at"]) if data.get("last_viewed_at") else None,
        collections=data.get("collections"),
        genres=data.get("genres"),
        labels=data.get("labels"),
        studio=data.get("studio"),
        rating_key=data.get("rating_key"),
    )
    return jsonify(series)


# Collection endpoints

@app.route('/library/sections/<int:section_id>/collections')
def section_collections(section_id: int):
    """Get all collections in a library section."""
    section_name = "Movies" if section_id == 1 else "TV Shows"
    collections = _collections.get(section_name, {})

    collection_list = []
    for name, rating_keys in collections.items():
        collection_list.append({
            "ratingKey": f"collection-{name}",
            "title": name,
            "type": "collection",
            "childCount": len(rating_keys),
        })

    return jsonify({
        "MediaContainer": {
            "size": len(collection_list),
            "Metadata": collection_list
        }
    })


@app.route('/library/collections/<collection_key>')
def get_collection(collection_key: str):
    """Get a specific collection by key."""
    # Extract collection name from key
    name = collection_key.replace("collection-", "")

    for section_name, section_collections in _collections.items():
        if name in section_collections:
            rating_keys = section_collections[name]
            items = []
            for library in _libraries.values():
                for item in library:
                    if item["ratingKey"] in rating_keys:
                        items.append(item)

            return jsonify({
                "MediaContainer": {
                    "ratingKey": collection_key,
                    "title": name,
                    "type": "collection",
                    "size": len(items),
                    "Metadata": items
                }
            })

    return jsonify({"error": "Collection not found"}), 404


@app.route('/library/collections/<collection_key>/items', methods=['PUT'])
def update_collection_items(collection_key: str):
    """Add or remove items from a collection."""
    name = collection_key.replace("collection-", "")
    uri = request.args.get('uri', '')

    # Parse rating keys from uri parameter
    # Format: server://machineId/com.plexapp.plugins.library/library/metadata/ratingKey
    import re
    rating_keys = re.findall(r'/library/metadata/(\d+)', uri)

    for section_name, section_collections in _collections.items():
        if name in section_collections:
            section_collections[name].extend(rating_keys)
            return jsonify({"status": "ok"})

    return jsonify({"error": "Collection not found"}), 404


@app.route('/library/collections/<collection_key>/items/<rating_key>', methods=['DELETE'])
def remove_from_collection(collection_key: str, rating_key: str):
    """Remove an item from a collection."""
    name = collection_key.replace("collection-", "")

    for section_name, section_collections in _collections.items():
        if name in section_collections:
            if rating_key in section_collections[name]:
                section_collections[name].remove(rating_key)
            return jsonify({"status": "ok"})

    return jsonify({"error": "Collection not found"}), 404


@app.route('/library/sections/<int:section_id>/collections', methods=['POST'])
def create_collection(section_id: int):
    """Create a new collection."""
    section_name = "Movies" if section_id == 1 else "TV Shows"
    title = request.args.get('title', 'Untitled')

    if title not in _collections[section_name]:
        _collections[section_name][title] = []

    return jsonify({
        "MediaContainer": {
            "Metadata": [{
                "ratingKey": f"collection-{title}",
                "title": title,
                "type": "collection",
            }]
        }
    })


# Label endpoints

@app.route('/library/metadata/<rating_key>/label', methods=['PUT'])
def add_label(rating_key: str):
    """Add a label to an item."""
    label = request.args.get('label.locked', '') or request.args.get('label[0].tag.tag', '')

    for library in _libraries.values():
        for item in library:
            if item["ratingKey"] == rating_key:
                if label and label not in [l["tag"] for l in item.get("labels", [])]:
                    if "labels" not in item:
                        item["labels"] = []
                    item["labels"].append({"tag": label})
                return jsonify({"status": "ok"})

    return jsonify({"error": "Item not found"}), 404


@app.route('/library/metadata/<rating_key>/label', methods=['DELETE'])
def remove_label(rating_key: str):
    """Remove a label from an item."""
    label = request.args.get('label.locked', '') or request.args.get('label[0].tag.tag', '')

    for library in _libraries.values():
        for item in library:
            if item["ratingKey"] == rating_key:
                item["labels"] = [l for l in item.get("labels", []) if l["tag"] != label]
                return jsonify({"status": "ok"})

    return jsonify({"error": "Item not found"}), 404


@app.route('/library/sections/<int:section_id>/all', methods=['GET'])
def section_all_with_filters(section_id: int):
    """Get all items in a library section with optional filters."""
    section_name = "Movies" if section_id == 1 else "TV Shows"
    items = _libraries.get(section_name, [])

    # Handle label filter
    label_filter = request.args.get('label', None)
    guid_filter = request.args.get('guid', None)
    title_filter = request.args.get('title', None)

    if label_filter:
        items = [
            item for item in items
            if any(l.get("tag", "").lower() == label_filter.lower() for l in item.get("labels", []))
        ]

    if guid_filter:
        items = [
            item for item in items
            if any(guid_filter in g.get("id", "") for g in item.get("guids", []))
        ]

    if title_filter:
        items = [
            item for item in items
            if title_filter.lower() in item.get("title", "").lower()
        ]

    return jsonify({
        "MediaContainer": {
            "size": len(items),
            "Metadata": items
        }
    })


# Test API endpoints for verification

@app.route('/api/collections/<section_name>')
def api_get_collections(section_name: str):
    """Get collections for a section (test API)."""
    return jsonify(_collections.get(section_name, {}))


@app.route('/api/collections/<section_name>/<collection_name>', methods=['POST'])
def api_create_collection(section_name: str, collection_name: str):
    """Create a collection (test API)."""
    if section_name not in _collections:
        _collections[section_name] = {}
    _collections[section_name][collection_name] = []
    return jsonify({"status": "created"})


@app.route('/api/collections/<section_name>/<collection_name>/items', methods=['POST'])
def api_add_to_collection(section_name: str, collection_name: str):
    """Add items to a collection (test API)."""
    data = request.json
    rating_keys = data.get("rating_keys", [])

    if section_name not in _collections:
        _collections[section_name] = {}
    if collection_name not in _collections[section_name]:
        _collections[section_name][collection_name] = []

    _collections[section_name][collection_name].extend(rating_keys)
    return jsonify({"status": "ok"})


@app.route('/api/item/<rating_key>/labels', methods=['GET'])
def api_get_labels(rating_key: str):
    """Get labels for an item (test API)."""
    for library in _libraries.values():
        for item in library:
            if item["ratingKey"] == rating_key:
                return jsonify({"labels": [l["tag"] for l in item.get("labels", [])]})
    return jsonify({"error": "Not found"}), 404


@app.route('/api/item/<rating_key>/labels', methods=['POST'])
def api_add_label(rating_key: str):
    """Add a label to an item (test API)."""
    data = request.json
    label = data.get("label")

    for library in _libraries.values():
        for item in library:
            if item["ratingKey"] == rating_key:
                if "labels" not in item:
                    item["labels"] = []
                if label not in [l["tag"] for l in item["labels"]]:
                    item["labels"].append({"tag": label})
                return jsonify({"status": "ok"})
    return jsonify({"error": "Not found"}), 404


@app.route('/api/item/<rating_key>/labels/<label>', methods=['DELETE'])
def api_remove_label(rating_key: str, label: str):
    """Remove a label from an item (test API)."""
    for library in _libraries.values():
        for item in library:
            if item["ratingKey"] == rating_key:
                item["labels"] = [l for l in item.get("labels", []) if l["tag"] != label]
                return jsonify({"status": "ok"})
    return jsonify({"error": "Not found"}), 404


# Initialize with default test data
def init_default_data():
    """Initialize with default test data for integration tests."""
    now = datetime.now()
    old_date = now - timedelta(days=180)
    recent_date = now - timedelta(days=10)

    # Movies
    add_movie(
        title="Old Unwatched Movie",
        year=2020,
        tmdb_id=550,
        imdb_id="tt0137523",
        added_at=old_date,
        last_viewed_at=None,
        rating_key="1001",
    )
    add_movie(
        title="Recently Watched Movie",
        year=2021,
        tmdb_id=551,
        imdb_id="tt0000001",
        added_at=old_date,
        last_viewed_at=recent_date,
        rating_key="1002",
    )
    add_movie(
        title="Movie In Excluded Collection",
        year=2019,
        tmdb_id=552,
        imdb_id="tt0000002",
        added_at=old_date,
        collections=["Favorites"],
        rating_key="1003",
    )
    add_movie(
        title="Recently Added Movie",
        year=2023,
        tmdb_id=553,
        imdb_id="tt0000003",
        added_at=recent_date,
        rating_key="1004",
    )

    # TV Shows
    add_series(
        title="Old Unwatched Show",
        year=2018,
        tvdb_id=81189,
        added_at=old_date,
        last_viewed_at=None,
        rating_key="2001",
    )
    add_series(
        title="Recently Watched Show",
        year=2019,
        tvdb_id=81190,
        added_at=old_date,
        last_viewed_at=recent_date,
        rating_key="2002",
    )
    add_series(
        title="Anime Series",
        year=2020,
        tvdb_id=81191,
        added_at=old_date,
        genres=["Anime"],
        rating_key="2003",
    )


if __name__ == '__main__':
    init_default_data()
    port = int(os.environ.get('PORT', 32400))
    app.run(host='0.0.0.0', port=port, debug=False)
