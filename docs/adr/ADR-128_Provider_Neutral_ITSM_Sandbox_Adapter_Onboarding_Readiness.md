# ADR-128: Provider-Neutral ITSM Sandbox Adapter Onboarding Readiness

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-13 |
| Owners | Enterprise Integration Architecture, Security Architecture, Deployment Architecture |
| Related | ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-013, ATLAS-016, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-036, ATLAS-047, ATLAS-050, ATLAS-052, ATLAS-055, ATLAS-056, ATLAS-057, ADR-124, ADR-125, ADR-126, ADR-127 |

## Context

ADR-126 establishes immutable provider-neutral ITSM profiles and ADR-127 demonstrates a bounded,
inert adapter diagnostic for one exact profile. Neither proves that the adapter deployment has the
ownership, identity, trust, resilience, audit and organizational evidence required for sandbox
onboarding.

No production ITSM vendor, endpoint, credential, sandbox or deployment approval is selected in this
workspace. Accepting readiness facts from a browser or treating the local no-network diagnostic as
deployment approval would create false assurance and blur the boundary between conformance evidence
and operational authority.

## Decision

Atlas will derive an immutable, exact-scope ITSM sandbox-adapter onboarding-readiness dossier. The
dossier binds the current active profile and mapping, latest unexpired conformance assessment,
adapter identity, fixed readiness-policy version and injected authoritative deployment evidence.
It records stable requirement results, an evidence interval and a canonical digest.

Requirements cover current profile integrity, current conformant diagnostic, approved adapter
registration, sandbox onboarding approval, workload identity, credential-reference ownership,
network and trust approval, mapping change control, rate limiting and backpressure, audit routing,
availability and recovery, and named security and deployment approvals.

Deployment evidence is supplied only through an application-injected authoritative source. The API
accepts only the profile identifier in its path. It accepts no provider class, endpoint, credential,
secret reference, token, payload, operation, requirement result or approval assertion. Missing,
expired, mismatched, nonconformant, policy-ineligible or non-production-eligible evidence fails
closed with stable reason codes.

Production uses an empty evidence source until deployment owners configure a separately reviewed
source. Local development may expose deterministic, explicitly non-production evidence so the
contract and blocked presentation can be tested without network access. Synthetic evidence cannot
establish readiness.

## Authorization And Audit

Read access requires a dedicated default-deny C1 permission and an authenticated browser session in
production. The result is exact organization, environment, site and profile scope, returns
`Cache-Control: no-store`, uses non-disclosing errors and creates an attributable audit event.

The dossier is computed on read. It is not a provider registration, adapter configuration,
credential request, approval record, dispatch request or execution token and requires no persistence
migration.

## Safety Boundary

`sandbox_onboarding_ready=true` means only that current authoritative evidence satisfies this
readiness policy for the exact profile and adapter. It does not contact a provider, test a custom
endpoint, create or update an ITSM record, enqueue outbound work, approve an Atlas or ITSM workflow,
authorize infrastructure execution or mutate infrastructure.

A later vendor adapter, evidence-source deployment, evidence authenticity mechanism, dispatch
workflow and production activation require independent architecture decisions and validation
slices.

## Consequences

- Operators can distinguish adapter conformance from deployment onboarding readiness.
- Every missing prerequisite is visible without exposing endpoints, credentials or secret material.
- Vendor selection can occur later without changing the provider-neutral dossier contract.
- Production remains fail-closed and cannot derive approval from local synthetic evidence.

## Validation

- Ready, missing, stale, nonconformant, non-production, scope-mismatch and integrity service tests
- Exact schema, digest, default-deny RBAC, browser-session, audit and `no-store` API tests
- Frontend runtime-contract and requirement-presentation tests with no configuration or action controls
- Complete backend/frontend regressions, one Alembic head, production build and responsive live UI
