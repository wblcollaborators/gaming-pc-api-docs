# Publication checklist (operator)

Complete before creating a public GitHub repository or pushing. This file is
guidance only. Do **not** treat a checked box as legal approval.

## License and copyright

- [x] Copyright holder set to **Weblytic Labs** (2026)
- [x] MIT applies only to `examples/` as written in `LICENSE-EXAMPLES-MIT.md`
- [x] Documentation remains under `LICENSE-NOTICE.md` (not MIT for the whole repo)
- [x] `api/examples/` JSON fixtures documented as documentation copyright, not MIT
- [x] Controller and Windows agent stay proprietary and unpublished
- [ ] Confirm trademarks may appear in the public README (operator sign-off)

## Content

- [ ] Re-read `README.md` reading order and claims
- [x] Confirm OpenAPI lists only implemented routes
- [x] Confirm no controller/agent source or binaries in the tree
- [x] Confirm no finished Windows installer / automated enrollment claim
- [x] Confirm no production-certification claim
- [ ] Confirm ADRs with amendment banners are acceptable for public readers

## Security

- [x] Secret scan of staged files (Phase 3)
- [x] `.gitignore` is present
- [x] No lab IPs or live credentials in staged content

## GitHub (manual; do not auto-run without approval)

- [ ] Create the empty public GitHub repository after approval
- [ ] Initialize Git in this folder (or a clean copy) after approval
- [ ] Push `main` once
- [ ] Set repository description: documentation and MIT examples only; no proprietary source

## After publish

- [ ] Verify the public tree has no `controller/` or `agent/` directories
- [ ] Verify raw GitHub links for OpenAPI and QUICKSTART open correctly
