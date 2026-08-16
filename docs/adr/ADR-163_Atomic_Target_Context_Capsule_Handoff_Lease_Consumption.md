# ADR-163: Atomic Single-Use Protected Target-Context Capsule Handoff-Authorization Lease Consumption and Sealed Protected-Boundary Capsule Handoff Without Unsealing, Runtime, Execution or Infrastructure Mutation Authority

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-16 |
| Owners | Workflow Architecture, Deployment Architecture, Security Architecture, Identity Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-157, ADR-160, ADR-161, ADR-162 |

## Context

ADR-162 grants one exact code-owned consumer a one-second, single-use authorization to request a
later protected target-context capsule handoff. The lease is immutable and non-bearer. It does not
consume itself, retrieve or move the capsule, unseal protected material, deliver an endpoint or
credential, or grant network or runtime authority.

Atlas now needs the next smallest irreversible boundary. The exact lease must be consumed before
any protected-boundary handoff is attempted. A crash, timeout or uncertain result after that point
must never make the lease reusable. Ordinary application, persistence, audit, API and UI paths must
never receive capsule bytes, a retrievable locator, endpoint material, credential material or a
bearer capability.

The handoff is an internal transfer of one still-sealed capsule to the exact consumer boundary
already bound by ADR-161. It is not general delivery, dispatch, execution or infrastructure
mutation. A successful receipt is lineage evidence for a later independently authorized consumer
opening boundary; it is not authority to unseal or use the capsule.

## Decision

Atlas will implement one atomic
`WorkflowProtectedTransportTargetContextCapsuleHandoffConsumption` boundary. It irreversibly
consumes one exact ADR-162 lease, starts one handoff attempt, invokes one trusted sealed-capsule
handoff adapter only after durable claim commit, and appends one minimized terminal result when the
outcome is trustworthy.

Only `service.workflow-protected-transport-target-context-capsule-consumer` authenticated for
`audience.workflow-protected-transport-target-context-capsule-consumer` may request consumption of
its own lease. The authenticated subject and audience must equal the values bound into the lease.
Human sessions, personal tokens, AI agents, binders, openers, publishers and all other workloads
fail closed.

The request contains only:

- handoff-authorization lease ID and canonical digest;
- code-owned consumption policy ID and version;
- `irreversible_consumption_acknowledged = true`;
- `uncertain_outcome_requires_new_authorization_acknowledged = true`; and
- idempotency metadata.

Atlas derives scope, consumer binding, capsule lineage, source protected-store identity, exact
consumer boundary, lifecycle evidence, deadlines, adapter identity and receipt contract from
authenticated context and authoritative server-side state. The caller cannot provide or override
capsule, source, destination, locator, endpoint, credential, route, assignment, outbox, event,
attestor, handoff adapter, TTL, unsealing, delivery, network or runtime fields.

### Authority Separation

The ADR-162 lease remains append-only. Effective consumption is derived from one unique claim,
never by updating the lease.

The claim, attempt and result contain the dedicated
`target_context_capsule_handoff_authority_granted` declaration and all existing 17 operational
authority declarations. Every declaration is exactly false. The dedicated authority existed only
on the unconsumed lease and is exhausted by the claim.

`sealed_capsule_handed_off = true` is historical outcome evidence. It is not protected-artifact
access, credential delivery, network, readiness, publication, general delivery, dispatch,
execution or infrastructure-mutation authority. The receipt and its identifiers are non-bearer.

### Fresh Time-Of-Use Evidence

Before opening the database transaction, Atlas obtains two independently signed, nonce-bound and
metadata-only attestations:

- capsule lifecycle and handoff eligibility for the exact lease, binding and sealed capsule; and
- consumer-boundary acceptance eligibility for the exact subject, audience, contract, purpose,
  capsule schema, destination-boundary identity, deployment identity, generation, fencing token,
  custody contract and approved adapter profile.

Before either attestor is called, Atlas performs a durable exact-replay preflight. An existing
trustworthy terminal result is returned directly. An existing matching claim or attempt returns
`pending` before its immutable handoff deadline and `handoff_outcome_uncertain` at or after that
deadline. Replay performs no attestor or adapter call. Only a request with no matching durable
claim proceeds to fresh attestation; the transaction repeats replay classification under lock to
close races.

Neither attestation may contain capsule bytes, a protected-store locator, destination coordinate,
endpoint, credential, secret, bearer token or provider payload. Unavailable, unsigned, malformed,
expired, mismatched, revoked, destroyed, already handed-off or negative evidence fails closed.

The consumer-boundary attestation must also bind the approved adapter ID/version, verification
signing-key ID and trusted destination-profile digest. These values are server-derived from the
code-owned trusted destination and adapter profile; callers cannot supply them. Attestations are
verified before the transaction and again offline while locks are held. No
protected-store, handoff adapter, broker, DNS, TLS, socket, proxy, provider or other external I/O
may occur inside the database transaction.

### Atomic Transaction And Point Of No Return

The PostgreSQL implementation follows the canonical ADR-162 lock and fence order. One transaction
locks and revalidates the complete target-context materialization, pending event, route,
credential-assignment, opening, consumer-binding and handoff-authorization lineages; the exact
fresh attestations; any prior claim, attempt or result; and the scoped idempotency claim.

PostgreSQL evaluates database time after locks are held. The exact destination identity,
deployment, generation, fence, custody contract, adapter profile, verification key and trusted
profile digest must match the server-derived trusted profile. The one-second lease, capsule,
consumer-binding, opening, outbox, route, assignment and both attestation deadlines must still be
valid and agree exactly. Cancellation, publication, quarantine, supersession, ambiguity, drift,
expiry, revocation, destruction, prior handoff or integrity failure fails closed.

The started attempt stores one immutable `handoff_deadline`, equal to or earlier than the minimum
of the lease, capsule, binding, opening, protected-material and both attestation deadlines. The
code-owned policy requires a minimum remaining handoff budget at claim commit and never extends or
shortens an expired source to manufacture eligibility. The deadline, destination profile and exact
adapter contract are included in the attempt canonical digest.

Code-owned consumption-authorization audit evidence is stored with the claim in the same
transaction. Atlas then reads database time again and repeats all database-resident currentness,
integrity and deadline checks. The transaction atomically appends exactly one consumption claim
and one started attempt. That commit is the irreversible point of no return.

A rollback or validation failure before commit leaves the lease unconsumed and no adapter is
called. After commit, every failure or uncertainty leaves the lease permanently consumed. SIEM or
external audit export occurs only after durable commit and is never the source of truth.

### Trusted Sealed-Capsule Handoff

After claim commit, one trusted adapter receives only protected-boundary references derived from
the committed attempt. It verifies the sealed capsule and exact destination commitments inside the
protected boundary, transfers the capsule without unsealing or decrypting it, and returns a signed,
minimized receipt.

The adapter instruction contains the immutable handoff deadline, exact destination identity,
deployment, generation, fence, custody contract, adapter contract, verification key and trusted
profile digest. The adapter must validate those commitments and protected-boundary time
immediately before movement. It must not begin or report success at or after the deadline.

The receipt binds the same destination and adapter commitments and may identify the opaque attempt
and consumer-receipt lineage, schema/profile, completion time, `usable_until`, source-retention or
cleanup state and canonical integrity. It contains no capsule contents, locator, endpoint,
credential, secret, destination coordinate, access token or provider payload. The consumer receipt
ID is evidence, not a bearer capability.

Production fails closed without an approved trusted adapter, protected store and destination
boundary. Development may use a deterministic synthetic adapter that validates fixed commitments
and emits receipt metadata while performing no filesystem, process, provider, network, delivery,
dispatch, execution or infrastructure operation.

### Outcomes, Replay And Recovery

A verified receipt completed strictly before `handoff_deadline` appends one `handed_off_sealed`
result. A known adapter rejection appends
one minimized `handoff_failed` result only when the signed receipt proves no handoff occurred and
cleanup state is trustworthy. Timeout, crash, invalid or late receipt, persistence ambiguity,
audit uncertainty, destination uncertainty or cleanup uncertainty produces
`handoff_outcome_uncertain`.

Success and known-failure results require a trusted signed receipt. For an observed timeout,
invalid receipt or other local uncertainty, Atlas may append a distinct code-owned uncertainty
result that explicitly contains no trusted receipt. A process crash may leave only the durable
claim and started attempt. Reads and exact replay derive `pending` while database time is before
the immutable handoff deadline and derive `handoff_outcome_uncertain` at or after it; a derived
uncertain view has no fabricated receipt and no completion timestamp.

After claim commit Atlas never retries the adapter, restores the lease, creates a replacement
claim or issues a second handoff for the same lease, binding or capsule. Exact replay returns the
same minimized result. Claim-only or started-attempt replay returns the same uncertain state and
performs no external call. Changed replay or competing consumption fails closed.

Success, known failure and uncertainty require a new consumer-side authorization boundary before
any unsealing or runtime use. No result authorizes automatic operational action.

### Durable Persistence

Production uses PostgreSQL and has no memory fallback. It stores three append-only groups:

- handoff lease-consumption claims, unique by lease, consumer binding and sealed capsule;
- handoff attempts, unique by claim and exact trusted adapter/destination contract, with immutable
  handoff deadline; and
- handoff results, unique by attempt, distinguishing trusted signed receipt evidence from explicit
  code-owned receipts-free uncertainty evidence.

Database constraints enforce code-owned identities, policy, acknowledgements, one claim per lease,
one attempt per claim, one result per attempt, canonical integrity, non-bearer declarations and all
18 authority fields as false. Triggers reject updates and deletes. Downgrade fails closed while
any table contains evidence.

### API And Human Presentation

The workload command is:

`POST /api/v1/workflows/physical-transport-target-context-capsule-handoffs`

Authorized humans may inspect a separate minimized read-only inventory through:

`GET /api/v1/workflows/physical-transport-target-context-capsule-handoffs`

Human reads use the existing normal username/password browser session and require no MFA, second
login or authorized-browser-session prompt. Responses are `no-store` and omit lease, binding,
capsule, attestation, source, destination, route, assignment, protected-store, idempotency and
internal fence material.

The UI exposes only minimized attempt/result identity, state, timestamps, consumer contract and
purpose references, adapter contract, policy reference, all-false authority declarations and a
non-sensitive integrity reference. It provides no consume, retry, handoff, reveal, unseal, decrypt,
copy, download, deliver, connect, probe, publish, dispatch, execute or mutate control.

## Consequences

- One durable claim consumes the handoff lease before any protected-boundary transfer is attempted.
- Crash or uncertainty cannot make a used authorization reusable.
- The capsule remains sealed and absent from ordinary application, persistence and presentation.
- A successful handoff proves only non-bearer consumer lineage and grants no runtime authority.
- A later independently authorized consumer opening boundary remains mandatory.

## Deferred Scope

- Consumer-side capsule access, retrieval, opening, unsealing or decryption
- Endpoint or credential reveal, injection, copy, download or export
- DNS, TLS, socket, proxy, network establishment or readiness probing
- Broker, transport-provider or provider SDK calls outside the trusted protected boundary
- Event publication, acknowledgement, retry, quarantine release or source cleanup workflows
- Worker dispatch, workflow state transition, execution or infrastructure mutation
- Automatic retry, lease renewal, replacement or reissue
- Human- or AI-initiated handoff or runtime use
- Active Directory management or an Active Directory MCP; AD remains authentication-only

## Validation

- Domain/application tests cover exact identity, caller-field prohibition, acknowledgements,
  database-time validity, unique consumption, exact/changed replay, known failure, uncertainty,
  late/invalid receipt, all-false authority and no automatic retry.
- Attestor and adapter tests cover signed nonce-bound metadata, exact lineage, negative states,
  sealed-only transfer, minimized receipt, cleanup uncertainty and no raw capsule return.
- PostgreSQL tests cover canonical lock/fence order, second database-time validation, atomic
  claim/attempt commit, concurrency, append-only enforcement, guarded downgrade, outcome
  persistence and no production memory fallback.
- API/UI tests cover workload-only POST, normal-session minimized GET, non-oracle errors,
  `no-store`, zero operational controls and no MFA, second login or authorized-browser prompt.
- Full backend/frontend suites, Alembic single-head and round-trip validation, real PostgreSQL CI,
  live desktop/mobile inspection, exact-head PR CI, SHA-locked merge and independent main CI are
  required.
