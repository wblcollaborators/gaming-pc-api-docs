#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Weblytic Labs
# See ../LICENSE-EXAMPLES-MIT.md
# Print the booking HTTP contract without calling a controller or a Windows PC.
# Live calls: export ACCESS_TOKEN and run curl-examples.sh instead.

set -eu

cat <<'EOF'
demo_mode printed_http_only
This script does not connect to a controller and does not control a Windows PC.

GET /api/v1/health
-> {"status":"ok"}
   Process liveness only.

GET /api/v1/devices?limit=50
Authorization: Bearer ACCESS_TOKEN
-> items[].status.connectivity may be offline in demo data.

POST /api/v1/sessions
Idempotency-Key: booking-98421-start
{"device_id":"...","external_reference":"booking-98421","expires_at":"...Z"}
-> HTTP 202 {"outcome":"accepted","session":{"start_confirmed":false,...}}
   HTTP 202 is stored, not unlocked play.

GET /api/v1/sessions/{session_id}
-> unwrapped session document. Wait for start_confirmed true on a live lab.

POST /api/v1/sessions/{session_id}/extend
POST /api/v1/sessions/{session_id}/end
-> HTTP 202 stored. lock_confirmed true only after a verified agent result.

Errors to handle: 401 unauthorized, 403 forbidden, 404 session_not_found,
429 rate_limited (Retry-After), 503 storage_unavailable.

Do not call POST /api/v1/agents/heartbeat
Do not call GET /api/v1/devices/{device_id}
Do not call GET /api/v1/commands/{command_id}
EOF
