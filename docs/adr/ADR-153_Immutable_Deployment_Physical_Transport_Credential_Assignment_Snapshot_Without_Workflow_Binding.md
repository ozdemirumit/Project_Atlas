# ADR-153: Immutable Deployment Physical Transport Credential-Assignment Snapshot Without Workflow Binding

- Status: Accepted
- Date: 2026-08-15
- Owners: Product Owner, Solution Architecture, Security Architecture
- Governing documents: ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025,
  ATLAS-032, ADR-148, ADR-149, ADR-150, ADR-151, ADR-152

## Context

ADR-152 produces a short-lived protected endpoint artifact after irreversible endpoint-resolution
lease consumption. That artifact contains no credential material and grants no credential or
network authority. The physical route snapshot records only the credential-requirement profile,
authentication-mechanism class and principal class expected by the route. It does not identify an
authoritative deployment credential assignment.

Credential access cannot be authorized safely from a requirement alone. Doing so would permit
credential substitution, cross-target reuse, privilege escalation or confused-deputy behavior.
Atlas first needs an independently immutable, deployment-owned snapshot of one exact active
credential-assignment revision. The snapshot must remain historical evidence only and must not
bind a credential to a workflow, reveal a secret reference or grant access to credential material.

## Decision

Atlas will add a dedicated physical-transport credential-assignment registry boundary. Only the
exact workload audience
`audience.workflow-transport-credential-assignment-registry` may create snapshots. Human browser
sessions, personal API credentials, AI agents, endpoint resolvers, publishers and workers cannot
create or select assignments through this boundary.

The workload request contains only:

- assignment ID and immutable assignment revision;
- canonical source-assignment digest;
- idempotency key; and
- authenticated workload scope and correlation context.

The caller cannot supply a route, credential profile, secret reference, store, broker, endpoint,
principal, authentication mechanism, privilege, lifetime, policy or authority field.

### Authoritative Source

A deployment-owned registry returns one exact active assignment revision. The source record binds:

- organization, environment and site scope;
- assignment ID and revision;
- route ID, route revision and source-route digest;
- credential-requirement profile ID, version and digest;
- opaque credential-profile ID, version and digest;
- authentication-mechanism, principal and privilege classes;
- opaque target-scope commitment;
- credential generation and rotation epoch;
- activation and expiry times plus explicit non-revoked state; and
- broker-policy ID, version and digest for a future independent brokerage boundary.

The source contains no password, token, key, certificate, username, secret value, vault path,
secret-store locator or retrievable secret reference. Its canonical digest covers every field.
Production requires a durable authoritative registry and durable snapshot repository; it never
falls back to process memory. Deployment automation may provide secret-free assignment revisions
through the validated `ATLAS_WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENTS` configuration contract;
startup synchronizes those immutable revisions into the durable workflow repository. Empty
production configuration remains fail-closed.

The append-only registry chooses one current head per assignment ID by the highest unique
`(rotation_epoch, credential_generation)` pair. A newer active head supersedes older revisions
without mutating them. A newer inactive or revoked head blocks all earlier revisions. Duplicate
head ranks are rejected as ambiguous in both memory and PostgreSQL adapters.

### Validation

Before persistence, Atlas verifies that:

- the workload subject, audience and scope are exact;
- the source ID, revision and digest match the request;
- the source assignment is active, not expired and not revoked at service time;
- the referenced physical route snapshot exists and exactly matches route ID, revision,
  source-route digest, credential requirement, authentication mechanism and principal class;
- the credential profile is least-privilege and compatible with the route requirement;
- credential generation and rotation epoch are positive and unambiguous;
- target scope and broker policy are present only as opaque, integrity-bound metadata; and
- no existing snapshot or idempotency record conflicts with the exact identity.

An exact idempotent replay is resolved from immutable snapshot history before current deployment
state is consulted. The historical snapshot is revalidated for canonical integrity, exact scope,
original subject and zero authority, but replay does not require the source assignment to remain
active, unexpired, unrevoked or present in current configuration. A new request still requires all
current source and route checks.

Snapshot creation does not claim that the assignment will remain current. Rotation, revocation,
expiry and authoritative-head freshness must be revalidated by a later independent admission
boundary before any credential-access authorization is issued.

### Persistence And Audit

Snapshots and request/idempotency records are append-only. The database enforces immutable rows,
unique assignment revision identity and deterministic idempotency. Exact replay returns the same
snapshot; reuse of an idempotency key for another request fails closed.

Required intent and commit-authorization audits succeed before persistence. The repository then
atomically commits the snapshot and idempotency claim. Only after that commit does Atlas write the
completion audit that truthfully reports creation. Audit records contain stable
assignment/snapshot IDs, scope, workload, policy outcome and correlation only. They contain no
credential-profile identity, credential requirement, target commitment, broker policy, digest,
secret reference or provider detail.

Intent or commit-authorization audit failure creates no snapshot. If completion audit delivery
fails after commit, Atlas reports an outcome-uncertain error while preserving the immutable
snapshot and claim; an exact retry recovers the committed snapshot and emits replay audit. History
listing is scope-based and does not disappear when deployment configuration rotates or removes the
source assignment.

### Authority

The snapshot is not a bearer capability. It grants none of the following:

- endpoint resolution or protected-artifact access;
- credential selection, access, brokerage, resolution or delivery;
- secret, key or certificate access;
- DNS, TLS, socket, proxy, broker or other network access;
- readiness probing or provider health checks;
- publication, delivery, acknowledgement, retry or quarantine;
- worker dispatch or workflow execution; or
- infrastructure mutation.

All authority declarations are explicitly false.

### Human Presentation

Authorized humans may inspect minimized read-only snapshot evidence through the existing normal
username/password browser session. No MFA, second login or authorized-browser-session prompt is
introduced. The API and UI show stable snapshot/assignment identity, source revision, lifecycle
state, credential generation, rotation epoch and timestamps only. They do not expose credential
profile or requirement identifiers, target commitments, broker policy, digests, usernames,
secrets, certificates, endpoints or operational controls.

## Consequences

- Credential requirements and authoritative credential assignments are separated explicitly.
- Later workflow binding can prove exact compatibility without selecting or opening a secret.
- Credential rotation and revocation remain visible as independent deployment state rather than
  silently mutating historical workflow evidence.
- The platform gains additional immutable records and deployment-registry integration work before
  any network operation is possible.

## Deferred Scope

- Binding a credential-assignment snapshot to a workflow, route binding, materialization result or
  protected endpoint artifact
- Credential-assignment current-head, rotation, expiry and non-revocation freshness admission
- Credential-access authorization or a brokerage lease
- Secret, key or certificate resolution and protected ephemeral delivery
- Protected endpoint-artifact access
- DNS, TLS, socket, proxy, broker metadata or runtime network establishment
- Readiness probes and provider health checks
- Publication, delivery, acknowledgement, retry, quarantine and receipts
- Worker dispatch and workflow execution
- Human or AI credential selection, reassignment, reveal or download

## Validation

- Domain and application tests cover exact workload identity, source digest, route compatibility,
  least privilege, expiry, revocation, replay, idempotency conflict, audit ordering and zero
  authority.
- PostgreSQL tests cover uniqueness, append-only triggers, deterministic replay, audit-before-
  commit authorization, post-commit completion audit, concurrent replay and no production memory
  fallback.
- CI executes a real PostgreSQL concurrent create/replay test and a latest-migration
  downgrade/upgrade round trip.
- API and UI tests reject credential, secret, target, broker, endpoint, digest and operational
  fields from ordinary surfaces.
- Full backend/frontend suites, Alembic single-head validation, live browser inspection and exact-
  head GitHub CI are required before merge.
