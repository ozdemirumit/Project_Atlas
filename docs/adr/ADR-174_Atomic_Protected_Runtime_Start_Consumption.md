# ADR-174: Atomic Protected Runtime-Start Consumption And Single Start Attempt

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-17 |
| Owners | Workflow Architecture, Security Architecture, Deployment Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-160 through ADR-173 |

## Context

ADR-173 issues one exact protected consumer workload a non-bearer runtime-start authorization lease
valid for no more than one second. The lease permits submission of one future request only. It is
not direct runtime-start authority, and the protected runtime envelope remains inactive and
unstarted.

Atlas now needs one explicit point of no return that consumes the lease and starts, at most once,
the exact pre-existing protected runtime envelope without exposing its locator or material to an
ordinary Atlas process. A separate consumption-only phase would create a state in which authority
was burned but no protected attempt existed. Reusing event delivery or generic workflow retry for
the starter call would instead permit duplicate starts after worker recovery or DLQ replay.

This decision therefore binds lease consumption and creation of one durable started-attempt record
in the same PostgreSQL transaction. The trusted protected starter is called directly only after
that transaction commits. A started attempt is never resumed, retried or transferred to another
worker. Missing or ambiguous post-commit evidence becomes permanent uncertainty.

## Decision

Atlas will append one immutable `WorkflowProtectedRuntimeStartConsumptionClaim` and one immutable
`WorkflowProtectedRuntimeStartAttempt`, while atomically transitioning the guarded coordination
head from `authorized_unconsumed` to `start_attempt_pending`. This commit is the irreversible point
of no return and occurs before one approved protected starter may be invoked.

A timely verified minimized receipt may then produce exactly one immutable
`WorkflowProtectedRuntimeStartResult` in one of these terminal states:

- `runtime_started_in_protected_boundary`;
- `runtime_start_failed_without_start`; or
- `runtime_start_outcome_uncertain`.

The protocol guarantees one durable attempt and at most one Atlas starter invocation. It does not
claim that a starter call occurred merely because the attempt was committed. A crash between the
commit and the call remains uncertain and cannot be recovered by invoking the starter again.

### Exact Caller And Request

Only the authenticated workload subject
`service.workflow-protected-transport-target-context-capsule-consumer` for audience
`audience.workflow-protected-transport-target-context-capsule-consumer` may call the command. The
identity must equal the immutable consumer binding across canonical ADR-160 through ADR-173
lineage. Human sessions, personal tokens, AI agents, MCP tools, connectors, runtime identities,
generic workers and recovery workers fail closed before protected-state I/O.

The caller supplies only:

- the ADR-173 authorization lease ID;
- code-owned runtime-start policy ID and version;
- tenant-scoped idempotency key;
- explicit irreversible-consumption acknowledgement; and
- explicit acknowledgement that uncertain outcomes are not retried or restored.

The caller cannot supply lease digest, runtime envelope, commitment, generation, destination,
fence, slot, protected operation reference, start attempt, nonce, instruction, starter, deadline,
receipt, outcome, authority, endpoint, credential, process, model or provider values. Source IDs
and digests are routing and integrity metadata and are never bearer authority.

### Code-Owned Policy

The policy is `policy.workflow-protected-runtime-start` version `1.0`, with purpose
`purpose.workflow-protected-runtime-start`. It binds the exact consumer contract, ADR-173 source
policy, runtime-start profile, starter contract, instruction signer and receipt verifier.

The immutable policy requires:

- durable exact replay classification before starter I/O;
- authoritative PostgreSQL time and complete lineage locks;
- an active, unexpired and unconsumed ADR-173 lease;
- a code-owned minimum invocation margin before lease expiry;
- atomic claim, started-attempt and coordination-head commit;
- no external I/O while the claim transaction is open;
- one signed metadata-only instruction and at most one starter invocation;
- exact protected-side attempt/instruction deduplication and compare-and-swap;
- timely signed receipts for known success or known failure;
- permanent uncertainty for every other post-commit outcome;
- no automatic retry, resume, cleanup, rollback, reauthorization or recovery; and
- no reusable authority in claim, attempt, receipt or result.

Mutable configuration and caller input cannot weaken the policy.

### State Machine

```text
authorized_unconsumed
  -> authorization_expired                         DB time reaches valid_until
  -> start_attempt_pending                         atomic claim + attempt + head commit

start_attempt_pending
  -> runtime_started_in_protected_boundary         timely verified success receipt
  -> runtime_start_failed_without_start            timely verified no-effect receipt
  -> runtime_start_outcome_uncertain                every other post-commit outcome
```

All result states are terminal. `runtime_start_outcome_uncertain` is monotonic: a late receipt,
operator action, event replay, worker recovery or later observation cannot convert it to success or
known failure. If a pending attempt passes its deadline without a result, the authoritative read
projection reports uncertainty. A no-I/O finalizer may append the same uncertainty result, but it
must never call the starter.

### Replay And Point Of No Return

The service performs one durable replay lookup as its first repository operation.

- Exact terminal replay returns the existing minimized presentation without trusted-component I/O.
- Exact started-attempt replay returns pending or authoritative uncertainty and never invokes the
  starter.
- Same idempotency key with changed request or lineage fails closed.
- A competing claim, attempt, envelope or lease consumer fails closed.
- A committed claim with an ambiguous transaction result is treated as started and never retried.

Cancellation before commit prevents the attempt. Cancellation at or after commit cannot restore
the lease, delete evidence, stop the protocol, transfer the call or create a retry right.

### PostgreSQL Atomicity And Locking

PostgreSQL is the sole production authority. In canonical order it locks and revalidates:

1. the complete immutable ADR-160 through ADR-172 source lineage;
2. the ADR-173 authorization claim and lease;
3. current destination generation and fencing token;
4. the exact protected runtime slot generation;
5. the guarded runtime-envelope coordination head; and
6. competing IMP-224 claims, attempts and terminal results.

Under authoritative database time, the transaction requires the exact lease to be
`authorized_unconsumed`, unexpired, inside its effective deadline and to have sufficient
code-owned invocation margin. It then atomically:

1. appends the consumption claim;
2. appends the started attempt and signed-instruction commitment; and
3. transitions the head to `start_attempt_pending` with the exact claim and attempt IDs.

The transaction commits before starter I/O. Commit failure or commit ambiguity never permits a
starter call. There is no consumption-only intermediate state.

Recording a verified result appends one result and atomically transitions the same coordination
head from pending to terminal. Success sets only the historical `runtime_started` outcome fact.
Known failure and uncertainty keep all runtime/process outcome facts false. Every transition binds
the exact envelope commitment/generation, destination fence, slot generation, lease, claim,
attempt and result.

### Signed Start Instruction

The persisted instruction and its signed envelope bind:

- the exact authorization lease, consumption claim and start attempt IDs and digests;
- request nonce and protected operation reference;
- runtime envelope ID, commitment and generation;
- destination deployment, generation and fencing token digest;
- runtime slot commitment and generation;
- runtime-start policy, profile, starter contract and approved starter identity;
- authoritative started time and invocation deadline; and
- all forbidden-effect declarations.

The invocation deadline is no later than the ADR-173 lease deadline and may be narrower. The
instruction contains no runtime locator, context, endpoint, credential, secret, bearer token,
prompt, model input or reusable capability.

The instruction signing key is distinct from the starter receipt verification key. Production
fails closed when either key boundary is unavailable.

### Protected-Side Start Primitive

The trusted starter independently verifies the signed instruction and applies one atomic,
deduplicated compare-and-swap over the exact pre-existing inactive runtime envelope.

The primitive binds attempt and instruction digests and proves:

- destination generation and fence are current;
- envelope commitment and generation are exact and current;
- the envelope is inactive and has no prior start attempt or terminal start;
- the protected runtime context remains terminal and non-reusable;
- the start count changes from zero to one only for known success;
- duplicate exact invocation does not start again and returns the same signed receipt when one
  exists; and
- changed invocation, ABA lineage, resume substitution, generic process creation or scheduling is
  rejected.

The starter may activate only the exact existing protected runtime envelope. It cannot resume a
runtime, create or schedule a generic process, construct a prompt, invoke a model, access an
endpoint or credential, establish network activity, call a connector or MCP, dispatch work or
mutate infrastructure.

### Receipt And Outcome Rules

A receipt is accepted only when it is timely, signed by the code-owned receipt key and binds the
exact instruction, attempt, nonce, lineage, envelope, fence, slot generation, start counters and
deadline.

Known success requires proof that:

- the exact envelope changed atomically from inactive/unstarted to started;
- start count changed from zero to one;
- no resume, generic process creation, scheduling or forbidden effect occurred; and
- no reusable capability or protected locator was returned.

Known failure requires proof that:

- the exact envelope remains inactive and unstarted;
- envelope generation and start count did not change;
- no residual process, task, scheduled work or partial transition exists; and
- every forbidden effect remains false.

Timeout, crash, call rejection without a valid no-effect receipt, response loss, invalid or late
receipt, partial transition, conflicting receipt, persistence failure, transaction ambiguity or
cleanup uncertainty is permanently `runtime_start_outcome_uncertain`. Atlas never guesses success
or known failure and never automatically invokes the starter again.

### Authority And Side Effects

The ADR-173 lease's dedicated future-request authority is consumed at the point of no return. Claim,
attempt, receipt and result declare every reusable authority false. They are immutable non-bearer
historical evidence.

`runtime_started=true` is a verified outcome fact only. It grants no runtime resume, process
creation, scheduling, prompt construction, model inference, endpoint or credential access,
network, connector/MCP, readiness, publication, delivery, dispatch, generic execution, workflow
transition or infrastructure-mutation authority.

### Events, Audit And Recovery

The starter is invoked directly by the request-owning service after commit. Event handlers,
transactional outbox consumers, workflow retries, scheduler retries, DLQ replay and recovery
workers are prohibited from invoking it.

Events may be appended only as facts after a durable terminal result. They contain minimized
identity, state, time and integrity references and cannot carry runtime envelope, process locator,
nonce, instruction, receipt, context or protected material. Event publication failure does not
retry the protected operation.

Audit records distinguish lease consumption, attempt commit, starter invocation observation,
terminal result and uncertainty. Audit or outbox failure cannot restore the lease or create another
starter invocation.

### API And User Interface

The workload POST is strict, minimized, non-oracular and `Cache-Control: no-store`. Production
returns fail-closed conflict or unavailable responses without revealing whether protected
identities or material exist.

Normal authorized human users may read a minimized projection through the existing
username/password browser session. The projection contains only safe attempt/result state, times,
`runtime_started` outcome and integrity references. It does not require MFA or a second browser
session and contains no lease digest, runtime envelope, destination, slot, instruction, receipt,
process or protected-operation reference.

The UI section is strictly read-only and provides no consume, start, retry, resume, process,
schedule, infer, connect, probe, connector, MCP, publish, deliver, dispatch, execute or mutate
control.

### Governance Invariants

AI remains advisory-only. No AI agent or human may directly consume the lease, initiate the
protected start attempt or use the result to operate infrastructure. The exact protected workload
protocol is code-owned and not exposed as an AI tool.

Active Directory remains authentication-only. This decision creates no Active Directory
management capability or Active Directory MCP. Normal authorized human reads require no mandatory
MFA or second browser session.

## Consequences

- Lease consumption and start-attempt creation cannot split into separate recovery states.
- Durable replay and protected-side deduplication prevent double start under concurrent callers or
  duplicate transport delivery.
- A worker crash before or during the starter call may permanently hide a real outcome; Atlas
  represents that honestly as uncertainty instead of retrying.
- The protocol starts only one exact pre-existing protected runtime envelope and creates no generic
  process, inference or infrastructure authority.
- Complete lineage locks, signed instructions, signed receipts and permanent uncertainty increase
  implementation cost but preserve fail-closed behavior.

## Deferred Scope

- Runtime resume, stop, restart, process creation, process control or scheduling
- Prompt construction, model inference, query execution or code execution
- Model input, output or derived-context return
- Runtime envelope, process locator, context, handle or slot reveal, copy, download or export
- Endpoint or credential reveal, delivery, copy, download or export
- DNS, TLS, socket, proxy, network establishment or readiness probing
- Connector, MCP, broker, provider SDK or capability calls
- Event-driven or worker-recovery starter invocation
- Event acknowledgement, retry or quarantine release
- Worker delivery, dispatch or workflow state transition
- Infrastructure mutation
- Lease renewal, transfer, replacement or reissue
- Automatic retry, cleanup, rollback, recovery, reauthorization or remediation
- Human- or AI-initiated start control
- Active Directory management or an Active Directory MCP

## Validation

- Domain tests prove code-owned policy, immutable state machine, chronology, zero reusable authority
  and separation of `runtime_started` outcome from authority.
- Service tests prove replay-first ordering, commit-before-I/O, one durable attempt, at most one
  starter call and no retry of pending, terminal or uncertain attempts.
- Starter tests prove signed-instruction validation, exact CAS, deduplication, success, known
  no-effect failure, partial transition, timeout and duplicate invocation behavior.
- PostgreSQL tests prove canonical locking, lease-expiry race closure, atomic claim/attempt/head
  transition, full composite lineage, one concurrent winner, terminal head transition, append-only
  triggers and guarded downgrade.
- API and frontend tests prove workload-only POST, password-session read-only GET, minimized
  `no-store` schemas, fail-closed production composition and zero operational controls.
- Full backend/frontend regression, Alembic single-head and round-trip validation, PostgreSQL CI,
  live desktop/mobile browser inspection, independent review, exact-head PR CI, SHA-locked merge
  and independent `main` CI are required for delivery.
