# Agent command delivery

Agents retrieve work through `POST /api/v1/agents/heartbeat`. There is no separate OAuth-accessible poll endpoint. Booking apps use `GET /api/v1/commands/{command_id}` with a bearer token; agents use mTLS and the heartbeat response.

## Authentication

Same rules as [agent-mtls.md](agent-mtls.md). The certificate must match `device_id` in the body. Revoked, unknown, or unregistered fingerprints receive HTTP `401`. A certificate bound to a device that is not in the authenticated account receives HTTP `404` `device_not_found`.

## Delivery channel

After the heartbeat observation is stored, the controller builds `pending_commands`:

1. Expire open commands whose `expires_at` is not later than the controller clock, and expire non-terminal sessions whose deadline has passed (same rules as session reads).
2. Select commands for the authenticated `account_id` and `device_id` with status `pending`, `delivered`, or `acknowledged` and `expires_at` still in the future.
3. Order by `created_at` ascending (oldest first).
4. Omit `start_session` and `extend_session` for a session that already has an `end_session` command in `pending`, `delivered`, `acknowledged`, or `executed`.
5. Mark each included `pending` command as `delivered` before returning.

Commands in `delivered` or `acknowledged` stay in later responses until they reach a terminal status through agent results.

## Empty queue

When no commands are eligible, `pending_commands` is an empty array. The heartbeat is still stored and HTTP `200` with `outcome: recorded` is returned.

## Command expiry

Command TTLs follow ADR-001 provisional examples (120s for start/extend, 300s for end), capped by the session deadline. Expired commands are not offered. They are not recreated automatically.

## Retry behavior

The agent should heartbeat on its normal schedule. Each poll is idempotent for already-`delivered` commands: the same `command_id` may appear again until a terminal result is stored. Concurrent heartbeats for one device are serialized with a PostgreSQL advisory lock so `pending` → `delivered` happens once.

## Agent polling

The Windows service production path loads `agent.toml`, the provisioned client certificate, and the SQLite command journal, then calls this heartbeat on `heartbeat_interval_secs` (5 to 300 seconds). Lifecycle-smoke mode does not open that connection. The fullscreen UI process does not poll.

Each attempt uses the configured connect and request timeouts. A timeout, disconnect, TLS failure, HTTP 500, or HTTP 503 is logged and the service keeps running. The next attempt waits for the heartbeat interval. The loop does not start a tighter retry. Service stop drops an in-flight request instead of waiting for the UI supervisor.

The agent reports `access_state` `unknown`, `current_session_id` null, and `local_enforcement` null. It does not report `playing` or `locked` from command arrival.

## Communication results

For `start_session`, `extend_session`, and `end_session`, the agent validates the command id, device id, session id, type, and deadline, then submits:

```json
{
  "command_id": "<command-uuid>",
  "status": "acknowledged",
  "completed_at": "2026-10-09T10:00:05Z",
  "error_code": null,
  "enforcement_succeeded": false
}
```

That is receipt. It does not set `start_confirmed`, `lock_confirmed`, or a new `expires_at`. The session stays `accepted` after a start acknowledgement.

`windows_enforcement.mode` defaults to `off`, which is this acknowledgement path. `simulate` stores one local authorization row in the existing SQLite journal and reports `executed` with `enforcement_succeeded` false. `enforce` is rejected unless `local_test_mode` is true. A `succeeded` result with `enforcement_succeeded` true is sent only after the interactive-session control file matches and `windows_ui_supervisor.enabled` is true. Receipt of a command never sets that flag. While `mode` is `off`, the service does not write the restricted-screen control file.

`shell` is not executed. With `mode` `off`, `lock` and `unlock` are also rejected as `failed` / `invalid_command`. With `simulate` or `enforce`, those two local actions restrict or restore access for the authorized session. The canonical controller command set remains `start_session`, `extend_session`, and `end_session`.

## Enforcement mode

| mode | PC effect | Result |
| --- | --- | --- |
| `off` (default) | none | `acknowledged`, `enforcement_succeeded` false |
| `simulate` | journal authorization only | `executed`, `enforcement_succeeded` false |
| `enforce` | control file plus a UI-process visibility report | `succeeded` and `enforcement_succeeded` true only when `ui-state` matches the request |

`enforce` also requires an admin recovery secret of at least 8 characters. On the restricted screen, hold Ctrl+Shift+Alt and type that secret. The overlay exits, a `permit` token is left in the control file, and `restricted-screen.ctl.admin-release` is written beside it. Delete that release file before expecting the restricted screen to return. Until then the supervisor does not treat the held overlay as a crash. A reboot with no stored unexpired authorization does not write `permit`. An expired local authorization is revoked on the next heartbeat even when the controller cannot be reached.

`succeeded` requires the interactive UI process to write `restricted-screen.ctl.ui-state` after the window exists (`visible`) or after it exits (`hidden`). A `permit` token in the control file is only a request. It does not set `enforcement_succeeded`. The fullscreen overlay is not Windows logon or OS-level lock.

The same heartbeat applies `command_results` before it builds `pending_commands`. A repeated acknowledgement for a command that is already `acknowledged` is stored once. Seeing the same `command_id` again does not dispatch it again. If that later offer is still `pending` or `delivered`, the agent queues the same acknowledgement again. It does not do that once the offer status is `acknowledged`, and it does not retry a settled `failed` result. The journal is local SQLite. An unsent acknowledgement survives a restart. That is at-least-once delivery. It is not exactly-once execution. A lost journal file can acknowledge the same command again; the controller still does not confirm a device effect from that acknowledgement.

## Command results

Terminal commands are not offered again. See `contracts/session-lifecycle.md`.

The controller records the authenticated report. It does not lock Windows. The agent locks nothing while `windows_enforcement.mode` is `off`.

## Example

After `POST /api/v1/sessions` created a session for the device. This curl is a direct client. The Windows agent sends `access_state` `unknown`, not `locked` or `playing`.

```bash
curl -sS -X POST "https://agent.example/api/v1/agents/heartbeat" \
  --cert "/path/to/windows-station-01-agent.pem" \
  --key "/path/to/windows-station-01-agent-key.pem" \
  --cacert "/path/to/agent-ca.pem" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "<device-uuid>",
    "reported_at": "2026-10-09T10:00:00Z",
    "agent_version": "0.1.0",
    "access_state": "locked",
    "current_session_id": null,
    "command_results": [],
    "local_enforcement": null
  }'
```

Example fragment of HTTP `200`:

```json
{
  "outcome": "recorded",
  "pending_commands": [
    {
      "command_id": "...",
      "command_type": "start_session",
      "status": "delivered",
      "parameters": {
        "command_type": "start_session",
        "expires_at": "2026-10-09T11:00:00Z"
      }
    }
  ],
  "applied_command_results": [],
  "rejected_command_results": []
}
```

See also [agent-heartbeat.md](agent-heartbeat.md) and `contracts/device-lifecycle.md`.

## Windows check

The Task 17.29C.5 runner stays the UI and service smoke test. It registers the service with `--lifecycle-smoke`, and that mode does not open the controller connection. Do not change that command to prove command delivery.

Automated coverage exists in the private controller and agent repositories. Those suites do not replace a Windows run against a live controller.

On the Windows PC, after the runner has produced `gaming-pc-agent.exe`, provision the device and certificate with [agent-mtls.md](agent-mtls.md). Point `agent.toml` at `https://<controller>:8443`, the device id, and the PEM files. Then, from the staged directory, leave the smoke service installed and run the same binary in the console:

```text
.\gaming-pc-agent.exe --config C:\ProgramData\GamingPcAgent\agent.toml
```

Create a session for that device with `POST /api/v1/sessions`. The console log should include the command id, `start_session`, and `result_status=acknowledged`. Read the session. Expect `status` `accepted`, `start_confirmed` false, and `lock_confirmed` false. A second heartbeat for the same command id does not create another command. Stop the console process with Ctrl+C. The smoke service and its supervised UI are a separate process and stay on the lifecycle-smoke path.

There is no production HTTP fallback. TLS verification stays on. Development certificate injection exists only in the controller test suite.
