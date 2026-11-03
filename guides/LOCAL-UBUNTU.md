# Local Ubuntu controller installation

This guide describes **requirements and known limitations** for running the
controller on a local Ubuntu host for lab or on-premise use. It does not ship
the controller application. Obtain the controller deployment package from the
platform operator.

## Supported roles

| Role | Typical host |
| --- | --- |
| Controller + PostgreSQL + nginx | Ubuntu server on the LAN |
| Booking application | Same LAN or a host that can reach booking HTTPS |
| Windows gaming PC | Same LAN; agent opens outbound HTTPS to the controller |

Current internal testing uses a local Ubuntu LAN controller and a Windows test
PC. That is a lab topology, not a published SaaS endpoint.

## Software requirements

| Component | Requirement |
| --- | --- |
| OS | Ubuntu 22.04 LTS or newer recommended |
| Python | **3.12** for the certified controller runtime. Ubuntu 22.04 system Python is 3.10 and is **not** the certified runtime. Install Python 3.12 (for example via a supported PPA) and create a virtualenv with it. |
| PostgreSQL | 14+ on localhost; dedicated database and role with password authentication |
| nginx | Existing or new install; TLS termination for booking and agent listeners |
| systemd | Service unit for the controller process |

Do not install controller packages into the system Python. Do not expose the
uvicorn process on a public interface.

## Network layout (required)

Use **two** TLS front doors:

| Listener | Client authentication | Callers |
| --- | --- | --- |
| Booking HTTPS | Server certificate only (`ssl_verify_client off`) | Booking / OAuth clients |
| Agent mTLS | `ssl_verify_client on` against the agent CA | Windows agents only |

Until DNS hostnames exist, two TLS ports on the Ubuntu host address are
acceptable. Prefer two hostnames on port 443 when DNS is available.

Both listeners proxy to the controller on `127.0.0.1` (configurable port).
Booking nginx must clear agent identity headers. Agent nginx must overwrite
the client-certificate header from the verified TLS session.

A single nginx `server` block with `ssl_verify_client on` for all paths forces
booking clients to present agent certificates. That layout is **not** suitable
for third-party booking integration.

## Configuration (names only)

Operator-supplied environment (no secret values in this document):

- `OAUTH_ISSUER`, `OAUTH_AUDIENCE`, `OAUTH_ACCOUNT_CLAIM`, optional `OAUTH_JWKS_URI`
- `DATABASE_URL`
- `AGENT_TLS_CA_FILE`, `AGENT_TLS_TRUSTED_PROXY`, `AGENT_TLS_TRUSTED_PROXY_PEERS`, `AGENT_TLS_CLIENT_CERT_HEADER`
- `CONTROLLER_HOST`, `CONTROLLER_PORT`
- Rate-limit knobs: `RATE_LIMIT_*`

Must stay unset in real deployments: `CONTROLLER_ENABLE_DOCS`,
`AGENT_AUTH_TEST_CERTIFICATE_INJECTION`.

The controller does not migrate the database on startup. Apply SQL migrations
from the deployment package before the first start.

## Identity provider

The controller does not issue OAuth tokens. A standards-compliant identity
provider must mint booking and provisioning JWTs. Lab-only issuers are not
part of this documentation repository.

## Known limitations (local)

- No turnkey apt package or snap is published in this documentation release.
- Certificate issuance for agents is operator-assisted; full enrollment
  automation is unfinished.
- `/docs` interactive API pages stay off unless explicitly enabled for a
  private lab and must not be enabled on a shared listener.
- Local HTTP to uvicorn is for operator health checks only. Integrators must
  use the HTTPS front door.
- This guide does not configure Windows enforcement or start live sessions.

## Health checks

```text
curl -sS https://BOOKING_HOST/api/v1/health
```

Expect `{"status":"ok"}` (process liveness only).

A booking call without a bearer token to `/api/v1/devices` must be HTTP 401.
`POST /api/v1/agents/heartbeat` with a booking bearer token must be HTTP 403.

## Related guides

- [CLOUD-VPS.md](CLOUD-VPS.md)
- [CLIENT-DEPLOYMENT.md](CLIENT-DEPLOYMENT.md)
- [WINDOWS-AGENT.md](WINDOWS-AGENT.md)
