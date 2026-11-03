# JWT access-token security (S5)

The controller does not issue booking tokens and does not keep a revocation
list of access tokens. Operators disable compromised clients at the identity
provider.

## What the controller checks

On every booking and provisioning call it verifies:

- RS/ES 256–512 signature against the issuer JWKS
- `iss`, `aud`, and `exp`
- `account_id` (configured claim) and `client_id` or `azp`
- the scope required by that route

A token that fails those checks receives HTTP 401 `unauthorized`. Missing
scope or client identity receives HTTP 403 `forbidden`.

## Recommended access-token lifetime

Use short-lived client-credentials access tokens. A practical starting point
is **5 to 15 minutes**. ADR-001 recorded 15 minutes as a provisional example;
choose the production value explicitly.

Shorter lifetime reduces the window in which a stolen token can be replayed.
It does not replace client-secret protection or TLS.

## How to disable a compromised OAuth client

1. Disable or delete that confidential client in the identity provider.
2. Rotate the client secret. Do not reuse the old secret.
3. Stop publishing the old signing key from JWKS only after every token signed
   with it has expired, or after you are willing to fail all outstanding tokens
   that used that key.

The controller will reject new tokens for a disabled client once the identity
provider no longer issues them. **Tokens already issued remain valid until
`exp`**, or until the signing key is removed from JWKS.

Agent certificates are different: setting `revoked_at` in PostgreSQL rejects
the next heartbeat with HTTP 401. There is no equivalent in-process denylist
for JWTs.

## What this process will not do

It will not mint tokens, store refresh tokens, or query an OAuth revocation
endpoint until a later approved task. DPoP and other sender-constrained bearer
schemes are also out of scope.

Booking software should request a new token when it receives HTTP 401, then
retry the original call with the same Idempotency-Key.
