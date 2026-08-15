# ADR-160: Atomic Single-Use Target-Context Access Lease Consumption and Paired Protected Artifact Opening Without Delivery or Runtime Authority

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-15 |
| Owners | Workflow Architecture, Deployment Architecture, Security Architecture, Identity Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-152, ADR-157, ADR-158, ADR-159 |

## Context

ADR-159 grants one exact dedicated workload a five-second, single-use authorization to access the
protected endpoint and credential artifacts already paired by ADR-158. The lease is immutable and
authorizes only a later access attempt. It deliberately does not consume itself, open either
artifact, reveal an endpoint, deliver a credential or grant network or runtime authority.

Atlas now needs the next smallest irreversible boundary. The exact lease must be consumed before
any protected-store opener is called, and the endpoint and credential artifacts must be opened as
one inseparable target context inside a trusted protected boundary. Neither raw value may enter
ordinary application, domain, API, UI, audit, event or persistence paths.

The boundary must remain crash-safe. A process loss after an opener call cannot leave a reusable
lease, and a partial or uncertain paired opening cannot be retried under the consumed lease. A
successful opening must produce only a sealed, short-lived target-context capsule lineage. The
capsule is evidence for a later separately authorized boundary; it is not a bearer capability and
cannot itself authorize delivery, network activity or runtime use.

## Decision

Atlas will implement one atomic `WorkflowProtectedTransportTargetContextArtifactOpening` boundary.
It irreversibly consumes one exact ADR-159 lease, opens only the exact bound endpoint and credential
artifact pair in one trusted opener, and records append-only claim, attempt and result evidence.

Only the exact service subject
`service.workflow-protected-transport-context-accessor` authenticated for the exact audience
`audience.workflow-protected-transport-context-accessor` may request an opening for its own lease.
The authenticated subject must equal the subject immutably bound into the lease. Human sessions,
personal access tokens, AI agents and every other workload fail closed.

The request contains only:

- authorization lease ID and canonical digest;
- the code-owned opening policy ID and version;
- `irreversible_consumption_acknowledged = true`;
- `uncertain_outcome_requires_new_authorization_acknowledged = true`; and
- idempotency metadata.

Atlas derives correlation, scope, subject, target-context binding, both materialization outcomes,
artifact references, currentness evidence, attestation requirements, time limits, opener identity
and capsule properties from authenticated context and authoritative server-side state. The caller
cannot supply any binding, materialization, artifact, attestation, route, assignment, endpoint,
credential, TTL, capsule, opener, provider, delivery, network or runtime field.

### Immutable Lease And Authority Separation

The ADR-159 lease row is never updated. Its immutable authority contract remains unchanged: only
`protected_artifact_access_authorized` is true on the lease. Effective `consumed` state is derived
from the unique append-only consumption claim, not by mutating the lease.

The consumption claim, opening attempt and opening result each contain the following 17 explicit
authority declarations, all exactly false:

- `endpoint_resolution_authorized`;
- `route_selection_authorized`;
- `route_binding_authorized`;
- `credential_selection_authorized`;
- `credential_assignment_binding_authorized`;
- `credential_access_authorized`;
- `credential_brokerage_authorized`;
- `credential_resolution_authorized`;
- `protected_artifact_access_authorized`;
- `credential_delivery_authorized`;
- `network_access_authorized`;
- `readiness_probe_authorized`;
- `publication_authorized`;
- `delivery_authorized`;
- `dispatch_authorized`;
- `execution_authorized`; and
- `infrastructure_mutation_authorized`.

`endpoint_opened` and `credential_opened` are historical outcome evidence only. They are not
authority declarations and cannot be interpreted as endpoint reveal, credential delivery,
connection permission, readiness, publication, dispatch, execution or mutation authority.

### Fresh Protected-Store Evidence

Before opening the database transaction, Atlas obtains new independently signed, nonce-bound,
metadata-only status and openability attestations for both exact artifacts. The attestations are
specific to the lease, binding, materialization result, artifact kind, intended trusted opener,
server-created nonce, observation time and validity deadline. They contain no artifact contents,
endpoint coordinate, credential, secret, bearer token, retrievable locator or provider payload.

Attestations are untrusted input until verified. Their signature, canonical integrity, nonce,
trusted attestor identity, exact lineage, positive state and deadline are verified before the
transaction. The captured bytes are verified again offline inside the transaction against trusted
key material. No protected-store, opener, DNS, network or other external I/O may occur while the
database transaction is open.

Unavailable, unsigned, malformed, expired, mismatched, revoked, destroyed or non-openable
evidence fails closed. ADR-159 issuance attestations cannot be reused because the consumption and
opening boundary requires fresh time-of-use evidence.

### Atomic Transaction And Point Of No Return

The durable PostgreSQL implementation uses the same canonical lock and fencing order established
for ADR-159. One transaction locks and revalidates:

1. the exact target-context binding and both complete successful materialization chains;
2. the pending outbox record and its cancellation and liveness state;
3. the physical route binding, logical channel binding, route snapshot and authoritative current
   route-selection head, generation and fencing token;
4. the credential-assignment binding and snapshot, assignment-scoped advisory fence and every
   authoritative assignment revision needed to prove the unique current active head;
5. the immutable access lease and its exact scope, subject, audience, policy, digest, issue and
   expiry times;
6. both fresh captured attestations through offline canonical and cryptographic validation;
7. any prior consumption claim, opening attempt and terminal result for the lease; and
8. the scoped idempotency claim and canonical request fingerprint.

PostgreSQL evaluates `clock_timestamp()` after the locks are held. The lease, outbox, route head,
route generation and fence, credential-assignment head, rotation, revocation and expiry, target-
context overlap, both source artifact deadlines and both attestation deadlines must remain valid
and agree exactly. Cancellation, supersession, ambiguity, drift, expiry, revocation, destruction,
integrity failure or insufficient remaining time fails closed.

Required consumption-authorization audit is durably recorded before commitment. Atlas then reads
database time again and repeats every database-resident currentness, integrity and deadline check.
The transaction atomically appends exactly one consumption claim and one started opening attempt.
This commit is the irreversible point of no return. Only after the commit succeeds may Atlas call
the trusted opener. A database rollback, audit failure or validation failure before commit leaves
the lease unconsumed; no opener has been called.

### Trusted Paired Opener And Sealed Capsule

The trusted opener receives only protected-boundary references derived for the committed attempt.
It opens the endpoint artifact first and the credential artifact second inside one protected
boundary. It validates both artifact commitments against the attempt and creates no usable target
context unless both artifacts are successfully opened and verified.

Raw endpoint and credential values never leave the trusted opener boundary. They are not returned
to application code and are not persisted, logged, audited, published, indexed or exposed through
an event, API or UI. Partial opening requires immediate cleanup and zeroization inside the trusted
boundary.

After successful pair validation, the opener may produce one sealed target-context capsule bound
to the exact opening attempt, accessor workload and canonical target-context commitment. The
capsule contains or protects the pair only inside the trusted boundary. Ordinary persistence may
store only opaque capsule identity, canonical digest, trusted opener identity, creation time,
`usable_until`, cleanup or revocation state and signed receipt metadata.

Capsule identity is lineage, not a bearer capability. Possessing or reading its ID or digest does
not authorize opening, transfer, delivery, reveal, injection, network use, provider negotiation,
readiness probing, publication, dispatch, execution or infrastructure mutation. A later boundary
must independently authorize any handoff or use. `usable_until` cannot exceed the lease expiry,
either source artifact deadline, either fresh attestation deadline or the code-owned capsule
lifetime.

### Result, Failure And Replay

Atlas verifies the opener's signed receipt, attempt binding, target-context commitment, pair
status, capsule lineage and deadline before appending a terminal result. A known timely complete
pair produces `opened_protected`. A known opener rejection or confirmed cleanup after a failed
attempt produces `opening_failed`. The result includes no raw artifact, endpoint, credential,
secret, retrievable locator or bearer material.

The following replay and recovery rules are mandatory:

- Before claim commit, a failed validation or transaction leaves the lease unconsumed. A fresh
  request may be attempted only while the same lease and complete evidence remain valid, using new
  attestations.
- After claim commit, crash, timeout, process loss, opener uncertainty, audit uncertainty or
  persistence uncertainty leaves the lease permanently consumed.
- A claim with no trustworthy terminal result is `outcome_uncertain`. Atlas never calls the opener
  again for that lease and never creates a replacement claim or attempt.
- Exact replay with an existing trustworthy terminal result returns the same minimized result
  without opening either artifact again, even when the original lease has since expired.
- Exact replay with only a claim or started attempt returns the same minimized uncertain state and
  performs no external call.
- A changed request, idempotency key, subject, audience, policy or digest conflicts. A competing
  claim for the lease fails closed.
- Partial pair opening, invalid or late receipt, cleanup uncertainty, route or assignment drift
  after claim, or persistence uncertainty requires capsule cleanup or zeroization and remains
  uncertain unless a trustworthy terminal failure receipt proves cleanup.

Uncertainty never restores access authority and never permits automatic retry. A later attempt
requires new endpoint and credential materialization evidence, a new target-context binding and a
new access lease.

### Durable Append-Only Persistence

Production uses durable PostgreSQL persistence and has no memory fallback. It records three
append-only groups:

- `target_context_access_lease_consumption_claims`, uniquely binding the lease, target-context,
  exact subject and audience, scope, request fingerprint, idempotency claim and claim time;
- `target_context_artifact_opening_attempts`, uniquely binding the claim, exact endpoint and
  credential materialization lineage, attestation digests, internal currentness-evidence digest,
  code-owned policy, trusted opener and opening deadline; and
- `target_context_artifact_opening_results`, uniquely binding the attempt and signed receipt,
  terminal state, code-owned failure class, opaque capsule lineage, cleanup or revocation evidence
  and usable deadline.

There is at most one claim per lease, one attempt per claim and one result per attempt. Database
constraints and triggers reject updates and deletes. Canonical integrity is revalidated on read,
replay and result persistence. Sensitive internal currentness and attestation evidence is never
included in human presentation.

### API And Human Presentation

The workload command is:

`POST /api/v1/workflows/physical-transport-target-context-artifact-openings`

Its response is minimized to result identity and digest, state, non-sensitive times and the exact
zero-authority contract. Authentication, authorization and internal failures use non-oracle error
mapping, and every response is `Cache-Control: no-store`.

Authorized humans may query a minimized read-only inventory through:

`GET /api/v1/workflows/physical-transport-target-context-artifact-openings`

Human access uses the normal username/password browser session and a separate read permission. It
requires no MFA, second login or authorized-browser-session prompt. Human responses and UI omit
artifact and attestation identifiers or digests, capsule identity or digest, endpoint, credential,
secret, route, assignment, protected-store, idempotency and internal fence evidence.

The UI may show only minimized attempt/result identity, state, timestamps, accessor label, policy
reference and the zero-authority declaration. It provides no open, retry, reveal, copy, download,
deliver, connect, probe, publish, dispatch, execute or mutation control.

## Consequences

- One exact lease is consumed before any protected-store opener is called, so process failure
  cannot make a used authorization reusable.
- Endpoint and credential artifacts are opened only as one exact pair inside a trusted boundary;
  ordinary platform layers never receive either raw value.
- Append-only claim, attempt and result evidence makes success, failure and uncertainty auditable
  without mutating the lease.
- A sealed capsule preserves short-lived target-context lineage without becoming a capability or
  granting delivery, network or runtime authority.
- Claim-after-commit uncertainty intentionally sacrifices automatic retry to preserve single-use
  safety.
- A later independently authorized boundary remains necessary before capsule handoff or use.

## Deferred Scope

- Endpoint reveal, copy, download or delivery
- Credential delivery, injection, reveal, copy, download or runtime handoff
- Capsule handoff, unsealing, transfer or runtime consumption
- DNS, TLS, socket, proxy, network establishment or readiness probing
- Transport-provider negotiation, provider SDK calls or publication attempts
- Acknowledgement, retry, quarantine, delivery receipts or source-artifact lifecycle cleanup
- Worker dispatch, workflow state transition, workflow execution or infrastructure mutation
- Human- or AI-initiated artifact opening

## Validation

- Domain and application tests cover the exact workload subject and audience, code-owned policy,
  caller-field prohibition, immutable lease, unique claim, exact replay, changed replay, competing
  claims and the exact 17-field all-false outcome authority contract.
- Call-order tests prove claim and started attempt commit before the opener and prove no opener call
  after claim-only uncertainty.
- Attestation tests cover signature, nonce, trusted identity, exact lineage, deadline, negative
  state and the prohibition on external I/O inside the transaction.
- PostgreSQL tests cover lock/fence order, database time, outbox cancellation, route generation and
  fence drift, credential rotation, revocation and expiry, concurrent replay, append-only triggers,
  migration round trip and no production memory fallback.
- Opener tests cover endpoint-first pair opening, partial failure, zeroization, late or invalid
  receipt, capsule deadline bounds and cleanup uncertainty.
- API and UI tests cover exact workload-only commands, non-oracle errors, minimized schemas,
  `no-store`, zero operational controls and normal username/password reads without MFA, a second
  login or authorized-browser prompt.
- Full backend/frontend suites, Alembic single-head validation, real PostgreSQL CI, live desktop
  and mobile browser inspection, exact-head PR CI, SHA-locked merge and independent main CI are
  required.
