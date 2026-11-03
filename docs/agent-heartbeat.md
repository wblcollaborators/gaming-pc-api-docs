# Agent heartbeat

`POST /api/v1/agents/heartbeat` stores device connectivity and the reported access state for one authenticated agent.

## Authentication

The same mutual TLS rules as [agent-mtls.md](agent-mtls.md) apply. The heartbeat `device_id` must match the certificate binding. OAuth bearer tokens receive HTTP `403`.

## Request

Required JSON fields match `HeartbeatRequest` in `api/openapi.yaml`:

| Field | Notes |
| --- | --- |
| `device_id` | Must match the authenticated certificate. |
| `reported_at` | UTC with `Z` suffix. Must be within 30 seconds of the controller clock (ADR-001 provisional example). Outside that window → HTTP `422` `clock_skew` and no state change. |
| `agent_version` | Stored on the device record. |
| `access_state` | `unknown`, `locked`, or `playing`. The Task 18.2 agent sends `unknown`. |
| `current_session_id` | Validated. The Task 18.2 agent sends null. |
| `command_results` | Processed in array order before `pending_commands` is built. The agent may send `acknowledged` or an unsupported `failed` result. Both use `enforcement_succeeded` false. |
| `local_enforcement` | Applied after command results when present. The Task 18.2 agent sends null. |

## Response

HTTP `200`:

```json
{
  "outcome": "recorded",
  "device_id": "<uuid>",
  "received_at": "2026-10-09T10:00:05Z",
  "status": {
    "device_id": "<uuid>",
    "connectivity": "online",
    "access_state": "locked",
    "last_reported_access_state": "locked",
    "reported_at": "2026-10-09T10:00:05Z",
    "last_seen_at": "2026-10-09T10:00:05Z",
    "status_stale": false,
    "stale_after_seconds": 90
  },
  "next_heartbeat_before": "2026-10-09T10:01:35Z",
  "pending_commands": [ "... Command objects when work is queued ..." ],
  "applied_command_results": [],
  "rejected_command_results": [],
  "local_enforcement_outcome": null
}
```

`received_at` is the controller receipt time. `status.reported_at` is the agent timestamp from the request. `next_heartbeat_before` is `received_at` plus `stale_after_seconds` (90 seconds in the provisional example).

## Persistence and staleness

On accept, the controller sets:

- `connectivity` → `online`
- `access_state` and `last_reported_access_state` → the reported value
- `reported_at` → agent timestamp
- `last_seen_at` → controller receipt time
- `status_stale` → `false`
- `agent_version` → request value

When `last_seen_at` is older than `stale_after_seconds`, a device list (or other read that refreshes staleness) stores:

- `connectivity` → `offline`
- `access_state` → `unknown`
- `last_reported_access_state`, `reported_at`, and `last_seen_at` unchanged
- `status_stale` → `true`

There is no background worker. Staleness is computed from persisted timestamps when devices are read.

## Device listing

`GET /api/v1/devices` returns the updated `status` object, including `reported_at` and `last_seen_at` when present.

## Local manual test

After device registration, certificate provisioning, and mTLS setup from
[agent-mtls.md](agent-mtls.md), call the **agent** HTTPS listener (not the
booking listener):

```bash
curl -sS --cacert /path/to/agent-ca.pem \
  --cert /path/to/device-client.pem \
  --key /path/to/device-client.key \
  -H 'Content-Type: application/json' \
  -d '{
    "device_id": "DEVICE_ID",
    "reported_at": "2026-10-09T10:00:00Z",
    "agent_version": "0.1.0-test",
    "access_state": "locked",
    "current_session_id": null,
    "command_results": [],
    "local_enforcement": null
  }' \
  https://agent.example/api/v1/agents/heartbeat
```

Use a `reported_at` within 30 seconds of the controller clock. Expect HTTP
`200` and `"outcome": "recorded"`.

Then list devices on the **booking** HTTPS listener with a provisioning or
booking token:

```bash
curl -sS -H "Authorization: Bearer REPLACE_WITH_ACCESS_TOKEN" \
  https://booking.example/api/v1/devices
```

Expect `"connectivity": "online"` and matching access fields for that device.

## Command delivery

Eligible session commands are returned in `pending_commands`. See [agent-command-delivery.md](agent-command-delivery.md) for authentication, ordering, expiry, and retry rules.

## Command results

See [agent-command-delivery.md](agent-command-delivery.md) for delivery rules and `contracts/session-lifecycle.md` for result transitions. The heartbeat response lists `applied_command_results` and `rejected_command_results` for the reports in that request.

## Limitations

- Commands are offered for retrieval only; the controller does not execute them on the PC.
- Physical lock/unlock on the workstation is out of scope; the controller records agent-reported outcomes only.
