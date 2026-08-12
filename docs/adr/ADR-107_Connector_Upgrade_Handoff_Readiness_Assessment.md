# ADR-107: Connector Upgrade Handoff Readiness Assessment

## Status

Accepted - 2026-08-12

## Context

ADR-106 proves that one exact connector-upgrade approval was independently revalidated. That
receipt deliberately leaves handoff blocked. ATLAS-037 requires additional current target, impact,
ITSM, maintenance-window, runtime and audit evidence before a consequential handoff. Treating
missing evidence as implicitly satisfied would convert approval into execution authority.

## Decision

Atlas will expose a read-only connector-upgrade handoff-readiness assessment.

- The service requires an enterprise human with MFA and scoped read permission.
- It verifies the exact request, approved decision, latest revalidation, active policy and freshly
  regenerated plan before evaluating readiness.
- Current approval, revalidation, identity separation, policy, plan lineage and absence of prior
  execution are reported as satisfied checks.
- Evidence not represented by an authoritative current source is reported as an explicit blocker.
  The initial blockers are target binding, service impact, ITSM change, maintenance window, runtime
  health and audit readiness.
- The assessment is computed on read and is not an approval state transition. It does not persist a
  token, consume approval, issue an artifact or change infrastructure.
- The endpoint is no-store and audit recorded. Its safe projection excludes tokens, credentials,
  target endpoints and custody metadata.

## Authority Boundary

IMP-151 supports only `assessment_state=blocked`. `handoff_ready`, artifact issuance, approval
consumption, target contact, package rebinding, configuration change, execution authorization and
infrastructure mutation remain false.

A later slice may replace individual blockers only after authoritative evidence contracts exist.
Handoff-artifact issuance requires a separate accepted ADR and cannot be inferred from readiness.

## User Experience

The exact upgrade approval panel displays “Handoff blocked,” states that no artifact was issued and
lists each missing evidence identifier. It offers no continue, issue, install, apply, execute or
handoff control.

## Verification

- Service tests cover exact lineage, freshness, explicit blockers and all no-authority invariants.
- API tests cover no-store behavior, safe projection and blocked state.
- Frontend tests cover blocker presentation and absence of consequential controls.
- Full backend/frontend regression, production build and live desktop/mobile validation are
  required before delivery.
