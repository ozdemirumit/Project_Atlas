# ADR-097: Bootstrap Service Deployment Workflow Ownership Contract

- Status: Accepted
- Date: 2026-08-11
- Owners: Product Architecture, Platform Engineering
- Governing documents: ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013,
  ATLAS-016, ATLAS-023, ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-037, ATLAS-047,
  ATLAS-050, ATLAS-052, ATLAS-055, ATLAS-056, ADR-079, ADR-080, ADR-081, ADR-082, ADR-083,
  ADR-084, ADR-085, ADR-086, ADR-087, ADR-088, ADR-089, ADR-090, ADR-091, ADR-092, ADR-093,
  ADR-094, ADR-095, ADR-096

## Context

IMP-140 assigned Data Initialization to a dedicated lazy Health workflow and reduced the
transitional operational chunk to 778.21 KB. Service Deployment is the next state-changing
Bootstrap phase. Its eligibility, human review, mutation, recovery and result presentation remain
in `App.tsx`.

This phase publishes a bounded synthetic Atlas service-state document. It does not start a real
process or container, install an operating-system service, bind a port, change a network, resolve or
mutate a secret, mutate external data, change infrastructure or invoke AI operations.

## Decision

Atlas will assign the complete Service Deployment interaction lifecycle to one static lazy Health
feature named `BootstrapServiceDeploymentWorkspace`.

The parent supplies current Bootstrap state, configuration preview, public trust plan, data plan,
service plan and authenticated organization scope. The feature owns exact-input fingerprinting,
fail-closed eligibility, review, justification, cancel and confirmation state, version-bound
mutation, stale-review rejection, cache recovery and bounded replay/result presentation.

The parent retains query, navigation, authentication and authorization ownership. The feature does
not own lease acquisition, plan generation, real runtime operations, Identity Handoff, later phases,
server validation, idempotency construction or audit policy.

## Exact Review Binding

One review intent is valid only for the exact fingerprint containing:

- run identity, version, state, current phase, release, profile, plan digest, resume key,
  configuration digest, scope, lease expiry and completed phases;
- completed Data Initialization and prior Service Deployment identities, states, result codes and
  bound plan digests;
- configuration, trust and data-plan identities, schemas, states, scopes and digests;
- service-plan schema, state, result, release, profile, scope, configuration, trust, data,
  migration-artifact and service-plan digests;
- target identity, kind and expected state; and
- every ordered service identity, sequence, artifact identity/digest, prior dependencies, workload
  identity reference, private endpoint class, resource limits, three probe identities and false
  root, privileged and arbitrary-public-egress flags.

Any change invalidates review. Confirmation compares the recorded fingerprint with current
evidence immediately before calling the existing API client.

## Availability

The workflow is available only when:

- a non-completed run exists, the current actor holds its lease and `phase.services` is current;
- no service deployment is running and Data Initialization completed successfully;
- configuration, trust, data and service plans passed and agree with run and authenticated scope;
- Data Initialization binds the exact trust, data and migration-artifact digests;
- the service plan contains unique, strictly ordered services whose dependencies refer only to
  earlier services; and
- every service is private, non-root, non-privileged and has no arbitrary public egress.

Absent, stale, failed, malformed, mismatched, cyclic/out-of-order, unleased or non-services evidence
exposes no action. Existing execution evidence may remain visible without later-phase authority.

## Mutation And Recovery

Confirmation calls the existing `deployBootstrapServices` client unchanged. The request remains
version-bound and idempotent and sends only validated configuration, trust, data, migration,
service-plan and target bindings plus an empty overlay and reviewed justification.

Success stores bounded returned evidence and refreshes Bootstrap state, invalidation evidence and
the service plan. Failure clears review intent, refreshes all three sources and requires a new
review. No automatic mutation retry is permitted.

## Presentation

The feature may present service count, dependency order, resource limits, probe identities,
execution state, result code, deployed/ready/probe counts, bounded status booleans and sanitized
evidence identifiers, dispositions and digest prefixes.

Runtime commands, process/container controls, OS-service operations, endpoints, ports, network
changes, credentials, secret values, external data, infrastructure controls and AI authority are
forbidden.

## Consequences

- Service Deployment can evolve and fail independently of the application coordinator.
- Dependency ordering, exact review and no-real-runtime behavior become directly testable.
- The Deployments view loads the workflow only when it owns the current task surface.
- The transitional operational chunk shrinks while server contracts remain unchanged.

## Verification

- Component tests cover exact request, replay/result evidence, cancel, stale review, dependency and
  scope gates, failure refresh, sensitive/runtime exclusion and absence of later authority.
- Existing integration coverage preserves data-before-services and services-before-identity order.
- ESLint, both TypeScript projects, full frontend tests and production build pass with a separate
  lazy feature chunk.
- Live desktop/mobile checks cover review/cancel, disabled confirmation, responsive fit and clean
  behavior without executing deployment.

## Follow-Up

Measure the resulting chunks, then define the Identity Handoff workflow owner while preserving
exact-input, audit, idempotency, recovery and no-autonomous-execution rules.
