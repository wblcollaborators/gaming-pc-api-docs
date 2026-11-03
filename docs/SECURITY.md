# Security requirements for booking developers

The operator hosts the controller, identity provider, and Windows agents.
You host the booking application. This page is the developer-facing subset.
Operators also use `docs/security-model.md`, `docs/jwt-access-tokens.md`,
and `docs/production-checklist.md`.

## Transport

- Call the HTTPS controller base URL. Verify TLS certificates. TLS 1.2 or later.
- Do not disable certificate verification.
- Send HTTP methods in uppercase (`GET`, `POST`).
- Do not call the uvicorn port, even if you discover it.

## OAuth 2.0

- Use **client credentials** (RFC 6749 section 4.4). Server-to-server only.
- Never embed client id, client secret, or access tokens in a browser, mobile
  app, source repository, log, or support ticket.
- Required booking scopes: `devices:read`, `sessions:read`, `sessions:write`.
- Do not request `devices:write` for booking software.
- You never send `account_id`. The controller reads it from the access token.
- HTTP 401: signature, issuer, audience, or expiry failed.
- HTTP 403: token verified, but account, client id, or scope is missing.

Access tokens remain valid until `exp` unless the operator unpublished the
signing key. Recommended lifetime is 5–15 minutes. Disable a stolen client at
the identity provider. See `docs/jwt-access-tokens.md`.

## Agent identity

`POST /api/v1/agents/heartbeat` is mutual TLS for the Windows agent. A booking
bearer token receives HTTP 403. Do not send agent certificates from booking
software.

## Rate limits

Limits are per token `account_id`. HTTP 429 `rate_limited` includes
`Retry-After`. Retry the same Idempotency-Key after that delay.

## Data you must not collect from this API

- Enrollment secrets from device registration (`devices:write` provisioning)
- Agent private keys or CA material
- Other accounts' devices or sessions (those calls return 404, not 403)

## Account isolation

Objects that are absent from your token's account return 404. Do not probe for
other tenants.
