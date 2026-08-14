# ADR-139: Durable Workflow Dispatch Intent Staging Without Publication Authority

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-14 |
| Owners | Workflow Platform, Security Architecture, Operations Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-025, ATLAS-032, ADR-134, ADR-135, ADR-136, ADR-137, ADR-138 |

## Context

Atlas can durably materialize a `created` attempt for an exact dependency-free root step under a
fenced orchestration lease. Before selecting or integrating a message broker, the engine needs an
immutable record of the exact attempt that a future delivery mechanism could consider. Recording
that intent must not publish a message, dispatch a worker or imply that work has started.

## Decision

The exact active orchestration-lease holder authenticated with the dedicated
`audience.workflow-worker` workload credential may idempotently stage one dispatch intent for one
exact `created` attempt. The bound plan must remain `planned`, the run must remain `created`, the
step run must remain `not_started`, and the current lease, fencing token, scope, target and worker
identity must all match.

The immutable intent is bound to the exact plan, run, step run, attempt, current lease, fencing
token, workload subject, scope and storage target. Its only state is `staged`. Canonical digest
coverage includes every binding and an all-false authority contract.

The transaction locks and revalidates the plan, current lease, run, step run and attempt, then
persists the staged intent and immutable idempotency claim atomically. It rejects stale, changed,
expired, released, cancelled, mismatched or competing requests without revealing unauthorized
state.

Staging does not create or select a queue, serialize a broker message, publish or deliver anything,
reserve a worker, change attempt/run/step state, invoke a connector or model, create an approval,
deliver a signal, schedule a retry or timer, mutate ITSM, execute a runbook or change
infrastructure. Every publication, delivery, dispatch and execution authority field remains
structurally false.

Humans may inspect staged intent evidence through the existing workflow read permission and normal
username/password browser session. The UI exposes no staging, publication, dispatch or execution
control and requires no additional login or MFA ceremony.

## Consequences

- Atlas records durable, fenced handoff intent before choosing a broker or delivery protocol.
- Future outbox and broker-delivery records can bind to one exact staged intent without inventing
  identity at publication time.
- A staged intent means only that immutable evidence exists; it does not mean work is queued,
  dispatched, running or authorized.
- Broker selection, outbox publication, delivery acknowledgement, worker dispatch, running states,
  results, retries, timers, signals and all external execution remain deferred.

## Validation

- Domain and application tests cover exact identity, idempotent replay, source-state and fencing
  checks, and all-false authority.
- PostgreSQL tests cover one-transaction intent and claim persistence under locked source rows.
- API and UI tests cover workload-only mutation and human read-only presentation.
- Full quality gates, live validation, exact PR CI and independent main CI pass before delivery.
