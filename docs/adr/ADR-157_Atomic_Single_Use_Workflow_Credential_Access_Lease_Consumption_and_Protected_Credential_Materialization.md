# ADR-157: Atomic Single-Use Workflow Credential-Access Lease Consumption and Protected Credential Materialization

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-15 |
| Owners | Workflow Architecture, Deployment Architecture, Security Architecture, Identity Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-153, ADR-154, ADR-155, ADR-156 |

## Context

ADR-156 issues one exact-accessor, non-transferable, 15-second credential-access authorization
lease. The lease contains no credential material and grants no brokerage, resolution, protected
artifact access, delivery, network, dispatch, execution or mutation authority.

Atlas now needs the next irreversible boundary: consume that authority once and ask a trusted
internal component to materialize the exact deployment-owned credential without exposing secret
content to ordinary application code.

Consumption cannot follow protected materialization. A crash, timeout or uncertain protected-store
outcome could otherwise leave the lease reusable after a credential was opened. Ordinary
PostgreSQL persistence also cannot atomically commit protected-store content. The safe contract
therefore commits consumption before invoking a materializer and records completion separately.

## Decision

Atlas will implement one append-only credential-access lease consumption claim, one append-only
protected credential materialization attempt and, for a known outcome, one append-only minimized
materialization result.

Only the exact credential-accessor workload and audience bound into the lease may request
materialization. Human sessions, personal access tokens and all other workloads fail closed. The
request contains only:

- credential-access authorization lease ID and canonical digest;
- code-owned credential materialization policy ID and version;
- acknowledgement that consumption is irreversible and non-retryable;
- acknowledgement that an uncertain outcome requires investigation and new upstream freshness
  plus authorization; and
- idempotency and correlation metadata.

The caller cannot supply assignment, credential, username, secret reference, vault path, broker,
provider, target, endpoint, artifact, destination, TTL, timeout, retry, delivery, network or
execution fields.

### Atomic Point Of No Return

After required intent and consumption-authorization audit succeeds, one PostgreSQL transaction
locks and revalidates in fixed order:

1. physical-transport credential-assignment binding;
2. immutable credential-assignment snapshot;
3. assignment-scoped advisory fence and every deployment assignment revision;
4. credential-assignment freshness admission; and
5. credential-access authorization lease.

Database time is read using `clock_timestamp()` after all locks and fences are held. The exact
assignment revision must still be the unique highest rotation/generation head, active, unexpired
and unrevoked. Every immutable digest, scope, assignment identity, generation, rotation epoch,
lifecycle fact, policy identity, accessor identity and authority declaration must match. The lease
must satisfy `issued_at <= database_time < valid_until`, remain
`authorized_unconsumed`, grant credential access only and have no prior consumption claim.

The same transaction appends one unique consumption claim and one started attempt. A unique
constraint on authorization lease ID makes this commit the single point of no return. Claim,
attempt and lease rows are never updated, deleted, released, renewed or reopened. Effective
consumption is derived from the claim rather than mutating historical lease evidence.

An exact replay with a known terminal result returns the same minimized metadata. A claim without
a known result is outcome-uncertain and never invokes the materializer again. Changed replay,
another identity or a competing claim fails closed as already consumed or conflicting.

### Trusted Credential Materializer

Only after claim and attempt commit may the service invoke an approved
`WorkflowPhysicalTransportCredentialMaterializer`. Its instruction is server-owned and contains
trusted assignment lineage, accessor binding, attempt identity, policy limits and the consumed
lease deadline. It contains no caller-supplied credential or secret locator.

Inside the protected boundary the materializer must:

- resolve the exact deployment-owned credential source from sealed assignment and broker-policy
  lineage;
- verify credential profile, authentication mechanism, principal class, least privilege,
  rotation epoch, generation and source commitments;
- reject ambiguity, stale or revoked material, unsupported credential forms and policy overflow;
- create a short-lived encrypted protected artifact bound to the exact accessor, assignment and
  attempt outside ordinary application persistence;
- ensure the artifact is usable no later than the consumed lease deadline and revoke or destroy
  it on rejection, timeout, late completion or cleanup uncertainty; and
- return only a signed, minimized receipt.

The receipt may identify opaque protected artifact, assignment generation, materializer contract,
schema/profile, attempt, accessor, completion time, `usable_until`, cleanup/revocation state and
canonical integrity. It contains no username, password, token, key, certificate, secret reference,
vault path, broker coordinate, provider payload, endpoint, network coordinate or raw credential.
The protected artifact ID is lineage evidence, not a bearer capability.

Production fails closed without an approved trusted materializer and protected store. Development
may use a deterministic synthetic materializer that validates fixed commitments and emits receipt
metadata while performing no secret-store, filesystem, process, provider, network, delivery,
dispatch, execution or infrastructure operation.

### Outcomes And Audit

A verified timely receipt appends one `materialized_protected` result. Completion at or after the
lease deadline is rejected and the protected artifact must be revoked or destroyed.

A known adapter rejection appends a minimized `materialization_failed` result with a stable
code-owned failure class and no provider detail. Timeout, crash, invalid receipt, persistence
ambiguity, audit failure after consumption, cleanup uncertainty or protected-store uncertainty
leaves the claim authoritative and returns `materialization_outcome_uncertain`. Atlas never
retries automatically and never restores the lease.

Intent and consumption-authorization audit precede the point of no return. Completion, known
failure and uncertainty audit is append-only and contains no credential, secret locator, protected
artifact access token or provider payload.

### Authority And Human Presentation

Claim, attempt and result contain 17 explicit authority declarations and every value is exactly
false. Materialization proves a protected artifact outcome but grants no continuing credential
access, protected-artifact access, brokerage, resolution, delivery, endpoint, network, readiness,
publication, dispatch, execution or mutation authority.

Authorized humans may inspect minimized attempt/result metadata through the existing
username/password browser session. No MFA, second login or authorized-browser prompt is required.
The API and UI expose no credential content, source or policy digest, secret locator, broker
coordinate or artifact access and provide no consume, materialize, retry, reveal, copy, download,
deliver, dispatch or execute control.

## Consequences

- One durable claim permanently consumes one credential-access lease before any credential can be
  opened.
- Failure and uncertainty cannot make a lease reusable.
- Raw credential material remains outside ordinary domain, persistence, API, logs, audit and UI.
- A protected artifact remains short-lived, exact-accessor bound and unusable without a later
  independent authority boundary.
- New freshness and authorization are required after failure, uncertainty, expiry or source drift.

## Deferred Scope

- Protected endpoint artifact access and endpoint/credential target-context binding
- Credential artifact delivery, injection, reveal, copy or download
- DNS, TLS, socket, proxy, network establishment and readiness probes
- Publication, acknowledgement, retry, quarantine and delivery receipts
- Worker dispatch, workflow execution and infrastructure mutation
- Credential selection, reassignment, rotation or revocation

## Validation

- Domain/application tests cover identity binding, acknowledgements, DB-time validity, assignment
  fencing, single consumption, exact replay, conflict, success, known failure, uncertainty, late
  receipt, invalid receipt, cleanup uncertainty and audit failure.
- PostgreSQL tests cover fixed lock order, shared assignment advisory fencing, unique claim,
  atomic claim/attempt insertion, concurrent callers, append-only triggers, claim-derived
  consumption, rollback before claim and no production memory fallback.
- Adapter tests prove sealed-lineage input, bounded deadline, signed minimized receipt and no raw
  credential return.
- Static, API and UI tests reject secret, locator, provider, artifact-access and operational fields
  from ordinary surfaces and prove one normal username/password session is sufficient for reads.
- Full backend/frontend suites, Alembic single-head validation, real PostgreSQL CI, live browser
  inspection, exact-head PR CI, SHA-locked merge and independent main CI are required.
