# ADR-146: Immutable Deployment Transport Capability Profile Snapshot Without Route Binding

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-14 |
| Owners | Event Platform, Deployment Architecture, Security Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-140, ADR-141, ADR-142, ADR-143, ADR-144, ADR-145 |

## Context

Atlas now binds exact workflow event bytes to an immutable logical publication contract. That
contract intentionally names no deployment transport implementation. A later compatibility
decision needs an independently immutable statement of what one deployment-owned transport
profile claims to support. Combining profile capture with logical-channel compatibility or route
binding would allow configuration capture to become an implicit publication decision.

## Decision

Atlas will persist one immutable `EventPhysicalTransportProfileSnapshot` for an exact active
server-owned deployment profile revision. The source profile is supplied by the deployment/event
platform configuration, not by browser input. Its normalized and allowlisted capability manifest
includes:

- stable profile, transport-resource, implementation and adapter-contract identities and versions;
- exact source-profile, transport-resource and adapter-contract digests;
- organization, environment and site scope plus deployment release and profile class;
- supported event contracts, classifications, representations and encodings;
- supported delivery semantics, durability, ordering-key kinds and retention classes;
- maximum message byte count, transport-encryption requirement and restricted-network support; and
- snapshot workload identity, capture time, immutable state and canonical digest.

Only a dedicated deployment-control workload authenticated for
`audience.workflow-transport-profile-registry` may create a snapshot. Human sessions, workflow
publisher workloads and connector workloads cannot create, update, select or remove it. Exact
replay returns the same snapshot; changed idempotent requests, competing identities, inactive or
changed source profiles, scope mismatch, malformed capability manifests and audit failure fail
closed. Production persistence never falls back to memory.

The snapshot state is `snapshotted`. It is not `compatible`, `selected`, `bound`, `ready` or
`healthy`. Every route-selection, publication, delivery, dispatch and execution authority flag is
false. Registration performs no DNS resolution, socket connection, TLS handshake, broker metadata
query, health probe, secret lookup or network call.

The snapshot contains no event, artifact, logical-channel binding, outbox, workflow, attempt or
lease lineage. It also contains no hostname, URL, IP address, broker endpoint, namespace, topic,
stream, queue, partition, routing key, credential or secret reference, vault path, certificate,
encryption-key reference, provider message, publication attempt, retry, receipt, acknowledgement,
offset or network-health result.

Authorized humans may read minimized profile identity, scope and declared capability metadata
through a dedicated default-deny permission and the existing username/password browser session.
The UI exposes no register, update, remove, select, bind, probe, publish, deliver, dispatch or
execute control and requires no additional login or MFA ceremony.

## Consequences

- Deployment transport capabilities become immutable independently of workflow events.
- A later compatibility-admission boundary can compare the exact logical-binding digest with the
  exact profile-snapshot digest without selecting a route.
- A later route-binding boundary can select a physical destination without redefining logical event
  meaning or transport capabilities.
- Snapshot registration does not prove configuration reachability, credentials, runtime readiness
  or publication authority.
- Profile changes produce a new revision and snapshot; historical snapshots are never updated or
  deleted.

## Validation

- Domain and application tests cover normalized allowlisted manifests, exact replay, changed
  requests, competing identities, source drift, scope mismatch, audit failure and zero authority.
- PostgreSQL tests cover immutable snapshot/idempotency persistence and transaction rollback.
- Static tests reject event lineage, route, endpoint, credential, network and publication fields.
- API tests prove deployment-workload-only creation, dedicated human read permission, no-store
  responses and minimized metadata.
- Web tests prove read-only identity/capability presentation, empty and error states, no mutation or
  operational controls and no second-login or MFA text.
- Full backend/frontend suites, Alembic single-head validation and live browser inspection are
  required before merge.
