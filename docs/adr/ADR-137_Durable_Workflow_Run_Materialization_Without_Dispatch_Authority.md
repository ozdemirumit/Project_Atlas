# ADR-137: Durable Workflow Run Materialization Without Dispatch Authority

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-14 |
| Owners | Workflow Platform, Security Architecture, Operations Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-025, ATLAS-032, ADR-134, ADR-135, ADR-136 |

## Context

Atlas has immutable workflow definitions, durable non-executable plans, plan cancellation and a
fenced orchestration lease. The next durable boundary must represent one execution instance and its
logical steps before any queue, attempt or worker dispatch authority exists. Moving a run or step to
`running`, or creating an attempt, would falsely imply that operational work began.

## Decision

An exact active orchestration-lease holder authenticated with the dedicated
`audience.workflow-worker` workload credential may idempotently materialize one immutable workflow
run for one exact `planned` plan digest. Materialization also creates the definition's ordered
logical step-run records.

The workflow run is bound to the exact plan, definition version and digest, scope, storage target,
lease identifier and digest, fencing token, workload subject and creation time. Its only state in
this slice is `created`. Every step run is bound to the exact run and code-owned step definition;
its only state is `not_started`. Canonical digests cover both the run and every step-run contract.

The transaction revalidates the source plan and active unexpired lease under lock, persists the
run, step runs and immutable materialization idempotency claim atomically, and rejects stale plan
digests, cancelled plans, released or expired leases, stale fencing tokens, competing identities,
wrong targets and changed idempotent requests.

Materialization does not alter the plan, start a step, create an attempt or queue message, dispatch
a worker, invoke a connector or model, create an approval, mutate ITSM, execute a runbook or change
infrastructure. The run and step-run contracts structurally grant none of those authorities.

Humans may inspect the materialized run through the existing workflow read permission and browser
session. The UI exposes no materialization or execution control and does not impose an additional
authorized-browser or MFA requirement.

## Consequences

- Atlas can persist and explain the exact run/step graph before dispatch semantics exist.
- Future attempt and queue slices have a durable parent contract and fencing lineage.
- A materialized run remains evidence of orchestration intent only; lease expiry does not turn it
  into execution authority.
- Queue delivery, attempts, running states, retries, timers, signals and all external execution
  remain deferred.

## Validation

- Domain and application tests cover exact definition expansion, immutable digests, idempotent
  replay, lease/plan fencing and all-false authority.
- PostgreSQL tests cover one-transaction run, step-run and claim persistence under locked plan and
  lease validation.
- API and UI tests cover workload-only mutation and human read-only presentation.
- Full quality gates, live validation, exact PR CI and independent main CI pass before delivery.
