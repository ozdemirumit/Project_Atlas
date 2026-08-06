# ADR-036: Connector Secret Brokerage Authorization Contract

- Status: Accepted
- Date: 2026-08-06
- Owners: Product Owner, Solution Architecture, Security Architecture

## Context

ADR-035 binds one exact enabled connector to a signed isolated runtime boundary. It grants no
credential resolution and starts no process. The next lifecycle decision must authorize a future
isolated runner to request one short-lived secret lease without allowing a web caller, API process,
AI agent, persistence adapter, log, audit event, or model context to receive secret material.

Authorization to use the broker is not secret resolution. A runtime that later activates must
reload this evidence and independently satisfy workload identity, revocation, target, freshness,
lease, and invocation policy before a broker may resolve and deliver anything.

## Decision

Atlas introduces an immutable secret-brokerage authorization that verifies one exact current
runtime-trust grant, one signed brokerage profile, and one signed brokerage policy.

### Request Boundary

The caller supplies only exact runtime-trust grant ID/digest, package digest, brokerage-profile
ID/digest, brokerage-policy ID/digest, purpose, acknowledgement, idempotency, and correlation.

Credential profile, secret reference, store, path, version, lease TTL, broker, workload identity,
delivery channel, target, network, runner, capability, command, parameter, schedule, execution,
deployment, and mutation fields are forbidden. They come only from signed governed evidence and
the revalidated upstream lineage.

### Signed Brokerage Profile

The profile binds organization, environment, package, connector, release, manifest, instance,
runtime-trust digest, credential-profile digest, runtime-profile digest, exact runner workload
identity, approved broker, secret-store profile, memory-only delivery policy, one-time lease policy,
maximum lease lifetime, revocation-check policy, signer, signature state, issue/expiry time, and
canonical digest.

It contains no secret reference or value, store path, credential value, username, token, private
key, certificate body, target coordinate, command, invocation input, or executable content.

### Independent Verification

The service reloads and completely revalidates the runtime-trust grant and all package,
registration, installation, instance, target, credential-reference, configuration, capability, and
runtime lineage. It verifies exact digests and tenant scope, signed profile/policy integrity and
freshness, instance and credential-profile parity, current rotation/revocation posture, read-only
privilege, exact trusted workload identity and secret-delivery policy, approved broker/store,
memory-only one-time delivery, bounded lease lifetime, actor separation, and no later authority.

Only a dedicated exact-tenant hardware-backed MFA human with C3 permission may authorize
brokerage. The actor must be distinct from every upstream actor and profile/policy signer. AI,
service, shared, wrong-scope, and insufficient-assurance identities fail closed without discovery.

### Resulting Authority

A valid record sets `secret_brokerage_governed`, `credential_resolution_authorized`, and
`eligible_for_runtime_activation`, with state `enabled_secret_brokerage_governed`.

It keeps `secret_lease_issued`, `credentials_resolved`, `runner_started`, `package_loaded`,
`target_connection_authorized`, `capability_invocation_authorized`, `execution_authorized`,
`deployment_approved`, and `infrastructure_mutation_performed` false. Creating or reading the
record performs no secret-store call, token exchange, process start, filesystem mount, network
request, target session, health check, schedule, or capability invocation.

The later runtime-activation path must reload this authorization and may request only a fresh,
single-use, non-renewable, workload-bound lease. Secret material may be delivered only directly to
the approved isolated runtime through the signed memory-only channel and must never be returned to
Atlas API or ordinary persistence.

### Persistence, Audit, And API

Authorizations are immutable, one-to-one per runtime-trust grant for version one, deterministic,
idempotent, concurrency-safe, and equivalent in memory/PostgreSQL. Required intent and completion
audit succeed before persistence. APIs use dedicated default-deny RBAC, exact scope, hardware MFA,
browser session, CSRF on mutation, strict schemas, no-store responses, safe errors, and minimized
evidence.

Audit and web output exclude credential-profile identity, secret reference, store identity/path,
broker internals, lease material, target details, signatures, request fingerprints, idempotency
keys, and mutable runner data.

## Consequences

### Positive

- Web users and AI can authorize a governed future lease without seeing or selecting secret data.
- Secret access stays exact-tenant, instance-, runtime-, workload-, credential-, and policy-bound.
- Rotation, revocation, expiry, and workload health remain mandatory at actual lease issuance.

### Costs

- Credential governance and broker catalogs must remain synchronized and signed.
- Runtime activation requires a separate one-time lease and direct-memory delivery protocol.
- Runtime health, target sessions, scheduling, and invocation remain separate lifecycle work.

## Rejected Alternatives

### Resolve The Secret During Authorization

Rejected because no isolated runtime exists to receive it and authorization must remain free of
secret-store and network side effects.

### Return An Opaque Lease Handle To The Browser

Rejected because bearer-like handles can be exfiltrated, replayed, logged, or correlated with
credential internals.

### Let The Caller Select Broker Or Lease Controls

Rejected because callers or AI could redirect delivery, extend lifetime, weaken workload binding,
or select a different credential boundary.

## Follow-Up

The next independent lifecycle contracts cover runtime activation and health evidence, fresh
single-use lease delivery, target-session authorization, scheduling, and governed invocation.
