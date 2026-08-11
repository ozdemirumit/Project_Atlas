# ADR-094: Bootstrap Configuration Rendering Workflow Ownership Contract

- Status: Accepted
- Date: 2026-08-11
- Owners: Product Architecture, Platform Engineering
- Governing documents: ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013,
  ATLAS-016, ATLAS-023, ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-037, ATLAS-047,
  ATLAS-050, ATLAS-052, ATLAS-055, ATLAS-056, ADR-079, ADR-080, ADR-081, ADR-082, ADR-083,
  ADR-084, ADR-085, ADR-086, ADR-087, ADR-088, ADR-089, ADR-090, ADR-091, ADR-092, ADR-093

## Context

IMP-137 separated Health into Overview, Investigate, Deployments and Governance task views. The
Deployments view still delegates the Configuration Rendering phase's eligibility, human review,
mutation, cache recovery and result presentation to the transitional `App.tsx` module.

Configuration Rendering is the second state-changing Bootstrap phase. It atomically publishes
canonical, non-secret configuration after immutable artifact acquisition. The workflow must bind a
human review to the exact run, lease, phase, configuration preview and organization scope without
creating authority over trust, secrets, data, services, infrastructure or later phases.

## Decision

Atlas will assign the complete Configuration Rendering interaction lifecycle to one static lazy
Health feature named `BootstrapConfigurationRenderingWorkspace`.

The parent application supplies only current authorized evidence:

- the Bootstrap state and current run;
- the deployment configuration preview;
- the authenticated organization, environment and site scope; and
- the shared timestamp formatter.

The feature owns:

- exact-input workflow fingerprinting;
- eligibility and fail-closed gates;
- review, justification, cancel and confirmation state;
- the version-bound configuration rendering mutation;
- stale-review rejection before submission;
- success and failure cache recovery; and
- bounded execution, replay and rendered-file evidence presentation.

The feature does not own Bootstrap state or configuration-preview queries, lease acquisition,
artifact acquisition, later phases, navigation, authentication, authorization, audit policy,
idempotency construction or server-side validation.

## Exact Review Binding

One review intent is valid only for the exact fingerprint containing:

- run identity, version, state, phase, release, profile, plan digest, resume key and configuration
  digest;
- organization, environment and site scope;
- lease ownership and expiry;
- completed phase identifiers;
- artifact-acquisition execution identity, state and result code;
- existing configuration-rendering execution identity, state and result code; and
- configuration preview identity, state, schema, release, profile, scope and digest.

Any change invalidates the review. Confirmation compares the recorded fingerprint with current
evidence immediately before calling the existing API client.

## Availability

The workflow is available only when all conditions are true:

- a non-completed run exists and the current actor holds its lease;
- `phase.configure` is current and no configuration rendering is running;
- `phase.acquire` is completed and artifact acquisition is completed;
- the deployment configuration preview passed validation;
- run, preview and authenticated organization scope agree;
- release, profile and configuration digest agree exactly.

Absent, malformed, stale, failed, mismatched, unleased or non-configure evidence exposes no action.
Existing completed or failed execution evidence may remain visible without exposing later authority.

## Mutation And Recovery

Confirmation calls the existing `renderBootstrapConfiguration` client unchanged. The server-bound
request remains version-bound and idempotent and continues to use an empty overlay.

Success stores only the returned bounded result and refreshes Bootstrap state and invalidation
evidence. Failure clears the stale review, refreshes both authoritative sources and requires a new
explicit review before retry. No automatic mutation retry is permitted.

## Presentation

The feature may present state, result code, schema version, file count, verified byte count,
completion time and bounded rendered-file identifiers, dispositions and digest prefixes.

It must state that only governed non-secret configuration storage may change. It must not expose
trust, secret, data, service, infrastructure, AI-operation, rollback or later-phase controls.

## Consequences

- Configuration Rendering can evolve and fail independently of the application coordinator.
- The Deployments view loads the workflow only when it owns the current task surface.
- Exact review ownership and recovery behavior become directly testable.
- The transitional operational chunk shrinks while server contracts remain unchanged.

## Verification

- Component tests cover exact request binding, replay/result evidence, cancel, unavailable gates,
  stale review, failure refresh and absence of later authority.
- Existing application integration coverage preserves configure-before-trust sequencing.
- ESLint, both TypeScript project references, full frontend tests and production build pass with a
  separate lazy feature chunk.
- Live desktop/mobile checks cover review/cancel, responsive fit, route isolation and clean
  application logs without executing Configuration Rendering.

## Follow-Up

Measure the resulting parent and lazy chunks, then define the next bounded Bootstrap phase workflow
owner while preserving exact-input, audit, idempotency, recovery and no-autonomous-execution rules.
