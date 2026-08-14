# ADR-148: Immutable Deployment Physical Transport Route Snapshot Without Workflow Binding

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-14 |
| Owners | Event Platform, Deployment Architecture, Security Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-146, ADR-147 |

## Context

Atlas can prove that one exact logical workflow event channel is compatible with one immutable
deployment transport capability profile. A later physical binding also needs independently
immutable evidence for the deployment route it selects. Reading mutable route configuration during
binding would permit a time-of-check/time-of-use race and would make historical bindings
unverifiable.

The capability profile's `transport_resource_id` is not a physical route. It intentionally contains
no endpoint set, destination or routing contract. A route revision must therefore be captured as a
separate deployment-owned snapshot before any workflow event can bind to it.

## Decision

Atlas will persist one immutable `EventPhysicalTransportRouteSnapshot` for one exact active,
server-owned `DeploymentEventTransportRoute` revision. Route capture is independent of workflow
events, logical bindings and compatibility admissions.

The source route is injected by deployment/event-platform configuration and includes a normalized,
allowlisted descriptor:

- stable route, route-set and selection-epoch identities and immutable revisions;
- deployment release/profile and organization, environment and site scope;
- exact transport profile, resource, implementation and adapter identities, versions and digests;
- allowlisted route kind plus opaque endpoint-set, destination and routing-contract IDs and
  immutable revisions;
- one internal private-route-descriptor commitment that is never returned by human APIs;
- credential-requirement profile ID/version/digest, authentication-mechanism class and principal
  class, without any credential assignment or secret reference;
- transport-security policy ID/version/digest, minimum TLS version, server-authentication
  requirement, client-authentication requirement and plaintext-fallback prohibition;
- network policy ID/version/digest, source/destination zone classes, restricted-network
  enforcement, public-egress prohibition and allowlisted proxy mode; and
- active state and canonical source-route digest.

Opaque IDs are identifiers only. They are not URLs, locators, capability tokens, secret references
or values an adapter can use without a later privileged resolver. Raw hostnames, URLs, IP
addresses, namespaces, topics, streams, queues, partitions and routing keys are absent from domain,
API, audit and UI contracts. Field-level digests of those predictable values are also absent from
human APIs because they could enable dictionary attacks. The internal descriptor commitment and
canonical source/snapshot digests are C1 evidence and remain server-side or abbreviated where an
authorized human view needs integrity correlation.

Only a dedicated deployment-control workload authenticated for
`audience.workflow-transport-route-registry` may create a snapshot. Human sessions, workflow
publishers, compatibility admitters, profile registries, connectors and ordinary API tokens cannot
create, update, select or remove one. The request supplies exact route identity/revision/source
digest and one idempotency key; it cannot supply endpoint, destination, routing, credential,
network, readiness or publication fields.

The service reloads the exact route from the server-owned registry, recomputes its canonical digest
and validates active state, deployment scope, allowlisted identities/classes, policy digests and
security invariants. Version 1 requires TLS 1.3 or newer, server authentication, no plaintext
fallback, restricted-network enforcement and prohibited public egress. Exact replay returns the
same snapshot. Changed idempotent requests, competing registry identities, inactive or drifted
sources, ambiguous route identity, malformed policy evidence, scope mismatch and audit failure fail
closed and create no partial record.

The snapshot records the normalized source evidence, snapshot workload identity, capture time,
state `snapshotted` and canonical digest. It is not `compatible`, `selected`, `bound`,
`credentialed`, `ready`, `healthy`, `published` or `delivered`. Endpoint-resolution,
route-selection, route-binding, credential-access, network-access, readiness-probe, publication,
delivery, dispatch and execution authority flags all remain false.

Capture performs no DNS lookup, socket connection, TLS handshake, broker metadata query, secret
lookup, credential brokerage, provider SDK call or network request. Production persistence never
falls back to memory. Route revisions and snapshots are append-only; change creates a new revision
and snapshot rather than update or deletion.

Authorized humans may read minimized route snapshot evidence through the dedicated default-deny
`workflow.transport-route-snapshots.read` permission and the existing username/password browser
session. The UI abbreviates opaque references, omits the private descriptor commitment and exposes
no register, update, remove, bind, resolve, probe, credential, publish, deliver, dispatch or execute
control. It requires no second login or MFA.

## Consequences

- Deployment route metadata becomes immutable before any workflow event selects it.
- A later route-binding transaction can lock exact compatibility-admission, logical-binding,
  profile-snapshot and route-snapshot rows and recompute every digest.
- Credential requirements are frozen without selecting a credential; security and network
  requirements are frozen without claiming runtime enforcement or readiness.
- Route snapshotting proves no compatibility, selection, binding, endpoint reachability,
  credential availability, publish authorization or delivery.
- Route/profile drift requires a new immutable source revision and snapshot; historical evidence is
  never rewritten.

## Validation

- Domain and application tests cover normalized allowlisted manifests, policy digest stability,
  exact replay, changed requests, competing identities, source drift, inactive/ambiguous sources,
  scope mismatch, audit failure and zero authority.
- PostgreSQL tests cover immutable snapshot/idempotency persistence, uniqueness, append-only
  behavior and transaction rollback.
- Static tests reject raw endpoint, destination, routing, credential assignment, secret, network
  result, readiness, provider-message and publication fields.
- API tests prove deployment-workload-only creation, default-deny human read access, no-store
  responses and minimized C1 metadata without private commitments or field-level fingerprints.
- Web tests prove read-only route presentation, empty and error states, no operational controls and
  no second-login or MFA text.
- Full backend/frontend suites, Alembic single-head validation and live browser inspection are
  required before merge.
