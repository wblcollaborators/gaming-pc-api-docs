# Device lifecycle

Device connectivity, trusted access state, and session status are independent. Connectivity says whether the controller has a fresh heartbeat. `access_state` is the trusted enforcement observation. Neither value is implied by accepting a session command, by `ended`, or by `expired`.

## Identity

`POST /api/v1/devices` creates a device in the caller's account. The request supplies `display_name`, `platform`, and an optional opaque `external_reference`. The controller assigns `device_id` and `account_id`.

`platform` is `windows` or `linux`. Windows is the first enforcement target. `linux` is part of the contract so a later Linux agent can register without a new booking API. A deployment with no Linux module responds `422` `platform_not_available`.

Registration does not contact the PC. The one-time enrollment token and the later certificate are specified in `docs/security-model.md`.

A repeated registration with the same idempotency key and body returns the original result while that token is still retained. After the retention window, the same key returns `409` `enrollment_replay_unavailable` and does not create another token. A different key with an `external_reference` already used by a device in the account returns `409` `external_reference_conflict` with `device_id` in `error.details`.

## Connectivity

| `connectivity` | Rule |
| --- | --- |
| `online` | A valid heartbeat has been received, and the controller receipt time is within `stale_after_seconds` of `status.last_seen_at`. |
| `offline` | No heartbeat has been received, or the latest receipt is older than `stale_after_seconds`. |

`status.last_seen_at` is the controller's receipt time of the latest accepted heartbeat. `status.reported_at` is the agent timestamp from that heartbeat. Freshness uses the controller clock, so a stale agent clock cannot keep a device online.

`status.stale_after_seconds` is the threshold the controller applied on that response. The number in examples is a provisional design example in ADR-001, not a production-approved security setting. Clients use the returned number.

`status_stale` is true when connectivity is `offline`, and false when connectivity is `online`.

A heartbeat whose `reported_at` is outside the provisional skew example is rejected with `422` `clock_skew`. Rejected heartbeats do not move `last_seen_at`. Safe behavior when the wall clock steps is an outstanding decision in ADR-001. The controller's comparison uses the clock on the controller at the time it processes the request.

## Access state

| `access_state` | Meaning |
| --- | --- |
| `locked` | The latest trusted agent report said the workstation was locked. |
| `playing` | The latest trusted agent report said an authorized session was in effect. |
| `unknown` | No trusted report is available. |

`access_state` is `unknown` in three cases: no heartbeat has been accepted, the agent reported `unknown`, or the last report is older than `stale_after_seconds`. In the third case the controller replaces the current access state with `unknown`. It keeps the previous observation in `last_reported_access_state` and keeps `reported_at` and `last_seen_at`. `last_reported_access_state` is not the current access state and is not a confirmed lock.

`reported_at` is the agent timestamp of the latest accepted report. `last_seen_at` is the controller receipt time of that report. Those timestamps remain when the device later becomes stale.

Before the first heartbeat, connectivity is `offline`, both access fields are `unknown`, both timestamps are null, and `status_stale` is true.

A session status does not set access state. `accepted` does not mean `playing`. `ending`, `ended`, and `expired` do not mean `locked`. `lock_confirmed` changes only from an authenticated enforcement result, as defined in `contracts/session-lifecycle.md`.

## Heartbeat processing order

1. Authenticate the agent certificate and require it to match `device_id`.
2. Reject the whole request, with no state change, when the body is invalid or the timestamp is outside the skew window.
3. Record receipt time, agent version, and connectivity `online`. Set `access_state` and `last_reported_access_state` to the reported value. This observation does not set `lock_confirmed`.
4. Apply `command_results` in order, using `contracts/session-lifecycle.md`.
5. Apply `local_enforcement` when it is present.
6. Return the remaining commands that are `pending`, `delivered`, or `acknowledged` for this device, oldest first, omitting start and extend commands for a session that already has an end command.

The controller process performs steps 1 through 6. Step 6 marks newly offered `pending` commands as `delivered`.

`outcome: recorded` means the heartbeat was stored. It does not mean a command was acknowledged, executed, or verified.

`local_enforcement` can set `lock_confirmed` only under the session rules. It is not implied by session `ended` or `expired`, and it is not implied by a stale access observation. An ineligible report leaves the session unchanged, returns `applied: false`, and still keeps the fresh access observation from step 3.

`current_session_id` is the agent's view of the session it is enforcing. A disagreement with the controller is an audit event. The identifier in the heartbeat does not create or extend authorization.

## Duplicate delivery

Commands in `pending`, `delivered`, or `acknowledged` stay available on later heartbeats, so a lost response can be recovered. Delivery is that inclusion. Acknowledgement, execution, and verified effect are later command results. A repeated verified result is idempotent. Applying the effect at most once across an agent restart is an outstanding decision in ADR-001.

## Disconnection

After the freshness window, connectivity is `offline`, `status_stale` is true, and `access_state` is `unknown`. `last_reported_access_state`, `reported_at`, and `last_seen_at` stay at the last accepted report.

That view does not end a session, does not fail a session, and does not confirm a lock. What the PC does while the controller cannot be reached, including whether a deadline survives an agent restart, is undecided.

## Relationship to sessions

| Controller fact | Device fact |
| --- | --- |
| Session `accepted` | Access may be `locked`, `playing`, or `unknown`. Start is unconfirmed. |
| Session `active` | A fresh report may say `playing`. A stale device shows `access_state: unknown` and does not clear `start_confirmed`. |
| Session `ending` | End is accepted and not yet executed. Lock is confirmed only by `lock_confirmed`. |
| Session `ended` | The explicit end was executed. `lock_confirmed` is independent. |
| Session `expired` | The authorized deadline passed. `lock_confirmed` is independent. `access_state: unknown` is not a lock. |
| Session `failed` | Start definitively failed. No lock is claimed. |

Callers that need a verified lock read `lock_confirmed`. Callers that need the trusted access state read `GET /api/v1/devices` and treat `access_state` as `unknown` whenever `status_stale` is true.
