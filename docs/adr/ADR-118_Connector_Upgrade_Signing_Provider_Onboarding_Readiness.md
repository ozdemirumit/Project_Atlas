# ADR-118: Connector Upgrade Signing-Provider Onboarding Readiness

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-12 |
| Owners | MCP Platform Architecture, Security Architecture, Deployment Architecture |
| Related | ATLAS-003, ATLAS-013, ATLAS-020, ATLAS-025, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-047, ATLAS-057, ADR-115, ADR-116, ADR-117 |

## Context

ADR-116 exposes immutable provider and key trust metadata. ADR-117 demonstrates the configured
adapter's bounded sign-and-verify contract. Neither proves that a provider has the deployment,
security, recovery and organizational approvals required for production onboarding.

Atlas does not have an approved production KMS/HSM product or deployment configuration in this
workspace. Selecting a vendor, endpoint, workload credential, key or lifecycle policy without the
deployment and security owners would create false production assurance.

## Decision

Atlas will derive a versioned, exact-scope signing-provider onboarding-readiness dossier. The dossier
binds the current signing-key trust inventory and latest conformance assessment to a fixed readiness
policy. It evaluates provider availability and approval, an eligible production key and algorithm,
current adapter conformance, workload identity, secret-reference ownership, network boundary, key
lifecycle and revocation, audit routing, availability and recovery, and named security and deployment
approval evidence.

Deployment evidence is supplied only through an injected authoritative source. The API accepts no
provider class, endpoint, credential, secret reference, key reference, signature, algorithm,
requirement result or approval assertion from the caller. An absent source produces explicit blocked
requirements. Scope mismatch, stale conformance, digest mismatch or policy-ineligible evidence fails
closed.

The dossier is computed on read and represented by an immutable domain value. It has a canonical
digest and stable requirement states and reason codes. It is not a provider registration, approval
record, credential, key-management request or execution token.

## Authorization And Audit

Read access requires a dedicated default-deny C1 permission and an authenticated browser session in
production. The development identity exception exists only when development mode is explicitly
enabled. Responses are exact organization/environment scope, `no-store`, non-disclosing and audited.

## Safety Boundary

`provider_onboarding_ready=true` means only that the currently configured authoritative evidence
satisfies this readiness policy. It does not configure or contact a provider, create or rotate a key,
sign a receipt, approve an upgrade, install a package, grant runtime trust, authorize execution or
mutate infrastructure.

The in-workspace non-production HMAC adapter is never production eligible. Production remains
fail-closed until deployment owners configure a separately reviewed provider adapter and evidence
source.

## Consequences

- Operators can see every unmet production prerequisite without exposing deployment secrets.
- Provider conformance and production onboarding approval remain distinct facts.
- A vendor can be selected later without changing the provider-neutral API contract.
- Atlas cannot claim production readiness from self-asserted browser input.

## Validation

- Ready, blocked, missing, stale, non-production and scope-mismatch service tests
- Exact schema, digest, default-deny RBAC, browser-session, audit and `no-store` tests
- Frontend contract and requirement-presentation tests
- Complete backend/frontend regressions, one Alembic head, production build and live responsive UI
