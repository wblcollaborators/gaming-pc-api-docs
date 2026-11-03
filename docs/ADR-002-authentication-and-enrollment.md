# ADR-002: Authentication and enrollment

- Status: Accepted. Amended 2026-11-03 for public documentation accuracy.
- Original date: 2026-10-09
- Scope: Identity classes, OAuth client-credentials for booking/provisioning, and mTLS for agents.

## Amendment (2026-11-03)

The original text described an early gap. The following are now implemented in
the controller that this documentation describes:

- Bearer validation on booking and provisioning `/api/v1` routes
- Agent mTLS validation on `POST /api/v1/agents/heartbeat`
- Session create, read, extend, and end
- Fingerprint registration for agent certificates

Still outside `/api/v1` / unfinished for public claims:

- Controller token issuance (intentionally never; use an external IdP)
- Fully automated enrollment exchange / installer-driven cert issuance

## Context

ADR-001 chose OAuth 2.0 client credentials for booking and provisioning
clients, and mutual TLS for each gaming-PC agent. `api/openapi.yaml` declares
those requirements. The running controller enforces them as listed in
[security-model.md](security-model.md).

`GET /api/v1/health` is intentionally unauthenticated.

## Decisions

1. The controller validates bearer tokens on booking and provisioning routes. It does not issue them, and it does not contain a signing key. Agent mTLS on heartbeat is implemented. A fully automated enrollment HTTP exchange remains outside `/api/v1` / unfinished as a product feature. An enrollment-shaped field in a registration response is not a booking access token.
2. Two integration classes and one agent class stay separate.
   - Booking software uses an OAuth client whose production scopes are `sessions:read`, `sessions:write`, `commands:read`, and `devices:read` only when device polling is required.
   - Provisioning software uses a different OAuth client whose production scopes are `devices:write` and `devices:read`.
   - Each gaming PC uses its own certificate, bound to one `device_id`. Agents do not use the client-credentials grant.
   - Production customers do not share clients. Production agents do not share certificates or private keys.
   - The OpenAPI document has one scheme, `bookingOAuth2`, because both integration classes use the same grant. Separate clients are an issuance rule, not a second API.
3. The grant is OAuth 2.0 client credentials (RFC 6749 section 4.4). The API credential is a bearer token (RFC 6750) in `Authorization: Bearer`. No refresh token is issued for this grant. No custom grant, token body, or signature scheme is added.
4. The token endpoint is not part of `/api/v1`. `https://controller.example/oauth/token` stays a placeholder. A deployment supplies the real issuer URL without changing paths or schemas under `/api/v1`.
5. The controller accepts a token only when it is unexpired, unrevoked, issued for this API, carrying the operation's scope, and bound to one `account_id`. Callers cannot submit `account_id`. A missing, expired, or revoked credential returns `401` `unauthorized`. A valid credential with the wrong scope, or the wrong identity class, returns `403` `forbidden`. An agent certificate that does not match the heartbeat `device_id` returns `403` `device_identity_mismatch`. After authentication, another account's identifier returns `404`.
6. `GET /api/v1/health` stays open. It must not gain account, device, session, or lock fields.
7. Revocation of a client or a device certificate affects the next request. Expiry alone is not the revocation mechanism. Rotation of a client secret or a device certificate stays outside `/api/v1` in this version. The replaced credential stops working.
8. The certificate exchange stays outside `/api/v1`. Production enrollment is the sequence in `docs/security-model.md`: an authenticated provisioning registration, a single-use token, a key pair generated on the PC, and proof of possession presented to that future exchange. The private key is not a request field and is not stored in this repository.
9. The idempotent HTTP replay of a registration response and the single use of an enrollment token are different rules. Replay may return the same token to the provisioning client during the provisional window. The exchange must not mint two certificates from that token. The 15-minute figure in ADR-001 is only the provisional HTTP replay example. It is not the production lifetime of an enrollment token.
10. Lab-only or disposable enrollment material is not a production credential and must not be copied into production agents or secret stores. Production enrollment starts from a new registration under a real provisioning client, followed by operator-assisted certificate issuance until automation ships.

## Unresolved choices

These are recorded with their trade-offs. This task does not pick a product or a production number.

| Choice | Options | Why it is still open |
| --- | --- | --- |
| Where the authorization server runs | A neighboring process, not inside the controller | ADR-003 selects that placement. The gaming API still has no token route. |
| Access-token format | Signed JWT, verified with the issuer JWKS | ADR-003 accepts local JWT validation. Opaque tokens are not accepted by this controller. Immediate revocation of an unexpired JWT remains open. |
| Authorization-server product | Keycloak is the reference issuer. Other issuers are usable when they publish the same claims. | The comparison and the remaining mapper settings are in ADR-003. |
| Certificate authority and certificate profile | A private CA is already allowed on a local deployment. | Partially superseded: the controller binds agents by registered certificate fingerprint to one `device_id`. SAN/profile product choices for a finished installer remain open. |
| Enrollment-exchange HTTP shape | Still outside `/api/v1` | The required properties are single use, proof of possession, and no private key in the request. The path, request schema, and response schema are a later contract change, not a correction of the current one. |
| Production lifetimes | Token lifetime, enrollment-token lifetime, and the HTTP replay window | ADR-001's 15-minute examples are provisional. Copying them into production settings would invent an approval this record does not have. |
| Sender-constrained bearer tokens | DPoP or an equivalent later addition | Not required. The cost is a stolen bearer token that works until expiry or revocation. |
| First account bootstrap | An operator procedure outside `/api/v1` | No public registration operation exists, and this task does not add one. |
| Delivery of the enrollment token from the operator to the PC | Local installer input or another out-of-band channel | The constraints are fixed: one delivery, no logs, no booking-database reuse, and no copy in this repository. The physical channel depends on how the agent is installed, which is not built. |

## Consequences

- A later authentication task can implement the existing OpenAPI security requirements without a new public gaming route.
- The development device routes remain a local prototype. They are not the first production enrollment path.
- Booking applications still see one HTTP contract. They do not integrate with a second session protocol or with the agent.
- Audit requirements in `docs/security-model.md` still apply when authentication is built. This record does not add an audit query API.

## Confirmation

No controller module, test, dependency, credential, certificate, or private key was added or changed for this decision.
