# License and copyright notice

This repository is a **documentation and integration-examples** package for the
Universal Gaming PC Agent Platform. It is not a release of the controller or
the Windows agent.

## Copyright holder

Copyright (c) 2026 Weblytic Labs

## What is licensed how

| Material | Location | License |
| --- | --- | --- |
| Integration examples (Python, PHP, cURL) | `examples/` | [MIT](LICENSE-EXAMPLES-MIT.md) |
| API docs, OpenAPI, JSON fixtures, contracts, guides, ADRs | `api/`, `contracts/`, `docs/`, `guides/`, and root Markdown other than the MIT examples license | Copyright (c) 2026 Weblytic Labs — all rights reserved; publicly readable on GitHub; **not** an open-source license for the whole repository |
| Controller implementation | Not in this repository | **Proprietary** — not licensed here |
| Windows agent implementation | Not in this repository | **Proprietary** — not licensed here |

Public readability of the documentation is **not** the same as an open-source
license for all documentation. Weblytic Labs retains copyright. No broader
grant is implied unless Weblytic Labs publishes one.

## Documentation copyright

- You may read the public documentation on GitHub.
- You may use the documented HTTP contract to build a booking integration that
  calls a controller URL the operator supplies.
- You may **not** treat OpenAPI schemas, contracts, or guides as permission to
  copy, republish, or relicense the proprietary controller or agent.
- Public API documentation does **not** grant rights to redistribute
  proprietary software.

## `api/examples/` JSON fixtures

Files under `api/examples/` are **documentation fixtures** (sample request and
response JSON for the OpenAPI contract). They are **not** MIT-licensed client
code. They fall under this documentation copyright notice, not under
[LICENSE-EXAMPLES-MIT.md](LICENSE-EXAMPLES-MIT.md).

Reusable integration code that third parties may copy, modify, and distribute
under MIT lives only under `examples/` (Python, PHP, and cURL helpers).

## Mixed directories and copied snippets

- Files under `examples/` are MIT (see [LICENSE-EXAMPLES-MIT.md](LICENSE-EXAMPLES-MIT.md)).
- Markdown guides that *quote* example HTTP requests remain documentation.
- Copying a whole example client file from `examples/` into your product is
  covered by MIT; keep the copyright and permission notice.
- `CAPABILITIES.json` and `api/openapi.yaml` describe the public HTTP contract.
  They do not include proprietary source and do not license the controller.
- Do not paste proprietary controller or agent source into forks of this repo.

## Proprietary software (not published here)

The Universal Gaming PC Controller and the Windows Gaming PC Agent remain
proprietary. This documentation-only repository must not contain their source
code or binaries. Receiving documentation does not include a license to those
products.

## Trademarks

No trademark license is granted by this notice or by the MIT example license.
