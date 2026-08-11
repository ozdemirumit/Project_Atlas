# ADR-089: Bootstrap Checkpoint Presentation Extraction Contract

- Status: Accepted
- Date: 2026-08-10
- Owners: Product Owner, Solution Architecture, User Experience, Security Architecture,
  Platform Engineering
- Governing documents: ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013,
  ATLAS-025, ATLAS-026, ATLAS-027, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-038, ATLAS-047,
  ATLAS-050, ATLAS-052, ATLAS-053, ATLAS-055, ATLAS-056, ATLAS-057, ADR-079, ADR-080,
  ADR-081, ADR-082, ADR-083, ADR-084, ADR-085, ADR-086, ADR-087, ADR-088

## Context

IMP-132 extracted Bootstrap Plan and reduced the transitional operational chunk to 822.91 KB. The
next read-only surface is the Bootstrap Checkpoint header and approximately 75 lines of durable run,
revision, phase progress, lease-state, plan-digest and lease-expiry evidence.

The same parent section owns lease claims and all phase-changing bootstrap workflows. Presentation
must not acquire a lease, reveal a lease-owner subject, infer execution authority or weaken the
exact-version and audit boundaries of those workflows.

## Decision

Atlas will extract Bootstrap Checkpoint presentation into a dedicated static lazy Health feature.
The parent retains the authorized state query and every state-changing bootstrap workflow. The lazy
boundary wraps the complete checkpoint/workflow section so a presentation load failure hides all
stateful controls rather than exposing them without checkpoint context.

### Presentation Ownership

- `BootstrapCheckpointWorkspace` owns durability, run/revision/completion summary, bounded lease
  status, ordered checkpoint progress, truncated plan digest, formatted lease expiry and empty-state
  presentation.
- Phase state is selected only from a matching server checkpoint, the server current-phase marker or
  the literal pending fallback; no readiness or execution state is inferred.
- The feature owns no API client, React Query cache, identity, RBAC, tenant scope, lease claim,
  invalidation, rebase, artifact store, phase runner, rollback or infrastructure authority.

### Authorization And Loading Contract

- The feature uses one static local import and mounts only while Health is active and an authorized,
  schema-valid state exists.
- A forbidden, malformed or absent state remains absent and discloses no run, phase or lease
  metadata.
- Connector routes must not download, evaluate or mount the feature.
- The parent query and server response remain authoritative for tenant isolation, run lineage,
  checkpoint integrity and lease availability.
- A lazy-load/render failure replaces the full checkpoint/workflow section with the existing
  fail-closed Health boundary; state-changing controls are not left visible.

### Evidence And Authority Contract

- Run identity, revision, phase order, checkpoint states, digests and lease timing are immutable
  server-produced evidence.
- The UI may display only `Available`, `Held by this session` or `Held by another operator`; it must
  not request or expose another actor's subject identifier.
- `execution_authorized` and `infrastructure_mutation_authorized` remain false and cannot be elevated
  by presentation.
- Viewing a durable or active run grants no lease, checkpoint update, phase execution, rollback,
  deployment or infrastructure mutation.

### Verification

- Focused tests cover durable/ephemeral and empty states, run identity, bounded lease labels, ordered
  completed/current/pending checkpoints, digest/expiry and absence of operational controls.
- Existing application tests preserve malformed absence, no-lease-on-load behavior and all governed
  stateful workflows.
- ESLint, both TypeScript project references, full Vitest and production build pass with a separate
  feature chunk.
- Live desktop/mobile checks cover checkpoint evidence, overflow, route isolation and final
  application logs.

## Consequences

### Positive

- Checkpoint evidence gains an independently testable and loadable presentation owner.
- Stateful controls cannot outlive a failed checkpoint presentation boundary.
- Lease privacy and no-action-on-view language remain explicit.

### Costs

- State query and all workflow state remain in the transitional parent.
- Stateful bootstrap actions still require further ownership decomposition.

## Rejected Alternatives

### Move State Query Into The Feature

Rejected because tenant identity, refetch/invalidation and all downstream mutations share the parent
query contract.

### Move Lease Claim With Presentation

Rejected because lease acquisition requires intent, justification, exact-version, idempotency,
audit, concurrency and recovery contracts that presentation does not own.

### Leave Actions Visible If Presentation Fails

Rejected because operators must not receive state-changing controls without authoritative
checkpoint context.

## Follow-Up

Extract the read-only Bootstrap Invalidation presentation and keep controlled rebase authority in
the parent, then continue stateful Bootstrap workflow decomposition.
