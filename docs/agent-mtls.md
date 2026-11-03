# Agent mutual TLS

Gaming PC agents authenticate with a pre-provisioned client certificate.
Booking and provisioning integrations keep using OAuth bearer tokens. The two
credential classes never authorize the same routes.

## What the controller verifies

For `POST /api/v1/agents/heartbeat` the controller:

1. Rejects OAuth bearer tokens with HTTP `403` `forbidden`.
2. Obtains the client certificate from a trusted source (see below).
3. Verifies the certificate chains to `AGENT_TLS_CA_FILE`.
4. Checks the certificate validity period with the controller clock.
5. Computes the SHA-256 fingerprint of the DER encoding.
6. Loads the fingerprint from the agent-certificate store in PostgreSQL.
7. Rejects unknown, expired, or revoked registrations with HTTP `401`
   `unauthorized`.
8. Binds the caller to exactly one `device_id` and `account_id` from that row.
9. Compares the heartbeat `device_id` to the bound identity. A mismatch returns
   HTTP `403` `device_identity_mismatch`.

Heartbeat storage and command exchange are implemented. Booking software must
not call this route. See [agent-heartbeat.md](agent-heartbeat.md) and
[agent-command-delivery.md](agent-command-delivery.md).

## Where the certificate comes from

| Mode | Use | Certificate source |
| --- | --- | --- |
| Trusted TLS proxy | Production and operator testing | A reverse proxy terminates mTLS, verifies the client against the same CA, and forwards the PEM in a configured header. The controller accepts that header only when trusted-proxy mode is enabled and the immediate TCP peer is listed. Wildcard peers such as `0.0.0.0/0` are ignored. The controller re-verifies the PEM against `AGENT_TLS_CA_FILE`. |
| ASGI TLS extension | Future-compatible | If the server sets `scope["extensions"]["tls"]["client_cert"]`, the controller reads it directly. |
| Test injection | Automated tests only | Enabled only when trusted-proxy mode is off and a test-only environment flag is set. Must stay unset in staging and production. |

Bind the application to localhost. Start it so clients cannot change the TCP
peer used for the trusted-proxy check. Missing `AGENT_TLS_CA_FILE` fails closed
with HTTP `503`.

## Provisioning (operator-assisted)

1. Register the device with OAuth `devices:write`.
2. Issue a client certificate for that device from the operator CA.
3. Record the certificate fingerprint in the controller database for that
   `device_id`, `account_id`, and credential id.
4. Install the certificate and private key only on that Windows PC.

Private keys stay on the gaming PC (or operator secure storage). Only the
fingerprint and metadata are stored in PostgreSQL.

Lab helper scripts that generate disposable certificates exist in the private
controller package. They are not part of this public documentation repository.

## Deployment assumptions

- The same private CA (or public CA profile) signs every agent certificate the
  controller trusts.
- One active certificate row exists per device.
- One fingerprint maps to one device globally.
- Certificate revocation is recorded in PostgreSQL. The next request fails
  closed with HTTP `401`.
- TLS handshake failure for an untrusted client may occur before any HTTP
  status is returned.
- Booking HTTPS and agent mTLS use separate listeners or hostnames.
