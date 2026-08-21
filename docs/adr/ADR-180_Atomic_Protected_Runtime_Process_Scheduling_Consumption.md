# ADR-180: Atomic Protected Runtime Process-Scheduling Consumption

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-21 |
| Owners | Workflow Architecture, Security Architecture, Deployment Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-160 through ADR-179 |

## Context

ADR-179 issues one exact protected consumer workload a single-use, non-bearer process-scheduling
authorization lease valid for no more than one second. The lease permits submission of one future
consumption request only. It is not evidence that scheduling occurred and grants no resume,
dispatch, execution, network, connector, MCP, provider or infrastructure authority.

Atlas needs one explicit scheduling point of no return. The exact lease must be consumed and one
durable scheduling attempt must exist before a trusted scheduler adapter is called. A retry after an
ambiguous adapter result could otherwise schedule the same process more than once. Consuming the
lease without atomically recording the attempt would also spend authority without durable evidence.

The platform's AI remains advisory-only. This protocol is available only to the exact authenticated
protected workload and a code-owned primitive. A successful result may prove only scheduler
registration of the existing sealed process while that process remains suspended and non-runnable.
It cannot resume, dispatch or execute the process.

## Decision

Atlas will atomically append one immutable
`WorkflowProtectedRuntimeProcessSchedulingConsumptionClaim` and one immutable
`WorkflowProtectedRuntimeProcessSchedulingAttempt` in a single PostgreSQL transaction. That commit
irreversibly consumes the exact ADR-179 lease and records one durable scheduling attempt. Only the
request-owning service may then call one approved protected scheduler adapter, at most once.

A timely verified metadata-only receipt may append exactly one immutable
`WorkflowProtectedRuntimeProcessSchedulingResult` in one terminal state:

- `process_scheduled_suspended_in_protected_boundary`;
- `process_scheduling_rejected_without_scheduling`;
- `process_scheduling_failed_without_scheduling`; or
- `process_scheduling_outcome_uncertain`.

There is no automatic retry. Attempt commit does not imply that scheduling occurred. A success
result is historical evidence and grants no follow-on authority.

### Exact Caller And Request

Only the authenticated protected consumer workload subject and audience bound through canonical
ADR-160 through ADR-179 lineage may POST. Humans, personal tokens, browser sessions, AI agents, MCP
tools, connectors, generic schedulers and recovery workers fail closed before protected-state I/O.

The caller supplies only:

- the ADR-179 authorization lease ID;
- code-owned scheduling-consumption policy ID and version;
- a tenant-scoped idempotency key;
- explicit irreversible-consumption acknowledgement; and
- explicit acknowledgement that uncertain outcomes are not retried or restored.

The caller cannot supply lineage digests, runtime or process locators, handles, commands,
executables, arguments, environments, working directories, queue names, priorities, affinity,
resource assignments, instructions, receipts, deadlines, endpoints, credentials, prompts, models,
providers or authority values.

### Code-Owned Suspended Scheduling Primitive

The scheduler primitive is bound to the exact ADR-178 process image, manifest, process-creation
result, runtime envelope, destination fence and protected slot generation. Required protected-side
references are resolved only inside the trusted adapter boundary and never enter API, audit, event,
log, UI or AI context.

The primitive guarantees that:

- the exact process is still created, sealed, suspended, non-runnable and unexecuted;
- the process has not already been scheduled, resumed or dispatched;
- process image, manifest, creation profile and scheduler profile match code-owned commitments;
- no caller-controlled queue, priority, affinity, resource or process material is accepted;
- successful scheduling preserves suspended and non-runnable state;
- exact protected-side instruction deduplication prevents changed or duplicate scheduling; and
- no resume, dispatch, execution, supervision, stop, cleanup or infrastructure mutation occurs.

The adapter performs no model invocation, network access outside the protected local scheduler
boundary, connector or MCP call, provider operation, publication, delivery or workflow execution.

### Code-Owned Policy

The immutable policy binds the exact ADR-179 lease and source lineage, consumer contract, process
image and manifest commitments, scheduler profile, scheduler adapter identity, instruction signer
and receipt verifier. It requires:

- durable replay classification before current-state validation or adapter I/O;
- authoritative PostgreSQL time and complete lineage validation under lock;
- one active, unexpired and unconsumed ADR-179 lease;
- a code-owned invocation margin before lease expiry;
- atomic claim and attempt commit before adapter I/O;
- no external I/O while the transaction is open;
- one signed metadata-only instruction and at most one adapter call;
- exact instruction deduplication and compare-and-swap at the protected boundary;
- timely signed receipts for known outcomes;
- permanent uncertainty for every other post-commit outcome; and
- no retry, resume, dispatch, execution, rollback, reauthorization or recovery invocation.

Configuration and caller input cannot weaken these requirements.

### State Derivation

```text
authorized_unconsumed
  -> authorization_expired
  -> process_scheduling_attempt_pending

process_scheduling_attempt_pending
  -> process_scheduled_suspended_in_protected_boundary
  -> process_scheduling_rejected_without_scheduling
  -> process_scheduling_failed_without_scheduling
  -> process_scheduling_outcome_uncertain
```

State is derived only from append-only evidence and authoritative database time. A pending attempt
past its invocation deadline projects as uncertainty. One terminal result is permanent. A no-I/O
finalizer may append the same uncertain result after deadline but cannot call the scheduler adapter.

### Replay, Ambiguity And Point Of No Return

- Exact terminal replay returns the existing minimized result without adapter I/O.
- Exact attempt replay returns pending or authoritative uncertainty without adapter I/O.
- Changed idempotency, identity, scope, lease or lineage fails closed.
- Competing consumption of one lease permits only one claim and one attempt commit.
- Commit failure prevents adapter invocation.
- Commit ambiguity is treated as consumed or potentially consumed and prevents invocation.
- Cancellation before commit consumes nothing; cancellation at or after commit creates no retry.
- Timeout, crash, response loss, late or malformed receipt, conflicting evidence and result-write
  ambiguity produce permanent `process_scheduling_outcome_uncertain`.

The atomic claim-and-attempt commit is the point of no return. Recovery is evidence-only.

### PostgreSQL Atomicity And Lineage

PostgreSQL is the sole production authority. In canonical lock order the repository revalidates:

1. complete immutable ADR-160 through ADR-179 lineage;
2. exact scheduling authorization claim and lease;
3. current process-creation result and scheduling-state commitments;
4. destination generation, fencing token, runtime envelope and protected slot generation;
5. absence of scheduling, resume, dispatch and execution evidence;
6. pending publication and orchestration fences relevant to the lineage; and
7. competing scheduling-consumption claims, attempts and results.

The repository uses authoritative database time, consumes the lease and appends claim plus attempt
in one transaction. Append-only triggers, exact composite foreign keys and unique constraints reject
orphan evidence, cross-lineage binding, update, delete, truncate and more than one consumer.
Production never falls back to in-memory authority.

### Signed Instruction And Receipt

The signed instruction binds the exact lease, claim, attempt, nonce, complete lineage, destination
fence, slot generation, runtime envelope, process image and manifest digests, scheduler profile,
adapter identity and invocation deadline. It contains no runtime/process locator, queue, priority,
affinity, resource, command, credential, endpoint, secret or reusable authority.

The protected adapter independently verifies the instruction and returns a signed metadata-only
receipt. Known success proves only scheduler registration while the process remained suspended and
non-runnable. Known rejection or failure proves no scheduling. Every unverifiable, late, conflicting
or incomplete outcome is uncertain. No receipt exposes protected material.

### Security And Governance

All authority declarations in claim, attempt, instruction, receipt and result remain false.
Scheduling success is historical evidence only. It grants no resume, dispatch, execution, access or
mutation authority.

AI remains advisory-only and cannot request or consume the lease, call the adapter or receive
protected process material. The operation is not exposed as an AI, MCP or connector tool. Active
Directory remains authentication-only and no Active Directory management capability or MCP is
introduced.

### API And User Interface

The POST is workload-only, strict, minimized, non-oracular and `Cache-Control: no-store`. Normal
authorized username/password sessions may GET only minimized read-only identity, state, timestamps,
policy references and integrity digests without MFA or another browser session.

The UI provides no consume, schedule, retry, resume, dispatch, execute, stop, cleanup, connect or
mutate control and never displays protected material.

### Events, Audit And Recovery

Audit distinguishes exact replay, lease consumption, attempt commit, observed adapter invocation,
terminal result and uncertainty using minimized metadata. Events may be appended only after
authoritative commits. Audit or event failure cannot roll back, retry or alter the operation.

Recovery may project durable evidence and append a deterministic no-I/O uncertain result after the
deadline. It cannot invoke the adapter, schedule, resume, dispatch, execute or clean up a process.

## Consequences

- Authorization and scheduling consumption remain separate trust boundaries.
- Atomic claim and attempt persistence prevents spent authority without durable attempt evidence.
- At-most-once adapter invocation and permanent uncertainty prevent retry-driven duplicate effects.
- A successful result still leaves the process suspended and non-runnable.
- No process can resume or execute until separately approved future protocols exist.

## Deferred Scope

- Process resume, dispatch, execution, supervision, stop and cleanup
- Generic queue placement, priority, affinity and caller-selected resource assignment
- Runtime/process locator, handle, context or protected material reveal
- Commands, executables, arguments, environments and working directories
- Prompt construction, model inference and model input
- Network, endpoint, credential, connector, MCP, broker or provider activity
- Publication, delivery, acknowledgement and workflow execution
- Infrastructure mutation and remediation
- Lease renewal, replacement, transfer, reissue or automatic recovery
- Human- or AI-initiated scheduling controls
- Active Directory management or an Active Directory MCP

## Validation

- Domain tests prove terminal-state invariants, suspended scheduling commitments and zero authority.
- Service tests prove replay-first ordering, atomic claim/attempt before adapter I/O, no retry,
  cancellation behavior and permanent uncertainty.
- Adapter tests prove signed instruction validation, exact deduplication, suspended success and
  fail-closed changed invocation.
- PostgreSQL tests prove database time, lock order, complete lineage, expiry-race closure, one
  concurrent winner, append-only evidence and guarded downgrade.
- API and frontend tests prove workload-only POST, password-session read-only GET, minimized
  `no-store` schemas, strict parsing and no operational controls.
- Focused local checks cover changed modules. Full backend/frontend regression and PostgreSQL
  integration run once in pull-request CI.
