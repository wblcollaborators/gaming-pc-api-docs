# Windows gaming PC agent — installation and enrollment

This guide describes **requirements** for connecting a Windows gaming PC to
the controller. It does **not** include agent source code, a finished GUI
installer, or private enrollment material.

## What the agent does

- Opens **outbound** HTTPS to the agent mTLS listener.
- Authenticates with a device-bound client certificate.
- Sends heartbeats to `POST /api/v1/agents/heartbeat`.
- Receives session commands and reports acknowledgement / execution /
  verified-effect results.
- Optionally enforces local access policy when the operator enables that mode.

The agent does **not** accept inbound controller connections. Booking apps do
not call the heartbeat route.

## Prerequisites

| Item | Requirement |
| --- | --- |
| OS | Supported Windows desktop/server SKU for the agent build you received |
| Network | Outbound HTTPS to the agent controller hostname/port |
| Device record | Created with `POST /api/v1/devices` using a provisioning OAuth client |
| Client certificate | Issued for that device and registered with the controller |
| Config | Operator-supplied agent configuration file (path and contents are deployment-specific) |

## Enrollment flow (current)

1. Provisioning client registers the device and receives one-time enrollment
   material.
2. Operator generates or obtains a client certificate for that device.
3. Operator registers the certificate fingerprint with the controller.
4. Operator installs the agent binary and configuration on the Windows PC.
5. Agent starts and begins heartbeats over mTLS.

## Unfinished automation (explicit)

The following are **not** complete in the current public documentation release:

| Work item | Status |
| --- | --- |
| End-user GUI installer (MSI / setup wizard) | Not finished |
| One-click enrollment that fetches certificates without an operator | Not finished |
| Automatic public CA enrollment for agents | Not finished |
| In-box Windows Store distribution | Not offered |
| Automatic enablement of enforcement on first install | Intentionally off by default |

Until those ship, installation is **operator-assisted**: copy the approved
binary, place certificates and configuration, and start the process under the
operator's runbook.

## Security rules for operators

- Keep `windows_enforcement` off unless a controlled test is approved.
- Never commit `agent.toml`, private keys, or enrollment tokens to git.
- One device certificate per PC. Do not share keys across machines.
- Do not place the agent CA private key on gaming PCs.
- Booking OAuth secrets do not belong on the gaming PC.

## Verifying connection

After the agent is running, the operator checks device connectivity through
the booking API (`GET /api/v1/devices`) using a token for that account. Look
for `connectivity: online` and a recent `last_seen_at`. Booking software must
not invent a device-status GET route; list devices instead.

## Related docs

- [../docs/agent-heartbeat.md](../docs/agent-heartbeat.md)
- [../docs/agent-mtls.md](../docs/agent-mtls.md)
- [../docs/agent-command-delivery.md](../docs/agent-command-delivery.md)
- [CLIENT-DEPLOYMENT.md](CLIENT-DEPLOYMENT.md)
