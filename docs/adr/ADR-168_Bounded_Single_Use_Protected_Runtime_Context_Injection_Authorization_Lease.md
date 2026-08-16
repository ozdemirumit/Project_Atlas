# ADR-168: Bounded Single-Use Protected Runtime-Context Injection Authorization Lease Without Injection, Handle Use, Network, Execution or Infrastructure Mutation Authority

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-16 |
| Owners | Workflow Architecture, Deployment Architecture, Security Architecture, Identity Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-160, ADR-161, ADR-162, ADR-163, ADR-164, ADR-165, ADR-166, ADR-167 |

## Context

ADR-167 may irreversibly consume one exact protected resident-context access lease and establish
one short-lived, non-bearer runtime-context handle inside the exact protected consumer boundary. A
canonical `handle_established_in_protected_boundary` result and trusted signed accessor receipt
prove only that the protected transition completed. They do not authorize handle lookup,
retrieval, injection or use, runtime use, network or connector activity, readiness probing,
publication, delivery, dispatch, execution or infrastructure mutation.

Atlas now needs the next smallest authorization boundary. The exact protected consumer workload
must be able to obtain one extremely short-lived lease that authorizes only a future request to a
separately designed protected runtime-context injection-consumption operation. Issuance must prove
that the complete ADR-167 lineage remains canonical and that the exact non-bearer handle is still
present and eligible for one exact code-owned injector and runtime-slot profile, without revealing
the handle identity, digest, locator, material or a reusable capability to an ordinary Atlas
process.

Historical handle-establishment success alone is insufficient. The handle may have expired, been
revoked, already been injected, already been used or become ineligible after a destination
deployment generation, fencing state, injector profile or runtime-slot profile change. A signed
ADR-167 receipt cannot be treated as current lifecycle state, and possession of an access-result
identifier or human-visible integrity reference cannot become injection authority.

## Decision

Atlas will issue one immutable
`WorkflowProtectedRuntimeContextInjectionAuthorizationLease` from one exact canonical ADR-167
`handle_established_in_protected_boundary` result. The lease authorizes only a future request to a
separately designed atomic protected runtime-context injection-consumption boundary. IMP-218 does
not inject context, retrieve or use a handle, use a runtime, establish a network path, call a
connector, probe readiness, publish or deliver an event, dispatch work, execute a workflow step or
mutate infrastructure.

Only the exact code-owned protected consumer subject
`service.workflow-protected-transport-target-context-capsule-consumer` authenticated for
`audience.workflow-protected-transport-target-context-capsule-consumer` may request issuance for
its own ADR-167 result. The authenticated subject and audience must equal the canonical ADR-161
binding and every consumer-bound ADR-162 through ADR-167 claim, attempt, lease, result and signed
receipt. Human sessions, personal access tokens, AI agents, attestors, accessors, injectors,
publishers, connector workloads and generic workflow services fail closed.

The request contains only:

- ADR-167 access-result ID and canonical digest;
- code-owned protected runtime-context injection-authorization policy ID and version; and
- idempotency metadata.

The caller cannot supply or override handle identity, digest, locator, lifetime or state;
destination identity, generation or fence; consumer, attestor, injector or runtime-slot profile;
lease duration, authority, endpoint, credential, route, network, readiness, publication, delivery,
dispatch, execution or mutation fields. Atlas derives every such value from authenticated context,
canonical append-only lineage, code-owned profiles and authoritative server-side state.

### Canonical Handle-Establishment Eligibility

Issuance accepts only one terminal canonical ADR-167
`handle_established_in_protected_boundary` result. The result must contain a trusted signed accessor
receipt completed strictly before its immutable access deadline and must prove:

- the exact ADR-166 lease was irreversibly consumed by one canonical claim and started attempt;
- the exact protected resident context was atomically consumed;
- exactly one short-lived non-bearer runtime-context handle was established inside the exact
  protected consumer boundary;
- handle creation and `usable_until` timestamps are trusted, internally consistent, strictly
  bounded by the persisted resident-context lifetime ceiling and accepted code-owned handle
  profile;
- the accessor instruction, consumer, destination generation and fence match the complete locked
  lineage; and
- the outcome is known and carries no failure class or forbidden return or side effect.

`resident_context_access_failed`, `access_outcome_uncertain`, pending, claim-only, attempt-only,
late, unsigned, malformed, ambiguous or receipt-free evidence is ineligible. The ADR-167 result,
attempt and claim must agree with the exact ADR-166 authorization and complete ADR-160 through
ADR-167 lineage. Canonical digests, signatures and append-only relationships must verify without
repair, inference, fallback or caller-provided replacement evidence.

### Fresh Protected-Boundary Handle Lifecycle And Injection-Eligibility Attestation

Before opening the issuance transaction, Atlas obtains one fresh, independently signed,
server-nonce-bound and metadata-only handle lifecycle and injection-eligibility attestation from
the trusted protected consumer boundary. This is passive eligibility evidence, not a readiness
probe or injector invocation. No protected-boundary, attestor, injector, runtime, connector,
provider or network call may occur while the PostgreSQL transaction is open.

The attestation canonically commits to:

- trusted attestor identity, signing-key ID and profile version;
- exact ADR-167 result, attempt and claim and complete ADR-160 through ADR-167 lineage digests;
- exact runtime-context handle ID and digest known only inside the protected boundary;
- exact consumer subject, audience, contract and code-owned purpose;
- exact destination boundary and deployment identity, current generation and fencing-token digest;
- exact code-owned injector profile ID, version and digest;
- exact code-owned runtime-slot profile ID, version and digest;
- server-created nonce, observed time and attestation validity deadline;
- handle present, non-bearer, unexpired and unrevoked;
- handle not previously injected, not previously used and not subject to an outstanding injection
  consumption or competing authorization;
- current destination generation and fence and eligibility of the exact injector/runtime-slot
  profile for that destination and handle lineage; and
- no raw context, handle material, handle locator, endpoint, credential, secret, bearer token,
  runtime payload or provider payload.

Unavailable, unsigned, malformed, future-dated, expired, mismatched, stale, negative, bearer,
revoked, injected, used, competing, locator-bearing or payload-bearing evidence fails closed. Atlas
verifies the captured attestation before the transaction and again offline while canonical
database locks are held. The attestation cannot perform or authorize injection, handle use,
runtime use or readiness probing.

### Authorization Policy And Lease

The code-owned policy is
`policy.workflow-protected-runtime-context-injection-authorization` version `1.0`, with purpose
`purpose.workflow-protected-runtime-context-injection-evaluation`. Its canonical digest, consumer
contract, attestor profile, injector profile, runtime-slot profile, destination profile, maximum
lifetime and authority declaration are code-owned and cannot be supplied by callers or mutable
configuration.

The lease is:

- append-only;
- single-use;
- non-renewable;
- non-transferable;
- non-bearer;
- valid for at most one second;
- strictly bounded by the signed runtime-context handle `usable_until` timestamp;
- strictly bounded by the fresh attestation validity deadline; and
- bound to the exact ADR-167 result and protected handle lineage, consumer identity, destination
  generation and fence, injector/runtime-slot profiles, policy, purpose and idempotency claim.

The idempotency claim sets
`protected_runtime_context_injection_authority_granted = false` and grants no authority. The
immutable lease declaration sets only
`protected_runtime_context_injection_authority_granted = true`. Every authorization decision and
ordinary API/UI projection treats that field as effectively true only while the lease is active
and no canonical future injection-consumption claim exists. At or after expiry, or once a future
unique consumption claim exists, effective
`protected_runtime_context_injection_authority_granted` is false without mutating the lease row.

The following existing 20 authority declarations remain exactly false on claim and lease:

- endpoint resolution, route selection and route binding;
- credential selection, assignment binding, access, brokerage, resolution and delivery;
- protected-artifact access;
- network access and readiness probing;
- publication, delivery, dispatch and execution;
- infrastructure mutation;
- target-context capsule handoff and capsule opening; and
- protected resident-context access.

The dedicated declaration means only that a future operation may request atomic consumption of
this exact lease. It is not handle access or injection authority usable by an ordinary process and
does not grant any current runtime capability.

### Durable Exact-Replay Preflight

Before requesting fresh attestation evidence, Atlas performs one durable replay lookup.
Exact replay with the same organization, environment, site, authenticated subject and audience,
idempotency key, request fingerprint and ADR-167 result returns the same minimized authorization
state without protected-boundary, attestor, injector, runtime, connector, provider or network I/O.
The response projects dedicated authority using one authoritative PostgreSQL statement and
database timestamp; an expired or later-consumed lease therefore replays with zero effective
injection-request authority.

Changed replay, competing identity, competing source result, digest mismatch, stale scope or a
prior nonmatching claim fails closed. A visible result ID, lease ID or integrity reference is
routing metadata, never authority.

### PostgreSQL Atomic Issuance

Atlas obtains the first authoritative PostgreSQL database timestamp before external attestation,
generates a one-time server nonce and verifies the returned signed metadata outside the issuance
transaction. It then starts one PostgreSQL transaction and locks the complete authoritative
lineage in canonical oldest-to-newest order, ending with the ADR-167 result and any existing
runtime-context injection-authorization claim.

Under those locks Atlas:

1. obtains the second authoritative PostgreSQL database timestamp;
2. revalidates organization, environment and site scope;
3. verifies every canonical digest, signature and composite lineage edge;
4. verifies the exact authenticated protected consumer subject and audience;
5. revalidates ADR-167 success, receipt signature, handle profile and strict deadlines;
6. revalidates destination deployment identity, current generation and fencing state;
7. verifies the captured lifecycle/injection-eligibility attestation offline against the server
   nonce, both database-time observations and locked lineage;
8. proves sufficient remaining handle and attestation lifetime for a positive lease window no
   greater than one second;
9. revalidates that no canonical injection-consumption claim, injection, use, competing
   authorization or conflicting idempotency claim exists;
10. classifies exact replay or conflict; and
11. atomically appends one idempotency claim and one authorization lease.

Both database-time observations are durable inputs to issuance validation. The second timestamp,
captured after canonical locks are held, is authoritative for `issued_at` and the effective
deadline. `valid_until` is no later than that timestamp plus one second, the signed handle
`usable_until` or the attestation deadline. No process clock can widen the window.

The transaction performs no external I/O. Canonical authorization audit payload and digest are
stored with the claim and lease. External audit and SIEM export occur only after commit and are
best-effort delivery of already committed evidence. Audit delivery failure cannot roll back,
duplicate, renew, transfer or widen authority.

Insertion races are classified in a new transaction under the same canonical locks. Exactly one
claim and lease may win for the source handle lineage and scoped idempotency key. Append-only
evidence is never repaired, replaced or mutated.

### Durable Persistence And Zero Disclosure

Production stores two append-only tables:

- protected runtime-context injection-authorization claims, unique by ADR-167 result, protected
  handle lineage and scoped idempotency key; and
- protected runtime-context injection-authorization leases, unique by claim, ADR-167 result and
  protected handle lineage.

Composite foreign keys bind the claim and lease to the exact ADR-167 result, attempt and access-
consumption claim and their complete upstream lineage. Database CHECK constraints enforce the
code-owned policy, consumer, destination, attestor, injector and runtime-slot contracts;
single-use, non-renewable, non-transferable and non-bearer semantics; the positive at-most-one-
second effective deadline; and the one-dedicated-authority contract. Triggers reject `UPDATE` and
`DELETE`. Downgrade fails closed while either table contains evidence.

Ordinary persistence, API, UI, logs, traces, metrics, audit payloads and events never expose the
runtime-context handle ID, digest, locator or material; raw context; endpoint or credential;
attestation payload or nonce; internal destination fence; or any bearer capability. Internal
protected identifiers required for composite lineage remain confined to the restricted
PostgreSQL/protected-boundary path and are never presented as authority. Production requires
PostgreSQL and the trusted handle lifecycle/injection-eligibility attestor. There is no process-
memory, permissive, caller-asserted or unguarded synthetic fallback.

### API And Human Presentation

The workload command is:

`POST /api/v1/workflows/protected-runtime-context-injection-authorizations`

Only the exact protected consumer workload may call POST. Authorized humans may inspect a separate
minimized inventory through:

`GET /api/v1/workflows/protected-runtime-context-injection-authorizations`

Human reads use the normal username/password browser session and a dedicated read permission.
No MFA, second login or authorized-browser-session prompt is required. Command, query and error
responses are `no-store`, minimized, non-oracle and zero-disclosure.

The human response exposes only non-sensitive authorization identity and effective state,
issue/effective timestamps, consumer contract and purpose references, policy, injector,
runtime-slot and destination-profile references, the dedicated effective authority declaration,
the existing all-false authority contract and a non-sensitive integrity reference. It omits the
ADR-167 source result, access lease, resident context, runtime handle, receipt, attestation, nonce,
route, credential, target, locator, idempotency, request-fingerprint and fencing material.

The UI section is titled `Protected runtime-context injection authorizations` and is strictly
read-only. It provides no authorize, consume, inject, retrieve, reveal, copy, download, use,
connect, probe, publish, deliver, dispatch, execute or mutate control.

## Consequences

- Successful handle establishment does not silently become reusable injection authority.
- Every future injection request is preceded by a fresh handle-state proof and an exact-lineage
  lease lasting no more than one second.
- Handle identity, locator and material remain inside the trusted protected boundary.
- Append-only claims make replay and competing authorization visible without mutating history.
- Actual injection and every form of handle or runtime use remain unavailable until a separate
  consumption boundary exists.

## Deferred Scope

- Injection-authorization lease consumption
- Runtime-context injection, runtime-slot mutation or runtime use
- Runtime-handle lookup, retrieval, reveal, copy, download, export or direct use
- Endpoint or credential reveal, delivery, copy, download or export
- DNS, TLS, socket, proxy, network establishment or readiness probing
- Connector, MCP, broker, provider SDK or capability calls
- Event publication, acknowledgement, retry or quarantine release
- Worker delivery, dispatch, workflow state transition or execution
- Infrastructure mutation
- Lease renewal, transfer, replacement or reissue
- Autonomous cleanup, recovery or operational remediation
- Human- or AI-initiated injection, handle access or runtime use
- Active Directory management or an Active Directory MCP; AD remains authentication-only

## Validation

- Domain and application tests cover exact workload identity, caller-field prohibition, canonical
  ADR-167 eligibility, signed handle lifetime, fresh nonce-bound attestation, injector/runtime-slot
  eligibility, one-second bounds, the one-true/twenty-false authority contract, exact replay,
  changed replay, expiry, revocation, injection, prior use, competing claim and fence drift.
- Call-order tests prove durable replay occurs before attestation and that no injector, runtime,
  connector, readiness, publication, delivery, dispatch, execution or mutation operation occurs.
- PostgreSQL tests cover canonical lock order, two database-time observations, concurrent unique
  winner, exact composite lineage, current destination generation/fence, append-only triggers,
  effective consumed/expired projection, guarded downgrade and no production fallback.
- API and UI tests cover workload-only POST, normal username/password session-only GET, personal-
  token/human/AI denial, no MFA or second-browser prompt, `no-store`, non-oracle errors, minimized
  schemas, zero disclosure and zero operational controls.
- Full backend and frontend suites, Alembic single-head and round-trip validation, real PostgreSQL
  CI, live desktop/mobile inspection, independent review, exact-head PR CI, SHA-locked merge and
  independent `main` CI are required for implementation delivery.
