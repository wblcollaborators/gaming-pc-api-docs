# Errors and troubleshooting

Authoritative HTTP schemas are in `api/openapi.yaml`. This page is for
independent developers integrating a booking application.

## Error body

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

Include `error.request_id` when you contact the operator. Do not send access
tokens, client secrets, or certificate material.

## Status codes

| HTTP | code | Retry? |
| --- | --- | --- |
| 400 | `invalid_json`, `validation_error`, `idempotency_key_required` | No. Fix the request. |
| 401 | `unauthorized` | Only after obtaining a new token from the IdP. |
| 403 | `forbidden` | No. |
| 404 | `not_found`, `device_not_found`, `session_not_found` | No. |
| 409 | `device_session_conflict`, `external_reference_conflict`, `idempotency_conflict`, `invalid_session_transition`, `extension_in_progress` | No with the same conflicting input. |
| 415 | `unsupported_media_type` | No. Send `Content-Type: application/json`. |
| 422 | `validation_error` | No. Deadline must be in the future, and later than the current deadline for extend. |
| 429 | `rate_limited` | Yes, after `Retry-After` seconds, same Idempotency-Key and body. |
| 503 | `storage_unavailable` | Yes, same Idempotency-Key and body. |

Network timeouts on POST: retry the same method, path, Idempotency-Key, and
JSON body. A stored key replay does not consume a new rate-limit slot.

Python and PHP `is_retryable` / `isRetryable` are true for 429 and 503 only.

## Symptoms

| Symptom | Check |
| --- | --- |
| HTML 400 | HTTP method is not uppercase, or the reverse proxy rejected the request. |
| 401 | Token URL, audience, issuer, or expiry. The controller is not the token issuer. |
| 403 on GET session | Add `sessions:read`. `sessions:write` is not enough. |
| 403 on heartbeat | Booking tokens cannot call agent routes. Do not call heartbeat. |
| 404 `session_not_found` | Wrong `session_id`, or it belongs to another account. Both look the same. |
| 404 `not_found` | Path is not in the published contract. Use the device list and GET session. |
| 202 but the customer cannot play | Poll until `start_confirmed` is true. 202 is storage only. |
| Session `ended` but the PC is still playable | Wait for `lock_confirmed`. Ended is not a verified lock. |
| 409 `device_session_conflict` | That PC already has a non-terminal session. |
| 409 `idempotency_conflict` | Same Idempotency-Key with a different JSON body. |
| 429 | Wait `Retry-After`. Limits are per platform account, not per IP. |
| Offline PC after create | Expected. The start command waits for the agent and can expire. |

## Offline devices

If `connectivity` is `offline` or `status_stale` is true, do not tell a
customer the PC is ready. Create is still allowed. Poll GET session until
`start_confirmed` or a terminal session/command status.
