# ADR-150: Immutable Workflow Physical Transport Route Freshness and Non-Supersession Admission Without Endpoint Resolution Authority

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-14 |
| Owners | Event Platform, Workflow Architecture, Deployment Architecture, Security Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-146, ADR-147, ADR-148, ADR-149 |

## Context

Atlas can immutably bind one exact logical workflow event channel to one exact physical transport
route snapshot. That binding is historical evidence: it proves which route revision was selected
when the binding was created, but it does not prove that the route remains the deployment's unique
current selection when a later resolver attempts to consume it.

Treating `active=true`, the original selection epoch or a recent binding timestamp as currentness
would permit a stale or superseded route to reach endpoint resolution. Resolving directly from a
mutable route registry would instead erase the evidence boundary and introduce a
time-of-check/time-of-use race. Atlas therefore needs a separate, bounded admission that compares
the immutable binding chain with a server-owned authoritative current-selection head without
granting any runtime capability.

## Decision

Atlas will persist one immutable `WorkflowEventPhysicalTransportRouteFreshnessAdmission` for one
exact:

- `WorkflowEventPhysicalTransportRouteBinding`;
- `EventPhysicalTransportRouteSnapshot` named by that binding; and
- authoritative `DeploymentEventTransportRouteSelectionHead` for the same organization,
  environment, site and route set.

The deployment route registry owns exactly one current-selection head for a scoped route set. The
head identifies one selected deployment-route ID, immutable revision and source-route digest, its
selection epoch, a strictly monotonic generation, an opaque fencing-token digest and a canonical
head digest. It deliberately does not reference an Atlas route-snapshot ID because the deployment
selection exists before Atlas creates that immutable snapshot. The head also records whether the
selection is active, eligible, suspended, withdrawn or superseded. The registry, not the caller or
the LLM, establishes this evidence. More than one current head or selected route for the same
scoped route set is ambiguity and fails closed.

The registry advances a head only through an atomic, locked monotonic update. Generations never
decrease or repeat, every successful advance requires a different opaque fencing-token digest and
PostgreSQL retains append-only generation history. Prior immutable admissions also retain the exact
historical generation and fencing evidence they observed. A database uniqueness invariant permits
only one current pointer per organization, environment, site and route set. The freshness-admitter
can read and lock this evidence but cannot create, advance, roll back or repair a head.

In development, Atlas derives and synchronizes one selection head from the configured active
route so the complete boundary remains locally testable. In production, an explicitly supplied
authoritative head set is synchronized as one complete snapshot: an empty set and omission of any
previously known scoped route-set key both fail closed. When the production head set is not
supplied at all, Atlas treats current-head rows as externally managed deployment-registry state
and does not rewrite them during application startup. Omission is therefore distinct from an
explicit empty authoritative snapshot and never fabricates a current route.

Only a dedicated service workload authenticated for
`audience.workflow-physical-transport-route-freshness-admitter` may create an admission. Human
sessions, API tokens, binders, route registries, endpoint resolvers, credential brokers,
publishers, connectors and other workloads cannot create, replace or remove one. The request
contains only the exact binding ID/digest, code-owned freshness-policy ID/version and an
idempotency key. The repository resolves and locks the route snapshot and authoritative current
head. A caller cannot provide or override TTL, currentness, supersession, endpoint, credential,
network, readiness or publication decisions.

The code-owned version 1 freshness policy requires:

- the binding and route snapshot to exist, retain their immutable states and match their
  recomputed canonical digests;
- the binding to name the exact route snapshot and digest;
- one organization, environment, site, route set and immutable selection epoch across the binding,
  route snapshot and current head;
- the current head to be the authoritative unique head for that scoped route set;
- the head's selected route ID, route revision and source-route digest to match the exact bound
  route snapshot's route ID, revision and `source_route_digest`;
- the locked head generation, fencing-token digest and canonical digest to remain exact throughout
  admission;
- the generation to satisfy the registry's strictly monotonic contract;
- the current selection to be active and eligible, not suspended, withdrawn or superseded; and
- every source record to retain zero operational authority.

`active=true` is never sufficient by itself. TTL is also never sufficient by itself: the exact
authoritative head generation and fencing-token digest must still match whenever the admission is
consumed.

The persistence transaction locks the exact physical binding, route snapshot and authoritative
current-selection head in that fixed order. It reloads each source, recomputes immutable and head
digests, proves unique-current selection and revalidates the complete chain immediately before
atomically inserting the admission and idempotency claim. Production persistence never falls back
to memory. Admission and claim rows are append-only; PostgreSQL rejects `UPDATE` and `DELETE`.

The admission records only exact source IDs and digests, scope, route-set identity, selection
epoch, head generation, fencing-token digest, policy evidence, admitter identity, `evaluated_at`,
server-computed bounded `valid_until`, state `admitted_current`, zero authority and a canonical
digest. The
maximum lifetime is code-owned and cannot be extended by a caller. Expiry or a head generation,
fencing token, selection or digest change does not mutate or delete historical admission evidence;
it makes that admission unusable for later resolution.

Exact replay returns the same admission only while its `valid_until` has not passed and the locked
authoritative head still has the exact generation, fencing-token digest, selected route and
canonical digest. Replay after expiry, drift, suspension, withdrawal or supersession fails closed
and cannot present the historical admission as current. A new evaluation requires a new
idempotency key and, when the selected route changed, the later explicit rebinding or supersession
boundary. Changed idempotent requests, competing identities, missing or cross-scope evidence,
ambiguous current selection, source drift, policy mismatch and audit failure fail closed without a
partial record. External errors do not distinguish missing, cross-scope or superseded evidence.

`admitted_current` means only that the exact bound route was found current and non-superseded at
`evaluated_at`, under the named policy, until no later than `valid_until`. It is not a durable
currentness claim or a bearer capability. Endpoint-resolution, route-selection, route-binding,
credential-access, network-access, readiness-probe, publication, delivery, dispatch and execution
authority flags all remain false.

A future endpoint resolver must use a separate workload identity, permission and policy boundary.
Immediately before any resolution, it must lock or otherwise obtain an authoritative fenced read
of the same route-set head, reject an expired admission and revalidate the exact head generation,
fencing-token digest, selected route and canonical digest. Successful admission alone cannot
authorize endpoint materialization, credential access, network activity or provider interaction.

Freshness admission performs no raw endpoint or locator resolution, DNS lookup, socket connection,
TLS handshake, broker metadata query, credential assignment, secret or certificate lookup,
readiness probe, provider SDK call, publication, delivery, dispatch or execution. It records no raw
locator, endpoint, credential, secret, certificate, network result, readiness result, provider
message, publication attempt or delivery receipt.

Authorized humans may read minimized admission evidence through the dedicated default-deny
`workflow.physical-transport-route-freshness-admissions.read` permission and the existing
username/password browser session. Human API and UI views omit source, policy, fencing-token and
canonical digests, expose no endpoint or private route material and provide no admit, renew,
override, resolve, credential, probe, publish, deliver, dispatch or execute control. They require
no second login or MFA.

## Consequences

- A physical route binding can be rejected as stale or superseded before any endpoint material is
  resolved.
- Currentness is a bounded observation tied to one exact monotonic head generation and fencing
  digest, not a permanent property of immutable binding evidence.
- A route-head change invalidates downstream use without rewriting the historical binding or
  admission.
- A future resolver must independently revalidate both admission lifetime and current-head
  fencing evidence, closing the admission-to-resolution race.
- Ambiguous selection, registry drift, suspension, withdrawal, supersession and audit uncertainty
  stop the workflow safely.
- Route failover, rebinding, binding supersession and endpoint resolution remain later explicit
  designs.
- The admission still proves no endpoint reachability, credential availability, runtime readiness,
  successful publication or delivery.

## Deferred Scope

- Raw endpoint, destination or locator resolution
- Credential assignment, brokerage, secret, key or certificate access
- DNS, TLS, socket, broker metadata and readiness probes
- Provider adapter calls and publication
- Delivery, retry, acknowledgement, receipt and quarantine
- Worker dispatch and execution
- Route failover and creation of a replacement physical binding
- Physical-binding supersession chains
- Resolver authorization, endpoint-consumption leases and runtime publication fencing

## Validation

- Domain and application tests cover exact-chain validation, code-owned TTL bounds, monotonic head
  generation, fencing-token digest stability, unique-current selection, expiry, replay, source
  drift, suspension, withdrawal, supersession, cross-scope evidence, zero authority and audit
  failure.
- PostgreSQL tests cover fixed-order source locking, immutable-source and mutable-head digest
  recomputation, concurrent head movement, atomic admission/claim insertion, uniqueness,
  append-only triggers, rollback and no production memory fallback.
- Integration tests prove that a head change between binding and admission fails closed and that a
  head change or expiry after admission prevents resolver consumption.
- Static tests reject raw locators, endpoint material, credentials, secrets, certificates,
  network/readiness results, provider messages, attempts and receipts.
- API tests prove freshness-admitter-workload-only creation, default-deny human read, no-store
  responses, minimized C1 metadata and normalized external errors.
- Web tests prove a read-only admission view, expired/stale presentation, empty/error states, zero
  operational controls and no second-login or MFA text.
- Full backend/frontend suites, Alembic single-head validation, live PostgreSQL concurrency tests
  and live browser inspection are required before merge.
