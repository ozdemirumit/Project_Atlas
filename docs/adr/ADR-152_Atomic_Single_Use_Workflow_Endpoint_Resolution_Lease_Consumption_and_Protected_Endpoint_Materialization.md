# ADR-152: Atomic Single-Use Workflow Endpoint-Resolution Lease Consumption and Protected Endpoint Materialization

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-14 |
| Owners | Event Platform, Workflow Architecture, Deployment Architecture, Security Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-148, ADR-149, ADR-150, ADR-151 |

## Context

ADR-151 creates one exact-resolver, non-transferable, 15-second authorization lease. The lease
contains no endpoint material and is deliberately insufficient for credential, network,
readiness, publication, delivery, dispatch or execution activity. Atlas now needs the next
irreversible boundary: consume that authority once and ask a trusted internal component to resolve
the deployment-owned endpoint set without exposing coordinates to ordinary application code.

Consumption cannot wait until after protected materialization. A process crash, timeout or
uncertain protected-store outcome could otherwise leave the lease reusable after an endpoint was
opened. Conversely, ordinary PostgreSQL persistence cannot atomically commit raw protected-store
content. The safe contract therefore separates the atomic point of no return from append-only
completion evidence while preserving the ADR-151 requirement that every attempt, including a
failed or uncertain one, consumes the lease exactly once.

## Decision

Atlas will implement one
`WorkflowEventPhysicalTransportEndpointMaterializationAttempt`, one
`WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaim` and, on a known outcome,
one append-only `WorkflowEventPhysicalTransportEndpointMaterializationResult`.

Only a service workload authenticated for
`audience.workflow-physical-transport-endpoint-resolver` may request materialization. Its subject
must exactly equal the resolver subject stored in the lease. Human sessions, API tokens and every
other workload fail closed. The request contains only:

- endpoint-resolution authorization lease ID and canonical digest;
- code-owned materialization policy ID and version;
- explicit acknowledgement that consumption is one-way and non-retryable;
- explicit acknowledgement that an uncertain outcome requires investigation and new upstream
  freshness plus authorization;
- idempotency key and correlation metadata.

The caller cannot name or override an endpoint, endpoint set, destination, route, artifact,
resolver subject, credential, secret, network zone, protocol, TLS mode, timeout, TTL, retry,
readiness probe, provider, publication or execution decision.

### Atomic Point Of No Return

After intent audit succeeds, one PostgreSQL transaction locks and revalidates:

1. physical transport route binding;
2. immutable transport route snapshot;
3. authoritative current-selection head;
4. route freshness admission; and
5. endpoint-resolution authorization lease.

Database time is read with PostgreSQL `clock_timestamp()` after all locks are acquired;
transaction-start time such as `now()` is insufficient because lock waiting could otherwise admit
an expired lease. That authoritative time must be earlier than both freshness and lease
`valid_until`. Every immutable digest,
scope, route-set and selection-epoch identity, selected-route ID/revision/digest, head generation,
fencing-token digest, selection flag, resolver identity, policy and authority declaration must
exactly match the current authoritative chain. The lease must remain
`authorized_unconsumed`, grant endpoint resolution only and have no prior consumption claim.

The same transaction appends a unique consumption claim and started-attempt record. A unique
constraint on authorization-lease ID makes this commit the single atomic point of no return.
Neither record is updated, deleted, released or reopened. The lease row also remains immutable;
effective consumption is derived from the unique claim rather than rewriting historical
authorization evidence.

An exact idempotent replay with an existing known result returns the same minimized metadata. An
existing claim without a known result is treated as outcome-uncertain and never invokes the
materializer again. Changed requests, another subject, another idempotency key or competing claims
fail as already consumed.

### Trusted Protected-Materializer Boundary

Only after the consumption transaction commits may the service call an approved
`WorkflowPhysicalTransportEndpointMaterializer`. The instruction contains trusted IDs, digests,
scope, resolver binding, route commitments, attempt ID, policy limits and the consumed lease
deadline. It contains no caller-supplied coordinate.

Inside its protected boundary the materializer must:

- resolve the exact deployment-owned endpoint-set revision and routing contract from sealed
  lineage;
- verify the route source digest, endpoint-set identity/revision, destination identity/revision,
  routing-contract identity/revision and private-route-descriptor commitment;
- reject ambiguity, drift, empty sets, unsupported protocols, malformed coordinates and policy
  limit violations;
- create an encrypted, resolver- and lineage-bound protected artifact outside ordinary
  application persistence;
- ensure the artifact is usable no later than the consumed lease's `valid_until` and destroy or
  revoke it on rejection, timeout or late completion; and
- return only a signed minimized receipt.

The receipt may contain protected-artifact ID/digest, normalized endpoint-set digest, endpoint
count, schema/profile and adapter IDs/versions, source commitment digests, attempt ID, resolver
subject, materialized/completed time, `usable_until`, cleanup/revocation evidence and canonical
digest. It contains no raw hostname, URL, IP address, port, namespace, topic, stream, queue,
partition, routing key, private descriptor, credential, secret, key, certificate, proxy, network
result, readiness result, provider message or payload. The artifact ID is an opaque lineage
identifier, not a bearer capability.

Production fails closed without an approved trusted materializer and protected store. Development
may use a deterministic synthetic materializer that verifies fixed commitments and emits receipt
metadata but performs no DNS, network, credential, secret-store, filesystem, process, broker,
provider, publication, delivery, dispatch or infrastructure operation.

### Completion And Failure Evidence

A successful receipt is verified against the exact instruction before Atlas appends one immutable
result with state `materialized_protected`. Completion at or after the lease deadline is rejected,
the protected artifact must be revoked and the lease remains consumed.

A known adapter rejection appends a minimized `materialization_failed` result with a stable
code-owned failure class and no provider detail. A timeout, crash, invalid receipt, persistence
ambiguity, cleanup uncertainty or protected-store ambiguity leaves the durable claim as the
authoritative consumed record and returns `materialization_outcome_uncertain`. Atlas never retries
automatically. Operators must investigate and obtain new upstream freshness and authorization.

Required completion/failure audit is append-only. Audit failure after consumption does not restore
the lease and is itself treated as outcome-uncertain.

### Authority And Presentation

Materialization proves endpoint resolution occurred; it grants no continuing endpoint-resolution
authority. Result authority declarations are all false for route selection, route binding,
endpoint resolution, credential access, network access, readiness probe, publication, delivery,
dispatch and execution. A later boundary must separately authorize any credential or network use
and must revalidate the current head plus protected-artifact deadline.

The immutable IMP-201 lease continues to record its original state and historical authority.
Human and internal projections derive lease usability as `active`, `expired` or `consumed`; a
consumption claim always wins over later wall-clock expiry and prevents the lease from appearing
active.

Authorized humans may read minimized attempt/result metadata through a dedicated default-deny
permission and the existing username/password browser session. Human API and UI views omit every
source, policy, fence, artifact and canonical digest, expose no endpoint coordinate or protected
artifact access and provide no materialize, retry, reveal, credential, probe, publish, deliver,
dispatch or execute control. They require no second login or MFA.

## Consequences

- One committed claim permanently consumes one lease before protected material can be opened.
- A crash or uncertain materializer outcome cannot make the lease reusable.
- Raw endpoint coordinates remain outside ordinary domain, persistence, API, logs, audit and UI.
- Success and known failure are explicit append-only outcomes; claim-without-result remains safely
  uncertain.
- Protected artifacts are short-lived, resolver-bound inputs for a later independent authority
  boundary, not transferable capabilities.
- New freshness and authorization are required after failure, uncertainty, expiry or head drift.

## Deferred Scope

- Credential assignment or brokerage and secret/key/certificate delivery
- DNS, TLS, socket, broker metadata or runtime network establishment
- Readiness probes and provider health checks
- Publication, delivery, acknowledgement, retry, quarantine and receipt
- Worker dispatch and workflow execution
- Route failover, rebinding and supersession chains
- Human reveal or download of endpoint/protected-artifact content

## Validation

- Domain/application tests cover exact resolver/audience binding, acknowledgements, DB-time
  freshness, head fencing, single consumption, exact replay, already-consumed conflict, success,
  known failure, uncertainty, late receipt, invalid receipt, cleanup uncertainty and audit failure.
- PostgreSQL tests cover fixed-order locking, unique claim, atomic claim/attempt insertion,
  concurrent requests, append-only triggers, claim-derived consumption, rollback before claim and
  no production memory fallback.
- Adapter tests prove sealed-lineage input, commitment verification, bounded endpoint count,
  deadline enforcement, receipt signing and no raw-coordinate return.
- Static/API/UI tests reject endpoint, locator, credential, secret, certificate, provider payload
  and operational controls from ordinary surfaces and logs.
- Full backend/frontend suites, Alembic single-head validation, live PostgreSQL concurrency tests
  and live browser inspection are required before merge.
