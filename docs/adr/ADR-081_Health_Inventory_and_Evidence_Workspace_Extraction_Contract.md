# ADR-081: Health Inventory and Evidence Workspace Extraction Contract

- Status: Accepted
- Date: 2026-08-10
- Owners: Product Owner, Solution Architecture, User Experience, Security Architecture,
  Infrastructure Operations
- Governing documents: ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013,
  ATLAS-016, ATLAS-020, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032,
  ATLAS-033, ATLAS-040, ATLAS-046, ATLAS-047, ATLAS-050, ATLAS-052, ATLAS-055, ATLAS-056,
  ADR-079, ADR-080

## Context

ADR-080 reduced the authenticated Workspace entry graph by 77.8 percent and established a lazy
operational boundary. The deferred operational chunk is still approximately 870 KB because Health,
enterprise governance, release/bootstrap and Connector lifecycle presentation remain in one module.

The Health route also presents upgrade, audit, deployment and identity administration before its
primary storage inventory. Engineers must scroll through unrelated operational surfaces before they
can inspect the selected system, current finding, evidence, dependency path or assessment report.

## Decision

Atlas will extract the read-only Health inventory and evidence presentation into a dedicated static
lazy module. That module will be the first substantive Health content after identity and storage
authorization states resolve.

### Presentation Ownership

- `OperationalApplication` remains authoritative for identity, React Query data, selected asset,
  investigation state, mutations, approvals and every server interaction.
- `HealthInventoryEvidenceWorkspace` receives immutable authorized view data and a bounded asset
  selection callback. It owns no API client, query, mutation, cache or authorization decision.
- The extracted workspace presents storage summary, inventory, active findings, provisional
  investigation context, selected-system evidence, dependency impact and the assessment report.
- Enterprise review, audit, deployment, identity, health-check, reasoning and recommendation
  surfaces remain below the core Health workspace until their own ownership slices are accepted.

### Loading Contract

- The Health inventory module is referenced through one static local dynamic import.
- Connector navigation must not download or evaluate the Health inventory module.
- Health displays an explicit bounded loading state while the presentation chunk is fetched.
- A presentation failure remains fail closed and must not invent health, evidence, impact or
  authorization state.

### Selection And Evidence Contract

- Asset selection uses the existing parent callback and resets only the existing derived
  investigation, RCA, recommendation and report client state.
- Evidence records are rendered only when their references are linked to the selected authorized
  asset. Missing evidence is represented as missing; it is never synthesized.
- Impact paths preserve direct, possible and unknown classifications and expose current gaps and
  the existing safety notice.
- All analysis remains decision support. The module exposes no execution, deployment, connector,
  command or infrastructure mutation control.

### Security And Authority

This decision changes presentation order and module ownership only. Server-side authentication,
tenant scope, RBAC, audit, CSRF, no-store, approval, review separation and trusted-boundary
validation remain authoritative. Props cannot grant permissions or operational authority.

Dynamic imports are build-time local references. No route value, vendor input, evidence content or
user-controlled path can select executable code.

### Verification

- Focused tests cover authorized inventory, selection, evidence filtering, impact boundaries,
  incomplete evidence and non-executable safety language.
- Existing application tests prove loading, selection reset, composer, inspector and direct route
  behavior remain intact.
- ESLint, TypeScript, full Vitest and production build pass.
- Build output contains a separate Health inventory module and Connector direct-load behavior does
  not request it.
- Live desktop and mobile checks cover content order, selection, evidence, overflow and console
  errors.

## Consequences

### Positive

- Health opens with the information engineers came to inspect.
- Inventory and evidence become an independently testable and loadable feature boundary.
- The transitional operational chunk begins shrinking without moving server authority.
- Later investigation, governance and release slices have a concrete extraction pattern.

### Costs

- Query and mutation ownership remains in the transitional operational application.
- Some Health-only API clients remain in the operational chunk until later state-owner extraction.
- Enterprise operational sections remain long until dedicated secondary views are introduced.

## Rejected Alternatives

### Move Health Queries In The Same Slice

Rejected because query ownership is shared with composer, inspector, RCA, recommendation and report
state. Moving presentation first creates a smaller reviewable contract before state ownership moves.

### Hide Existing Enterprise Sections

Rejected because implemented capabilities must remain discoverable until truthful dedicated routes
or tabs own them.

### Duplicate A New Health Dashboard

Rejected because a second source of derived health state would drift from authorized evidence and
create misleading authority.

## Follow-Up

Extract investigation/RCA/recommendation state, introduce truthful secondary Health views for
governance and platform operations, and then remove Health-only clients from the transitional
operational module.
