# ADR-166: Bounded Single-Use Protected Resident-Context Access Authorization Lease Without Handle Creation, Injection, Network, Execution or Infrastructure Mutation Authority

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-16 |
| Owners | Workflow Architecture, Deployment Architecture, Security Architecture, Identity Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-160, ADR-161, ADR-162, ADR-163, ADR-164, ADR-165 |

## Context

ADR-165 may irreversibly consume one exact capsule-opening lease and establish one short-lived,
non-bearer protected resident context inside the exact consumer boundary. A successful
`opened_in_protected_consumer_boundary` result and signed receipt prove that the target-context pair
was verified, the protected source was closed and the source capsule was zeroized. They do not
authorize later lookup, handle creation, access, injection, network use, dispatch, execution or
infrastructure mutation.

Atlas now needs the next smallest authorization boundary. The exact consumer workload must be able
to obtain one extremely short-lived lease that authorizes only a future request to a separate
resident-context access-consumption operation. Issuance must prove that the complete opening
lineage remains canonical and that the exact protected resident context still exists and is usable,
without returning its identity, locator, material or a reusable capability to an ordinary Atlas
process.

Historical opening success alone is insufficient. The resident context may have expired, been
revoked, been consumed, been destroyed or become inaccessible after a destination deployment or
fencing change. A signed receipt cannot be treated as current lifecycle state, and possession of an
opening result identifier cannot become access authority.

## Decision

Atlas will issue one immutable
`WorkflowProtectedResidentContextAccessAuthorizationLease` from one exact canonical ADR-165
successful opening result. The lease authorizes only a future request to a separately designed
atomic resident-context access-consumption boundary. It does not retrieve, reveal, copy, export,
deserialize, inject or use resident context, create a runtime handle, establish a network path or
call a connector.

Only the exact code-owned consumer subject
`service.workflow-protected-transport-target-context-capsule-consumer` authenticated for
`audience.workflow-protected-transport-target-context-capsule-consumer` may request issuance for
its own opening result. The authenticated subject and audience must equal the ADR-161 binding,
ADR-163 receipt, ADR-164 lease and ADR-165 claim, attempt, result and signed opening receipt. Human
sessions, personal access tokens, AI agents, attestors, openers, binders, publishers and generic
workflow services fail closed.

The request contains only:

- opening result ID and canonical digest;
- code-owned resident-context access-authorization policy ID and version; and
- idempotency metadata.

The caller cannot supply or override resident-context identity, digest, locator, lifetime,
destination, fence, consumer, attestor, lease duration, authority, endpoint, credential, route,
network, runtime, publication, dispatch, execution or mutation fields. Atlas derives every such
value from authenticated context, canonical append-only lineage and authoritative server-side
state.

### Canonical Opening Eligibility

Issuance accepts only one terminal canonical ADR-165
`opened_in_protected_consumer_boundary` result. The result must contain a trusted signed opening
receipt completed strictly before its immutable opening deadline and must prove:

- the exact target-context pair was verified;
- a non-bearer protected resident context was established;
- resident-context creation equals trusted completion time;
- resident-context `usable_until` is later than creation, no more than 30 seconds later and no
  later than the persisted source-lifetime ceiling;
- the protected source was closed and the source capsule was zeroized; and
- the outcome is known and carries no failure class.

`opening_failed`, `opening_outcome_uncertain`, pending, claim-only, attempt-only, late, unsigned,
malformed, ambiguous or receipts-free evidence is ineligible. The result, attempt and claim must
agree with the exact ADR-164 lease and complete ADR-160 through ADR-163 lineage. Canonical digests
and append-only relationships must verify without repair, inference or fallback.

### Fresh Protected-Boundary Lifecycle Attestation

Before opening the database transaction, Atlas obtains one fresh, independently signed,
nonce-bound and metadata-only lifecycle attestation from the trusted protected consumer boundary.
No protected-boundary, attestor, provider or network call may occur while the PostgreSQL transaction
is open.

The attestation canonically commits to:

- trusted attestor identity, signing-key ID and profile version;
- exact opening result, attempt, claim, opening lease and complete upstream lineage digests;
- exact protected resident-context ID and digest known only inside the protected boundary;
- exact consumer subject, audience, contract and purpose;
- destination boundary and deployment identity, generation and fencing-token digest;
- server-created nonce, observed time and attestation validity deadline;
- resident context present, non-bearer, unexpired, unrevoked and undestroyed;
- resident context not previously consumed and no access handle currently outstanding; and
- no raw context, endpoint, credential, secret, bearer token, locator or provider payload.

Unavailable, unsigned, malformed, expired, mismatched, stale, negative, bearer, revoked,
destroyed, consumed or handle-bearing evidence fails closed. Atlas verifies the captured attestation
before the transaction and again offline while canonical database locks are held.

### Authorization Policy And Lease

The code-owned policy is
`policy.workflow-protected-resident-context-access-authorization` version `1.0`, with purpose
`purpose.workflow-protected-resident-context-access-evaluation`. Its canonical digest, consumer
contract, attestor profile, destination profile, maximum lifetime and authority declaration are
code-owned and cannot be supplied by callers or mutable configuration.

The lease is:

- single-use;
- non-renewable;
- non-transferable;
- non-bearer;
- valid for at most one second;
- strictly bounded by the signed resident-context `usable_until` timestamp;
- strictly bounded by the fresh lifecycle-attestation deadline; and
- bound to the exact opening result, protected resident context, consumer identity, destination
  fence, policy, purpose and idempotency claim.

The lease sets only
`protected_resident_context_access_authority_granted = true`. This means a future operation may
request atomic consumption of this exact lease; it is not direct resident-context access.
`target_context_capsule_handoff_authority_granted`,
`target_context_capsule_opening_authority_granted`, protected-artifact access and all route,
credential, network, readiness, publication, delivery, dispatch, execution and
infrastructure-mutation authority fields remain exactly false.

### Atomic Issuance And Replay

Atlas captures database time before external attestation, generates a one-time nonce and verifies
the signed evidence outside the transaction. It then starts one PostgreSQL transaction and locks
the complete upstream lineage in canonical oldest-to-newest order, ending with the ADR-165 opening
result and any existing resident-context access-authorization claim.

Under those locks Atlas:

1. reads database time again;
2. revalidates organization, environment and site scope;
3. verifies every canonical digest and composite lineage edge;
4. verifies the exact authenticated consumer subject and audience;
5. revalidates opening success, receipt signature and strict deadlines;
6. revalidates destination deployment generation and fencing state;
7. verifies the captured lifecycle attestation offline against the nonce and locked lineage;
8. proves sufficient remaining resident-context and attestation lifetime;
9. classifies exact replay or conflict; and
10. atomically appends one idempotency claim and one authorization lease.

The transaction performs no external I/O. Canonical authorization audit payload and digest are
stored with the claim and lease. External audit and SIEM export occur only after commit and are
best-effort delivery of already committed evidence. Audit delivery failure cannot roll back,
duplicate or widen authority.

Exact replay with the same scope, idempotency key, request fingerprint and opening result returns
the same minimized lease state without new attestation or external I/O. Changed replay, competing
identity, competing result, digest mismatch, stale fence, consumed context or uniqueness conflict
fails closed. Insertion races are classified in a new transaction under the same canonical locks;
append-only evidence is never repaired by mutation.

### Durable Persistence

Production stores two append-only tables:

- resident-context access-authorization claims, unique by opening result, protected resident
  context and scoped idempotency key; and
- resident-context access-authorization leases, unique by claim, opening result and protected
  resident context.

Composite foreign keys bind the claim and lease to the exact ADR-165 result, attempt and
consumption claim. Database CHECK constraints enforce the code-owned policy and consumer contract,
single-use/non-renewable/non-transferable/non-bearer semantics, bounded effective deadline and the
one-dedicated-authority contract. Triggers reject `UPDATE` and `DELETE`. Downgrade fails closed while
either table contains evidence.

Production requires PostgreSQL and the trusted lifecycle attestor. There is no process-memory,
permissive, caller-asserted or unguarded synthetic fallback.

### API And Human Presentation

The workload command is:

`POST /api/v1/workflows/protected-resident-context-access-authorizations`

Only the exact consumer workload may call POST. Authorized humans may inspect a separate minimized
inventory through:

`GET /api/v1/workflows/protected-resident-context-access-authorizations`

Human reads use the normal username/password browser session and a dedicated read permission. No
MFA, second login or authorized-browser-session prompt is required. Command, query and error
responses are `no-store`, minimized and non-oracle.

The human response exposes only non-sensitive lease identity and state, issue/effective timestamps,
consumer contract and purpose references, policy reference, destination profile reference, the
authority declaration and a non-sensitive integrity reference. It omits opening, capsule, receipt,
resident-context, attestation, nonce, route, credential, target, locator, idempotency, request-
fingerprint and fencing material.

The UI section is titled `Protected resident-context access authorizations` and is strictly
read-only. It provides no authorize, consume, access, retrieve, reveal, copy, download, inject,
connect, probe, publish, dispatch, execute or mutate control.

## Consequences

- A successful opening does not silently become reusable runtime authority.
- Every access request is preceded by a fresh lifecycle proof and a one-second exact-lineage lease.
- Resident-context identity and material remain inside the trusted protected boundary.
- Append-only claims make replay and competing authority visible without mutating history.
- Actual resident-context access remains unavailable until a separate consumption boundary exists.

## Deferred Scope

- Access-authorization lease consumption
- Runtime-context handle creation, retrieval, access, injection or use
- Endpoint or credential reveal, delivery, copy, download or export
- DNS, TLS, socket, proxy, network establishment or readiness probing
- Broker, provider SDK or connector capability calls
- Event publication, acknowledgement, retry or quarantine release
- Worker dispatch, workflow state transition, execution or infrastructure mutation
- Lease renewal, transfer, replacement or reissue
- Autonomous cleanup, recovery or operational remediation
- Human- or AI-initiated resident-context access or runtime use
- Active Directory management or an Active Directory MCP; AD remains authentication-only

## Validation

- Domain and application tests cover exact workload identity, caller-field prohibition, canonical
  opening eligibility, signed lifetime, fresh attestation, one-second bounds, authority fields,
  exact replay, changed replay, expiry, revocation, consumption, fence drift and no external I/O
  under transaction.
- PostgreSQL tests cover canonical lock order, two database-time checks, concurrent unique winner,
  exact composite lineage, append-only triggers, guarded downgrade and no production fallback.
- API and UI tests cover workload-only POST, session-only GET, personal-token/human/AI denial,
  `no-store`, non-oracle errors, minimized schemas and zero operational controls.
- Full backend/frontend suites, Alembic single-head and round-trip validation, real PostgreSQL CI,
  live desktop/mobile inspection, independent review, exact-head PR CI, SHA-locked merge and
  independent `main` CI are required.
