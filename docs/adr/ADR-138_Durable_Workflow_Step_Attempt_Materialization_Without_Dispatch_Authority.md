# ADR-138: Durable Workflow Step Attempt Materialization Without Dispatch Authority

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-14 |
| Owners | Workflow Platform, Security Architecture, Operations Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-025, ATLAS-032, ADR-134, ADR-135, ADR-136, ADR-137 |

## Context

Atlas can durably materialize one immutable workflow run and its ordered `not_started` step runs
under an exact fenced orchestration lease. Before any queue or dispatch mechanism exists, the
engine needs a durable identity for one execution attempt. Creating an attempt must not imply that
a worker was dispatched, a step started, or an external capability ran.

## Decision

The exact active orchestration-lease holder authenticated with the dedicated
`audience.workflow-worker` workload credential may idempotently materialize attempt number one for
one exact eligible step run. In this slice, eligibility means that the step is `not_started`, no
attempt already exists, and every declared dependency is completed. Because completed step states
do not yet exist, only root steps with no dependencies are eligible.

The attempt is bound to the exact run and run digest, step-run and step-run digest, plan and plan
digest, definition version and digest, scope, storage target, lease identifier and digest, fencing
token, workload subject, attempt number and creation time. Its only state is `created`. Canonical
digest coverage includes all of those fields and an all-false authority contract.

The transaction locks and revalidates the plan, current lease, run and step run, then persists the
attempt and immutable idempotency claim atomically. It rejects stale or changed plans, leases,
fencing tokens, runs, step runs and idempotent requests; cancelled plans; expired or released
leases; non-root or otherwise ineligible steps; and competing identities.

Attempt materialization does not change run or step-run state, enqueue a message, dispatch a worker,
invoke a connector or model, create an approval, deliver a signal, schedule a retry or timer, mutate
ITSM, execute a runbook or change infrastructure. Every authority field remains structurally false.

Humans may inspect attempt evidence through the existing workflow read permission and browser
session. The UI exposes no attempt creation or execution control and requires no additional login or
MFA ceremony.

## Consequences

- Atlas has a durable attempt identity before any dispatch semantics or side effects exist.
- Future queue records can bind to an exact attempt and fencing lineage without inventing identity
  at delivery time.
- Only dependency-free root steps are eligible until completed step transitions are implemented.
- Queue delivery, dispatch, running states, results, retries, timers, signals and all external
  execution remain deferred.

## Validation

- Domain and application tests cover exact attempt identity, eligibility, idempotent replay,
  plan/run/step/lease fencing and all-false authority.
- PostgreSQL tests cover one-transaction attempt and claim persistence under locked source rows.
- API and UI tests cover workload-only mutation and human read-only presentation.
- Full quality gates, live validation, exact PR CI and independent main CI pass before delivery.
