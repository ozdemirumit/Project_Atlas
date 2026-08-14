# ADR-141: Fenced Workflow Outbox Publication Lease Without Publication Authority

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-14 |
| Owners | Workflow Platform, Security Architecture, Operations Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-025, ATLAS-032, ADR-136, ADR-137, ADR-138, ADR-139, ADR-140 |

## Context

Atlas now persists one immutable, provider-neutral `pending_publication` outbox entry in the same
transaction as each workflow dispatch intent. A future publisher must coordinate ownership of that
entry across concurrent processes and process failure before any broker-specific publication can be
introduced. Treating the existing orchestration lease as publisher ownership would couple two
independent workloads and would not provide a publication-specific fence.

## Decision

Atlas will add a durable publication lease bound to one exact pending workflow outbox entry and its
complete immutable lineage. A dedicated service identity authenticated with a workload credential
for `audience.workflow-outbox-publisher` may acquire, heartbeat or release the lease. Browser
sessions and ordinary API tokens cannot mutate publication leases.

The lease records the outbox entry and digest, dispatch intent, plan, run, step run, attempt, exact
scope and target, source orchestration lease and fence, publisher subject, acquisition, heartbeat
and expiry times, a monotonically increasing publication fencing token, lifecycle state and
canonical digest. Acquisition is idempotent for the same request, rejects a competing unexpired
publisher, and replaces an expired or released lease with a higher publication fence. Heartbeat and
release require the exact current publication lease digest, publisher subject and fence.

Every mutation locks and revalidates the planned plan, exact pending outbox entry and current active
source orchestration lease. Changed, cancelled, stale, expired, released, mismatched or competing
evidence fails closed. All mutations are durable, optimistic and audited.

This lease provides publication coordination only. It contains no broker selection, endpoint,
queue, topic, partition, routing key, wire payload, serialization, publication attempt, delivery
receipt or worker reservation. It does not publish or deliver a message, change workflow state,
dispatch a worker, invoke a connector or model, create an approval, mutate ITSM, execute a runbook
or change infrastructure. Publication, delivery, dispatch and execution authority remain
structurally false.

Humans may inspect publication-lease evidence through the existing workflow read permission and
normal username/password browser session. The UI exposes no lease mutation or operational action
and requires no additional login or MFA ceremony.

## Consequences

- Concurrent and stale publisher processes can be fenced before a transport is selected.
- A publication lease means only that one publisher owns a bounded coordination window; it does not
  mean that a message was serialized, sent, accepted, delivered or dispatched.
- Broker choice and credentials remain outside the domain contract and can be introduced later
  behind a provider adapter.
- Publication attempts, receipts, worker dispatch, running states, results, retries, timers,
  signals and all external execution remain deferred.

## Validation

- Domain and repository tests cover acquire, replay, contention, expiry/release takeover,
  heartbeat, release, stale fencing, source-lease invalidation and zero authority.
- PostgreSQL tests cover locking, complete lineage revalidation, atomic idempotency and monotonic
  publication fencing without a memory fallback.
- API and UI tests cover workload-only mutation and human read-only presentation.
- Full quality gates, live validation, exact PR CI and independent main CI pass before delivery.
