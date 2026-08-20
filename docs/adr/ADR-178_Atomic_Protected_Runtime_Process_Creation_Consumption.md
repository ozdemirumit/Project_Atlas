# ADR-178: Atomic Protected Runtime Process-Creation Consumption

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-20 |
| Owners | Workflow Architecture, Security Architecture, Deployment Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-160 through ADR-177 |

## Context

ADR-177 issues one exact protected consumer workload a non-bearer process-creation authorization
lease valid for no more than one second. The lease authorizes submission of one future request
only. It is not process-creation, scheduling, resume, dispatch or execution authority and contains
no process primitive, runtime locator, command, executable, argument, environment or protected
material.

Atlas needs one explicit point of no return that consumes the exact lease and records one durable
process-creation attempt before invoking an approved protected-boundary creator. Retrying through
HTTP, workflow recovery, scheduler, outbox or DLQ paths after an ambiguous result could otherwise
create more than one process. Consuming the lease without creating the attempt in the same
transaction would also leave authority spent without durable evidence of the intended operation.

The primitive must preserve Atlas's immutable governance rule: AI is advisory-only and cannot
perform infrastructure operations. This decision therefore permits only creation of one sealed,
suspended process inside the already-started protected runtime. It does not permit the process to
be scheduled, resumed, dispatched or executed.

## Decision

Atlas will atomically append one immutable
`WorkflowProtectedRuntimeProcessCreationConsumptionClaim` and one immutable
`WorkflowProtectedRuntimeProcessCreationAttempt` in a single PostgreSQL transaction. The commit
irreversibly consumes the exact ADR-177 lease and records one durable creation attempt. Only after
that transaction commits may the request-owning service call one approved protected-boundary
creator, at most once.

A timely verified minimized receipt may append exactly one immutable
`WorkflowProtectedRuntimeProcessCreationResult` in one of these terminal states:

- `process_created_suspended_in_protected_boundary`;
- `process_creation_rejected_without_creation`;
- `process_creation_failed_without_creation`; or
- `process_creation_outcome_uncertain`.

There is no automatic retry. The protocol proves one durable attempt and at most one Atlas creator
invocation. It does not infer that a process was created merely because the attempt committed.

### Exact Caller And Request

Only the authenticated protected consumer workload subject and audience bound through the
canonical ADR-160 through ADR-177 lineage may POST. Human sessions, personal access tokens, AI
agents, MCP tools, connectors, runtime identities, generic workers and recovery workers fail closed
before protected-state I/O.

The caller supplies only:

- the ADR-177 authorization lease ID;
- code-owned process-creation consumption policy ID and version;
- a tenant-scoped idempotency key;
- explicit irreversible-consumption acknowledgement; and
- explicit acknowledgement that an uncertain outcome is not retried or restored.

The caller cannot supply lease or lineage digests, process profile, command, executable, arguments,
environment, working directory, user or group identity, runtime or process locator, handle,
instruction, nonce, deadline, receipt, outcome, endpoint, credential, prompt, model, provider,
transport or authority values. Atlas derives every operational commitment from trusted state and
code-owned policy.

### Code-Owned Suspended Process Primitive

The process primitive is one sealed, policy-owned process image and manifest already associated
with the protected consumer contract. The creator may only instantiate that process in a suspended,
non-runnable state inside the exact existing protected runtime.

The signed primitive digest transitively commits both the code-owned process-image digest and the
code-owned process-manifest digest.

The primitive guarantees that:

- the exact runtime, destination fence and protected slot generation remain current;
- the process image, manifest and creation profile match code-owned digest commitments;
- no caller-controlled command, argument, environment, working directory or identity is accepted;
- no inherited descriptor, socket, endpoint, credential or reusable bearer material is introduced;
- the created process is suspended and cannot run before a separately approved future protocol;
- one lineage can produce at most one process-creation attempt and at most one created process; and
- changed invocation, ABA lineage, generic spawn, shell execution or scheduling fails closed.

The primitive performs no resume, dispatch, execution, model invocation, network access, connector
or MCP call, provider operation, publication, delivery, workflow transition or infrastructure
mutation.

### Code-Owned Policy

The code-owned policy binds the exact ADR-177 lease and source lineage, protected consumer
contract, suspended-process image and manifest digests, creation profile, approved creator contract
and identity, instruction signer and receipt verifier. It requires:

- durable exact replay classification as the first repository operation;
- authoritative PostgreSQL time and complete lineage validation under lock;
- one active, unexpired and unconsumed ADR-177 lease;
- a code-owned invocation margin before lease expiry;
- atomic claim and attempt commit before creator I/O;
- no external I/O while the transaction is open;
- one signed metadata-only instruction and at most one creator call;
- exact protected-side instruction deduplication and compare-and-swap;
- timely signed receipts for known outcomes;
- permanent uncertainty for every other post-commit outcome; and
- no retry, resume, cleanup, rollback, reauthorization or recovery invocation.

Configuration and caller input cannot weaken these requirements.

### State Derivation

```text
authorized_unconsumed
  -> authorization_expired                         DB time reaches lease deadline
  -> process_creation_attempt_pending              atomic claim + attempt commit

process_creation_attempt_pending
  -> process_created_suspended_in_protected_boundary
  -> process_creation_rejected_without_creation
  -> process_creation_failed_without_creation
  -> process_creation_outcome_uncertain
```

State is derived from append-only evidence and authoritative database time. A pending attempt past
its invocation deadline projects as uncertainty. One terminal result is permanent and cannot be
replaced. A no-I/O finalizer may append the same uncertain result after the deadline but cannot call
the creator.

### Replay, Ambiguity And Point Of No Return

The service performs durable replay lookup as its first repository operation.

- Exact terminal replay returns the existing minimized result without creator I/O.
- Exact attempt replay returns pending or authoritative uncertainty and never calls the creator.
- The same idempotency key with changed request, identity, scope or lineage fails closed.
- A competing consumer of the lease fails closed; only one claim and attempt can commit.
- Commit failure prevents creator invocation.
- Commit ambiguity is treated as consumed or potentially consumed and never permits invocation.
- Cancellation before commit consumes nothing; cancellation at or after commit creates no retry.
- Timeout, crash, response loss, malformed or late receipt, conflicting evidence and unresolved
  result-write ambiguity produce permanent `process_creation_outcome_uncertain`.

The atomic claim-and-attempt commit is the Atlas point of no return. Recovery may read durable
evidence but cannot create, retry, infer, resume or remove a process.

### PostgreSQL Atomicity And Lineage

PostgreSQL is the sole production authority. In canonical lock order the repository revalidates:

1. the complete immutable ADR-160 through ADR-177 lineage;
2. the exact process-creation authorization claim and lease;
3. the current destination generation and fencing token;
4. the exact protected slot generation;
5. the terminal started runtime and ready result, read-only;
6. pending publication and orchestration fences relevant to the lineage; and
7. competing process-creation consumption claims, attempts and results.

At authoritative database time the lease must remain active with the code-owned invocation margin.
The repository then atomically consumes the lease and appends the claim and attempt. Append-only
triggers, exact composite foreign keys and unique constraints reject update, delete, truncate,
orphan evidence, cross-lineage binding, changed replay and more than one consumer or attempt.
Production never falls back to in-memory authority.

### Signed Instruction And Receipt

The persisted instruction and signed envelope bind the exact lease, claim, attempt, request nonce,
complete lineage, destination fence, slot generation, process image and manifest digests, creation
profile, creator identity and invocation deadline. They contain no runtime/process locator, command,
argument, environment, endpoint, credential, secret or reusable authority.

The creator independently verifies the instruction and returns a signed metadata-only receipt. A
known-success receipt proves only that one process was created in a sealed suspended state and that
no scheduling, resume, dispatch or execution occurred. Known-without-creation receipts prove the
corresponding rejection or failure and no residual process. Every unverifiable, late, conflicting
or incomplete outcome is uncertain.

An uncertain outcome records process-created, process-sealed and process-suspended as unknown. It
must never present those facts as false because the protected-side creation may have occurred.

No receipt or result exposes a process locator, handle, command, executable, argument, environment,
credential, endpoint or protected material. Success is an outcome fact, never bearer authority.

### Security And Governance

All authority declarations in the claim, attempt, instruction, receipt and result remain false.
`process_created_suspended_in_protected_boundary=true` is historical outcome evidence only. It
does not grant scheduling, resume, dispatch, execution, access or mutation authority.

AI remains advisory-only. No AI agent may request, consume or exercise the lease, call the creator,
or receive process material. The command is not exposed as an AI, MCP or connector tool.

Active Directory remains authentication-only. This decision adds no Active Directory management
route, capability, service or MCP. Normal username/password browser sessions require neither MFA
nor a second authorized browser session.

### API And User Interface

The consumption POST is workload-only, strict, minimized, non-oracular and
`Cache-Control: no-store`. Production returns generic fail-closed conflict or unavailable responses
without revealing protected source existence or process material.

Normal authorized users may GET a minimized read-only projection through the existing username and
password browser session. The projection contains safe identity, state, attempt/result timestamps,
policy references and integrity digests only.

The UI provides no consume, create, retry, resume, schedule, dispatch, execute, stop, cleanup,
download, connect or mutate control and never displays protected material.

### Events, Audit And Recovery

Audit distinguishes exact replay, lease consumption, attempt commit, observed creator invocation,
terminal result and uncertainty using minimized identity, state, time and integrity references.
Events may be appended only after authoritative commits. Event publication or audit-export failure
cannot roll back, retry, alter or infer the protected-side outcome.

Recovery is evidence-only. It may project durable state and append a deterministic no-I/O uncertain
result after deadline, but it cannot invoke the creator or perform cleanup.

## Consequences

- Process-creation authorization and process creation remain separate trust boundaries.
- The only permitted primitive creates one sealed suspended process, never a generic or runnable
  process.
- Atomic claim and attempt persistence prevents a consumed lease without durable attempt evidence.
- At-most-once creator invocation prevents retry-driven duplicate process creation.
- Ambiguous post-commit outcomes remain permanently uncertain and may require external operational
  investigation outside Atlas.
- No process can run until a separately approved authorization and consumption protocol exists.

## Deferred Scope

- Process scheduling, resume, dispatch, execution, supervision, stop and cleanup
- Prompt construction, model inference and model input
- Runtime or process locator, context, handle or protected material reveal
- Commands, executables, arguments, environments and working directories
- Network, endpoint, credential, connector, MCP, broker or provider activity
- Publication, delivery, acknowledgement and workflow execution
- Infrastructure mutation and remediation
- Lease renewal, replacement, transfer, reissue or automatic recovery
- Human- or AI-initiated process controls
- Active Directory management or an Active Directory MCP

## Validation

- Domain tests prove code-owned primitive commitments, terminal-state invariants, zero authority and
  rejection of prohibited material.
- Service tests prove replay-first ordering, atomic claim/attempt before creator I/O, exact replay,
  no retry, cancellation behavior and permanent uncertainty.
- Creator tests prove signed instruction validation, exact deduplication/CAS, suspended success,
  known-without-creation outcomes and fail-closed changed invocation.
- PostgreSQL tests prove authoritative time, canonical lock order, full lineage revalidation,
  expiry-race closure, one concurrent winner, append-only enforcement and guarded downgrade.
- API and frontend tests prove workload-only POST, password-session read-only GET, minimized
  `no-store` schemas, strict parsing and zero operational controls.
- Focused local checks cover changed modules. Full backend/frontend regression and PostgreSQL
  integration run once in pull-request CI before merge.
