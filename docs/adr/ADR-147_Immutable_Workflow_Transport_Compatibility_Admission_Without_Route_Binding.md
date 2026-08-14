# ADR-147: Immutable Workflow Transport Compatibility Admission Without Route Binding

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-14 |
| Owners | Event Platform, Workflow Platform, Security Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-143, ADR-144, ADR-145, ADR-146 |

## Context

Atlas now has two independently immutable records: one exact workflow byte artifact bound to a
code-owned logical publication channel, and one deployment-owned physical transport capability
profile snapshot. Neither record states that the logical requirements can be satisfied by the
profile. Selecting an endpoint or route before that comparison would turn compatibility checking
into an implicit physical-routing and publication decision.

## Decision

Atlas will persist one immutable `WorkflowEventTransportCompatibilityAdmission` for one exact
logical-channel binding and one exact transport-profile snapshot. A versioned code-owned
compatibility policy compares only their declared contracts. Version 1 requires exact support for:

- event type, version and canonical schema URI;
- internal classification, canonical JSON representation and UTF-8 encoding;
- durable at-least-once delivery;
- workflow-run ordering-key kind and workflow-operational retention class; and
- the logical contract's maximum and exact artifact byte count within the profile's maximum
  message-byte count.

The admission records the compatibility-policy identity, version and digest; exact logical-binding
and profile-snapshot identities and digests; profile identity and revision; organization,
environment and site scope; the compared logical contract and artifact byte count; the dedicated
admitter workload identity; admission time; immutable state and canonical digest. The binding
digest transitively commits its artifact, admission, event, outbox and workflow lineage. The
snapshot digest transitively commits the deployment release, implementation, adapter and declared
capabilities. Those histories are not redefined by this record.

Only a dedicated workload authenticated for
`audience.workflow-transport-compatibility-admitter` may create an admission. Human sessions,
workflow publishers, profile registries, connector workloads and ordinary API tokens cannot create
one. Exact replay returns the same admission. Changed idempotent requests, competing identities,
scope mismatch, malformed or tampered evidence, unsupported contracts, insufficient message size
and audit failure fail closed and create no partial record.

The authoritative logical binding must be exactly `bound` and the authoritative profile snapshot
must be exactly `snapshotted`. Both canonical digests are recomputed before comparison. A valid but
incompatible pair is rejected with an allowlisted audit reason and creates no compatibility
admission; malformed, missing or unverifiable evidence fails separately without inferring an
incompatibility result.

The admission state is `admitted`. It is not `selected`, `bound`, `ready`, `healthy`, `published` or
`delivered`. Route-selection, route-binding, credential-access, publication, delivery, dispatch and
execution authority flags all remain false. PostgreSQL locks and revalidates the exact logical
binding and exact profile snapshot before atomically writing the admission and idempotency claim.
Production persistence never falls back to memory.

Compatibility performs no deployment-profile discovery, current-profile inference, endpoint or
destination selection, DNS resolution, socket connection, TLS handshake, broker metadata query,
health probe, credential or secret lookup, provider SDK call or network request. Transport
encryption and restricted-network declarations remain bounded profile evidence for a later route
binding; this admission does not claim that any concrete route satisfies them.

The record contains no hostname, URL, IP address, broker endpoint, namespace, topic, stream, queue,
partition, routing key, credential or secret reference, vault path, certificate, encryption-key
reference, provider message, publication attempt, retry, receipt, acknowledgement, offset,
network-health result, current-profile claim or readiness result.

Authorized humans may read minimized compatibility evidence through the dedicated default-deny
`workflow.transport-compatibility-admissions.read` permission and the existing username/password
browser session. The UI exposes no admit, recalculate, override, select,
bind, probe, publish, deliver, dispatch or execute control and requires no additional login or MFA
ceremony.

## Consequences

- Logical requirements and deployment capability evidence can be compared deterministically before
  any physical route exists.
- An admitted compatibility decision means only that the exact declared contracts match under the named policy.
  It does not prove profile currency, endpoint configuration, credentials, reachability or runtime
  readiness.
- A later physical-route binding can require the exact admission, binding and profile digests
  without repeating compatibility policy.
- Profile or logical-channel changes require new immutable source records and a new admission;
  historical admissions are never updated or deleted.

## Validation

- Domain and application tests cover policy digest stability, exact compatibility, replay,
  changed-request conflict, scope mismatch, unsupported contracts, insufficient size, tampered
  evidence, competing identities, audit failure and zero authority.
- PostgreSQL tests cover locked source revalidation, atomic admission/idempotency persistence and
  transaction rollback.
- Static tests reject route, endpoint, credential, network, readiness and publication fields.
- API tests prove dedicated-workload-only creation, default-deny human read access, no-store
  responses and minimized metadata.
- Web tests prove read-only compatibility presentation, empty and error states, no operational
  controls and no second-login or MFA text.
- Full backend/frontend suites, Alembic single-head validation and live browser inspection are
  required before merge.
