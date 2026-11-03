# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Weblytic Labs
# See ../../LICENSE-EXAMPLES-MIT.md
"""Request-construction tests that do not contact a controller or a PC."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from demo_transport import DEMO_DEVICE_ID, DEMO_SESSION_ID, DemoTransport, canned_error
from gaming_controller_client import (
    ControllerApiError,
    GamingControllerClient,
    lock_confirmed,
    play_confirmed,
    session_document,
)

TOKEN = "test-access-token"


class Recorder:
    def __init__(self, status: int = 200, body: bytes = b'{"status":"ok"}') -> None:
        self.calls: list[tuple[str, str, dict[str, str], bytes | None]] = []
        self.status = status
        self.body = body

    def __call__(self, method, url, headers, body, timeout):
        del timeout
        self.calls.append((method, url, dict(headers), body))
        return self.status, {"Content-Type": "application/json", "X-Request-Id": "req-1"}, self.body


class ClientRequestTests(unittest.TestCase):
    def test_health_omits_authorization(self) -> None:
        recorder = Recorder()
        client = GamingControllerClient("https://controller.example", TOKEN, transport=recorder)
        self.assertEqual(client.health(), {"status": "ok"})
        method, url, headers, body = recorder.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(url, "https://controller.example/api/v1/health")
        self.assertNotIn("Authorization", headers)
        self.assertIsNone(body)

    def test_session_lifecycle_paths_match_php_and_curl(self) -> None:
        created = {
            "outcome": "accepted",
            "session": {
                "session_id": "33333333-3333-4333-8333-333333333333",
                "status": "accepted",
                "start_confirmed": False,
                "lock_confirmed": False,
            },
            "command": {"command_id": "44444444-4444-4444-8444-444444444444", "status": "pending"},
        }
        recorder = Recorder(status=202, body=json.dumps(created).encode())
        client = GamingControllerClient("https://controller.example", TOKEN, transport=recorder)
        payload = client.create_session(
            device_id="22222222-2222-4222-8222-222222222222",
            expires_at="2026-10-30T12:00:00Z",
            external_reference="booking-98421",
            idempotency_key="booking-98421-start",
        )
        method, url, headers, body = recorder.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://controller.example/api/v1/sessions")
        self.assertEqual(headers["Authorization"], "Bearer test-access-token")
        self.assertEqual(headers["Idempotency-Key"], "booking-98421-start")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(
            json.loads(body.decode()),
            {
                "device_id": "22222222-2222-4222-8222-222222222222",
                "expires_at": "2026-10-30T12:00:00Z",
                "external_reference": "booking-98421",
            },
        )
        self.assertFalse(play_confirmed(payload))
        self.assertFalse(lock_confirmed(payload))
        self.assertEqual(session_document(payload)["session_id"], created["session"]["session_id"])

    def test_get_session_and_extend_and_end_use_implemented_paths(self) -> None:
        session = {
            "session_id": "33333333-3333-4333-8333-333333333333",
            "status": "active",
            "start_confirmed": True,
            "lock_confirmed": False,
        }
        recorder = Recorder(body=json.dumps(session).encode())
        client = GamingControllerClient("https://controller.example", TOKEN, transport=recorder)
        fetched = client.get_session("33333333-3333-4333-8333-333333333333")
        self.assertTrue(play_confirmed(fetched))
        recorder.body = json.dumps({"outcome": "accepted", "session": session, "command": {}}).encode()
        recorder.status = 202
        client.extend_session(
            "33333333-3333-4333-8333-333333333333",
            expires_at="2026-10-30T13:00:00Z",
            idempotency_key="booking-98421-extend",
        )
        client.end_session(
            "33333333-3333-4333-8333-333333333333",
            idempotency_key="booking-98421-end",
            reason="user_request",
        )
        paths = [call[1] for call in recorder.calls]
        self.assertEqual(
            paths,
            [
                "https://controller.example/api/v1/sessions/33333333-3333-4333-8333-333333333333",
                "https://controller.example/api/v1/sessions/33333333-3333-4333-8333-333333333333/extend",
                "https://controller.example/api/v1/sessions/33333333-3333-4333-8333-333333333333/end",
            ],
        )
        self.assertEqual(recorder.calls[0][0], "GET")
        self.assertEqual(recorder.calls[1][0], "POST")
        self.assertEqual(recorder.calls[2][0], "POST")

    def test_authorization_error_is_not_retryable(self) -> None:
        body = {
            "error": {
                "code": "forbidden",
                "message": "The token does not include the required scope.",
                "request_id": "req-1",
                "details": [],
            }
        }
        recorder = Recorder(status=403, body=json.dumps(body).encode())
        client = GamingControllerClient("https://controller.example", TOKEN, transport=recorder)
        with self.assertRaises(ControllerApiError) as raised:
            client.list_devices()
        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.error_code, "forbidden")
        self.assertFalse(raised.exception.is_retryable())

    def test_unauthorized_error_is_not_retryable(self) -> None:
        status, _headers, body = canned_error(401)
        recorder = Recorder(status=status, body=body)
        client = GamingControllerClient("https://controller.example", TOKEN, transport=recorder)
        with self.assertRaises(ControllerApiError) as raised:
            client.list_devices()
        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(raised.exception.error_code, "unauthorized")
        self.assertFalse(raised.exception.is_retryable())

    def test_not_found_error_is_not_retryable(self) -> None:
        status, _headers, body = canned_error(404)
        recorder = Recorder(status=status, body=body)
        client = GamingControllerClient("https://controller.example", TOKEN, transport=recorder)
        with self.assertRaises(ControllerApiError) as raised:
            client.get_session("33333333-3333-4333-8333-333333333333")
        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.error_code, "session_not_found")
        self.assertFalse(raised.exception.is_retryable())

    def test_storage_unavailable_is_retryable(self) -> None:
        status, _headers, body = canned_error(503)
        recorder = Recorder(status=status, body=body)
        client = GamingControllerClient("https://controller.example", TOKEN, transport=recorder)
        with self.assertRaises(ControllerApiError) as raised:
            client.list_devices()
        self.assertEqual(raised.exception.status_code, 503)
        self.assertTrue(raised.exception.is_retryable())

    def test_rate_limited_error_is_retryable(self) -> None:
        body = {
            "error": {
                "code": "rate_limited",
                "message": "The account exceeded the request rate limit.",
                "request_id": "req-1",
                "details": [],
            }
        }
        recorder = Recorder(status=429, body=json.dumps(body).encode())
        client = GamingControllerClient("https://controller.example", TOKEN, transport=recorder)
        with self.assertRaises(ControllerApiError) as raised:
            client.list_devices()
        self.assertEqual(raised.exception.status_code, 429)
        self.assertTrue(raised.exception.is_retryable())

    def test_repr_omits_access_token(self) -> None:
        client = GamingControllerClient("https://controller.example", TOKEN, transport=Recorder())
        self.assertNotIn(TOKEN, repr(client))

    def test_non_loopback_http_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            GamingControllerClient("http://controller.example", TOKEN, transport=Recorder())

    def test_php_client_declares_the_same_paths(self) -> None:
        php = (Path(__file__).resolve().parent.parent / "php" / "GamingControllerClient.php").read_text()
        curl = (Path(__file__).resolve().parent.parent / "curl-examples.sh").read_text()
        for path in (
            "/api/v1/health",
            "/api/v1/devices",
            "/api/v1/sessions",
            "/extend",
            "/end",
        ):
            self.assertIn(path, php)
            self.assertIn(path, curl)
        self.assertNotIn("/api/v1/commands/", php)
        self.assertNotIn("/api/v1/agents/heartbeat", php)

    def test_demo_transport_never_confirms_windows_effects(self) -> None:
        transport = DemoTransport()
        client = GamingControllerClient("https://controller.example", TOKEN, transport=transport)
        created = client.create_session(
            device_id=DEMO_DEVICE_ID,
            expires_at="2026-10-30T12:00:00Z",
            idempotency_key="demo-start-key",
        )
        fetched = client.get_session(DEMO_SESSION_ID)
        ended = client.end_session(DEMO_SESSION_ID, idempotency_key="demo-end-key")
        self.assertEqual(created["outcome"], "accepted")
        self.assertFalse(play_confirmed(created))
        self.assertFalse(play_confirmed(fetched))
        self.assertFalse(lock_confirmed(ended))
        self.assertNotIn("/api/v1/agents/heartbeat", [path for _method, path in transport.calls])


if __name__ == "__main__":
    unittest.main()
