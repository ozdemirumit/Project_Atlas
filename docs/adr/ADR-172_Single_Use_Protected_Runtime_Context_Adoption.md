# ADR-172: Single-Use Protected Runtime-Context Adoption After Terminal Authorization Consumption

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-17 |
| Owners | Workflow Architecture, Security Architecture, Deployment Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-160 through ADR-171 |

## Context

ADR-171 atomically consumes one exact ADR-170 runtime-context use-authorization lease and records
`authorization_consumed_without_runtime_use`. Its claim and result are terminal historical
evidence, not bearer authority, and all 26 authority declarations remain false.

Atlas still needs one explicit boundary that can use the already injected context inside the
protected runtime boundary without disclosing context to an ordinary Atlas process. Treating the
ADR-171 result as authority would launder historical evidence into a reusable capability. Merely
writing `used=true` to PostgreSQL would also be false evidence because it would not prove any
protected-side state transition.

This decision therefore defines actual context use narrowly as protected runtime-context
**adoption**: one existing inert protected slot changes atomically from unused to used exactly once,
the context remains inside the protected boundary, transient material is zeroized, and the slot
becomes terminal and non-reusable. Adoption does not start or resume a runtime and performs no
query, code, process, network, connector, MCP, dispatch or infrastructure operation.

## Decision

Atlas will append one immutable
`WorkflowProtectedRuntimeContextUseClaim` and one immutable
`WorkflowProtectedRuntimeContextUseAttempt` before invoking one approved protected-boundary use
executor. A timely verified minimized receipt may then produce exactly one immutable
`WorkflowProtectedRuntimeContextUseResult` in one of these terminal states:

- `context_used_once_in_protected_boundary`;
- `context_use_failed_without_use`; or
- `context_use_outcome_uncertain`.

The claim and started attempt commit is the irreversible point of no return. Atlas never retries
the protected operation automatically. Success is accepted only from a signed receipt proving the
protected-side unused-to-used compare-and-swap and all forbidden effects as false.

### Exact Caller And Request

Only the authenticated workload subject
`service.workflow-protected-transport-target-context-capsule-consumer` for audience
`audience.workflow-protected-transport-target-context-capsule-consumer` may call the command. The
identity must equal the immutable consumer binding across the canonical ADR-160 through ADR-171
lineage. Human sessions, personal access tokens, AI agents, MCP tools, connectors, runtime
identities and generic workflow services fail closed before protected-state I/O.

The caller supplies only:

- the ADR-171 result ID and digest;
- code-owned context-use policy ID and version;
- tenant-scoped idempotency key;
- explicit irreversible-use acknowledgement; and
- explicit acknowledgement that uncertain outcomes are not retried or restored.

The caller cannot supply context, handle or slot identity or material; destination generation or
fence; protected operation reference; executor identity; instruction, nonce or receipt; timing;
authority; operational outcome; endpoint, credential, secret, provider or runtime values. Source
IDs and digests are routing and integrity metadata and are never bearer authority.

### Code-Owned Policy

The policy is `policy.workflow-protected-runtime-context-use` version `1.0`, with purpose
`purpose.workflow-protected-runtime-context-use`. It binds the exact consumer contract, source
policy, protected-slot use profile, executor profile and these immutable rules:

- durable replay classification precedes attestor or executor I/O;
- fresh signed metadata-only use-eligibility evidence is mandatory;
- claim and started attempt commit before executor I/O;
- the protected executor is invoked at most once by Atlas;
- success requires one timely valid receipt proving exact atomic adoption;
- known failure requires one timely valid receipt proving no use or residual transition;
- every other post-commit outcome is permanently uncertain;
- no context or protected locator leaves the protected boundary; and
- every authority declaration remains false.

Mutable configuration and caller input cannot weaken the policy.

### Protected-Side Adoption Primitive

The only permitted use primitive is an atomic compare-and-swap inside the trusted protected
boundary over:

- the exact injected-context commitment and canonical ADR-169 lineage;
- current destination generation and fence;
- exact protected-slot commitment and current post-injection generation;
- context state `present_inert_unused` and use count zero;
- exact code-owned use and executor profiles; and
- the persisted attempt and signed instruction digest.

Success adopts the context into the already existing inactive runtime envelope, advances the exact
slot generation, changes the context state to `used_terminal`, increments use count from zero to
one and zeroizes transient material. The operation returns no context, handle, slot locator,
derived prompt, model input, model output or reusable capability.

Adoption is an outcome fact, not query or code execution. It creates no process and does not start,
resume, schedule or invoke model inference. Those remain separate future boundaries.

### Trust Boundary

The trusted computing base contains only the protected slot/context manager, dedicated use
executor, lifecycle/use attestor, protected-side atomic deduplication store, local authenticated
call gate and distinct attestation and receipt signing keys.

Atlas API, UI, ordinary workers, AI agents, connector and MCP components, event publishers and
ordinary PostgreSQL readers are outside this boundary. Production has no process-memory,
synthetic, caller-asserted or permissive executor fallback. A deterministic development executor
may exist only under explicit development composition and performs no real protected-state,
network, process, provider or infrastructure operation.

### Durable Replay First

After local request-shape and caller checks and the durable-repository requirement, the first
repository operation is one durable replay lookup. Exact terminal replay returns the same minimized
result without attestor or executor I/O. A matching started attempt without a terminal result is
never resumed or reinvoked and projects pending before its deadline or uncertainty after it.

Changed requests, competing identities or lineages, digest mismatch and tenant-scoped idempotency
reuse fail closed. Commit-response loss is recovered only from durable claim, attempt and result
evidence.

### Fresh Metadata-Only Attestation

Before the irreversible transaction, Atlas sends one server nonce and expected non-sensitive
commitments to the approved use-eligibility attestor. A fresh signed response must prove:

- the exact injected context remains present, inert, unexpired, unrevoked, uncleared,
  unsuperseded and unused;
- context use count is zero and no competing adoption is pending or terminal;
- destination generation/fence and exact slot generation are current;
- the exact use and executor profiles remain eligible; and
- no context, handle, slot locator, endpoint, credential or secret is disclosed.

Attestation is advisory evidence. The executor independently repeats protected-side CAS checks at
operation time, preventing attestation-to-use time-of-check/time-of-use substitution.

### PostgreSQL Claim And Attempt Commit

Production requires PostgreSQL. In one transaction Atlas obtains an authoritative database time,
locks the complete canonical lineage oldest-to-newest through the ADR-171 claim and result, locks
the current destination and exact protected-slot heads, and locks any competing use claim. After
all locks it obtains a second authoritative database time and revalidates:

1. every composite lineage edge, digest, signature, scope, identity and deadline;
2. the exact terminal ADR-171 state `authorization_consumed_without_runtime_use`;
3. all-false authority and no-use declarations on the ADR-171 source;
4. current destination generation/fence and exact unused slot generation;
5. fresh attestation nonce, subject, audience, profile, generation and deadline binding;
6. absence of any claim for the ADR-171 result, injected context, exact slot generation or scoped
   idempotency identity; and
7. an invocation deadline bounded by every effective upstream and attestation deadline.

The transaction appends the claim and one `use_started` attempt with a signed instruction digest,
opaque protected-operation reference and audit evidence. In the same transaction, the SQL slot-head
compare-and-swaps from `inert_context_present` to `use_outcome_uncertain` at the same generation.
This is a conservative coordination state, not proof that protected-side use occurred. No external
I/O occurs while locks are held. Transaction failure before commit performs no use. Commit
permanently consumes the operation opportunity for success, failure, timeout, crash, late receipt,
partial transition or uncertainty.

### Executor Invocation And Receipt

After commit, Atlas invokes the dedicated protected executor exactly once with only the opaque
operation reference and signed instruction digest. The executor independently resolves protected
state, atomically deduplicates by attempt and instruction digest, performs the exact CAS primitive
and returns one signed minimized receipt.

Attestation and receipt keys are distinct. The receipt binds source, claim, attempt, instruction,
nonce, consumer, policy, executor, context and slot commitments, destination generation/fence,
pre/post slot generation, use-count transition, completion time, deadline and every forbidden
effect. Raw receipt payload and protected identifiers are not exposed through ordinary API, UI,
logs, events or audit exports.

Atlas records:

- `context_used_once_in_protected_boundary` only when a timely valid receipt proves exact
  unused-to-used adoption, use count `0 -> 1`, terminal non-reusable state, transient zeroization and
  every forbidden effect as false; its SQL slot head becomes `context_used_terminal` at the exact
  signed post-generation;
- `context_use_failed_without_use` only when a timely valid receipt proves no adoption, no use-count
  or slot-generation change, no residual transition and every forbidden effect as false; its SQL
  slot head returns to `inert_context_present` at the unchanged signed generation, but the committed
  claim still prevents retry or reauthorization; or
- `context_use_outcome_uncertain` for timeout, crash, late, invalid or unsigned receipt, partial or
  contradictory transition, cleanup uncertainty, persistence ambiguity or any condition that does
  not prove a known outcome; its SQL slot head remains `use_outcome_uncertain`.

A late receipt never changes a terminal uncertainty result. Atlas performs no automatic retry,
cleanup, rollback, recovery, replacement, reauthorization or remediation.

### Authority And Effect Separation

Claims, attempts, receipts, results, event IDs and integrity references are non-bearer evidence.
All 26 authority declarations remain false, including
`protected_runtime_context_use_authority_granted`, runtime use, runtime start/resume, connector,
network, dispatch, execution and infrastructure-mutation authorities.

`protected_runtime_context_use_performed=true` is permitted only as a verified success outcome
fact. It grants no authority and cannot authorize inference, prompt construction, model output,
network access, connector activity or infrastructure operation.

### Durable Persistence And Events

Production stores append-only:

- `workflow_protected_runtime_context_use_claims`;
- `workflow_protected_runtime_context_use_attempts`; and
- `workflow_protected_runtime_context_use_results`.

Uniqueness covers the ADR-171 source result, injected-context lineage, exact destination/slot
generation, use profile, tenant-scoped subject/audience/idempotency digest and instruction digest.
Composite foreign keys, chronology and code-owned-value checks preserve lineage. Triggers reject
`UPDATE` and `DELETE`. The existing slot-head contract adds `use_outcome_uncertain` and
`context_used_terminal` states. Downgrade fails closed while evidence exists.

Terminal commit may enqueue one minimized historical event in the transactional outbox:

- `WorkflowProtectedRuntimeContextUsed`;
- `WorkflowProtectedRuntimeContextUseFailed`; or
- `WorkflowProtectedRuntimeContextUseOutcomeBecameUncertain`.

Event replay cannot invoke the executor or become an authorization source.

### API And Human Projection

The workload command is:

`POST /api/v1/workflows/protected-runtime-context-uses`

Authorized humans may inspect minimized read-only history through:

`GET /api/v1/workflows/protected-runtime-context-uses`

Human reads use the normal username/password session and a dedicated read permission. No MFA or
second authorized browser session is required. Responses are `no-store`, minimized and non-oracle.
They expose only non-sensitive use identity, state, policy/purpose references, consumer contract,
started/completed time, all-false authority summary, minimized effect summary and integrity
reference.

The UI is strictly read-only and contains no adopt, use, retry, start, resume, connect, MCP,
dispatch, execute or mutate control.

### Governance

AI remains advisory-only and cannot request context adoption. Active Directory remains
authentication-only; this decision creates no Active Directory management capability or Active
Directory MCP.

## Consequences

- Atlas can prove one real protected-side context-use transition without receiving context.
- ADR-171 historical evidence cannot be replayed as bearer authority.
- Protected-side CAS and deduplication prevent double use even when callers race or responses are
  lost.
- Split-brain between PostgreSQL and the protected boundary is represented as permanent uncertainty,
  never guessed success.
- Runtime start, inference and operational authority remain separate explicit boundaries.
- Complete lineage locking, attestation, receipt verification and uncertainty handling increase
  implementation cost but preserve fail-closed behavior.

## Deferred Scope

- Runtime start, resume, scheduling or process creation
- Prompt construction, model inference, query execution or code execution
- Model output or derived-context return
- Context, handle or slot reveal, copy, download, export or direct ordinary-process access
- Endpoint or credential reveal, delivery, copy, download or export
- DNS, TLS, socket, proxy, network establishment or readiness probing
- Connector, MCP, broker, provider SDK or capability calls
- Event acknowledgement, retry or quarantine release
- Worker delivery, dispatch or workflow state transition
- Infrastructure mutation
- Automatic retry, cleanup, rollback, recovery, reauthorization or remediation
- Human- or AI-initiated adoption
- Active Directory management or an Active Directory MCP

## Validation

- Domain tests prove exact policy, state machine, use-count transition, chronology, all 26 false
  authority fields and separation of outcome facts from authority.
- Service tests prove workload-only access, durable replay-first ordering, no retry of started or
  uncertain attempts, strict attestation and receipt verification and exactly one executor call.
- Executor tests prove exact protected-side CAS, atomic deduplication, zero disclosure, transient
  zeroization and success, known failure, partial mutation, timeout and invalid-receipt behavior.
- PostgreSQL tests prove canonical locks, two database-time observations, complete composite
  lineage, one concurrent winner, append-only triggers and guarded downgrade.
- API and frontend tests prove workload-only POST, normal password-session read-only GET, minimized
  `no-store` schemas, fail-closed production composition and zero operational controls.
- Full backend/frontend regression, Alembic single-head and round-trip validation, PostgreSQL CI,
  live desktop/mobile browser inspection, independent review, exact-head PR CI, SHA-locked merge
  and independent `main` CI are required for delivery.
