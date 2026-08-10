# ADR-080: Health Workspace Loading Boundary and Route Code Splitting Contract

- Status: Accepted
- Date: 2026-08-10
- Owners: Product Owner, Solution Architecture, User Experience, Security Architecture,
  Infrastructure Operations
- Governing documents: ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-030, ATLAS-031,
  ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-040, ATLAS-046, ATLAS-047, ATLAS-050, ATLAS-052,
  ATLAS-055, ATLAS-056, ADR-079

## Context

ADR-079 introduced a truthful Workspace, Health and Connectors information architecture and moved
the responsive application shell behind a bounded component. The frontend entry module still owns
more than fourteen thousand lines and imports every operational API and connector surface before
the default Workspace directory can render. The production JavaScript entry chunk is approximately
1.11 MB before compression and Vite reports both transformation and chunk-size warnings.

The next slice must create a real loading and ownership boundary without weakening authentication,
server-side authorization, audit, approval, privacy, or human-decision controls. A direct rewrite of
the operational state graph would create unnecessary regression risk because Health, enterprise
governance, release/bootstrap and Connector lifecycle state currently share one tested module.

## Decision

Atlas will make the application entry module a small workspace coordinator and load the existing
operational application through a React lazy boundary. The normal Workspace landing remains in the
entry graph. Health and Connectors load the operational module only when their URL is active.

### Route Ownership

- `App` owns canonical workspace selection, URL synchronization and the loading boundary.
- `WorkspaceLanding` owns only the authenticated capability directory shell and its minimal
  platform-status and sign-out interactions.
- `OperationalApplication` owns the existing Health and Connectors queries, mutations, forms,
  login experience and operational state until later domain extraction slices move them behind
  smaller tested boundaries.
- Workspace transitions are reported to the coordinator. Browser back, forward, refresh, direct
  links and unknown-route fallback remain deterministic.

### Loading Contract

- The default authenticated `#/workspace` route must render without downloading or evaluating the
  operational application chunk.
- `#/health`, `#/connectors`, approval deep links and unauthenticated sign-in load the operational
  chunk through `React.lazy` and `Suspense`.
- Loading UI uses the real application shell language, identifies the requested workspace and does
  not invent identity, health, approval or authorization state.
- A chunk-load failure presents an explicit retry/reload action. It must not silently substitute
  stale operational content or claim that the platform is healthy.

### Authentication And Cache Boundaries

- The coordinator may read the existing minimized current-identity endpoint only to decide whether
  the authenticated Workspace landing can be shown.
- The operational module remains authoritative for sign-in and all existing domain behavior.
- Workspace sign-out invalidates identity and removes domain query cache without changing server
  session semantics.
- React Query cache keys and server responses remain unchanged so moving module boundaries does not
  create a second authority source.

### Security And Authority

This decision changes module loading and presentation ownership only. It grants no permission,
review lease, approval, workflow, ITSM, change, execution, deployment or infrastructure-mutation
authority. Server-side authentication, CSRF, RBAC, tenant scope, audit, no-store and trusted-boundary
validation remain authoritative.

Dynamic imports are static build-time module references. No route, module name or executable path
is accepted from user input. Chunk loading never evaluates vendor packages, connector artifacts,
prompts, commands or remote code.

### Verification

- Focused tests prove Workspace, Health and Connectors route selection, history synchronization,
  approval-link compatibility, loading fallback and chunk-load recovery.
- Existing application tests remain green against the lazy boundary.
- TypeScript, ESLint, full Vitest and production build pass.
- Build evidence proves a small entry chunk and a separate operational chunk.
- Live desktop and mobile checks prove direct route loading, navigation, no overflow, no overlap and
  an empty final browser error log.

## Consequences

### Positive

- The normal Workspace entry no longer pays the parse and evaluation cost of every operation.
- The application entrypoint becomes a bounded coordinator instead of a domain state owner.
- Existing operational behavior is preserved while a safe extraction point is established.
- Later Health, Governance, Release and Connector slices can move independently from one lazy
  module into dedicated route chunks.

### Costs

- The first operational chunk still contains both Health and Connectors behavior.
- The operational module remains large until subsequent ownership slices extract its domain panels.
- Workspace and the operational module both read the same cached minimized identity record.

## Rejected Alternatives

### Configure Only Vite Manual Chunks

Rejected because vendor-oriented chunk configuration would change file layout without creating a
workspace ownership or loading boundary.

### Rewrite Every Health Panel At Once

Rejected because hundreds of interdependent state values and mutations would make one large change
difficult to review and would increase security and workflow regression risk.

### Keep The Entry Module Monolithic

Rejected because it preserves the exact initial-load and ownership problem accepted for correction
by ADR-079.

## Follow-Up

Subsequent slices extract Health inventory and evidence, investigation/RCA/recommendation, enterprise
governance and release/bootstrap domains into independently tested feature modules. Connector
lifecycle then receives its own route chunk, after which the transitional operational module is
removed.
