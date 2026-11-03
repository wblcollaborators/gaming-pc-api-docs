# Integration examples

**License:** MIT — see [../LICENSE-EXAMPLES-MIT.md](../LICENSE-EXAMPLES-MIT.md).  
Copyright (c) 2026 Weblytic Labs.

Python, PHP, and cURL call the **same** `/api/v1` HTTPS JSON contract. There
is no language-specific controller API.

GitHub hosts this documentation. It is **not** a running API. Obtain
`CONTROLLER_URL` and an OAuth access token from the operator before any live
call.

| Path | Purpose |
| --- | --- |
| `python/demo.py` | Offline canned walk; never confirms Windows effects |
| `python/gaming_controller_client.py` | Booking client library |
| `python/example_odoo_service.py` | Live helper sketch (not an Odoo module) |
| `php/demo.php` | Offline canned walk |
| `php/GamingControllerClient.php` | Booking client class |
| `php/example.php` | Live helper sketch (not a Laravel app) |
| `curl-demo.sh` | Printed contract; no network |
| `curl-examples.sh` | Live HTTPS examples |

Export `CONTROLLER_URL` and `ACCESS_TOKEN` only for live helpers. Never commit
those values.

This MIT grant does **not** license the proprietary controller or Windows agent.
