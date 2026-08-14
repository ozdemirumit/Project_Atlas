# ADR-149: Immutable Workflow Physical Transport Route Binding Without Runtime Authority

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-14 |
| Owners | Event Platform, Workflow Architecture, Security Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-145, ADR-146, ADR-147, ADR-148 |

## Context

Atlas can freeze one logical workflow event channel, prove that channel compatible with one exact
deployment transport profile and independently freeze one exact physical route revision. None of
those records selects a physical route for the event. A later publisher cannot safely infer that
selection from mutable deployment configuration or from identifiers supplied by a human caller.

The next boundary must bind the exact logical and physical evidence while preserving Atlas's core
safety rule: evidence that a route was selected and bound is not authority to resolve, credential,
probe or operate that route.

## Decision

Atlas will persist one immutable `WorkflowEventPhysicalTransportRouteBinding` for one exact:

- `WorkflowEventLogicalChannelBinding`;
- `WorkflowEventTransportCompatibilityAdmission` tied to that logical binding;
- `EventPhysicalTransportProfileSnapshot` tied to that compatibility admission; and
- `EventPhysicalTransportRouteSnapshot` whose profile, resource, implementation, adapter,
  deployment scope and immutable route evidence match the selected profile snapshot.

Only a dedicated service workload authenticated for
`audience.workflow-physical-transport-route-binder` may create a binding. Human sessions, API
tokens, publishers, connectors, profile or route registries and compatibility admitters cannot
bind, replace or remove one. The request contains only the four exact source IDs and digests, the
code-owned binding policy ID/version/digest and an idempotency key. A caller cannot provide or
override endpoint, destination, routing, credential, network, readiness or publication fields.

The code-owned version 1 binding policy does not re-adjudicate transport compatibility. It
requires:

- all four source records to exist, retain their immutable state and match their canonical digest;
- one organization, environment and site scope across the complete source chain;
- the compatibility admission to name the exact logical binding and profile snapshot;
- the route snapshot to name the exact profile ID/revision, transport resource and digest,
  implementation ID/version and adapter contract ID/version/digest frozen by the profile snapshot;
- a TLS 1.3 minimum, required server authentication, prohibited plaintext fallback, restricted
  network enforcement and prohibited public egress on the selected route;
- the exact admitted chain to remain intact without replacing the compatibility policy decision;
  and
- zero operational authority on every source record.

The repository transaction locks the exact logical-binding, profile-snapshot,
compatibility-admission and route-snapshot rows in that fixed order, reloads their payloads,
recomputes every canonical digest and revalidates the complete chain before inserting the binding
and idempotency claim. Production
persistence never falls back to memory. Binding and claim rows are append-only; PostgreSQL rejects
`UPDATE` and `DELETE`. One logical channel binding can have only one physical route binding in
version 1. A different route requires a later explicit supersession design and cannot rewrite
history.

The binding records only the four source IDs and digests, policy evidence, scope, binder identity,
binding time, state `bound`, zero authority and a canonical digest. Route-set, selection-epoch,
endpoint-set, destination, routing-contract, deployment and transport details remain transitively
bound through the exact route-snapshot and profile-snapshot digests rather than being copied. The
binding contains no private route
descriptor commitment, raw locator, field-level locator digest, credential assignment, secret
reference, resolved endpoint, network result, readiness result, provider message, publication
attempt, delivery receipt or worker instruction.

`bound` is historical evidence only. Endpoint-resolution, route-selection, route-binding,
credential-access, network-access, readiness-probe, publication, delivery, dispatch and execution
authority flags remain false. The record cannot be used as a bearer capability or passed directly
to a provider adapter.

Exact replay returns the same binding. Changed idempotent requests, competing binder identities,
missing or drifted evidence, chain mismatch, cross-scope evidence, policy mismatch, nonzero source
authority, duplicate physical selection and audit failure fail closed without a partial record.
The pre-persistence audit event states only that persistence was authorized; it never claims that a
database commit succeeded. Exact replay may audit a successful replay because the durable binding
already exists.

Binding performs no DNS lookup, socket connection, TLS handshake, broker metadata query, secret
lookup, credential brokerage, provider SDK call, network request, publication or delivery.

Authorized humans may read minimized binding evidence through the dedicated default-deny
`workflow.physical-transport-route-bindings.read` permission and the existing username/password
browser session. Human API and UI views omit all source and policy digests and expose only stable
source IDs plus a server-generated opaque integrity reference for correlation. They expose no
private commitment or locator fingerprint and provide no create, replace, supersede, resolve,
credential, probe, publish, deliver, dispatch or execute control. They require no second login or
MFA.

## Consequences

- One workflow event gains a deterministic historical link to one immutable physical route.
- Mutable deployment route configuration cannot change the meaning of an existing binding.
- A future resolver must consume the binding through a separate workload identity, policy and
  authorization boundary; this ADR grants no resolver or credential capability.
- Route failover and supersession remain explicit future designs rather than mutation of history.
- Binding does not claim that the snapshotted selection epoch is still the deployment's current
  epoch; freshness and supersession require a later explicit policy boundary.
- Physical binding still proves no endpoint reachability, credential availability, runtime
  readiness, successful publication or delivery.

## Validation

- Domain and application tests cover exact-chain validation, policy stability, idempotent replay,
  competing identities, source drift, cross-scope evidence, source authority and audit failure.
- PostgreSQL tests cover four-row locking and digest recomputation, atomic binding/claim insertion,
  uniqueness, append-only triggers, rollback and no production memory fallback.
- Static tests reject private commitments, raw locators, field-level locator digests, credential or
  secret references, network/readiness results, provider messages, attempts and receipts.
- API tests prove binder-workload-only creation, default-deny human read, no-store responses and
  minimized C1 metadata.
- Web tests prove a read-only binding view, empty/error states, zero operational controls and no
  second-login or MFA text.
- Full backend/frontend suites, Alembic single-head validation and live browser inspection are
  required before merge.
