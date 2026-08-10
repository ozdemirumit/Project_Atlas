# ADR-082: Health Decision-Support Presentation Extraction Contract

- Status: Accepted
- Date: 2026-08-10
- Owners: Product Owner, Solution Architecture, User Experience, Security Architecture,
  Infrastructure Operations
- Governing documents: ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013,
  ATLAS-016, ATLAS-020, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032,
  ATLAS-033, ATLAS-037, ATLAS-040, ATLAS-041, ATLAS-042, ATLAS-043, ATLAS-044, ATLAS-046,
  ATLAS-047, ATLAS-050, ATLAS-052, ATLAS-055, ATLAS-056, ADR-079, ADR-080, ADR-081

## Context

ADR-081 moved inventory and evidence into the first independently loaded Health feature. The
transitional operational module remains approximately 860 KB and still contains the complete
investigation, provisional RCA and recommendation comparison presentation.

These three surfaces form one decision-support progression but do not own execution authority.
Their API mutations, parent reset behavior, approval URL state and technical report generation are
currently intertwined with later governance panels. Moving state ownership and presentation in one
change would create unnecessary regression risk.

## Decision

Atlas will extract the investigation, RCA and recommendation presentation into a dedicated static
lazy Health feature. The operational application retains all query, mutation, approval and report
authority and supplies immutable artifacts, explicit state flags and bounded callbacks.

### Presentation Ownership

- `HealthDecisionSupportWorkspace` presents the reasoning artifact, provisional RCA case and
  compared recommendation options.
- The feature receives artifact values and pending/error flags; it owns no API client, React Query
  cache, mutation, URL state, identity or permission decision.
- `OperationalApplication` retains the exact build-RCA and compare-options callbacks, including all
  existing downstream reset behavior.
- Approval review and technical report/ITSM handoff remain outside this module and preserve their
  current server and human authority boundaries.

### Loading Contract

- The feature uses one static local dynamic import and mounts only while Health is active.
- Direct Workspace and Connector routes must not download, evaluate or mount the feature.
- Loading and chunk failures are explicit and fail closed without showing stale conclusions or
  inferring root cause, impact, recommendation, permission or execution authority.

### Decision-Support Contract

- Investigation claims retain epistemic type, confidence, evidence balance and unknowns.
- RCA remains provisional unless the server artifact explicitly states otherwise; missing evidence
  and blockers remain visible.
- Recommendations preserve all compared options, risk, duration, interruption, recovery, policy
  and exclusion data. A preferred option is not an approval or executable instruction.
- No button in the extracted feature can execute infrastructure, deploy code, mutate an external
  system or grant runtime authority.

### Security And Authority

This decision changes presentation and module ownership only. Server authentication, tenant scope,
RBAC, audit, CSRF, approval separation, signed evidence, human review and no-autonomous-execution
policies remain authoritative. Callback availability cannot elevate user authority.

### Verification

- Focused tests cover empty, pending, failed and populated artifact states, bounded callbacks,
  epistemic labels, provisional language, compared options and no-execution claims.
- Existing application tests prove investigation, RCA, recommendation, approval and report flow
  remains intact.
- ESLint, TypeScript, full Vitest and production build pass with a separate decision-support chunk.
- Live desktop and mobile checks cover progression, action enablement, option comparison, overflow
  and final console errors.

## Consequences

### Positive

- A coherent decision-support progression becomes independently testable and loadable.
- The operational module shrinks without moving approval or execution authority.
- Later state-owner extraction can use a typed callback and artifact contract.

### Costs

- Mutation and URL ownership remain in the transitional parent.
- The feature receives a broad artifact contract until state ownership moves.
- Approval and technical report panels remain in the operational chunk.

## Rejected Alternatives

### Move Approval And Report In The Same Slice

Rejected because review separation, approval URL state, report download and ITSM handoff introduce a
larger authority boundary than presentation extraction requires.

### Reimplement The Reasoning Flow

Rejected because duplicating derivation in the browser would create a second, non-authoritative
source of truth.

### Keep Decision Support In The Transitional Module

Rejected because the existing contiguous presentation has a clear ownership boundary and preserves
the primary remaining chunk-size and maintainability problem.

## Follow-Up

Extract approval/report presentation, then move Health decision-support mutation ownership behind a
dedicated state owner after its review and URL contracts are independently tested.
