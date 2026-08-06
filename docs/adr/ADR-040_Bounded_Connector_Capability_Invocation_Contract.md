# ADR-040: Bounded Connector Capability Invocation Contract

- Status: Accepted
- Date: 2026-08-06
- Owners: Product Owner, Solution Architecture, Security Architecture
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-020,
  ATLAS-021, ATLAS-023, ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033,
  ATLAS-037, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-053, ATLAS-055, ATLAS-056,
  ADR-009 through ADR-039

## Context

ADR-039 creates one short-lived, single-use, non-renewable authorization bound to an exact closed
target-session verification, enabled C0/C1 capability, signed invocation profile, and signed typed
input-envelope digest. It does not consume that authorization, reconnect to a target, obtain a
secret lease, invoke a connector handler, validate a result, or ingest evidence.

The next lifecycle boundary must invoke exactly one authorized read-only capability while keeping
target coordinates, credentials, secret material, lease and session handles, raw input, commands,
and raw vendor output outside the API, web, persistence, audit, logs, and model context. It must
also prevent replay when a timeout or transport failure leaves the remote outcome uncertain.

## Decision

Atlas will implement a dedicated bounded connector capability-invocation service. The service
atomically consumes one unexpired ADR-039 authorization before any side effect, invokes exactly one
C0/C1 handler through a narrow trusted adapter, closes every ephemeral resource, validates and
redacts the returned evidence, and persists an immutable minimized completion record.

### Caller Contract

The caller may provide only:

- exact invocation-authorization ID and canonical digest;
- exact package digest;
- exact signed bounded-invocation policy ID and digest;
- a bounded operational purpose;
- explicit acknowledgement of one-way single-use consumption and uncertain-outcome handling;
- idempotency and correlation identifiers.

The caller cannot provide or override target coordinates, DNS names, ports, protocols, routes,
TLS material, credential or secret identities, broker or lease details, workload or runner details,
session handles, capability ID, handler name, input fields, commands, timeout, output limits,
redaction controls, schedules, execution flags, deployment flags, or mutation controls.

### Authorization And Lineage

Before consumption the service revalidates:

- the complete immutable connector lifecycle lineage through ADR-039;
- exact authorization ID, digest, schema, state, tenant, package, instance, capability, profile,
  input-envelope, and policy bindings;
- C0 or C1 capability class and the capability's exact required permission at invocation time;
- authorization freshness, single-use, non-renewable, and initially unconsumed state;
- exact signed bounded-invocation policy, signer, schema, scope, and freshness;
- hardware-backed human assurance and separation from every upstream lifecycle actor, policy
  signer, profile signer, envelope signer, adapter attestor, and workload identity;
- absence of scheduling, prior invocation, result ingestion, execution, deployment, and
  infrastructure-mutation authority.

Wrong-scope, expired, development-assurance, service, shared, already-consumed, altered, ambiguous,
or insufficiently authorized requests fail closed without target access.

### Atomic Single-Use Consumption

After intent audit succeeds and before the adapter is called, the repository creates an immutable
consumption claim with a unique constraint on the authorization ID. Claim creation is the atomic
point of no return.

An existing claim returns the same completed record only when actor, idempotency key, request
fingerprint, and completion evidence match. Otherwise the request fails as already consumed. A
claim is never deleted or released after timeout, cancellation, adapter failure, audit failure, or
uncertain remote outcome. Operators must investigate uncertain outcomes and obtain a new upstream
authorization; Atlas never retries automatically.

### Trusted Adapter Boundary

The application sends the adapter an immutable instruction containing only trusted IDs, digests,
capability class, bounded timeout and output limits, policy references, and the invocation ID. The
adapter resolves the signed typed input envelope, target binding, workload identity, fresh
credential lease, and transport internally. Those values and handles never cross into the
application service.

The adapter must:

1. verify the exact trusted instruction and current connector runtime boundary;
2. obtain one fresh memory-only lease through the trusted broker;
3. establish one fresh bounded target session using trusted target configuration;
4. invoke exactly the authorized handler once with the exact signed input envelope;
5. enforce timeout and output-size limits;
6. validate the output schema and apply the signed redaction/result policy;
7. close the target session and delivery channel and revoke or expire the lease in all outcomes;
8. return a signed minimized receipt with no raw input, raw output, secret, handle, or coordinate.

Production fails closed when no trusted adapter is configured. Development may use a deterministic
synthetic adapter that performs no DNS, network, secret-store, process, filesystem, vendor, model,
deployment, or infrastructure operation.

### Completion Receipt

A successful immutable record uses state `enabled_bounded_capability_invocation_completed` and
contains only lineage IDs and digests, capability ID/class and required permission, policy ID and
digest, adapter ID, normalized redacted-result digest, result schema digest, bounded observation
count, timing, cleanup proof, actor, purpose, and canonical digest.

It records that authorization consumption, one bounded connection, one capability call, result
receipt, schema validation, redaction, target-session closure, delivery-channel closure, and lease
revocation were proven. At rest the target is disconnected and no reusable runtime handle remains.

Scheduling, persistent evidence ingestion, model-context publication, workflow continuation,
autonomous execution, deployment approval, and infrastructure mutation remain false and outside
this ADR.

### Failure And Uncertain Outcome

Failures before claim creation cause no consumption and no adapter call. Failures after claim
creation permanently consume the authorization. The service emits safe audit outcomes that
distinguish rejected, failed, timed-out, and uncertain attempts without including sensitive data.

No completion record is created unless the receipt signature, instruction binding, result schema,
redaction proof, output limits, timestamps, and complete cleanup proof validate. Missing cleanup
proof or ambiguous adapter outcome is treated as uncertain and never retried.

### Persistence, Audit, And API

Consumption claims and completion records are immutable, deterministic, concurrency-safe, and
equivalent in memory and PostgreSQL. Required intent audit precedes claim creation. Claim audit
follows successful atomic consumption. Completion audit succeeds before completion persistence.

APIs use dedicated default-deny RBAC, exact capability permission re-evaluation, hardware MFA,
browser session, mutation CSRF, strict request schemas, no-store responses, safe errors, and
minimized evidence. Persistence, audit, logs, and web output exclude raw input and output, target
coordinates, credential and secret identities, store/broker/lease/session identity, tokens,
signatures, commands, request fingerprints, idempotency keys, and mutable runtime data.

## Consequences

### Positive

- A single-use authorization cannot be replayed after a timeout or uncertain remote outcome.
- Exactly one signed C0/C1 capability and typed input envelope reach a trusted adapter.
- All target, secret, session, and raw vendor material remains inside the adapter boundary.
- Successful output is schema-validated, redacted, bounded, signed, and attributable.
- The final persisted state proves cleanup and leaves no reusable connection or lease.

### Costs

- A failed or uncertain attempt consumes the authorization and requires human investigation.
- Production adapters must support fresh lease/session setup, deterministic cleanup, result
  validation, redaction, signing, and explicit uncertain-outcome reporting.
- Input-envelope and result-policy stores must be available inside the trusted runtime boundary.

## Rejected Alternatives

### Consume After A Successful Result

Rejected because concurrent requests and uncertain outcomes could invoke the same capability more
than once.

### Automatically Retry Timeouts

Rejected because Atlas cannot prove whether the remote system processed the first call.

### Return Raw Vendor Output

Rejected because it can contain secrets, coordinates, identifiers, commands, personal data, and
unbounded or malicious content.

### Reuse The Earlier Target Session Or Secret Lease

Rejected because ADR-038 proves both were closed and revoked. Invocation must obtain fresh,
bounded, internally managed ephemeral resources.

## Follow-Up

Later independent lifecycle contracts cover durable evidence ingestion, governed scheduling,
workflow continuation, uncertain-outcome investigation, connector re-attestation, and upgrade.
