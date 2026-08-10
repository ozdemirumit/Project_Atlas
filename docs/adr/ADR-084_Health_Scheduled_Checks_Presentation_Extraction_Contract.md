# ADR-084: Health Scheduled Checks Presentation Extraction Contract

- Status: Accepted
- Date: 2026-08-10
- Owners: Product Owner, Solution Architecture, User Experience, Security Architecture,
  Infrastructure Operations
- Governing documents: ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013,
  ATLAS-016, ATLAS-020, ATLAS-023, ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033,
  ATLAS-040, ATLAS-046, ATLAS-047, ATLAS-050, ATLAS-052, ATLAS-055, ATLAS-056, ADR-079,
  ADR-080, ADR-081, ADR-082, ADR-083

## Context

IMP-127 extracted Health approval and report presentation, reducing the transitional operational
chunk to 834.15 KB. Scheduled health checks remain a contiguous read-only presentation block in the
operational parent even though their query, selection and mutation boundaries are already explicit.

The panel presents definitions, deterministic schedules, latest observations, findings, evidence
counts and limits. It may request an authorized read-only run, but it does not own connector,
credential, capability, policy, scheduler or execution authority.

## Decision

Atlas will extract scheduled health-check presentation into a dedicated static lazy Health feature.
The parent supplies the authorized overview, selected definition/schedule/run, explicit loading and
failure state, and bounded selection/run callbacks.

### Presentation Ownership

- `HealthScheduledChecksWorkspace` owns definition tabs, schedule/run summaries, observation and
  finding presentation, limits, unknowns and the read-only safety notice.
- The feature owns no API client, React Query cache, identity, RBAC, credential, connector,
  scheduler, mutation or infrastructure authority.
- Definition selection and manual read-only run requests delegate through parent callbacks.

### Loading And Failure Contract

- The feature loads through one static local import and mounts only while Health is active.
- Loading, unavailable, empty and run-failure states remain explicit and fail closed.
- Workspace and direct Connector routes must not download, evaluate or mount the feature.

### Authority Contract

- The server and existing parent mutation remain authoritative for identity, scope, enabled state,
  capability class, connector policy, audit, timeout, evidence limits and request execution.
- The Run Check command cannot enable a disabled definition or bypass pending/error state.
- A health-check run is bounded read-only evidence collection. Findings do not confirm root cause,
  outage or permission to change infrastructure.

### Verification

- Focused tests cover loading, failure, empty and populated states, selection, run delegation,
  disabled definitions, observations, findings, limits and no-authority claims.
- Existing application tests preserve query invalidation and API request behavior.
- ESLint, TypeScript, full Vitest and production build pass with a separate feature chunk.
- Live desktop/mobile checks cover tab selection, one read-only run, overflow and application logs.

## Consequences

### Positive

- A frequent Health workflow becomes independently testable and loadable.
- Observation tables and failure states have one presentation owner.
- The operational module shrinks without enlarging connector or execution authority.

### Costs

- Query, selected-definition state and mutation remain in the transitional parent.
- Secondary Health operations still require further bounded extraction slices.

## Rejected Alternatives

### Move Query And Mutation State Into The Feature

Rejected because selection presentation does not require moving cache invalidation, identity scope or
connector invocation authority.

### Combine Security Export And Health Checks

Rejected because Syslog/SIEM delivery evidence and connector health evidence have separate security,
transport and operational contracts.

## Follow-Up

Extract the Security Export presentation, then assess release/bootstrap presentation ownership as a
separate multi-step authority decision.
