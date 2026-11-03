# Production integration checklist (booking developers)

This is the integrator checklist. The operator checklist is
`docs/production-checklist.md`. Completing this list does not certify a
production deployment.

## Before writing code

- [ ] Received the HTTPS controller base URL (not a uvicorn port).
- [ ] Received OAuth token URL, audience, booking client id, and client secret.
- [ ] Booking client has `devices:read`, `sessions:read`, and `sessions:write`.
- [ ] Provisioning (`devices:write`) is a separate client you do not use.
- [ ] Read [../guides/QUICKSTART.md](../guides/QUICKSTART.md) and [HANDOVER.md](HANDOVER.md).
- [ ] Ran the local demo (`python demo.py` or `php demo.php`) and saw
      `play_confirmed false`.

## Client implementation

- [ ] TLS certificate verification is on.
- [ ] HTTP methods are uppercase.
- [ ] `Idempotency-Key` is persisted per booking operation and reused on retry.
- [ ] GET session is used to poll; command GET routes are not called.
- [ ] HTTP 202 is treated as stored, not unlocked.
- [ ] Customers see “ready to play” only when `start_confirmed` is true.
- [ ] “PC restricted” is shown only when `lock_confirmed` is true.
- [ ] Offline or stale devices are not advertised as ready.
- [ ] 401 obtains a new token; 403/404 do not retry the same input.
- [ ] 429 waits `Retry-After`; 503 retries the same Idempotency-Key.
- [ ] Unknown JSON response fields are ignored.
- [ ] Client secrets and access tokens are not in source, logs, or tickets.

## Go-live with the operator

- [ ] Operator has a production identity provider (lab TokenAuthority is not it).
- [ ] Operator has confirmed the live audience and account claim.
- [ ] You tested against a lab PC only with written permission.
- [ ] You did not enable or assume Windows enforcement from this kit.

## Operator production blockers you cannot close

These remain with the platform operator:

- Production hosting, reverse-proxy TLS, and mTLS
- Identity provider client disable procedure
- Rate-limit numeric values
- Windows agent heartbeat and enforcement on the PC
