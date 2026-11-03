# Universal Gaming PC Agent Platform — API Documentation

Public documentation and integration examples for the Universal Gaming PC
Agent Platform. This repository describes the HTTPS JSON API that booking
applications call, and the operational requirements for running a controller
and connecting Windows gaming PCs.

This GitHub material is **documentation and examples only**. It is not a
running API. Developers connect to a **deployed controller HTTPS URL** supplied
by the operator. This repository does **not** include controller source code,
Windows agent source code, binaries, installers, private keys, certificates,
or live credentials.

**Suggested reading order:** [README](README.md) →
[guides/QUICKSTART.md](guides/QUICKSTART.md) →
[api/openapi.yaml](api/openapi.yaml) →
[docs/SECURITY.md](docs/SECURITY.md) /
[docs/security-model.md](docs/security-model.md) →
[examples/](examples/) →
[guides/LOCAL-UBUNTU.md](guides/LOCAL-UBUNTU.md) →
[guides/CLOUD-VPS.md](guides/CLOUD-VPS.md) →
[guides/WINDOWS-AGENT.md](guides/WINDOWS-AGENT.md) →
[guides/CLIENT-DEPLOYMENT.md](guides/CLIENT-DEPLOYMENT.md).

## What the software does

Gaming centers and similar venues take bookings in their own applications
(Odoo, Laravel, custom stacks, and others). Those applications need a
reliable way to authorize play on a specific Windows PC and to learn whether
access was actually granted or locked.

This platform provides:

| Component | Role |
| --- | --- |
| Controller | HTTPS API, PostgreSQL session store, OAuth validation for booking apps, mTLS validation for agents |
| Windows agent | Outbound connection to the controller, command acknowledgement, local access enforcement when enabled |
| Booking application | Customers, payments, PC assignment, business rules — owned by the integrator |

The controller accepts a session request. Confirmed play and verified lock are
separate facts. HTTP **202** with `outcome: accepted` means the controller
stored a command. It does **not** mean the PC unlocked.

## Architecture

```text
Booking app  --OAuth Bearer-->  Booking HTTPS  -->  Controller (localhost)
Windows agent --mTLS-------->  Agent HTTPS    -->  Controller (localhost)
Controller  <---------------->  PostgreSQL
```

- One API contract for local Ubuntu and cloud/VPS deployments:
  `https://{controllerHost}/api/v1`
- Booking clients authenticate with OAuth 2.0 client credentials.
- Agents authenticate with device-bound mutual TLS. Booking bearer tokens
  cannot call agent routes.
- Agents initiate outbound HTTPS. Gaming PCs do not listen for inbound
  controller connections.

See [docs/architecture.md](docs/architecture.md) and
[docs/deployment-models.md](docs/deployment-models.md).

## Implemented API (booking)

| Method | Path | Scope |
| --- | --- | --- |
| `GET` | `/api/v1/health` | none |
| `GET` | `/api/v1/devices` | `devices:read` |
| `POST` | `/api/v1/devices` | `devices:write` (provisioning) |
| `POST` | `/api/v1/sessions` | `sessions:write` |
| `GET` | `/api/v1/sessions/{session_id}` | `sessions:read` |
| `POST` | `/api/v1/sessions/{session_id}/extend` | `sessions:write` |
| `POST` | `/api/v1/sessions/{session_id}/end` | `sessions:write` |

Agent-only (not for booking software):

| Method | Path | Auth |
| --- | --- | --- |
| `POST` | `/api/v1/agents/heartbeat` | mTLS |

Not served (do not call): `GET /devices/{id}`, `GET /devices/{id}/status`,
`GET /commands/{id}`. Details: [api/future-endpoints.md](api/future-endpoints.md).

Contract files: [api/openapi.yaml](api/openapi.yaml),
[CAPABILITIES.json](CAPABILITIES.json).

## Session start, extend, end, and confirmation

1. Create a session with `POST /api/v1/sessions` (this is the start request).
2. Expect HTTP 202 and `outcome: accepted` while play is unconfirmed.
3. Poll `GET /api/v1/sessions/{session_id}` until `start_confirmed` is true
   (session `active`) or a terminal failure/expiry/cancel occurs.
4. Extend only while `active` with `POST .../extend`.
5. End with `POST .../end`. A verified lock is `lock_confirmed: true`, not
   merely `status: ended` or `expired`.

Normative rules: [contracts/session-lifecycle.md](contracts/session-lifecycle.md),
[docs/LIFECYCLE.md](docs/LIFECYCLE.md).

## OAuth authentication

- The controller does **not** issue tokens and has no `/token` route.
- Obtain a JWT from the operator identity provider (client credentials).
- Send `Authorization: Bearer <access_token>` on booking routes.
- Recommended booking scopes: `devices:read`, `sessions:read`,
  `sessions:write`. Use a separate provisioning client for `devices:write`.
- Default audience claim: `gaming-pc-agent-api` unless the operator says
  otherwise.

## Device registration and agent connection

1. A provisioning client registers the device (`POST /api/v1/devices`).
2. The response includes one-time enrollment material.
3. The operator provisions a device client certificate bound to that device.
4. The Windows agent connects outbound over HTTPS with mTLS and sends
   heartbeats to `POST /api/v1/agents/heartbeat`.

See [guides/WINDOWS-AGENT.md](guides/WINDOWS-AGENT.md). Enrollment automation
and a full Windows installer are **not** finished; current installs are
operator-assisted.

## Offline behavior

- Lost connectivity is not success and is not failure by itself.
- An offline or stale device should not be presented to a customer as ready.
- Authorized deadlines still expire. Offline expiry uses the agent clock for
  local enforcement when that feature is enabled.
- Booking apps must poll session state; do not assume unlock from HTTP 202.

## Security requirements

- TLS 1.2+ for booking and agent traffic.
- Separate booking HTTPS and agent mTLS listeners (or hostnames). Do not
  require agent client certificates on the booking front door.
- Bind the controller process to localhost; terminate TLS at a reverse proxy.
- Never embed client secrets, enrollment tokens, or agent private keys in
  source, browsers, or mobile apps.
- Rate limits apply per token `account_id` on booking routes.

See [docs/SECURITY.md](docs/SECURITY.md) and
[docs/security-model.md](docs/security-model.md).

## Local vs cloud deployment

| Mode | Description |
| --- | --- |
| Local Ubuntu | Controller and PostgreSQL on a LAN Ubuntu host; Windows PCs on the same network |
| Cloud / VPS | Same controller application on a reachable host; agents open outbound HTTPS |

Paths and schemas do not change between modes. Installation guidance:

- [guides/LOCAL-UBUNTU.md](guides/LOCAL-UBUNTU.md)
- [guides/CLOUD-VPS.md](guides/CLOUD-VPS.md)
- [guides/CLIENT-DEPLOYMENT.md](guides/CLIENT-DEPLOYMENT.md)

Controller binaries and deployment packages are distributed separately from
this documentation repository.

## Developer quick start

Third-party integrators: start at [guides/QUICKSTART.md](guides/QUICKSTART.md).

Safe offline demos (no network, no Windows PC):

```text
python examples/python/demo.py
php examples/php/demo.php
sh examples/curl-demo.sh
```

Live helpers (operator URL and token required):

```text
examples/python/example_odoo_service.py
examples/php/example.php
examples/curl-examples.sh
```

## Repository layout

```text
api/                      OpenAPI contract and JSON examples
contracts/                Normative session, device, and error rules
docs/                     Architecture, security, integration detail
guides/                   Quick start and deployment guides
examples/                 Python, PHP, and cURL clients (MIT)
CAPABILITIES.json         Machine-readable implemented operations
LICENSE-NOTICE.md              Documentation copyright and proprietary notice
LICENSE-EXAMPLES-MIT.md        MIT license for examples/ only
PUBLICATION-CHECKLIST.md       Operator checklist before GitHub push
GITHUB-PUBLICATION-COMMANDS.md Proposed git/gh commands (do not run until approved)
MANIFEST.txt                   File list for this staging tree
```

## License

Copyright (c) 2026 Weblytic Labs

| Material | License |
| --- | --- |
| `examples/` (Python, PHP, cURL) | [MIT](LICENSE-EXAMPLES-MIT.md) — third parties may copy, modify, and distribute |
| API docs, OpenAPI, `api/examples/` JSON fixtures, contracts, guides | [LICENSE-NOTICE.md](LICENSE-NOTICE.md) — publicly readable; copyright retained; **not** an open-source license for the whole repository |
| Universal Gaming PC Controller | **Proprietary** — not published here |
| Windows Gaming PC Agent | **Proprietary** — not published here |

Public documentation readability does not grant redistribution rights for
proprietary software.

## Status

This documentation matches the implemented `/api/v1` contract. It does not
claim production certification, public SaaS availability, or a finished
Windows GUI installer / automated enrollment.
