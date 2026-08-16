# ADR-165: Atomic Single-Use Consumer-Side Target-Context Capsule Opening Lease Consumption Without Runtime, Delivery, Execution or Infrastructure Mutation Authority

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-16 |
| Owners | Workflow Architecture, Deployment Architecture, Security Architecture, Identity Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-159, ADR-160, ADR-161, ADR-162, ADR-163, ADR-164 |

## Context

ADR-164 grants the exact consumer workload one immutable one-second authorization to request a
later consumer-side opening of one handed-off sealed target-context capsule. The lease is
single-use, non-renewable, non-transferable and non-bearer. It does not consume itself, retrieve or
open the capsule, unseal protected material, create a runtime context, connect to a target or grant
delivery, dispatch, execution or infrastructure-mutation authority.

Atlas now needs the next smallest irreversible boundary. The lease must be durably consumed before
any trusted opener is called. A crash, timeout or uncertain outcome after that commit must never
make the lease, handoff receipt or capsule reusable. Raw capsule bytes, endpoint material,
credential material, retrievable coordinates and bearer capabilities must remain outside ordinary
application, domain, persistence, audit, event, API and UI paths.

A successful opening may establish one short-lived protected resident target-context lineage
inside the exact destination boundary. That lineage is historical evidence for a future separately
authorized runtime boundary. It is not a runtime handle, cannot be used by possession and grants no
network, provider, dispatch, execution or mutation authority.

## Decision

Atlas will implement one atomic
`WorkflowProtectedTransportTargetContextCapsuleOpeningConsumption` boundary. It irreversibly
consumes one exact ADR-164 opening-authorization lease, commits one append-only claim and started
attempt, calls one trusted consumer-boundary opener only after that commit, and appends one
minimized terminal result when the outcome is trustworthy.

Only the exact code-owned consumer subject
`service.workflow-protected-transport-target-context-capsule-consumer` authenticated for
`audience.workflow-protected-transport-target-context-capsule-consumer` may request consumption of
its own lease. The authenticated subject and audience must equal the values bound through the
ADR-161 binding, ADR-163 receipt and ADR-164 lease. Human sessions, personal tokens, AI agents,
binders, handoff adapters, openers, publishers and every other workload fail closed.

The request contains only:

- opening-authorization lease ID and canonical digest;
- code-owned opening-consumption policy ID and version;
- `irreversible_consumption_acknowledged = true`;
- `uncertain_outcome_requires_new_authorization_acknowledged = true`; and
- idempotency metadata.

The caller cannot provide or override capsule, receipt, handoff, destination, protected-store,
locator, attestor, opener, key, TTL, endpoint, credential, runtime, route, assignment, outbox,
network or authority fields. Atlas derives all such values from authenticated context, canonical
lineage, code-owned trusted profiles and authoritative server-side state.

### Immutable Lease And Authority Separation

The ADR-164 lease row is never updated. Effective consumption is derived from one unique
append-only claim.

The claim, attempt and result set both dedicated authorization declarations exactly false:

- `target_context_capsule_opening_authority_granted = false`; and
- `target_context_capsule_handoff_authority_granted = false`.

All existing 17 operational authority declarations are also exactly false. In particular, opening
success does not grant protected-artifact access, endpoint or credential delivery, network access,
readiness, publication, delivery, dispatch, execution or infrastructure mutation.

`capsule_opened_in_protected_boundary = true`, `target_context_pair_verified = true` and a
protected resident-context identity are historical outcome evidence only. The identity and digest
are non-bearer lineage and cannot authorize lookup, retrieval, injection or use.

### Durable Replay Preflight

Before any attestor or opener call, Atlas performs one durable replay lookup. An exact trustworthy
terminal result is returned directly. An exact matching claim or started attempt is presented as
`opening_pending` before its immutable deadline and `opening_outcome_uncertain` at or after that
deadline. Replay performs no attestor, protected-store, opener or network I/O.

A changed request, idempotency conflict, competing subject, mismatched digest or prior claim for
the lease, handoff, receipt or capsule fails closed. The transaction repeats replay classification
under canonical locks before creating new records.

### Fresh Time-Of-Use Evidence

Only when no durable claim exists, Atlas obtains two independently signed, nonce-bound and
metadata-only attestations before opening the database transaction:

- destination custody and capsule lifecycle evidence for the exact ADR-164 lease, ADR-163 handoff
  and receipt, sealed capsule and destination fence; and
- trusted consumer-side opener acceptance and openability evidence for the exact consumer,
  contract, purpose, capsule schema, protected resident-context profile, opener contract and
  verification key.

The destination attestation must prove the capsule remains sealed, usable, non-revoked,
non-destroyed and non-bearer; destination custody remains final; and source reuse authority remains
terminated. The opener attestation must prove that the exact destination generation and fence can
open only the bound capsule into the code-owned protected resident-context profile.

Both attestations bind the server-created nonce, observation time and validity deadline. They
contain no capsule bytes, protected-store locator, destination coordinate, endpoint, credential,
secret, bearer token or provider payload. Unavailable, unsigned, malformed, expired, mismatched,
negative, revoked, destroyed, non-final or reuse-capable evidence fails closed.

Atlas verifies both captured attestations before the transaction and again offline while locks are
held. No attestor, protected store, opener, DNS, TLS, socket, proxy, broker, provider or other
external I/O may occur inside the transaction. ADR-164 issuance evidence cannot be reused as
time-of-use evidence.

### Atomic Transaction And Point Of No Return

Production uses PostgreSQL and the canonical target-context lock and fencing order. One transaction
locks and revalidates:

1. the complete endpoint, credential, route, assignment and target-context materialization lineage;
2. the pending outbox, event envelope and event byte-artifact lineage;
3. the authoritative current route-selection and credential-assignment heads and fences;
4. the ADR-160 opening claim, attempt, result and sealed capsule;
5. the ADR-161 consumer binding;
6. the ADR-162 handoff lease and ADR-163 claim, attempt, result and signed consumer receipt;
7. the ADR-164 opening-authorization lease and its idempotency claim;
8. both fresh captured attestations through offline verification; and
9. any prior opening-consumption claim, attempt, result or scoped idempotency record.

All records must agree on organization, environment, site, plan, run, step, execution attempt,
target, event, route, assignment, opening, capsule, handoff, receipt, destination, consumer,
contract, purpose, policy, opener profile and canonical digests.

PostgreSQL evaluates authoritative time after all locks are held. The code-owned policy requires a
minimum remaining opening budget. The immutable `opening_deadline` cannot exceed the lease,
capsule, receipt, handoff, binding, protected material or either fresh attestation deadline.
Cancellation, publication, quarantine, supersession, ambiguity, expiry, revocation, destruction,
destination drift, route drift, credential drift, custody-finality loss, restored source reuse
authority or integrity failure fails closed.

Code-owned consumption-authorization audit evidence is stored with the claim. After precommit
audit, Atlas obtains a second database time and repeats database-resident currentness, integrity,
deadline and replay checks immediately before append. The transaction atomically appends exactly
one consumption claim and one started attempt. That commit is the irreversible point of no return.

A rollback or validation failure before commit leaves the lease unconsumed and no opener is
called. After commit, every failure, crash or uncertainty leaves the lease permanently consumed.
SIEM and external audit export occur after commit and are never the source of truth.

### Trusted Consumer-Boundary Opener

After claim commit, one trusted opener receives only protected-boundary references derived from the
committed attempt. It validates the exact capsule, destination generation and fence, custody
contract, opener contract, verification key, protected resident-context profile and immutable
opening deadline inside the protected boundary.

The opener may unseal and decrypt only the exact handed-off capsule. Endpoint and credential values
remain inside the trusted destination boundary and are never returned to application code,
persisted, logged, audited, published, indexed or exposed through an event, API or UI. A partial
opening must zeroize temporary material and cannot produce a resident context.

On complete pair verification, the opener may establish one short-lived protected resident target
context bound to the exact attempt, consumer, target-context commitment and destination fence.
Ordinary persistence stores only opaque non-bearer identity, canonical digest, trusted opener
identity, profile, creation time, `usable_until` and signed receipt metadata. It stores no
retrievable locator or access token. The resident context cannot be looked up or used without a
future independently authorized protected-boundary operation.

The opener must begin and complete before `opening_deadline`. `usable_until` cannot exceed the
capsule, handoff receipt, protected material, destination custody or code-owned resident-context
lifetime. Production fails closed without the approved trusted opener and protected destination.
A deterministic development adapter may emit fixed metadata only when explicitly test-enabled and
must perform no filesystem, process, provider, network, dispatch, execution or mutation operation.

### Outcomes, Replay And Recovery

A valid signed receipt completed strictly before `opening_deadline` may append:

- `opened_in_protected_consumer_boundary` only when the exact pair was verified and the protected resident
  context was established; or
- `opening_failed` only when the trusted receipt proves no resident context remains and temporary
  material was zeroized.

Timeout, crash, late or invalid receipt, partial opening, cleanup uncertainty, destination
uncertainty, persistence ambiguity or post-commit audit uncertainty produces
`opening_outcome_uncertain`. Atlas may append explicit code-owned receipts-free uncertainty for an
observed local failure. A process crash may leave only the durable claim and started attempt; reads
derive pending before the deadline and uncertainty afterward without fabricating a receipt or
completion time.

After claim commit Atlas never retries the opener, restores the lease, creates a replacement claim
or permits another opening for the same lease, handoff, receipt or capsule. Exact replay returns the
same minimized terminal or derived state without external I/O. Known failure and uncertainty do not
authorize automatic cleanup or operational action; any recovery requires a separately designed
human-governed boundary and new end-to-end lineage.

### Durable Persistence

Production stores three append-only groups:

- opening lease-consumption claims, unique by opening lease, handoff, receipt and capsule;
- opening attempts, unique by claim and exact destination/opener/profile contract, with immutable
  opening deadline and both attestation digests; and
- opening results, unique by attempt, distinguishing trusted signed receipt evidence from explicit
  code-owned receipts-free uncertainty evidence.

Composite foreign keys bind the claim and attempt to the exact ADR-164 lease and complete ADR-163
handoff/receipt/capsule lineage. Database CHECK constraints enforce the code-owned workload,
policy, acknowledgements, non-bearer declarations and all 19 authority fields as false. Triggers
reject `UPDATE` and `DELETE`. Downgrade fails closed while any table contains evidence.

Insertion races and uniqueness failures are classified only in a new transaction that reacquires
the canonical locks and revalidates exact replay or conflict. Partial state is never repaired by
mutating history. Production has no process-memory or permissive fallback.

### API And Human Presentation

The workload command is:

`POST /api/v1/workflows/physical-transport-target-context-capsule-openings`

Only the exact consumer workload may call POST. Human sessions, personal tokens and AI identities
are denied. Authorized humans may inspect a separate minimized inventory through:

`GET /api/v1/workflows/physical-transport-target-context-capsule-openings`

Human reads use the normal username/password browser session and a dedicated read permission. No
MFA, second login or authorized-browser-session prompt is required. Command, query and error
responses are `no-store`, minimized and non-oracle.

The human response exposes only non-sensitive attempt/result identity, immutable state, timestamps,
consumer contract and purpose references, opener/profile references, policy reference, the all-
false authority contract and a non-sensitive integrity reference. It omits lease, capsule, receipt,
binding, source, destination, attestation, resident-context identity, route, assignment,
idempotency, request-fingerprint and internal fencing material.

The UI section is titled `Target-context capsule openings` and is strictly read-only. It provides
no consume, open, retry, retrieve, reveal, unseal, decrypt, copy, download, inject, connect, probe,
publish, dispatch, execute or mutate control.

## Consequences

- One durable claim consumes the opening lease before the trusted opener can touch the capsule.
- Crash or uncertainty cannot make used authority reusable.
- Raw endpoint and credential material remains inside the exact consumer protected boundary.
- Success yields only non-bearer protected resident-context lineage and grants no runtime authority.
- Every later use still requires a separate policy and authorization boundary.

## Deferred Scope

- Endpoint or credential reveal, delivery, copy, download or export
- Runtime-context handle creation, access, injection or use
- DNS, TLS, socket, proxy, network establishment or readiness probing
- Broker, provider SDK or connector capability calls
- Event publication, acknowledgement, retry or quarantine release
- Worker dispatch, workflow state transition, execution or infrastructure mutation
- Automatic opener retry, lease renewal, replacement or reissue
- Autonomous cleanup, recovery or operational remediation
- Human- or AI-initiated opening or runtime use
- Active Directory management or an Active Directory MCP; AD remains authentication-only

## Validation

- Domain and application tests cover exact workload identity, caller-field prohibition,
  acknowledgements, unique consumption, exact/changed replay, pending, success, known failure,
  uncertainty, late/invalid receipt and all 19 authority fields as false.
- Call-order tests prove claim and started attempt commit before opener invocation and prove exact
  replay or claim-only recovery performs no attestor or opener call.
- Attestor and opener tests cover signed nonce-bound evidence, exact lineage, negative states,
  partial opening, zeroization, resident-context profile, late receipts and no raw material return.
- PostgreSQL tests cover canonical lock order, two database-time checks, concurrent unique winner,
  composite lineage, append-only triggers, crash state, guarded downgrade and no production
  fallback. The IMP-213 and IMP-215 live PostgreSQL behavior tests are explicit CI inputs.
- API and UI tests cover workload-only POST, session-only GET, personal-token/human/AI denial,
  `no-store`, non-oracle errors, minimized schemas and zero operational controls.
- Full backend/frontend suites, Alembic single-head and round-trip validation, real PostgreSQL CI,
  live desktop/mobile inspection, independent review, exact-head PR CI, SHA-locked merge and
  independent `main` CI are required.
