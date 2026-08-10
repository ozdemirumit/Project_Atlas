# ADR-086: Release Preflight Presentation Extraction Contract

- Status: Accepted
- Date: 2026-08-10
- Owners: Product Owner, Solution Architecture, User Experience, Security Architecture,
  Platform Engineering, Release Management
- Governing documents: ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013,
  ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-038, ATLAS-047, ATLAS-050, ATLAS-052,
  ATLAS-055, ATLAS-056, ATLAS-057, ATLAS-059, ADR-079, ADR-080, ADR-081, ADR-082, ADR-083,
  ADR-084, ADR-085

## Context

IMP-129 extracted Security Export and reduced the transitional operational chunk to 828.09 KB.
Release and bootstrap presentation remains the next large ownership area. It combines small
read-only preflight/configuration/plan panels with a much larger stateful bootstrap workflow that
contains leases, attributable intent, exact-version checks and phase-changing operations.

Moving that entire area in one change would blur the boundary between evidence presentation and
deployment coordination. The first bounded step is the approximately 75-line Release Preflight
panel, which only presents an immutable authorized report and selects query inputs.

## Decision

Atlas will extract Release Preflight presentation into a dedicated static lazy Health feature. The
parent retains acquisition mode and deployment profile state, the authorized query, identity scope
and all downstream release/bootstrap composition. It supplies one authorized report and controlled
mode/profile callbacks.

### Presentation Ownership

- `ReleasePreflightWorkspace` owns the report heading, mode/profile controls, release and manifest
  identity, check evidence, remediation text and read-only safety notice.
- The feature owns no API client, React Query cache, identity, RBAC, release artifact, signature,
  deployment, bootstrap, approval or execution authority.
- Mode and profile controls only request parent state changes; they do not start acquisition,
  installation, deployment or a bootstrap phase.

### Authorization And Loading Contract

- The feature uses one static local import and mounts only while Health is active and an authorized
  immutable preflight report exists.
- A forbidden or absent report remains absent. Presentation must not reveal release metadata when
  discovery is denied.
- Connector routes must not download, evaluate or mount the feature.
- The existing parent query remains authoritative for mode/profile validation, tenant scope,
  authorization and refetch behavior.

### Evidence And Authority Contract

- Report state, checks, evidence, remediation, release/build identity and manifest digest are
  server-produced immutable evidence.
- `mutation_authorized` and `execution_authorized` remain false; the feature cannot reinterpret or
  elevate them.
- A passed preflight is readiness evidence only. It grants no release approval, change approval,
  installation, deployment, bootstrap lease, phase execution or infrastructure mutation.

### Verification

- Focused tests cover report identity, check evidence, remediation, controlled mode/profile
  callbacks, non-authority language and absence of installation/deployment commands.
- Existing application tests preserve query input/refetch behavior and forbidden-report absence.
- ESLint, TypeScript, full Vitest and production build pass with a separate feature chunk.
- Live desktop/mobile checks cover mode/profile selection, evidence presentation, route isolation,
  overflow and final application logs.

## Consequences

### Positive

- Release readiness evidence gains one independently testable and loadable presentation owner.
- Forbidden discovery and no-execution semantics remain unchanged.
- The operational module shrinks without moving bootstrap authority.

### Costs

- Query and selection state remain in the transitional parent.
- Deployment Configuration, Bootstrap Plan and the stateful Bootstrap workflow require separate
  ownership decisions.

## Rejected Alternatives

### Extract The Entire Release And Bootstrap Area

Rejected because immutable readiness presentation and lease-bound phase mutation have materially
different authority, audit and recovery contracts.

### Move The Query Into The Feature

Rejected because identity scope, forbidden-report behavior, cache keys and downstream bootstrap
composition are larger than presentation extraction requires.

### Treat Passed Preflight As Deployment Approval

Rejected because technical readiness cannot grant release, change, deployment or bootstrap
authority.

## Follow-Up

Extract the read-only Deployment Configuration and Bootstrap Plan presentations in bounded slices,
then design stateful Bootstrap workflow ownership around lease, intent, version and audit contracts.

