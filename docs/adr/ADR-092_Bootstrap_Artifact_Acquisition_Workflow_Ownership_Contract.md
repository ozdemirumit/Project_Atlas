# ADR-092: Bootstrap Artifact Acquisition Workflow Ownership Contract

- Status: Accepted
- Date: 2026-08-11
- Owners: Product Owner, Solution Architecture, User Experience, Security Architecture,
  Infrastructure Operations
- Governing documents: ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013,
  ATLAS-016, ATLAS-020, ATLAS-023, ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-038,
  ATLAS-047, ATLAS-050, ATLAS-052, ATLAS-055, ATLAS-056, ATLAS-057, ADR-079 through ADR-091

## Context

IMP-135 moved Bootstrap lease eligibility, exact-input review intent, audited justification,
confirmation, mutation, result and cache recovery into one independently tested lazy feature. The
remaining Bootstrap phase workflows are still owned by the transitional Health application
component.

Artifact Acquisition is the first state-changing deployment phase. It stages and verifies one
immutable release set in the governed Atlas artifact store. It has explicit phase, lease,
preflight, warning acknowledgement, run-version, idempotency and recovery responsibilities. It
does not authorize configuration rendering, service deployment, infrastructure mutation or AI
operation.

The complete interaction must have one owner so a reviewed intent cannot survive a changed run,
plan, preflight report, manifest, mode, profile, scope, lease or execution state.

## Decision

Atlas will introduce a lazy `BootstrapArtifactAcquisitionWorkspace` that owns the complete bounded
Artifact Acquisition review and mutation lifecycle.

### Ownership Boundary

The feature owns:

- server-evidence eligibility presentation;
- exact-input workflow fingerprint and review invalidation;
- justification and conditional preflight-warning acknowledgement;
- confirmation, mutation pending/error/result state and cancel behavior;
- version-bound acquisition submission; and
- authoritative Bootstrap state and invalidation-cache recovery after success or failure.

The parent Health workspace retains identity, release preflight, deployment configuration,
Bootstrap plan and Bootstrap state queries. It also retains every later Bootstrap phase, rebase,
rollback, review, handoff and deployment workflow.

### Exact Reviewed Intent

The review fingerprint binds at least:

- run ID, version, state, current phase, plan digest and resume key;
- release ID, profile and current artifact-execution state;
- lease ownership by the current actor;
- Bootstrap plan state, release, profile, plan digest and resume key;
- preflight report ID, release, manifest digest, mode, profile and state; and
- organization, environment and site scope.

Any fingerprint change remounts the review state. Prior justification and warning acknowledgement
cannot be reused. Confirmation compares the submitted fingerprint with the current fingerprint and
fails closed on mismatch.

### Eligibility

The workflow is available only when:

- a non-completed Bootstrap run exists and the current actor holds its lease;
- the current phase is `phase.acquire` and no acquisition is running;
- the Bootstrap plan is ready and its release, profile, digest and resume key match the run;
- preflight release and profile match the run; and
- preflight state is `passed` or `warning`.

A warning requires an explicit acknowledgement inside the current review. Failed, unchecked,
missing, malformed, drifted or mismatched evidence exposes no action.

### Mutation And Recovery

The existing typed Artifact Acquisition API remains authoritative. The request binds the current
run version, plan digest, resume key, exact release/preflight evidence, scope, reviewed warning
state and justification. Idempotency remains `bootstrap-acquire.<run-version>.<nonce>`.

The feature performs no automatic retry. Success and failure both invalidate authorized Bootstrap
state and invalidation evidence. Failure clears review intent and requires a fresh review against
refreshed evidence. Exact server replay is presented as replay evidence and does not create new
authority.

### Presentation And Authority

The result may present bounded execution state, result code, mode, artifact count, verified bytes,
completion time and artifact ID/hash/disposition evidence supplied by the validated server schema.
It must preserve the server's false configuration, service, infrastructure and AI authority flags.

This decision grants no configuration, trust, data, service, identity, integration, verification,
handoff, rollback, connector or infrastructure authority. UI visibility is not authorization.

## Consequences

### Positive

- Artifact review intent cannot survive run, lease, plan, preflight or scope drift.
- Mutation, evidence refresh and result presentation have one testable owner.
- The transitional application component loses the first phase's local state and mutation logic.
- Later phase workflows can follow the same bounded ownership pattern.

### Costs

- Parent query composition remains transitional until later Health ownership slices.
- Existing shared Bootstrap styles remain in the global stylesheet until the planned Health UI
  consolidation.
- Each later phase still requires its own authority-specific contract and extraction.

## Rejected Alternatives

### Keep Mutation In The Parent

Rejected because split ownership permits review state, mutation state and cache recovery to drift.

### Reuse Review Intent After Evidence Refresh

Rejected because a justification and warning acknowledgement are meaningful only for the exact
reviewed revision and preflight evidence.

### Automatically Retry Conflict Or Transport Failure

Rejected because the server may have accepted or superseded the request. A new authoritative read
and explicit review are required.

### Generalize All Bootstrap Phases In One Component

Rejected because phase authority, evidence, acknowledgement and recovery contracts differ. A
generic executor would hide security distinctions and enlarge regression scope.

## Validation

- Focused component tests cover exact passed and warning submissions, stale-intent invalidation,
  conflict recovery, unavailable gates, cancel, replay/result evidence and no-authority behavior.
- Existing application integration coverage preserves lease-before-acquisition and downstream
  phase behavior.
- ESLint, TypeScript, full frontend tests and production build pass with a separate lazy chunk.
- Live desktop/mobile checks cover review/cancel, responsive fit, route isolation and clean direct
  application logs without executing an acquisition.

## Follow-Up

Create a dedicated Health UI consolidation slice after this extraction, then continue bounded
ownership extraction for Configuration Rendering and subsequent Bootstrap phases.
