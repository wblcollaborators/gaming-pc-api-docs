# ADR-001: Technology and architecture

- Status: Baseline accepted. Amended 2026-11-03 for public documentation accuracy.
- Original date: 2026-10-09
- Scope: Architecture and API contract.

## Amendment (2026-11-03)

Implemented since the original ADR text: booking session create/read/extend/end,
agent mTLS heartbeat, command delivery on heartbeat, agent certificate store,
and booking API rate limits. Extension and end still do **not** lock a PC by
themselves; verified lock remains `lock_confirmed`. The Windows agent exists as
a separate private binary; a finished public installer and automated enrollment
exchange are not claimed complete. See [../guides/WINDOWS-AGENT.md](../guides/WINDOWS-AGENT.md).

## Context

Independent booking products need one way to authorize a gaming-PC session, extend it, and end it. Those products include PHP, Odoo/Python, and other HTTP clients. The first PCs are Windows. Linux PCs are a later target. Some operators will host the controller locally, and some will host it in the cloud. The controller must not depend on a booking product's database, language, or hosting model.

## Baseline decisions

1. The public interface is REST JSON at `/api/v1`, specified by OpenAPI 3.1 in `api/openapi.yaml`.
2. The controller is one Python FastAPI application with a PostgreSQL database. The same application and the same contract are used in the cloud and on-premise. (Original ADR text said “future controller”; the controller exists as a proprietary product outside this docs repo.)
3. The Windows agent is Rust. It communicates with outbound HTTPS. Persistent connections are deferred and, if added, must preserve this session and command contract. (Original ADR text said “future Windows agent”; the agent exists as a proprietary binary outside this docs repo. A finished public installer is not claimed.)
4. The heartbeat request carries agent status and command results. The heartbeat response carries pending commands. That keeps agent coordination inside the endpoint list of this version.
5. Linux support is a later OS enforcement module and `platform: linux` on the current device schema. It is not a new booking API.
6. Booking and provisioning clients use OAuth 2.0 client credentials. Agents use mutual TLS certificates bound to a device. Bearer validation and agent certificate validation are implemented. The issuer choice is ADR-003.
7. The only command types are `start_session`, `extend_session`, and `end_session`.
8. Resources are scoped to the account of the caller credential. Another account's identifiers are answered with `404`.
9. Controller acceptance and confirmed device effect are different outcomes, represented by `outcome`, `start_confirmed`, `lock_confirmed`, and `device_effect_confirmed`.
10. Delivery is at-least-once. Idempotency keys and `command_id` define safe replay. Exactly-once network delivery is not a guarantee.
11. Within version 1, the contract may gain optional response fields and new API error codes. It does not silently gain session statuses or command types. Clients should ignore unknown response fields.
12. One heartbeat carries at most 20 command results. Further results are sent on a following heartbeat.

## Consequences

- Booking applications integrate with HTTP and JSON only.
- The controller is the only component that writes session and command state in PostgreSQL.
- The API shows a confirmed lock only after an authenticated enforcement result. What the agent does with a deadline while the controller is unreachable is undecided.
- No Odoo module, PHP SDK, or other language binding is part of the platform contract.

## Provisional design examples

The numbers below appear in examples so the contract has concrete timestamps. They are not production-approved security settings, and they are not guarantees of an implementation. A later task has to choose production values explicitly.

| Item | Provisional example |
| --- | --- |
| Device stale threshold | 90 seconds |
| Agent clock skew | 30 seconds |
| `start_session` command TTL | 120 seconds, and not later than the session deadline |
| `extend_session` command TTL | 120 seconds, and not later than the requested new deadline |
| `end_session` command TTL | 300 seconds |
| Idempotency-key retention | 24 hours |
| Enrollment-token replay retention | 15 minutes |
| OAuth access-token lifetime | 15 minutes |

## Unresolved

| Topic | What is undecided |
| --- | --- |
| License (documentation repo) | Superseded for this public docs package: integration examples under `examples/` are MIT ([../LICENSE-EXAMPLES-MIT.md](../LICENSE-EXAMPLES-MIT.md)); documentation copyright and proprietary controller/agent rights are in [../LICENSE-NOTICE.md](../LICENSE-NOTICE.md). Controller and agent source remain proprietary and are not in this repository. |
| TLS cipher suites | TLS 1.2 or later is required. The cipher policy is undecided. |
| Certificate authority and enrollment exchange | The production sequence is recorded in ADR-002. The exchange stays outside `/api/v1`. The CA product, certificate profile, and HTTP shape remain undecided. |
| Credential rotation endpoint | ADR-002 confirms that rotation stays outside `/api/v1` in this version. Revocation must affect the next request. A later replacement operation is still undecided. |
| OAuth request signing | ADR-002 confirms that DPoP is not required. A stolen bearer token remains a residual risk. Adding sender constraint later is still open. |
| Rate-limit numbers | Rate limiting is required. The numbers are deployment configuration. |
| Audit retention and audit query API | Audit events are required. Retention and a read API are undecided. |
| Local deadline persistence across agent restart | Undecided. The API does not assume a deadline survives a restart. |
| Wall-clock changes and safe deadline calculation | Undecided. The controller compares `expires_at` with its own clock when it processes a request. Agent clock steps are not specified. |
| Loss of controller connectivity | The controller keeps the session status, sets device access to `unknown` after the freshness window, and does not infer lock, start, or failure. What the PC does during the outage is undecided. |
| Failure to confirm an end-session operation | The command can become `expired`, the session can stay `ending` or become `expired`, and `lock_confirmed` stays false. Automatic replacement of that command is undecided. |
| Escalation and operator notification when locking remains unconfirmed | Undecided. Silence must not be stored as `lock_confirmed` or as session `failed`. |
| First account and first OAuth client | Bootstrap of the first platform account is outside `/api/v1` and is undecided. |
| Session search | Callers that lose both the idempotency key and `external_reference` cannot search sessions in this version. |
| Site or location grouping | Devices have `display_name` and `external_reference`. A location object is not in this version. |
| Agent update format | Updates must be signed. The package format and distribution flow are undecided. |
| Alerting | A contradictory unlock or lock report is audited. Operator alerting is undecided. |
| Database schema | Device, registration-idempotency, list-cursor, session, command, agent-certificate, and rate-limit tables are implemented in the private controller package. Durable audit-event storage remains an open product decision. |

## Recorded limitations

These are constraints of the version-1 contract, not defects that require a different architecture.

- A one-time enrollment secret cannot be reconstructed after its replay window. The idempotent response in that window is an explicit, time-bounded exception.
- Controller-generated command expiry can be superseded by a late agent success only in the cases in `contracts/session-lifecycle.md`. That exception is how an outage still produces a truthful lock confirmation.
- `expired` means the authorized deadline was reached. It is not a start failure and not a lock confirmation. `ended` means an explicit end was executed and is also not a lock confirmation. `lock_confirmed` is a separate field.
- Command statuses `acknowledged` and `executed` were added so delivery, acknowledgement, execution, and verified effect are not the same event. Session status names are unchanged.
- The heartbeat is the agent command channel so this version does not add a second agent protocol. A later persistent connection has to carry the same commands and results.

No concrete contradiction was found that requires replacing the REST contract, the single controller, or the Windows-first agent plan.
