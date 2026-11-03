#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Weblytic Labs
# See ../LICENSE-EXAMPLES-MIT.md
# Booking HTTPS examples for the Universal Gaming PC Agent Controller.
# Python and PHP send these same methods, paths, headers, and JSON bodies.
# Export CONTROLLER_URL, ACCESS_TOKEN, DEVICE_ID, and SESSION_ID. Do not print ACCESS_TOKEN.

set -euo pipefail

CONTROLLER_URL="${CONTROLLER_URL:-https://controller.example}"
DEVICE_ID="${DEVICE_ID:-22222222-2222-4222-8222-222222222222}"
SESSION_ID="${SESSION_ID:-33333333-3333-4333-8333-333333333333}"
EXPIRES_AT="${EXPIRES_AT:-2026-10-30T12:00:00Z}"
EXTEND_EXPIRES_AT="${EXTEND_EXPIRES_AT:-2026-10-30T13:00:00Z}"
EXTERNAL_REFERENCE="${EXTERNAL_REFERENCE:-booking-98421}"

if [[ -z "${ACCESS_TOKEN:-}" ]]; then
  echo "export ACCESS_TOKEN from the operator identity provider before running these examples." >&2
  echo "The controller does not issue booking tokens." >&2
  exit 1
fi

# 1. Process health. No bearer token.
curl -sS -X GET "${CONTROLLER_URL}/api/v1/health"

# 2. List devices and observed access state.
curl -sS -X GET "${CONTROLLER_URL}/api/v1/devices?limit=50&connectivity=online" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Accept: application/json"

# 3. Create/start a session. HTTP 202 accepted is not unlocked play.
curl -sS -X POST "${CONTROLLER_URL}/api/v1/sessions" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: ${EXTERNAL_REFERENCE}-start" \
  --data "{\"device_id\":\"${DEVICE_ID}\",\"external_reference\":\"${EXTERNAL_REFERENCE}\",\"expires_at\":\"${EXPIRES_AT}\"}"

# 4. Poll confirmed execution. GET returns the session document unwrapped.
curl -sS -X GET "${CONTROLLER_URL}/api/v1/sessions/${SESSION_ID}" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Accept: application/json"

# 5. Extend the authorized deadline. Confirmed after a verified agent result.
curl -sS -X POST "${CONTROLLER_URL}/api/v1/sessions/${SESSION_ID}/extend" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: ${EXTERNAL_REFERENCE}-extend" \
  --data "{\"expires_at\":\"${EXTEND_EXPIRES_AT}\"}"

# 6. End the session. lock_confirmed is the verified restriction.
curl -sS -X POST "${CONTROLLER_URL}/api/v1/sessions/${SESSION_ID}/end" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: ${EXTERNAL_REFERENCE}-end" \
  --data '{"reason":"user_request"}'

# Retry a timed-out POST with the same Idempotency-Key and the same body.
# HTTP 401: request a new access token from the operator IdP, then retry.
# HTTP 403 or 404: do not retry the same input.
# HTTP 429: wait Retry-After seconds, then retry the same Idempotency-Key.
# HTTP 503: retry the same Idempotency-Key and body.
# Do not call POST /api/v1/agents/heartbeat from booking software.
# Do not call GET /api/v1/commands/{command_id}; that route is not served yet.
