# Booking session API

Booking applications (Odoo, PHP, or any HTTP client) use OAuth 2.0 client credentials. They remain the system of record for customers, payments, and pricing. The controller stores authorized play windows and session lifecycle state only.

## Authentication

| Operation | Scope |
| --- | --- |
| `POST /api/v1/sessions` | `sessions:write` |
| `GET /api/v1/sessions/{session_id}` | `sessions:read` |
| `POST /api/v1/sessions/{session_id}/extend` | `sessions:write` |
| `POST /api/v1/sessions/{session_id}/end` | `sessions:write` |

The account comes from the access token claim configured as `OAUTH_ACCOUNT_CLAIM` (typically `account_id`). Never send account id in the body for authorization.

Agent routes use mutual TLS only. Booking tokens cannot call `POST /api/v1/agents/heartbeat`.

## Typical Odoo flow

1. **Provision the device** (once per PC): a provisioning integration with `devices:write` calls `POST /api/v1/devices` and completes certificate enrollment outside this API. See [agent-mtls.md](agent-mtls.md).

2. **Create a session** when a booking starts: the booking application (Odoo, PHP, or other) obtains a client-credentials token with `sessions:write` and calls:

   ```http
   POST /api/v1/sessions
   Idempotency-Key: booking-{sale_order_id}-start
   Content-Type: application/json

   {
     "device_id": "<uuid from registration>",
     "external_reference": "odoo-sale-12345",
     "expires_at": "2026-10-09T12:00:00Z"
   }
   ```

   Expect HTTP `202`, `outcome: accepted`, session `status: accepted`, and a pending `start_session` command. This does not lock the PC or confirm play.

3. **Poll session state** with `GET /api/v1/sessions/{session_id}` and `sessions:read`. Use the returned `status`, `start_confirmed`, `expires_at`, and `lock_confirmed`. Device connectivity is separate: `GET /api/v1/devices` and [agent-heartbeat.md](agent-heartbeat.md).

4. **Extend** (optional) while `status` is `active`: `POST /api/v1/sessions/{session_id}/extend` with a later `expires_at`. The controller stores `pending_expires_at` until the agent verifies the extension over heartbeat.

5. **End early** when the booking ends: `POST /api/v1/sessions/{session_id}/end` with optional `{"reason":"user_request"}`. Before play is verified, the session may become `cancelled`. After play is active, the session becomes `ending` with a pending `end_session` command.

6. **Retry safely**: repeat the same `Idempotency-Key` and body on create, extend, or end to recover from network loss.

Odoo-specific XML-RPC, payment hooks, and customer records stay in Odoo. This controller does not store prices or invoices.

## Session statuses

`pending` is a command status. It is not a session status. The session enum stays `requested`, `accepted`, `active`, `ending`, `ended`, `expired`, `failed`, and `cancelled`.

| Booking phase | Record the caller reads |
| --- | --- |
| pending | Session `accepted` (or `requested` if checks are unfinished), `start_session` command `pending`, `start_confirmed` false |
| accepted | Session `accepted`. Controller acceptance only. |
| active | Session `active` and `start_confirmed` true after a verified start result |
| expired | Session `expired` |
| ended | Session `ended` |

Cancellation before start delivery is session `cancelled`. Rejection of a start that definitively fails is session `failed`. An end that was accepted and not yet executed is session `ending`. Do not send or expect `rejected` or `canceled`.

| From | Event | To |
| --- | --- | --- |
| `requested` | checks succeed | `accepted` |
| `requested` | checks fail | `failed` |
| `requested` | end while start is not delivered | `cancelled` |
| `accepted` | verified start result | `active`, `start_confirmed` true |
| `accepted` | definitive start failure | `failed` |
| `accepted` | end after the start was offered | `ending` |
| `accepted` | end while start is still `pending` or was not delivered | `cancelled` |
| `accepted` | controller clock reaches `expires_at` | `expired` |
| `active` | end requested | `ending` |
| `active` | controller clock reaches `expires_at` | `expired` |
| `ending` | end command executed | `ended` |
| `ending` | controller clock reaches `expires_at` | `expired` |
| `ended`, `expired`, `failed`, `cancelled` | another start, extend, or end | no status change; HTTP `409` `invalid_session_transition`, or an idempotent replay of the stored end |

Extend does not change the session status. It is valid only while status is `active`, the requested `expires_at` is later than the stored one, and no extend command is `pending`, `delivered`, `acknowledged`, or `executed`. The stored field for that request is `pending_expires_at`. `expires_at` changes only after a verified extend result that is still inside the previous deadline.

## Requested access and confirmed access

`start_confirmed` is false on create. It becomes true only when a verified start result moves the session to `active`. Expiry and end do not clear it. `lock_confirmed` stays false until an authenticated enforcement result says the OS effect succeeded. `access_state` on the device (`unknown`, `locked`, `playing`) is not copied from the session status. `accepted` does not mean playing. `ended` and `expired` do not mean locked.

## Operations

| Action | Method and path | Scope |
| --- | --- | --- |
| Create a session and store `start_session` | `POST /api/v1/sessions` | `sessions:write` |
| Read the session | `GET /api/v1/sessions/{session_id}` | `sessions:read` |
| Request a later deadline | `POST /api/v1/sessions/{session_id}/extend` | `sessions:write` |
| End or cancel | `POST /api/v1/sessions/{session_id}/end` | `sessions:write` |
| Read devices, including `access_state` and `connectivity` | `GET /api/v1/devices` | `devices:read` |

There is no separate start route. Create is the start request. The account is the token's account claim. The device must already belong to that account. Another account's device or session is HTTP `404`. A missing or invalid token is HTTP `401`. A token without the required scope is HTTP `403`.

`GET /api/v1/devices/{device_id}`, `GET /api/v1/devices/{device_id}/status`, and `GET /api/v1/commands/{command_id}` are not in the published contract. See [api/future-endpoints.md](../api/future-endpoints.md). Read `access_state` from `GET /api/v1/devices` and command progress from the session body's `latest_command_id` together with `start_confirmed` and `lock_confirmed`.

## Idempotency and conflicts

`Idempotency-Key` is required on create, extend, and end. The same account, key, and body replay the stored session and command. The same key with a different body is HTTP `409` `idempotency_conflict`. A different key while that device has a non-terminal session is HTTP `409` `device_session_conflict`. A different key whose `external_reference` matches a non-terminal session in the same account is HTTP `409` `external_reference_conflict`, and `error.details` includes `session_id`. A second extend while one is outstanding is HTTP `409` `extension_in_progress`.

## Time

Send `expires_at` as UTC `YYYY-MM-DDTHH:MM:SSZ`. The controller clock decides expiry. A later agent timestamp does not extend the deadline. Command TTL is not the session deadline. A start command can become `expired` while the session stays `accepted` until `expires_at`. A duplicate request with the same key returns the current row. It does not apply the effect twice.

These cases are specified now and are not new behavior in this task:

- A command that arrives after its TTL is `expired`. That is not `failed` and not a verified effect.
- A booking retry after a timeout repeats the same key and body, then reads `outcome` and the session fields.
- Clock differences between the booking system and the controller are resolved by the controller clock on read. The booking clock is not authoritative.
- A controller restart keeps committed PostgreSQL rows, including idempotency keys. Expiry is applied on the next read. There is no in-memory session store and no background expiry worker.
- Agent restart, exactly-once command execution, and local deadline persistence remain open in ADR-001. This task does not claim those.

## Storage limits

Session create, read, extend, and end commit to PostgreSQL. A committed row is still there after the controller process starts again with the same `DATABASE_URL`. That is not recovery of an uncommitted request, and it is not proof the gaming PC applied a command. If PostgreSQL is down, the call returns HTTP `503` `storage_unavailable`. This process does not fall back to memory.

Booking HTTP does not lock or unlock Windows and does not talk to the agent. The agent polls `POST /api/v1/agents/heartbeat`. A booking response of `accepted` is controller storage only. Confirmed play is `start_confirmed: true`. A verified lock is `lock_confirmed: true`. See [agent-command-delivery.md](agent-command-delivery.md) and [LIFECYCLE.md](LIFECYCLE.md).

## Manual checks

Replace the token. The device id must belong to that token's account. `expires_at` must be in the future. Use the booking HTTPS front door:

```text
curl -sS -D - https://booking.example/api/v1/sessions \
  -H "Authorization: Bearer REPLACE_WITH_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: booking-98421-start" \
  -d '{"device_id":"REPLACE_WITH_DEVICE_ID","external_reference":"booking-98421","expires_at":"2026-10-28T12:00:00Z"}'
```

Expect HTTP `202`, `outcome` `accepted`, session `status` `accepted`, `start_confirmed` false, and command `status` `pending`. Repeat the same command and expect the same session id. Then:

```text
curl -sS https://booking.example/api/v1/sessions/REPLACE_WITH_SESSION_ID \
  -H "Authorization: Bearer REPLACE_WITH_ACCESS_TOKEN"

curl -sS https://booking.example/api/v1/devices \
  -H "Authorization: Bearer REPLACE_WITH_ACCESS_TOKEN"

curl -sS -D - https://booking.example/api/v1/sessions/REPLACE_WITH_SESSION_ID/end \
  -H "Authorization: Bearer REPLACE_WITH_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: booking-98421-end" \
  -d '{"reason":"user_request"}'
```

The session read needs `sessions:read`. The device list needs `devices:read`. Ending while the start command is still `pending` returns HTTP `200`, session `cancelled`, and `lock_confirmed` false. That does not lock the PC.

Normative rules: [../contracts/session-lifecycle.md](../contracts/session-lifecycle.md) and [../api/openapi.yaml](../api/openapi.yaml).
