# ADR-167: Atomic Single-Use Protected Resident-Context Access Lease Consumption and Non-Bearer Runtime-Handle Materialization

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-16 |
| Owners | Workflow Architecture, Deployment Architecture, Security Architecture, Identity Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-160, ADR-161, ADR-162, ADR-163, ADR-164, ADR-165, ADR-166 |

## Context

ADR-166 grants the exact protected consumer workload one immutable, at-most-one-second
authorization to request a later access operation for one non-bearer protected resident context.
The lease is single-use, non-renewable, non-transferable and non-bearer. It does not consume itself,
look up or expose resident context, create a runtime handle, inject context, establish a network
path or call a connector.

Atlas now needs the next smallest functional and irreversible boundary. The lease must be durably
consumed before any trusted protected-boundary accessor is called. The protected boundary may then
atomically exchange the exact resident context for one short-lived, non-bearer runtime-context
handle that remains inside that boundary. Ordinary Atlas processes must never receive a handle,
locator, token, endpoint, credential or raw context.

Handle creation is historical outcome evidence for a future independently authorized injection or
use operation. It is not permission to retrieve or use the handle. A crash, timeout or uncertain
outcome after the consumption commit must never make the lease or resident context reusable.

## Decision

Atlas will implement one
`WorkflowProtectedResidentContextAccessConsumption` boundary. It irreversibly consumes one exact
ADR-166 lease, atomically appends one claim and one started attempt, calls one trusted accessor only
after that commit, and appends one minimized terminal result only when the outcome is trustworthy.

Only the exact code-owned consumer subject
`service.workflow-protected-transport-target-context-capsule-consumer` authenticated for
`audience.workflow-protected-transport-target-context-capsule-consumer` may request consumption of
its own lease. Human sessions, personal tokens, AI agents, generic workflow services, attestors,
openers, accessors, publishers and every other workload fail closed.

The request contains only:

- access-authorization lease ID;
- code-owned access-consumption policy ID and version;
- `irreversible_consumption_acknowledged = true`;
- `uncertain_outcome_requires_new_authorization_acknowledged = true`; and
- idempotency metadata.

The lease ID and any human-visible integrity reference are routing metadata, never authority. Atlas
resolves the canonical lease digest and complete originating-operation lineage server-side after
authenticating the exact workload. The caller cannot provide or override resident-context,
runtime-handle, destination, fence, attestor, accessor, lifetime, endpoint, credential, route,
network, provider or authority fields. Atlas derives all such values from authenticated context,
canonical append-only lineage, code-owned trusted profiles and authoritative server-side state.

### Authority Separation

The ADR-166 lease row remains append-only. Effective consumption is derived from one unique claim.

The claim, attempt and result set `protected_resident_context_access_authority_granted = false`.
Both capsule authority declarations and all 17 operational authority declarations are also exactly
false. In particular, successful handle materialization grants no protected-artifact access,
endpoint or credential delivery, network access, readiness, publication, delivery, dispatch,
execution or infrastructure mutation.

`runtime_handle_established_in_protected_boundary = true` is historical outcome evidence. The
handle identity and digest are non-bearer lineage and cannot authorize lookup, retrieval,
injection or use.

### Durable Replay Preflight

Before any attestor or accessor call, Atlas performs one durable replay lookup. An exact trustworthy
terminal result is returned directly. An exact matching claim or started attempt is presented as
`access_pending` before its immutable deadline and `access_outcome_uncertain` at or after that
deadline. Replay performs no protected-boundary, attestor, accessor, provider or network I/O.

A changed request, idempotency conflict, competing identity, mismatched digest or prior claim for
the lease or resident context fails closed. The transaction repeats replay classification under
canonical locks before creating records.

### Fresh Time-Of-Use Evidence

Only when no durable claim exists, Atlas obtains fresh, independently signed, nonce-bound and
metadata-only resident lifecycle and accessor-readiness attestations before opening the database
transaction. Together they must prove:

- the exact ADR-166 lease and complete ADR-160 through ADR-166 lineage;
- the exact resident context remains present, unexpired, unrevoked, undestroyed and unconsumed;
- no runtime handle is outstanding;
- the exact consumer, destination boundary, deployment generation and fence remain current;
- the trusted accessor can atomically consume only the bound resident context and create only the
  code-owned non-bearer runtime-handle profile; and
- no raw context, endpoint, credential, secret, bearer token, locator or provider payload exists in
  the evidence.

Unavailable, unsigned, malformed, expired, mismatched, stale, negative, consumed, handle-bearing
or bearer evidence fails closed. Atlas verifies captured evidence before the transaction and again
offline while canonical database locks are held. No external I/O occurs inside the transaction.
The protected boundary independently performs an atomic compare-and-set from the exact
`resident_context_unconsumed && !handle_outstanding` state; database evidence alone cannot perform
that transition.

### Atomic Commit And Point Of No Return

Production uses PostgreSQL and canonical oldest-to-newest lineage locking. One transaction locks
and revalidates the complete target-context, capsule, binding, handoff, opening, resident-context
and ADR-166 authorization lineage; current route and credential-assignment heads; destination
generation and fence; both fresh attestations; and any prior scoped consumption records.

PostgreSQL evaluates authoritative time after all locks are held. The lease must remain
`authorized_unconsumed`, active, single-use, non-renewable, non-transferable and non-bearer. The
resident context and both attestations must retain the code-owned minimum remaining budget.
The claim commit and trusted accessor completion must both occur strictly before the immutable
`access_deadline`, which cannot exceed the ADR-166 lease `valid_until`, resident-context
`usable_until` or either fresh attestation deadline. Consumption is therefore chained immediately
by the workload and is not a human copy-and-paste workflow.

Canonical consumption-authorization audit payload and digest are stored inside the transaction.
Atlas obtains database time again and repeats currentness, integrity, deadline and replay checks
immediately before append. The transaction atomically appends exactly one consumption claim and
one started attempt. That commit is the irreversible point of no return.

A rollback before commit leaves the lease unconsumed and no accessor is called. After commit every
failure or uncertainty leaves the lease permanently consumed. External audit and SIEM export occur
only after commit and cannot roll back, duplicate or retry protected-boundary work.

### Trusted Protected-Boundary Accessor

After claim commit, one trusted accessor receives only protected-boundary references derived from
the committed attempt. It revalidates the exact resident context, consumer, destination generation
and fence, accessor contract, runtime-handle profile and immutable access deadline inside the
protected boundary.

The accessor atomically consumes the resident context and creates at most one short-lived runtime-
context handle. The handle remains inside the exact protected boundary, is non-bearer, cannot be
looked up by ordinary Atlas code and has a hard expiry no later than the resident-context lifetime
ceiling. Raw context and handle locators are never returned, persisted, logged, audited, published,
indexed or exposed through an API or UI.

Production requires the approved trusted accessor and protected destination. A deterministic
development adapter may emit fixed metadata only when explicitly test-enabled and performs no
filesystem, provider, network, dispatch, execution or infrastructure-mutation operation.

### Outcomes And Recovery

A valid signed receipt completed strictly before `access_deadline` may append:

- `handle_established_in_protected_boundary` only when the exact resident context was atomically
  consumed and one non-bearer protected runtime handle was established; or
- `resident_context_access_failed` only when signed evidence proves no runtime handle remains and
  the resident context cannot be ambiguously reused.

Timeout, crash, late or invalid receipt, partial transition, cleanup uncertainty, destination
uncertainty or persistence ambiguity produces `access_outcome_uncertain`. Claim-only reads derive
pending before the deadline and uncertainty afterward without fabricating a receipt.

After claim commit Atlas never retries the accessor, restores the lease, renews authority or
creates a competing claim. Exact replay returns durable state without external I/O. Known failure
and uncertainty authorize no autonomous cleanup or operational action.

### Durable Persistence

Production stores three append-only groups:

- access lease-consumption claims, unique by authorization lease and protected resident context;
- access attempts, unique by claim and exact destination/accessor/runtime-handle profile, with an
  immutable access deadline and attestation digests; and
- access results, unique by attempt, distinguishing trusted signed receipt evidence from explicit
  code-owned receipts-free uncertainty evidence.

Composite foreign keys bind the claim and attempt to the exact ADR-166 claim and lease and complete
ADR-165 result lineage. Database CHECK constraints enforce code-owned workload, policy,
acknowledgements, non-bearer declarations and all 20 authority fields as false. Triggers reject
`UPDATE` and `DELETE`. Downgrade fails closed while any table contains evidence. Production has no
process-memory, permissive or caller-asserted fallback.

### API And Human Presentation

The workload command is:

`POST /api/v1/workflows/protected-resident-context-access-consumptions`

Only the exact consumer workload may call POST. The command accepts no digest copied from human
presentation and resolves all integrity evidence server-side. Authorized humans may inspect a
separate minimized inventory through:

`GET /api/v1/workflows/protected-resident-context-access-consumptions`

Human reads use the normal username/password browser session and a dedicated read permission. No
MFA, second login or authorized-browser-session prompt is required. Responses are `no-store`,
minimized and non-oracle.

The human response exposes only non-sensitive attempt/result identity and state, timestamps,
consumer contract and purpose references, accessor/runtime-profile references, policy reference,
the all-false authority contract and a non-sensitive integrity reference. It omits lease, opening,
resident-context, handle, receipt, attestation, nonce, route, credential, locator, idempotency,
request-fingerprint and fence material.

The UI section is titled `Protected resident-context access consumptions` and is strictly read-only.
It provides no consume, access, retry, retrieve, reveal, copy, download, inject, connect, probe,
publish, dispatch, execute or mutate control.

## Consequences

- One durable claim consumes the access lease before the trusted accessor can touch resident state.
- Crash or uncertainty cannot make used authority reusable.
- A successful protected transition yields only non-bearer handle lineage, not runtime authority.
- Raw context and handle location remain inside the exact protected boundary.
- Every later injection or use still requires a separate policy and authorization boundary.

## Deferred Scope

- Runtime-handle lookup, retrieval, reveal, copy, download or export
- Context injection or runtime use
- DNS, TLS, socket, proxy, network establishment or readiness probing
- Connector, MCP, broker, provider SDK or capability calls
- Event publication, acknowledgement, retry or quarantine release
- Worker dispatch, workflow state transition, execution or infrastructure mutation
- Automatic accessor retry, lease renewal, replacement or reissue
- Autonomous cleanup, recovery or operational remediation
- Human- or AI-initiated resident-context access or runtime use
- Active Directory management or an Active Directory MCP; AD remains authentication-only

## Validation

- Domain and application tests cover exact workload identity, caller-field prohibition,
  acknowledgements, unique consumption, exact and changed replay, pending, success, known failure,
  uncertainty, late or invalid receipt and all 20 authority fields as false.
- Call-order tests prove claim and started-attempt commit before accessor invocation and prove replay
  or claim-only recovery performs no external I/O.
- Attestor and accessor tests cover nonce-bound signatures, exact lineage, negative lifecycle,
  atomic transition, handle hard expiry, late receipts and no raw material or locator return.
- PostgreSQL tests cover canonical lock order, two database-time checks, concurrent unique winner,
  composite lineage, append-only triggers, crash state, guarded downgrade and no production fallback.
- API and UI tests cover workload-only POST, session-only GET, personal-token, human and AI denial,
  `no-store`, non-oracle errors, minimized schemas and zero operational controls.
- Full backend and frontend suites, Alembic single-head and round-trip validation, real PostgreSQL
  CI, independent review, exact-head PR CI, SHA-locked merge and independent `main` CI are required.
