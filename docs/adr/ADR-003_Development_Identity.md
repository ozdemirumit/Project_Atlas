# ADR-003: Development Identity Boundary

| Field | Value |
| --- | --- |
| Status | Accepted |
| Decision Date | 2026-08-03 |
| Decision Owner | Umit Ozdemir, acting Security Architecture Owner |
| Related Documents | ATLAS-003, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-050, ATLAS-051 |
| Supersedes | None |

## Context

Atlas needs authenticated and authorized API behavior before an enterprise LDAP, Active
Directory, or federation adapter is selected and available. Treating a browser header as identity
or adding a development bypass would weaken the production boundary and make later tests
misleading.

## Decision

The first implementation uses a server-configured development identity provider behind the same
identity-provider port that future enterprise adapters will implement.

- The provider is disabled by default.
- It can operate only in `development` and `test` environments.
- Enabling it in `production` is a configuration error that prevents startup.
- Subject, provider, organization, roles, and exact scope are supplied by trusted server
  configuration, never by request headers.
- Presented bearer credentials are rejected until a validating provider exists.
- Authentication creates a normalized subject but grants no permission by itself.
- A separate authorization service evaluates registered permission, role version, assignment,
  exact resource scope, validity interval, and correlation context.
- Protected-operation denials and authorization allows cross the audit port.

The default development role grants only `identity.self.read` within the explicitly configured
local C0 scope. It is not a bootstrap administrator and has no connector, workflow, policy,
approval, or infrastructure-changing permission.

## Consequences

- Developers can exercise genuine `401`, `403`, and allowed paths without a directory service.
- No client-controlled identity shortcut becomes part of the API contract.
- Local startup scripts must explicitly opt into development identity.
- Enterprise LDAP or OIDC work remains a separate task and must replace the adapter, not the
  authorization model.
- Exact-scope matching is intentionally conservative; hierarchical scope inheritance requires a
  later reviewed extension.

## Rejected Alternatives

- Trusting `X-User`, role, or scope headers: rejected because clients could elevate themselves.
- Enabling a fixed identity automatically for every non-production process: rejected because
  secure tests require an unauthenticated default.
- Implementing LDAP before authorization contracts: rejected because provider access would not
  establish deterministic least-privilege enforcement.
