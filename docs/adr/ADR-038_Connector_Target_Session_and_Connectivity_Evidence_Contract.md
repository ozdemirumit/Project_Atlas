# ADR-038: Connector Target Session and Connectivity Evidence Contract

- Status: Accepted
- Date: 2026-08-06
- Owners: Product Owner, Solution Architecture, Security Architecture

## Context

ADR-037 activates one exact signed connector runtime and proves bounded local health. It grants no
target access and leaves no credential lease active. The next lifecycle decision must verify that
the exact runtime can authenticate to the exact governed target through the approved network path
without exposing target coordinates, credentials, lease handles, session handles, protocol
transcripts, or raw vendor responses to web, API, AI, persistence, audit, logs, or model contexts.

Connectivity evidence is not capability invocation. A successful handshake proves only bounded
transport, target identity, authentication, and least-privilege session establishment. It must not
run discovery, inventory, health, diagnostic, configuration, or mutation functions.

## Decision

Atlas introduces an immutable connector target-session verification record that verifies one exact
current runtime activation, one signed target-session profile, one signed target-session policy,
and one signed safe connectivity receipt from a trusted target-session adapter.

### Request Boundary

The caller supplies only exact runtime-activation ID/digest, package digest, target-session profile
ID/digest, target-session policy ID/digest, purpose, acknowledgement, idempotency, and correlation.

Target ID, address, hostname, endpoint, port, protocol, proxy, route, certificate, credential,
secret, store, broker, lease, session, workload, runner, command, capability, parameter, schedule,
execution, deployment, and mutation fields are forbidden. They come only from signed governed
evidence and the revalidated upstream lineage.

### Signed Target Session Profile

The profile binds organization, environment, package, connector, release, manifest, instance,
runtime-activation digest, target-profile digest, expected target product and identity digest,
approved protocol and TLS policy, certificate-validation policy, network-path policy, workload
identity digest, credential-profile digest, broker/delivery/lease policy digests, session adapter,
session timeout, bounded handshake checks, signer, signature state, issue/expiry time, and canonical
digest.

It contains no target coordinate, secret reference or value, store path, username, token, private
key, certificate body, lease handle, session handle, command, capability input, or executable
content.

### Independent Verification

The service reloads and completely revalidates runtime activation and all package, registration,
installation, instance, target, credential-reference, configuration, capability, runtime-trust,
brokerage, and activation lineage. It verifies exact digests and tenant scope, signed
profile/policy integrity and freshness, target/product and workload parity, current credential
rotation/revocation posture, exact approved network and TLS controls, read-only privilege, bounded
handshake checks, actor separation, and no capability or later authority.

Only a dedicated exact-tenant hardware-backed MFA human with C3 permission may request target
verification. The actor must be distinct from every upstream actor, profile/policy signer,
target-session adapter attestor, and workload identity. AI, service, shared, wrong-scope, and
insufficient-assurance identities fail closed without discovery.

### Trusted Target Session Boundary

After validation and required intent audit, the application passes only an opaque exact signed
session instruction to a trusted target-session adapter. The adapter is the sole component allowed
to attest the workload, request a fresh single-use lease, deliver credentials directly to runtime
memory, resolve signed target coordinates internally, establish the approved transport and TLS
channel, authenticate, verify bounded target identity and read-only privilege, close the session,
close the delivery channel, revoke or expire the lease, and return signed safe evidence.

The application receives no coordinate, credential, lease/session handle, certificate body,
protocol transcript, command, process output, or raw vendor response. Production fails closed when
no trusted adapter is configured. The development adapter is deterministic and synthetic: it proves
orchestration and evidence contracts without reading a secret store, opening a socket, resolving
DNS, starting a process, or contacting a target.

Adapter timeout, ambiguous completion, target mismatch, authentication or TLS failure, privilege
mismatch, invalid evidence, or cleanup failure does not produce a successful record. The adapter
must close or quarantine the session/runtime and revoke or expire the lease. Atlas records safe
failure evidence and grants no later authority.

### Resulting Authority

A valid record sets `target_connection_authorized`, `target_connectivity_verified`,
`target_identity_verified`, `read_only_session_verified`, `target_session_established`,
`target_session_closed`, and `eligible_for_capability_invocation_governance`, with state
`enabled_target_session_verified`.

The record keeps `target_connected` false because no reusable session remains. It also keeps
`capability_invocation_authorized`, `capability_invoked`, `scheduled`, `execution_authorized`,
`deployment_approved`, and `infrastructure_mutation_performed` false. Creating or reading the
record performs no connector capability call, inventory read, health query, schedule, deployment,
or infrastructure mutation.

### Persistence, Audit, And API

Verification records are immutable, one-to-one per runtime activation for version one,
deterministic, idempotent, concurrency-safe, and equivalent in memory/PostgreSQL. Required intent
audit succeeds before the handshake; required completion audit succeeds before persistence. APIs
use dedicated default-deny RBAC, exact scope, hardware MFA, browser session, CSRF on mutation,
strict schemas, no-store responses, safe errors, and minimized evidence.

Persistence, audit, and web output exclude target ID and coordinates, credential profile identity,
secret/store/broker identity, lease/session identity or timing, certificate body, network route,
raw target response, signatures, request fingerprints, idempotency keys, and mutable runtime data.
Safe evidence contains only approved profile/policy digests, target identity digest, normalized
protocol/TLS classifications, bounded check identifiers and outcomes, verification time, and
canonical digest.

## Consequences

### Positive

- Target identity, authentication, transport, and least-privilege posture are proven before any
  connector capability can be considered.
- Credentials and target coordinates remain inside the trusted runtime boundary.
- Every verification ends with a closed session and revoked or expired lease.
- Production target implementations can evolve behind a narrow signed adapter contract.

### Costs

- Production requires hardened broker, runtime, network, TLS, and target-session adapters.
- Vendor-specific handshake semantics need independent evidence and test fixtures.
- A successful handshake does not prove that any declared capability behaves correctly.

## Rejected Alternatives

### Keep The Session Open For Later Invocation

Rejected because a reusable session becomes ambient authority, weakens revocation, and complicates
ownership, timeout, failover, and audit guarantees.

### Return An Opaque Session Handle

Rejected because bearer-like handles can be replayed, logged, correlated with target details, or
passed into unauthorized capability calls.

### Run A Read-Only Discovery Capability During Verification

Rejected because authentication and connectivity evidence must remain independent from connector
capability governance, invocation inputs, output validation, scheduling, and operational intent.

## Follow-Up

The next independent lifecycle contracts cover capability invocation authorization, bounded
read-only invocation, scheduling, output validation and evidence ingestion, runtime/session
teardown, and re-attestation or upgrade.
