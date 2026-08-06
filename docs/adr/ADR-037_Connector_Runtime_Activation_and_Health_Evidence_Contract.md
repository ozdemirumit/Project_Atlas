# ADR-037: Connector Runtime Activation and Health Evidence Contract

- Status: Accepted
- Date: 2026-08-06
- Owners: Product Owner, Solution Architecture, Security Architecture

## Context

ADR-036 authorizes one exact trusted connector workload to use governed secret brokerage, but it
does not issue a lease, resolve a credential, start a runner, or load a package. The next lifecycle
decision must activate the exact signed runtime boundary and prove local runtime health without
allowing web, API, AI, persistence, audit, logs, or model contexts to receive credential material or
lease handles. Activation must not authorize a target session or invoke a connector capability.

Runtime activation is a bounded platform operation, not infrastructure execution. It may establish
only the approved isolated runner, exact package, direct memory-only secret delivery, and signed
local health evidence required by later target-session authorization.

## Decision

Atlas introduces an immutable connector runtime activation record that verifies one exact current
secret-brokerage authorization, one signed activation profile, one signed activation policy, and one
signed safe activation receipt from a trusted runtime activation adapter.

### Request Boundary

The caller supplies only exact secret-brokerage authorization ID/digest, package digest,
activation-profile ID/digest, activation-policy ID/digest, purpose, acknowledgement, idempotency,
and correlation.

Credential profile, secret reference, store, broker, lease, token, workload identity, runner,
image, filesystem, environment variable, delivery channel, health command, target, network,
capability, command, parameter, schedule, deployment, and mutation fields are forbidden. They come
only from signed governed evidence and the revalidated upstream lineage.

### Signed Activation Profile

The profile binds organization, environment, package, connector, release, manifest, instance,
secret-brokerage authorization digest, runtime-profile digest, exact runner and image identity,
workload identity, isolation, filesystem, egress, memory-only delivery and lease policies,
activation adapter, startup timeout, local health-probe contract, telemetry policy, resource limits,
signer, signature state, issue/expiry time, and canonical digest.

It contains no secret reference or value, store path, credential value, username, token, private
key, certificate body, lease handle, target coordinate, command, invocation input, or executable
content.

### Independent Verification

The service reloads and completely revalidates the secret-brokerage authorization and all package,
registration, installation, instance, target, credential-reference, configuration, capability,
runtime-trust, and brokerage lineage. It verifies exact digests and tenant scope, signed
profile/policy integrity and freshness, package and workload parity, current credential rotation and
revocation posture, exact immutable runner controls, approved adapter, one-time non-renewable lease,
memory-only delivery, local-only health contract, actor separation, and no later authority.

Only a dedicated exact-tenant hardware-backed MFA human with C3 permission may request activation.
The actor must be distinct from every upstream actor, profile/policy signer, activation adapter
attestor, and workload identity. AI, service, shared, wrong-scope, and insufficient-assurance
identities fail closed without discovery.

### Trusted Activation Boundary

After validation and required intent audit, the application passes only an opaque, exact signed
activation instruction to a trusted activation adapter. The adapter is the sole component allowed
to attest the workload, request a fresh single-use lease, deliver credential material directly to
the approved runtime memory channel, start the approved isolated runner, load the exact package,
perform bounded local self-health probes, close the delivery channel, and return signed safe
evidence.

The application receives no secret, lease handle, environment content, process output, or raw
health output. A production deployment fails closed when no trusted adapter is configured. The
development adapter is deterministic and synthetic: it proves orchestration and evidence contracts
without reading a secret store, starting an external process, or making a network request.

Adapter timeout, ambiguous completion, invalid evidence, failed health, or compensation failure
does not produce a successful activation. The adapter must stop or quarantine the runtime and
revoke or expire any lease. Atlas records a safe failure audit and grants no later authority.

### Resulting Authority

A valid record sets `secret_lease_issued`, `credentials_resolved`, `runner_started`,
`package_loaded`, `runtime_health_verified`, and `eligible_for_target_session_authorization`, with
state `enabled_runtime_healthy`.

These flags describe signed adapter evidence, not secret possession by Atlas. The record keeps
`target_connected`, `target_connection_authorized`, `capability_invocation_authorized`,
`capability_invoked`, `execution_authorized`, `deployment_approved`, and
`infrastructure_mutation_performed` false. Creating or reading the record performs no target
connection, vendor API call, scheduled operation, connector capability invocation, deployment, or
infrastructure mutation.

### Persistence, Audit, And API

Activation records are immutable, one-to-one per secret-brokerage authorization for version one,
deterministic, idempotent, concurrency-safe, and equivalent in memory/PostgreSQL. Required intent
audit succeeds before activation; required completion audit succeeds before persistence. APIs use
dedicated default-deny RBAC, exact scope, hardware MFA, browser session, CSRF on mutation, strict
schemas, no-store responses, safe errors, and minimized evidence.

Persistence, audit, and web output exclude credential-profile identity, secret reference,
store/broker identity, lease identity or timing, workload token, delivery internals, target details,
raw process or health output, signatures, request fingerprints, idempotency keys, and mutable runner
data. Safe evidence contains only bounded status, approved profile/policy digests, runner/package
identity digests, probe identifiers and normalized outcomes, activation time, and canonical digest.

## Consequences

### Positive

- Exact package and isolated runtime health are proven before any target-session authority exists.
- Secret material remains within the broker-to-runtime memory boundary.
- Production runtime implementations can evolve behind a narrow signed adapter contract.
- Ambiguous or unhealthy activation cannot silently progress to target access.

### Costs

- Production requires a separately hardened broker/runtime adapter and workload attestation path.
- Compensation and quarantine behavior must be tested independently for each runtime platform.
- Runtime health evidence has limited meaning until target-session evidence is added later.

## Rejected Alternatives

### Return A Lease Handle To The Application

Rejected because any bearer-like handle crossing web/API/application boundaries increases replay,
logging, persistence, and model-context exposure risk.

### Use A Shell Command Supplied By The Caller

Rejected because caller- or AI-selected commands bypass signed package, runtime, and health-probe
contracts and create arbitrary execution authority.

### Connect To The Target As Part Of Activation

Rejected because runtime health and target-session authorization require independent evidence,
policy, audit, failure handling, and human intent.

## Follow-Up

The next independent lifecycle contracts cover target-session authorization and bounded
connectivity evidence, scheduling, governed capability invocation, session teardown and lease
revocation, and runtime re-attestation or upgrade.
