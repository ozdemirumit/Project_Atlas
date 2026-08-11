# ADR-096: Bootstrap Data Initialization Workflow Ownership Contract

- Status: Accepted
- Date: 2026-08-11
- Owners: Product Architecture, Platform Engineering
- Governing documents: ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013,
  ATLAS-016, ATLAS-023, ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-037, ATLAS-047,
  ATLAS-050, ATLAS-052, ATLAS-055, ATLAS-056, ADR-079, ADR-080, ADR-081, ADR-082, ADR-083,
  ADR-084, ADR-085, ADR-086, ADR-087, ADR-088, ADR-089, ADR-090, ADR-091, ADR-092, ADR-093,
  ADR-094, ADR-095

## Context

IMP-139 assigned Trust Provisioning to a dedicated lazy Health workflow and reduced the
transitional operational chunk to 786.67 KB. Data Initialization is the next state-changing
Bootstrap phase. Its eligibility, human review, mutation, recovery and result presentation remain
in `App.tsx`.

Data Initialization applies an ordered, reversible, non-destructive schema plan to the bounded
Atlas clean-install target. It does not provision an external database, reveal database URLs,
credentials or SQL, perform a backup, deploy a service or authorize infrastructure or AI actions.

## Decision

Atlas will assign the complete Data Initialization interaction lifecycle to one static lazy Health
feature named `BootstrapDataInitializationWorkspace`.

The parent application supplies only current authorized evidence:

- Bootstrap state and current run;
- the validated deployment configuration preview;
- the validated public trust plan;
- the validated data plan; and
- authenticated organization, environment and site scope.

The feature owns exact-input workflow fingerprinting, fail-closed eligibility, review,
justification, cancel and confirmation state, the version-bound initialization mutation,
stale-review rejection, success/failure cache recovery and bounded replay/result presentation.

The parent retains query ownership. The feature does not own navigation, authentication,
authorization, lease acquisition, Trust Provisioning, later phases, server validation, idempotency
construction, migration generation or audit policy.

## Exact Review Binding

One review intent is valid only for the exact fingerprint containing:

- run identity, version, state, current phase, release, profile, plan digest, resume key,
  configuration digest, scope, lease expiry and completed phases;
- completed Trust Provisioning execution identity, state, result code and trust-plan digest;
- existing Data Initialization execution identity, state, result code, data-plan digest and
  migration-artifact digest;
- configuration preview identity, schema, state, release, profile, scope and digest;
- trust-plan schema, state, release, profile, scope, configuration digest and trust-plan digest;
- data-plan schema, state, result, release, profile, scope, configuration digest, trust-plan digest,
  migration-artifact digest and data-plan digest;
- target identity, kind, state, current revision, target revision and backup applicability; and
- every ordered migration identity, sequence, digest, revision pair, compatibility, reversibility,
  destructive flag, recovery code and expected object count.

Any change invalidates the review. Confirmation compares the recorded fingerprint with current
evidence immediately before calling the existing API client.

## Availability

The workflow is available only when all conditions are true:

- a non-completed run exists and the current actor holds its lease;
- `phase.data` is current and no data initialization is running;
- `phase.trust` is completed and Trust Provisioning completed successfully;
- configuration, trust and data plans passed validation;
- the data plan contains at least one ordered reversible migration;
- run, plans and authenticated organization scope agree; and
- release, profile, configuration digest, trust-plan digest and target bindings agree exactly.

Absent, stale, failed, malformed, mismatched, unleased or non-data evidence exposes no action.
Existing completed or failed execution evidence may remain visible without exposing later authority.

## Mutation And Recovery

Confirmation calls the existing `initializeBootstrapData` client unchanged. The request remains
version-bound and idempotent and sends only the validated configuration, trust, data-plan,
migration-artifact and target bindings plus an empty overlay and reviewed justification.

Success stores only the bounded returned result and refreshes Bootstrap state, invalidation evidence
and the data plan. Failure clears stale review intent, refreshes all three authoritative sources and
requires a new review. No automatic mutation retry is permitted.

## Presentation

The feature may present execution state, result code, revision transition, migration count,
verified-object count, backup applicability and bounded evidence identifiers, dispositions and
digest prefixes.

Database URLs, credentials, SQL text, destructive operations, backup controls, service deployment,
infrastructure commands and AI authority are forbidden. The feature must state that external
databases, backups, services and infrastructure remain unchanged.

## Consequences

- Data Initialization can evolve and fail independently of the application coordinator.
- Exact migration-plan review and no-later-authority behavior become directly testable.
- The Deployments view loads the workflow only when it owns the current task surface.
- The transitional operational chunk shrinks while server contracts remain unchanged.

## Verification

- Component tests cover exact request binding, replay/result evidence, cancel, stale review,
  unavailable gates, failure refresh, sensitive-data exclusion and absence of later authority.
- Existing application integration coverage preserves trust-before-data and data-before-services
  sequencing.
- ESLint, both TypeScript project references, full frontend tests and production build pass with a
  separate lazy feature chunk.
- Live desktop/mobile checks cover review/cancel, disabled confirmation, responsive fit, route
  isolation and clean application behavior without executing initialization.

## Follow-Up

Measure the resulting parent and lazy chunks, then define the Service Deployment workflow owner
while preserving exact-input, audit, idempotency, recovery and no-autonomous-execution rules.

