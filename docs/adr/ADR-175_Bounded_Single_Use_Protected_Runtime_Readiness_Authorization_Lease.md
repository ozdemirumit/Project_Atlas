# ADR-175: Bounded Single-Use Protected Runtime-Readiness Authorization Lease Without Probing, Network, Connector, Execution or Infrastructure Mutation Authority

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-17 |
| Owners | Workflow Architecture, Security Architecture, Deployment Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-160 through ADR-174 |

## Context

ADR-174 may produce one canonical `runtime_started_in_protected_boundary` result for the exact
pre-existing protected runtime envelope. That result is immutable historical outcome evidence. It
does not prove that the started runtime is still current, responsive or eligible for a readiness
attempt, and it grants no readiness, process, scheduler, network, connector, publication,
dispatch, execution or infrastructure-mutation authority.

Atlas now needs the next smallest authorization boundary. The exact protected consumer workload
must be able to request one extremely short-lived lease authorizing only submission of a future
protected runtime-readiness attempt. Runtime start success cannot itself become readiness
authority. Doing so would convert an old outcome into an unbounded operational capability.

Current eligibility may differ from the historical start result. The runtime envelope,
destination generation and fence, protected slot generation, consumer binding, readiness profile
or policy may have drifted, expired, been revoked or already acquired a competing readiness
authorization. Issuance therefore requires fresh signed metadata-only lifecycle evidence and
complete canonical lineage revalidation without revealing a process or runtime locator.

## Decision

Atlas will issue one immutable `WorkflowProtectedRuntimeReadinessAuthorizationLease` from one
exact canonical ADR-174 `runtime_started_in_protected_boundary` result. The lease authorizes only
submission of one future request to a separately designed atomic readiness-attempt boundary.
IMP-225 performs no readiness probe, process control, scheduling, DNS, TLS, socket, proxy, network,
connector or MCP call, publication, delivery, dispatch, generic execution or infrastructure
mutation.

Only the exact code-owned protected consumer workload authenticated as
`service.workflow-protected-transport-target-context-capsule-consumer` for
`audience.workflow-protected-transport-target-context-capsule-consumer` may request issuance for
its own ADR-174 result. The subject and audience must match the immutable consumer binding across
the complete ADR-160 through ADR-174 lineage. Human sessions, personal access tokens, AI agents,
attestors, runtime identities, connectors, MCP tools, publishers and generic workflow services
fail closed before protected-state I/O.

The request contains only:

- ADR-174 start-result ID and canonical digest;
- code-owned protected runtime-readiness authorization policy ID and version; and
- tenant-scoped idempotency metadata.

The caller cannot supply or override runtime envelope, process, slot, context, destination,
locator, commitment, generation, fence, lifecycle state, readiness profile, attestation, timing,
lease duration, authority, endpoint, credential, route, network, connector, MCP, publication,
dispatch, execution or mutation fields. IDs, digests and integrity references are routing and
integrity metadata, never bearer authority.

### Canonical ADR-174 Eligibility

Issuance accepts only one terminal canonical ADR-174
`runtime_started_in_protected_boundary` result. Its timely verified signed starter receipt must
prove:

- the exact ADR-173 lease, IMP-224 claim and started attempt are its sole lineage;
- the protected-side inactive-to-started compare-and-swap completed for the exact envelope once;
- `runtime_started=true`, with no resume, generic process creation or scheduling effect;
- destination generation and fence, protected slot generation, consumer, policy and runtime-start
  profile match the complete locked lineage;
- every forbidden effect and every reusable authority declaration is false; and
- the outcome is known, timely and free of failure, ambiguity or prohibited returned material.

`runtime_start_failed_without_start`, `runtime_start_outcome_uncertain`, pending, claim-only,
attempt-only, late, unsigned, malformed, ambiguous or receipt-free evidence is ineligible. The
result, attempt and claim must agree with the exact ADR-173 lease and complete ADR-160 through
ADR-174 lineage. Canonical digests, signatures, chronology and append-only relationships must
verify without repair, inference, fallback or caller-provided replacement evidence.

### Fresh Signed Metadata-Only Readiness Eligibility Attestation

Before opening the issuance transaction, Atlas generates one server nonce and obtains one fresh,
independently signed, metadata-only runtime-lifecycle and readiness-eligibility attestation from
the trusted protected boundary. This passive evidence collection is not a readiness probe,
process operation, scheduler call, network request, connector invocation or executor operation.
No protected prober, process controller, network adapter, connector, MCP tool or provider may be
called while the PostgreSQL transaction is open.

The attestation canonically commits to:

- server nonce, issued-at and expires-at values;
- attestor identity, contract ID/version and signing-key ID;
- ADR-174 result, attempt, claim and authorization-lease identities and digests;
- consumer subject, audience, contract and purpose;
- runtime envelope identity, commitment, generation and started lifecycle state;
- destination deployment, generation and fencing-token digest;
- protected slot commitment and current generation;
- runtime-start result state and `runtime_started=true` outcome;
- code-owned readiness profile ID, version and digest;
- no prior readiness claim, lease, attempt or result for the same lineage;
- no runtime resume, stop, restart, generic process or scheduling transition; and
- zero readiness probing, network, connector, publication, dispatch, execution or mutation effects.

The signed payload contains no runtime locator, process identifier, context, handle, endpoint,
credential, secret, network coordinate or command. It is evidence only and cannot be replayed as
authority. Signature verification, nonce equality, exact contract matching, chronology and a
code-owned freshness window of no more than one second are mandatory before database writes. The
service, PostgreSQL transaction and database constraints all enforce this maximum independently.

### Durable Exact-Replay Preflight

Before requesting fresh attestation evidence, Atlas performs one durable replay lookup. Exact
replay with the same scope, authenticated workload, ADR-174 result, policy and idempotency key
returns the original minimized claim and lease state without attestor I/O. Changed replay,
idempotency reuse for another result or a competing canonical claim fails closed.

Replay preflight is an optimization, not the authority boundary. PostgreSQL remains authoritative
and repeats all uniqueness, lineage, signature, currentness, fence and time checks under lock.

### PostgreSQL Authority And Lease Semantics

PostgreSQL is the sole production authority. In canonical order the issuance transaction locks
and revalidates:

1. the complete immutable ADR-160 through ADR-173 source lineage;
2. the ADR-174 consumption claim, attempt and successful terminal result;
3. current destination generation and fencing token;
4. the exact protected slot generation;
5. the guarded runtime-envelope coordination head in terminal started state;
6. the code-owned readiness profile and policy; and
7. competing readiness-authorization claims, leases or later readiness attempts.

The transaction verifies the fresh attestation offline and observes authoritative database time
before and after all locks and validations. Both observations must remain inside the attestation,
source and code-owned eligibility windows. It then atomically appends one idempotency claim and one
positive lease.

The lease is:

- valid for no more than one second and never beyond any upstream or attestation deadline;
- single-use, non-renewable, non-transferable and non-replaceable;
- bound to the exact ADR-174 result and complete protected runtime lineage;
- bound to the exact consumer, destination generation/fence, slot generation, readiness profile,
  policy, purpose and idempotency claim; and
- non-bearer and unusable by a human, AI agent, connector or generic Atlas process.

Append-only constraints, composite foreign keys, unique indexes, check constraints and guarded
coordination state reject duplicate, conflicting, stale or cross-lineage issuance. Production
never falls back to in-memory authority.

### Authority Model

The idempotency claim grants no authority. The immutable lease may set only
`protected_runtime_readiness_authority_granted=true`. Every existing authority declaration remains
false, including runtime start/resume, process control, network access, readiness probe,
connector activity, publication, delivery, dispatch, execution and infrastructure mutation.

The dedicated declaration means only that the exact workload may submit this exact lease to the
future readiness-attempt boundary. It is not `readiness_probe_authorized`, does not authorize a
probe or network operation, and cannot be interpreted as connector, MCP, publication, dispatch,
execution or infrastructure-operation authority. At expiry or once a unique future consumption
claim exists, effective authority is false without mutating the immutable lease.

### Events, Audit And Recovery

Issuance emits only minimized claim/lease facts after commit. Events, outbox consumers, workflow
retries, scheduler retries, DLQ replay and recovery workers cannot request, renew, transfer or
consume the lease. Event payloads omit runtime, process, slot, endpoint, credential, attestation,
nonce and protected material.

Audit distinguishes exact replay, successful issuance, changed replay, stale lineage, ineligible
start outcome, attestation failure and fail-closed repository unavailability. Audit or publication
failure cannot create, restore or extend authority.

### API And User Interface

The workload POST is strict, minimized, non-oracular and `Cache-Control: no-store`. Production
returns fail-closed conflict or unavailable responses without revealing protected identities,
locators or lifecycle details.

Normal authorized human users may read a minimized projection through the existing
username/password browser session. It contains only safe claim/lease state, times, policy/readiness
profile integrity references and effective authority. It requires no MFA or second browser
session. The UI is strictly read-only and provides no authorize, consume, probe, retry, process,
schedule, connect, publish, dispatch, execute or mutate control.

### Governance Invariants

AI remains advisory-only. No AI agent or human may request, approve or consume this protected
workload lease or use it to operate infrastructure. The protocol is code-owned and is not exposed
as an AI, MCP or connector tool.

Active Directory remains authentication-only. This decision creates no Active Directory
management capability or Active Directory MCP. Normal authorized human reads require no mandatory
MFA or second browser session.

## Consequences

- Runtime start success cannot silently become readiness or network authority.
- Readiness eligibility is based on fresh protected-boundary evidence and exact current lineage.
- Replay and competing issuance are durable, observable and fail closed.
- The next readiness attempt can consume one bounded lease without receiving a reusable runtime or
  process locator.
- An additional authorization boundary increases implementation cost but preserves least privilege
  before the first readiness operation.

## Deferred Scope

- Readiness-authorization lease consumption and the protected readiness attempt
- Runtime resume, stop, restart, process creation, process control or scheduling
- Runtime or process locator reveal, copy, download or export
- DNS, TLS, socket, proxy, network establishment or provider negotiation
- Endpoint or credential reveal, delivery, copy, download or export
- Connector, MCP, broker or provider SDK calls
- Publication, delivery, acknowledgement, retry, quarantine or receipt
- Worker delivery, dispatch, workflow transition or generic execution
- Infrastructure mutation
- Lease renewal, transfer, replacement, reissue or automatic recovery
- Human- or AI-initiated readiness control
- Active Directory management or an Active Directory MCP

## Validation

- Domain tests prove canonical policy, chronology, zero inherited authority and bounded lease state.
- Service tests prove replay-first ordering, fresh signed evidence, exact lineage and no prober or
  network I/O.
- PostgreSQL tests prove lock order, two database-time observations, composite lineage, one
  concurrent winner, append-only enforcement and guarded downgrade.
- API and frontend tests prove workload-only POST, password-session read-only GET, minimized
  `no-store` schemas, fail-closed production composition and zero operational controls.
- Full backend/frontend regression, Alembic single-head and round-trip validation, PostgreSQL CI,
  live desktop/mobile browser inspection, independent review, exact-head PR CI, SHA-locked merge
  and independent `main` CI are required for delivery.
