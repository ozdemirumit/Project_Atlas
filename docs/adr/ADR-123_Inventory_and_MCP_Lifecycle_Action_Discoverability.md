# ADR-123: Inventory and MCP Lifecycle Action Discoverability

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-12 |
| Owners | Product Architecture, Experience Architecture, Security Architecture |
| Related | ATLAS-001, ATLAS-003, ATLAS-020, ATLAS-031, ATLAS-032, ATLAS-047, ATLAS-052, ADR-111, ADR-112, ADR-122 |

## Context

Atlas already provides governed device registration and retirement plus MCP instance creation and
retirement. The device registry is presented under a generic Health Overview label. Connector
lifecycle controls share their first screen with extensive signing-provider diagnostics, which push
the inventory table and retirement controls far below the initial viewport.

Development identity is intentionally insufficient for protected lifecycle mutations. The current
screen reports an authorization failure but does not offer a direct path to the enterprise login
form, making an existing capability appear absent or broken.

## Decision

The Health overview entry will be named Inventory and health while retaining its stable route. Device
registration remains the first section in that view.

Connector Inventory will keep Add MCP in its primary heading and visually order lifecycle filters,
status, records and retirement controls before secondary signing and onboarding diagnostics. Those
diagnostics will be grouped in a closed disclosure that operators can expand when needed.

The current-identity contract will distinguish ambient identity-provider fallback, browser session
and API-token authentication. Device mutation requires a signed browser session even in development;
ambient development identity can only read. The local browser session enables device lifecycle
testing without changing infrastructure.

MCP instance management continues to require a directory-backed multi-factor or hardware-backed
human identity. Development identity and the local demo browser session remain read-only for MCP
creation, upgrade review and retirement. The UI explains this boundary instead of presenting a
generic inventory failure. The login route does not alter or bypass server authorization.

## Safety Boundary

The current-identity response gains credential-kind metadata and the device mutation dependency now
requires a browser session consistently. Existing exact-scope RBAC, MCP MFA, attributable human
identity, acknowledgements, idempotency, optimistic concurrency and required audit remain
authoritative. No hard delete, runtime activation, infrastructure mutation, target contact,
credential handling, policy mutation, key management or signing authority is added.

## Consequences

- Operators can find device and MCP lifecycle controls without knowing internal Atlas terminology.
- Development mode remains useful for inspection and browser-session-bound device lifecycle testing;
  MCP mutations remain enterprise-MFA-only.
- Detailed security evidence remains available without dominating the repeated inventory workflow.
- Existing lifecycle hashes and mutation contracts remain unchanged; current identity gains additive
  credential-kind metadata.

## Validation

- Health and Connector navigation, disclosure and enterprise-login transition component tests
- Existing device and MCP create/retire contract and authorization regressions
- Complete frontend and backend quality gates plus production build
- Live local-session desktop and mobile navigation, device add/retire checks and MCP MFA-boundary checks
