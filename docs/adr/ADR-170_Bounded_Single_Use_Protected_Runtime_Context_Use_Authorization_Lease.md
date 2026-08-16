# ADR-170: Bounded Single-Use Protected Runtime-Context Use Authorization Lease Without Runtime Use, Start, Resume, Network, Execution or Infrastructure Mutation Authority

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-16 |
| Owners | Workflow Architecture, Deployment Architecture, Security Architecture, Identity Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-160 through ADR-169 |

## Context

ADR-169 may irreversibly consume one exact protected runtime-context injection lease and ask one
trusted protected-boundary injector to place the exact opaque context into one exact inert runtime
slot. A canonical `injected_into_protected_runtime_slot` result and trusted signed injector receipt
prove only that the protected transition completed, the source handle was consumed and the slot
advanced to its exact post-injection generation. They do not authorize context use, runtime start
or resume, query or code execution, endpoint or credential access, network or connector activity,
readiness probing, publication, delivery, dispatch, workflow execution or infrastructure mutation.

Atlas now needs the next smallest authorization boundary. The exact protected consumer workload
must be able to obtain one extremely short-lived lease that authorizes only a future request to a
separately designed atomic protected runtime-context use-consumption operation. Issuance must prove
that the complete ADR-160 through ADR-169 lineage remains canonical and that the exact injected
context is still present, inert, unused and eligible for one exact code-owned runtime-context use
profile, without revealing its identity, commitment, locator, material or a reusable capability to
an ordinary Atlas process.

Historical injection success alone is insufficient. The injected context may have expired, been
revoked, cleared, superseded, used or become ineligible after a destination deployment generation,
fencing state, slot generation or runtime-context use profile change. A signed ADR-169 receipt
cannot be treated as current protected-slot lifecycle state, and possession of an injection result
identifier or human-visible integrity reference cannot become context-use authority.

## Decision

Atlas will issue one immutable `WorkflowProtectedRuntimeContextUseAuthorizationLease` from one
exact canonical ADR-169 `injected_into_protected_runtime_slot` result. The lease authorizes only a
future request to a separately designed atomic protected runtime-context use-consumption boundary.
IMP-220 does not consume or use the injected context, start or resume a runtime, execute a query or
code, establish a network path, call a connector, probe readiness, publish or deliver an event,
dispatch work, execute a workflow step or mutate infrastructure.

Only the exact code-owned protected consumer subject
`service.workflow-protected-transport-target-context-capsule-consumer` authenticated for
`audience.workflow-protected-transport-target-context-capsule-consumer` may request issuance for
its own ADR-169 result. The authenticated subject and audience must equal the canonical ADR-161
binding and every consumer-bound ADR-162 through ADR-169 claim, attempt, lease, result and signed
receipt. Human sessions, personal access tokens, AI agents, MCP tools, attestors, accessors,
injectors, runtime identities, publishers, connector workloads and generic workflow services fail
closed.

The request contains only:

- ADR-169 injection-result ID and canonical digest;
- code-owned protected runtime-context use-authorization policy ID and version; and
- idempotency metadata.

The caller cannot supply or override injected-context identity, commitment, locator, material,
lifetime or state; runtime-slot identity, commitment, locator, generation or fence; destination
identity, generation or fence; consumer, attestor or runtime-context use profile; lease duration,
authority, endpoint, credential, route, network, readiness, publication, delivery, dispatch,
execution or mutation fields. Atlas derives every such value from authenticated context, canonical
append-only lineage, code-owned profiles and authoritative server-side state.

### Canonical Injection Eligibility

Issuance accepts only one terminal canonical ADR-169
`injected_into_protected_runtime_slot` result. The result must contain a trusted signed injector
receipt completed strictly before its immutable injection deadline and must prove:

- the exact ADR-168 lease was irreversibly consumed by one canonical claim and started attempt;
- the exact non-bearer protected runtime-context handle was atomically consumed;
- the exact opaque context was injected into the expected empty inert protected slot;
- the exact slot advanced once from the committed pre-generation to the receipt-bound
  post-generation;
- injected context remained inert and every forbidden runtime, process, filesystem, provider,
  network, connector, readiness, publication, delivery, dispatch, execution and infrastructure
  side effect was false; and
- the outcome is known and carries no failure class, contradictory transition or cleanup
  uncertainty.

`injection_failed`, `injection_outcome_uncertain`, `injection_pending`, claim-only, attempt-only,
late, unsigned, malformed, ambiguous, contradictory or receipt-free evidence is ineligible. The
ADR-169 result, attempt and claim must agree with the exact ADR-168 authorization and complete
ADR-160 through ADR-169 lineage. Canonical digests, signatures and append-only relationships must
verify without repair, inference, fallback or caller-provided replacement evidence.

### Fresh Protected-Slot Lifecycle And Use-Eligibility Attestation

Before opening the issuance transaction, Atlas obtains one fresh, independently signed,
server-nonce-bound and metadata-only protected-slot lifecycle and use-eligibility attestation from
the trusted protected consumer boundary. This is passive eligibility evidence, not runtime use,
runtime readiness probing or a runtime invocation. No protected-boundary, attestor, runtime,
connector, provider or network call may occur while the PostgreSQL transaction is open.

The attestation canonically commits to:

- trusted attestor identity, signing-key ID and profile version;
- exact ADR-169 result, attempt and claim and complete ADR-160 through ADR-169 lineage digests;
- exact injected-context commitment known only inside the protected boundary;
- exact protected runtime-slot commitment, post-injection generation and lifecycle state;
- exact consumer subject, audience, contract and code-owned purpose;
- exact destination boundary and deployment identity, current generation and fencing-token digest;
- exact code-owned runtime-context use profile ID, version and digest;
- server-created nonce, observed time and attestation validity deadline;
- injected context present, inert, unexpired, unrevoked, uncleared, unsuperseded and unused;
- no runtime started or resumed, no context active or in use and no outstanding use-consumption or
  competing use-authorization claim;
- current destination generation and fence, exact current slot post-generation and eligibility of
  the runtime-context use profile for that destination, slot and lineage; and
- no raw context, handle material, slot locator, endpoint, credential, secret, bearer token,
  runtime payload or provider payload.

Unavailable, unsigned, malformed, future-dated, expired, mismatched, stale, negative, active,
bearer, revoked, cleared, superseded, used, competing, locator-bearing or payload-bearing evidence
fails closed. Atlas verifies the captured attestation before the transaction and again offline
while canonical database locks are held. The attestation cannot perform or authorize actual
context use, runtime start or resume, readiness probing, connector activity or execution.

### Authorization Policy And Lease

The code-owned policy is `policy.workflow-protected-runtime-context-use-authorization` version
`1.0`, with purpose `purpose.workflow-protected-runtime-context-use-evaluation`. Its canonical
digest, consumer contract, attestor profile, runtime-context use profile, destination profile,
maximum lifetime and authority declaration are code-owned and cannot be supplied by callers or
mutable configuration.

The lease is:

- append-only;
- single-use;
- non-renewable;
- non-transferable;
- non-bearer;
- valid for at most one second;
- strictly bounded by the canonical injected-context lifetime ceiling;
- strictly bounded by the fresh attestation validity deadline; and
- bound to the exact ADR-169 result and protected injected-context lineage, consumer identity,
  destination generation and fence, slot post-generation, runtime-context use profile, policy,
  purpose and idempotency claim.

The idempotency claim sets `protected_runtime_context_use_authority_granted = false` and grants no
authority. The immutable lease declaration sets only
`protected_runtime_context_use_authority_granted = true`. Every authorization decision and
ordinary API/UI projection treats that field as effectively true only while the lease is active
and no canonical future use-consumption claim exists. At or after expiry, or once a future unique
consumption claim exists, effective `protected_runtime_context_use_authority_granted` is false
without mutating the lease row.

Every pre-existing authority declaration remains exactly false on claim and lease, including:

- endpoint resolution, route selection and route binding;
- credential selection, assignment binding, access, brokerage, resolution and delivery;
- protected-artifact access;
- target-context capsule handoff and capsule opening;
- protected resident-context access and protected runtime-context injection;
- network access and readiness probing;
- publication, delivery, dispatch and execution; and
- infrastructure mutation.

The dedicated declaration means only that a future operation may request atomic consumption of
this exact lease. It is not injected-context access or runtime-use authority usable by an ordinary
process and does not grant any current runtime capability.

### Durable Exact-Replay Preflight

Before requesting fresh attestation evidence, Atlas performs one durable replay lookup. Exact
replay with the same organization, environment, site, authenticated subject and audience,
idempotency key, request fingerprint and ADR-169 result returns the same minimized authorization
state without protected-boundary, attestor, runtime, connector, provider or network I/O. The
response projects dedicated authority using one authoritative PostgreSQL statement and database
timestamp; an expired or later-consumed lease therefore replays with zero effective context-use
request authority.

Changed replay, competing identity, competing source result, digest mismatch, stale scope or a
prior nonmatching claim fails closed. A visible result ID, lease ID or integrity reference is
routing metadata, never authority. Replay never renews, transfers, replaces or reissues a lease and
never performs actual protected runtime-context use.

### PostgreSQL Atomic Issuance

Atlas obtains the first authoritative PostgreSQL database timestamp before external attestation,
generates a one-time server nonce and verifies the returned signed metadata outside the issuance
transaction. It then starts one PostgreSQL transaction and locks the complete authoritative
lineage in canonical oldest-to-newest order, ending with the ADR-169 result, the current
destination head, exact protected-slot head at the receipt-bound post-generation and any existing
runtime-context use-authorization claim.

Under those locks Atlas:

1. obtains the second authoritative PostgreSQL database timestamp;
2. revalidates organization, environment and site scope;
3. verifies every canonical digest, signature and composite lineage edge;
4. verifies the exact authenticated protected consumer subject and audience;
5. revalidates ADR-169 success, injector-receipt signature and strict deadlines;
6. revalidates destination deployment identity, current generation and fencing state;
7. proves the exact protected-slot head remains at the expected post-injection generation and inert
   state;
8. verifies the captured lifecycle/use-eligibility attestation offline against the server nonce,
   both database-time observations and locked lineage;
9. proves sufficient remaining injected-context and attestation lifetime for a positive lease
   window no greater than one second;
10. revalidates that no canonical use-consumption claim, actual use, runtime activation, competing
    authorization or conflicting idempotency claim exists;
11. classifies exact replay or conflict; and
12. atomically appends one idempotency claim and one authorization lease.

Both database-time observations are durable inputs to issuance validation. The second timestamp,
captured after canonical locks are held, is authoritative for `issued_at` and the effective
deadline. `valid_until` is no later than that timestamp plus one second, the canonical injected-
context lifetime ceiling or the attestation deadline. No process clock can widen the window.

The transaction performs no external I/O. Canonical authorization audit payload and digest are
stored with the claim and lease. External audit and SIEM export occur only after commit and are
best-effort delivery of already committed evidence. Audit delivery failure cannot roll back,
duplicate, renew, transfer or widen authority.

Insertion races are classified in a new transaction under the same canonical locks. Exactly one
claim and lease may win for the source injected-context lineage, exact slot post-generation and
scoped idempotency key. Append-only evidence is never repaired, replaced or mutated.

### Durable Persistence And Zero Disclosure

Production stores two append-only tables:

- protected runtime-context use-authorization claims, unique by ADR-169 result, injected-context
  lineage, exact slot post-generation and scoped idempotency key; and
- protected runtime-context use-authorization leases, unique by claim, ADR-169 result and injected-
  context lineage.

Composite foreign keys bind the claim and lease to the exact ADR-169 result, attempt and injection-
consumption claim and their complete upstream lineage. Database CHECK constraints enforce the
code-owned policy, consumer, destination, attestor, runtime-context use and slot contracts;
single-use, non-renewable, non-transferable and non-bearer semantics; the positive at-most-one-
second effective deadline; and the one-dedicated-authority contract. Triggers reject `UPDATE` and
`DELETE`. Downgrade fails closed while either table contains evidence.

Ordinary persistence, API, UI, logs, traces, metrics, audit payloads and events never expose the
injected-context identity, commitment, locator or material; runtime handle; protected-slot
commitment or locator; endpoint or credential; attestation payload or nonce; internal destination
fence; or any bearer capability. Internal protected identifiers required for composite lineage
remain confined to the restricted PostgreSQL/protected-boundary path and are never presented as
authority.

Production requires PostgreSQL, the trusted protected-slot lifecycle/use-eligibility attestor and
code-owned verification keys. Unavailable defaults fail closed. There is no process-memory,
permissive, caller-asserted or unguarded synthetic fallback. A deterministic development attestor
is allowed only under explicit development composition and must perform no real runtime, process,
provider, network, connector or infrastructure operation.

### API And Human Presentation

The workload command is:

`POST /api/v1/workflows/protected-runtime-context-use-authorizations`

Only the exact protected consumer workload may call POST. Authorized humans may inspect a separate
minimized inventory through:

`GET /api/v1/workflows/protected-runtime-context-use-authorizations`

Human reads use the normal username/password browser session and a dedicated read permission. No
MFA, second login or authorized-browser-session prompt is required. Command, query and error
responses are `no-store`, minimized, non-oracle and zero-disclosure.

The human response exposes only non-sensitive authorization identity and effective state,
issue/effective timestamps, consumer contract and purpose references, policy, runtime-context use
and destination-profile references, the dedicated effective authority declaration, the existing
all-false authority contract and a non-sensitive integrity reference. It omits the ADR-169 source
result, injection lease, runtime handle, injected-context and slot commitments, receipts,
attestation, nonce, route, credential, target, locator, idempotency, request-fingerprint and fencing
material.

The UI section is titled `Protected runtime-context use authorizations` and is strictly read-only.
It provides no authorize, consume, retrieve, reveal, copy, download, use, start, resume, connect,
probe, publish, deliver, dispatch, execute or mutate control.

### Governance Invariants

AI remains advisory-only. No AI agent may request this workload authorization, approve it, consume
it or use it to operate infrastructure. Active Directory remains authentication-only; this ADR
creates no Active Directory management capability or Active Directory MCP. Normal authorized human
inventory reads require no MFA or second browser session.

## Consequences

- Successful inert-slot injection does not silently become reusable context-use or runtime
  authority.
- Every future use request is preceded by a fresh protected-slot lifecycle proof and an exact-
  lineage lease lasting no more than one second.
- Injected-context identity, slot locator and material remain inside the trusted protected
  boundary.
- Append-only claims make replay and competing authorization visible without mutating history.
- Actual context use, runtime start or resume and every network, connector, dispatch, execution or
  infrastructure side effect remain unavailable until separate boundaries exist.
- The complete lineage and mutable destination/slot locks increase implementation cost but keep
  the first context-use authorization auditable and fail-closed.

## Deferred Scope

- Protected runtime-context use-authorization lease consumption
- Injected-context retrieval, reveal, copy, download, export, activation or actual use
- Runtime start, resume, query execution, code execution or process creation
- Runtime-handle or protected-slot lookup, retrieval, reveal, copy, download, export or direct use
- Endpoint or credential reveal, delivery, copy, download or export
- DNS, TLS, socket, proxy, network establishment or readiness probing
- Connector, MCP, broker, provider SDK or capability calls
- Event publication, acknowledgement, retry or quarantine release
- Worker delivery, dispatch or workflow state transition
- Infrastructure mutation
- Lease renewal, transfer, replacement or reissue
- Automatic retry, cleanup, rollback, recovery or remediation
- Human- or AI-initiated context use or runtime operation
- Active Directory management or an Active Directory MCP; AD remains authentication-only

## Validation

- Domain and application tests cover exact workload identity, caller-field prohibition, canonical
  ADR-169 success eligibility, injector-receipt verification, signed context lifetime, fresh nonce-
  bound slot lifecycle/use-eligibility attestation, one-second bounds, one-dedicated-authority
  semantics, exact replay, changed replay, expiry, revocation, use, competing claim, slot-generation
  drift and destination-fence drift.
- Call-order tests prove durable replay occurs before attestation and that no runtime use, start,
  resume, connector, readiness, publication, delivery, dispatch, execution or mutation operation
  occurs.
- PostgreSQL tests cover canonical lock order, two database-time observations, current destination
  and exact slot heads, concurrent unique winner, exact composite lineage, append-only triggers,
  effective consumed/expired projection, guarded downgrade and no production fallback.
- API and UI tests cover workload-only POST, normal username/password session-only GET, personal-
  token/human/AI/MCP denial, no MFA or second-browser prompt, `no-store`, non-oracle errors,
  minimized schemas, zero disclosure and zero operational controls.
- Full backend and frontend suites, Alembic single-head and round-trip validation, real PostgreSQL
  CI, live desktop/mobile inspection, independent review, exact-head PR CI, SHA-locked merge and
  independent `main` CI are required for implementation delivery.
