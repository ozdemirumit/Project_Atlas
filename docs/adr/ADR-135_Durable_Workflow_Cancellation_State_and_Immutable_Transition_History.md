# ADR-135: Durable Workflow Cancellation State and Immutable Transition History

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-13 |
| Owners | Workflow Platform, Security Architecture, Operations Architecture |
| Related | ATLAS-002 FR-014, ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-025, ATLAS-032, ADR-134 |

## Context

ADR-134 created durable, non-executable workflow plans that remain `planned`. Before Atlas adds
workers, queues or timers, it needs an authoritative and auditable way to withdraw intent. Deleting
a plan would erase evidence; treating cancellation as a UI flag would split state authority.

## Decision

Atlas will add one durable lifecycle transition: `planned -> cancelled`. An authorized human using
a CSRF-protected browser session may request cancellation for one exact visible plan and provide a
bounded normalized reason plus acknowledgement that cancellation does not undo external work.

The transition updates the plan and appends an immutable history record atomically in PostgreSQL.
It records the prior and new state, actor, exact scope and target, reason digest, correlation,
timestamp and canonical transition digest. Optimistic state checks reject races. An idempotency key
replays the exact prior outcome and conflicts when reused for different content.

Cancellation never deletes history, starts a step, dispatches a worker, invokes a connector,
creates an approval, mutates ITSM, executes a runbook or changes infrastructure. Every step remains
`not_started` and every authority flag remains false. A cancelled plan is terminal in this slice.

Production remains PostgreSQL-backed and fail closed. Explicit development mode may use the
labeled non-durable repository while preserving the same transition contract.

## Consequences

- Users can safely withdraw an unstarted plan without losing its evidence trail.
- The workflow module gains its first authoritative state transition and immutable history contract.
- Running-step cancellation, cancellation propagation, compensation and recovery remain deferred
  until worker and attempt state exist.

## Validation

- Domain and service tests cover valid transition, terminal replay, races, idempotency and audit.
- Persistence tests cover atomic state/history/idempotency mapping and canonical reconstruction.
- API and frontend tests cover browser session, exact scope, acknowledgement and history display.
- Full quality gates and live username/password validation pass before delivery.
