# ADR-103: Connector Upgrade Plan Contract

- Status: Accepted
- Date: 2026-08-12
- Owners: MCP Platform Architecture, Infrastructure Operations, Security Architecture
- Governing documents: ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-020,
  ATLAS-021, ATLAS-023, ATLAS-024, ATLAS-031, ATLAS-032, ATLAS-050, ATLAS-052, ATLAS-055,
  ATLAS-056, ADR-100, ADR-102

## Context

Connector upgrade readiness identifies newer governed packages and declaration differences, but it
does not describe the ordered work, prerequisites, interruption assumptions, validation, stop
conditions or rollback path required before a human can assess a change. Reusing the Atlas
platform-upgrade plan would incorrectly bind connector lifecycle to bootstrap releases, database
backup evidence and platform service topology.

## Decision

Atlas will generate a deterministic connector-specific upgrade plan for one exact readiness
candidate. The plan binds the current instance version, current and candidate installation
receipts, readiness digest, candidate digest and current target-binding digest when present.

The plan contains:

- human approval and policy prerequisites;
- seven ordered approval, baseline, quiescence, package-binding, configuration, verification and
  rollback-gate steps;
- post-change validation checks;
- stop conditions;
- rollback steps and rollback window;
- explicit blockers and unknowns; and
- interruption estimates only when they are supported by evidence.

## Impact Boundary

An unconfigured connector has no target, runtime or service authority, so its interruption range is
deterministically zero. A target-configured connector cannot receive a synthetic downtime or
service-impact estimate. Its plan is blocked with `connector.upgrade.impact-evidence-required`
until a future governed impact assessment establishes current service mapping, active sessions and
an approved maintenance window.

Candidate publisher or SDK blockers from readiness remain blockers in the plan. Source or target
drift during planning fails closed.

## API Contract

`GET /api/v1/connectors/instances/{record_id}/upgrade-plans/{candidate_receipt_id}` uses existing
scoped instance-read authorization. It is no-store and audit recorded. The response omits target
endpoints, configuration values, secrets, credentials, artifact custody, fingerprints and
idempotency metadata.

Plan generation does not persist or mutate lifecycle state. Repeating the same request against the
same evidence produces the same plan identity and digest.

## Safety Boundary

Every plan requires human approval and is decision support only. It cannot rebind a package,
migrate configuration, quiesce a session, contact a target, restore data, grant runtime trust,
authorize execution or mutate infrastructure. The ordered steps describe future governed work;
they are not executable commands.

## Presentation

Each upgrade candidate exposes Review plan. The existing update modal presents plan state,
interruption evidence, rollback window, prerequisites, ordered steps, stop conditions, rollback,
post-validation, blockers and unknowns. No install, apply, execute or approval mutation is exposed.

## Consequences

- Human reviewers receive an evidence-bound change outline instead of a package diff alone.
- Unknown impact remains visible and blocks configured-target planning rather than being guessed.
- Immutable proposal creation, impact enrichment, approval and actual upgrade/rollback execution
  remain separate future workflows.

## Verification

- Backend tests cover deterministic planning, candidate binding, configured-target blocking,
  no-store responses, audit evidence and absence of execution authority or sensitive fields.
- Component tests cover plan discovery, ordered evidence and absence of execution actions.
- Full quality gates, production build and live responsive checks pass.
