# Client deployment guide (local and cloud)

Guide for operators who host a controller for one or more gaming sites and for
integrators who connect booking software to that controller.

## Deployment choices

| Mode | Controller location | Agent connectivity |
| --- | --- | --- |
| Local Ubuntu | Site LAN | Outbound HTTPS to LAN controller |
| Cloud / VPS | Internet-reachable Ubuntu host | Outbound HTTPS from each PC to the VPS |

API paths stay `/api/v1/...` in both modes. See
[../docs/deployment-models.md](../docs/deployment-models.md).

## Shared checklist

1. Dedicated Linux service user for the controller.
2. Dedicated PostgreSQL database (password auth; not world-reachable).
3. Python 3.12 virtualenv and pinned dependencies from the deployment package.
4. Database migrations applied before first start.
5. Controller bound to localhost only.
6. Two nginx TLS sites: booking (no client cert) and agent (mTLS).
7. Operator identity provider configured; booking and provisioning clients
   separated.
8. Agent CA public certificate installed; private key safeguarded.
9. Windows agents enrolled and heartbeating before customer traffic.
10. Health and auth smoke tests from [QUICKSTART.md](QUICKSTART.md) and
    [../docs/CHECKLIST.md](../docs/CHECKLIST.md).

## Local Ubuntu

Follow [LOCAL-UBUNTU.md](LOCAL-UBUNTU.md). Prefer private DNS names even on a
LAN. Do not skip TLS because callers are local.

## Cloud / VPS

Follow [CLOUD-VPS.md](CLOUD-VPS.md). If DNS is not ready, use two TLS ports and
document them for booking apps and agents. Replace ports with hostnames when
DNS is available.

## Booking application integration

Integrators receive:

- Booking HTTPS base URL
- OAuth token URL, client id, client secret, audience
- Scopes `devices:read`, `sessions:read`, `sessions:write`

They do **not** receive:

- Agent CA private key
- Agent client certificates
- Uvicorn loopback URL as the integration endpoint
- Provisioning `devices:write` unless they also operate enrollment

Start with [QUICKSTART.md](QUICKSTART.md) and
[../docs/HANDOVER.md](../docs/HANDOVER.md).

## Windows PCs

Follow [WINDOWS-AGENT.md](WINDOWS-AGENT.md). Confirm each PC appears online in
`GET /api/v1/devices` before selling sessions on that PC.

## Rollback

Keep the previous controller package and a PostgreSQL dump taken before each
upgrade. Stop the service, restore the tree and database if needed, restore
nginx site files if they changed, then start and re-check health.

## Out of scope for this documentation repository

- Publishing controller or agent source
- Creating cloud accounts
- Issuing production certificates
- Enabling Windows enforcement without an approved test plan
