# ADR-126: Provider-Neutral ITSM Adapter Readiness

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-13 |
| Owners | Product Architecture, Security Architecture, Operations Architecture |
| Related | ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-016, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-036, ATLAS-047, ATLAS-050, ATLAS-052, ATLAS-053, ATLAS-055, ATLAS-056, ADR-124, ADR-125 |

## Context

Atlas can persist a technical report and the exact human review of its review-only ITSM handoff,
but it has no governed contract for an ITSM provider instance. Provider selection, endpoint trust,
credential brokerage, normalized field mappings, sandbox evidence and accountable ownership are
deployment inputs that must be explicit before outbound behavior can be designed. A human review of
a handoff cannot supply or imply those prerequisites.

No production provider, endpoint or sandbox has been selected. Implementing dispatch now would mix
configuration readiness with external mutation authority and would violate Atlas's decision-support
boundary.

## Decision

Atlas will persist immutable, provider-neutral ITSM integration profiles. A profile is tenant and
environment scoped and binds a provider family, opaque instance reference, accountable owner,
purpose, HTTPS origin, trust-boundary reference, credential-broker reference, classification ceiling,
allowed operation vocabulary, audit profile and lifecycle. Secret material is never stored by this
module or returned through its API; public responses expose only that a credential reference is
configured.

Each profile carries a versioned allowlisted field contract. Atlas source fields are fixed by the
platform. Work notes use append-only semantics; report and review fields are reference-only.
Arbitrary fields, credential fields and mutable replacement semantics are rejected. Mapping updates
will require a new profile version in a future slice rather than in-place mutation.

Atlas computes exactly six deterministic readiness checks: accountable ownership, network and trust,
credential reference, field mapping, sandbox validation and audit binding. All checks satisfied means
only `ready_for_sandbox`; missing prerequisites produce exact blockers. Readiness is canonicalized and
digest-bound to the profile.

Profile registration and retirement use dedicated default-deny permissions, a CSRF-protected human
browser session, idempotency, exact tenant/environment/site scope, attributable audit and optimistic
concurrency. Retirement preserves the complete record. PostgreSQL persistence follows the platform's
async repository and migration lifecycle; development without a database remains process-memory-only.

The Health governance UI presents profile inventory, provider family, lifecycle, mapping version,
credential-reference presence and readiness blockers. It can register or retire configuration
profiles but cannot test an endpoint, retrieve a credential, dispatch a payload, create or update a
ticket, approve a workflow or execute an infrastructure operation.

## Safety Boundary

An active profile, complete mapping, sandbox evidence, `ready_for_sandbox` assessment or accepted
human handoff review does not authorize outbound dispatch. The readiness artifact always keeps
dispatch, external record mutation, workflow approval and execution authority false. No endpoint is
contacted by this slice. Any sandbox transport, provider adapter, ticket mutation or production
enablement requires a separate ADR, policy boundary and validation slice.

## Consequences

- Operators can inventory provider-neutral ITSM configuration and see exact missing prerequisites.
- Credential material remains outside Atlas profile persistence and presentation.
- Mapping behavior is reviewable, versioned and constrained before a provider adapter exists.
- Readiness cannot be confused with workflow approval or external mutation authority.
- Profile history survives retirement and can be audited without retaining secret material.
- Future adapter work has a stable configuration contract but must independently establish transport,
  sandbox conformance, approval and dispatch controls.

## Validation

- Domain tests for mapping allowlists, deterministic readiness, idempotency, retirement and authority
  booleans
- PostgreSQL payload round-trip, optimistic concurrency and one-head migration checks
- API authorization, browser-session, CSRF, no-store and secret-minimization tests
- Frontend readiness, mapping, lifecycle and no-dispatch control tests
- Complete backend/frontend gates, production build and responsive live validation
