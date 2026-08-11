# ADR-101: Capability-Aware Workspace Navigation

- Status: Accepted
- Date: 2026-08-11
- Owners: Product Architecture, Frontend Architecture, Infrastructure Operations
- Governing documents: ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-031,
  ATLAS-050, ATLAS-052, ATLAS-055, ATLAS-056

## Context

The authenticated Workspace landing page presents implemented capabilities, but every capability
button currently targets only a broad Health or Connectors workspace. Investigation, governance
and deployment capabilities therefore open Health Overview, while all connector capabilities
open the same unstructured top of a long governed lifecycle. The behavior makes implemented
features difficult to discover and breaks the user's task intent.

Health already owns four stable task views. Connectors now owns a visible installed MCP inventory
and a complete governed Builder and lifecycle chain, but lacks stable task-level navigation.

## Decision

Atlas will represent Workspace capability destinations as typed task routes. Health capabilities
target one of Overview, Investigate, Deployments or Governance. Connector capabilities target one
of Inventory, Builder, Runtime or Knowledge.

Canonical connector routes are:

- `#/connectors/inventory`
- `#/connectors/builder`
- `#/connectors/runtime`
- `#/connectors/knowledge`

The existing `#/connectors` route remains valid and resolves to Inventory. Unknown nested routes
fail closed to Workspace. Browser back, forward and direct navigation restore the exact task view.

## Presentation

Connectors receives an accessible task tab list. Selecting a tab updates the canonical route and
brings the corresponding existing governed section into view:

- Inventory targets installed MCP management;
- Builder targets OpenAPI source intake;
- Runtime targets target, credential, trust and bounded-operation lifecycle coverage; and
- Knowledge targets evidence, knowledge publication and protected AI-context lifecycle coverage.

The Workspace landing page displays the exact destination beside every capability. Navigation
does not synthesize missing records, expose controls before their prerequisites, or grant any
connector, target, credential, runtime, AI or infrastructure authority.

## Accessibility And State

Task tabs use tab semantics, roving focus and left/right/home/end keyboard navigation. Route state
is the source of truth. Scrolling is a presentation effect only and cannot alter workflow state.
Reduced-motion preference disables smooth scrolling.

## Consequences

- Implemented capabilities become reachable from the landing page without guesswork.
- Connector inventory, Builder, runtime and knowledge areas gain durable shareable URLs.
- The long connector lifecycle remains intact; this slice improves task discovery without
  weakening ordered prerequisites or duplicating workflow state.
- Future extraction into independent connector workspaces can preserve these route contracts.

## Verification

- Unit tests cover route parsing, canonical hashes, invalid-route fallback and browser history.
- Component tests cover exact capability destinations and accessible connector task navigation.
- Full frontend quality gates and production build pass.
- Live desktop and mobile checks cover direct routes, capability navigation, browser history,
  focused section placement, keyboard tabs and horizontal fit.
