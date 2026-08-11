# ADR-102: Connector Upgrade Readiness Contract

- Status: Accepted
- Date: 2026-08-11
- Owners: MCP Platform Architecture, Infrastructure Operations, Security Architecture
- Governing documents: ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-020,
  ATLAS-021, ATLAS-031, ATLAS-032, ATLAS-050, ATLAS-052, ATLAS-055, ATLAS-056, ADR-100

## Context

Atlas can install governed connector packages and create or retire disabled connector instances,
but an operator cannot determine whether a newer installed package applies to an existing MCP.
FR-002 requires independently versioned MCP upgrade and rollback. Direct upgrade execution at
this stage would bypass policy review, configuration migration, runtime revocation and rollback
governance.

## Decision

Atlas will introduce a read-only upgrade-readiness contract. For one active connector instance it
resolves the exact current installation receipt, registration and manifest, discovers newer
installed receipts for the same connector and compares their governed declarations.

The result reports semantic upgrade class, risk, capability and permission changes, target and
network destination changes, configuration and secret-reference deltas, policy and migration
requirements, blockers and the exact current receipt retained as the rollback anchor.

Readiness is decision support only. It cannot install a package, change an instance binding,
configure a target, resolve a credential, grant runtime trust, invoke a capability or mutate
infrastructure.

## API Contract

`GET /api/v1/connectors/instances/{record_id}/upgrade-readiness` requires the existing scoped
connector-instance read permission. The response is no-store, audit recorded and contains only
governance metadata. It omits artifact custody, source material, target endpoints, secret values,
credential references, fingerprints and idempotency metadata.

Current and candidate package lineage must agree exactly across receipt, registration, package
digest, manifest digest, connector, release, publisher and SDK declarations. Missing, retired,
cross-scope or inconsistent records fail closed. Candidates are sorted by semantic version and
only strictly newer releases are returned.

## Risk Classification

- Patch candidates are low risk unless declaration changes raise the classification.
- Minor candidates are at least medium risk.
- Major candidates are at least high risk.
- Publisher or SDK changes block eligibility and raise critical risk.
- Removed capabilities, changed permissions, added network destinations, target changes,
  configuration schema growth and new secret references raise review requirements.

Risk is an explainable conservative classification, not approval or execution authority.

## Presentation

Each active MCP row exposes a distinct Review update action. The modal shows the current governed
release, all newer installed candidates, declaration differences, risk, policy and configuration
migration requirements, blockers and rollback anchor. When no newer package exists, it directs
the operator to complete Builder assurance and installation.

The modal exposes only Close review. It contains no install, apply, execute or infrastructure
action.

## Consequences

- Operators can see whether an update is available and why it is risky without changing state.
- Upgrade planning remains traceable to immutable package evidence and an exact rollback anchor.
- Actual package rebinding, configuration migration, runtime transition, approval and rollback
  execution remain future ordered workflows.

## Verification

- Service and API tests cover exact lineage comparison, candidate discovery, scope isolation,
  no-store responses, audit evidence and absence of mutation authority or sensitive fields.
- Component tests cover visible review controls, candidate evidence, empty/error states and the
  absence of update execution commands.
- Full backend and frontend quality gates, production build and live responsive checks pass.
