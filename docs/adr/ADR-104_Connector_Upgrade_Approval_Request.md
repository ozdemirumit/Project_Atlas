# ADR-104: Connector Upgrade Approval Request

## Status

Accepted - 2026-08-12

## Context

ADR-102 and ADR-103 provide exact upgrade readiness and a non-executable connector upgrade plan.
An operator can inspect this evidence, but cannot submit the exact proposal into a durable human
approval boundary. The general approval service is currently bound to storage recommendations and
must not be overloaded with a connector-specific payload that it cannot validate.

ATLAS-020 requires exact connector digests to enter environment approval before upgrade. ATLAS-037
requires immutable packet binding, explicit human intent, separation of duties, expiry, audit and a
strict distinction between requesting approval, recording a decision and authorizing execution.

## Decision

Atlas will add a connector-specific upgrade approval request contract and service.

- A request may be created only for an exact `ready_for_human_review` and `plan_eligible` connector
  upgrade plan.
- The request binds the source instance/version, current and candidate receipts/digests, readiness
  digest, plan ID/digest, risk and one current signed approval policy.
- The server selects exactly one active policy for the caller's organization and environment. Zero
  or multiple active policies fail closed.
- The caller supplies a bounded purpose, explicit acknowledgement and idempotency key. The request
  is immutable, pending and expiring.
- A second materially different request for the same plan is rejected. An exact idempotent replay is
  returned as reused evidence.
- Request creation is separately authorized as C3 administration, requires an enterprise human with
  MFA, is no-store and is audit recorded.
- PostgreSQL persistence uses a dedicated table with unique plan and actor-idempotency constraints.
- API projections omit request fingerprints, idempotency keys, credentials, endpoints and custody
  metadata.

## Authority Boundary

Creating a request is not an approval decision. It cannot install or rebind a package, change
configuration, contact a target, interrupt a service, approve the request, mint an execution token,
authorize execution or mutate infrastructure.

The request records `requested_by` and requires separation of duties so a future decision workflow
can prevent self-approval. Approval decisions and operational execution are explicitly outside
ATLAS-IMP-148.

## User Experience

The exact plan panel exposes a review-purpose field, explicit no-authority acknowledgement and
`Request human approval` only when the plan is eligible. Success displays pending state, exact plan
digest, expiry and the separation-of-duties rule. Blocked plans expose no request control.

## Verification

- Domain invariants reject malformed, pre-approved or execution-authorized records.
- Service tests cover exact binding, policy selection, idempotency, plan drift and configured-target
  rejection.
- Repository conversion and migration topology are tested by existing persistence and migration
  gates.
- API tests verify authorization, no-store responses and minimized projections.
- Frontend tests verify explicit acknowledgement, pending evidence and absence of execution controls.
- Full backend/frontend regression, production build and live desktop/mobile validation are required
  before delivery.
