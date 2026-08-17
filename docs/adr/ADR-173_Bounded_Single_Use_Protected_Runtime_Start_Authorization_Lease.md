# ADR-173: Bounded Single-Use Protected Runtime-Start Authorization Lease Without Runtime Start, Process, Scheduling, Inference, Network, Execution or Infrastructure Mutation Authority

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-17 |
| Owners | Workflow Architecture, Security Architecture, Deployment Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-160 through ADR-172 |

## Context

ADR-172 may produce one canonical `context_used_once_in_protected_boundary` result after the exact
protected runtime context is adopted once into an existing inactive runtime envelope. That result
is immutable historical evidence, not bearer authority. Its verified use-performed value proves
only the completed protected-side adoption transition, and all existing 26 authority declarations
remain false.

Atlas now needs the next smallest authorization boundary. The exact protected consumer workload
must be able to obtain one extremely short-lived lease authorizing only submission of a future
request that will atomically consume the lease and initiate one protected runtime-start attempt.
The ADR-172 result cannot itself authorize start, resume, process creation, scheduling or any other
operation. Treating it as such would launder historical outcome evidence into operational
authority.

Historical adoption success is also insufficient proof of current start eligibility. The protected
runtime envelope, destination generation, fence, slot generation, consumer binding, runtime-start
profile or policy may have expired, changed, been revoked, become ineligible or already acquired a
competing start authorization or attempt. Issuance therefore requires fresh signed protected-side
metadata and complete canonical lineage revalidation without exposing context, protected locators
or a reusable capability.

## Decision

Atlas will issue one immutable `WorkflowProtectedRuntimeStartAuthorizationLease` from one exact
canonical ADR-172 `context_used_once_in_protected_boundary` result. The lease authorizes only a
future request to the IMP-224 atomic protected runtime-start lease-consumption and start-attempt
boundary. IMP-223 performs no runtime start or resume, process creation, scheduling, prompt
construction, model inference, network or readiness activity, connector or MCP call, publication,
delivery, dispatch, generic execution or infrastructure mutation.

Only the exact code-owned protected consumer workload authenticated as
`service.workflow-protected-transport-target-context-capsule-consumer` for
`audience.workflow-protected-transport-target-context-capsule-consumer` may request issuance for
its own ADR-172 result. The subject and audience must equal the immutable consumer binding across
the complete ADR-160 through ADR-172 lineage. Human sessions, personal access tokens, AI agents,
attestors, executors, runtime identities, connectors, MCP tools, publishers and generic workflow
services fail closed before protected-state I/O.

The request contains only:

- ADR-172 use-result ID and canonical digest;
- code-owned protected runtime-start authorization policy ID and version; and
- tenant-scoped idempotency metadata.

The caller cannot supply or override context, handle, slot or runtime-envelope identity,
commitment, locator, material or lifecycle state; destination generation or fence; consumer,
attestor, runtime-start or execution profile; timing, lease duration or authority; endpoint,
credential, route, network, readiness, connector, MCP, inference, process, scheduling, dispatch,
execution or mutation fields. IDs, digests and integrity references are routing and integrity
metadata, never bearer authority.

### Canonical ADR-172 Eligibility

Issuance accepts only one terminal canonical ADR-172
`context_used_once_in_protected_boundary` result. Its timely verified signed executor receipt must
prove:

- the exact ADR-171 terminal result was the sole source for the adoption attempt;
- the exact protected-side unused-to-used compare-and-swap completed once;
- use count changed from zero to one;
- the adopted context became terminal and non-reusable and transient material was zeroized;
- destination generation and fence, exact protected-slot pre/post generations, consumer, policy,
  use profile and executor profile match the complete locked lineage;
- every forbidden effect and all existing 26 authority declarations are false; and
- the outcome is known and has no failure class, ambiguity or prohibited returned material.

`context_use_failed_without_use`, `context_use_outcome_uncertain`, pending, claim-only,
attempt-only, late, unsigned, malformed, ambiguous or receipt-free evidence is ineligible. The
ADR-172 result, attempt and claim must agree with the exact ADR-171 result and complete ADR-160
through ADR-172 lineage. Canonical digests, signatures, chronology and append-only relationships
must verify without repair, inference, fallback or caller-provided replacement evidence.

The `context_used_terminal` slot state means the protected context cannot be adopted or reused
again. It does not by itself prove that the existing inactive runtime envelope is currently
eligible to start. Only the dedicated fresh attestation and code-owned policy defined here may
establish that separate eligibility precondition.

### Fresh Signed Metadata-Only Runtime-Start Eligibility Attestation

Before opening the issuance transaction, Atlas generates one server nonce and obtains one fresh,
independently signed, metadata-only runtime-start lifecycle and eligibility attestation from the
trusted protected boundary. This passive evidence collection is not a readiness probe, process
operation, scheduler call or executor invocation. No protected runtime-start executor, process
manager, scheduler, model gateway, connector, MCP, provider or network call occurs during IMP-223
or while the PostgreSQL transaction is open.

The attestation canonically commits to:

- trusted attestor identity, signing-key ID and profile version;
- exact ADR-172 result, attempt and claim and complete ADR-160 through ADR-172 lineage digests;
- exact adopted-context and inactive runtime-envelope commitments known only inside the protected
  boundary;
- exact protected-slot commitment and receipt-bound post-adoption generation;
- exact consumer subject, audience, contract and code-owned purpose;
- exact destination boundary and deployment identity, current generation and fencing-token digest;
- exact code-owned protected runtime-start profile ID, version and digest;
- server-created nonce, observed time and attestation validity deadline;
- the adopted context remains terminal, non-reusable and bound to the same inactive runtime
  envelope;
- no runtime has started or resumed, no process has been created or scheduled and no start attempt
  is pending or terminal for the exact envelope and lineage;
- no competing runtime-start authorization or consumption claim exists;
- current destination generation, fence and exact slot post-generation remain canonical and the
  code-owned runtime-start profile remains eligible; and
- no raw context, handle, slot or runtime locator, prompt, model input/output, endpoint, credential,
  secret, bearer token, process payload or provider payload.

Unavailable, unsigned, malformed, future-dated, expired, mismatched, stale, negative, bearer,
started, resumed, scheduled, process-bearing, competing, locator-bearing or payload-bearing
evidence fails closed. Atlas verifies the captured attestation before the transaction and again
offline while canonical database locks are held. The attestation grants no authority and cannot
start, resume, create or schedule anything.

### Authorization Policy And Lease

The code-owned policy is `policy.workflow-protected-runtime-start-authorization` version `1.0`,
with purpose `purpose.workflow-protected-runtime-start-evaluation`. Its canonical digest,
consumer contract, attestor profile, protected runtime-start profile, destination profile,
maximum lifetime and authority declarations are code-owned and cannot be supplied by callers or
mutable configuration.

The lease is:

- append-only;
- single-use;
- non-renewable;
- non-transferable;
- non-bearer;
- valid for a positive interval no greater than one second;
- strictly bounded by the canonical protected runtime-envelope eligibility ceiling;
- strictly bounded by the fresh attestation validity deadline; and
- bound to the exact ADR-172 result and complete protected context lineage, consumer identity,
  destination generation and fence, exact slot post-generation, runtime-start profile, policy,
  purpose and idempotency claim.

The idempotency claim sets `protected_runtime_start_authority_granted = false` and grants no
authority. The immutable lease declaration may set only
`protected_runtime_start_authority_granted = true`. Every authorization decision and ordinary
API/UI projection treats that field as effectively true only while the lease is active and no
canonical future IMP-224 consumption/start claim exists. At or after expiry, or once that unique
future claim exists, effective `protected_runtime_start_authority_granted` is false without
mutating the lease row.

All existing 26 authority declarations remain exactly false on both claim and lease:

- endpoint resolution, route selection and route binding;
- credential selection, credential-assignment binding, credential access, credential brokerage,
  credential resolution and credential delivery;
- protected-artifact access;
- target-context capsule handoff and capsule opening;
- protected resident-context access and protected runtime-context injection;
- protected runtime-context use and general runtime use;
- runtime start and runtime resume;
- network access and readiness probing;
- connector activity;
- publication, delivery, dispatch and execution; and
- infrastructure mutation.

The new dedicated declaration means only that the exact workload may submit this exact lease to
the future IMP-224 boundary. It is not `runtime_start_authorized`, does not itself authorize a
runtime start, process creation or scheduling, and is unusable as a bearer capability by an
ordinary Atlas process. It cannot be interpreted as model-inference, connector, MCP, network,
dispatch, execution or infrastructure-operation authority.

### Durable Exact-Replay Preflight

Before requesting fresh attestation evidence, Atlas performs one durable replay lookup. Exact
replay with the same organization, environment, site, authenticated subject and audience,
idempotency key, request fingerprint and ADR-172 result returns the same minimized authorization
state without protected-boundary, attestor, executor, runtime, process, scheduler, model,
connector, MCP, provider or network I/O. The response projects dedicated authority using one
authoritative PostgreSQL statement and database timestamp; an expired or future-consumed lease
therefore replays with zero effective runtime-start-request authority.

Changed replay, competing identity, competing source result, digest mismatch, stale scope or a
prior nonmatching claim fails closed. A visible result ID, lease ID or integrity reference is never
authority. Replay never renews, transfers, replaces or reissues a lease and never invokes an
executor or starts a runtime.

### PostgreSQL Atomic Issuance

Atlas obtains the first authoritative PostgreSQL database timestamp before external attestation,
generates a one-time server nonce and verifies the returned signed metadata outside the issuance
transaction. It then starts one PostgreSQL transaction and locks the complete authoritative
ADR-160 through ADR-172 lineage in canonical oldest-to-newest order, ending with the ADR-172
result, current destination head, exact protected-slot head at the receipt-bound post-adoption
generation, protected runtime-envelope coordination head and any existing runtime-start
authorization claim.

Under those locks Atlas:

1. obtains the second authoritative PostgreSQL database timestamp;
2. revalidates organization, environment and site scope;
3. verifies every canonical digest, signature, receipt, chronology and composite lineage edge;
4. verifies the exact authenticated protected consumer subject and audience;
5. revalidates ADR-172 success and the all-false authority/effect contract;
6. revalidates destination deployment identity, current generation and fencing state;
7. proves the exact protected-slot head remains `context_used_terminal` at the signed post-adoption
   generation and has no competing lineage;
8. verifies the captured runtime-start lifecycle/eligibility attestation offline against the
   server nonce, both database-time observations and locked lineage;
9. proves a positive lease window no greater than one second and bounded by every relevant
   protected runtime-envelope and attestation deadline;
10. revalidates that no canonical runtime-start consumption claim, start attempt, runtime start or
    resume, process creation, scheduling, competing authorization or conflicting idempotency claim
    exists;
11. classifies exact replay or conflict; and
12. atomically appends one idempotency claim and one authorization lease.

Both database-time observations are durable validation inputs. The second timestamp, captured
after canonical locks are held, is authoritative for `issued_at` and the effective deadline.
`valid_until` is no later than that timestamp plus one second, the protected runtime-envelope
eligibility ceiling or the attestation deadline. No process clock can widen the interval.

The transaction performs no external I/O. No executor is called before, during or after issuance.
Canonical authorization audit payload and digest are stored with the claim and lease. External
audit and SIEM export occur only after commit as best-effort delivery of already committed
evidence. Delivery failure cannot roll back, duplicate, renew, transfer or widen authority.

Insertion races are classified in a new transaction under the same canonical locks. Exactly one
claim and lease may win for the source adoption lineage, exact slot post-generation, protected
runtime-envelope commitment and scoped idempotency key. Append-only evidence is never repaired,
replaced or mutated.

### Durable Persistence And Zero Disclosure

Production stores two append-only PostgreSQL tables:

- protected runtime-start authorization claims, unique by ADR-172 result, adopted-context/runtime-
  envelope lineage, exact slot post-generation and scoped idempotency key; and
- protected runtime-start authorization leases, unique by claim, ADR-172 result and protected
  runtime-envelope lineage.

Composite foreign keys bind the claim and lease to the exact ADR-172 result, attempt and use claim
and the complete upstream ADR-160 through ADR-172 lineage. Database CHECK constraints enforce the
code-owned policy, consumer, destination, attestor, runtime-start and exact-slot contracts;
single-use, non-renewable, non-transferable and non-bearer semantics; the positive at-most-one-
second effective deadline; all existing 26 false authorities; and the one dedicated lease-only
declaration. Triggers reject `UPDATE` and `DELETE`. Downgrade fails closed while either table
contains evidence.

Ordinary persistence, API, UI, logs, traces, metrics, audit payloads and events never expose raw
context; context, handle, slot or runtime-envelope identities, commitments, locators or material;
prompt or model data; endpoint or credential; attestation payload or nonce; internal destination
fence; or any bearer capability. Internal protected identifiers required for composite lineage
remain confined to the restricted PostgreSQL/protected-boundary path and are never presented as
authority.

Production requires PostgreSQL, the trusted runtime-start lifecycle/eligibility attestor and
code-owned verification keys. Unavailable defaults fail closed. There is no process-memory,
permissive, caller-asserted or unguarded synthetic fallback. A deterministic development attestor
is allowed only under explicit development composition and must perform no protected runtime,
process, scheduler, model, provider, network, connector, MCP or infrastructure operation.

### API And Human Presentation

The workload command is:

`POST /api/v1/workflows/protected-runtime-start-authorizations`

Only the exact protected consumer workload may call POST. Authorized humans may inspect a separate
minimized inventory through:

`GET /api/v1/workflows/protected-runtime-start-authorizations`

Human reads use the normal username/password browser session and dedicated read permission
`workflow.protected-runtime-start-authorizations.read`. No MFA, second login or authorized-browser-
session prompt is required. Command, query and error responses are `no-store`, minimized,
non-oracle and zero-disclosure.

The human response exposes only non-sensitive authorization identity and effective state,
issue/effective timestamps, consumer contract and purpose references, policy, runtime-start and
destination-profile references, the dedicated effective authority declaration, the existing all-
false authority contract and a non-sensitive integrity reference. It omits the ADR-172 source
result, upstream leases, protected context and runtime-envelope material, slot commitments,
receipts, attestation, nonce, route, credential, target, locator, idempotency, request fingerprint
and fencing material.

The UI section is titled `Protected runtime-start authorizations` and is strictly read-only. It
provides no authorize, consume, start, resume, retry, process, schedule, infer, connect, probe,
connector, MCP, publish, deliver, dispatch, execute or mutate control.

### Governance Invariants

AI remains advisory-only. No AI agent or human may directly request this workload authorization,
approve or consume it, or use it to operate infrastructure. IMP-223 creates no human or AI
operational control. Active Directory remains authentication-only; this decision creates no Active
Directory management capability or Active Directory MCP. Normal authorized human inventory reads
require no MFA or second browser session.

### IMP-224 Sequencing Contract

IMP-224 must atomically and irreversibly consume one exact unexpired ADR-173 lease and initiate one
protected runtime-start attempt at the same point of no return. It must commit the unique
consumption claim and started-attempt evidence before any future protected start executor call.

Atlas will not insert an additional consumption-only layer that consumes the lease without
initiating the one protected start attempt. Such a layer would add sequencing and recovery states
without strengthening the protected operation boundary. Actual start outcome, signed receipt,
uncertainty and no-retry rules remain for IMP-224 to define; ADR-173 neither invokes nor specifies
the start executor protocol beyond these atomicity requirements.

## Consequences

- Canonical ADR-172 success cannot silently become reusable runtime-start authority.
- Every future protected start request is preceded by fresh lifecycle proof and an exact-lineage
  lease lasting no more than one second.
- Existing runtime start/resume and all other 26 authority declarations remain false.
- The new dedicated declaration is confined to submission of one future IMP-224 request and is not
  direct start authority.
- Protected identities, locators and material remain inside restricted trust boundaries.
- Append-only PostgreSQL claims expose exact replay and competing issuance without mutating history.
- Actual runtime start and every process, scheduler, inference, network, connector, MCP, dispatch,
  execution or infrastructure side effect remain unavailable until IMP-224.

## Deferred Scope

- Runtime-start lease consumption and the protected runtime-start attempt defined by IMP-224
- Runtime start, resume, process creation, process control or scheduling
- Prompt construction, model inference, query execution or code execution
- Model input, output or derived-context return
- Context, handle, slot or runtime-envelope reveal, copy, download, export or ordinary-process use
- Endpoint or credential reveal, delivery, copy, download or export
- DNS, TLS, socket, proxy, network establishment or readiness probing
- Connector, MCP, broker, provider SDK or capability calls
- Event acknowledgement, retry or quarantine release
- Worker delivery, dispatch or workflow state transition
- Infrastructure mutation
- Lease renewal, transfer, replacement or reissue
- Automatic retry, cleanup, rollback, recovery, reauthorization or remediation
- Human- or AI-initiated authorization, start or operation control
- Active Directory management or an Active Directory MCP

## Validation

- Domain and application tests must prove exact workload identity, caller-field prohibition,
  canonical ADR-172-success-only eligibility, complete lineage, signed fresh nonce-bound
  metadata-only attestation, one-second bounds, lease-only dedicated authority, all 26 existing
  false authorities, exact replay, changed replay, expiry, competing claims and fence/slot drift.
- Call-order tests must prove durable replay precedes attestation and that no executor, runtime,
  process, scheduler, model, connector, MCP, readiness, publication, delivery, dispatch, execution
  or mutation operation occurs.
- PostgreSQL tests must cover canonical full-lineage lock order, two database-time observations,
  concurrent unique winner, exact composite lineage, current destination/fence/slot/envelope state,
  append-only triggers, effective consumed/expired projection, guarded downgrade and no production
  fallback.
- API and UI tests must cover workload-only POST, normal username/password session read-only GET,
  personal-token/human/AI denial, no MFA or second-browser prompt, `no-store`, non-oracle errors,
  minimized schemas, zero disclosure and zero operational controls.
- Implementation delivery must include full backend/frontend regression, Alembic single-head and
  round-trip validation, real PostgreSQL CI, live desktop/mobile inspection, independent review,
  exact-head PR CI, SHA-locked merge and independent `main` CI.
