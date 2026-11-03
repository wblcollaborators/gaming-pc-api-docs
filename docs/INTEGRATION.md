# Universal API integration guide

This kit is for booking applications that already own customers, payments, PC assignment, and business rules. The controller owns device communication, session execution, access enforcement, and command acknowledgements.

Python, PHP, Laravel, Odoo 19, Node.js, and cURL use the same HTTPS JSON contract. There is no language-specific controller API and no second session model.

Authoritative HTTP schemas live in `api/openapi.yaml`. That file lists only
operations this process serves. Planned routes that are not served are in
`api/future-endpoints.md` and `CAPABILITIES.json`.

## Ownership boundary

| Owner | Owns | Does not own |
| --- | --- | --- |
| Booking application | Bookings, customers, payments, which PC to assign, refunds, café hours | Device certificates, Windows overlay, command TTL, heartbeat |
| Controller | Devices in an account, session records, commands, agent mTLS, confirmed play and lock flags | Customer records, invoices, seat maps |

`external_reference` is the booking application's own booking identifier. The controller stores it as an opaque string. Callers never send `account_id`; the controller reads it from the access token.

## Implemented booking operations

| Method | Path | Scope | What a 2xx means |
| --- | --- | --- | --- |
| GET | `/api/v1/health` | none | This process answered. It is not device or lock state. |
| GET | `/api/v1/devices` | `devices:read` | Devices in this token's account, including nested `status`. |
| POST | `/api/v1/devices` | `devices:write` | A device record was stored. The PC was not contacted. |
| POST | `/api/v1/sessions` | `sessions:write` | A session and a pending `start_session` command were stored. Create is the start request. There is no separate start route. |
| GET | `/api/v1/sessions/{session_id}` | `sessions:read` | Current session document. The body is not wrapped in `session`. |
| POST | `/api/v1/sessions/{session_id}/extend` | `sessions:write` | A later deadline was requested. |
| POST | `/api/v1/sessions/{session_id}/end` | `sessions:write` | An end was requested. |

POST create, extend, and end return `{outcome, session, command}`. GET session returns the session object only.

`sessions:write` does not imply `sessions:read`. Booking clients need both.

## Planned and not in this contract

These paths are documented only in `api/future-endpoints.md`. They are not
OpenAPI operations and this process does not serve them:

- `GET /api/v1/devices/{device_id}`
- `GET /api/v1/devices/{device_id}/status`
- `GET /api/v1/commands/{command_id}`

Until they exist, list devices and poll `GET /api/v1/sessions/{session_id}`.
Unauthenticated calls receive HTTP 401. A valid token receives HTTP 404
`not_found` with the Error schema. Do not treat that 404 as `session_not_found`.

## Agent operation (not a booking call)

`POST /api/v1/agents/heartbeat` is mTLS only. The client certificate must match `device_id`. A booking bearer token receives HTTP 403. Booking software must not call this route.

## Authentication

The controller does not issue tokens and has no `/token` route. The OpenAPI token URL is a placeholder for the operator identity provider.

### Booking and provisioning (OAuth 2.0 client credentials)

1. The booking or provisioning client authenticates to the operator IdP with its client id and client secret (RFC 6749 section 4.4).
2. The IdP returns a JWT access token (RFC 6750).
3. The caller sends `Authorization: Bearer <access_token>` on `/api/v1` booking routes.
4. The controller fetches JWKS from the configured issuer, verifies RS/ES256–512, `iss`, `aud`, and `exp`, then reads `account_id` and scopes.

Required token claims:

- `iss` matches `OAUTH_ISSUER`
- `aud` is the controller API (`gaming-pc-agent-api` in the lab)
- `exp` is present and in the future
- `account_id` is a UUID (claim name is `OAUTH_ACCOUNT_CLAIM`)
- `client_id` or `azp`
- `scope` as a space-separated string, or an array of strings

HTTP 401 means the token failed signature, issuer, audience, or expiry checks. HTTP 403 means the token verified but the account, client id, or required scope is missing.

Recommended booking scopes: `devices:read`, `sessions:read`, `sessions:write`, `commands:read`. Provisioning uses a separate client with `devices:write`. Do not share one production secret between booking software and provisioning software, or between two customers.

### Windows agent (mTLS)

The agent presents a device-bound client certificate during TLS. It does not send a booking bearer token. A bearer token on an agent route is rejected. Heartbeat `command_results` are how the controller learns confirmed play and lock. That channel is not available to booking HTTP.

### Transport

Production booking traffic uses HTTPS. TLS 1.2 or later is required. Agent traffic uses HTTPS with mutual TLS. The clients in this kit verify TLS certificates. They do not disable verification and they do not log bearer tokens, client secrets, or enrollment material.

Cloud and on-premise controllers keep the same paths. Change the host, not the contract.

## Request rules

- `Content-Type: application/json` when a JSON body is sent. Mixed-case HTTP methods such as `Post` are rejected by some reverse proxies with HTML 400. Send `GET` and `POST` in uppercase.
- `Idempotency-Key` is required on POST devices, sessions, extend, and end. Pattern `^[A-Za-z0-9._:-]{8,128}$`. Reuse the same key and the same body on retry. A different body with the same key returns 409 `idempotency_conflict`.
- `external_reference` is optional, 1–256 characters when present. Explicit JSON `null` is rejected.
- `expires_at` is UTC ISO 8601 with a `Z` suffix, for example `2026-10-30T12:00:00Z`.
- Unknown JSON fields are rejected.
- Clients must ignore unknown response fields.
- GET is safe to retry.

## Outcomes versus confirmed device effects

| HTTP | `outcome` | Meaning |
| --- | --- | --- |
| 202 | `accepted` | Stored. The device effect is unconfirmed. |
| 200 | `effect_confirmed` | An earlier verified agent result already confirmed the effect. |
| 200 | `effect_not_applied` | The operation finished without the requested device effect. Read `session.status`. |

Confirmed play is `session.start_confirmed: true`. A verified lock is `session.lock_confirmed: true`. Session status `ended` or `expired` is not a lock. Device `access_state` is an observation (`unknown`, `locked`, `playing`) and is independent of session status. `command.device_effect_confirmed` is true only when command status is `succeeded`.

Command statuses that booking software may see on POST responses: `pending`, `delivered`, `acknowledged`, `executed`, `succeeded`, `failed`, `expired`, `cancelled`. `pending` is a command status, not a session status.

Session statuses: `requested`, `accepted`, `active`, `ending`, `ended`, `expired`, `failed`, `cancelled`.

## Rate limits

Limits are per platform `account_id`, not per HTTP connection or API key
string. Session create, extend, and end share one write budget. Device
registration has a separate write budget. GET booking reads have a separate
read budget. Health and agent heartbeat are not limited.

Numeric limits are operator configuration. When you receive HTTP 429
`rate_limited`, wait `Retry-After` seconds, then retry the same method, path,
`Idempotency-Key`, and JSON body. A stored Idempotency-Key replay does not
consume a new slot, so a timeout retry is safe.

## Error handling and retries

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

| HTTP | code | Retry? |
| --- | --- | --- |
| 400 | `invalid_json`, `validation_error`, `idempotency_key_required` | No. Fix the request. |
| 401 | `unauthorized` | No, except after obtaining a new token from the IdP. |
| 403 | `forbidden` | No. |
| 404 | `device_not_found`, `session_not_found` | No. Another account's objects also return 404. |
| 409 | `device_session_conflict`, `external_reference_conflict`, `idempotency_conflict`, `invalid_session_transition`, `extension_in_progress` | No with the same conflicting input. |
| 415 | `unsupported_media_type` | No. |
| 422 | `validation_error` (deadline rules) | No. |
| 429 | `rate_limited` | Yes, after `Retry-After` seconds, with the same Idempotency-Key and body. |
| 503 | `storage_unavailable` | Yes, with the same Idempotency-Key and body. |

Network timeouts on POST are retried with the same Idempotency-Key and body. A replay returns the original stored result.

## Device listing and access state

`GET /api/v1/devices` accepts `limit` (1–100), `cursor`, `platform` (`windows` or `linux`), and `connectivity` (`offline` or `online`). Each item includes `status`:

- `connectivity`: `offline` or `online` from heartbeat freshness
- `access_state`: `unknown`, `locked`, or `playing`
- `last_reported_access_state`: last observation, not a confirmed lock
- `status_stale`: when true, treat `access_state` as unknown
- `stale_after_seconds`: freshness window used by the controller

A newly registered device is `offline` with `access_state` `unknown` until a heartbeat is accepted.

## Selecting a PC

Booking software chooses an available PC using its own assignment rules plus this list. The controller does not reserve a PC until `POST /api/v1/sessions` succeeds. A device that already has a non-terminal session returns 409 `device_session_conflict`.

## Clients in this kit

| Language | File | Use |
| --- | --- | --- |
| Python | `python/gaming_controller_client.py` | Odoo 19 or any Python 3.10+ service. Standard library only. |
| Python | `python/example_odoo_service.py` | Copy-paste usage. Not an Odoo module. |
| PHP | `php/GamingControllerClient.php` | Laravel or plain PHP 8.1+. |
| PHP | `php/example.php` | Copy-paste usage. |
| cURL | `curl-examples.sh` | Other languages. |

All three send the same method, path, headers, and JSON. They do not call heartbeat or the unimplemented GET routes.

Do not put client secrets, recovery secrets, or enrollment tokens in source, logs, or tickets.

## API versioning and compatibility

The version is in the path: `/api/v1`. A later major version would be a new
path and a new OpenAPI document.

Within v1:

- Ignore unknown response fields.
- Unknown request fields are rejected with HTTP 400.
- Implemented paths and session semantics in this kit stay stable.
- Routes in `CAPABILITIES.json` `planned_not_in_contract` are not part of v1
  compatibility. They are not served.

Cloud and on-premise deployments change the host and keep these paths.
