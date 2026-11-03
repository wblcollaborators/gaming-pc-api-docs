# Developer handover guide

This is the integration contract for third-party booking applications. The
Gaming Controller, REST API, and PC Agent are owned by the platform. You own
your booking product, customers, payments, PC assignment, and business rules.

Python, PHP, Laravel, Node.js, Java, C#, and cURL all call the same HTTPS JSON
API. There is no language-specific controller API.

Start with [../guides/QUICKSTART.md](../guides/QUICKSTART.md), then use
[INTEGRATION.md](INTEGRATION.md) and [LIFECYCLE.md](LIFECYCLE.md) for
field-level rules. The OpenAPI file is [../api/openapi.yaml](../api/openapi.yaml).
Implemented versus unavailable operations are listed in
[../CAPABILITIES.json](../CAPABILITIES.json).

## What you receive from the operator

| Item | Example shape | Notes |
| --- | --- | --- |
| Controller base URL | `https://controller.example` | Paths below are `/api/v1/...`. Cloud and on-premise keep the same paths. |
| OAuth token URL | the operator identity provider | The controller does **not** issue tokens and has no `/token` route. The OpenAPI `tokenUrl` is a placeholder. |
| Client id and client secret | confidential client credentials | Server-to-server only. Never embed these in a browser, mobile app, or source repository. |
| Audience | `gaming-pc-agent-api` unless the operator says otherwise | Must match the access-token `aud` claim. |
| Account | bound to your OAuth client | You never send `account_id`. The controller reads it from the token. |

Use TLS 1.2 or later. Verify server certificates. Send HTTP methods in uppercase (`GET`, `POST`). Some reverse proxies reject mixed-case methods with an HTML 400.

## Required permissions

Ask the operator for a **booking** client with:

- `devices:read`
- `sessions:read`
- `sessions:write`

`sessions:write` does not include `sessions:read`. You need both to start a
session and then poll it.

Do not request `devices:write` for booking software. That scope registers
devices and returns one-time enrollment material. It belongs to a separate
provisioning client.

`commands:read` is reserved for a command-read route that is not served yet.
Polling `GET /api/v1/sessions/{session_id}` does not require it.

## Authenticate

1. Exchange client id and client secret at the operator token URL (OAuth 2.0
   client credentials, RFC 6749 section 4.4).
2. Send `Authorization: Bearer <access_token>` on every booking call except
   health.
3. When the token expires, request another from the identity provider. The
   controller does not refresh tokens. See [jwt-access-tokens.md](jwt-access-tokens.md).

HTTP 401 means the token failed verification. HTTP 403 means the token verified
but the account, client id, or required scope is missing.

## List PCs

```http
GET /api/v1/devices?limit=50&connectivity=online
Authorization: Bearer ACCESS_TOKEN
```

Each item includes nested `status`:

- `connectivity`: `offline` or `online`
- `access_state`: `unknown`, `locked`, or `playing`
- `status_stale`: when true, treat `access_state` as unknown

The list does not reserve a PC. Your application chooses which device to
assign. A newly registered PC is `offline` with `access_state` `unknown` until
the agent heartbeats.

There is no `GET /api/v1/devices/{device_id}`. Filter the list.

## Start, extend, and end sessions

Create **is** the start request. There is no separate start route.

```http
POST /api/v1/sessions
Authorization: Bearer ACCESS_TOKEN
Content-Type: application/json
Idempotency-Key: booking-98421-start

{
  "device_id": "22222222-2222-4222-8222-222222222222",
  "external_reference": "booking-98421",
  "expires_at": "2026-10-30T12:00:00Z"
}
```

HTTP 202 with `outcome: accepted` means the controller stored a
`start_session` command. It does **not** mean the PC is unlocked.

```http
GET /api/v1/sessions/{session_id}
Authorization: Bearer ACCESS_TOKEN
```

The GET body is the session document. It is not wrapped in `session`.

```http
POST /api/v1/sessions/{session_id}/extend
Idempotency-Key: booking-98421-extend

{"expires_at": "2026-10-30T13:00:00Z"}
```

HTTP 202 stores `pending_expires_at`. The authorized `expires_at` changes after
a verified agent result.

```http
POST /api/v1/sessions/{session_id}/end
Idempotency-Key: booking-98421-end

{"reason": "user_request"}
```

Empty body is treated as `user_request`. Allowed reasons are `user_request` and
`operator`.

Persist `session_id`, `command_id`, and each `Idempotency-Key` on your existing
booking row. Do not create a second session model inside the controller.

## Verify actual PC lock and unlock

| Question | Field to wait for | What is not enough |
| --- | --- | --- |
| Did the PC unlock for play? | `start_confirmed: true` and status `active` | HTTP 202, command `pending`/`acknowledged`/`executed`, device `access_state` |
| Did the PC restrict after end? | `lock_confirmed: true` | Session status `ended` or `expired`, device `access_state: locked` |

`access_state` is a heartbeat observation. It is independent of session status
and is not a confirmed lock.

Do not call `POST /api/v1/agents/heartbeat`. That route is mutual TLS for the
Windows agent. A booking bearer token receives HTTP 403.

## Offline PCs

If `connectivity` is `offline` or `status_stale` is true, do not tell a
customer the PC is ready. You may still create a session; the start command
waits for the agent and can expire. Poll GET session until `start_confirmed`
or a terminal session/command status.

## Rate limits

Your traffic is counted against the platform account in the access token, not
against your source IP. Session create, extend, and end share one write
budget. Listing devices uses a separate read budget. The operator sets the
numeric values.

HTTP 429 `rate_limited` includes `Retry-After` in seconds. Wait that long, then
retry the same `Idempotency-Key` and body. A stored key replay does not consume
a new slot.

## Idempotency and retries

`Idempotency-Key` is required on POST devices, sessions, extend, and end.
Pattern: `^[A-Za-z0-9._:-]{8,128}$`.

- Timeout or HTTP 503: retry the **same** method, path, key, and JSON body.
- HTTP 429 `rate_limited`: wait `Retry-After` seconds, then retry the same
  method, path, key, and JSON body. Limits are per platform account, not per
  HTTP connection. A replay of a stored Idempotency-Key does not consume a
  new slot.
- Same key with a different body: HTTP 409 `idempotency_conflict`.
- GET is safe to retry.
- 401 after expiry: obtain a new access token, then retry.
- 400, 403, 404, 409, 415, 422: do not retry the same input.

## Error codes

Error body:

```json
{
  "error": {
    "code": "session_not_found",
    "message": "The session is not in this account.",
    "request_id": "77777777-7777-4777-8777-777777777777",
    "details": []
  }
}
```

| HTTP | code | Meaning |
| --- | --- | --- |
| 400 | `invalid_json`, `validation_error`, `idempotency_key_required` | Fix the request. |
| 401 | `unauthorized` | Missing or invalid bearer token. |
| 403 | `forbidden` | Token verified; scope, client, or account is insufficient. |
| 404 | `not_found`, `device_not_found`, `session_not_found` | Unknown path, or the object is not in this account. Other accounts look the same. |
| 409 | `device_session_conflict`, `external_reference_conflict`, `idempotency_conflict`, `invalid_session_transition`, `extension_in_progress` | Conflicting stored state. |
| 415 | `unsupported_media_type` | Send `Content-Type: application/json`. |
| 422 | `validation_error` | Deadline is not in the future, or not later than the current deadline. |
| 429 | `rate_limited` | Wait `Retry-After`, then retry the same Idempotency-Key. |
| 503 | `storage_unavailable` | Retry with the same Idempotency-Key. |

Include `error.request_id` when you contact the operator.

## Do not call these routes

Not in the published contract and **not served** by this controller:

- `GET /api/v1/devices/{device_id}`
- `GET /api/v1/devices/{device_id}/status`
- `GET /api/v1/commands/{command_id}`

Unauthenticated calls receive HTTP 401. A valid booking token receives HTTP
404 `not_found` with the Error schema. Do not treat that body as
`session_not_found`.

Agent-only:

- `POST /api/v1/agents/heartbeat`

## Working examples

| Language | File |
| --- | --- |
| Python | `python/gaming_controller_client.py`, `python/example_odoo_service.py`, `python/demo.py` |
| PHP 8.1+ | `php/GamingControllerClient.php`, `php/example.php`, `php/demo.php` |
| cURL | `curl-examples.sh`, `curl-demo.sh` |

`demo.py` / `demo.php` / `curl-demo.sh` are local canned walks. They do not
control a Windows PC. Live helpers verify TLS and do not log access tokens.

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for the full table. Short form:
HTML 400 means a mixed-case method; 401 is token verification; 403 on GET
session means add `sessions:read`; HTTP 202 is not unlocked play; wait for
`lock_confirmed` after end.
