# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Weblytic Labs
# See ../../LICENSE-EXAMPLES-MIT.md
"""HTTPS JSON client for the Universal Gaming PC Agent Controller.

Booking applications obtain an OAuth 2.0 access token from the operator
identity provider. This module does not mint tokens and does not call
agent mTLS routes. Python, PHP, and cURL use the same paths and schemas.
"""

from __future__ import annotations

import json
import re
import secrets
import ssl
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen
from uuid import UUID

IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
EXPIRES_AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
HEALTH_PATH = "/api/v1/health"
DEVICES_PATH = "/api/v1/devices"
SESSIONS_PATH = "/api/v1/sessions"
RETRYABLE_STATUS = frozenset({503, 429})
RETRYABLE_CODES = frozenset({"storage_unavailable", "rate_limited"})
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "testserver"})

Transport = Callable[[str, str, dict[str, str], bytes | None, float], tuple[int, Mapping[str, str], bytes]]


class ControllerApiError(Exception):
    """A controller JSON error or an unexpected HTTP failure."""

    def __init__(
        self,
        *,
        status_code: int,
        error_code: str,
        message: str,
        request_id: str | None,
        details: list[dict[str, Any]],
        body: Any,
    ) -> None:
        super().__init__(f"HTTP {status_code} {error_code}: {message}")
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.request_id = request_id
        self.details = details
        self.body = body

    def is_retryable(self) -> bool:
        return self.status_code in RETRYABLE_STATUS or self.error_code in RETRYABLE_CODES


def new_idempotency_key(prefix: str = "booking") -> str:
    """Return a unique Idempotency-Key. Do not reuse it for a different body."""
    token = secrets.token_hex(8)
    key = f"{prefix}-{token}"
    if IDEMPOTENCY_KEY_RE.fullmatch(key) is None:
        raise ValueError("generated Idempotency-Key does not match the required pattern")
    return key


def session_document(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return the session object from a POST result or an unwrapped GET body."""
    nested = payload.get("session")
    if isinstance(nested, dict) and "session_id" in nested:
        return nested
    return payload


def play_confirmed(payload: Mapping[str, Any]) -> bool:
    return bool(session_document(payload).get("start_confirmed") is True)


def lock_confirmed(payload: Mapping[str, Any]) -> bool:
    return bool(session_document(payload).get("lock_confirmed") is True)


class GamingControllerClient:
    """Booking-side client. Pass a bearer token obtained from the operator IdP."""

    def __init__(
        self,
        base_url: str,
        access_token: str,
        *,
        timeout_seconds: float = 30,
        transport: Transport | None = None,
    ) -> None:
        parsed = urlparse(base_url.strip())
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise ValueError("base_url must be an absolute http(s) URL")
        if parsed.scheme == "http" and parsed.hostname not in _LOOPBACK_HOSTS:
            raise ValueError("non-loopback controller URLs must use https")
        if not access_token:
            raise ValueError("access_token is required")
        root = urlunparse((parsed.scheme, parsed.netloc, "", "", "", "")).rstrip("/")
        self.base_url = root
        self._access_token = access_token
        self.timeout_seconds = timeout_seconds
        self._transport = transport or _urllib_transport

    def __repr__(self) -> str:
        return f"GamingControllerClient(base_url={self.base_url!r})"

    def health(self) -> dict[str, Any]:
        return self._request("GET", HEALTH_PATH, auth=False)

    def list_devices(
        self,
        *,
        limit: int | None = None,
        cursor: str | None = None,
        platform: str | None = None,
        connectivity: str | None = None,
    ) -> dict[str, Any]:
        query: dict[str, str] = {}
        if limit is not None:
            query["limit"] = str(limit)
        if cursor is not None:
            query["cursor"] = cursor
        if platform is not None:
            query["platform"] = platform
        if connectivity is not None:
            query["connectivity"] = connectivity
        path = DEVICES_PATH
        if query:
            path = f"{DEVICES_PATH}?{urlencode(query)}"
        return self._request("GET", path)

    def create_session(
        self,
        *,
        device_id: str,
        expires_at: str,
        idempotency_key: str,
        external_reference: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "device_id": _uuid(device_id, "device_id"),
            "expires_at": _expires_at(expires_at),
        }
        if external_reference is not None:
            body["external_reference"] = external_reference
        return self._request("POST", SESSIONS_PATH, json_body=body, idempotency_key=idempotency_key)

    def get_session(self, session_id: str) -> dict[str, Any]:
        return self._request("GET", f"{SESSIONS_PATH}/{_uuid(session_id, 'session_id')}")

    def extend_session(self, session_id: str, *, expires_at: str, idempotency_key: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"{SESSIONS_PATH}/{_uuid(session_id, 'session_id')}/extend",
            json_body={"expires_at": _expires_at(expires_at)},
            idempotency_key=idempotency_key,
        )

    def end_session(
        self,
        session_id: str,
        *,
        idempotency_key: str,
        reason: str | None = "user_request",
    ) -> dict[str, Any]:
        json_body: dict[str, Any] | None = None
        if reason is not None:
            json_body = {"reason": reason}
        return self._request(
            "POST",
            f"{SESSIONS_PATH}/{_uuid(session_id, 'session_id')}/end",
            json_body=json_body,
            idempotency_key=idempotency_key,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        auth: bool = True,
    ) -> dict[str, Any]:
        if method != method.upper() or method not in {"GET", "POST"}:
            raise ValueError("method must be GET or POST in uppercase")
        headers = {"Accept": "application/json"}
        raw: bytes | None = None
        if json_body is not None:
            raw = json.dumps(json_body, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if auth:
            headers["Authorization"] = f"Bearer {self._access_token}"
        if idempotency_key is not None:
            if IDEMPOTENCY_KEY_RE.fullmatch(idempotency_key) is None:
                raise ValueError("Idempotency-Key does not match the required pattern")
            headers["Idempotency-Key"] = idempotency_key
        url = f"{self.base_url}{path}"
        status, response_headers, content = self._transport(
            method,
            url,
            headers,
            raw,
            self.timeout_seconds,
        )
        payload = _decode_json(content)
        if 200 <= status < 300:
            if not isinstance(payload, dict):
                raise ControllerApiError(
                    status_code=status,
                    error_code="invalid_response",
                    message="The controller response is not a JSON object.",
                    request_id=_header(response_headers, "x-request-id"),
                    details=[],
                    body=payload,
                )
            return payload
        raise _error_from_body(status, payload, response_headers)


def fastapi_transport(test_client: Any) -> Transport:
    """Adapter for FastAPI TestClient. Used by automated tests only."""

    def send(
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout: float,
    ) -> tuple[int, Mapping[str, str], bytes]:
        del timeout
        parsed = urlparse(url)
        path = parsed.path
        if parsed.query:
            path = f"{path}?{parsed.query}"
        response = test_client.request(method, path, headers=headers, content=body)
        return response.status_code, response.headers, response.content

    return send


def _urllib_transport(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None,
    timeout: float,
) -> tuple[int, Mapping[str, str], bytes]:
    request = Request(url, data=body, headers=headers, method=method)
    context = ssl.create_default_context()
    try:
        with urlopen(request, timeout=timeout, context=context) as response:
            return response.status, dict(response.headers), response.read()
    except HTTPError as exc:
        return exc.code, dict(exc.headers or {}), exc.read()
    except URLError as exc:
        raise ControllerApiError(
            status_code=0,
            error_code="network_error",
            message="The controller could not be reached.",
            request_id=None,
            details=[],
            body={"reason": str(exc.reason)},
        ) from exc


def _uuid(value: str, field: str) -> str:
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise ValueError(f"{field} must be a UUID") from exc


def _expires_at(value: str) -> str:
    if EXPIRES_AT_RE.fullmatch(value) is None:
        raise ValueError("expires_at must be UTC ISO 8601 with a Z suffix")
    return value


def _decode_json(content: bytes) -> Any:
    if not content:
        return None
    try:
        return json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"raw": content[:200].decode("utf-8", errors="replace")}


def _header(headers: Mapping[str, str], name: str) -> str | None:
    lower = name.lower()
    for key, value in headers.items():
        if key.lower() == lower:
            return value
    return None


def _error_from_body(status: int, payload: Any, headers: Mapping[str, str]) -> ControllerApiError:
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        details = error.get("details") or []
        if not isinstance(details, list):
            details = []
        return ControllerApiError(
            status_code=status,
            error_code=str(error.get("code") or "unknown_error"),
            message=str(error.get("message") or "The controller rejected the request."),
            request_id=error.get("request_id") or _header(headers, "x-request-id"),
            details=details,
            body=payload,
        )
    return ControllerApiError(
        status_code=status,
        error_code="unexpected_error",
        message="The controller returned a non-JSON error.",
        request_id=_header(headers, "x-request-id"),
        details=[],
        body=payload,
    )
