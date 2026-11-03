# Developer quick start

This walkthrough uses the implemented `/api/v1` contract only. Python, PHP,
and cURL send the same HTTPS JSON. There is no language-specific controller
API and no demonstration route on the controller.

GitHub hosts this documentation. It is **not** a running API. For live calls,
use the deployed controller HTTPS base URL and OAuth credentials the operator
gives you.

HTTP **202** `outcome: accepted` means the controller stored a command. It
does **not** mean the PC unlocked.

## Safe demo (no Windows PC)

Run the canned clients. They never open a network connection to a controller
or a gaming PC, and they never set `start_confirmed` or `lock_confirmed` to
true.

```text
cd examples/python
python demo.py
```

```text
cd examples/php
php demo.php
```

```text
sh examples/curl-demo.sh
```

Use a live controller only after the operator gives you HTTPS, OAuth, and
permission to affect a lab PC.

## Live walkthrough

### 1. Obtain the controller URL

Ask the operator for the HTTPS base, for example `https://controller.example`.
Paths below are `/api/v1/...`. Do not call the uvicorn port.

### 2. Obtain OAuth credentials

Ask for a **booking** confidential client (not provisioning):

- token URL at the operator identity provider
- client id and client secret
- audience, usually `gaming-pc-agent-api`
- scopes `devices:read sessions:read sessions:write`

The controller does **not** issue tokens and has no `/token` route. The
OpenAPI `tokenUrl` is a placeholder.

### 3. Request an access token

OAuth 2.0 client credentials (RFC 6749 section 4.4):

```http
POST {tokenUrl}
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&client_id=...&client_secret=...
```

Send the access token as `Authorization: Bearer ...` on every booking call
except health. When it expires, request another from the IdP.

### 4. List gaming PCs

```http
GET /api/v1/devices?limit=50
Authorization: Bearer ACCESS_TOKEN
```

There is no `GET /api/v1/devices/{device_id}`. Filter this list.

### 5. Select a PC

Your application chooses the PC. Prefer `status.connectivity=online` and
`status.status_stale=false`. The list does not reserve the PC.

If `connectivity` is `offline` or `status_stale` is true, do not tell a
customer the PC is ready. You may still create a session; the start command
waits for the agent and can expire.

### 6. Start a session

Create **is** the start request.

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

HTTP 202 with `start_confirmed: false` is normal. Persist `session_id`,
`command_id`, and the Idempotency-Key on your booking row.

### 7. Poll until `start_confirmed`

```http
GET /api/v1/sessions/{session_id}
Authorization: Bearer ACCESS_TOKEN
```

The GET body is the session document (not wrapped in `session`). Wait until
`start_confirmed` is true and `status` is `active` before telling a customer
the PC is unlocked. Command `pending`, `acknowledged`, or `executed` is not
enough.

### 8. Extend if required

```http
POST /api/v1/sessions/{session_id}/extend
Idempotency-Key: booking-98421-extend

{"expires_at": "2026-10-30T13:00:00Z"}
```

HTTP 202 stores `pending_expires_at`. The authorized `expires_at` changes
after a verified agent result.

### 9. End the session

```http
POST /api/v1/sessions/{session_id}/end
Idempotency-Key: booking-98421-end

{"reason": "user_request"}
```

### 10. Poll until `lock_confirmed`

Wait until `lock_confirmed` is true. Session status `ended` or `expired` is
not a verified lock. Device `access_state: locked` is a heartbeat observation
and is also not `lock_confirmed`.

## Errors you must handle

| HTTP | code | Action |
| --- | --- | --- |
| 401 | `unauthorized` | Request a new token, then retry. |
| 403 | `forbidden` | Stop. Missing scope or client. |
| 404 | `session_not_found` / `device_not_found` | Stop. Other accounts look the same. |
| 429 | `rate_limited` | Wait `Retry-After`, retry the same Idempotency-Key. |
| 503 | `storage_unavailable` | Retry the same Idempotency-Key. |

Details: [../docs/TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md) and
[../docs/INTEGRATION.md](../docs/INTEGRATION.md).

## Do not call

- `POST /api/v1/agents/heartbeat` (Windows agent, mTLS only)
- `GET /api/v1/devices/{device_id}`
- `GET /api/v1/devices/{device_id}/status`
- `GET /api/v1/commands/{command_id}`

Those last three are not served. A valid token receives HTTP 404 `not_found`.
