# ADR-095: Bootstrap Trust Provisioning Workflow Ownership Contract

- Status: Accepted
- Date: 2026-08-11
- Owners: Product Architecture, Platform Engineering
- Governing documents: ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013,
  ATLAS-016, ATLAS-023, ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-037, ATLAS-047,
  ATLAS-050, ATLAS-052, ATLAS-055, ATLAS-056, ADR-079, ADR-080, ADR-081, ADR-082, ADR-083,
  ADR-084, ADR-085, ADR-086, ADR-087, ADR-088, ADR-089, ADR-090, ADR-091, ADR-092, ADR-093,
  ADR-094

## Context

IMP-138 assigned Configuration Rendering to a dedicated lazy Health workflow and reduced the
transitional operational chunk to 794.20 KB. The next state-changing Bootstrap phase is Trust
Provisioning. Its eligibility, human review, mutation, cache recovery and result presentation still
belong to `App.tsx`.

Trust Provisioning publishes approved public trust anchors and opaque workload identity reference
metadata. It must never handle private keys, credential values or resolved secrets, and it must not
create authority over data, services, infrastructure or later phases.

## Decision

Atlas will assign the complete Trust Provisioning interaction lifecycle to one static lazy Health
feature named `BootstrapTrustProvisioningWorkspace`.

The parent application supplies only current authorized evidence:

- Bootstrap state and current run;
- the validated deployment configuration preview;
- the validated public trust plan;
- authenticated organization, environment and site scope.

The feature owns exact-input workflow fingerprinting, fail-closed eligibility, review,
justification, cancel and confirmation state, the version-bound provisioning mutation, stale-review
rejection, success/failure cache recovery and bounded replay/result presentation.

The parent retains query ownership. The feature does not own navigation, authentication,
authorization, lease acquisition, Configuration Rendering, later phases, server validation,
idempotency construction or audit policy.

## Exact Review Binding

One review intent is valid only for the exact fingerprint containing:

- run identity, version, state, current phase, release, profile, plan digest, resume key,
  configuration digest, scope, lease expiry and completed phases;
- completed Configuration Rendering execution identity, state, result code and digest;
- existing Trust Provisioning execution identity, state, result code and trust-plan digest;
- configuration preview identity, schema, state, release, profile, scope and digest;
- trust-plan schema, state, result, release, profile, scope, configuration digest and plan digest;
- ordered public anchor identifiers, source identifiers, purposes and SHA-256 digests; and
- ordered workload identity, service, instance, owner, audience and secret-reference identifiers.

Any change invalidates the review. Confirmation compares the recorded fingerprint with current
evidence immediately before calling the existing API client.

## Availability

The workflow is available only when all conditions are true:

- a non-completed run exists and the current actor holds its lease;
- `phase.trust` is current and no trust provisioning is running;
- `phase.configure` is completed and Configuration Rendering completed successfully;
- the deployment configuration preview passed validation;
- the trust plan passed validation and contains bounded public anchors and workload identities;
- run, preview, trust plan and authenticated organization scope agree; and
- release, profile, configuration digest and trust-plan binding agree exactly.

Absent, stale, failed, malformed, mismatched, unleased or non-trust evidence exposes no action.
Existing completed or failed execution evidence may remain visible without exposing later authority.

## Mutation And Recovery

Confirmation calls the existing `provisionBootstrapTrust` client unchanged. The request remains
version-bound and idempotent and continues to send only the validated trust-plan digest and an empty
overlay.

Success stores only the bounded returned result and refreshes Bootstrap state and invalidation
evidence. Failure clears stale review intent, refreshes both authoritative sources and requires a
new review. No automatic mutation retry is permitted.

## Presentation

The feature may present execution state, result code, public anchor count, workload identity count,
file count, verified byte count and bounded file identifiers, dispositions and digest prefixes.

Private keys, certificate private material, credential values, resolved secret values, raw tokens,
data payloads and infrastructure commands are forbidden. The feature must state that later phases
and operational authority remain unchanged.

## Consequences

- Trust Provisioning can evolve and fail independently of the application coordinator.
- Exact review ownership and secret-exclusion behavior become directly testable.
- The Deployments view loads the workflow only when it owns the current task surface.
- The transitional operational chunk shrinks while server contracts remain unchanged.

## Verification

- Component tests cover exact request binding, replay/result evidence, cancel, stale review,
  unavailable gates, failure refresh, secret exclusion and absence of later authority.
- Existing application integration coverage preserves configure-before-trust and trust-before-data
  sequencing.
- ESLint, both TypeScript project references, full frontend tests and production build pass with a
  separate lazy feature chunk.
- Live desktop/mobile checks cover review/cancel, disabled confirmation, responsive fit, route
  isolation and clean application behavior without executing provisioning.

## Follow-Up

Measure the resulting parent and lazy chunks, then define the Data Initialization workflow owner
while preserving exact-input, audit, idempotency, recovery and no-autonomous-execution rules.
