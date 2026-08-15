# ADR-155: Immutable Workflow Physical Transport Credential-Assignment Freshness Admission Without Access Authority

- Status: Accepted
- Date: 2026-08-15
- Owners: Product Owner, Workflow Architecture, Security Architecture
- Governing documents: ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025,
  ATLAS-032, ADR-150, ADR-153, ADR-154

## Context

ADR-154 binds one workflow physical route lineage to one immutable credential-assignment snapshot.
That binding proves historical selection only. It does not prove that the selected assignment
revision is still the deployment registry's unique current head, active, unexpired and unrevoked
when a later credential-access authorizer evaluates it.

Treating the immutable binding or its original snapshot state as current would permit a rotated,
expired or revoked credential assignment to reach a future brokerage boundary. Reading only one
mutable assignment revision would also miss a later head and leave a time-of-check/time-of-use
race. Atlas therefore needs a separate bounded freshness admission before any credential-access
authorization can be designed.

## Decision

Atlas will persist one immutable
`WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission` for one exact:

- `WorkflowEventPhysicalTransportCredentialAssignmentBinding` and canonical digest;
- `EventPhysicalTransportCredentialAssignmentSnapshot` named by that binding; and
- authoritative current `DeploymentPhysicalTransportCredentialAssignment` registry head for the
  same assignment ID.

The deployment credential-assignment registry is append-only. Its unique current head is selected
from all revisions of one assignment ID by the strict maximum `(rotation_epoch,
credential_generation)` rank. Duplicate ranks, malformed rows or more than one candidate at the
maximum rank are ambiguity and fail closed. The current head must exactly match the bound
snapshot's assignment revision and source-assignment digest. A later higher rank therefore
supersedes the historical binding without mutating it.

Only a dedicated service workload authenticated for
`audience.workflow-physical-transport-credential-assignment-freshness-admitter` may create an
admission. Human sessions, personal API credentials, AI agents, route or credential binders,
credential registries, brokers, publishers and workers cannot create, renew, replace or remove
one.

The request contains only the credential-assignment-binding ID and digest, code-owned policy ID
and version, and an idempotency key. The caller cannot provide assignment revision, generation,
rotation epoch, lifecycle state, TTL, credential, secret, broker, endpoint, principal, privilege,
target, readiness or authority fields.

### Freshness Policy

The code-owned version 1 policy requires:

- the credential-assignment binding to exist, remain `bound`, match its recomputed canonical
  digest and grant zero authority;
- the exact assignment snapshot named by the binding to exist, remain `snapshotted`, match the
  binding's ID and digest and grant zero authority;
- one organization, environment and site scope across binding, snapshot and registry head;
- one unambiguous current registry head selected by the strict maximum positive rotation epoch and
  credential generation;
- exact assignment ID, revision, source digest, route ID/revision/source digest, requirement
  profile, authentication mechanism, principal class, read-only privilege, target commitment,
  credential profile and broker-policy evidence across snapshot and current head;
- the current head to be active, non-revoked and within `activated_at <= database time <
  expires_at`; and
- every source and result to retain zero operational authority.

The admission validity window is code-owned and at most 60 seconds. `valid_until` is the earlier
of the policy window and the current assignment's `expires_at`. A caller cannot extend it.
Lifetime alone never proves currentness: a future consumer must re-read the registry head while
holding the same assignment-scoped fence and reject a changed rank, revision, digest, active state,
revocation state or expiry.

### Persistence And Concurrency

Production requires durable PostgreSQL persistence and never falls back to process memory. The
transaction locks the immutable credential-assignment binding and exact assignment snapshot,
then acquires the assignment-ID advisory transaction fence before reading every registry revision.
Credential-assignment synchronization uses the same fence. The transaction recomputes all
canonical digests, selects and validates the unique head, obtains database time, and atomically
inserts the admission and idempotency claim. After required precommit audit returns, the same
transaction obtains database time again and revalidates the complete evidence and validity window
before insertion.

Admission and claim rows are append-only. PostgreSQL rejects `UPDATE` and `DELETE`. Multiple
bounded admissions may be evaluated for one exact credential-assignment binding over time, and
each idempotency claim names exactly one immutable result. Historical admission evidence remains
immutable after expiry, rotation or revocation.

Exact idempotent replay returns the same admission only while its validity window is open and the
locked registry head still exactly matches the recorded revision, digest, rank and lifecycle
state. Replay always enters the repository transaction, takes the same source locks and assignment
fence, and evaluates currentness with database time; application-clock validation alone is never
sufficient. Replay after expiry, rotation, deactivation or revocation fails closed. A new evaluation
requires a new idempotency key and, after rotation, a new snapshot and workflow binding for the new
assignment revision. Changed idempotent requests, competing identities, missing or cross-scope
evidence, ambiguous heads, source drift, policy mismatch and required audit failure fail closed
without a partial record.

Required intent and commit-authorization audits succeed before persistence. Completion audit is
written after commit. If completion audit delivery fails, Atlas reports an outcome-uncertain error
while preserving the committed immutable result; exact replay can recover it. Audit metadata uses
only stable IDs, scope, workload, result and correlation. It contains no credential profile,
target commitment, broker policy, digest, endpoint, secret reference or provider detail.

### Record And Authority

The admission stores exact binding and snapshot IDs/digests, assignment ID/revision/source digest,
credential generation and rotation epoch, lifecycle booleans and times, policy evidence, scope,
admitter identity, evaluation time, bounded validity, state `admitted_current`, explicit
zero-authority declarations and a canonical digest.

It contains no username, password, token, key, certificate, secret value, secret-store locator,
retrievable secret reference, target commitment, credential profile, broker-policy detail, raw
endpoint, protected-artifact handle or network coordinate. It is not a bearer capability and
grants no endpoint resolution, protected-artifact access, credential selection, assignment
binding, access, brokerage, resolution or delivery, network access, readiness probing,
publication, delivery, dispatch, execution or infrastructure mutation authority.

### Human Presentation

Authorized humans may inspect minimized read-only freshness evidence through the existing normal
username/password session. No MFA, second login or authorized-browser-session prompt is added.
The API and UI show only stable admission, binding and snapshot IDs, assignment revision,
generation and rotation epoch, the admission's immutable policy ID/version, state,
evaluation/expiry times and an opaque integrity reference. Historical policy versions remain
truthful after code-owned policy rotation. They expose no source or policy digest, credential
profile, target commitment, broker policy,
endpoint, protected artifact, secret or operational control.

## Consequences

- Rotated, expired, deactivated and revoked assignment revisions fail before credential access is
  considered.
- Freshness is a bounded observation tied to one exact registry-head rank and source digest, not a
  durable property of the immutable workflow binding.
- Append-only assignment history and immutable workflow evidence remain intact across rotation.
- A future credential-access authorization boundary must independently fence and revalidate this
  same head immediately before issuing any capability.
- Credential access, brokerage and secret delivery remain unavailable after this decision.

## Deferred Scope

- Credential-access authorization or brokerage lease
- Credential or protected endpoint-artifact access
- Secret, key or certificate resolution and protected ephemeral delivery
- DNS, TLS, socket, proxy, broker metadata or runtime network establishment
- Readiness probes and provider health checks
- Publication, delivery, acknowledgement, retry, quarantine and receipts
- Worker dispatch, workflow execution and infrastructure mutation
- Human or AI credential selection, reassignment, reveal or download

## Validation

- Domain and application tests cover exact-chain validation, unique current-head selection,
  positive monotonic rank, rotation, expiry, revocation, deactivation, bounded validity, replay,
  idempotency conflict, competing identity, source drift, cross-scope evidence, audit ordering and
  zero authority.
- PostgreSQL tests cover fixed-order row locking, assignment advisory fencing, concurrent head
  insertion, database-time lifecycle evaluation, atomic admission/claim insertion, uniqueness,
  append-only triggers, rollback and no production memory fallback.
- Static and API tests reject credential, secret, target, broker, endpoint, protected-artifact,
  private digest and operational fields from ordinary surfaces.
- Web tests prove read-only presentation, open/expired window presentation, empty/error states,
  zero operational controls and no second-login, MFA or authorized-browser text.
- Full backend/frontend suites, Alembic single-head validation, real PostgreSQL CI, live browser
  inspection and exact-head GitHub CI are required before merge.
