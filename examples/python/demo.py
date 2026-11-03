# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Weblytic Labs
# See ../../LICENSE-EXAMPLES-MIT.md
"""Walk the booking API locally without a controller or a Windows PC.

Usage:

    python demo.py

This process does not mint tokens, does not call heartbeat, and never sets
start_confirmed or lock_confirmed to true.
"""

from __future__ import annotations

from demo_transport import DEMO_DEVICE_ID, DEMO_SESSION_ID, DemoTransport
from gaming_controller_client import (
    ControllerApiError,
    GamingControllerClient,
    lock_confirmed,
    new_idempotency_key,
    play_confirmed,
    session_document,
)

# Placeholder only. DemoTransport never sends this value on the network.
DEMO_TOKEN = "demo-access-token-not-a-credential"


def main() -> None:
    transport = DemoTransport()
    client = GamingControllerClient("https://controller.example", DEMO_TOKEN, transport=transport)

    health = client.health()
    devices = client.list_devices(limit=50)
    created = client.create_session(
        device_id=DEMO_DEVICE_ID,
        expires_at="2026-10-30T12:00:00Z",
        external_reference="demo-booking-98421",
        idempotency_key=new_idempotency_key("demo-start"),
    )
    session = client.get_session(DEMO_SESSION_ID)
    extended = client.extend_session(
        DEMO_SESSION_ID,
        expires_at="2026-10-30T13:00:00Z",
        idempotency_key=new_idempotency_key("demo-extend"),
    )
    ended = client.end_session(DEMO_SESSION_ID, idempotency_key=new_idempotency_key("demo-end"))

    print("demo_mode local_canned_responses")
    print(f"health {health['status']}")
    print(f"devices {len(devices['items'])} connectivity={devices['items'][0]['status']['connectivity']}")
    print(f"create outcome={created['outcome']} http_meaning=stored_not_unlocked")
    print(f"play_confirmed {play_confirmed(session)}")
    print(f"extend outcome={extended['outcome']} pending_expires_at={session_document(extended).get('pending_expires_at')}")
    print(f"end outcome={ended['outcome']} lock_confirmed={lock_confirmed(ended)}")
    print("demo_never_controls_a_windows_pc")
    print("poll_start_confirmed_on_a_lab_controller_before_telling_a_customer_the_pc_is_ready")


def describe_error(exc: ControllerApiError) -> str:
    if exc.is_retryable():
        return "retry_same_idempotency_key"
    if exc.status_code == 401:
        return "request_a_new_access_token"
    if exc.status_code in {403, 404}:
        return "do_not_retry_same_input"
    return exc.error_code


if __name__ == "__main__":
    main()
