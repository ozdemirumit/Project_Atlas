# ADR-083: Health Governance And Report Presentation Extraction Contract

- Status: Accepted
- Date: 2026-08-10
- Owners: Product Owner, Solution Architecture, User Experience, Security Architecture,
  Infrastructure Operations
- Governing documents: ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013,
  ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033,
  ATLAS-036, ATLAS-037, ATLAS-040, ATLAS-043, ATLAS-046, ATLAS-047, ATLAS-050, ATLAS-052,
  ATLAS-055, ATLAS-056, ADR-079, ADR-080, ADR-081, ADR-082

## Context

ADR-082 moved investigation, provisional RCA and recommendation comparison into an independently
loaded Health feature. The transitional operational module remains approximately 845 KB and still
owns the contiguous human-approval and technical-report presentation.

Approval and reporting expose high-value governance evidence but do not own the underlying
authority. Approval creation, deep-link retrieval, reviewer eligibility, attributable decision
mutation, report generation, Markdown download and ITSM dispatch boundaries remain parent or
server responsibilities. Moving those responsibilities with presentation would enlarge the
security boundary and increase regression risk.

## Decision

Atlas will extract approval-review and technical-report presentation into one dedicated static lazy
Health feature. The operational application supplies immutable artifacts, explicit readiness and
failure state, controlled rationale input and bounded callbacks.

### Presentation Ownership

- `HealthGovernanceReportWorkspace` presents the immutable approval packet, decision history,
  separated-reviewer boundary, technical report, source lineage and review-only ITSM draft.
- The feature receives server artifacts and explicit parent state. It owns no API client, React
  Query cache, URL, identity, RBAC, approval, report, download or external-system authority.
- Approval rationale remains controlled by the parent and is passed as a value/change callback.
- Approval submission, attributable decision, report generation and Markdown download are invoked
  only through bounded parent callbacks.

### Loading Contract

- The feature uses one static local dynamic import and mounts only while Health is active.
- Workspace and direct Connector routes must not download, evaluate or mount the feature.
- Loading and chunk failures remain explicit and fail closed without disclosing stale packets,
  reports or invented authority.

### Governance Contract

- Review eligibility is computed by the existing authoritative parent/server boundary and supplied
  as `canReview`; the presentation cannot elevate it.
- Approval packets preserve exact recommendation and option versions, digest, risk, impact,
  interruption, recovery, assumptions, unknowns, plan and decision history.
- An approval records a human decision only. It grants no RBAC, connector, runtime or infrastructure
  execution authority.
- Rationale and outcome callbacks cannot bypass server-side separation of duties, optimistic
  concurrency, audit or attribution controls.

### Reporting Contract

- Technical reports preserve immutable source lineage, classification, redaction, evidence,
  limitations, digest and human-review state.
- Markdown download remains a local user command supplied by the parent; the feature does not write
  files autonomously.
- The ITSM handoff remains a review-only draft. No external dispatch or external-record mutation is
  inferred from presentation.
- Report generation does not authorize execution or external-system mutation.

### Security And Authority

This decision changes presentation and module ownership only. Authentication, tenant scope, RBAC,
CSRF, approval separation, audit, URL deep-link validation, report integrity, download initiation,
ITSM dispatch and no-autonomous-execution policies remain authoritative and unchanged.

### Verification

- Focused tests cover empty, pending, failed and populated approval/report states, controlled
  rationale, bounded callbacks, reviewer separation, decision history, lineage, download readiness,
  ITSM draft boundaries and no-authority claims.
- Existing application tests prove deep links, approval decisions, report generation and download
  wiring remains intact.
- ESLint, TypeScript, full Vitest and production build pass with a separate governance/report chunk.
- Live desktop and mobile checks cover recommendation-to-review/report progression, rationale
  controls, overflow and final application console errors.

## Consequences

### Positive

- Human-governance evidence becomes independently testable and loadable.
- The operational module shrinks without moving sensitive state or authority.
- Approval and reporting remain visually adjacent while their server contracts stay separate.

### Costs

- The feature receives a broad controlled-props contract.
- Approval and report mutations remain in the transitional parent.
- Later state-owner extraction still requires an independent URL, query and authority decision.

## Rejected Alternatives

### Move Approval State And Mutations With Presentation

Rejected because URL deep links, reviewer separation, concurrency and audit are a larger authority
boundary than presentation extraction requires.

### Dispatch ITSM From The Report Feature

Rejected because a generated draft is not dispatch authorization and presentation must not mutate
an external record.

### Keep Governance And Reports In The Transitional Module

Rejected because the contiguous presentation has a clear controlled boundary and remains a material
part of the deferred operational chunk.

## Follow-Up

Extract the remaining Health secondary operational presentations, then design a dedicated Health
state owner for queries and mutations after URL and authority contracts are independently tested.
