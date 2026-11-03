# Booking-to-PC lifecycle and state mapping

This is the Task 18.4 Phase 1 mapping for existing controller behavior. Booking HTTP records a request. Confirmed Windows effects arrive only after the agent heartbeat carries a verified command result.

## Requested versus confirmed

| Booking action | Controller stores | Confirmed device effect |
| --- | --- | --- |
| Create session | Session `accepted`, command `start_session` `pending`, `start_confirmed` false | None |
| Poll GET session | Latest stored session | `start_confirmed` true means play was verified |
| Extend session | `pending_expires_at` until verified | `expires_at` advances after a succeeded extend |
| End session | Session `ending` or `cancelled`, command `end_session` | `lock_confirmed` true means restriction was verified |
| Device list | Last heartbeat observation | `access_state` is not `lock_confirmed` |

Never treat HTTP 202 `outcome: accepted` as unlocked play or a locked PC.

## Happy path

1. **Select an available PC.** Call `GET /api/v1/devices` with `devices:read`. Prefer `connectivity: online` and no non-terminal session. Assignment policy stays in the booking application. The list does not reserve the PC.

2. **Create or start a controller session.** Call `POST /api/v1/sessions` with `device_id`, `expires_at`, optional `external_reference`, and a new `Idempotency-Key`. Create is the start request. HTTP 202 with session status `accepted` means stored, not playing.

3. **Controller offers the start command to the Windows agent.** The next accepted `POST /api/v1/agents/heartbeat` may include that command in `pending_commands`. Booking software does not send this heartbeat.

4. **Agent unlocks the PC** when enforcement is enabled on that workstation and the start command executes. That step is outside booking HTTP.

5. **Booking application checks confirmed execution.** Poll `GET /api/v1/sessions/{session_id}` with `sessions:read` until `start_confirmed` is true and status is `active`, or until the command fails, expires, or the session becomes `failed` / `expired`. A POST replay may already show `outcome: effect_confirmed` if the agent result arrived first.

6. **Booking extension updates the session deadline.** `POST /api/v1/sessions/{session_id}/extend` with a later `expires_at`. HTTP 202 means the new deadline is requested (`pending_expires_at`). The authorized `expires_at` changes after a verified extend result.

7. **Booking end triggers PC restriction.** `POST /api/v1/sessions/{session_id}/end` with optional `{"reason":"user_request"}` or `{"reason":"operator"}`. Empty body is treated as `user_request`. HTTP 202 means an end command was stored. Status may be `ending`.

8. **Agent confirms the PC is restricted.** Poll GET session until `lock_confirmed` is true. Status `ended` without `lock_confirmed` is a recorded end, not a verified lock. Device `access_state: locked` is a heartbeat observation and still is not `lock_confirmed`.

9. **Handle offline devices, expiry, failed commands, and retries safely** as below.

## Offline devices

If `connectivity` is `offline` or `status_stale` is true, `access_state` is not trustworthy. The booking application may still create a session; the start command waits for the agent. Command TTL still applies. Do not tell a customer the PC is unlocked because create returned 202.

## Expired sessions and commands

When the authorized deadline passes, the session can become `expired`. That is not a verified lock. A start or extend command can become `expired` when its TTL elapses without a definitive result. `expired` on a command is not `failed` and is not a verified effect. If a start command expired and the session deadline has not passed, read the session: `latest_command_id` may identify a replacement, and status can still be `accepted`.

## Failed commands

`acknowledged` means the agent received the command. `executed` means it reported an attempt with `device_effect_confirmed` false. Neither confirms play or lock. `failed` is a definitive agent failure. Booking software should surface that to an operator and must not assume the PC changed.

## Retries

- Timeout or 503: retry the same POST with the same `Idempotency-Key` and body.
- 409 `idempotency_conflict`: do not reuse that key with a different body.
- 409 `device_session_conflict`: another non-terminal session already holds the PC. Read `details[].session_id` when present.
- 409 `external_reference_conflict`: this account already has a non-terminal session with that booking reference.
- 409 `extension_in_progress`: wait and poll GET session, then retry with a new key only if a new extend is still required.
- 404 `session_not_found`: the session is absent from this token's account. Do not probe other accounts.

## State mapping cheat sheet

| Booking intent | Session status | Flag to wait for |
| --- | --- | --- |
| Start requested | `accepted` | `start_confirmed` |
| Playing | `active` | `start_confirmed` true |
| Time added, unconfirmed | `active` or `accepted` with `pending_expires_at` set | later GET where `expires_at` matches the request |
| Stop requested | `ending` | `lock_confirmed` |
| Stopped, lock verified | `ended` | `lock_confirmed` true |
| Deadline passed | `expired` | not a lock |
| Could not complete | `failed` | read `error_code` |
| Cancelled before start | `cancelled` | no play |

## What this mapping does not do

It does not create an Odoo booking application, a PHP booking database, or a duplicate session table in the booking product. Persist `session_id`, `command_id`, and each `Idempotency-Key` next to the existing booking row.
