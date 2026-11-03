# Security model

This document states the security requirements. Device and session routes validate bearer tokens. Agent routes validate pre-provisioned client certificates. Booking API rate limits are implemented per token `account_id`. Durable audit-log storage is not specified as implemented in this documentation release. The identity and enrollment choices are in [ADR-002-authentication-and-enrollment.md](ADR-002-authentication-and-enrollment.md) and [ADR-003-identity-provider.md](ADR-003-identity-provider.md). Agent transport details are in [agent-mtls.md](agent-mtls.md).

Cloud and on-premise deployments are both covered. A local network is not treated as trusted.

## What the running process enforces

`api/openapi.yaml` is the published integration contract. It lists only operations this process serves. Planned routes that are not served are in [../api/future-endpoints.md](../api/future-endpoints.md).

| Operation | Contract credential | Running process |
| --- | --- | --- |
| `GET /api/v1/health` | None. `security: []`. | No credential check. The body is `{"status":"ok"}` and contains no account, device, session, or lock data. |
| `POST /api/v1/devices` | OAuth client credentials, scope `devices:write`. | Implemented. A bearer token is required. The signature, issuer, audience, and time claims are checked before the scope. The account comes from the configured token claim. |
| `GET /api/v1/devices` | OAuth client credentials, scope `devices:read`. | Implemented. A bearer token is required. The list contains only that token's account. |
| `GET /api/v1/devices/{device_id}` | Not in the published contract. | Unauthenticated 401. Authenticated 404 `not_found`. |
| `GET /api/v1/devices/{device_id}/status` | Not in the published contract. | Unauthenticated 401. Authenticated 404 `not_found`. |
| `POST /api/v1/sessions` | OAuth, scope `sessions:write`. | Implemented. Account from the token. |
| `GET /api/v1/sessions/{session_id}` | OAuth, scope `sessions:read`. | Implemented. Account from the token. |
| `POST /api/v1/sessions/{session_id}/extend` | OAuth, scope `sessions:write`. | Implemented. Account from the token. |
| `POST /api/v1/sessions/{session_id}/end` | OAuth, scope `sessions:write`. | Implemented. Account from the token. |
| `GET /api/v1/commands/{command_id}` | Not in the published contract. | Unauthenticated 401. Authenticated 404 `not_found`. |
| `POST /api/v1/agents/heartbeat` | Mutual TLS certificate bound to one `device_id`. | Certificate verification, device binding, heartbeat storage, and command exchange are implemented. Booking credentials receive 403. |

Health does not call the identity provider. OAuth routes reject a request when the issuer settings are missing, the signing keys cannot be fetched, or the token fails verification. They do not accept a decoded but unverified token. Agent routes require `AGENT_TLS_CA_FILE` and a provisioned fingerprint. Missing trust configuration fails closed with HTTP `503`. A device response is not evidence that a gaming PC is enrolled.

## Transport

All booking, provisioning, and agent communication uses TLS. TLS 1.2 or later is required. TLS 1.3 is preferred. The allowed cipher suites are unresolved and are recorded in ADR-001.

Enrollment responses and session responses are not cacheable. Booking and session responses send `Cache-Control: no-store`.

## Identities

Three identity classes are separate.

| Identity | Credential | Calls |
| --- | --- | --- |
| Provisioning client | OAuth 2.0 client credentials | `POST /api/v1/devices` and device reads. Scope `devices:write` is required to register. |
| Booking client | OAuth 2.0 client credentials | Session, command, and device-read operations. |
| Device agent | Mutual TLS certificate bound to one `device_id` | `POST /api/v1/agents/heartbeat` only. |

A booking client cannot call the heartbeat operation. A provisioning client cannot call session or heartbeat operations. An agent certificate cannot call booking or provisioning operations. The approved choice is OAuth 2.0 client credentials for server-to-server integrations, and mutual TLS for agents. ADR-002 and ADR-003 record that choice. Bearer validation on booking and provisioning routes is implemented. Agent certificate validation on heartbeat is implemented. There is no custom token format.

The OpenAPI scheme `bookingOAuth2` is one client-credentials grant used by both integration classes. They are not two grants. Production deployments issue them as separate clients, with separate secrets, and with only the scopes that class needs. A booking client receives `sessions:read`, `sessions:write`, `commands:read`, and `devices:read` when it must poll devices. A provisioning client receives `devices:write` and `devices:read`. A production client is not given every scope for convenience. The schema still allows a token to carry more than one scope; that is not permission to share one production secret between booking software and provisioning software, or between two customers.

Each gaming PC has its own certificate. Agents do not share a certificate, a private key, or an OAuth client. Customers do not share OAuth clients. `account_id` is taken from the credential that was authenticated. Callers do not supply `account_id`.

The placeholder token URL `https://controller.example/oauth/token` is not a route in `/api/v1` and not a deployed issuer. A later deployment replaces that host with a standards-compliant OAuth 2.0 authorization server. This contract does not define a custom token schema.

## Authentication flow

Booking and provisioning routes validate bearer tokens. Agent routes validate pre-provisioned client certificates. The controller does not issue tokens. A signed token is not checked against a revocation list in this version: until it expires, or until the signing key is no longer published, a stolen token still verifies. ADR-003 records that limit.

An authorized integration obtains an access token with the OAuth 2.0 client-credentials grant (RFC 6749 section 4.4). It sends its client identifier and client secret to the authorization server over TLS. The server returns a bearer token (RFC 6750). The integration then calls `/api/v1` with `Authorization: Bearer`. Client-credentials tokens are not refreshed with a refresh token. When a token expires, the integration requests another one with the same client secret.

The authorization server must bind each client to exactly one platform account and to the scopes issued for that client. The controller accepts a token only when all of the following are true:

- The token was issued for this controller API. When the token format has an audience, that audience is the controller.
- The token has not expired.
- The client has not been revoked, and this token has not been revoked.
- The token includes the scope required by the operation.
- The identity class matches the operation. A bearer token does not authorize `POST /api/v1/agents/heartbeat`. A client certificate does not authorize a booking or provisioning operation.

The controller reads `account_id` from that authenticated client. It does not accept `account_id` from the body, a query, or a header.

Client secrets are provisioned outside `/api/v1` and outside this repository. They are not hardcoded in source, images, examples, or OpenAPI descriptions. The example `EXAMPLE_TOKEN` is a label, not a client secret. How the first account and its first client are created remains an open operational step in ADR-001 and ADR-002.

A gaming-PC agent does not use this grant. It proves its identity with a certificate during TLS. The private key is generated on that PC, stays on that PC, and is never sent to the controller, stored in a device field, or committed to this repository. The certificate is bound to one `device_id`. Heartbeat requests that present a different device id receive `403` `device_identity_mismatch`.

Revocation of an OAuth client or a device certificate takes effect on the next use. Waiting for expiry is not sufficient. A revoked or expired credential receives `401` `unauthorized`. Replacing a client secret or a device certificate is an operational procedure outside `/api/v1` in this version. The old credential stops working when the new one is issued, or sooner if it is revoked first.

The provisional access-token lifetime in ADR-001 is 15 minutes. That number is not a production-approved setting. A later task must choose the production lifetime explicitly. DPoP, or another proof-of-possession signature on the bearer token, is not part of this baseline. A stolen bearer token can be replayed until it expires or the client is revoked. That residual risk is accepted until a later decision adds sender constraint.

## Enrollment

`POST /api/v1/devices` creates a device record. It does not install an agent and it does not prove that a PC is reachable. The `enrollment` object is material for a later certificate exchange. That exchange is not an operation in `/api/v1`.

Two clocks must stay distinct:

- The provisioning client may retry the same `Idempotency-Key` and the same body and receive the original `201` response, including the same enrollment token, during the provisional retention window in ADR-001. That replay repairs a lost HTTP response. It does not authorize a second certificate.
- The enrollment token itself is single-use at the certificate exchange. A second exchange with the same token fails, including when the HTTP retry window has not ended. After a successful exchange, or after the token's own lifetime, the token cannot be used. The production lifetime of that token is not the 15-minute HTTP example. It is an open decision and must be chosen explicitly.

Production enrollment, once authentication exists, is:

1. A provisioning client, authenticated with `devices:write`, registers the device. The response carries the one-time token. `Cache-Control: no-store` is required. The token is not written to logs and is not a device field returned by list or read operations.
2. An operator supplies that token once to the agent on the matching PC. The booking application is not the channel that installs the private key.
3. The agent generates a key pair locally and proves possession of the private key to the enrollment exchange. The controller receives a certificate signing request, or an equivalent proof, together with the single-use token. It does not receive the private key.
4. The exchange consumes the token, issues a certificate bound to that `device_id`, and rejects any later presentation of the token.
5. The agent uses that certificate for `POST /api/v1/agents/heartbeat`.

The HTTP shape of step 3, the certificate profile, and the certificate authority product are not decided. They stay outside `/api/v1` until a later task adds them. Adding them is not required to correct the current contract.

### Development registration is not enrollment

The current `POST /api/v1/devices` handler returns an enrollment-shaped object so the response matches `DeviceRegistrationResult`. That token is generated after the caller has presented a valid provisioning access token. It is stored only on that account's idempotency row so the same account and idempotency key can replay the same `201` body for the provisional window, including after a process restart. It is cleared when that window ends. It is not an OAuth token, it is not bound to a private key, it is not returned by device listing, and there is no exchange that can consume it. Another account that reuses the idempotency key receives its own registration, not this response.

Lab-only enrollment material must not be copied into a production agent, a secret store, or a later certificate exchange. Production enrollment starts with a new registration under a real provisioning credential. Clearing the token at the end of the replay window is not a substitute for revocation.

The documented example `EXAMPLE_ONLY_NOT_A_REAL_SECRET` is a placeholder in `api/examples/register-device.json`. It is not a credential.

## Authorization

Least privilege uses these scopes:

| Scope | Operations |
| --- | --- |
| `devices:read` | List and read devices and device status |
| `devices:write` | Register a device |
| `sessions:read` | Read a session |
| `sessions:write` | Create, extend, and end a session |
| `commands:read` | Read a command |

`sessions:write` does not imply `sessions:read`. A booking application that polls needs both. Production provisioning and booking clients are separate, as stated under Identities.

Every device, session, and command belongs to the credential's account. A request for an identifier outside that account receives `404`, including when the identifier exists in another account. One customer or application therefore cannot control another account's PCs through this API.

The agent certificate must match `device_id` in the heartbeat body. A mismatch receives `403` `device_identity_mismatch`. Command results for a command that belongs to another device are rejected inside the heartbeat and do not change that other device.

## Command limits

The public command types are `start_session`, `extend_session`, and `end_session`. The API has no operation and no schema field for a shell command, executable path, or script. The agent command channel cannot be used to push an unsigned binary.

Each command has `expires_at`. When that command TTL elapses with no definitive execution result, the command status becomes `expired`. That is not a verified effect and not a session `failed` state. Replay of a booking request is handled with `Idempotency-Key`, not by executing the effect twice. Replay of a device command is handled with `command_id`. Late agent reports are accepted only in the cases stated in `contracts/session-lifecycle.md`. The TTL numbers in ADR-001 are provisional design examples.

OAuth token expiry, TLS, idempotency keys, command ids, and command expiry are the proposed replay controls. An additional request-signing scheme such as DPoP is unresolved and is not required by this baseline.

## Credential rotation and revocation

Operators disable a compromised OAuth client at the identity provider. Device certificates are revoked in PostgreSQL (`revoked_at`). Later use of a revoked certificate receives `401`. A JWT that was already issued remains valid until `exp` or until its signing key leaves JWKS. See [jwt-access-tokens.md](jwt-access-tokens.md). Expiry without revocation also receives `401`. A missing credential receives `401`, not `404`.

A credential that is valid and does not include the required scope receives `403` `forbidden`. An agent certificate that does not match the heartbeat `device_id` receives `403` `device_identity_mismatch`. After a caller is authenticated, an identifier that is absent from that caller's account receives `404`, including when the same identifier exists in another account. The `404` hides the other account. It is not the response for a missing token.

`GET /api/v1/health` stays unauthenticated. It must not be extended with account, device, session, or lock fields. Those fields would make an open health check into a data API.

Rotation of a client secret or a device certificate is required and is not an operation in `/api/v1`. Until a later operation exists, replacement is an operational procedure. The one-time enrollment token is returned on the registration response and is retained for replay of the same `Idempotency-Key` only for the provisional window recorded in ADR-001. That window is not a production-approved security setting, and it is not the production lifetime of the enrollment token. After it, the same key returns `409` `enrollment_replay_unavailable` and does not mint a second secret.

## Validation and rate limits

Requests are validated against the OpenAPI schemas. Unknown fields, invalid enums, and illegal deadlines receive `400` or `422` as specified per operation. Heartbeat timestamps outside the provisional skew example receive `422` `clock_skew`, and that request does not update device state. Wall-clock steps and a production skew limit are unresolved.

Rate limits are enforced per token `account_id` in PostgreSQL fixed windows. Exceeding them returns `429` with `Retry-After` and `error.code` `rate_limited`. Session create, extend, and end share the session-write budget. GET booking reads have a separate budget. A stored Idempotency-Key replay does not consume a slot. Health and agent heartbeat are not limited here. Numeric defaults are deployment configuration supplied with the controller package.

## Audit

The controller records an audit event for authentication failure, authorization failure, device registration, credential revocation, session transition, command creation, command result, rejected command result, idempotency conflict, and cross-account access that was answered with `404`.

Each event includes the time, the `request_id`, the credential identifier or `device_id`, the operation, and the result. Audit storage is part of the controller's database. A query API for audit events is not part of this version. The retention period is unresolved.

## Agent updates

A future agent update mechanism must verify a signature before installation. Session commands are not an update channel. The signing workflow and package format are unresolved.

## Lock confirmation

The controller sets `lock_confirmed` only after an authenticated agent result says the OS enforcement operation succeeded. Passage of `expires_at` moves an `active` or `ending` session to `expired` and may store an `end_session` command. That clock event does not set `lock_confirmed`. Session status `ended` or `expired` does not set it either.

When the freshness window passes without a heartbeat, device `access_state` becomes `unknown`. That value is not a confirmed lock.

## Threats and the required mitigation

Bearer checks, scope checks, and per-account device records are implemented for the two device routes. Agent certificates, revocation introspection, session commands, and audit storage are not.

| Threat | Required mitigation |
| --- | --- |
| Stolen integration client secret | Revoke that client. Later token use returns `401` even if a previously issued token has not reached its expiry. The provisional short lifetime limits the window but does not replace revocation. A booking secret must not also be the provisioning secret. |
| Stolen bearer token | The token dies at expiry or when its client is revoked. There is no sender constraint in this baseline, so theft before that point is a residual risk recorded in ADR-002. |
| Stolen or replayed enrollment token | The exchange accepts the token once, then rejects it. HTTP idempotency replay may repeat the original registration response to the provisioning client; it must not issue a second certificate. The token is not logged, not cached, and not stored on the device record. A development token is never presented to a production exchange. |
| Unauthorized device registration | `POST /api/v1/devices` requires a validated bearer token with `devices:write`. The listener stays on `127.0.0.1`. The enrollment object in the response is not an access token. |
| Cross-tenant device access | The authenticated account is the only query scope. Device lists, external references, and idempotency keys are stored per account. Another account's device, session, or command id returns `404` once those routes exist. An agent certificate will authorize only its own `device_id`. |
| Agent certificate compromise | Revoke that certificate. The next heartbeat receives `401` or fails the TLS handshake. The replacement certificate is still bound to the same single `device_id`. No other PC inherits the old certificate. |
| Expired credential | `401` `unauthorized`. The integration requests a new access token. An expired certificate is not treated as a booking credential. |
| Network interruption and stale status | After the freshness window, `connectivity` is `offline` and `access_state` is `unknown`. That state is not a lock, not a start failure, and not permission to extend play. Session rules stay in `contracts/session-lifecycle.md`. |
| Unauthorized command or session extension | The only command types are `start_session`, `extend_session`, and `end_session`. Requesting one requires `sessions:write`. Reporting a result requires the agent certificate for that device. A booking client cannot submit command results. An accepted extension does not change `expires_at` until a verified result arrives before the previous deadline. |

## Outstanding enforcement decisions

Local deadline persistence across an agent restart, wall-clock changes, behavior while the controller is unreachable, and what happens when an end command is never verified are undecided. They are listed in ADR-001. This specification does not promise that a disconnected PC locks itself, and it does not promise an operator alert.
