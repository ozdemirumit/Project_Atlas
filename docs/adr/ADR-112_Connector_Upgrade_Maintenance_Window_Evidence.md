# ADR-112: Connector Upgrade Maintenance-Window Evidence

## Status

Accepted - 2026-08-12

## Context

ADR-111 validates an authoritative ITSM change record, but an active record does not prove that the
current time is inside an approved maintenance window. ATLAS-036 and ATLAS-037 require current
window, freeze, revocation, exact-plan and source-version checks before any future handoff.

## Decision

Handoff-readiness evaluation will accept a versioned vendor-neutral maintenance-window evidence
snapshot from an explicit source. The snapshot is bound to the exact organization, environment,
approval request, latest revalidation, immutable plan and current authoritative ITSM change evidence.

Evidence must identify the external record version and window version, preserve approved start and
end times, and assert authoritative source, approval, current source version, exact change and plan
binding, current-time inclusion, clear freeze state, no conflict and no revocation. Atlas verifies the
canonical digest, deterministic evidence ID, scope, lineage and bounded validity period.

The default source is empty. Atlas does not infer a window from its earlier internal draft and does
not treat a future, expired or merely scheduled window as current evidence.

## Evidence-Complete State

When every required evidence check is current, the assessment advances from `blocked` to
`evidence_complete` and carries no blockers. This is a review result only. It does not set
`handoff_ready`, issue a handoff artifact, consume approval, contact a target, rebind a package,
change configuration, authorize execution or mutate infrastructure.

The inbound contract does not create, approve, schedule, reschedule or modify an ITSM record or
maintenance window. It exposes no endpoint, token, credential or free-form ticket content. Any
window evidence change alters the readiness digest and invalidates an older change-context draft.

## Verification

- Domain and browser validators permit an empty blocker set only for `evidence_complete` with every
  required check satisfied.
- Service tests cover absent, exact-current and digest-corrupt window evidence.
- The current window must be bound to the exact current ITSM evidence and contain the assessment
  time within both its approved and evidence-valid intervals.
- UI explicitly states that evidence review completed without issuing handoff or execution authority.
- Full regression, production build and responsive live validation are required.
