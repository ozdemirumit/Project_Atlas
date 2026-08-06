# ADR-035: Connector Runtime Trust Grant Contract

- Status: Accepted
- Date: 2026-08-06
- Owners: Product Owner, Solution Architecture, Security Architecture

## Context

ADR-034 administratively enables one exact signed C0/C1 capability set for a configuration-validated
connector. It does not establish where or how the package may be loaded. The next lifecycle decision
must bind that exact enabled instance to an approved isolated runner boundary without starting a
runner, loading package code, resolving credentials, connecting to a target, or invoking a capability.

Runtime trust is platform admission evidence. It is not execution authorization, deployment
approval, target authorization, or a claim that a runtime process is healthy or currently running.

## Decision

Atlas introduces an immutable runtime-trust grant that verifies one exact current capability
enablement, one signed runtime profile, and one signed runtime-trust policy.

### Request Boundary

The caller supplies only exact capability-enablement ID/digest, package digest, runtime-profile
ID/digest, trust-policy ID/digest, purpose, acknowledgement, idempotency, and correlation.

Runner image, pool, workload identity, sandbox, filesystem, network, secret-delivery, telemetry,
resource, target, credential, capability, command, parameter, schedule, execution, deployment, and
mutation fields are forbidden in the request. They come only from signed governed evidence.

### Signed Runtime Profile

The profile binds organization, environment, package, connector, release, manifest, instance,
capability-enablement digest, SDK profile, runner runtime, runner pool, immutable runner image digest,
workload identity, isolation profile, filesystem policy, egress policy, secret-delivery policy,
telemetry policy, resource-limit profile, signer, signature-verification state, issue/expiry time,
and canonical digest.

The profile contains no target coordinates, secret references or values, invocation input, command,
schedule, executable content, or mutable runner configuration.

### Independent Verification

The service independently reloads and completely revalidates the capability enablement and all
package, registration, installation, instance, target, credential-reference, configuration-evidence,
and capability-governance lineage. It verifies exact digests and scope, signed profile/policy
integrity and freshness, package/manifest/instance/enablement parity, registered SDK compatibility,
approved runner runtime and pool, immutable image digest, required workload identity and isolation,
filesystem, egress, secret-delivery, telemetry, and resource profiles, actor separation, and the
absence of later authority.

Only a dedicated exact-tenant MFA human with C3 permission may grant runtime trust. The actor must
be distinct from every upstream actor and profile/policy signer. AI, service, shared, wrong-scope,
and insufficient-assurance identities fail closed without discovery.

### Resulting Authority

A valid grant sets `runtime_boundary_bound`, `runtime_trust_granted`, and
`eligible_for_secret_brokerage`, with effective state `enabled_runtime_trusted`.

It keeps `runner_started`, `package_loaded`, `credential_resolution_authorized`,
`credentials_resolved`, `target_connection_authorized`, `capability_invocation_authorized`,
`execution_authorized`, `deployment_approved`, and `infrastructure_mutation_performed` false.
No process, filesystem mount, network rule, secret delivery, target session, health check, schedule,
or capability invocation occurs while creating or reading the grant.

Every future secret resolution or invocation must independently reload this grant and satisfy
current revocation, expiry, runtime health, target, policy, approval, and evidence requirements.

### Persistence, Audit, And API

Grants are immutable, one-to-one per capability enablement for version one, deterministic,
idempotent, concurrency-safe, and equivalent in memory/PostgreSQL. Required intent and completion
audit succeed before persistence. APIs use dedicated default-deny RBAC, exact scope, MFA, browser
session, CSRF on mutation, strict schemas, no-store responses, safe errors, and minimized evidence.

Audit and web output exclude target coordinates, credential/secret internals, invocation content,
signatures, request fingerprints, idempotency keys, and mutable runner configuration.

## Consequences

### Positive

- Runtime admission is exact, signed, package- and instance-bound, and independently reviewable.
- A trusted package cannot run outside its approved isolation and workload boundary.
- Runtime trust cannot silently become secret access, target access, or capability invocation.

### Costs

- Runtime profiles must be regenerated when runner images or boundary policies change.
- Revocation and expiry must be checked again before every later secret or invocation operation.
- Secret brokerage, runtime health, scheduling, and invocation remain separate lifecycle work.

## Rejected Alternatives

### Trust A Package Globally

Rejected because trust depends on organization, environment, instance, enabled capabilities, and
the exact runner boundary rather than package identity alone.

### Let The Caller Select Runner Controls

Rejected because callers or AI could weaken isolation, egress, workload identity, or secret policy.

### Start The Runner To Prove Trust

Rejected because a lifecycle admission decision must not load untrusted code or become an
invocation path. Runtime health requires a later bounded evidence contract.

## Follow-Up

The next independent lifecycle contracts cover secret-resolution brokerage, runtime health
evidence, scheduling, and governed invocation.
