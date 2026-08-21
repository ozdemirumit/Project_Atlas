# ADR-179: Bounded Single-Use Protected Runtime Process-Scheduling Authorization Lease

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-20 |
| Owners | Workflow Architecture, Security Architecture, Deployment Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-160 through ADR-178 |

## Context

ADR-178 may produce one canonical `process_created_suspended_in_protected_boundary` result after
atomically consuming the ADR-177 lease and recording exactly one process-creation attempt. That
result is immutable historical evidence that one exact code-owned process primitive was created
sealed, suspended and non-runnable at the verified time. It is non-bearer evidence and grants no
scheduling, resume, dispatch, execution or other operational authority.

Atlas needs a separate authorization boundary before one future process-scheduling request may be
submitted. Treating process-creation success as direct scheduling authority would collapse outcome
and authorization, permit stale process state to be reused and allow retry, event, recovery, human
or AI paths to advance a process toward execution without a fresh, short-lived, single-use grant.

This decision authorizes only submission of one future request. It does not define, consume or
perform scheduling. The scheduling-consumption point of no return and the exact protected-side
scheduler primitive remain deferred to a separately approved ADR and implementation task.

## Decision

Atlas will permit only the exact protected consumer workload bound through the canonical ADR-160
through ADR-178 lineage to request a protected runtime process-scheduling authorization lease. The
sole eligible source is one canonical, successful ADR-178
`process_created_suspended_in_protected_boundary` result.

After fresh protected-boundary process-state attestation and complete PostgreSQL revalidation,
Atlas may atomically append one immutable authorization claim and one immutable lease. The lease:

- expires no later than one second after authoritative PostgreSQL issuance time;
- is single-use, non-renewable, non-transferable, non-replaceable, non-reissuable and non-bearer;
- permits only submission of one future process-scheduling request for the exact process lineage;
- cannot authorize a different process, runtime, tenant, identity, policy or request;
- carries no direct scheduling, resume, dispatch or execution authority; and
- cannot be converted into existing authority or reused through retry, event or recovery paths.

Only an active lease may set
`protected_runtime_process_scheduling_authority_granted=true`. Every pre-existing authority
declaration remains false. The field means only that the exact bound workload may submit one future
scheduling-consumption request. It does not mean that the process is scheduled, runnable, resumed,
dispatched or executed.

### Exact Eligibility

The source result must be the one canonical terminal ADR-178 result for the exact tenant, protected
consumer contract, runtime-start lineage, destination fence, protected slot generation and
code-owned suspended-process primitive. Only
`process_created_suspended_in_protected_boundary` is eligible. Rejected, failed, pending,
uncertain, absent or conflicting process-creation outcomes fail closed.

Before opening the PostgreSQL transaction, Atlas obtains fresh, signed, server-nonce-bound,
metadata-only protected process-state attestation. The attestation must bind the exact canonical
ADR-178 result and prove that the exact process:

- remains created from the signed code-owned process-image and process-manifest commitments;
- remains sealed and bound to the same protected runtime and process lineage;
- remains suspended and non-runnable;
- remains unscheduled and has no scheduling attempt, reservation or queue placement;
- remains current under the code-owned process-scheduling authorization policy;
- has never been resumed, dispatched or executed; and
- has no pending or conflicting scheduling, resume, dispatch, execution, supervision, cleanup or
  replacement state.

The attestation also proves that the exact runtime, destination fence and protected slot generation
remain current. It contains no runtime or process locator, handle, queue identifier, command,
executable, argument, environment, credential, endpoint or reusable protected material. It is
transaction evidence only and is never bearer authority.

### Exact Caller And Request

Only the authenticated protected consumer workload subject and audience already fixed by the
canonical ADR-160 through ADR-178 lineage may POST. Human sessions, personal access tokens, AI
agents, MCP tools, connectors, runtime identities, generic workers, schedulers and recovery workers
fail closed before protected-state I/O.

The caller supplies only:

- the canonical ADR-178 process-creation result ID;
- code-owned process-scheduling authorization policy ID and version;
- a tenant-scoped idempotency key; and
- explicit acknowledgement that the lease is single-use and authorizes only a future request.

The caller cannot supply result or lineage digests, attestation values, lease timing, authority
values, scheduling class, priority, affinity, queue, command, executable, arguments, environment,
runtime or process locator, handle, endpoint, credential, prompt, model, provider, transport,
publication, delivery, dispatch, execution or mutation values. Atlas derives integrity references,
deadlines and policy commitments from trusted state and code-owned policy.

### Code-Owned Policy And PostgreSQL Authority

PostgreSQL is the sole production authority. Durable replay classification is the first repository
operation. The repository then locks and revalidates in canonical order:

1. the complete immutable ADR-160 through ADR-178 lineage;
2. the canonical successful process-creation result and its exact authorization, claim, attempt,
   primitive and receipt ancestry;
3. the current destination generation and fencing token;
4. the exact protected slot generation and terminal started runtime coordination head, read-only;
5. current process image, manifest, creation profile and scheduling-authorization policy digests;
6. pending publication and orchestration fences relevant to the same lineage; and
7. competing process-scheduling authorization claims and leases in stable key order.

The transaction observes authoritative database time before and after locking. At the final
observation, the source result and fresh attestation must remain timely, every generation and fence
must remain current, no later process-state evidence may conflict and the deadline must retain the
code-owned safety margin while remaining no more than one second after issuance. Atlas then
atomically appends the claim and lease without external I/O.

Append-only triggers, exact composite foreign keys and unique constraints enforce one grant for the
exact process-creation result and process lineage, tenant-scoped idempotency, complete ancestry and
rejection of update, delete, truncate, changed replay, stale generation, cross-lineage evidence or
multiple active claims. Production never falls back to process-local or in-memory authority.

### Replay, Expiry And Cancellation

- Exact replay returns the same minimized claim and lease without extending its deadline or
  obtaining a replacement attestation.
- The same idempotency key with changed request, identity, scope, policy or lineage fails closed.
- Concurrent requests have at most one winner for the exact canonical process result and lineage.
- An expired or consumed lease cannot be renewed, transferred, replaced, restored or reissued.
- No later request may create a successor lease from the same canonical ADR-178 result.
- Cancellation before commit appends nothing; cancellation at or after commit does not remove,
  extend or replace the lease.
- Process-state drift, stale attestation, fence or generation drift, clock-margin failure,
  persistence ambiguity or unavailable PostgreSQL fails closed.
- HTTP retry middleware, event replay, workflow recovery, scheduler, outbox, DLQ and audit-export
  paths cannot issue, consume, renew or replace the lease.

No recovery path may infer that scheduling occurred from lease issuance. Only a separately approved
future consumption protocol may consume the exact active lease and define an operational point of
no return.

### Prohibited Effects And Material

ATLAS-IMP-229 and this lease perform or carry none of the following:

- process scheduling, queue placement, reservation, resume, dispatch or execution;
- process creation, fork, spawn, launch, restart, stop, supervision or cleanup;
- command, executable, argument, environment, working-directory or scheduling material;
- runtime or process locator, handle, context or other protected runtime material;
- prompt construction, model inference, model input or AI tool invocation;
- DNS, TLS, socket, proxy or any other network activity;
- endpoint or credential reveal, access, delivery, copy or export;
- connector, MCP, broker, provider API or provider SDK calls;
- publication, delivery, acknowledgement, generic workflow execution or transition; or
- infrastructure mutation, remediation or external-system change.

IDs, digests, policy references, states and timestamps are minimized integrity metadata, never
operational instructions or bearer capability.

### Security And Governance

The claim and lease are immutable non-bearer authorization evidence. Every pre-existing authority
field remains false. Only an unexpired, unconsumed lease may expose
`protected_runtime_process_scheduling_authority_granted=true`; expired or consumed projections must
report it as false.

AI remains advisory-only. No AI agent may request, receive, consume or exercise the lease, and this
command is not exposed as an AI, MCP or connector tool.

Active Directory remains authentication-only. This decision introduces no Active Directory
management route, capability, service or MCP.

### API And User Interface

The authorization POST is workload-only, strict, minimized, non-oracular and
`Cache-Control: no-store`. Production returns generic fail-closed conflict or unavailable responses
without revealing protected source existence, process state or protected material.

Normal authorized users may GET a minimized read-only projection through the existing username and
password browser session. No MFA, step-up authentication or second authorized browser session is
required. The projection contains only safe claim/lease identity, state, issued/expiry timestamps,
policy references and lineage integrity references.

The UI provides no authorize, schedule, consume, retry, renew, transfer, reissue, resume, dispatch,
execute, stop, cleanup, connect or mutate control and never displays protected material.

### Events, Audit And Recovery

Audit distinguishes exact replay, issuance, rejection, expiry and observed later consumption using
only minimized identity, state, time and integrity references. Events may be appended only after the
authoritative claim and lease commit. Publication or audit-export failure cannot roll back, extend,
renew, reissue or consume the lease.

Recovery is evidence-only. It may project durable state but cannot attest process state, schedule,
resume, dispatch, execute, perform protected I/O or cross the future consumption boundary.

## Consequences

- Process-creation success and process-scheduling request authorization remain separate trust
  boundaries.
- One-second expiry and exact single use reduce stale-state and replay risk.
- Fresh signed process-state evidence prevents a historical creation result from standing in for
  current sealed, suspended, unscheduled and unexecuted state.
- Exact replay is stable without renewing, transferring, replacing or reissuing authority.
- A lease is not evidence that scheduling, resume, dispatch or execution occurred.
- Full lineage revalidation and PostgreSQL-only authority increase implementation and testing cost
  while preserving fail-closed behavior.
- The platform still cannot schedule or run a process until a separately approved consumption
  protocol is implemented.

## Deferred Scope

- Lease consumption and the process-scheduling point of no return
- Scheduler primitive, queue placement, reservation, priority, affinity and resource assignment
- Process scheduling, resume, dispatch, execution, supervision, stop and cleanup
- Commands, executables, arguments, environments and working directories
- Runtime/process locators, handles, contexts or protected material
- Prompt construction, model inference or AI operation
- Network, endpoint, credential, connector, MCP, broker or provider activity
- Publication, delivery, acknowledgement or workflow execution
- Infrastructure mutation or remediation
- Lease renewal, replacement, transfer, reissue or automatic recovery
- Human- or AI-initiated scheduling authorization controls
- Active Directory management or an Active Directory MCP

## Validation

- Domain tests prove source eligibility, code-owned policy, one-second exclusive upper bound,
  authority truth table and zero prohibited material or effects.
- Service tests prove replay-first ordering, fresh signed process-state attestation, exact replay,
  changed-replay rejection, cancellation behavior and fail-closed composition.
- PostgreSQL tests prove authoritative time, canonical lock order, complete lineage and current-state
  revalidation, expiry-race closure, one concurrent winner, no reissue, append-only enforcement and
  guarded migration downgrade.
- API and frontend tests prove workload-only POST, normal password-session read-only GET, minimized
  `no-store` schemas, strict parsing and zero operational controls.
- Live validation proves one username/password login, no MFA or second browser prompt, no browser
  POST, desktop/mobile read-only rendering and no console errors or warnings.
- Focused local checks cover changed modules. Full backend/frontend regression and PostgreSQL
  integration run once in pull-request CI before merge.
