# Production deployment checklist

This is an operator checklist. Completing it does not by itself make a
deployment production-certified. Do not expose uvicorn on a public interface.

## Listener and TLS

- [ ] Bind the controller to `127.0.0.1` (or a private socket) only.
- [ ] Terminate booking HTTPS and agent mTLS on a reverse proxy in front of that listener.
- [ ] Start uvicorn with `--no-proxy-headers` so `X-Forwarded-For` cannot change the TCP peer used for mTLS header trust.
- [ ] TLS 1.2 or later. Prefer TLS 1.3.
- [ ] `CONTROLLER_ENABLE_DOCS` is unset on production listeners.

## Agent mTLS

- [ ] `AGENT_TLS_CA_FILE` points at the live agent CA. Missing CA fails closed with HTTP 503 `agent_auth_unavailable`.
- [ ] `AGENT_TLS_TRUSTED_PROXY=1` only when the proxy verifies client certificates.
- [ ] `AGENT_TLS_TRUSTED_PROXY_PEERS` is the proxy's actual TCP address (usually `127.0.0.1`). Do not use `0.0.0.0/0`.
- [ ] The proxy overwrites `X-Forwarded-Tls-Client-Cert` with the verified certificate and clears `X-Agent-Test-Client-Certificate`.
- [ ] `AGENT_AUTH_TEST_CERTIFICATE_INJECTION` is unset. The controller ignores that header whenever trusted-proxy mode is on.
- [ ] Booking bearer tokens still receive HTTP 403 on `/api/v1/agents/*`.

## OAuth

- [ ] `OAUTH_ISSUER`, `OAUTH_AUDIENCE`, and `OAUTH_ACCOUNT_CLAIM` match the live identity provider.
- [ ] Booking and provisioning are separate confidential clients.
- [ ] Access-token lifetime is short (see [jwt-access-tokens.md](jwt-access-tokens.md)).
- [ ] A procedure exists to disable a stolen client at the identity provider.

## Rate limits

- [ ] `RATE_LIMIT_ENABLED=1` (default).
- [ ] Session write, booking read, and device write limits are chosen for this deployment.
- [ ] PostgreSQL is the shared counter store. Every controller worker must use the same `DATABASE_URL`.
- [ ] Without PostgreSQL the limiter cannot apply a shared budget; booking calls fail with `storage_unavailable`.

## Data

- [ ] Apply migrations, including `005_api_rate_windows.sql`.
- [ ] PostgreSQL is not reachable from untrusted networks.

## Third-party developers

Give them [HANDOVER.md](HANDOVER.md) and the live booking HTTPS base URL. Do not give them the uvicorn port, agent CA private key, or client secrets.
