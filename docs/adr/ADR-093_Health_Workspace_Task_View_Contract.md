# ADR-093: Health Workspace Task View Contract

- Status: Accepted
- Date: 2026-08-11
- Owners: Product Owner, Solution Architecture, User Experience, Security Architecture,
  Infrastructure Operations
- Governing documents: ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013,
  ATLAS-016, ATLAS-023, ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-037, ATLAS-046,
  ATLAS-047, ATLAS-050, ATLAS-052, ATLAS-055, ATLAS-056, ADR-079 through ADR-092

## Context

ADR-079 established a truthful Workspace, Health and Connectors shell. Subsequent bounded feature
extractions reduced the transitional operational bundle and gave several Health capabilities
independent presentation or workflow ownership. The Health workspace nevertheless presents
inventory, scheduled checks, investigation, recommendation, release readiness, Bootstrap,
identity governance, human review, audit and security delivery in one long scrolling surface.

The capabilities are implemented, but their presentation does not match the repeated task model
defined by ATLAS-052. Operators cannot quickly distinguish assessment, investigation, deployment
coordination and governance work. The consolidation must improve information architecture without
moving domain authority, changing requests or weakening fail-closed behavior.

## Decision

Health will expose four task views through one persistent secondary navigation:

- `Overview` owns inventory, findings, dependency impact and scheduled read-only health checks;
- `Investigate` owns the question composer, investigation, RCA, recommendation, technical report
  and recommendation approval presentation;
- `Deployments` owns release preflight, redacted deployment configuration, Bootstrap plan,
  checkpoint, lease, phase, invalidation, recovery, support and upgrade coordination; and
- `Governance` owns assigned human reviews, browser sessions, personal tokens, administrative
  access, workload identities, audit delivery and Syslog/SIEM evidence.

This is a presentation partition. Existing feature components, queries, mutations, cache recovery,
server validation and authorization boundaries retain their current owners.

### URL And History Contract

The canonical Health destinations are:

- `#/health/overview`;
- `#/health/investigate`;
- `#/health/deployments`; and
- `#/health/governance`.

`#/health` remains a compatible direct link and resolves to Overview. Primary Health navigation
opens Overview. A valid nested Health route survives refresh and browser history. Unknown nested
routes fail to Workspace under the existing shell contract. An `approval_request_id` deep link
opens Investigate unless the URL already names a valid explicit Health task view.

### Presentation Contract

- The page heading and summary describe the selected task view.
- Only the selected view's task surfaces are rendered; shared authentication, loading, unavailable
  and current-context evidence remain available where required.
- The secondary navigation remains visible while the task surface scrolls.
- Desktop presentation uses four stable equal tracks. Mobile presentation preserves legible control
  sizes through bounded horizontal navigation rather than shrinking or wrapping labels into
  overlap.
- Tabs expose selected state, keyboard focus and Left, Right, Home and End navigation.
- Composer visibility is limited to Investigate. The context inspector remains available across
  Health views because selected target evidence is shared context, not task authority.

### Security And Authority

View selection is not authorization. It grants no permission, reviewer lease, approval, workflow,
ITSM, release, Bootstrap, connector, execution or infrastructure-mutation authority. The backend
continues to decide data visibility and every mutation. Hidden surfaces remain mounted only through
their existing authorized data and cannot be treated as a client-side security boundary.

No request payload, idempotency rule, CSRF control, exact-input review fingerprint, audit event,
server schema or cache-recovery contract changes in this decision.

## Consequences

### Positive

- Health is organized by operator intent instead of implementation chronology.
- The initial view is concise enough for routine inventory and health assessment.
- Deployment and governance controls no longer compete with investigation evidence in one scroll.
- Direct URLs can be shared, refreshed and traversed with browser history.
- Existing bounded feature ownership is preserved for later extraction work.

### Costs

- The transitional application component still composes many Health queries and workflows.
- View selection initially changes presentation, not query activation or backend workload.
- Dedicated top-level Investigations, Approvals, Audit and Administration workspaces remain future
  slices under ADR-079.

## Rejected Alternatives

### Cosmetic Spacing And Color Changes

Rejected because visual polish alone would leave unrelated tasks in one scrolling surface.

### Move Every Health Capability Into A New Top-Level Workspace

Rejected because the current shell may expose only distinct, tested destinations. A broad route
expansion would overstate ownership and increase regression risk.

### Rewrite Health Before Consolidating It

Rejected because current security and workflow boundaries are tested and can be partitioned
without a high-risk replacement.

### Persist Selection Only In Local State

Rejected because refresh, direct links and browser history would lose operator context.

## Validation

- Route tests cover all canonical Health destinations, default resolution, unknown-route failure,
  approval deep links and browser history synchronization.
- Component tests cover selected state, explicit navigation and keyboard traversal.
- Application tests enter the owning route for deployment and governance workflows and traverse
  Overview, Governance and Investigate in one integrated task flow.
- Full lint, strict TypeScript, frontend tests, production build and desktop/mobile live validation
  are required before merge.

## Follow-Up

Continue bounded Health feature extraction within the new task views. Evaluate query activation
and dedicated top-level workspaces only through separate authority and performance contracts.
