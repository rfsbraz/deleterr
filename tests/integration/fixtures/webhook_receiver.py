# encoding: utf-8
"""
Webhook receiver mock server for integration testing.

This Flask app captures incoming webhook requests and provides an API
to retrieve and verify captured payloads, enabling real HTTP integration
tests for the notification system.
"""

from flask import Flask, jsonify, request
from datetime import datetime, timezone
from typing import Dict, List, Any
import os

app = Flask(__name__)

# In-memory storage for captured webhooks
_webhooks: List[Dict[str, Any]] = []


def reset_webhooks() -> None:
    """Reset all captured webhooks."""
    global _webhooks
    _webhooks = []


def capture_webhook(
    method: str,
    path: str,
    headers: Dict[str, str],
    body: Any,
    query_params: Dict[str, str],
) -> Dict[str, Any]:
    """Capture a webhook request."""
    webhook = {
        "id": len(_webhooks) + 1,
        "method": method,
        "path": path,
        "headers": dict(headers),
        "body": body,
        "query_params": dict(query_params),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _webhooks.append(webhook)
    return webhook


# Health check endpoint
@app.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "webhooks_captured": len(_webhooks)})


# API endpoints for test verification
@app.route("/api/webhooks", methods=["GET"])
def list_webhooks():
    """List all captured webhooks."""
    return jsonify({
        "count": len(_webhooks),
        "webhooks": _webhooks,
    })


@app.route("/api/webhooks/latest", methods=["GET"])
def latest_webhook():
    """Get the most recently captured webhook."""
    if not _webhooks:
        return jsonify({"error": "No webhooks captured"}), 404
    return jsonify(_webhooks[-1])


@app.route("/api/webhooks/<int:webhook_id>", methods=["GET"])
def get_webhook(webhook_id: int):
    """Get a specific webhook by ID."""
    for webhook in _webhooks:
        if webhook["id"] == webhook_id:
            return jsonify(webhook)
    return jsonify({"error": "Webhook not found"}), 404


@app.route("/api/reset", methods=["POST"])
def api_reset():
    """Reset all captured webhooks (for test isolation)."""
    reset_webhooks()
    return jsonify({"status": "reset", "webhooks_cleared": True})


@app.route("/api/webhooks/count", methods=["GET"])
def webhook_count():
    """Get count of captured webhooks."""
    return jsonify({"count": len(_webhooks)})


@app.route("/api/webhooks/by-path/<path:webhook_path>", methods=["GET"])
def webhooks_by_path(webhook_path: str):
    """Get all webhooks captured at a specific path."""
    matching = [w for w in _webhooks if w["path"].lstrip("/") == webhook_path.lstrip("/")]
    return jsonify({
        "count": len(matching),
        "webhooks": matching,
    })


# Catch-all webhook receiver endpoints
# These endpoints capture incoming webhooks from the notification system

@app.route("/webhook", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@app.route("/webhook/<path:subpath>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def receive_webhook(subpath: str = ""):
    """
    Capture any webhook sent to /webhook or /webhook/<subpath>.
    Supports all HTTP methods.
    """
    path = f"/webhook/{subpath}" if subpath else "/webhook"

    # Try to parse JSON body, fallback to raw text
    body = None
    if request.is_json:
        body = request.get_json(silent=True)
    elif request.data:
        try:
            import json
            body = json.loads(request.data)
        except (json.JSONDecodeError, ValueError):
            body = request.data.decode("utf-8", errors="replace")

    webhook = capture_webhook(
        method=request.method,
        path=path,
        headers=request.headers,
        body=body,
        query_params=request.args,
    )

    return jsonify({
        "status": "received",
        "webhook_id": webhook["id"],
    })


# Discord-style webhook endpoint
@app.route("/discord", methods=["POST"])
@app.route("/discord/<path:subpath>", methods=["POST"])
def receive_discord(subpath: str = ""):
    """Capture Discord-style webhooks."""
    path = f"/discord/{subpath}" if subpath else "/discord"

    body = request.get_json(silent=True) if request.is_json else None

    webhook = capture_webhook(
        method=request.method,
        path=path,
        headers=request.headers,
        body=body,
        query_params=request.args,
    )

    # Discord webhooks return 204 No Content on success
    return "", 204


# Slack-style webhook endpoint
@app.route("/slack", methods=["POST"])
@app.route("/slack/<path:subpath>", methods=["POST"])
def receive_slack(subpath: str = ""):
    """Capture Slack-style webhooks."""
    path = f"/slack/{subpath}" if subpath else "/slack"

    body = request.get_json(silent=True) if request.is_json else None

    webhook = capture_webhook(
        method=request.method,
        path=path,
        headers=request.headers,
        body=body,
        query_params=request.args,
    )

    # Slack webhooks return "ok" text on success
    return "ok", 200


# Telegram-style webhook endpoint
@app.route("/telegram", methods=["POST"])
@app.route("/telegram/<path:subpath>", methods=["POST"])
def receive_telegram(subpath: str = ""):
    """Capture Telegram-style webhooks."""
    path = f"/telegram/{subpath}" if subpath else "/telegram"

    body = request.get_json(silent=True) if request.is_json else None

    webhook = capture_webhook(
        method=request.method,
        path=path,
        headers=request.headers,
        body=body,
        query_params=request.args,
    )

    # Telegram API returns JSON with ok: true
    return jsonify({"ok": True, "result": True})


# Generic catch-all for any path (lowest priority)
@app.route("/<path:anypath>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def receive_any(anypath: str):
    """
    Catch-all endpoint for any path not matched by specific routes.
    Useful for testing custom webhook endpoints.
    """
    # Skip API and health paths
    if anypath.startswith("api/") or anypath == "health":
        return jsonify({"error": "Not found"}), 404

    body = None
    if request.is_json:
        body = request.get_json(silent=True)
    elif request.data:
        try:
            import json
            body = json.loads(request.data)
        except (json.JSONDecodeError, ValueError):
            body = request.data.decode("utf-8", errors="replace")

    webhook = capture_webhook(
        method=request.method,
        path=f"/{anypath}",
        headers=request.headers,
        body=body,
        query_params=request.args,
    )

    return jsonify({
        "status": "received",
        "webhook_id": webhook["id"],
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
