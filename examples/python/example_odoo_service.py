# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Weblytic Labs
# See ../../LICENSE-EXAMPLES-MIT.md
"""Copy-paste usage for an Odoo 19 service.

This file is not an Odoo module and does not change any booking models.
Obtain the access token from the operator identity provider, then call the
same HTTPS contract that PHP and cURL use. For a local walk without a PC,
run demo.py (canned responses, start_confirmed stays false).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from gaming_controller_client import (
    ControllerApiError,
    GamingControllerClient,
    lock_confirmed,
    new_idempotency_key,
    play_confirmed,
    session_document,
)


def _future_deadline(minutes: int = 60) -> str:
    moment = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def start_play(
    controller_url: str,
    access_token: str,
    device_id: str,
    booking_reference: str,
    minutes: int = 60,
) -> dict:
    client = GamingControllerClient(controller_url, access_token)
    created = client.create_session(
        device_id=device_id,
        expires_at=_future_deadline(minutes),
        external_reference=booking_reference,
        idempotency_key=new_idempotency_key(booking_reference),
    )
    session = session_document(created)
    # Persist session["session_id"], created["command"]["command_id"], and the Idempotency-Key
    # on the existing booking row. HTTP 202 accepted is not unlocked play.
    return {
        "session_id": session["session_id"],
        "status": session["status"],
        "play_confirmed": play_confirmed(created),
        "outcome": created["outcome"],
    }


def wait_for_play(client: GamingControllerClient, session_id: str) -> dict:
    session = client.get_session(session_id)
    return {
        "status": session["status"],
        "play_confirmed": play_confirmed(session),
    }


def add_time(client: GamingControllerClient, session_id: str, extra_minutes: int) -> dict:
    return client.extend_session(
        session_id,
        expires_at=_future_deadline(extra_minutes),
        idempotency_key=new_idempotency_key("extend"),
    )


def stop_play(client: GamingControllerClient, session_id: str) -> dict:
    ended = client.end_session(session_id, idempotency_key=new_idempotency_key("end"))
    session = client.get_session(session_id)
    return {
        "outcome": ended["outcome"],
        "status": session["status"],
        "lock_confirmed": lock_confirmed(session),
    }


def handle_controller_error(exc: ControllerApiError) -> str:
    if exc.is_retryable():
        return "retry_same_idempotency_key"
    if exc.status_code in {401, 403}:
        return "authorization_failed"
    return exc.error_code
