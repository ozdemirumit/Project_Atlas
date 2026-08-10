# ADR-088: Bootstrap Plan Presentation Extraction Contract

- Status: Accepted
- Date: 2026-08-10
- Owners: Product Owner, Solution Architecture, User Experience, Security Architecture,
  Platform Engineering
- Governing documents: ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013,
  ATLAS-025, ATLAS-026, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-038, ATLAS-047, ATLAS-050,
  ATLAS-052, ATLAS-053, ATLAS-055, ATLAS-056, ATLAS-057, ADR-079, ADR-080, ADR-081, ADR-082,
  ADR-083, ADR-084, ADR-085, ADR-086, ADR-087

## Context

IMP-131 extracted Deployment Configuration and reduced the transitional operational chunk to
824.09 KB. The next contiguous read-only surface is the approximately 45-line Bootstrap Plan. It
shows exact-input plan identity, resume metadata, ordered phases, dependencies, readiness and stop
guidance without claiming a lease or executing a phase.

The plan query is composed from an authorized preflight, redacted deployment configuration and
tenant scope. The same plan later contributes to checkpoint invalidation, controlled rebase and
lease claims. Those stateful capabilities have stronger identity, intent, exact-version, audit and
recovery requirements than read-only presentation.

## Decision

Atlas will extract Bootstrap Plan presentation into a dedicated static lazy Health feature. The
parent retains the authorized query and every downstream stateful bootstrap capability. It supplies
one schema-valid immutable plan to the presentation.

### Presentation Ownership

- `BootstrapPlanWorkspace` owns plan state, truncated digest, resume key, phase count, ordered phase
  title/identifier/dependencies/state/stop guidance and the planning-only safety notice.
- The feature owns no API client, React Query cache, identity, RBAC, tenant scope, checkpoint,
  invalidation, rebase, lease, intent, audit, phase runner, rollback or infrastructure authority.
- Phase order and dependencies are rendered exactly as supplied by the validated server response;
  presentation does not infer readiness or modify topology.

### Authorization And Loading Contract

- The feature uses one static local import and mounts only while Health is active and an authorized,
  schema-valid plan exists.
- A forbidden, malformed or absent plan remains absent and discloses no plan, resume or phase
  metadata.
- Connector routes must not download, evaluate or mount the feature.
- Parent query composition remains authoritative for release/configuration lineage, tenant scope,
  invalidation and downstream state changes.

### Evidence And Authority Contract

- Plan identity, digest, resume key, phases, dependencies, readiness and stop guidance are
  server-produced immutable evidence.
- `mutation_authorized` and `execution_authorized` remain false and cannot be elevated by the
  presentation.
- A ready plan grants no checkpoint update, rebase, lease claim, phase execution, rollback,
  deployment or infrastructure mutation.

### Verification

- Focused tests cover plan identity, ordered phases, dependency and stop guidance, blocked evidence,
  planning-only language and absence of operational controls.
- Existing application tests preserve exact-input query composition, forbidden/malformed absence
  and downstream invalidation behavior.
- ESLint, TypeScript, full Vitest and production build pass with a separate feature chunk.
- Live desktop/mobile checks cover phase evidence, overflow, route isolation and final application
  logs.

## Consequences

### Positive

- Bootstrap planning evidence gains an independently testable and loadable presentation owner.
- Planning and phase-execution authority remain visibly separate.
- The operational module shrinks before stateful bootstrap workflow extraction.

### Costs

- Plan query and downstream state composition remain in the transitional parent.
- Bootstrap checkpoint, invalidation, rebase, lease and phase workflows still require separate
  ownership decisions.

## Rejected Alternatives

### Move Plan Query Into The Feature

Rejected because tenant scope, release/configuration lineage and cache/downstream composition are
larger than presentation extraction requires.

### Extract Plan And Stateful Bootstrap Workflow Together

Rejected because immutable plan evidence and lease-bound mutation have different authorization,
audit, concurrency and recovery contracts.

### Derive Or Reorder Phases In Presentation

Rejected because order, dependencies, readiness and stop guidance are trusted server evidence and
must not be reinterpreted by the UI.

## Follow-Up

Extract the read-only Bootstrap Checkpoint presentation, then design stateful Bootstrap workflow
ownership around intent, lease, exact-version, audit, concurrency and recovery contracts.
