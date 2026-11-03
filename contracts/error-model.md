# Error model

HTTP errors use one JSON object, defined as `Error` in `api/openapi.yaml`. Resource-level `error_code` values on sessions and commands are a separate list. They describe a stored operation. They are not a second HTTP shape.

## HTTP error object

```json
{
  "error": {
    "code": "external_reference_conflict",
    "message": "A non-terminal session already uses this external reference.",
    "request_id": "77777777-7777-4777-8777-777777777777",
    "details": [
      {
        "field": "external_reference",
        "code": "external_reference_conflict",
        "message": "A non-terminal session already uses this external reference.",
        "session_id": "33333333-3333-4333-8333-333333333333"
      }
    ]
  }
}
```

`request_id` matches the `X-Request-Id` response header. `details` is an empty array when the error has no field-level entries. `session_id`, `device_id`, and `command_id` appear on a detail only when that identifier lets the same account recover or correlate the conflict.

| HTTP | When it is used |
| --- | --- |
| 400 | Malformed JSON, a missing idempotency key, or a value of the wrong JSON type. |
| 401 | Missing, invalid, or revoked credentials for this endpoint. |
| 403 | The credential is valid and does not authorize the operation, or the agent certificate does not match `device_id`. |
| 404 | The identifier is not in the caller's account. Identifiers that belong to another account also receive 404. |
| 409 | The body is valid and conflicts with stored state or with a previous idempotency key. |
| 415 | A body was sent with a media type other than `application/json`. |
| 422 | The types are valid and a semantic rule fails. |
| 429 | The deployment rate limit was exceeded. `Retry-After` is present. |
| 501 | Historical design status only. The current implemented controller does not advertise unfinished routes as HTTP 501; unknown `/api/v1` paths return 401 unauthenticated or 404 `not_found` authenticated. |
| 503 | Device storage is unavailable, or agent trust configuration is missing. The response does not include database connection details. |

## API error codes

| `error.code` | HTTP | Meaning |
| --- | --- | --- |
| `invalid_json` | 400 | The body is not JSON. |
| `idempotency_key_required` | 400 | The operation requires `Idempotency-Key` and the header is absent. |
| `validation_error` | 400 or 422 | A field is missing, has the wrong type, or violates a schema or deadline rule. Wrong JSON types use 400. Semantic failures, including a deadline that is not in the future, use 422. |
| `unauthorized` | 401 | The credential is missing, invalid, or revoked. |
| `forbidden` | 403 | The credential cannot perform this operation. |
| `device_identity_mismatch` | 403 | The heartbeat `device_id` does not match the agent certificate. |
| `not_found` | 404 | The path is not an implemented API resource. Used after a valid credential reaches an unknown `/api/v1` route. |
| `device_not_found` | 404 | The device is not in the caller's account. |
| `session_not_found` | 404 | The session is not in the caller's account. |
| `command_not_found` | 404 | The command is not in the caller's account. |
| `idempotency_conflict` | 409 | This idempotency key was already used with a different body. |
| `enrollment_replay_unavailable` | 409 | The registration key was reused after the one-time token retention window. |
| `device_session_conflict` | 409 | The device already has a non-terminal session. |
| `external_reference_conflict` | 409 | The account already has a device or a non-terminal session with this reference. |
| `invalid_session_transition` | 409 | The session status does not allow this operation. |
| `extension_in_progress` | 409 | An extend command is already `pending` or `delivered`. |
| `platform_not_available` | 422 | This deployment has no enforcement module for the requested `platform`. |
| `clock_skew` | 422 | The heartbeat timestamp is outside the allowed skew. |
| `unsupported_media_type` | 415 | The body is not `application/json`. |
| `not_implemented` | 501 | The agent route is authenticated but not fully implemented. |
| `agent_auth_unavailable` | 503 | Agent trust configuration is missing or unreadable. |
| `rate_limited` | 429 | The caller exceeded the deployment rate limit. |
| `storage_unavailable` | 503 | Device storage could not be used. The controller does not fall back to process memory. |

Unknown future `error.code` values are failures. Callers show `message` to operators and branch on `code` for the cases they handle.

`409` `external_reference_conflict` for a session includes `details[].session_id`. The same code for a device includes `details[].device_id`. `extension_in_progress` includes `details[].command_id`.

## Command and session `error_code`

These values appear on `command.error_code` and may be copied to `session.error_code`. They are null when the operation has no stored error.

| Code | Meaning |
| --- | --- |
| `enforcement_failed` | The agent could not apply the command on the PC. |
| `session_not_recognized` | The agent has no matching local session for the command. |
| `device_busy` | The agent could not apply the command because the workstation was busy. |
| `invalid_command` | The agent rejected the command as inconsistent with its local state. |
| `authorization_window_elapsed` | The command was not applied because the authorized deadline had passed. |
| `command_expired` | The command TTL elapsed before a definitive execution result. This is not a session `failed` status and not a verified effect. |

A succeeded command has `error_code` null and `device_effect_confirmed` true. A failed command has `device_effect_confirmed` false and an `error_code` from this list.

## Heartbeat rejection codes

A heartbeat can be stored while an individual command result is rejected. The HTTP status stays `200`, and the result is listed in `rejected_command_results`.

| Code | Meaning |
| --- | --- |
| `command_not_found` | The command is unknown or belongs to another device. |
| `conflicting_command_result` | An earlier agent terminal result is already stored. |
| `invalid_command` | The result is not eligible for the current session state. |
| `authorization_window_elapsed` | A late start or extend would authorize time outside the stored window. |

`local_enforcement_outcome.detail_code` uses `session_not_found` or `session_not_eligible` when a lock report is not applied to the session. The device access state from that heartbeat is still recorded.
