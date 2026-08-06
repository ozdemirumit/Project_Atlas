# ADR-039: Connector Capability Invocation Authorization Contract

- Status: Accepted
- Date: 2026-08-06
- Owners: Product Owner, Solution Architecture, Security Architecture

## Context

ADR-038 proves that one exact healthy connector runtime can establish and close a bounded
read-only session with the governed target. It invokes no connector capability and leaves no
session or credential lease active. The next lifecycle decision must authorize one exact future
C0 or C1 capability invocation without turning connectivity evidence into ambient target access,
accepting caller-selected target coordinates, or executing the capability during authorization.

Capability enablement identifies the approved capability set, while target-session evidence proves
the current runtime, target identity, TLS, authentication, network path, and read-only privilege.
Neither record alone authorizes an invocation. Authorization must bind both lineages to one exact
capability, one signed typed-input envelope, one bounded result contract, and one short-lived,
single-use policy decision.

## Decision

Atlas introduces an immutable connector capability-invocation authorization record. It authorizes
one future bounded invocation only after independently revalidating the complete connector
lifecycle, exact target-session evidence, exact enabled capability, signed invocation profile,
signed input envelope, and signed invocation-authorization policy.

### Request Boundary

The caller supplies only the exact target-session verification ID/digest, package digest,
capability ID, invocation-profile ID/digest, input-envelope ID/digest, policy ID/digest, purpose,
acknowledgement, idempotency, and correlation.

Target ID or coordinates, endpoint, port, protocol, proxy, route, credential, secret, store,
broker, lease, session, workload, runner, command, raw parameter object, output, schedule,
execution, deployment, and mutation fields are forbidden. They come only from signed governed
evidence reloaded by the service.

### Signed Invocation Profile

The invocation profile binds organization, environment, package, connector, release, manifest,
instance, target-profile and target-identity digests, target-session digest, capability ID, C0/C1
class, required permission, input and output schema digests, input-envelope schema, result-policy
digest, maximum timeout and output bytes, invocation adapter and attestor, signer, signature state,
issue and expiry time, and canonical digest.

The profile contains no target coordinate, secret reference or value, lease/session handle,
certificate body, executable command, shell content, arbitrary URL, mutable runtime setting, raw
vendor output, or reusable authority.

### Signed Typed-Input Envelope

The input envelope binds one exact invocation profile and capability to a normalized schema-valid
input digest. Version one permits only a fixed allowlisted scalar and bounded-list JSON subset and
contains no secret, credential, target coordinate, URL, command, script, file path, binary content,
callback, or model-produced executable material. The authorization record persists only envelope
identity, schema, and digest, never raw input values.

Envelope construction and signing occur through a separate governed preparation boundary. The
authorization API cannot create, alter, merge, or reinterpret parameters.

### Independent Authorization

The service reloads and fully revalidates target-session verification and every upstream package,
registration, installation, instance, target, credential-reference, configuration, capability,
runtime-trust, brokerage, and activation record. It verifies exact digests, tenant scope, signed
profile, envelope, and policy integrity and freshness, package and instance parity, target identity,
the capability is uniquely enabled as C0 or C1, required permission parity, input/output contract
parity, one-use and expiry limits, actor separation, and no invocation or later authority.

Only a dedicated exact-tenant hardware-backed MFA human with the capability's own required
permission and dedicated C3 authorization-record permission may request authorization. The actor
must be distinct from every upstream lifecycle actor, profile, envelope, and policy signer,
invocation-adapter attestor, and workload identity. AI, service, shared, wrong-scope, expired, and
insufficient-assurance identities fail closed without discovery.

### No Invocation During Authorization

Authorization performs no target connection, DNS lookup, secret lease, credential resolution,
runner start, package load, connector handler call, vendor API request, schedule, output ingestion,
deployment, or infrastructure mutation. It calls no invocation adapter and creates no bearer token
or session handle.

Production and development use the same deterministic authorization contract. A later bounded
invocation service must revalidate the authorization and all current source evidence, perform
required intent audit, atomically consume the single use, obtain a fresh lease and session inside
the trusted runtime, invoke exactly one handler, close all ephemeral resources, validate and redact
the result, and return signed evidence. That behavior is outside this ADR.

### Resulting Authority

A valid record sets `capability_invocation_authorized` and
`eligible_for_bounded_capability_invocation`, with state
`enabled_capability_invocation_governed`. It is single-use, non-renewable, short-lived, bound to one
exact input-envelope digest, and initially unconsumed.

The record keeps `target_connected`, `capability_invoked`, `scheduled`, `result_received`,
`result_validated`, `evidence_ingested`, `execution_authorized`, `deployment_approved`, and
`infrastructure_mutation_performed` false. Creating or reading it performs no capability call.

### Persistence, Audit, And API

Authorization records are immutable, deterministic, idempotent, concurrency-safe, and equivalent
in memory and PostgreSQL. Version one allows one authorization per target-session verification.
Required intent audit succeeds before authorization construction; required completion audit
succeeds before persistence.

APIs use dedicated default-deny RBAC, exact capability permission evaluation, hardware MFA,
browser session, CSRF on mutation, strict schemas, no-store responses, safe errors, and minimized
evidence. Persistence, audit, logs, and web output exclude raw input values, target coordinates,
credential and secret identities, lease/session identity, invocation tokens, signatures, request
fingerprints, idempotency keys, commands, output, and mutable runtime data.

## Consequences

### Positive

- Connectivity proof cannot silently become ambient capability authority.
- One authorization is bound to one exact enabled C0/C1 capability and typed-input digest.
- No caller-controlled target, transport, secret, session, command, or raw parameter reaches the
  authorization service.
- A later invocation boundary can consume a short-lived single-use record atomically.

### Costs

- Input-envelope preparation, signing, storage, and schema governance require a trusted source.
- Capability-specific required permissions must be evaluated in addition to generic authorization
  record permissions.
- Authorization expiry can require a new human decision even when connectivity evidence remains
  otherwise current.

## Rejected Alternatives

### Invoke Immediately After Authorization

Rejected because authorization, single-use consumption, target access, result validation, cleanup,
and uncertain-outcome handling require independent evidence and failure boundaries.

### Accept Raw Parameters In The Authorization API

Rejected because it permits schema confusion, target or command injection, secret disclosure, and
parameter substitution between authorization and invocation.

### Authorize The Entire Enabled Capability Set

Rejected because broad reusable authority violates least privilege, weakens intent binding, and
makes audit and revocation ambiguous.

## Follow-Up

The next independent lifecycle contracts cover atomic single-use consumption and bounded C0/C1
invocation, signed result validation and redaction, evidence ingestion, scheduling, teardown and
uncertain outcomes, and re-attestation or upgrade.
