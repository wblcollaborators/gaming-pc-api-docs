# ADR-003: Identity provider and bearer-token validation

- Status: Accepted for controller token validation. Amended 2026-11-03.
- Original date: 2026-10-09
- Scope: Which issuer operators should run, and how this controller validates access tokens. This record does not deploy an identity provider and is not a production certification.

## Decision

Keycloak is the reference OAuth 2.0 / OpenID Connect issuer for both cloud and customer-managed on-premises deployments.

The controller does not link against Keycloak. It validates a signed JWT using OIDC discovery and the issuer's JWKS. Any issuer that publishes the claims below can replace Keycloak without a controller change. The controller does not issue tokens, does not embed a provider signing key, and does not read provider-specific role claims.

## What was reviewed

Official or primary sources checked for this decision:

- Keycloak's securing-apps document, which describes the realm certificate endpoint, OIDC discovery, the client-credentials grant, and local JWT validation with the realm public keys: `https://www.keycloak.org/securing-apps/oidc-layers`.
- Keycloak's service-account procedure, which shows `grant_type=client_credentials` against `/realms/{realm}/protocol/openid-connect/token` and states that only an access token is returned: the server-admin topic `proc-using-a-service-account`.
- ZITADEL's client-credentials guide and OIDC endpoints, including `jwks_uri` at `/oauth/v2/keys`: `https://zitadel.com/docs/guides/integrate/service-accounts/client-credentials` and `https://zitadel.com/docs/apis/openidoauth/endpoints`.
- The ZITADEL `LICENSE` file at `https://raw.githubusercontent.com/zitadel/zitadel/main/LICENSE`, which is the GNU Affero General Public License version 3.
- Auth0 and Amazon Cognito comparison material that describes both as cloud-hosted and not self-hostable, and Microsoft Entra ID material that describes cloud IAM with directory federation rather than a customer-run token server.

| Provider | Cloud | Customer-managed on-premises | OIDC discovery and JWKS | Client credentials and scopes | License and lock-in | Fit for a separate agent certificate |
| --- | --- | --- | --- | --- | --- | --- |
| Keycloak | Run the same server on your own cloud hosts. There is no first-party Keycloak SaaS. | The same distribution runs on a customer server. | Realm discovery and a certificate JWKS are documented. Access tokens are signed JWTs and can be checked locally. | Documented client-credentials grant. Scopes are client scopes. Audience and extra claims need protocol mappers. | Apache-2.0. Operational cost is a JVM service and its database. Tokens stay standard if mappers emit standard claims. | Agent mTLS stays at the controller TLS listener. Keycloak is not on that path. |
| ZITADEL | ZITADEL Cloud and a self-hosted build exist. | Self-hosted. Organizations are a built-in tenant model. | Documented discovery and `/oauth/v2/keys`. JWT access tokens are optional and must be turned on. | Documented client-credentials grant. Several authorization claims use `urn:zitadel:` scopes. | The current upstream license file is AGPL-3.0. That copyleft is a deployment obligation this product does not need to take on. | Same separation as Keycloak, if the controller ignores ZITADEL-specific claims. |
| Auth0, Amazon Cognito, Microsoft Entra ID | Managed cloud issuers with standard OIDC options. | Not a customer-run token server. Entra can federate an existing directory; it does not replace an on-premises issuer for a site that cannot depend on that cloud. | Usable when they publish JWKS and the claims this controller requires. | Client credentials exists, with vendor-specific audience and scope configuration. | Proprietary services. Moving tenants later is an operational project. | Usable only as the integration issuer. They do not become the agent certificate authority. |

## Why Keycloak

The platform must use one API in the cloud and on a customer site. The issuer therefore has to be software the customer can run, not only a vendor region. Keycloak is that software, its client-credentials flow matches ADR-002, and its license does not add an AGPL obligation. ZITADEL is technically capable and has a stronger organization model, but AGPL-3.0 is the reason it is not the reference. A managed issuer remains available for an operator who only needs cloud and who configures the same claims.

## Token rules the controller enforces

Configuration is the OAuth environment variables supplied with the controller package (`OAUTH_ISSUER`, `OAUTH_AUDIENCE`, `OAUTH_ACCOUNT_CLAIM`, optional `OAUTH_JWKS_URI`). None of them has a silent default. If issuer, audience, or account claim is missing or unsafe, device requests fail with `401`. Health does not consult the issuer.

1. Read `Authorization: Bearer`. Absence is `401` `unauthorized`.
2. Load signing keys from `OAUTH_JWKS_URI` or from `{OAUTH_ISSUER}/.well-known/openid-configuration`. The discovery document's `issuer` must equal `OAUTH_ISSUER`. Key URLs must be `https`, or `http` only for `127.0.0.1` or `localhost`. A fetch failure is `401`.
3. Verify the signature with that key. Allowed algorithms are RS256, RS384, RS512, ES256, ES384, and ES512. Decoding without verification is not acceptance.
4. Require `iss` to equal `OAUTH_ISSUER`, `aud` to equal `OAUTH_AUDIENCE`, and `exp` to be in the future. `nbf` and `iat`, when present, must be consistent with the current time. Leeway is zero. A failure is `401`.
5. Require an integration client identifier in `client_id` (RFC 9068) or, if that claim is absent, `azp` (OpenID Connect). If neither is present, the response is `403` `forbidden`.
6. Read scopes from the `scope` claim. A space-separated string is the primary form. An array of strings is also accepted. `realm_access` and other vendor role claims are ignored. The device routes require `devices:write` or `devices:read`. A valid token without that scope is `403`.
7. Read the account id from the claim named by `OAUTH_ACCOUNT_CLAIM`. The conventional name is `account_id`. The value must be a UUID. A missing or non-UUID value is `403`, not access to every account. The request body cannot supply `account_id`.

Idempotency keys and external references are stored under that account. Reusing a key from another account does not return the first account's registration or enrollment token.

## Issuer setup that remains an operator task

This repository does not start Keycloak. An operator who wants a local issuer:

- Runs Keycloak where it is reachable from this controller, and does not publish it as part of this task.
- Creates a realm and two confidential service-account clients.
- Assigns `devices:write` only to the provisioning client.
- Adds an audience mapper whose value is `OAUTH_AUDIENCE`.
- Adds a mapper that sets `account_id` to that customer's UUID.
- Keeps the client secret in a secret store or a shell variable, not in this repository.

## Still open

- The production access-token lifetime. ADR-001's 15 minutes remains a provisional example.
- Introspection or another revocation check. Local JWT validation cannot see a revoked token while the signature and `exp` are still valid.
- Clock-skew leeway. This implementation uses zero.
- The Keycloak realm name, hostname, database, and high-availability layout.
- Whether a cloud-only operator uses a managed issuer instead of Keycloak. That choice does not change the controller when the claims above are present.
- Agent mTLS, which stays outside this issuer.

## Confirmation

No identity provider is deployed by this change. No client secret, signing key, or live access token is stored in the repository. Test tokens are generated in the test process from an ephemeral local key.
