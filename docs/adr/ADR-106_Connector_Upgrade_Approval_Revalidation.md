# ADR-106: Connector Upgrade Approval Revalidation

## Status

Accepted - 2026-08-12

## Context

ADR-105 records an immutable human decision for one exact connector upgrade request. An approved
decision alone must not silently become handoff or execution authority. ATLAS-037 requires approval
freshness, exact binding and revalidation before a later consequential boundary can rely on it.
Requesting, approving and revalidating the same proposal with fewer than three independent people
would weaken separation of duties.

## Decision

Atlas will create an immutable connector-upgrade approval revalidation receipt.

- A scoped enterprise human with MFA and explicit revalidation permission may revalidate only a
  current approved decision.
- The revalidator must be distinct from both the requester and approver. Development identities,
  service identities and insufficient assurance fail closed.
- The caller supplies the exact request and decision digests, a bounded purpose, an explicit
  no-handoff/no-execution acknowledgement and an idempotency key.
- The service verifies request and decision integrity, approval outcome, expiry, organization and
  environment scope, the exact active signed policy and a freshly regenerated unchanged plan.
- The receipt binds request, decision, plan, readiness, current/candidate package receipts, policy
  and all three accountable actors. Its validity ends at the earliest request, regenerated plan or
  policy expiry.
- PostgreSQL persistence uses a dedicated append-only table with unique actor-idempotency
  constraints. Exact replay is safe; conflicting replay, stale lineage and drift fail closed.
- Create and latest-read endpoints are no-store and audit recorded. Safe projections omit internal
  fingerprints, idempotency keys, credentials, target endpoints and custody metadata.

## Authority Boundary

The receipt means only that the exact approval was current when independently revalidated. It sets
`governance_ready=true` while preserving `handoff_ready=false`. It does not create a handoff
artifact, install or rebind a package, change configuration, contact a target, interrupt a service,
issue a token, authorize execution or mutate infrastructure.

Any future handoff requires a separate accepted contract that consumes a still-current receipt and
rechecks all relevant policy, impact and operational evidence.

## Deterministic Plan Identity

Generation and expiry timestamps are observations, not source identity. Readiness and plan digests
exclude generation time so an unchanged source remains exactly comparable as the clock advances.
The returned timestamps still communicate freshness and bound each newly generated observation.
Any material source, package, configuration, target or policy change continues to alter or reject
the lineage.

## User Experience

After an approved decision, the upgrade panel exposes revalidation only to a third eligible human.
The requester and approver see a third-verifier requirement. A successful receipt displays the
accountable verifier, checks and validity window while stating that handoff remains blocked. No
install, apply, execute or handoff control is introduced.

## Verification

- Domain and service tests cover three-person separation, exact binding, advancing time,
  idempotency, safe replay and all no-authority invariants.
- Repository and migration tests cover durable mapping and actor-idempotency uniqueness.
- API tests verify permission, CSRF, no-store behavior and safe projection.
- Frontend tests cover eligible third-person revalidation, requester/approver denial, restored
  evidence and absence of handoff/execution controls.
- Full backend/frontend regression, production build and live desktop/mobile validation are
  required before delivery.
