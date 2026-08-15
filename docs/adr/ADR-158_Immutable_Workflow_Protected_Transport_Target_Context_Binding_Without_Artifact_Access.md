# ADR-158: Immutable Workflow Protected Transport Target-Context Binding Without Artifact Access

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-15 |
| Owners | Workflow Architecture, Deployment Architecture, Security Architecture, Identity Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-149, ADR-152, ADR-154, ADR-157 |

## Context

ADR-152 can produce one short-lived protected endpoint artifact for an exact physical route.
ADR-157 can independently produce one short-lived protected credential artifact for an exact
credential assignment. Both outcomes are minimized, exact-subject-bound and unusable through
ordinary application persistence, API or UI.

Atlas must prove that one successful endpoint outcome and one successful credential outcome belong
to the same workflow physical route before any later component may request protected-artifact
access, credential delivery, network establishment or publication authority. Merely accepting two
opaque artifact identifiers would permit cross-route, cross-scope, stale-generation or confused-
deputy pairing. Opening either artifact to compare its contents would violate the protected-store
boundary.

## Decision

Atlas will create one immutable `WorkflowProtectedTransportTargetContextBinding` from the complete
append-only lineage of one endpoint materialization result and one credential materialization
result. The binding is historical evidence only. It neither accesses nor confers access to either
protected artifact.

The binding computes a versioned, code-owned `target_context_commitment`; it does not interpret the
older opaque assignment `target_scope_commitment` as sufficient proof. Version `1.0` canonically
commits the scope, physical route binding ID/digest, route snapshot ID/digest, destination
ID/revision, endpoint-set ID/revision, routing-contract ID/revision, endpoint materialization
ID/digest, credential-assignment binding ID/digest, credential-assignment snapshot ID/digest and
credential materialization ID/digest. Future algorithms require a new schema version and cannot
silently reinterpret existing bindings.

Only the exact dedicated target-context binder workload and audience may request creation. Human
sessions, personal tokens and all other workloads fail closed. The request contains only:

- endpoint materialization result ID and canonical digest;
- credential materialization result ID and canonical digest;
- code-owned binding policy ID, version and digest; and
- idempotency and correlation metadata.

The caller cannot supply route, assignment, endpoint, credential, artifact, protected-store,
provider, target, destination, runtime, TTL, delivery, network, publication or execution fields.
Atlas derives every relationship and bounded time from authoritative committed evidence.

### Complete Lineage Proof

One durable transaction locks the immutable source rows in a fixed order and validates canonical
integrity for:

1. physical transport route binding and transport route snapshot;
2. endpoint route-freshness admission, consumed authorization lease, claim, attempt and successful
   materialization result;
3. physical transport credential-assignment binding and credential-assignment snapshot;
4. credential freshness admission, consumed authorization lease, claim, attempt and successful
   materialization result; and
5. any prior binding or idempotency claim for the same request.

The credential-assignment binding must reference the exact physical route binding and route
snapshot proven by the endpoint chain. Scope, immutable digests, route lineage, assignment lineage,
materializer receipts and zero-authority declarations must agree throughout both chains. Both
results must be `materialized_protected`, cleanup-confirmed, not revoked, and structurally valid.
The recomputed versioned target-context commitment must equal the candidate binding commitment.

Database time is read with `clock_timestamp()` after locks are held. Creation requires
`database_time < endpoint_usable_until` and `database_time < credential_usable_until`. The binding
records `bound_at` and the derived `joint_usable_until = min(endpoint_usable_until,
credential_usable_until)`. This is an observation, not a future validity promise. A later access
authorizer must independently revalidate protected-store state and remaining lifetime.

Because all bound source evidence is append-only and this boundary makes no current-route,
current-assignment or protected-store-state claim, it takes no route-selection or assignment-head
advisory fence. After required precommit audit, PostgreSQL reads database time again and repeats
the complete evidence and overlap validation before the atomic insert.

### Atomicity, Replay And History

Required intent and commit-authorization audit precede persistence. The binding and idempotency
claim commit atomically. Each endpoint materialization result and each credential materialization
result may belong to at most one target-context binding; both source IDs are independently unique.

Exact replay returns the same immutable binding after revalidating committed history without
requiring the artifacts to remain live. A changed request under the same idempotency key, a
different binder identity, cross-scope evidence, a different credential generation or a competing
pairing fails closed. Historical bindings are never updated, deleted, renewed, reopened or treated
as bearer capabilities.

Completion audit follows commit. If completion audit fails, the committed binding remains
authoritative and exact replay recovers the minimized result; audit uncertainty cannot create a
second binding.

### Authority And Human Presentation

The binding contains endpoint and credential materialization lineage, route and assignment
lineage, exact binder identity, bounded times, policy identity and 17 explicit authority
declarations. Every authority value is exactly false.

Authorized humans may inspect a minimized inventory through the existing username/password
browser session. No MFA, second login or authorized-browser prompt is required. Human API/UI
responses omit protected artifact IDs and digests, endpoint-set digest, route or endpoint
coordinates, assignment/provider commitments, credential metadata, secret locators and source or
policy digests. They expose no bind, access, reveal, copy, download, deliver, connect, publish,
dispatch or execute control.

## Consequences

- Endpoint and credential outcomes cannot be paired across route, scope or assignment lineage.
- Ordinary application code still never opens endpoint or credential artifacts.
- Expiry during or after binding never creates access authority and cannot be hidden as readiness.
- A later dedicated boundary can authorize one exact workload to access the already bound context
  only after independent protected-store and time revalidation.
- Failed or uncertain materialization results cannot enter a target context.

## Deferred Scope

- Protected-artifact access authorization and single-use consumption
- Credential delivery or injection into a transport runtime
- Endpoint reveal, DNS, TLS, socket, proxy or network establishment
- Readiness probes and transport-provider negotiation
- Publication, acknowledgement, retry, quarantine and delivery receipts
- Worker dispatch, workflow execution and infrastructure mutation
- Credential selection, reassignment, rotation or revocation

## Validation

- Domain and application tests cover exact workload/audience, policy, canonical lineage, route and
  assignment agreement, successful-only results, overlap at database time, replay, conflict,
  competing identity, post-commit audit uncertainty and all-false authority.
- PostgreSQL tests cover deterministic locks, atomic binding/idempotency insertion, unique result
  pairs, concurrent callers, append-only triggers, DB-time expiry and no production memory fallback.
- API and UI tests prove workload-only creation, default-deny minimized human reads, non-oracle
  errors and absence of protected artifact, endpoint, credential and operational fields.
- Full backend/frontend suites, Alembic single-head validation, real PostgreSQL CI, live browser
  inspection, exact-head PR CI, SHA-locked merge and independent main CI are required.
