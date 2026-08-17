# ADR-176: Atomic Protected Runtime-Readiness Consumption And Single Assessment Attempt

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-17 |
| Owners | Workflow Architecture, Security Architecture, Deployment Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-160 through ADR-175 |

## Context

ADR-175 issues one exact protected consumer workload a non-bearer runtime-readiness authorization
lease valid for no more than one second. The lease authorizes submission of one future readiness
request only. It is not readiness-assessment authority and contains no runtime or process locator,
endpoint, credential or reusable protected material.

Atlas now needs one explicit point of no return that consumes the lease and records one readiness
assessment attempt before calling the approved protected-boundary assessor. Splitting lease
consumption from attempt creation would permit a consumed lease with no durable attempt. Retrying an
assessment through HTTP, workflow, scheduler, outbox or DLQ recovery could instead assess the same
runtime more than once after an ambiguous failure.

Readiness is an observation of the exact runtime already proven started by ADR-174; it is not a new
runtime lifecycle transition. A new mutable readiness coordination head would duplicate state that
can be derived exactly from one immutable lease-consumption claim, one immutable attempt and at most
one immutable terminal result. The existing runtime-start coordination head remains authoritative
for the started lineage and is locked and validated read-only. It is never advanced or repurposed by
this decision.

## Decision

Atlas will atomically append one immutable
`WorkflowProtectedRuntimeReadinessConsumptionClaim` and one immutable
`WorkflowProtectedRuntimeReadinessAttempt` in a single PostgreSQL transaction. That commit
irreversibly consumes the exact ADR-175 lease and creates one durable assessment attempt. Only after
the transaction commits may the request-owning service call one approved protected-boundary
readiness assessor, at most once.

A timely verified minimized receipt may append exactly one immutable
`WorkflowProtectedRuntimeReadinessResult` in one of these terminal states:

- `runtime_ready_in_protected_boundary`;
- `runtime_not_ready_in_protected_boundary`;
- `runtime_readiness_failed_without_assessment`; or
- `runtime_readiness_outcome_uncertain`.

There is no automatic retry. The protocol proves one durable attempt and at most one Atlas assessor
invocation; it does not infer that an assessment occurred merely because the attempt committed.

### Exact Caller And Request

Only the authenticated protected consumer workload subject
`service.workflow-protected-transport-target-context-capsule-consumer` for audience
`audience.workflow-protected-transport-target-context-capsule-consumer` may call the command. The
subject, audience and consumer contract must match the immutable binding across the canonical
ADR-160 through ADR-175 lineage. Human sessions, personal access tokens, AI agents, MCP tools,
connectors, runtime identities, generic workers and recovery workers fail closed before protected-
state I/O.

The caller supplies only:

- the ADR-175 authorization lease ID;
- code-owned runtime-readiness consumption policy ID and version;
- a tenant-scoped idempotency key;
- explicit irreversible-consumption acknowledgement; and
- explicit acknowledgement that uncertain outcomes are not retried or restored.

The caller cannot supply lease or lineage digests, runtime envelope, process, locator, destination,
slot, readiness profile, assessor, instruction, nonce, deadline, receipt, outcome, endpoint,
credential, model, provider, transport or authority values. IDs and integrity references are
routing and verification metadata, never bearer authority.

### Code-Owned Policy

The code-owned policy binds the exact ADR-175 source policy and lease, protected consumer contract,
readiness profile, approved assessor contract and identity, instruction signer and receipt verifier.
It requires:

- durable exact replay classification as the first repository operation;
- authoritative PostgreSQL time and complete lineage validation under lock;
- one active, unexpired and unconsumed ADR-175 lease;
- a code-owned invocation margin before lease expiry;
- atomic claim and attempt commit before assessor I/O;
- no external I/O while the transaction is open;
- one signed metadata-only instruction and at most one assessor call;
- exact protected-side instruction deduplication;
- timely signed receipts for known outcomes;
- permanent uncertainty for every other post-commit outcome;
- no automatic retry, resume, cleanup, rollback, reauthorization or recovery; and
- no reusable authority in the claim, attempt, receipt or result.

Mutable configuration and caller input cannot weaken these requirements.

### State Derivation

```text
authorized_unconsumed
  -> authorization_expired                         DB time reaches lease deadline
  -> readiness_attempt_pending                     atomic claim + attempt commit

readiness_attempt_pending
  -> runtime_ready_in_protected_boundary           timely verified ready receipt
  -> runtime_not_ready_in_protected_boundary       timely verified not-ready receipt
  -> runtime_readiness_failed_without_assessment   timely verified no-assessment receipt
  -> runtime_readiness_outcome_uncertain            every other post-commit outcome
```

State is derived from append-only evidence and authoritative database time:

- no claim and an active lease means `authorized_unconsumed`;
- no claim and an expired lease means `authorization_expired`;
- one claim and one attempt without a result means pending until the invocation deadline;
- a pending attempt past its deadline projects as uncertainty; and
- one result defines the permanent terminal state.

No mutable readiness coordination head is created. A no-I/O finalizer may append the same uncertain
result after the deadline, but it cannot invoke the assessor. All terminal outcomes are monotonic.

### Replay, Ambiguity And Point Of No Return

The service performs durable replay lookup as its first repository operation.

- Exact terminal replay returns the existing minimized result without assessor I/O.
- Exact attempt replay returns pending or authoritative uncertainty and never calls the assessor.
- The same idempotency key with changed request, identity, scope or lineage fails closed.
- A competing consumer of the lease fails closed; only one claim and attempt can commit.
- Commit failure prevents assessor invocation.
- Commit ambiguity is treated as consumed or potentially consumed and never permits invocation.
- Cancellation before commit consumes nothing; cancellation at or after commit creates no retry.
- Timeout, crash, response loss, malformed or late receipt, conflicting evidence and result-write
  ambiguity produce permanent `runtime_readiness_outcome_uncertain`.

Event delivery, HTTP retry middleware, workflow retries, scheduler retries, outbox consumers, DLQ
replay and recovery workers are prohibited from calling the assessor.

### PostgreSQL Atomicity And Lineage

PostgreSQL is the sole production authority. In canonical order the transaction locks and
revalidates:

1. the complete immutable ADR-160 through ADR-174 source lineage;
2. the ADR-175 authorization claim and lease;
3. current destination generation and fencing token;
4. the exact protected slot generation;
5. the existing runtime-start coordination head in terminal started state, read-only;
6. the canonical successful runtime-start result; and
7. competing readiness consumption claims, attempts and results in stable key order.

The transaction observes authoritative database time before and after locking. At the final
observation the lease must remain active, unexpired and unconsumed, and the code-owned invocation
deadline must leave the required margin while remaining no later than the lease's effective
deadline. The transaction then appends the claim and attempt together and commits before assessor
I/O. There is no consumption-only intermediate state.

Append-only triggers, exact composite foreign keys and unique constraints enforce:

- at most one consumption claim per ADR-175 lease;
- exactly one attempt for the committed claim;
- at most one result per attempt;
- exact tenant, consumer, policy, lease, start-result, destination-fence, slot-generation and
  runtime-envelope lineage; and
- rejection of update, delete, truncate, cross-lineage, stale-generation and duplicate evidence.

The existing runtime-start coordination head is locked only to prove that the exact envelope remains
the canonical terminal started runtime. Readiness consumption never mutates that head. Production
never falls back to process-local or in-memory authority.

### Signed Assessment Instruction

The persisted instruction and signed envelope bind the exact lease, claim, attempt, request nonce,
runtime-start result, envelope commitment and generation, destination generation and fence, slot
generation, readiness profile, assessor identity, authoritative start time and invocation deadline.
Every prohibited-effect and reusable-authority declaration is false.

The instruction contains no runtime or process locator, context, handle, endpoint, credential,
secret, token, prompt, model input, provider coordinate or reusable capability. Its signing key is
distinct from the receipt verification key and from prior lifecycle-attestation and runtime-start
keys. Production fails closed when a required key boundary is unavailable.

### Protected-Boundary Readiness Assessor

The approved assessor independently verifies the signed instruction and evaluates only the exact
already-started runtime represented by its protected, opaque lineage binding. It performs one local,
metadata-only readiness assessment inside the protected boundary and returns one minimized signed
receipt. Exact duplicate protected-side delivery may return the same stored receipt, but it cannot
repeat the assessment; changed delivery fails closed.

The assessor cannot reveal or return runtime/process location or material. It performs no process
creation, resume, restart, stop or scheduling; no DNS, TLS, socket, proxy or other network activity;
no endpoint or credential access; no connector, MCP, broker or provider SDK call; no model or prompt
operation; no publication, delivery or dispatch; no generic execution; and no infrastructure
mutation.

### Receipt And Terminal Outcomes

A receipt is accepted only when it is timely, signed by the code-owned receipt key and binds the
exact instruction, nonce, lease, claim, attempt, complete runtime lineage, readiness profile,
assessor identity and deadline.

- `runtime_ready_in_protected_boundary` is a known positive observation.
- `runtime_not_ready_in_protected_boundary` is a known negative observation.
- `runtime_readiness_failed_without_assessment` requires timely signed proof that no readiness
  assessment occurred and that no prohibited effect or residual operation exists.
- Every other post-commit condition is `runtime_readiness_outcome_uncertain`.

`runtime_ready=true` and `runtime_ready=false` are historical outcome facts only. Neither grants
runtime, process, network, connector, MCP, model, publication, delivery, dispatch, execution,
workflow-transition or infrastructure-mutation authority. A late observation cannot replace or
upgrade a terminal outcome.

### Security And Governance

Claim, attempt, receipt and result are immutable non-bearer evidence. All reusable authority
declarations remain false. Consuming the ADR-175 lease does not transfer its dedicated request
authority into the result.

AI remains advisory-only. No AI agent or human may consume the lease, invoke the assessor or use a
readiness result to operate infrastructure. The command is code-owned and is not exposed as an AI,
MCP or connector tool.

Active Directory remains authentication-only. This decision creates no Active Directory management
route, service, capability or MCP.

### API And User Interface

The command POST is workload-only, strict, minimized, non-oracular and
`Cache-Control: no-store`. Production returns generic fail-closed conflict or unavailable responses
without revealing protected source existence, runtime material or lifecycle detail.

Normal authorized human users may GET a minimized projection through the existing username/password
browser session. The projection contains only safe readiness ID, pending or terminal state, outcome
boolean when known, timestamps and policy/profile integrity references. It requires no MFA, step-up
authentication or second browser session.

The UI is strictly read-only. It contains no consume, assess, probe, retry, resume, process,
schedule, connect, infer, publish, deliver, dispatch, execute or mutate control and never displays
runtime/process locator, endpoint, credential, nonce, instruction, receipt or protected material.

### Events, Audit And Recovery

Audit distinguishes exact replay, lease consumption, attempt commit, assessor-call observation,
known ready, known not-ready, known failed-without-assessment and uncertainty. Audit and events carry
only minimized identity, state, time and integrity references.

Events may be appended only as facts after durable evidence exists. Publication or audit-export
failure cannot restore a lease, invoke the assessor, repeat an assessment or change a terminal
result. Recovery is evidence-only and never operational.

## Consequences

- Lease consumption and attempt creation cannot split into separate recovery states.
- Append-only evidence derives readiness state without adding another mutable coordination head.
- Existing runtime-start state remains stable for ADR-175 and later exact-lineage references.
- Durable replay, lease uniqueness and protected-side deduplication prevent duplicate assessments.
- A crash after commit may permanently hide whether assessment occurred; Atlas represents that
  honestly as uncertainty instead of retrying.
- Ready and not-ready remain non-bearer observations and do not create operational authority.
- Exact lineage, short deadlines, signed instructions/receipts and permanent uncertainty increase
  implementation and test cost but preserve fail-closed behavior.

## Deferred Scope

- Any operation based on a ready or not-ready result
- Runtime resume, stop, restart, process creation, process control or scheduling
- Runtime/process locator, context, handle or protected material reveal, copy or export
- DNS, TLS, socket, proxy, network establishment or remote health probing
- Endpoint or credential reveal, use, delivery, copy or export
- Connector, MCP, broker or provider SDK calls
- Prompt construction, model inference, query or code execution
- Publication, delivery, acknowledgement, retry or quarantine release
- Worker delivery, dispatch, workflow transition or generic execution
- Infrastructure mutation
- Lease renewal, transfer, replacement, reissue or automatic recovery
- Automatic assessor retry, cleanup, rollback, reauthorization or remediation
- Human- or AI-initiated readiness controls
- Active Directory management or an Active Directory MCP

## Validation

- Domain tests prove code-owned policy, immutable state derivation, chronology, terminal outcomes,
  no mutable readiness head and zero reusable authority.
- Service tests prove replay-first ordering, atomic claim/attempt commit before I/O, at most one
  assessor call and no retry of pending, terminal, expired or uncertain attempts.
- Assessor tests prove signed instruction validation, exact deduplication, ready, not-ready,
  failed-without-assessment, timeout, malformed/late receipt and prohibited-material rejection.
- PostgreSQL tests prove authoritative time, canonical lock order, lease-expiry race closure, atomic
  claim/attempt commit, complete composite lineage, one concurrent winner, append-only enforcement,
  derived consumed state and guarded migration downgrade.
- API and frontend tests prove workload-only POST, normal password-session read-only GET, dedicated
  read permission, minimized `no-store` schemas, fail-closed production composition, strict response
  parsing and zero operational controls.
- Live validation proves one username/password login, no MFA or second browser prompt, no browser
  POST, desktop/mobile read-only rendering, no overflow and no console errors or warnings.
- Full backend/frontend regression, Alembic single-head and round-trip validation, PostgreSQL CI,
  independent review, exact-head PR CI, SHA-locked merge and independent `main` CI are required for
  delivery.
