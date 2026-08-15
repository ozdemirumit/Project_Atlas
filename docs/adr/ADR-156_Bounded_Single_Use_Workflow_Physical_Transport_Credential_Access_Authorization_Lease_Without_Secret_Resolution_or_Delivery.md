# ADR-156: Bounded Single-Use Workflow Physical-Transport Credential-Access Authorization Lease Without Secret Resolution or Delivery

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-15 |
| Owners | Event Platform, Workflow Architecture, Deployment Architecture, Security Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-151, ADR-152, ADR-153, ADR-154, ADR-155 |

## Context

ADR-155 records bounded evidence that one exact workflow credential-assignment binding still
names the deployment registry's unique current, active, unexpired and unrevoked assignment head.
That admission intentionally grants no credential access. Treating freshness evidence as a secret
capability would collapse decision evidence and access authority, allow transfer to another
subject and leave no single-use authorization boundary before protected credential material is
opened.

Secret material is not required to establish who may attempt one future access, against which
exact assignment evidence and for how long. Atlas therefore needs a separate authorization lease
before any broker, vault, protected-artifact or delivery operation.

## Decision

Atlas will persist one immutable
`WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease` for one exact:

- credential-assignment freshness admission;
- credential-assignment binding and assignment snapshot named by that admission;
- authoritative deployment credential-assignment registry head; and
- credential-access workload subject.

Protected endpoint artifacts are not part of this lease. Endpoint and credential material remain
independent protected chains until a later context-binding boundary proves that both belong to the
same exact target context.

### Request And Identity Boundary

Only the dedicated workload subject authenticated for
`audience.workflow-physical-transport-credential-accessor` may request a lease, and it may obtain
one only for its own subject. Human sessions, personal tokens, AI agents, connectors, freshness
admitters, binders and other workloads cannot request, renew, transfer, consume or remove one.

The request contains only freshness-admission ID/digest, current code-owned policy ID/version and
an idempotency key. The caller cannot provide subject, scope, lifetime, assignment rank, credential
profile, target, broker, secret, endpoint or authority fields.

### Source Revalidation And Fencing

The repository transaction locks the exact credential-assignment binding and snapshot, acquires
the same assignment-ID advisory transaction fence used by assignment synchronization and
ADR-155, locks all registry revisions, selects the unique maximum rotation/generation head and
locks the exact freshness admission. The transaction recomputes every immutable digest and proves:

- one organization, environment and site across the complete chain;
- the admission names the exact binding, snapshot, assignment revision, source digest, credential
  generation and rotation epoch;
- the binding, snapshot and admission retain valid canonical digests and expected authority;
- the unique current head still exactly matches the recorded assignment revision, source digest
  and rank;
- the assignment remains active, unexpired and unrevoked;
- database time is inside the freshness-admission and assignment windows; and
- both windows retain the complete code-owned lease lifetime.

The fixed lock order is binding, assignment snapshot, assignment advisory fence, all assignment
revisions and freshness admission. Synchronization takes the same assignment fence, preventing a
new revision from racing lease issuance.

Required intent and commit-authorization audits succeed before persistence. After the precommit
audit returns, the same transaction obtains `clock_timestamp()` again and repeats the complete
evidence, lifecycle and window validation before inserting any row.

### Lifetime, Uniqueness And Replay

The code-owned version 1 policy grants exactly 15 seconds from authoritative database time. A
caller cannot shorten or extend the interval. If fewer than 15 seconds remain on either the
freshness admission or assignment, authorization fails closed instead of issuing a shorter lease.

One freshness admission may produce at most one lease. The lease is single-use, non-renewable,
non-transferable and append-only. Its identifier is not a bearer capability. A later consumer must
authenticate the same workload subject and audience and revalidate the full chain before use.

Exact idempotent replay always enters the repository transaction, takes the same locks and fence,
uses database time and returns the same lease only while the lease, freshness admission and exact
assignment head remain current. Expiry, rotation, deactivation, revocation, ambiguous head,
source drift, changed request, competing identity, cross-scope evidence, policy mismatch and audit
failure fail closed without a partial lease or claim.

The lease and idempotency claim are inserted atomically. Both tables reject `UPDATE` and `DELETE`.
Production requires PostgreSQL and never falls back to process memory. Effective active or expired
state is derived from database time; immutable history is not rewritten when a window closes.

### Record And Authority

The lease records exact source IDs and digests, assignment revision, credential generation,
rotation epoch, lifecycle evidence, scope, accessor subject, historical policy evidence,
`issued_at`, `valid_until`, state `authorized_unconsumed`, authority declarations and a canonical
digest.

It contains no username, password, token, key, certificate, secret value, vault path, secret-store
locator, retrievable secret reference, credential profile, target commitment, broker detail,
provider handle, endpoint coordinate, protected-artifact handle, header, command, environment
variable, provider response or network result.

`credential_access_authorized` is true. It means only that the exact accessor workload may use a
future trusted consumer boundary for one credential-access attempt while every source and fence
remains valid. Endpoint resolution, protected-artifact access, route selection, route binding,
credential selection, assignment binding, brokerage, credential resolution, credential delivery,
network access, readiness probing, publication, delivery, dispatch, execution and infrastructure
mutation authority are exactly false.

Lease issuance performs no credential selection, vault or broker call, secret resolution,
protected-artifact access, endpoint access, filesystem or process operation, network request,
readiness probe, provider interaction, publication, dispatch, execution or mutation.

### Human Presentation

Authorized humans may inspect minimized read-only lease evidence through a dedicated default-deny
permission and the existing normal username/password session. No MFA, second login or
authorized-browser-session prompt is added.

The API and UI expose only stable lease, freshness-admission and assignment revision identifiers,
credential generation, rotation epoch, immutable policy ID/version, scope, accessor subject,
issue/expiry times, immutable and effective state, single-use/non-renewable declarations, explicit
authority booleans and an opaque integrity reference. They expose no source or policy digest,
idempotency key, request fingerprint, credential, secret, target, broker, endpoint or protected
artifact and provide no issue, renew, transfer, consume, resolve, reveal, download or operational
control.

## Consequences

- Assignment freshness is no longer mistaken for credential access authority.
- Access authority is bound to one exact workload, source chain and fenced assignment head for
  only 15 seconds.
- Head movement or lifecycle change invalidates downstream use even before wall-clock expiry.
- A later consumer has an explicit one-way consumption contract and cannot reuse a historical or
  transferred lease.
- No credential or endpoint material becomes available after this decision.

## Deferred Scope

- Lease consumption API and append-only consumption claim
- Trusted broker or vault invocation
- Secret, key, certificate or token resolution
- Protected credential artifact materialization
- Protected endpoint artifact access
- Exact endpoint/credential target-context binding
- Ephemeral runner delivery or injection
- DNS, TLS, socket, proxy, broker metadata and readiness probes
- Publication, delivery, acknowledgement, retry, quarantine and receipts
- Worker dispatch, workflow execution and infrastructure mutation
- Human or AI credential selection, reassignment, reveal or download

## Validation

- Domain and application tests cover exact subject/audience binding, code-owned 15-second lifetime,
  full-window containment, single authority, exact replay, competing identity, expiry, rotation,
  revocation, deactivation, ambiguous head, source drift, cross-scope evidence, policy rotation,
  audit ordering and completion-audit recovery.
- PostgreSQL tests cover fixed-order locks, the shared assignment advisory fence, database-time
  evaluation, concurrent registry movement, second validation after audit, uniqueness, atomic
  lease/claim insertion, append-only triggers, rollback and no production memory fallback.
- Static and API tests reject credential, secret, target, broker, endpoint, protected-artifact,
  private digest and operational fields from ordinary surfaces.
- API tests prove workload-only creation, default-deny human read, generic non-oracle errors,
  CSRF/no-store behavior and minimized C1 metadata.
- Web tests prove active/expired read-only presentation, empty/error states, exactly one true and
  16 false authority declarations, zero operational controls and no MFA, second-login or
  authorized-browser text.
- Full backend/frontend suites, Alembic single-head validation, real PostgreSQL CI, live browser
  inspection, exact-head PR CI and independent main CI are required before merge.
