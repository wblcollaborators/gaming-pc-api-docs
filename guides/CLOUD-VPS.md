# Cloud / VPS controller deployment

Same controller application and same `/api/v1` contract as local Ubuntu.
Only the hostname and operational placement change.

## When to use cloud / VPS

- Booking software and gaming PCs are not on one private LAN.
- Multiple sites share one controller account model.
- The operator prefers a hosted Ubuntu VPS (any provider) with outbound agent
  access from each gaming PC.

## Requirements

| Item | Requirement |
| --- | --- |
| Host | Ubuntu 22.04+ VPS with a public or privately routed address |
| Python | 3.12 virtualenv (certified). Do not use system 3.10 as the certified runtime. |
| PostgreSQL | Dedicated database; localhost or private network only |
| nginx | Existing install supported; add **new** site files without replacing unrelated sites |
| DNS | Recommended. Until DNS exists, two TLS ports on the VPS address can front booking vs agent traffic |
| Firewall | Allow booking HTTPS and agent mTLS inbound; do not publish PostgreSQL or uvicorn |

## Split TLS (required)

| Front door | Client certs | Traffic |
| --- | --- | --- |
| Booking HTTPS | Off | OAuth booking and provisioning clients |
| Agent mTLS | On (agent CA) | Windows agents |

Do not put both modes on one `server` block. Do not require Windows agent
certificates from OAuth clients.

Trusted reverse-proxy peers must be the actual nginx TCP peer (usually
loopback). Wildcards such as `0.0.0.0/0` are ignored and fail closed.

## Installation outline

Exact package filenames are distributed separately from this documentation
repository. Typical steps:

1. Create a dedicated Linux service user.
2. Install Python 3.12, PostgreSQL, and nginx packages.
3. Extract the controller deployment package to an application directory.
4. Create the database and fill an environment file (never commit secrets).
5. Create a virtualenv and install pinned requirements from the package.
6. Apply database migrations.
7. Install the systemd unit and start the service (loopback bind only).
8. Add two nginx site files for booking and agent listeners; `nginx -t`; reload.
9. Place the agent CA **public** PEM on the host. Keep the CA private key off
   the application account.

## Production-safe defaults

- `CONTROLLER_ENABLE_DOCS` unset
- `AGENT_AUTH_TEST_CERTIFICATE_INJECTION` unset
- Rate limiting enabled
- Uvicorn with proxy-header handling that does not let clients spoof the TCP
  peer used for mTLS header trust
- Separate OAuth clients for booking and provisioning

## What this guide does not provide

- Automatic creation of a cloud account or VPS
- Automatic DNS or public CA certificates
- A finished Windows agent installer
- OAuth client creation inside Keycloak, ZITADEL, or similar
- Claims of production certification

## Related guides

- [LOCAL-UBUNTU.md](LOCAL-UBUNTU.md)
- [CLIENT-DEPLOYMENT.md](CLIENT-DEPLOYMENT.md)
- [WINDOWS-AGENT.md](WINDOWS-AGENT.md)
- [../docs/production-checklist.md](../docs/production-checklist.md)
