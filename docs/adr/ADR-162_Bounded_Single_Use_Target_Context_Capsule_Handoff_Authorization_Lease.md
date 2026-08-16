# ADR-162: Bounded Single-Use Protected Target-Context Capsule Handoff Authorization Lease Without Retrieval, Unsealing, Transfer, Delivery or Runtime Authority

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-16 |
| Owners | Workflow Architecture, Event Platform, Security Architecture, Identity Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-158, ADR-159, ADR-160, ADR-161 |

## Context

ADR-161 binds one successful protected target-context opening result and its sealed capsule
lineage to one exact code-owned future consumer workload, audience, versioned contract and
purpose. That immutable binding has zero authority. It is not a lease, bearer capability,
handoff instruction or permission to retrieve or unseal the capsule.

Atlas now needs the next smallest authorization boundary before any protected-boundary handoff can
be attempted. The exact bound consumer must be able to receive one extremely short-lived
authorization to request a later, separate handoff-consumption operation. Issuance must prove that
the consumer binding, capsule lifecycle and complete transport lineage remain current without
retrieving, transferring, unsealing or exposing the capsule.

A lease based only on historical binding success would be unsafe. The capsule may have expired,
been revoked or destroyed; the outbox may have been cancelled, published or quarantined; the
physical route or credential assignment may have changed; or the consumer binding may no longer
retain enough lifetime for a complete authorization window. Treating the binding ID, capsule ID
or any digest as a bearer capability would also collapse evidence and authority into one reusable
identifier.

## Decision

Atlas will issue one immutable
`WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease` for one exact ADR-161
consumer binding and its server-derived sealed capsule lineage. The lease authorizes only a
future request to a separate atomic handoff-consumption boundary. It does not retrieve, open,
unseal, decrypt, copy, transfer, deliver or inject the capsule.

Only the exact code-owned consumer subject
`service.workflow-protected-transport-target-context-capsule-consumer` authenticated for
`audience.workflow-protected-transport-target-context-capsule-consumer` may request issuance for
itself. Human sessions, personal access tokens, AI agents, binders, openers, publishers, generic
workflow services and every other workload fail closed.

The request contains only:

- consumer-binding ID and canonical digest;
- the code-owned handoff-authorization policy ID and version; and
- idempotency metadata.

The caller cannot supply the capsule ID or digest, consumer identity, audience, contract, purpose,
scope, policy digest, lifetime, outbox, event, route, credential-assignment, protected-store,
attestor, endpoint, credential, broker, network, runtime or authority fields. Atlas derives every
such value from trusted server-side state.

### Fresh Capsule Lifecycle Attestation

Before opening the database transaction, Atlas obtains one fresh, independently signed,
metadata-only capsule lifecycle attestation from the trusted protected capsule store. The request
uses a server-created nonce. No protected-store or network call may occur while the PostgreSQL
transaction is open.

The attestation canonically commits to:

- trusted attestor identity and key version;
- the exact opening-result ID and digest;
- the exact consumer-binding ID and digest;
- the exact sealed-capsule ID, digest and schema version;
- the server-created nonce;
- observed and valid-until timestamps; and
- usable, non-revoked, non-destroyed, sealed and non-bearer lifecycle declarations.

It contains no capsule contents, retrievable locator, protected-store handle, endpoint,
credential, bearer token or provider payload. An unavailable, unsigned, malformed, expired,
mismatched or negative attestation fails closed.

The attestation is untrusted input until verified. Inside the durable transaction Atlas performs
only offline signature, canonical-integrity, nonce, identity, lineage, state and deadline
validation against the captured bytes and code-owned trusted key material. Issuance does not
remove the later time-of-check to time-of-use boundary; the future handoff consumer must obtain
and validate new lifecycle evidence.

### Atomic Currentness And Liveness Proof

One durable PostgreSQL transaction follows the canonical target-context lock and fencing order
and revalidates:

1. the exact target-context binding and both complete successful materialization chains;
2. the pending outbox, event envelope and event byte-artifact lineage;
3. the physical route binding, route snapshot and authoritative current route-selection head,
   generation and fencing token;
4. the credential-assignment binding and snapshot, assignment advisory fence and authoritative
   unique current assignment head;
5. the opening lease-consumption claim, opening attempt, terminal result and canonical opener
   receipt;
6. the exact ADR-161 consumer binding and its atomic authorization-audit claim;
7. the captured capsule lifecycle attestation through offline verification;
8. any prior handoff-authorization lease for the binding or capsule; and
9. any existing idempotency claim for the exact scoped request.

All records must agree on organization, environment, site, plan, run, step, execution attempt,
target, event, route, assignment, opening, capsule, consumer, contract, purpose and policy.
Expiry, revocation, destruction, cancellation, publication, quarantine, supersession, route
drift, credential drift, ambiguous current heads, incomplete audit lineage or canonical-integrity
mismatch fails closed.

Required intent and commit-authorization audit succeeds before persistence. PostgreSQL evaluates
`clock_timestamp()` only after the locks are held. After the precommit audit, Atlas obtains a
second database time and repeats all database-resident currentness, liveness, canonical-integrity
and full-window checks immediately before append. The pre-fetched attestation must remain valid
for the complete lease window at that second database time.

The transaction atomically appends the lease, scoped idempotency claim and code-owned canonical
authorization-audit evidence. It performs no external I/O. Production requires PostgreSQL and has
no process-memory fallback.

### Lifetime, Single Use And Replay

The code-owned version 1 policy grants exactly one second from authoritative database time. Atlas
issues a lease only when the complete one-second interval fits inside every applicable bound,
including the opening result and capsule deadline, consumer-binding effective deadline, capsule
lifecycle attestation deadline, protected material deadlines and credential-assignment expiry.
Atlas never shortens the lease to fit a smaller remaining window.

Each consumer binding and sealed capsule may produce at most one handoff-authorization lease. The
lease begins only in `authorized_unconsumed` state and is append-only, single-use, non-renewable
and non-transferable. Expiry does not permit replacement or renewal from the same binding or
capsule. Lease ID and digest are evidence, not bearer capabilities.

Exact replay always obtains a fresh capsule lifecycle attestation, enters the repository
transaction, takes the same locks and fences, uses database time and repeats the complete
validation. It returns the same minimized lease only while the lease and every source remain
current. A changed request, competing subject, different idempotency key for the same binding,
expired lease, lifecycle change or source drift fails closed and cannot create a second lease.

Completion audit follows commit. If completion audit fails, the committed lease remains
authoritative and cannot be duplicated. The caller receives an outcome-uncertain response until
an exact, still-valid replay recovers the minimized record.

### Authority Contract

The lease adds one dedicated narrow declaration:

- `target_context_capsule_handoff_authorized = true`.

This value means only that the exact consumer may later request a separate atomic, irreversible
handoff-consumption operation while every source and deadline remains valid. It is not general
delivery authority and must never be represented by `delivery_authorized`,
`credential_delivery_authorized` or `protected_artifact_access_authorized`.

The existing 17 authority declarations remain exactly false:

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

Lease issuance performs no capsule retrieval, protected-store opening, unsealing, decryption,
copy, transfer, delivery, runtime injection, endpoint or credential reveal, broker call, DNS, TLS,
socket, proxy, provider SDK call, readiness probe, publication, dispatch, execution or mutation.

### Persistence And Database Enforcement

Lease and claim tables are append-only. Database triggers reject `UPDATE` and `DELETE`. Unique
constraints prevent more than one lease for a consumer binding or sealed capsule and prevent a
second canonical result or conflicting scoped idempotency claim.

Database CHECK constraints enforce the code-owned consumer subject, audience, contract, purpose,
policy ID/version, exact one-second lifetime, `authorized_unconsumed` state, non-bearer,
single-use, non-renewable and non-transferable declarations, the dedicated single true handoff
authorization and all 17 existing authority fields as false. Downgrade fails closed while either
append-only table contains evidence.

An insertion race or uniqueness `IntegrityError` is classified only in a new transaction that
reacquires the canonical locks and revalidates replay or conflict. Partial state is never repaired
by mutating history.

### Human Presentation

Authorized humans may inspect a separate minimized read-only inventory through the existing
normal username/password browser session. No MFA, second login or authorized-browser-session
prompt is required.

Human API and UI responses expose only non-sensitive lease identity, scope, consumer contract and
purpose references, immutable state, issue and expiry times, single-use/non-renewable/
non-transferable declarations, minimized policy reference, explicit authority declarations and a
non-sensitive integrity reference.

They omit consumer subject internals, binding and capsule IDs or digests, opening and artifact
lineage, protected-store attestations or locators, endpoint, credential, outbox, route, assignment,
fence, idempotency, request fingerprint and source or policy digests. The UI provides no issue,
renew, retry, consume, handoff, reveal, unseal, copy, download, deliver, connect, probe, publish,
dispatch, execute or mutate control.

## Consequences

- One exact bound consumer receives a narrow one-second authorization without any capsule
  movement or exposure.
- Fresh lifecycle evidence prevents historical binding success from being treated as current
  capsule availability.
- A dedicated handoff declaration avoids broadening general delivery or artifact-access powers.
- One-lease-per-binding and one-lease-per-capsule rules prevent renewal and competing consumers.
- A later irreversible handoff-consumption boundary remains mandatory before the capsule can move
  or be used.

## Deferred Scope

- Handoff-lease consumption claim and actual protected-boundary capsule handoff
- Capsule retrieval, unsealing, decryption, transfer, copy, download or runtime injection
- Endpoint or credential reveal, delivery, copy, download or export
- DNS, TLS, socket, proxy, network establishment or readiness probing
- Broker, transport-provider or provider SDK calls
- Event publication, delivery, acknowledgement, retry, quarantine release or source cleanup
- Worker dispatch, workflow state transition, execution or infrastructure mutation
- Lease renewal, replacement or reissue
- Human- or AI-initiated issuance, handoff or runtime use
- Active Directory management or an Active Directory MCP; AD remains authentication-only

## Validation

- Domain and application tests cover exact consumer subject/audience, caller-field prohibition,
  code-owned one-second full window, single source use and the dedicated single-true authority.
- Attestor tests cover signed nonce-bound metadata, negative lifecycle states, key identity,
  expiry, lineage mismatch and no protected-store call inside a database transaction.
- PostgreSQL tests cover canonical lock order, all current heads and fences, second database-time
  validation, concurrent issuance, uniqueness, exact and changed replay, expiry, source drift,
  append-only enforcement, audit atomicity, rollback and no production memory fallback.
- API and UI tests cover workload-only issuance, default-deny minimized human reads, non-oracle
  errors, strict response keys, `no-store`, zero operational controls and normal username/password
  access without MFA, second login or an authorized-browser prompt.
- Full backend and frontend suites, Alembic single-head and round-trip validation, real PostgreSQL
  CI, live desktop/mobile inspection, exact-head PR CI, SHA-locked merge and independent main CI
  are required.
