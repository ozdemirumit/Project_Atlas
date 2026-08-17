# ADR-171: Atomic Protected Runtime-Context Use-Authorization Lease Consumption Without Runtime Use

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-17 |
| Owners | Workflow Architecture, Security Architecture, Deployment Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-160 through ADR-170 |

## Context

ADR-170 issues one append-only, non-bearer, non-renewable and non-transferable lease lasting no
more than one second. Its dedicated authority allows only a future request to consume that exact
authorization. It does not expose or authorize access to the injected context and does not permit
runtime use, start, resume, network activity, connector activity, dispatch, execution or
infrastructure mutation.

Atlas needs the next smallest irreversible boundary: consume the exact ADR-170 lease and record
that its effective authority is permanently zero. This boundary must not be confused with actual
protected runtime-context use. Combining lease consumption with context use would make a durable
authorization bookkeeping transition depend on external protected-boundary behavior and would
silently widen ADR-170's contract.

## Decision

Atlas will atomically append one immutable
`WorkflowProtectedRuntimeContextUseAuthorizationConsumptionClaim` and one immutable
`WorkflowProtectedRuntimeContextUseAuthorizationConsumptionResult` for one exact active ADR-170
lease. The terminal state is:

`authorization_consumed_without_runtime_use`

The operation consumes only authorization. It does not access, retrieve, reveal, copy, activate or
use the injected context. It performs no attestation, runtime or protected-boundary call and no
network, MCP, connector, publication, delivery, dispatch, execution or infrastructure mutation.

### Exact Caller And Request

Only the authenticated workload subject
`service.workflow-protected-transport-target-context-capsule-consumer` for audience
`audience.workflow-protected-transport-target-context-capsule-consumer` may call the command. The
identity must equal the immutable ADR-170 consumer binding. Human sessions, personal access
tokens, AI agents, MCP tools, connectors, runtime identities and generic workflow services fail
closed.

The caller supplies only:

- ADR-170 authorization lease ID;
- code-owned consumption policy ID and version;
- idempotency key; and
- explicit irreversible-consumption acknowledgement.

The caller cannot supply lease digest, source lineage, context or slot commitment, destination
generation or fence, lease timestamps, authority, operational outcome, context-use state or any
endpoint, credential, secret, runtime or provider value. The lease ID is routing metadata and is
never bearer authority.

### Code-Owned Policy

The policy is
`policy.workflow-protected-runtime-context-use-authorization-consumption` version `1.0`, with
purpose `purpose.workflow-protected-runtime-context-use-authorization-consumption`. It binds to
the canonical ADR-170 policy, consumer subject, audience and contract. It requires:

- durable replay before the consuming transaction;
- one atomic append of claim and terminal result;
- an active, unconsumed, exact-lineage ADR-170 source lease;
- irreversible acknowledgement; and
- zero external I/O and zero operational side effects.

The policy is code-owned. Mutable configuration and caller fields cannot weaken it.

### Durable Replay First

After local caller-shape validation and the durable-repository check, the first repository
operation is a durable replay lookup. An exact match on scope, authenticated subject and audience,
lease, policy, idempotency digest, request fingerprint and deterministic consumption identifiers
returns the already committed terminal claim and result without opening a new consuming
transaction.

A changed request, competing identity, competing lease, digest mismatch or reuse of an
idempotency key with different content fails closed. Replay does not renew, transfer, replace,
reissue or retry the lease and performs no external I/O.

### PostgreSQL Atomic Consumption

Production requires PostgreSQL. In one transaction the repository locks and revalidates the
canonical lineage in its established oldest-to-newest order, including:

1. the ADR-169 injected-context success lineage;
2. the current destination deployment head and exact generation/fence;
3. the current protected-slot head and exact post-injection generation;
4. the ADR-170 authorization claim and lease; and
5. any existing ADR-171 claim or result for the lease, lineage or idempotency scope.

After all locks are held, PostgreSQL `clock_timestamp()` is authoritative. The transaction proves:

- every composite lineage edge and canonical digest is exact;
- the lease is `authorized_unconsumed`, single-use, non-bearer, non-renewable and non-transferable;
- `issued_at <= consumed_at < valid_until` with an exclusive upper boundary;
- `consumed_at` is also before the lease effective deadline and injected-context lifetime ceiling;
- destination generation/fence and protected-slot post-generation still match;
- the injected context remains represented as inert and unused in canonical state;
- the request identity, scope, policy and consumer contract match the lease; and
- no canonical consumption claim already exists except an exact replay.

The repository then appends the claim and terminal result in the same transaction. There is no
observable claim-only or pending state. Transaction failure before commit consumes nothing. A
response loss after commit is recovered only through exact durable replay. Concurrent requests
have exactly one winner; uniqueness conflicts are reclassified in a new transaction.

The transaction performs no external call. Audit payload and digest are stored atomically with the
evidence. Syslog or SIEM export is a later best-effort projection of committed history and cannot
change the result.

### Immutable Zero-Authority Result

The claim and result are append-only, non-bearer historical evidence. All 26 authority fields are
false, including the dedicated
`protected_runtime_context_use_authority_granted` field. The terminal result additionally proves:

- authorization lease consumed: true;
- historical result only: true;
- context accessed or used: false;
- runtime started or resumed: false;
- readiness, network or connector activity: false;
- publication, delivery or dispatch: false;
- execution or infrastructure mutation: false; and
- renewal, transfer, replacement or retry created: false.

`authorization_lease_consumed = true` records history; it grants no capability. The immutable
ADR-170 lease row is not updated. Its effective authority becomes false because a canonical
ADR-171 claim exists. Future context use requires a separately designed policy, fresh lifecycle
evidence and an independent authorization boundary.

### Persistence

Production uses two append-only tables:

- protected runtime-context use-authorization consumption claims; and
- protected runtime-context use-authorization consumption results.

Composite foreign keys bind the claim to the exact ADR-170 lease and authorization claim and bind
the result to the exact claim and source lease. Additional composite lineage constraints preserve
the ADR-169 injection result, destination generation/fence, slot commitment/post-generation and
use-profile snapshot. Unique constraints enforce one consumption per lease and injected-context
lineage and one exact scoped idempotency winner.

Database checks enforce code-owned policy values, irreversible acknowledgement, the terminal state,
time ordering, historical-only semantics and every all-false authority and side-effect field.
Triggers reject `UPDATE` and `DELETE`. Downgrade fails closed while evidence exists. Production has
no process-memory or permissive fallback.

### API And Human Projection

The workload command is:

`POST /api/v1/workflows/protected-runtime-context-use-authorization-consumptions`

Authorized humans may inspect minimized, read-only history through:

`GET /api/v1/workflows/protected-runtime-context-use-authorization-consumptions`

Human reads use the normal username/password session and a dedicated read permission. No MFA or
second authorized browser session is required. Responses are `no-store`, minimized and non-oracle.
They expose only non-sensitive consumption identity, terminal state, policy and purpose references,
consumer contract, consumed time, all-false effect summary and a non-sensitive integrity reference.

The UI is strictly read-only. It contains no consume, use, start, resume, retry, connect, MCP,
dispatch, execute or mutate control.

### Governance

AI remains advisory-only and cannot request or consume this lease. Active Directory remains
authentication-only; this decision creates no Active Directory management capability or Active
Directory MCP.

## Consequences

- ADR-170 authority can be retired atomically without exposing or using protected context.
- Claim and terminal result cannot diverge through a visible pending state.
- Exact replay recovers commit-response loss without retrying consumption.
- The one-second lease boundary is enforced by authoritative database time under locks.
- Actual context use remains unavailable and must be designed as a separate, explicitly approved
  boundary.
- Complete lineage locking and composite persistence constraints increase implementation cost but
  preserve fail-closed behavior.

## Deferred Scope

- Injected-context access, retrieval, reveal, copy, download, export, activation or actual use
- Runtime start, resume, process creation, query execution or code execution
- Fresh context-use attestation or a protected-boundary context-use adapter
- Runtime-handle or protected-slot lookup, retrieval, reveal, copy, download or direct use
- Endpoint or credential reveal, delivery, copy, download or export
- DNS, TLS, socket, proxy, network establishment or readiness probing
- Connector, MCP, broker, provider SDK or capability calls
- Event publication, acknowledgement, retry or quarantine release
- Worker delivery, dispatch or workflow state transition
- Infrastructure mutation
- Lease renewal, transfer, replacement, reissue or automatic retry
- Cleanup, rollback, recovery or remediation
- Human- or AI-initiated context use or runtime operation
- Active Directory management or an Active Directory MCP

## Validation

- Domain tests prove the policy is code-owned, the terminal state is exact, all 26 authority fields
  remain false, every operational result remains false and lease/result chronology is valid.
- Service tests prove the exact workload-only request surface, durable replay-first ordering,
  deterministic exact replay, changed replay rejection, durable-repository requirement and a
  single atomically consuming repository call with no adapter or attestor dependency.
- PostgreSQL tests will prove exclusive deadline handling, canonical lock order, complete composite
  lineage, one concurrent winner, exact replay, append-only triggers, zero-authority checks and
  fail-closed production composition.
- API and frontend tests will prove workload-only POST, normal password-session read-only GET,
  zero-disclosure responses and the absence of operational controls.
