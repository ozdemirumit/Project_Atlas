# ADR-105: Connector Upgrade Approval Decision

## Status

Accepted - 2026-08-12

## Context

ADR-104 creates an immutable pending request for one exact connector upgrade plan, but no distinct
human can retrieve that request after a session transition or record a governed decision. Reusing
the package-approval decision would lose instance, receipt, readiness and plan lineage. Treating a
pending request as approval would violate ATLAS-037.

## Decision

Atlas will add a connector-specific immutable upgrade approval decision and safe record projection.

- A scoped enterprise human with MFA and explicit decision permission may record `approve`,
  `reject`, `needs_evidence` or `defer` for one pending request.
- The requester cannot decide. Service identities, development authentication and insufficient
  assurance fail closed.
- The caller supplies the expected request version and digest, a bounded rationale, an explicit
  no-execution acknowledgement and an idempotency key.
- The service verifies request integrity, expiry, organization/environment scope, the exact active
  signed policy and a freshly regenerated plan with the same record, candidate and plan digest.
- One immutable decision is allowed per request. Exact replay returns reused evidence; conflicting
  idempotency, stale versions, concurrent decisions and plan drift are rejected.
- PostgreSQL persistence uses a dedicated decision table with unique request and actor-idempotency
  constraints. Decisions and protected reads are audit recorded.
- A plan-bound read endpoint returns the current safe approval record so another authorized session
  can resume review without receiving fingerprints, idempotency keys, credentials, endpoints or
  artifact-custody metadata.

## Authority Boundary

An approved decision means that the exact proposal was accepted for review purposes until its
bounded expiry. It does not install or rebind a package, change configuration, contact a target,
interrupt a service, issue a runtime token, authorize execution or mutate infrastructure.

No execution or handoff artifact is created in ATLAS-IMP-149. Any future controlled handoff requires
a separate approved contract and fresh revalidation under ATLAS-037.

## User Experience

The exact upgrade-plan panel restores any existing request. The requester sees an independent-
approver requirement. A different eligible human receives equally accessible approve, reject,
request-evidence and defer choices, a rationale field and explicit no-execution acknowledgement.
The resulting state, accountable decision actor, rationale, decision time and expiry are visible;
no apply, install or execute control is introduced.

## Verification

- Domain and service tests cover separation, exact binding, expiry, drift, policy mismatch,
  optimistic concurrency, idempotency and all outcomes.
- Repository and migration tests cover one-decision and actor-idempotency uniqueness.
- API tests verify permission, CSRF, no-store behavior, safe projection and plan-bound retrieval.
- Frontend tests cover requester denial, independent decision, persisted state and absence of
  execution controls.
- Full backend/frontend regression, production build and live desktop/mobile validation are required
  before delivery.
