# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Weblytic Labs
# See ../../LICENSE-EXAMPLES-MIT.md
"""Canned HTTPS responses for local API learning.

This transport never contacts a controller, an identity provider, or a
Windows PC. HTTP 202 here still means "stored", not unlocked play.
"""

from __future__ import annotations

import json
from typing import Mapping
from urllib.parse import urlparse

DEMO_DEVICE_ID = "22222222-2222-4222-8222-222222222222"
DEMO_SESSION_ID = "33333333-3333-4333-8333-333333333333"
DEMO_COMMAND_ID = "44444444-4444-4444-8444-444444444444"
DEMO_EXPIRES_AT = "2026-10-30T12:00:00Z"
DEMO_EXTEND_AT = "2026-10-30T13:00:00Z"

_HEADERS = {"Content-Type": "application/json", "X-Request-Id": "77777777-7777-4777-8777-777777777777"}


def _json(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def _error(status: int, code: str, message: str) -> tuple[int, dict[str, str], bytes]:
    headers = dict(_HEADERS)
    if status == 429:
        headers["Retry-After"] = "16"
    return (
        status,
        headers,
        _json(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "request_id": "77777777-7777-4777-8777-777777777777",
                    "details": [],
                }
            }
        ),
    )


class DemoTransport:
    """Return the unconfirmed booking contract. start_confirmed stays false."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def __call__(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, str], bytes]:
        del headers, body, timeout
        parsed = urlparse(url)
        path = parsed.path
        self.calls.append((method, path))
        if method == "GET" and path == "/api/v1/health":
            return 200, _HEADERS, _json({"status": "ok"})
        if method == "GET" and path == "/api/v1/devices":
            return 200, _HEADERS, _json(
                {
                    "items": [
                        {
                            "device_id": DEMO_DEVICE_ID,
                            "display_name": "Demo Station",
                            "platform": "windows",
                            "external_reference": "demo-station",
                            "status": {
                                "connectivity": "offline",
                                "access_state": "unknown",
                                "last_reported_access_state": "unknown",
                                "status_stale": True,
                                "stale_after_seconds": 30,
                            },
                        }
                    ],
                    "next_cursor": None,
                }
            )
        if method == "POST" and path == "/api/v1/sessions":
            return 202, _HEADERS, _json(self._created())
        if method == "GET" and path == f"/api/v1/sessions/{DEMO_SESSION_ID}":
            return 200, _HEADERS, _json(self._created()["session"])
        if method == "POST" and path == f"/api/v1/sessions/{DEMO_SESSION_ID}/extend":
            payload = self._created()
            payload["command"]["command_type"] = "extend_session"
            payload["session"]["pending_expires_at"] = DEMO_EXTEND_AT
            return 202, _HEADERS, _json(payload)
        if method == "POST" and path == f"/api/v1/sessions/{DEMO_SESSION_ID}/end":
            payload = self._created()
            payload["command"]["command_type"] = "end_session"
            payload["session"]["status"] = "ending"
            return 202, _HEADERS, _json(payload)
        return _error(404, "not_found", "The resource was not found.")

    @staticmethod
    def _created() -> dict:
        return {
            "outcome": "accepted",
            "session": {
                "session_id": DEMO_SESSION_ID,
                "account_id": "11111111-1111-4111-8111-111111111111",
                "device_id": DEMO_DEVICE_ID,
                "status": "accepted",
                "start_confirmed": False,
                "lock_confirmed": False,
                "expires_at": DEMO_EXPIRES_AT,
                "pending_expires_at": None,
            },
            "command": {
                "command_id": DEMO_COMMAND_ID,
                "command_type": "start_session",
                "status": "pending",
                "device_effect_confirmed": False,
            },
        }


def canned_error(status: int) -> tuple[int, Mapping[str, str], bytes]:
    """Fixture bodies for 401, 403, 404, 429, and 503 handling examples."""
    mapping = {
        401: ("unauthorized", "The bearer token is not valid."),
        403: ("forbidden", "The token does not include the required scope."),
        404: ("session_not_found", "The session is not in this account."),
        429: ("rate_limited", "The account exceeded the request rate limit."),
        503: ("storage_unavailable", "Device storage is unavailable."),
    }
    code, message = mapping[status]
    return _error(status, code, message)
