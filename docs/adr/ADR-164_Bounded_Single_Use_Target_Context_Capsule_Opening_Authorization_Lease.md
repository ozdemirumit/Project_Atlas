# ADR-164: Bounded Single-Use Consumer-Side Protected Target-Context Capsule Opening Authorization Lease Without Retrieval, Unsealing, Runtime, Execution or Infrastructure Mutation Authority

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-16 |
| Owners | Workflow Architecture, Deployment Architecture, Security Architecture, Identity Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-158, ADR-159, ADR-160, ADR-161, ADR-162, ADR-163 |

## Context

ADR-163 irreversibly consumes one exact ADR-162 handoff-authorization lease and may hand one
still-sealed protected target-context capsule to the exact consumer custody boundary. A successful
`handed_off_sealed` result and its signed receipt are immutable, non-bearer historical evidence.
They do not authorize retrieval, opening, unsealing, decryption, endpoint or credential use,
network access, runtime injection, dispatch, execution or infrastructure mutation.

Atlas now needs the next smallest authorization boundary before consumer-side opening can ever be
attempted. The exact consumer workload must be able to obtain one extremely short-lived lease that
authorizes only a future request to a separate opening-consumption operation. Issuance must prove
that the handoff result, consumer receipt, destination custody and complete target-context lineage
remain current without retrieving or opening the capsule.

Historical handoff success alone is insufficient. Destination custody may no longer be final or
trustworthy, the capsule may have expired, been revoked or been destroyed, the destination
deployment or fencing generation may have changed, the pending outbox may no longer be live, or
the route and credential-assignment heads may have drifted. Source-side physical deletion is not
a safe or portable prerequisite: Atlas instead requires explicit signed evidence that destination
custody is final and that the source can no longer authorize reuse of the handed-off capsule.

## Decision

Atlas will issue one immutable
`WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease` from one exact canonical
ADR-163 `handed_off_sealed` result. The lease authorizes only a future request to the separate
IMP-215 atomic opening-consumption boundary. It does not retrieve, open, unseal, decrypt, copy,
download, reveal, inject, connect to or use the capsule or its protected contents.

Only the exact code-owned consumer subject
`service.workflow-protected-transport-target-context-capsule-consumer` authenticated for
`audience.workflow-protected-transport-target-context-capsule-consumer` may request issuance for
its own handed-off capsule. The authenticated subject and audience must equal the consumer binding
and signed handoff receipt. Human sessions, personal access tokens, AI agents, binders, handoff
adapters, future openers, publishers, generic workflow services and every other workload fail
closed.

The request contains only:

- handoff result ID and canonical digest;
- code-owned opening-authorization policy ID and version; and
- idempotency metadata.

The caller cannot supply or override capsule, receipt, consumer, destination, source, custody,
lifecycle, attestor, lease lifetime, authority, opener, protected-store, locator, endpoint,
credential, route, assignment, outbox, event, network or runtime fields. Atlas derives every such
value from authenticated context, the canonical handoff lineage and authoritative server-side
state.

### Canonical Handoff Eligibility

Issuance accepts only one terminal, canonical `handed_off_sealed` result from ADR-163. The result
must have a trusted signed consumer receipt completed strictly before its immutable handoff
deadline. `handoff_failed`, `handoff_outcome_uncertain`, pending, claim-only, attempt-only, late,
unsigned, malformed, ambiguous or receipts-free evidence is ineligible.

The result, attempt and claim must agree on the exact consumed ADR-162 lease, ADR-161 consumer
binding, opening result, sealed capsule lineage, consumer subject and audience, destination
boundary, deployment, generation, fencing token, custody contract, approved handoff adapter,
verification key and trusted destination profile. Their canonical digests and append-only lineage
must verify without repair, inference or fallback.

### Fresh Destination Custody And Lifecycle Attestation

Before opening the database transaction, Atlas obtains one fresh, independently signed,
nonce-bound and metadata-only destination custody/lifecycle attestation from the trusted
destination boundary. No protected-store, attestor, adapter or network call may occur while the
PostgreSQL transaction is open.

The attestation canonically commits to:

- trusted attestor identity, signing-key ID and attestation profile version;
- exact handoff result, attempt, claim, consumer receipt and sealed-capsule lineage;
- exact consumer subject, audience, contract and code-owned purpose;
- exact destination boundary and deployment identity, generation and fencing token;
- exact custody contract, approved adapter profile and trusted destination-profile digest;
- the server-created nonce, observed time and validity deadline;
- sealed, usable, non-revoked, non-destroyed and non-bearer lifecycle declarations; and
- `destination_custody_final = true` and `source_reuse_authority_terminated = true`.

Custody finality means the exact destination has accepted durable responsibility for the capsule
and the source can no longer authorize another handoff or opening from its prior custody. It does
not require proof of source-side physical deletion. Source cleanup may remain false or unknown
when the attestation proves source reuse authority is terminated. Cleanup uncertainty that also
leaves reuse authority uncertain fails closed.

The attestation contains no capsule bytes, protected-store locator, destination coordinate,
endpoint, credential, secret, bearer token or provider payload. Unavailable, unsigned, malformed,
expired, mismatched, negative, revoked, destroyed, non-final or reuse-capable evidence fails
closed. Atlas verifies the captured attestation before the transaction and again offline while
canonical database locks are held.

### Atomic Currentness And Liveness Proof

One durable PostgreSQL transaction follows the canonical target-context lock and fencing order and
revalidates:

1. the complete endpoint and credential materialization and target-context binding lineages;
2. the pending outbox, event envelope and event byte-artifact lineage;
3. the authoritative current route-selection and credential-assignment heads and fences;
4. the opening claim, attempt, result and sealed capsule created by ADR-160;
5. the ADR-161 consumer binding and ADR-162 handoff-authorization lease;
6. the ADR-163 handoff claim, attempt, canonical result and trusted consumer receipt;
7. the captured destination custody/lifecycle attestation through offline verification;
8. any prior opening-authorization lease for the handoff result, consumer receipt or capsule; and
9. any existing scoped idempotency claim for the exact request.

All records must agree on organization, environment, site, plan, run, step, execution attempt,
target, event, route, assignment, opening, capsule, handoff, receipt, destination, consumer,
contract, purpose and policy. Cancellation, publication, quarantine, supersession, ambiguity,
expiry, revocation, destruction, destination drift, route drift, credential drift, custody-finality
loss, restored source reuse authority, incomplete audit lineage or canonical-integrity mismatch
fails closed.

Required intent and commit-authorization audit succeeds before persistence. PostgreSQL evaluates
authoritative time only after all locks are held. After precommit audit, Atlas obtains a second
database time and repeats all database-resident currentness, liveness, custody-finality,
canonical-integrity and full-window checks immediately before append. The captured attestation
must remain valid for the complete lease window at that second database time.

The transaction atomically appends the lease, scoped idempotency claim and code-owned canonical
authorization-audit evidence. It performs no external I/O. Production requires PostgreSQL and a
trusted custody/lifecycle attestor and has no process-memory, synthetic or permissive fallback.

### Lifetime, Single Use And Replay

The code-owned version 1 policy grants exactly one second from authoritative database time. Atlas
issues a lease only when the complete one-second interval fits inside the handoff result, consumer
receipt, capsule, consumer binding, protected material, assignment and attestation deadlines. It
never shortens, extends or backdates a lease to manufacture eligibility.

Each handoff result, consumer receipt and sealed capsule may produce at most one opening-
authorization lease. The lease begins only in `authorized_unconsumed` state and is append-only,
single-use, non-renewable, non-transferable and non-bearer. Expiry, custody drift or failed future
consumption cannot create replacement, renewal or reissue authority.

Exact replay always obtains a fresh destination custody/lifecycle attestation, enters the durable
transaction, reacquires the same locks and fences, uses database time and repeats the complete
validation. It returns the same minimized lease only while the lease and every source remain
current and valid. Changed request, competing subject, different idempotency key for the same
lineage, expired lease, stale receipt, destination drift, lost custody finality or changed source
reuse authority fails closed and cannot create a second lease.

Completion audit follows commit. If completion audit fails, the committed lease remains
authoritative and cannot be duplicated. The caller receives an outcome-uncertain response until
an exact, still-valid replay recovers the minimized record.

### Authority Contract

The lease adds one dedicated narrow declaration:

- `target_context_capsule_opening_authorized = true`.

This value means only that the exact consumer workload may later request IMP-215 consumption of
this exact lease while every bound source and deadline remains valid. The lease is not a bearer
capability and cannot be presented directly to a protected store or trusted opener.

The prior dedicated declaration remains exactly false:

- `target_context_capsule_handoff_authorized = false`.

All existing 17 operational authority declarations remain exactly false:

- endpoint resolution;
- route selection;
- route binding;
- credential selection;
- credential-assignment binding;
- credential access;
- credential brokerage;
- credential resolution;
- protected-artifact access;
- credential delivery;
- network access;
- readiness probing;
- publication;
- delivery;
- dispatch;
- execution; and
- infrastructure mutation.

Issuance performs no capsule retrieval, protected-store opening, unsealing, decryption, copy,
download, endpoint or credential reveal, runtime-context creation or injection, broker call, DNS,
TLS, socket, proxy, provider SDK call, readiness probe, publication, dispatch, execution or
infrastructure mutation.

### Persistence And Database Enforcement

Lease and claim tables are append-only. Database triggers reject `UPDATE` and `DELETE`. Unique
constraints prevent more than one lease for a handoff result, consumer receipt or sealed capsule
and prevent a conflicting scoped idempotency claim.

Composite foreign keys bind each lease to the exact ADR-163 result, attempt and claim lineage and
to its upstream handoff lease, consumer binding and opening result. Database CHECK constraints
enforce code-owned workload identity and policy, exact one-second lifetime,
`authorized_unconsumed` state, single-use, non-renewable, non-transferable and non-bearer
declarations, the one true opening authority, the false handoff authority and all 17 operational
authority fields as false. Downgrade fails closed while either append-only table contains evidence.

An insertion race or uniqueness failure is classified only in a new transaction that reacquires
the canonical locks and revalidates exact replay or conflict. Partial state is never repaired by
mutating history.

### API And Human Presentation

The workload command is:

`POST /api/v1/workflows/physical-transport-target-context-capsule-opening-authorization-leases`

Only the exact consumer workload may call POST. Human sessions, personal tokens and AI identities
are denied. Authorized humans may inspect a separate minimized inventory through:

`GET /api/v1/workflows/physical-transport-target-context-capsule-opening-authorization-leases`

Human reads use the existing normal username/password browser session and a dedicated read
permission. No MFA, second login or authorized-browser-session prompt is required. Every command,
query and error response is `no-store`, minimized and non-oracle.

The human response exposes only a non-sensitive lease identity, immutable state, issue and expiry
times, consumer contract and purpose references, destination custody-profile reference, minimized
policy reference, single-use/non-renewable/non-transferable/non-bearer declarations, explicit
authority declarations and a non-sensitive integrity reference. It omits capsule, receipt,
binding, opening, artifact, source, destination, attestation, route, assignment, idempotency,
request-fingerprint and internal fencing material.

The UI section is titled `Target-context capsule opening authorization leases` and is strictly
read-only. It provides no issue, renew, retry, consume, retrieve, open, reveal, unseal, decrypt,
copy, download, inject, connect, probe, publish, dispatch, execute or mutate control.

## Consequences

- One exact consumer receives a narrow one-second authorization for a future opening-consumption
  request without gaining access to the capsule or its contents.
- Fresh destination custody/lifecycle evidence prevents historical handoff success from being
  treated as present custody or opening eligibility.
- Explicit custody finality terminates source reuse authority without requiring source-side
  physical deletion as a prerequisite.
- The dedicated opening declaration does not broaden handoff or any operational authority.
- IMP-215 remains mandatory before any consumer-side opening can occur.

## Deferred Scope

- Lease consumption and irreversible consumer-side opening under IMP-215
- Capsule retrieval, protected-store access, opening, unsealing or decryption
- Endpoint or credential reveal, delivery, copy, download, export or runtime injection
- Runtime-context handle creation or use
- DNS, TLS, socket, proxy, network establishment or readiness probing
- Broker, opener, provider SDK or connector capability calls
- Event publication, delivery, acknowledgement, retry or quarantine release
- Worker dispatch, workflow state transition, execution or infrastructure mutation
- Automatic retry, lease renewal, replacement or reissue
- Human- or AI-initiated issuance, opening or runtime use
- Active Directory management or an Active Directory MCP; AD remains authentication-only

## Validation

- Domain and application tests cover canonical `handed_off_sealed` eligibility, exact workload,
  caller-field prohibition, one-second lifetime, one-true/eighteen-false authority and no access.
- Attestor tests cover signed nonce-bound destination custody/lifecycle evidence, exact lineage,
  custody finality, terminated source reuse authority, fresh replay and negative states without
  sensitive payloads.
- PostgreSQL tests cover canonical lock order, second database time, concurrent issuance, one lease
  per result/receipt/capsule, exact and changed replay, append-only enforcement, composite lineage,
  guarded downgrade and no production fallback.
- API and security tests cover workload-only POST, session-only GET, personal-token/human/AI denial,
  `no-store`, non-oracle errors and strict minimized schemas.
- UI tests cover loading, empty, denied and unavailable states, strict schema validation, normal
  username/password access and zero issue/open/retry/reveal/unseal/execute controls.
- Isolation tests prove the issuance path cannot reach a protected store, opener, connector,
  broker, DNS, TLS, socket, dispatch, execution or infrastructure-mutation adapter.
- Full backend and frontend suites, Alembic single-head and round-trip validation, real PostgreSQL
  CI, live desktop/mobile inspection, exact-head PR CI, SHA-locked merge and independent main CI
  are required.
