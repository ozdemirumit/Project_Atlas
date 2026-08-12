# ADR-108: Connector Upgrade Handoff Evidence Applicability

## Status

Accepted - 2026-08-12

## Context

ADR-107 introduced a fail-closed, read-only upgrade handoff-readiness assessment and initially
reported six evidence categories as missing. The approved upgrade flow currently accepts only a
disabled, unconfigured connector instance with no target binding and a zero-minute service
interruption estimate. Requiring target binding for that exact lineage is contradictory: adding a
target changes the source record and plan digest, invalidating the approval that the assessment is
evaluating.

Atlas must distinguish evidence that is required and missing from evidence that does not apply to
the exact plan. This distinction must remain deterministic, policy-bound and non-authorizing.

## Decision

Atlas will classify connector-upgrade handoff evidence as `required`, `satisfied` or
`not_applicable` under a versioned applicability policy.

- Approval, revalidation, identity separation, policy, plan lineage and absence of prior execution
  remain required and satisfied only after the existing exact-current checks pass.
- Target binding, service-impact evidence and runtime-health evidence are required only when the
  exact approved plan has a configured target. They are not applicable for the current
  disabled/unconfigured, targetless plan.
- ITSM change and maintenance-window evidence are required for every connector package upgrade
  handoff. A low risk label cannot bypass change governance.
- Audit-readiness evidence is always required.
- Missing required evidence remains a blocker. Not-applicable evidence is never treated as
  satisfied and never silently removes a required blocker.
- Policy ID, version and canonical digest are returned and included in the assessment digest.
- The API schema advances to `atlas.connector-upgrade-handoff-readiness.v2`. Runtime validators
  reject duplicate, overlapping or internally inconsistent evidence sets.

The initial applicability policy is
`connector-upgrade-handoff-evidence-applicability.default`, version `v2026.08.12.1`.

## Authority Boundary

This decision does not make handoff ready. For the current targetless plan, ITSM change,
maintenance window and audit-readiness evidence remain missing. `handoff_ready`, artifact
issuance, approval consumption, target contact, package rebinding, configuration change, execution
authorization and infrastructure mutation remain false.

Future evidence-source integrations may satisfy required checks only through a separate accepted
contract. Handoff artifact issuance remains outside this decision.

## User Experience

The upgrade panel presents three separate sections: required evidence missing, satisfied checks and
checks that are not applicable in the current context. It displays the applicability-policy version
and continues to offer no install, apply, execute or handoff control.

## Verification

- Domain and service tests verify disjoint evidence sets, exact policy binding and unchanged
  no-authority invariants.
- API tests verify the v2 safe projection and explicit applicability fields.
- Frontend type, runtime-validation and component tests verify all three classifications.
- Full backend/frontend regression, production build and live desktop/mobile validation are
  required before delivery.

## Relationship to ADR-107

ADR-108 supersedes ADR-107 only for unconditional classification of the initial six evidence
categories. ADR-107's fail-closed lineage verification, read-only behavior and authority boundary
remain accepted.
