# ADR-091: Bootstrap Lease Workflow Ownership Contract

- Status: Accepted
- Date: 2026-08-11
- Owners: Product Owner, Solution Architecture, User Experience, Security Architecture,
  Platform Engineering
- Governing documents: ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013,
  ATLAS-025, ATLAS-026, ATLAS-027, ATLAS-028, ATLAS-029, ATLAS-030, ATLAS-031, ATLAS-032,
  ATLAS-038, ATLAS-047, ATLAS-050, ATLAS-052, ATLAS-053, ATLAS-055, ATLAS-056, ATLAS-057,
  ADR-079, ADR-080, ADR-081, ADR-082, ADR-083, ADR-084, ADR-085, ADR-086, ADR-087, ADR-088,
  ADR-089, ADR-090

## Context

IMP-134 extracted read-only Bootstrap Invalidation evidence and reduced the transitional operational
chunk to 819.78 KB. Bootstrap Checkpoint still leaves the coordination-lease workflow in the parent:
eligibility, review intent, justification, confirmation, mutation, result, cache recovery and UI
state are split across a large transitional module.

Lease claim is the first stateful Bootstrap ownership slice. It can initialize an exact run or
reclaim an expired coordination lease, but it cannot execute a deployment phase. Its security
boundary depends on immutable input identity, exact run revision, explicit human intent, bounded
lease duration, audited justification, idempotency and fail-closed concurrency recovery.

## Decision

Atlas will extract the complete coordination-lease workflow into a dedicated lazy Health feature.
The parent supplies only authorized, schema-valid Bootstrap state, plan, deployment configuration
and identity scope. The feature owns the user intent and mutation lifecycle.

### Workflow Ownership

- `BootstrapLeaseWorkspace` owns lease eligibility presentation, reviewed intent, justification,
  confirmation, mutation pending/error/result state and query-cache recovery.
- The reviewed intent binds current run identity/revision, plan digest/resume key, configuration
  digest and organization/environment/site scope into one exact workflow fingerprint.
- Confirmation is disabled when the current fingerprint differs from the reviewed fingerprint.
  Changed evidence requires a new review intent; stale intent is never submitted.
- The existing `claimBootstrapLease` API remains the request authority. Its idempotency key is bound
  to the current run revision and its body carries the exact release, configuration, plan, phase
  order, scope, ten-minute lease duration and audited justification.

### Authorization And Loading Contract

- The feature mounts only on Health while authorized state, ready plan, passed configuration and
  identity scope are all present.
- Lease availability is derived from the same server state and immutable preview gates used by the
  parent. A completed run, unavailable lease, blocked plan or failed configuration offers no action.
- The feature uses a static local lazy import inside the existing fail-closed Bootstrap boundary.
  Load/render failure hides the lease workflow with the rest of the governed Bootstrap section.
- Connector routes must not download, evaluate or mount the feature.

### Audit, Concurrency And Recovery Contract

- Explicit review intent and a minimum twelve-character justification are required before submit.
- Cancel clears the reviewed intent and justification without calling the API.
- A mutation failure clears stale intent, preserves a bounded error state and invalidates Bootstrap
  state plus invalidation-preview caches before another review can begin.
- Success clears intent, records only the schema-validated result and invalidates both caches.
- Result presentation distinguishes a new claim, an expired-lease reclaim and an idempotent replay.
  It displays server run identity/revision and never infers phase readiness.

### Authority Boundary

- Lease claim coordinates one Atlas bootstrap run; it does not execute a phase or write release
  artifacts.
- `execution_authorized` and `infrastructure_mutation_authorized` remain false in every accepted
  result.
- The feature owns no release acquisition, configuration rendering, trust, data, service, identity,
  integration, verification, handoff, rollback, connector or infrastructure operation.

### Verification

- Focused tests cover unavailable gates, explicit review/cancel, exact initial-run submission,
  existing-run version binding, replay/reclaim result classification, stale-intent invalidation,
  mutation recovery and absence of phase authority.
- Existing application tests preserve end-to-end lease initialization before phase execution.
- Full ESLint, both TypeScript project references, full Vitest and production build pass with a
  separate feature chunk.
- Live desktop/mobile checks cover the empty-state lease workflow, route isolation, overflow and
  final application warning/error state.

## Consequences

### Positive

- The first stateful Bootstrap workflow gains one auditable owner instead of scattered parent state.
- Exact-input drift and concurrency failures require a fresh review before retry.
- Parent size and state pressure decrease while server authority remains unchanged.

### Costs

- The feature imports React Query because it owns mutation recovery and cache invalidation.
- Phase workflows remain in the transitional parent and require later ownership slices.

## Rejected Alternatives

### Move Only The Confirmation Markup

Rejected because intent, mutation, recovery and result would remain split across ownership
boundaries.

### Preserve A Review Across Input Changes

Rejected because a human intent recorded for one run revision or digest cannot authorize another.

### Automatically Retry A Failed Claim

Rejected because conflicts and lease races require refreshed evidence and a new explicit review.

## Follow-Up

Define the next bounded Bootstrap phase workflow owner after measuring the resulting parent and
lazy chunks; preserve exact-input, audit, idempotency, recovery and no-autonomous-execution rules.
