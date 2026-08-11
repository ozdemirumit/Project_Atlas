# ADR-090: Bootstrap Invalidation Presentation Extraction Contract

- Status: Accepted
- Date: 2026-08-11
- Owners: Product Owner, Solution Architecture, User Experience, Security Architecture,
  Platform Engineering
- Governing documents: ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013,
  ATLAS-025, ATLAS-026, ATLAS-027, ATLAS-028, ATLAS-029, ATLAS-030, ATLAS-031, ATLAS-032,
  ATLAS-038, ATLAS-047, ATLAS-050, ATLAS-052, ATLAS-053, ATLAS-055, ATLAS-056, ATLAS-057,
  ADR-079, ADR-080, ADR-081, ADR-082, ADR-083, ADR-084, ADR-085, ADR-086, ADR-087, ADR-088,
  ADR-089

## Context

IMP-133 extracted Bootstrap Checkpoint and reduced the transitional operational chunk to 821.45 KB.
The next bounded surface is the read-only part of Bootstrap Invalidation: empty/unchanged/drifted
state, source revision, earliest boundary, reusable and invalidated counts, bounded change reasons,
and downstream review phase lists.

The same section also contains a controlled checkpoint rebase workflow. Rebase requires a current
lease, exact source revision, explicit review intent, justification, idempotency, audit and server
mutation. Those responsibilities are outside read-only presentation.

## Decision

Atlas will extract Bootstrap Invalidation evidence into a dedicated static lazy Health feature. The
parent retains the authorized preview query, rebase eligibility, confirmation state, mutation,
cache invalidation and result. The lazy boundary wraps the complete invalidation/rebase section so
state-changing controls fail closed if evidence presentation cannot load.

### Presentation Ownership

- `BootstrapInvalidationWorkspace` owns state, empty-state guidance, source revision, earliest
  boundary, reusable/invalidated counts, bounded change reasons and reusable/invalidated/downstream
  phase lists.
- Change presentation includes reason code, normalized field name and earliest affected phase only.
  `old_reference` and `new_reference` are not rendered.
- The feature owns no API client, React Query cache, identity, RBAC, tenant scope, lease, rebase,
  checkpoint mutation, phase runner, rollback or infrastructure authority.

### Authorization And Loading Contract

- The feature uses one static local import and mounts only while Health is active and an authorized,
  schema-valid preview exists.
- A forbidden, malformed or absent preview remains absent and discloses no drift metadata.
- Connector routes must not download, evaluate or mount the feature.
- Parent query composition remains authoritative for exact plan/configuration/tenant lineage.
- Lazy-load/render failure replaces the full invalidation/rebase section with the existing
  fail-closed Health boundary; review and confirmation controls are not left visible.

### Evidence And Authority Contract

- Preview state, source revision, changes and phase classifications are immutable server-produced
  evidence.
- Presentation does not infer checkpoint reusability, rebase eligibility or phase readiness.
- `execution_authorized`, `lease_mutation_authorized`, `checkpoint_mutation_authorized` and
  `infrastructure_mutation_authorized` remain false and cannot be elevated by presentation.
- Viewing drift grants no checkpoint update, lease, phase execution, rollback, deployment or
  infrastructure mutation.

### Verification

- Focused tests cover empty, unchanged and drifted evidence; counts, change reasons, phase lists,
  reference privacy and absence of operational controls.
- Existing application tests preserve malformed absence and controlled rebase eligibility,
  confirmation and mutation behavior.
- Full ESLint, both TypeScript project references, full Vitest and production build pass with a
  separate feature chunk.
- Live desktop/mobile checks cover invalidation evidence, overflow, route isolation and final
  application logs.

## Consequences

### Positive

- Drift evidence gains an independently testable and loadable presentation owner.
- Sensitive old/new references remain outside visible UI.
- Rebase controls cannot outlive a failed evidence presentation boundary.

### Costs

- Preview query and rebase workflow remain in the transitional parent.
- Other stateful bootstrap actions still require further decomposition.

## Rejected Alternatives

### Move Rebase Into The Presentation Feature

Rejected because exact revision, lease, intent, justification, idempotency, audit and recovery are
state-changing responsibilities.

### Render Old And New References

Rejected because bounded field/reason/phase evidence is sufficient for this view and references may
contain unnecessary operational detail.

### Leave Rebase Controls Visible If Presentation Fails

Rejected because checkpoint mutation must not be offered without authoritative drift evidence.

## Follow-Up

Define the next stateful Bootstrap workflow ownership slice using intent, exact-version, lease,
audit, concurrency and recovery contracts; continue reducing the transitional operational module.
