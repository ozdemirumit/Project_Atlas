# ADR-161: Immutable Target-Context Capsule Consumer Binding Without Handoff or Runtime Authority

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-16 |
| Owners | Workflow Architecture, Deployment Architecture, Security Architecture, Identity Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-158, ADR-159, ADR-160 |

## Context

ADR-160 irreversibly consumes one target-context access lease and permits one trusted paired opener
to create a sealed, short-lived target-context capsule. The successful opening result is immutable,
append-only evidence. Its capsule identity and digest are lineage, not bearer capabilities, and do
not authorize transfer, unsealing, delivery, network activity or runtime use.

Atlas now needs the next smallest safe boundary before any future handoff can be considered. One
successful opening result must be bound immutably to one code-owned future consumer workload,
consumer contract and purpose, while preserving its exact pending outbox and event lineage. This
binding must prevent a capsule created for one event from being confused with another event,
consumer or purpose. It must not move or expose the capsule and must not combine binding authority
with handoff, runtime or transport authority.

The binding is therefore authorization evidence for a later, independently controlled decision.
It is not a handoff authorization lease, access token, secret handle, delivery instruction,
dispatch instruction or permission to perform any external side effect.

## Decision

Atlas will implement one immutable
`WorkflowProtectedTransportTargetContextCapsuleConsumerBinding` boundary. It joins exactly one
canonical successful ADR-160 opening result to exactly one server-derived future consumer
workload, versioned consumer contract, code-owned purpose and exact pending outbox/event lineage.
It records no raw target context and performs no external I/O.

Only the exact dedicated binder service subject
`service.workflow-protected-transport-target-context-capsule-binder` authenticated for the exact
audience `audience.workflow-protected-transport-target-context-capsule-binder` may request the
binding. Human sessions, personal access tokens, AI agents, the ADR-160 accessor, publishers,
dispatchers, generic workflow services and every other workload fail closed.

The command contains only:

- opening-result ID and canonical digest;
- the code-owned binding policy ID and version; and
- idempotency metadata.

Atlas derives correlation, scope, opening attempt and claim, capsule lineage, target-context
commitment, consumer subject, consumer audience, consumer contract ID and version, purpose ID,
pending outbox and event lineage, route and credential-assignment lineage, deadlines and every
authority declaration from authenticated context and authoritative server-side state. The caller
cannot supply or override capsule, consumer, purpose, outbox, event, target, route, assignment,
endpoint, credential, opener, broker, network, runtime, dispatch or execution fields.

### Exact Consumer And Purpose

The consumer workload, audience, contract and purpose are code-owned and version-controlled. They
identify one future protected-boundary role and one narrowly defined reason for which a later
handoff authorization may be evaluated. They are not selected from caller input and cannot be
broadened by deployment configuration, an LLM response, a workflow variable or event metadata.

One binding includes:

- the exact successful opening-result ID and digest;
- the exact sealed capsule ID and digest derived from that result;
- the exact opening-attempt and lease-consumption lineage;
- the canonical target-context commitment;
- the exact future consumer subject and audience;
- the exact consumer contract ID and version;
- the exact code-owned purpose ID;
- the exact pending outbox ID, event ID, event artifact ID and their canonical digests;
- the exact workflow, physical route and credential-assignment lineage required to prove that the
  event and capsule describe the same target context;
- the code-owned binding policy ID, version and digest;
- creation and effective expiry times; and
- all 17 explicit authority declarations set to false.

Consumer identity is descriptive binding evidence only. It grants no permission to authenticate
as that consumer, read the capsule, ask another component to retrieve it or invoke any future
consumer endpoint.

### Source Eligibility And Currentness

Production binding is permitted only when the ADR-160 result is canonical `opened_protected` and:

- the opening claim, attempt, result and signed opener receipt form one exact intact lineage;
- endpoint and credential opening both succeeded as one inseparable pair;
- required partial-opening cleanup is confirmed and no cleanup uncertainty remains;
- the capsule is sealed, opaque, non-revoked, non-destroyed and explicitly non-bearer;
- database time is strictly before the result and capsule usable deadline with the code-owned
  minimum remaining window;
- the target-context binding and both complete successful materialization chains remain canonical;
- the exact pending outbox is live, uncancelled, unpublished, unquarantined and still references
  the same event and event artifact;
- the event artifact, logical channel, physical route binding, route snapshot and authoritative
  current route-selection head, generation and fencing token still agree;
- the credential-assignment binding and snapshot still match the unique authoritative current
  assignment revision, rotation, revocation and expiry state; and
- the opening result, target-context commitment, event lineage, route lineage and assignment
  lineage all describe the same tenant, organization, environment, workflow and target scope.

Expiry, revocation, destruction, cancellation, publication, quarantine, supersession, ambiguity,
digest mismatch, route drift, credential drift, insufficient remaining lifetime or any incomplete
lineage fails closed. Historical success alone is insufficient when current source state is no
longer eligible for a new binding.

### Atomic Append-Only Transaction

Production uses durable PostgreSQL and has no memory fallback. One transaction follows the
canonical lock and fencing order inherited from ADR-160 and locks and revalidates:

1. the exact pending outbox, event and event-artifact lineage;
2. the target-context binding and both complete materialization chains;
3. the physical route binding, logical channel binding, route snapshot and authoritative current
   route-selection head, generation and fencing token;
4. the credential-assignment binding and snapshot, assignment advisory fence and authoritative
   unique current assignment head;
5. the ADR-160 lease-consumption claim, opening attempt, terminal result and canonical opener
   receipt evidence;
6. the capsule status, non-bearer declaration, cleanup or revocation evidence and usable deadline;
7. any existing consumer binding for the opening result, capsule or exact event lineage; and
8. the scoped idempotency claim and canonical request fingerprint.

PostgreSQL evaluates `clock_timestamp()` only after the locks are held. Atlas validates the full
lineage and deadlines, records the database observation time, then repeats all database-resident
currentness, canonical-integrity and lifetime checks immediately before append. The transaction
atomically appends one binding and its code-owned authorization-audit payload. It makes no
protected-store, opener, broker, DNS, TLS, socket, proxy, provider SDK or other external call.

The table is append-only. Database constraints and triggers reject update and delete. There is at
most one binding for an opening result, one binding for a capsule and one exact consumer binding
for the event lineage under the code-owned contract and purpose. Canonical integrity is rechecked
on read and replay. A deployment that cannot provide these PostgreSQL guarantees fails closed.

### Zero-Authority Contract

The binding contains the following 17 explicit authority declarations, all exactly false:

- `endpoint_resolution_authorized`;
- `route_selection_authorized`;
- `route_binding_authorized`;
- `credential_selection_authorized`;
- `credential_assignment_binding_authorized`;
- `credential_access_authorized`;
- `credential_brokerage_authorized`;
- `credential_resolution_authorized`;
- `protected_artifact_access_authorized`;
- `credential_delivery_authorized`;
- `network_access_authorized`;
- `readiness_probe_authorized`;
- `publication_authorized`;
- `delivery_authorized`;
- `dispatch_authorized`;
- `execution_authorized`; and
- `infrastructure_mutation_authorized`.

The binding does not call the protected store or opener. It does not retrieve, open, unseal,
decrypt, copy, transfer, export, inject or deliver the capsule or either protected artifact. It
does not resolve an endpoint or credential, create a network client, perform DNS, negotiate TLS,
open a socket, call a broker or provider, probe readiness, publish an event, dispatch a worker,
advance workflow execution or mutate infrastructure.

Binding status, consumer identity, capsule identity and every digest are evidence, not bearer
material. Possession of any identifier or digest does not confer access. The binding cannot be
presented directly to a protected store, opener, broker, runtime or consumer as authorization.

### Replay And Conflict Semantics

Replay is resolved from durable state before any current-source query that could hide a valid
historical result:

- Exact replay by the same binder subject and audience with the same opening-result digest,
  policy, scoped idempotency key and canonical request fingerprint returns the same minimized
  immutable binding.
- Exact replay remains stable after source expiry or later lifecycle drift because it returns
  historical evidence and creates no new authority.
- A changed opening-result digest, policy, subject, audience, idempotency key or request
  fingerprint conflicts and fails closed.
- A competing request for an already bound opening result or capsule fails closed, including a
  request that would derive a different consumer, contract, purpose, outbox or event lineage.
- A conflicting pre-existing binding, ambiguous lineage or partial persistence state fails closed
  and is never repaired by mutating history.

Exact replay never performs protected-store, opener, broker or network I/O. No replay path may
create a second binding, change the consumer or extend the capsule deadline.

### Audit, API And Human Presentation

The binding append includes a code-owned canonical authorization-audit payload and digest in the
same PostgreSQL transaction. Secondary audit, Syslog or SIEM export occurs after durable commit
and is not the source of truth. Audit and logs contain no raw endpoint, credential, capsule
contents, retrievable locator, protected-store handle or bearer material.

The workload command response contains only minimized binding identity and digest, state,
non-sensitive times, policy reference and the exact zero-authority contract. Every response uses
`Cache-Control: no-store` and non-oracle error mapping.

Authorized humans may inspect a separate minimized read-only inventory using the existing normal
username/password browser session and a dedicated read permission. No MFA, second login or
authorized-browser-session prompt is required. Human responses and UI omit capsule ID and digest,
opening-result digest, artifact lineage, protected-store references, endpoint, credential,
outbox internals, route and assignment internals, idempotency and fence evidence. The UI provides
no bind, retry, handoff, reveal, unseal, copy, download, deliver, connect, probe, publish, dispatch,
execute or mutate control.

## Consequences

- One sealed capsule is immutably associated with one exact future consumer contract and purpose
  before any handoff authority can be considered.
- Confused-deputy and cross-event reuse risks are reduced without exposing or moving protected
  material.
- Append-only lineage preserves an auditable historical decision while exact replay remains
  stable and side-effect free.
- The additional transaction and full-chain revalidation deliberately trade throughput for
  enterprise consistency and fail-closed behavior.
- A later independently authorized handoff boundary remains mandatory; this binding alone cannot
  be used operationally.

## Deferred Scope

- Target-context capsule handoff authorization lease
- Handoff-lease consumption and protected-boundary capsule handoff
- Capsule retrieval, unsealing, decryption, transfer or runtime injection
- Endpoint or credential reveal, delivery, copy, download or export
- DNS, TLS, socket, proxy, network establishment or readiness probing
- Transport-provider negotiation, broker access, provider SDK calls or publication
- Event delivery, acknowledgement, retry, quarantine release or source cleanup
- Worker dispatch, workflow state transition, workflow execution or infrastructure mutation
- Human- or AI-initiated binding, handoff or runtime use

## Validation

- Domain and application tests cover the exact binder subject and audience, caller-field
  prohibition, code-owned consumer/contract/purpose derivation, exact lineage, deadline and the
  exact 17-field all-false authority contract.
- PostgreSQL tests cover canonical lock order, database time, complete opening-result and target-
  context lineage, pending-outbox state, route and credential-assignment currentness, unique
  opening-result/capsule binding, append-only triggers and no production memory fallback.
- Replay tests cover exact stable replay, changed replay, competing derived consumers, conflicting
  event lineage and source expiry after a successful binding.
- Isolation tests prove no protected-store, opener, broker, DNS, TLS, socket, network, provider,
  dispatch, execution or infrastructure-mutation call is reachable from this boundary.
- API and UI tests cover workload-only commands, non-oracle errors, minimized schemas, `no-store`,
  zero operational controls and normal username/password reads without MFA, a second login or an
  authorized-browser prompt.
- Full backend/frontend suites, Alembic single-head validation, real PostgreSQL CI, live desktop
  and mobile browser inspection, exact-head PR CI, SHA-locked merge and independent main CI are
  required.
