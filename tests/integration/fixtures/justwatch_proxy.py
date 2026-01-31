# encoding: utf-8
"""
JustWatch caching proxy for integration testing.

This Flask app acts as a proxy for the JustWatch GraphQL API, caching
responses to avoid rate limiting during integration tests. On startup,
it optionally makes a single real request to validate the API format.
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from flask import Flask, jsonify, request

app = Flask(__name__)

# Configuration
JUSTWATCH_API_URL = "https://apis.justwatch.com/graphql"
CACHE_DIR = Path("/app/cache")
CACHE_FILE = CACHE_DIR / "justwatch_cache.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# In-memory cache (loaded from file on startup)
_cache: Dict[str, Any] = {}
_stats = {
    "hits": 0,
    "misses": 0,
    "real_requests": 0,
    "errors": 0,
}


def _hash_request(body: Dict) -> str:
    """Create a deterministic hash of the request body.

    Uses only the search query, country, and language from the variables
    to ensure cache hits regardless of library version differences in
    query formatting.
    """
    # Extract the key search parameters for a stable hash
    variables = body.get("variables", {})
    search_filter = variables.get("searchTitlesFilter", {})
    search_query = search_filter.get("searchQuery", "")
    country = variables.get("country", "US")
    language = variables.get("language", "en")

    # Create a stable key from search parameters only
    cache_key_data = {
        "query": search_query.lower().strip(),
        "country": country,
        "language": language,
    }
    normalized = json.dumps(cache_key_data, sort_keys=True)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _load_cache() -> None:
    """Load cache from disk."""
    global _cache
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r") as f:
                _cache = json.load(f)
            print(f"Loaded {len(_cache)} cached responses from {CACHE_FILE}")
        except Exception as e:
            print(f"Error loading cache: {e}")
            _cache = {}
    else:
        print("No cache file found, starting with empty cache")
        _cache = {}


def _save_cache() -> None:
    """Save cache to disk."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(_cache, f, indent=2)
    except Exception as e:
        print(f"Error saving cache: {e}")


def _make_real_request(body: Dict) -> Optional[Dict]:
    """Make a real request to JustWatch API."""
    try:
        headers = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}
        response = httpx.post(
            JUSTWATCH_API_URL, json=body, headers=headers, timeout=30.0
        )
        response.raise_for_status()
        _stats["real_requests"] += 1
        return response.json()
    except Exception as e:
        print(f"Error making real request: {e}")
        _stats["errors"] += 1
        return None


def _validate_api_format() -> bool:
    """Make a single real request to validate API format is working."""
    test_query = {
        "operationName": "GetSearchTitles",
        "variables": {
            "country": "US",
            "language": "en",
            "first": 1,
            "searchTitlesFilter": {"searchQuery": "test"},
        },
        "query": """
        query GetSearchTitles($country: Country!, $language: Language!, $first: Int!, $searchTitlesFilter: TitleFilter) {
            popularTitles(country: $country, first: $first, filter: $searchTitlesFilter) {
                edges {
                    node {
                        id
                        objectType
                    }
                }
            }
        }
        """,
    }

    print("Validating JustWatch API format with a test request...")
    result = _make_real_request(test_query)
    if result and "data" in result:
        print("API validation successful")
        return True
    print("API validation failed - will rely on cached data only")
    return False


# Health check endpoint
@app.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "cache_entries": len(_cache),
        "stats": _stats,
    })


# Stats endpoint
@app.route("/stats")
def stats():
    """Return proxy statistics."""
    return jsonify({
        "cache_entries": len(_cache),
        "stats": _stats,
        "cache_keys": list(_cache.keys()),
    })


# Reset endpoint (for test isolation)
@app.route("/reset", methods=["POST"])
def reset():
    """Reset statistics (cache is preserved)."""
    global _stats
    _stats = {"hits": 0, "misses": 0, "real_requests": 0, "errors": 0}
    return jsonify({"status": "reset"})


# GraphQL proxy endpoint
@app.route("/graphql", methods=["POST"])
def graphql_proxy():
    """
    Proxy endpoint for JustWatch GraphQL API.

    Returns cached responses when available, otherwise returns a
    mock response indicating the title wasn't found.
    """
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Invalid request body"}), 400

    cache_key = _hash_request(body)

    # Check cache first
    if cache_key in _cache:
        _stats["hits"] += 1
        cached = _cache[cache_key]
        print(f"Cache HIT for key {cache_key}")
        return jsonify(cached["response"])

    _stats["misses"] += 1
    print(f"Cache MISS for key {cache_key}")

    # Check if we should make real requests (disabled by default in tests)
    allow_real = os.environ.get("JUSTWATCH_ALLOW_REAL_REQUESTS", "false").lower() == "true"

    if allow_real:
        result = _make_real_request(body)
        if result:
            # Cache the successful response
            _cache[cache_key] = {
                "response": result,
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "request_hash": cache_key,
            }
            _save_cache()
            return jsonify(result)

    # Return empty result (no titles found) for uncached queries
    # This mimics the JustWatch API response when no results are found
    return jsonify({
        "data": {
            "popularTitles": {
                "edges": []
            }
        }
    })


# Admin endpoint to add cache entries manually
@app.route("/cache", methods=["POST"])
def add_cache_entry():
    """Add a cache entry manually (for seeding test data)."""
    data = request.get_json(silent=True)
    if not data or "request" not in data or "response" not in data:
        return jsonify({"error": "Need 'request' and 'response' fields"}), 400

    cache_key = _hash_request(data["request"])
    _cache[cache_key] = {
        "response": data["response"],
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "request_hash": cache_key,
    }
    _save_cache()

    return jsonify({"status": "cached", "key": cache_key})


@app.route("/cache", methods=["GET"])
def list_cache():
    """List all cache entries."""
    return jsonify({
        "count": len(_cache),
        "entries": [
            {"key": k, "cached_at": v.get("cached_at")}
            for k, v in _cache.items()
        ],
    })


if __name__ == "__main__":
    # Load existing cache (pre-seeded via Dockerfile)
    _load_cache()

    # Optionally validate API format on startup with a single real request
    if os.environ.get("JUSTWATCH_VALIDATE_ON_STARTUP", "false").lower() == "true":
        _validate_api_format()

    port = int(os.environ.get("PORT", 8888))
    print(f"Starting JustWatch proxy on port {port} with {len(_cache)} cached entries")
    app.run(host="0.0.0.0", port=port, debug=False)
