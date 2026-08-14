# ADR-151: Bounded Single-Use Workflow Physical Transport Endpoint-Resolution Authorization Lease Without Endpoint Materialization

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-14 |
| Owners | Event Platform, Workflow Architecture, Deployment Architecture, Security Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-148, ADR-149, ADR-150 |

## Context

Atlas can bind one workflow event to one immutable physical route snapshot and can prove, for a
bounded interval, that the route remains the deployment registry's unique current and
non-superseded selection. That freshness admission intentionally grants no endpoint-resolution
authority. Treating it as a resolver capability would collapse decision evidence and access
authority, permit transfer to another subject and leave no bounded single-use authorization
record before sensitive endpoint material is opened.

Raw endpoint material is not required to establish who may attempt resolution, against which
exact evidence and for how long. Atlas therefore needs a separate authorization boundary before
endpoint materialization, credential access or network activity.

## Decision

Atlas will persist one immutable
`WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease` for one exact:

- `WorkflowEventPhysicalTransportRouteFreshnessAdmission`;
- `WorkflowEventPhysicalTransportRouteBinding` named by that admission;
- `EventPhysicalTransportRouteSnapshot` named by the binding;
- authoritative `DeploymentEventTransportRouteSelectionHead`; and
- resolver workload subject.

Only a dedicated workload authenticated for
`audience.workflow-physical-transport-endpoint-resolver` may request a lease. The requester can
obtain a lease only for its own subject identity. Human sessions, API tokens, freshness admitters,
binders, route registries, publishers, connectors and other workloads cannot request, renew,
transfer, replace or remove one. The request contains only freshness-admission ID/digest,
code-owned policy ID/version and an idempotency key. It cannot name a different resolver or supply
TTL, endpoint, credential, network, readiness or publication decisions.

The code-owned version 1 policy requires the repository transaction to lock the physical binding,
route snapshot, authoritative current-selection head and freshness admission in that fixed order.
It reloads every source, recomputes immutable and head digests and proves:

- one organization, environment, site, route set and selection epoch across the complete chain;
- the freshness admission names the exact binding, route snapshot and current head;
- the binding and route snapshot retain their immutable source digests and zero operational
  authority;
- the current head still names the exact route ID, revision and source-route digest;
- head generation, fencing-token digest, selected route and canonical digest still exactly match
  the freshness admission;
- the selection remains active and eligible, not suspended, withdrawn or superseded;
- database time is earlier than the freshness admission's `valid_until`; and
- the full code-owned endpoint-resolution lease lifetime remains available.

The lease lifetime is exactly 15 seconds measured from authoritative database time. It cannot be
shortened or extended by a caller, renewed, heartbeated or reopened. If fewer than 15 seconds
remain on the freshness admission, authorization fails closed rather than issuing a shorter lease.
The lease `valid_until` therefore never exceeds the admission `valid_until`.

The lease records only exact source IDs and digests, scope and route-set identity, head generation
and fencing evidence, resolver subject, code-owned policy evidence, `issued_at`, `valid_until`,
state `authorized_unconsumed`, authority declarations and a canonical digest. It contains no raw
hostname, URL, IP address, port, namespace, topic, stream, queue, partition, routing key, private
route descriptor, endpoint-set content, credential assignment, secret, key, certificate, proxy,
network result, readiness result, provider message, publication attempt or delivery receipt.

`endpoint_resolution_authority` is true. It means only that the exact resolver workload may use a
future trusted materializer boundary to attempt one internal endpoint resolution while every
source and fence remains valid. Route-selection, route-binding, credential-access, network-access,
readiness-probe, publication, delivery, dispatch and execution authority remain false. The lease
ID and integrity reference are identifiers, not bearer capabilities.

One freshness admission can produce at most one lease. Exact idempotent replay returns the same
lease only while database time remains inside both lease and freshness windows and the exact
current-head fence is unchanged. Expiry, head drift, suspension, withdrawal, supersession,
changed requests, competing identities, source drift, cross-scope evidence or audit failure fail
closed without a partial lease or claim.

Lease and idempotency rows are append-only and stored atomically. Production persistence never
falls back to memory. Effective state is derived as active or expired from database time; history
is not rewritten when the window closes.

A later endpoint materializer must use the same resolver subject and audience. In one transaction
it must lock binding, route snapshot, current head, freshness admission and lease in that order,
revalidate both time windows and the exact head fence, then atomically write a unique append-only
consumption claim together with the protected materialization result. The claim makes every
attempt, including a failed materialization attempt, consume the lease exactly once. IMP-201
defines this mandatory consumption contract but does not expose a consumption API or materialize
an endpoint.

Authorized humans may read minimized lease evidence through a dedicated default-deny permission
and the existing username/password browser session. Human API and UI views omit source, policy,
fencing-token and canonical digests, expose no route or endpoint material and provide no issue,
renew, transfer, consume, resolve, credential, probe, publish, deliver, dispatch or execute
control. They require no second login or MFA.

## Consequences

- Freshness evidence is no longer mistaken for endpoint access authority.
- Resolution authority is bound to one exact resolver identity, source chain and fenced head for
  only 15 seconds.
- The eventual materializer has an explicit single-use contract and cannot reuse a historical or
  transferred lease.
- Endpoint material, credentials and network operations remain outside this boundary.
- Head movement invalidates downstream use even if wall-clock TTL has not expired.
- A new freshness admission is required after the original window closes; authorization cannot
  silently extend currentness.

## Deferred Scope

- Lease consumption API and append-only consumption claim implementation
- Raw endpoint, destination and routing-value materialization
- Protected endpoint-artifact encryption, storage and access policy
- Credential assignment, brokerage, secret, key or certificate access
- DNS, TLS, socket, broker metadata and readiness probes
- Provider adapter calls and publication
- Delivery, retry, acknowledgement, receipt and quarantine
- Worker dispatch and execution
- Route failover, rebinding and binding-supersession chains

## Validation

- Domain and application tests cover exact subject/audience binding, code-owned 15-second TTL,
  admission-window containment, exact replay, competing identity, expiry, head drift, suspension,
  withdrawal, supersession, source drift, cross-scope evidence, authority and audit failure.
- PostgreSQL tests cover fixed-order source locking, database-time evaluation, digest
  recomputation, concurrent head movement, uniqueness, atomic lease/claim insertion, append-only
  triggers, rollback and no production memory fallback.
- Static tests reject raw locators, endpoint material, credentials, secrets, certificates,
  network/readiness results, provider messages, attempts and receipts.
- API tests prove resolver-workload-only creation, default-deny human read, no-store responses,
  minimized C1 metadata and normalized external errors.
- Web tests prove active/expired read-only presentation, empty/error states, one true endpoint-
  resolution authority declaration, nine false authority declarations, zero operational controls
  and no second-login or MFA text.
- Full backend/frontend suites, Alembic single-head validation, live PostgreSQL concurrency tests
  and live browser inspection are required before merge.
