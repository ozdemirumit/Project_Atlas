# ADR-169: Atomic Single-Use Protected Runtime-Context Injection Lease Consumption and Inert Protected-Slot Injection

- Status: Accepted
- Date: 2026-08-16
- Owners: Workflow Architecture, Security Architecture, Platform Engineering
- Related: ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032,
  ADR-160 through ADR-168

## Context

ADR-168 may issue one append-only, non-bearer authorization lease lasting no more than one second.
The lease authorizes only a future request to consume protected runtime-context injection authority.
It does not retrieve or reveal a runtime handle, inject context, use a runtime, establish a network
path, call a connector, dispatch work, execute a workflow step or mutate infrastructure.

Atlas now needs the next smallest functional boundary. The exact protected consumer workload must
be able to irreversibly consume one ADR-168 lease and ask one trusted protected-boundary injector to
atomically place the exact opaque context represented by the protected handle into one exact inert
runtime slot. Ordinary Atlas processes must never receive the handle, its locator or material, the
slot locator, credentials, endpoint material or a reusable capability.

Injection is the first boundary in this lineage that mutates protected runtime-slot state. A crash,
timeout, late receipt or ambiguous partial transition after the injector may have started must not
restore the lease, retry the injector or represent the outcome as known. A successful injection is
evidence that inert context exists in the protected slot. It is not runtime-use, network, connector,
readiness, dispatch, execution or infrastructure-mutation authority.

## Decision

Atlas will implement one operation named protected runtime-context injection consumption. Lease
consumption and protected-slot injection belong to the same application operation and API boundary,
but not to one database transaction:

1. classify durable replay before external I/O;
2. obtain fresh signed handle-lifecycle and exact-slot readiness evidence;
3. lock and revalidate the complete ADR-160 through ADR-168 lineage and mutable destination/slot
   heads in PostgreSQL;
4. atomically append one consumption claim and one started attempt;
5. commit that transaction as the irreversible point of no return;
6. call the trusted injector exactly once outside the transaction; and
7. independently verify and append one signed known result or one explicit receipt-free uncertain
   result.

Consumption and injection will not be exposed as two independent APIs. A second caller-visible step
would create an authority gap and risk turning a claim or attempt identifier into a bearer token.

### Caller And Request Boundary

Only the exact code-owned protected consumer workload subject and audience bound through the
canonical ADR-167 and ADR-168 lineage may call POST. Human sessions, personal access tokens, AI
agents, MCP tools, generic workflow workers, injector identities and every other workload fail
closed.

Caller input is limited to:

- the ADR-168 authorization lease ID;
- the code-owned consumption policy ID and version;
- an idempotency key and request fingerprint; and
- explicit acknowledgement that consumption is irreversible and uncertainty requires a new human-
  governed investigation rather than retry.

Handle, slot, destination, generation, fence, injector, attestor, receipt, deadline, lifetime and
authority fields are server-derived. Visible identifiers and integrity references are never
authority.

### Durable Replay Preflight

Before any attestor, injector or other external boundary is called, Atlas queries durable state by
the scoped idempotency identity, lease lineage, handle commitment and exact slot pre-generation.

- An exact terminal replay returns the same minimized terminal state.
- Claim-only or started-attempt replay returns `injection_pending` before the immutable deadline and
  `injection_outcome_uncertain` at or after it.
- Changed or competing replay fails closed.
- Replay never calls the injector again and never restores or replaces the lease.

Historical lifecycle, readiness and injector receipts are verified offline with their exact code-
owned verification keys. Replay performs no live attestor or injector I/O.

### Fresh Time-Of-Use Evidence

After replay misses, Atlas obtains signed, server-nonce-bound and metadata-only evidence proving:

- the exact protected runtime handle remains present, unexpired, unrevoked, undestroyed,
  uninjected, unused and non-bearer;
- the destination generation and fencing token remain current;
- one exact protected runtime-slot commitment exists at the expected pre-mutation generation and is
  empty, inert and eligible for the code-owned slot profile;
- the injector contract and implementation are eligible for that exact destination and slot; and
- injection cannot start a runtime, open a network path, call a connector, probe readiness,
  dispatch work, execute code or mutate infrastructure.

The attestation contains no handle identity, locator, material, slot locator, endpoint, credential
or reusable token. Attestation validity is strictly bounded by the handle lifetime, lease deadline
and code-owned policy maximum.

### Canonical Locks And Point Of No Return

PostgreSQL obtains an authoritative database timestamp, then locks the complete canonical lineage
oldest-to-newest, including the ADR-168 claim and lease, followed by the current destination head,
the exact slot head and any competing injection-consumption claim. Under those locks Atlas:

1. obtains a second authoritative database timestamp;
2. revalidates every canonical digest, signature, scope, identity, deadline and all-false upstream
   authority declarations;
3. proves the ADR-168 lease is active, unconsumed and bound to the same handle, destination,
   injector and slot profile;
4. proves the mutable destination and slot heads match the attested generation and fence;
5. proves no claim exists for the lease, handle or `(destination, slot commitment,
   pre-generation)` tuple; and
6. appends one immutable claim and one immutable started attempt in one transaction.

No attestor, injector, connector, network, publication, dispatch or audit-export I/O occurs while
the transaction is open. Claim and attempt commit is the irreversible point of no return. After
commit, the lease and handle lineage remain consumed for success, known failure, timeout, crash,
late receipt, invalid receipt, partial mutation, persistence ambiguity and uncertainty.

### Trusted Protected-Boundary Injector

After commit, Atlas builds one signed instruction from the persisted attempt and sends only an
opaque protected-operation reference plus the instruction digest to the approved injector. The
injector independently resolves protected state inside the trusted boundary and performs one atomic
compare-and-swap over:

- the exact protected handle commitment and uninjected state;
- destination generation and fence;
- exact slot commitment and pre-mutation generation; and
- expected empty, inert slot state.

Success consumes the handle, injects only inert context and advances the exact slot generation. It
does not start or resume a runtime and creates no process, filesystem, provider, network, connector,
readiness, publication, delivery, dispatch, execution or infrastructure side effect.

Production requires an approved trusted injector, trusted lifecycle/readiness attestors and
receipt-specific verification keys. Unavailable defaults fail closed. A deterministic development
injector is allowed only under explicit development composition and must perform no real protected
state, network, process, provider or infrastructure operation.

### Signed Receipt And Outcomes

The injector returns only a signed minimized receipt binding the lease, claim, attempt, instruction
digest, handle commitment, destination generation/fence, injector identity, slot profile, exact slot
commitment, pre- and post-generation, completion time, deadline and every forbidden side effect as
false. The receipt key is distinct from lifecycle and readiness attestation keys.

Atlas may append:

- `injected_into_protected_runtime_slot` only when a timely valid receipt proves exact atomic
  injection, handle consumption, slot-generation advance, inert context and zero forbidden effects;
- `injection_failed` only when a timely valid receipt proves no slot mutation or resident injected
  context remains and all temporary material was zeroized; or
- `injection_outcome_uncertain` for timeout, crash, late/invalid/unsigned receipt, partial or
  contradictory transition, cleanup uncertainty, persistence ambiguity or any condition not
  satisfying a known outcome.

Known success and failure require a verified receipt. Receipt-free persistence is limited to
explicit uncertainty. A late receipt never changes an already uncertain outcome and no outcome
causes an automatic retry, cleanup or recovery action.

### Authority Separation

Claims, attempts, receipts and results are evidence, not authority. Every existing operational
authority declaration remains false. `runtime_slot_mutation_performed` is an outcome fact on a
verified success receipt; it is not infrastructure-mutation authority.

Runtime use, start, resume, query execution, endpoint resolution, routing, credential access,
network access, connector calls, readiness probing, publication, delivery, dispatch, execution and
infrastructure mutation require later independent authorization boundaries.

### Durable Persistence

Production stores append-only:

- injection-consumption claims, unique by lease, protected-handle commitment, exact slot
  pre-generation and scoped idempotency identity;
- injection attempts, unique by claim and signed injector instruction; and
- injection results, unique by attempt and distinguishing signed known outcomes from receipt-free
  uncertainty.

Mutable destination and slot heads are current-state records locked with `FOR UPDATE`. Immutable
claims, attempts and results preserve point-in-time snapshots and are not exact-foreign-keyed to a
mutable head. Composite lineage constraints, uniqueness, chronology checks and append-only triggers
independently enforce the contract. The ADR-168 authorization projection derives `consumed=true`
from the canonical consumption claim and grants zero effective authority thereafter.

### API And Human Presentation

The workload endpoint is:

`POST /api/v1/workflows/protected-runtime-context-injection-consumptions`

It returns minimized, non-oracle, `no-store` status and a non-sensitive integrity reference. Human
users receive only a username/password-session-protected, minimized, `no-store` GET on the same
path. No MFA or second authorized-browser-session prompt is required by default.

The read-only UI section is titled `Protected runtime-context injection consumptions`. It contains
no consume, inject, retry, reveal, copy, download, use, connect, probe, publish, deliver, dispatch,
execute or mutate control. It discloses no handle, slot locator, endpoint, credential, nonce,
idempotency material, protected reference or raw receipt.

## Consequences

- Used authority cannot become reusable after a crash or uncertain injector outcome.
- Exact-slot CAS prevents duplicate handle injection and stale slot mutation.
- Injection success is inert evidence and cannot silently become runtime-use or execution authority.
- Ordinary Atlas processes continue to have zero access to handle or slot material.
- The wider lineage and live PostgreSQL concurrency tests increase implementation cost but make the
  first protected runtime-state mutation auditable and fail-closed.

## Deferred Scope

- Runtime-slot context use, runtime start, resume or execution
- Runtime-handle lookup, retrieval, reveal, copy, download, export or direct use
- Endpoint or credential reveal, delivery, copy, download or export
- DNS, TLS, socket, proxy, network establishment or readiness probing
- Connector, MCP, broker, provider SDK or capability calls
- Event publication, acknowledgement, retry or quarantine release
- Worker delivery, dispatch or workflow state transition
- Infrastructure mutation
- Automatic retry, cleanup, rollback, recovery or remediation
- Human- or AI-initiated injection or runtime use
- Active Directory management or an Active Directory MCP; AD remains authentication-only

## Validation

- Domain and application tests cover exact policy, caller-field prohibition, irreversible
  acknowledgements, slot pre/post generation, deadlines, one-call ordering and all-false authority.
- Replay tests prove terminal, pending and uncertainty classification occurs before external I/O and
  the injector is never retried.
- Injector tests cover atomic CAS, exact slot/handle binding, inert success, known failure, partial
  mutation, timeout, late/invalid receipt and every forbidden side effect.
- PostgreSQL tests cover canonical locks, two database-time observations, one winner per lease,
  handle and slot pre-generation, append-only chronology, consumed projection and guarded downgrade.
- API and UI tests cover workload-only POST, normal session-only GET, human/PAT/AI/MCP denial,
  minimized `no-store` schemas, zero disclosure and zero operational controls.
- Full backend and frontend suites, Alembic single-head and round-trip validation, real PostgreSQL
  CI, live browser inspection, independent review, exact-head PR CI, SHA-locked merge and independent
  `main` CI are required for delivery.
