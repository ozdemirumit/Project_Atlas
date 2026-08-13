# ADR-136: Fenced Workflow Orchestration Lease Without Execution Authority

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-13 |
| Owners | Workflow Platform, Security Architecture, Operations Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-025, ATLAS-032, ADR-134, ADR-135 |

## Context

Atlas now has immutable workflow definitions, durable non-executable plans and authoritative plan
cancellation. A future worker must not begin orchestration until ownership can survive process
failure and reject stale or competing workers. Moving a plan or step to `running` before step-run
and attempt authority exists would falsely imply execution.

## Decision

Atlas will add a durable orchestration lease bound to one exact `planned` plan and its canonical
digest. A dedicated service identity authenticated with a workload credential for
`audience.workflow-worker` may acquire, heartbeat or release the lease. Browser sessions and API
tokens cannot perform worker lease mutations.

The lease records the plan, exact scope and target, workload subject, acquisition/heartbeat/expiry
times, monotonically increasing fencing token, lifecycle state and canonical digest. Acquisition is
idempotent for the same request, rejects a competing unexpired owner, and replaces an expired lease
with a higher fencing token. Heartbeat and release require the exact lease digest, worker subject,
plan digest and fencing token. Every mutation is durable, optimistic and audited.

This lease coordinates future orchestration ownership only. It does not change plan or step state,
dispatch a worker task, invoke a connector, create an approval, mutate ITSM, execute a runbook or
change infrastructure. If the source plan is cancelled or its digest changes, subsequent lease
operations fail closed and the stale lease grants no authority.

Humans may inspect lease status in the workflow UI but receive no lease-mutation control. Expired
leases are displayed as expired based on authoritative server time; no bearer token or credential
material is returned.

## Consequences

- Competing and stale future workers can be fenced before step execution exists.
- Workload identity authentication remains separate from human browser authentication and MFA is
  not fabricated as a lease prerequisite.
- Run materialization, step runs, attempts, queues, dispatch, retries and external execution remain
  deferred to later slices.

## Validation

- Domain and repository tests cover acquire, replay, contention, expiry takeover, heartbeat,
  release, stale fencing and plan-digest invalidation.
- API tests cover dedicated workload authentication and human read-only presentation.
- Full quality gates and live validation pass before delivery.
