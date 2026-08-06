# ADR-034: Connector Capability Governance And Enablement Contract

- Status: Accepted
- Date: 2026-08-06
- Owners: Product Owner, Solution Architecture, Security Architecture

## Context

ADR-033 proves bounded configuration and connectivity posture for a disabled connector without
granting a capability or runtime authority. The next lifecycle decision must select the exact
registered capabilities that an organization permits for that instance. Administrative enablement
must not be confused with runtime trust, credential resolution, target access, or execution.

## Decision

Atlas introduces an immutable capability-enablement record that verifies one exact current
configuration validation, one signed capability profile, and one signed enablement policy. Version
one permits only manifest-declared C0 informational and C1 read-only capabilities with read-only
permissions already admitted by the governed registration pipeline.

### Request Boundary

The caller supplies only exact configuration-validation ID/digest, package digest, capability
profile ID/digest, enablement-policy ID/digest, purpose, acknowledgement, idempotency, and
correlation. Capability IDs/classes, commands, parameters, target coordinates, credentials,
secret references or values, network settings, runtime, deployment, and mutation fields are
forbidden in the request.

### Signed Capability Profile

The profile binds organization, environment, package, connector, release, manifest, instance,
target type, exact capability ID/class/required-permission tuples, profile signer,
signature-verification state, issue/expiry time, and canonical digest. It contains no endpoint,
credential, invocation parameter, command, executable content, or target data.

### Independent Verification

The service independently reloads and completely revalidates the current configuration validation
and all package, registration, installation, instance, target, credential, and evidence lineage.
It verifies exact digests and scope, signed profile/policy integrity and freshness, manifest parity,
allowed C0/C1 classes, registered permissions, target compatibility, required
separation, and no-later-authority state.

Only a dedicated exact-tenant MFA human with C3 permission may enable the governed capability set.
The actor must be distinct from every upstream actor and profile/policy signer. AI, service, shared,
wrong-scope, and insufficient-assurance identities fail closed without discovery.

### Resulting Authority

A valid record sets `capability_governance_applied`, `connector_enabled`, and
`eligible_for_runtime_trust`, with effective state `enabled_capabilities_governed`. The enabled flag
means only that a bounded capability set is administratively selected. It does not start a process,
resolve a credential, connect to a target, invoke a capability, schedule work, grant runtime trust,
authorize execution, approve deployment, or mutate infrastructure.

`credentials_resolved`, `runtime_trust_granted`, `execution_authorized`, `deployment_approved`, and
`infrastructure_mutation_performed` remain false. Every future invocation must independently reload
this record and satisfy runtime trust, policy, approval, and evidence requirements.

### Persistence, Audit, And API

Records are immutable, one-to-one per configuration validation for version one, deterministic,
idempotent, concurrency-safe, and equivalent in memory/PostgreSQL. Required intent and completion
audit succeed before persistence. APIs use dedicated default-deny RBAC, exact scope, MFA, browser
session, CSRF on mutation, strict schemas, no-store responses, safe errors, and minimized evidence.

Audit and web output exclude target coordinates, credential/secret internals, invocation content,
signatures, request fingerprints, and idempotency keys.

## Consequences

### Positive

- Capability authority is exact, signed, manifest-bound, and independently reviewable.
- Administrative enablement cannot execute a connector or expose credentials.
- C2 through C5 capabilities remain impossible in the version-one enablement path.

### Costs

- Capability profiles must be regenerated when package manifests or organizational policy changes.
- Runtime trust, health evidence, scheduling, and invocation remain separate lifecycle work.

## Rejected Alternatives

### Accept Caller-Selected Capability IDs

Rejected because callers or AI could expand authority beyond a reviewed signed profile.

### Enable Every Manifest Capability

Rejected because package declaration is not organizational authorization and future manifests may
contain higher-risk capabilities.

### Execute A Health Check During Enablement

Rejected because administrative lifecycle promotion must not resolve secrets, create network
traffic, or become an invocation path.

## Follow-Up

The next independent lifecycle contracts cover runtime trust, secret-resolution brokerage, health
evidence, scheduling, and governed invocation.
