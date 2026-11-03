# Session lifecycle

This file is the normative session and command state machine. `api/openapi.yaml` is normative for the HTTP representation.

These facts are separate. None of them is inferred from another:

| Fact | Where it is recorded |
| --- | --- |
| Controller accepted a session or command | Session `accepted` or `ending`, command `pending`, HTTP `outcome: accepted` |
| Start command delivered to the agent | Command `delivered` |
| Agent acknowledgement | Command `acknowledged` |
| Agent execution report | Command `executed` |
| Verified OS enforcement effect | Command `succeeded` and `device_effect_confirmed: true` |
| Start confirmed | Session `active` and `start_confirmed: true` |
| Start definitively failed | Session `failed` |
| Authorized deadline reached | Session `expired` |
| Explicit end accepted, not yet executed | Session `ending` |
| Explicit end executed | Session `ended` |
| Lock verified | `lock_confirmed: true` and `lock_confirmed_at` |
| Device connectivity | Device `connectivity` |
| Trusted access state | Device `access_state` |
| Time of the latest device report | Device `reported_at` and `last_seen_at` |

`ended` and `expired` do not set `lock_confirmed`. A booking application that needs a lock claim reads `lock_confirmed`.

The network does not provide exactly-once delivery. Lost connectivity is not a success and is not a failure.

## Session statuses

No new session status is added. `acknowledged` and `executed` are command statuses, added so delivery, acknowledgement, execution, and verified effect are not the same event.

| Status | `start_confirmed` | `lock_confirmed` | Meaning |
| --- | --- | --- | --- |
| `requested` | false | false | Stored while authorization checks are unfinished. |
| `accepted` | false | false | The controller accepted the session and stored `start_session`. Play is unconfirmed. |
| `active` | true | false | The agent verified that start enforcement succeeded. |
| `ending` | true or false | false unless a separate lock result arrived | An explicit end command has been accepted and has no definitive execution result yet. |
| `ended` | true or false | true or false | An explicit end command was executed. This status is the session close, not a lock proof. |
| `expired` | true if the session had been `active`, otherwise false | true or false | `expires_at` has been reached. This is not a start failure and not a lock proof. |
| `failed` | false | false | The start operation definitively failed. |
| `cancelled` | false | false | Withdrawn before `start_session` was delivered. |

`failed` is used only when a stored start cannot proceed because the agent reports `failed`, or because checks fail after the session was stored. A command TTL expiry, a missed heartbeat, or an offline device does not make the session `failed` and does not make it `active`.

`expired` means the authorized deadline has been reached.

- If the session never became `active`, `accepted` becomes `expired` when `expires_at` passes. `start_confirmed` stays false. That timeout has no definitive start result, so it is not `failed`.
- If the session was `active`, or an explicit end is still `ending` when `expires_at` passes, the status becomes `expired`. `start_confirmed` stays true when play had already been verified. The session is no longer authorized. `lock_confirmed` stays false until a later authenticated enforcement result.

`lock_confirmed_at` is null until that enforcement result is stored. `ended_at` is the time `ended`, `expired`, `failed`, or `cancelled` was recorded. It is not the lock time.

`expires_at` is the last verified authorization deadline. `pending_expires_at` is only a requested extension.

## Valid transitions

| From | To | Condition |
| --- | --- | --- |
| `requested` | `accepted` | Checks succeed and `start_session` is stored. |
| `requested` | `failed` | Checks fail after the session was stored. |
| `requested` | `cancelled` | End is requested before a start command is delivered. |
| `accepted` | `active` | A start result has `enforcement_succeeded: true` and the deadline has not passed. |
| `accepted` | `ending` | End is requested after `start_session` was delivered and before play is verified. |
| `accepted` | `cancelled` | End is requested while `start_session` is still `pending`. |
| `accepted` | `expired` | `expires_at` passes with start unverified. |
| `accepted` | `failed` | The agent reports `start_session` as `failed`. |
| `active` | `ending` | An explicit end is accepted before the deadline. |
| `active` | `expired` | `expires_at` passes. The controller may store `end_session` with reason `deadline_reached`. That acceptance leaves the status `expired`. |
| `ending` | `ended` | The end command reaches `executed` or `succeeded` before the deadline. `lock_confirmed` is set only when the result has `enforcement_succeeded: true`. |
| `ending` | `expired` | `expires_at` passes before end execution. The end command remains outstanding. |

`ended`, `expired`, `failed`, and `cancelled` have no further status transitions. `lock_confirmed` may still change from false to true on `ended` or `expired` when a later authenticated enforcement result matches that session. That field update does not change the status.

There is no transition from `ending` to `failed`. An unconfirmed end stays `ending` until it is executed or the deadline moves it to `expired`.

A successful `POST /api/v1/sessions` finishes checks before it responds, so the body uses `accepted`. Callers must still accept `requested` if a later read shows it. A validation failure before a session is stored returns an HTTP error and does not create a session.

`POST /api/v1/sessions/{session_id}/extend` is valid only for `active`. Any other status returns `409` `invalid_session_transition`.

`POST /api/v1/sessions/{session_id}/end` is valid for `requested`, `accepted`, `active`, and `ending`. It returns `409` `invalid_session_transition` for `expired`, `failed`, and `cancelled`. For `ended` it returns the current session and command and does not create another end command.

The controller process stores create, read, extend, and end in PostgreSQL. Booking OAuth clients use those HTTP operations. Agent results on heartbeat move `accepted` to `active`, apply verified extend, set status `ended`, and set `lock_confirmed` under the rules below. Lazy expiry on read sets `expired` when `expires_at` passes.

`POST /api/v1/sessions/{session_id}/extend` requires `sessions:write` and `Idempotency-Key`. The account comes from the bearer token. On an `active` session whose requested `expires_at` is later than the current deadline, HTTP 202 stores `pending_expires_at` and a pending `extend_session` command. `expires_at` is unchanged. The command TTL is the provisional 120 seconds, and it is not later than the current session deadline. The same key and same requested deadline replay that command. The same key with a different deadline returns `409` `idempotency_conflict`. A different key while that command is `pending`, `delivered`, `acknowledged`, or `executed` returns `409` `extension_in_progress`. A requested deadline that is not later returns `422` `validation_error`. Any session status other than `active` returns `409` `invalid_session_transition`, including `accepted`. Booking HTTP does not move `accepted` to `active`. Only a verified start result on the agent heartbeat does that. An acknowledgement with `enforcement_succeeded` false leaves the session `accepted` and `start_confirmed` false.

`POST /api/v1/sessions/{session_id}/end` requires `sessions:write` and `Idempotency-Key`. An omitted body uses reason `user_request`. When the start command is `pending` or `expired`, the session becomes `cancelled`, that start command is `cancelled` when it was still `pending`, and the response is HTTP 200 `effect_not_applied`. No `end_session` command is stored. When the session is `active`, or the start command is `delivered`, `acknowledged`, `executed`, or `succeeded`, the response is HTTP 202 `accepted`, the session becomes `ending`, and a pending `end_session` command is stored. Its TTL is the provisional 300 seconds, and it is not later than the session deadline. A pending `extend_session` command is withdrawn, and `pending_expires_at` is cleared. `lock_confirmed` stays false. A repeated end, including one with a different idempotency key, does not store a second `end_session` command. The first key replays its stored result. The same key with a different reason returns `409` `idempotency_conflict`. After the session is `cancelled`, `expired`, or `failed`, a different key returns `409` `invalid_session_transition`.

## HTTP outcome

| Situation | HTTP | `outcome` |
| --- | --- | --- |
| A command is stored and the device effect is unverified | 202 | `accepted` |
| `device_effect_confirmed` is already true for the requested effect | 200 | `effect_confirmed` |
| The operation is finished and the verified effect was not applied | 200 | `effect_not_applied` |

`effect_confirmed` is the verified-effect outcome. Session status `ended` can occur with `effect_not_applied` when the end was executed and the lock was not verified. Callers read `outcome`, `device_effect_confirmed`, and `lock_confirmed`.

## Command statuses

| Status | `device_effect_confirmed` | Event |
| --- | --- | --- |
| `pending` | false | Controller accepted the command. It has not been delivered. |
| `delivered` | false | Included in at least one heartbeat response. The agent has not acknowledged it. |
| `acknowledged` | false | The agent reported receipt. It has not reported execution. |
| `executed` | false | The agent reported that it performed the operation. OS enforcement is not verified. |
| `succeeded` | true | An authenticated agent result says the OS enforcement operation succeeded. |
| `failed` | false | The agent reported a definitive failure. |
| `expired` | false | The command TTL elapsed with no definitive execution result. This is not success and not `failed`. |
| `cancelled` | false | Withdrawn before it was included in a heartbeat response. |

The controller marks a command `delivered` when it places that command in a heartbeat response. Acknowledgement is a later `command_results` entry with status `acknowledged`. Execution is a result with status `executed`. Verified effect is a result with status `succeeded` and `enforcement_succeeded: true`. A single heartbeat may carry only one of those results.

`device_effect_confirmed` becomes true only for `succeeded`. `succeeded` is not stored for a result whose `enforcement_succeeded` is false; that result is stored as `executed`.

The same `command_id` may appear in later heartbeats while it is `pending`, `delivered`, or `acknowledged`. The agent applies the effect of a `command_id` at most once (at-least-once delivery, local dedup). Cross-restart local authorization behavior is operator/agent configuration; see [../docs/ADR-001-technology-and-architecture.md](../docs/ADR-001-technology-and-architecture.md).

Once an `end_session` command exists for a session, later heartbeats for that session include the end command and omit `start_session` and `extend_session`.

## Processing an agent report

The controller processes `command_results` in array order, after it has recorded the heartbeat and before it builds `pending_commands`.

A result is applied only from an authenticated agent whose certificate matches the device. The controller does not synthesize a success, a failure, or a lock from a missing heartbeat.

| Report | Controller result |
| --- | --- |
| Unknown `command_id`, or a command for another device | Rejected with `command_not_found`. The heartbeat itself remains recorded. |
| `acknowledged` for a `pending` or `delivered` command | Command becomes `acknowledged`. Session status, `start_confirmed`, and `lock_confirmed` stay unchanged. |
| Same `acknowledged` report repeated | Applied idempotently. |
| `executed` | Command becomes `executed`, `device_effect_confirmed` stays false. Session effects are below. |
| `succeeded` with `enforcement_succeeded: true` | Command becomes `succeeded`, `device_effect_confirmed` becomes true. Session effects are below. |
| `succeeded` with `enforcement_succeeded: false` | Treated as `executed`. The effect is not verified. |
| `failed` | Command becomes `failed`, `device_effect_confirmed` stays false. |
| A contradictory result after `succeeded` or `failed` | Rejected with `conflicting_command_result`. The first of those two results stands. |
| `succeeded` after `executed`, while the effect is still eligible | Upgrades the command to `succeeded` and sets `device_effect_confirmed`. |

Session effects of an eligible result:

| Command and result | Session effect |
| --- | --- |
| `start_session` verified before `expires_at`, session `accepted` | Session becomes `active`, `start_confirmed` becomes true, `started_at` is set. |
| `start_session` verified at or after `expires_at` | Play is not confirmed. The session is `expired` if the deadline has passed. The command stays unverified with `authorization_window_elapsed`. The session is not `failed`. |
| `start_session` `executed` only | Session stays `accepted`. Start is not confirmed. |
| `start_session` `failed` while `accepted` | Session becomes `failed`. |
| `extend_session` verified while `active`, `pending_expires_at` matches, and the controller time is still before the previous `expires_at` | `expires_at` becomes the new deadline. `pending_expires_at` becomes null. The session stays `active`. |
| `extend_session` `executed` only, `failed`, or verified too late | The previous `expires_at` remains. `pending_expires_at` becomes null. See the extension section. |
| `end_session` `executed` while `ending`, before the deadline | Session becomes `ended`. `lock_confirmed` stays false. `ended_at` is set. |
| `end_session` verified while `ending`, before the deadline | Session becomes `ended`. `lock_confirmed` becomes true. `lock_confirmed_at` is set. |
| `end_session` verified while the session is already `expired` | Status stays `expired`. `lock_confirmed` becomes true. `lock_confirmed_at` is set. |
| `end_session` `failed` | Status stays `ending`, or `expired` if the deadline has passed. `lock_confirmed` stays false. The session does not become `failed`. |

`local_enforcement` is an authenticated lock result. It may set `lock_confirmed` and `lock_confirmed_at` for a matching `ending` or `expired` session, or for an `active` session whose deadline has passed. It does not change `expired` into `ended`, does not start play, and does not extend `expires_at`. A heartbeat `access_state` of `locked` or `playing` is an observation. It does not set `lock_confirmed`.

A controller-generated command `expired` or a pre-delivery `cancelled` is not an agent result. A late verified start is applied only while the session is still `accepted` and the deadline has not passed. A late verified end may still set `lock_confirmed` on `ending` or `expired`. It does not authorize play. A late verified extend is applied only while the session is still `active` and the controller time is before the previous `expires_at`.

A verified start for a `cancelled` command is rejected. The session stays `cancelled`.

## Extension effectiveness

An extension is effective only when all of the following are true:

1. The session status is `active`.
2. The extend command's verified result is accepted (`succeeded`, `enforcement_succeeded: true`).
3. `pending_expires_at` equals that command's requested deadline.
4. The controller's time at acceptance is strictly before the `expires_at` already in force.

At that moment `expires_at` becomes the new deadline and `pending_expires_at` becomes null. Until that moment the deadline in force is the previous `expires_at`. The HTTP `202` body, with `outcome: accepted` and a non-null `pending_expires_at`, is not a completed extension.

While the extend command is `pending`, `delivered`, `acknowledged`, or `executed`:

- The agent is offered the proposed deadline only inside that command.
- The session `expires_at` is unchanged.
- A second extend with a different idempotency key returns `409` `extension_in_progress`.
- If the agent reports `failed`, or the command reaches `expired` because its TTL elapsed, `pending_expires_at` is cleared and the previous `expires_at` remains. The session stays `active` when that deadline is still in the future. The extension is not treated as applied.
- If heartbeats stop, the session and `expires_at` stay as they were. Connectivity loss does not apply the pending deadline and does not mark the extension failed.
- If the previous `expires_at` passes first, the session becomes `expired`, `pending_expires_at` is cleared, and a late verification is rejected. The new deadline is not granted.

The controller therefore does not silently grant play time after the previous authorized deadline. How an agent should behave if its own clock steps across that deadline is an outstanding decision in ADR-001.

## Commands that expire before a definitive result

Provisional command TTL examples are in ADR-001. They are not production-approved settings. A command's `expires_at` is never later than the session authorization deadline.

A command TTL and the session authorization deadline are different events. Command status `expired` means that command's TTL elapsed with no definitive execution result. That command status does not by itself make the session `failed`, and it does not set `lock_confirmed`.

A start command that times out before a definitive result does not close the session. If `start_session` reaches command status `expired` while the session `expires_at` is still in the future, the session stays `accepted` and `start_confirmed` stays false. The controller may store a replacement start command, and `latest_command_id` then identifies that replacement. Callers that see the original command as `expired` read the session before treating the session as finished. If that session deadline later passes with start still unverified, the session becomes `expired` with `start_confirmed` false. The command timeout itself is neither session `expired` nor session `failed`, and it is not a lock.

An active session that reaches its authorized deadline is a separate transition. When an `active` session's `expires_at` passes, the session becomes `expired` and `start_confirmed` stays true. That change records the authorization deadline. It is not a command TTL, not a start failure, and not a lock. `lock_confirmed` stays false until a later authenticated enforcement result. The controller may store `end_session` with reason `deadline_reached`. That acceptance leaves the status `expired`.

An end command that times out, or that remains unconfirmed, does not prove a lock. If `end_session` reaches command status `expired` without `executed` or `succeeded`, `lock_confirmed` stays false. The session stays `ending` when the session deadline has not passed, and becomes `expired` when that deadline has passed. The same lock rule applies when the end is still unconfirmed because the agent is silent: silence does not set `lock_confirmed` and does not make the session `failed`. Whether the controller creates another end command, and how an operator is notified, is undecided.

## Deadline reached while the agent is unreachable

The controller compares `expires_at` with its own clock. When that deadline passes:

- An `accepted` session becomes `expired` with `start_confirmed` false.
- An `active` session becomes `expired` with `start_confirmed` true. The controller may store `end_session` with reason `deadline_reached`.
- An `ending` session becomes `expired` if the end has not been executed.
- `lock_confirmed` is unchanged by the clock alone.
- Device connectivity and access state follow `contracts/device-lifecycle.md`. After the freshness window, `access_state` is `unknown`.

No production behavior is specified here for what the PC does during the outage. Local deadline persistence, wall-clock changes, and loss of controller connectivity are outstanding decisions in ADR-001.

On a later authenticated heartbeat, a verified end or an eligible `local_enforcement` report can set `lock_confirmed` without changing `expired` to `ended`. A `playing` observation does not move an `expired` session back to `active` and does not extend `expires_at`.

## Booking application retry after a timeout

The caller repeats the original request with the same `Idempotency-Key` and body, then reads `outcome`, the command status, `start_confirmed`, `lock_confirmed`, and the session status. A retried HTTP request is not evidence that the PC executed the command.

If the key was lost and `external_reference` was sent, the `409` `external_reference_conflict` detail supplies `session_id`. If both were lost, this version has no session search operation. That gap is recorded in ADR-001.

## Booking integration reading

Booking software uses the statuses in this document. No additional session status is added for Task 18.1. The word `pending` in a booking request means the command status `pending`, not a session status. The booking-visible phases map as follows:

| Booking phase | Existing record |
| --- | --- |
| pending | Session `accepted` or `requested`, start command `pending`, `start_confirmed` false |
| accepted | Session `accepted` |
| active | Session `active` and `start_confirmed` true |
| expired | Session `expired` |
| ended | Session `ended` |

Cancellation before the start command is delivered uses the existing status `cancelled`. A definitive start failure uses `failed`. An accepted end that is not yet executed uses `ending`. There is no `rejected` or `canceled` status. HTTP `409` and `422` reject conflicting operations without writing a new status.

`start_confirmed` and `access_state` stay separate. Requested access is the stored session and its command. Confirmed device access is `start_confirmed` after a verified start result, and `lock_confirmed` after a verified enforcement result. `access_state` remains a device observation (`unknown`, `locked`, or `playing`).

The HTTP operations are `POST /sessions`, `GET /sessions/{session_id}`, `POST /sessions/{session_id}/extend`, and `POST /sessions/{session_id}/end`. Device status is read from the device resource, not from the session status. The integration notes, UTC rules, and storage limits are in `docs/booking-sessions.md`.
