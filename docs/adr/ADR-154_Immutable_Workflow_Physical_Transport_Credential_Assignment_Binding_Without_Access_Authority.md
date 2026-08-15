# ADR-154: Immutable Workflow Physical Transport Credential-Assignment Binding Without Access Authority

- Status: Accepted
- Date: 2026-08-15
- Owners: Product Owner, Workflow Architecture, Security Architecture
- Governing documents: ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025,
  ATLAS-032, ADR-149, ADR-150, ADR-151, ADR-152, ADR-153

## Context

ADR-149 binds one workflow event lineage to one immutable physical route. ADR-153 separately
captures one deployment-owned credential-assignment revision that is compatible with the same
physical route snapshot. Neither record proves that the assignment was chosen for that workflow.

Credential-access authorization cannot infer this relationship from mutable deployment state,
route requirements, a protected endpoint artifact or caller-supplied credential metadata. Atlas
first needs an immutable workflow-scoped binding that joins the exact route binding and exact
credential-assignment snapshot while granting no access to either protected endpoint or credential
material.

## Decision

Atlas will persist one immutable `WorkflowEventPhysicalTransportCredentialAssignmentBinding` for
one exact:

- `WorkflowEventPhysicalTransportRouteBinding` and canonical digest;
- `EventPhysicalTransportRouteSnapshot` named by that route binding; and
- `EventPhysicalTransportCredentialAssignmentSnapshot` that names the same route snapshot.

Only a dedicated service workload authenticated for
`audience.workflow-physical-transport-credential-binder` may create a binding. Human sessions,
personal API credentials, AI agents, route or credential registries, endpoint resolvers,
publishers and workers cannot create, replace or remove one.

The request contains only the route-binding ID and digest, credential-assignment-snapshot ID and
digest, the code-owned policy digest and an idempotency key. The caller cannot provide a route,
credential profile, credential requirement, secret reference, store, broker, endpoint, protected
artifact, principal, privilege, lifetime, freshness decision or authority field.

### Binding Policy

The code-owned version 1 policy requires:

- the route binding to exist, remain `bound`, match its canonical digest and grant zero authority;
- the route snapshot named by the route binding to exist, remain `snapshotted`, match the binding's
  exact ID and digest and grant zero authority;
- the credential-assignment snapshot to exist, remain `snapshotted`, match its canonical digest
  and grant zero authority;
- one organization, environment and site scope across all three records;
- the assignment snapshot to name the exact route-snapshot ID, route ID, route revision and source
  route digest;
- exact credential-requirement profile, authentication-mechanism and principal compatibility with
  the route snapshot; and
- read-only least privilege with positive credential generation and rotation epoch.

The service does not consult the mutable credential-assignment registry. The binding records an
historical selection only; it does not claim that the selected assignment remains the current
head, active, unexpired or unrevoked. A later independent freshness admission must revalidate
those properties before any credential-access authorization is considered.

### Rotation And History

One route binding may have immutable bindings to different credential-assignment snapshot
revisions over time. The exact pair of route-binding ID and assignment-snapshot ID is unique and
can be bound only once. Rebinding the same pair by another identity or request fails closed.

Allowing append-only historical generations prevents credential rotation from requiring mutation
of prior evidence. This boundary does not choose which historical binding is current. The later
freshness boundary must compare one exact binding with the authoritative assignment head and deny
superseded generations.

### Persistence And Replay

Production requires durable PostgreSQL persistence and never falls back to process memory. The
repository locks the route-binding row, exact route-snapshot row and assignment-snapshot row in
that fixed order, reloads their payloads, recomputes every canonical digest and revalidates the
complete chain before atomically inserting the binding and idempotency claim.

Binding and claim rows are append-only. PostgreSQL rejects `UPDATE` and `DELETE`. Exact idempotent
replay is resolved from committed immutable history before source evidence is consulted. Reusing
an idempotency key for another request, changing a source digest, cross-scope evidence, chain
mismatch, nonzero authority, duplicate exact-pair selection or malformed persisted evidence fails
closed without a partial record.

Required intent and commit-authorization audits succeed before persistence. Completion audit is
written only after commit. If completion audit delivery fails, Atlas reports an outcome-uncertain
error while preserving the immutable binding and claim; exact replay recovers the committed
result. Audit metadata includes only stable binding/source IDs, scope, workload, result and
correlation. It contains no credential profile, requirement, target commitment, broker policy,
digest, endpoint, secret reference or provider detail.

### Record And Authority

The binding stores only:

- binding ID;
- route-binding ID and digest;
- route-snapshot ID and digest;
- credential-assignment-snapshot ID and digest;
- policy ID, version and digest;
- scope, binder subject, binding time and state `bound`;
- explicit zero-authority declarations; and
- canonical digest.

It contains no username, password, token, key, certificate, secret value, secret-store locator,
retrievable secret reference, target commitment, broker policy, raw endpoint, protected-artifact
handle or network coordinate. It is not a bearer capability and grants no route selection,
endpoint resolution, protected-artifact access, credential selection, access, brokerage,
resolution or delivery, network access, readiness probing, publication, delivery, dispatch,
execution or infrastructure mutation authority.

### Human Presentation

Authorized humans may inspect minimized read-only binding evidence through the existing normal
username/password session. No MFA, second login or authorized-browser-session prompt is added.
The API and UI show stable binding, route-binding and assignment-snapshot IDs, state, binding time
and an opaque integrity reference only. They expose no source or policy digest, credential profile
or requirement, target commitment, broker policy, endpoint, protected artifact, secret or
operational control.

## Consequences

- Workflow lineage gains an explicit immutable relationship to one credential-assignment
  generation without opening credential material.
- Credential rotation remains append-only and can create later historical bindings without
  rewriting prior evidence.
- Current-head, expiry and revocation decisions remain independently auditable rather than being
  hidden inside selection.
- An additional persistence, policy, workload identity, audit and UI boundary is required before
  credential-access authorization can be designed.

## Deferred Scope

- Credential-assignment current-head, rotation, expiry and non-revocation freshness admission
- Credential-access authorization or brokerage lease
- Credential or protected endpoint-artifact access
- Secret, key or certificate resolution and protected ephemeral delivery
- DNS, TLS, socket, proxy, broker metadata or runtime network establishment
- Readiness probes and provider health checks
- Publication, delivery, acknowledgement, retry, quarantine and receipts
- Worker dispatch, workflow execution and infrastructure mutation
- Human or AI credential selection, reassignment, reveal or download

## Validation

- Domain and application tests cover exact-chain validation, policy stability, multiple historical
  generations, exact-pair uniqueness, replay, idempotency conflict, competing identity, source
  drift, cross-scope evidence, audit ordering and zero authority.
- PostgreSQL tests cover fixed-order row locking, digest recomputation, atomic binding/claim
  insertion, concurrent exact replay, uniqueness, append-only triggers, rollback and no production
  memory fallback.
- Static and API tests reject credential, secret, target, broker, endpoint, protected-artifact,
  digest and operational fields from ordinary surfaces.
- Web tests prove read-only presentation, empty/error states, zero operational controls and no
  second-login, MFA or authorized-browser text.
- Full backend/frontend suites, Alembic single-head validation, real PostgreSQL CI, live browser
  inspection and exact-head GitHub CI are required before merge.
