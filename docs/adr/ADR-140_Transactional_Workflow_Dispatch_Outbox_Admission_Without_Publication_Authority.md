# ADR-140: Transactional Workflow Dispatch Outbox Admission Without Publication Authority

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-14 |
| Owners | Workflow Platform, Security Architecture, Operations Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-025, ATLAS-032, ADR-134, ADR-135, ADR-136, ADR-137, ADR-138, ADR-139 |

## Context

Atlas can stage an immutable dispatch intent for an exact `created` attempt under a fenced
orchestration lease. A future publisher needs durable input that cannot be lost between the local
intent commit and broker publication. The event-backbone technology is intentionally undecided, so
this boundary cannot depend on a vendor, transport or wire format.

## Decision

Dispatch-intent staging atomically persists one immutable, provider-neutral workflow outbox entry
with the staged intent and its idempotency claim. The entry binds the exact plan, run, step run,
attempt, dispatch intent, current lease digest, fencing token, workload subject, scope and storage
target. Its only state in this slice is `pending_publication`.

The transaction locks and revalidates the plan, current lease, run, step run and attempt before any
record is written. Exact idempotent replay returns the same intent and outbox evidence. Stale,
expired, released, cancelled, changed, mismatched or competing requests fail closed. Existing
staged intents are upgraded deterministically to one matching pending-publication entry so a schema
upgrade cannot leave an untracked handoff gap.

The entry contains no broker selection, endpoint, queue, topic, partition, routing key, serialized
payload, publication attempt, delivery receipt or worker reservation. It does not publish or deliver
a message, change plan/run/step/attempt/intent state, dispatch a worker, invoke a connector or model,
create an approval, mutate ITSM, execute a runbook or change infrastructure. Publication, delivery,
dispatch and execution authority remain structurally false.

Humans may inspect outbox evidence through the existing workflow read permission and normal
username/password browser session. The UI exposes no admission, publication, delivery, dispatch or
execution control and requires no additional login or MFA ceremony.

## Consequences

- New staged intents cannot commit without their durable future-publication input.
- A pending-publication entry means only that database evidence exists; it does not mean a broker
  accepted, delivered or dispatched anything.
- The future publisher can bind publication attempts and receipts to one exact immutable entry
  without rebuilding identity or authority from mutable state.
- Broker choice, wire schemas, publication leasing, delivery acknowledgement, worker dispatch,
  running states, results, retries, timers, signals and all external execution remain deferred.

## Validation

- Domain and application tests cover exact lineage, current fencing, atomic candidate construction,
  idempotent replay and all-false authority.
- PostgreSQL and migration tests cover one-transaction intent, outbox and claim persistence plus
  deterministic upgrade of pre-existing staged intents.
- API and UI tests cover workload-only staging and human read-only outbox presentation.
- Full quality gates, live validation, exact PR CI and independent main CI pass before delivery.
