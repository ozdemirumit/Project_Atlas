# ADR-079: Operational Workspace Information Architecture Contract

- Status: Accepted
- Date: 2026-08-10
- Owners: Product Owner, Solution Architecture, User Experience, Security Architecture,
  Infrastructure Operations
- Governing documents: ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-030, ATLAS-031,
  ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-040, ATLAS-046, ATLAS-047, ATLAS-050, ATLAS-052,
  ATLAS-055, ATLAS-056 and ADR-001 through ADR-078

## Context

Atlas now contains broad operational, connector, knowledge, recommendation and governance
capabilities. The web client exposes many of them inside one component of more than fourteen
thousand lines. Six primary navigation labels are visible, but only Connector and non-Connector
states are distinct; several labels therefore open the same workspace and two administrative
controls do not navigate anywhere. Completed capabilities are difficult to discover and the
interface does not clearly separate available workspaces from later planned authority.

The platform needs an incremental information-architecture correction before more capabilities
are added. The correction must preserve all security, authorization, audit, privacy and
human-decision boundaries already established by the product architecture.

## Decision

Atlas will introduce a bounded application shell and a truthful operational workspace directory.
The first slice exposes only navigation destinations that have distinct, tested content:

- `Workspace` provides a concise capability directory grouped by operations, connector lifecycle,
  AI decision support and platform governance;
- `Health` preserves the existing storage-health, investigation, RCA, recommendation, approval,
  reporting and impact workspace; and
- `Connectors` preserves the governed MCP Builder and connector lifecycle workspace.

Inactive or unimplemented destinations are not presented as working controls. Later dedicated
Infrastructure, Topology, Reports, Governance and Settings destinations require their own tested
workspace slices before entering primary navigation.

### Truthful Capability Visibility

The Workspace directory may describe only capabilities implemented in the repository. It groups
capabilities by user intent and links to the owning workspace. It must distinguish available
decision-support functions from later or separately authorized operations. It must not infer
runtime health, connector state, completion, approval or authority from static documentation.

Static lifecycle labels are limited to product capability availability. Dynamic health or work
state must come from authenticated APIs and fail closed when unavailable.

### Application Shell Boundary

Sidebar, top bar, responsive navigation, platform status and authenticated identity presentation
move behind a dedicated application-shell component. The shell owns layout and navigation events,
not domain queries, mutations, secrets or decision state. Domain workspaces remain independently
testable and are extracted incrementally rather than through one high-risk rewrite.

The active workspace is represented in the URL so refresh, browser history and direct links retain
context. Unknown destinations resolve to Workspace without exposing hidden controls.

### Interaction And Accessibility

- Primary navigation uses icon and text labels with a single selected state.
- Mobile navigation is modal, keyboard reachable and dismissible without moving page content.
- Familiar icon-only controls retain accessible names and tooltips where meaning is not obvious.
- Headings, status labels and controls fit at desktop and 390-pixel mobile widths without overlap
  or horizontal scrolling.
- Sections remain unframed; cards are reserved for repeated capability records and are never
  nested inside cards.
- Loading, empty, unavailable and permission-denied states remain distinct and do not invent data.

### Security And Authority

This work changes presentation and navigation only. It grants no permission, reviewer lease,
approval, workflow, ITSM, change, execution, deployment or infrastructure-mutation authority.
Existing server-side authentication, CSRF, RBAC, tenant scope, audit and no-store boundaries remain
authoritative. Hidden or disabled client controls are never treated as authorization controls.

### Delivery Strategy

The first implementation slice will:

1. add the Workspace capability directory and make it the honest entry workspace;
2. reduce primary navigation to the three distinct destinations;
3. ensure Health and Connectors render only their own content, composer and inspector surfaces;
4. introduce URL-backed workspace selection and responsive behavior;
5. begin application-shell extraction without moving domain state across ownership boundaries; and
6. retain existing tests while adding focused navigation, capability visibility and mobile tests.

Further extraction proceeds by independently tested feature workspaces. No big-bang rewrite of the
current application component is authorized.

## Consequences

### Positive

- Users can see what Atlas already provides and where each capability belongs.
- Navigation no longer implies that unfinished destinations work.
- Refresh and direct links retain workspace context.
- Layout responsibilities begin moving out of the monolithic application component.
- Future workspace extraction can proceed in bounded, reviewable slices.

### Costs

- The first slice does not fully decompose every existing domain workspace.
- Additional UI slices are required for dedicated Infrastructure, Topology, Reports, Governance
  and Settings experiences.
- Existing broad application tests must remain green while focused shell tests are added.

## Rejected Alternatives

### Cosmetic Restyling Only

Rejected because spacing and color changes would not fix false navigation, poor capability
discovery or the monolithic ownership boundary.

### Rewrite The Entire Frontend

Rejected because a large rewrite would create unnecessary behavioral, accessibility and security
regression risk.

### Display Every Planned Capability As Available

Rejected because the interface must not overstate implementation state or operational authority.

## Follow-Up

Later slices extract dedicated Infrastructure, Topology, Reports and Governance workspaces, split
domain query ownership from the current application component, add role-aware task inboxes and
optimize production chunking without weakening strict transport validation.
