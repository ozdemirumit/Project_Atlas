# ADR-177: Bounded Single-Use Protected Runtime Process-Creation Authorization Lease

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-18 |
| Owners | Workflow Architecture, Security Architecture, Deployment Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-160 through ADR-176 |

## Context

ADR-176 may produce one canonical `runtime_ready_in_protected_boundary` result after atomically
consuming the ADR-175 lease and recording exactly one readiness-assessment attempt. That result is
immutable historical evidence that the exact protected runtime was ready at the verified time. It
is non-bearer evidence and grants no process-creation, scheduling, execution or other operational
authority.

Atlas needs a separate authorization boundary before any future process-creation request may be
submitted. Treating readiness as direct process-creation authority would collapse observation and
authorization, permit stale evidence to be reused and allow human, AI, retry or event paths to cross
an operational boundary without a short-lived, single-use grant.

This decision authorizes only a future request. It does not define or perform process creation. The
exact process primitive and the consumption protocol remain deferred to ADR-178 and ATLAS-IMP-228.

## Decision

Atlas will permit only the exact protected consumer workload bound through the canonical ADR-160
through ADR-176 lineage to request a protected runtime process-creation authorization lease. The
sole eligible source is one canonical, timely verified
`runtime_ready_in_protected_boundary` result.

After fresh protected-boundary attestation and complete PostgreSQL revalidation, Atlas may append
one immutable authorization claim and one immutable lease. The lease:

- expires no later than one second after authoritative PostgreSQL issuance time;
- is single-use, non-renewable, non-transferable and non-bearer;
- permits only submission of one future process-creation request for the exact lineage;
- carries no direct process-creation, scheduling, dispatch or execution authority; and
- cannot be converted into existing authority or reused by another identity, tenant, runtime or
  request.

Only an active lease may set
`protected_runtime_process_creation_authority_granted=true`. Every existing authority declaration
remains false. The field means only that the bound workload may submit one future ATLAS-IMP-228
request. It does not mean that a process exists, is scheduled, is runnable or has executed.

### Exact Eligibility

The source result must be the canonical terminal ADR-176 result for the exact tenant, protected
consumer contract, runtime-start lineage, destination fence and protected slot generation. The
result must be `runtime_ready_in_protected_boundary`; not-ready, failed-without-assessment,
pending, expired or uncertain outcomes are ineligible.

Before opening the PostgreSQL transaction, Atlas obtains fresh, signed, server-nonce-bound,
metadata-only protected-boundary attestation. The attestation must prove that the exact runtime:

- remains started and ready;
- remains bound to the current destination fence and protected slot generation;
- remains current under the code-owned process-creation authorization policy;
- has no process created or scheduled under this lineage; and
- has no pending or conflicting process-creation, publication, orchestration or execution state.

The attestation contains no runtime locator, process handle, command, executable, argument,
environment, credential, endpoint or reusable protected material. It is evidence for one
transaction only and is never bearer authority.

### Exact Caller And Request

Only the authenticated protected consumer workload subject and audience already fixed by the
canonical ADR-160 through ADR-176 lineage may POST. Human sessions, personal access tokens, AI
agents, MCP tools, connectors, generic workers and recovery workers fail closed before protected-
state I/O.

The caller supplies only:

- the canonical ADR-176 readiness-result ID;
- code-owned process-creation authorization policy ID and version;
- a tenant-scoped idempotency key; and
- explicit acknowledgement that the lease is single-use and authorizes only a future request.

The caller cannot supply readiness or lineage digests, lease timing, authority values, process
type, command, executable, arguments, environment, runtime locator or material, endpoint,
credential, prompt, model, provider, transport, publication, delivery, dispatch, execution or
mutation values. Atlas derives integrity references and deadlines from trusted state and code-owned
policy.

### Code-Owned Policy And PostgreSQL Authority

PostgreSQL is the sole production authority. The repository performs durable replay
classification as its first operation, then locks and revalidates in canonical order:

1. the complete immutable ADR-160 through ADR-176 lineage;
2. the canonical ready result and its exact readiness claim, attempt and lease ancestry;
3. the current destination generation and fencing token;
4. the exact protected slot generation;
5. the terminal started runtime coordination head, read-only;
6. current pending publication and orchestration fences relevant to the same lineage; and
7. competing process-creation authorization claims and leases in stable key order.

The transaction observes authoritative database time before and after locking. At the final
observation, the readiness result and fresh attestation must remain timely, every fence must remain
current and the requested deadline must leave the code-owned safety margin while remaining no more
than one second after issuance. Atlas then atomically appends the claim and lease.

Append-only triggers, exact composite foreign keys and unique constraints enforce one active grant
for the exact source lineage, tenant-scoped idempotency, complete ancestry and rejection of update,
delete, truncate, changed replay, stale generation and cross-lineage evidence. Production never
falls back to process-local or in-memory authority.

### Replay, Expiry And Cancellation

- Exact replay returns the same minimized claim and lease without extending its deadline.
- The same idempotency key with changed request, identity, scope or lineage fails closed.
- Concurrent requests have at most one winner for the exact source lineage.
- An expired lease cannot be renewed, replaced, transferred or restored.
- Cancellation before commit appends nothing; cancellation at or after commit does not remove,
  extend or reissue the lease.
- Lineage drift, readiness drift, stale attestation, fence drift, clock-margin failure, persistence
  ambiguity or unavailable PostgreSQL fails closed.
- Event replay, HTTP retry middleware, workflow recovery, scheduler, outbox, DLQ and audit-export
  paths cannot issue, consume or replace the lease.

No recovery path may infer process creation from lease issuance. Only a future ADR-178 protocol may
consume the exact active lease and define an operational point of no return.

### Prohibited Effects And Material

ATLAS-IMP-227 and this lease perform or carry none of the following:

- process creation, fork, spawn, launch, resume, restart, stop or scheduling;
- command, executable, argument, environment or working-directory material;
- runtime locator, process locator, handle, context or other protected runtime material;
- prompt construction, model inference, model input or AI tool invocation;
- DNS, TLS, socket, proxy or any other network activity;
- endpoint or credential reveal, access, delivery, copy or export;
- connector, MCP, broker, provider API or provider SDK calls;
- publication, delivery, acknowledgement, dispatch or generic execution; or
- infrastructure mutation, remediation or workflow transition.

IDs, digests, policy references and timestamps are minimized integrity metadata, never operational
instructions or bearer capability.

### Security And Governance

The claim and lease are immutable non-bearer authorization evidence. All existing authority fields
remain false. Only an unexpired, unconsumed lease may expose
`protected_runtime_process_creation_authority_granted=true`; expired or consumed projections must
report it as false.

AI remains advisory-only. No AI agent may request, receive, consume or exercise the lease, and this
command is not exposed as an AI, MCP or connector tool.

Active Directory remains authentication-only. This decision introduces no Active Directory
management route, capability, service or MCP.

### API And User Interface

The authorization POST is workload-only, strict, minimized, non-oracular and
`Cache-Control: no-store`. Production returns generic fail-closed conflict or unavailable responses
without revealing protected source existence or runtime material.

Normal authorized users may GET a minimized read-only projection through the existing username and
password browser session. No MFA, step-up authentication or second browser session is required.
The projection contains only safe claim/lease identity, state, issued/expiry timestamps and policy
or lineage integrity references.

The UI provides no authorize, create, schedule, retry, renew, transfer, infer, connect, publish,
deliver, dispatch, execute or mutate control and never displays protected material.

### Events, Audit And Recovery

Audit distinguishes exact replay, issuance, rejection, expiry and observed later consumption using
only minimized identity, state, time and integrity references. Events may be appended only after
the authoritative claim and lease commit. Publication or audit-export failure cannot roll back,
extend, reissue or consume the lease.

Recovery is evidence-only. It may project durable state but cannot create a process, perform I/O or
cross the future ADR-178 consumption boundary.

## Consequences

- Runtime readiness and process-creation request authorization remain separate trust boundaries.
- One-second expiry and single-use lineage reduce stale or replayed authorization risk.
- Exact replay is stable without renewing authority.
- A lease is not evidence that a process was created, scheduled, dispatched or executed.
- Full lineage revalidation, fresh attestation and PostgreSQL-only authority increase implementation
  and testing cost but preserve fail-closed behavior.
- The platform still cannot create a process until a separately approved consumption protocol and
  process primitive are defined.

## Deferred Scope

- Lease consumption and the process-creation point of no return
- Selection of a process, suspended child process, container task, worker sandbox or other runtime
  primitive
- Process creation, scheduling, resume, dispatch, execution, supervision, stop or cleanup
- Commands, executables, arguments, environments and working directories
- Runtime/process locators, handles, contexts or protected material
- Prompt construction, model inference or AI operation
- Network, endpoint, credential, connector, MCP, broker or provider activity
- Publication, delivery, acknowledgement or workflow execution
- Infrastructure mutation or remediation
- Lease renewal, replacement, transfer, reissue or automatic recovery
- Human- or AI-initiated process-creation authorization controls
- Active Directory management or an Active Directory MCP

## Validation

- Domain tests prove source eligibility, code-owned policy, one-second maximum lifetime, authority
  truth table and zero prohibited material or effects.
- Service tests prove replay-first ordering, fresh attestation, exact replay, changed-replay
  rejection, cancellation behavior and fail-closed composition.
- PostgreSQL tests prove authoritative time, canonical lock order, lineage/fence revalidation,
  expiry race closure, one concurrent winner, append-only enforcement and guarded migration
  downgrade.
- API and frontend tests prove workload-only POST, normal password-session read-only GET, minimized
  `no-store` schemas, strict parsing and zero operational controls.
- Live validation proves one username/password login, no MFA or second browser prompt, no browser
  POST, desktop/mobile read-only rendering and no console errors or warnings.
- Full backend/frontend regression, Alembic single-head and round-trip validation, PostgreSQL CI,
  independent review, exact-head PR CI, SHA-locked merge and independent `main` CI are required for
  delivery.
