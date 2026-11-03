# Planned endpoints (not in the published contract)

These operations are **not served** by the controller and are **not** part of
`api/openapi.yaml`. Independent booking applications must not call them.
Python, PHP, and cURL examples in `examples/` do not call them.

Until a later approved task implements a route, use the published substitute.

| Method | Path | Planned scope | Use instead |
| --- | --- | --- | --- |
| GET | `/api/v1/devices/{device_id}` | `devices:read` | `GET /api/v1/devices` |
| GET | `/api/v1/devices/{device_id}/status` | `devices:read` | `GET /api/v1/devices` and the nested `status` object |
| GET | `/api/v1/commands/{command_id}` | `commands:read` | `GET /api/v1/sessions/{session_id}` plus the `command` object on create, extend, and end |

Unauthenticated calls to these paths receive HTTP 401. A valid booking token
receives HTTP 404 `not_found` with the Error schema. That is not
`session_not_found` and is not a command status.

Do not treat this file as a promise that the routes will be added. Adding them
requires a separate approval and must not change existing session semantics.
