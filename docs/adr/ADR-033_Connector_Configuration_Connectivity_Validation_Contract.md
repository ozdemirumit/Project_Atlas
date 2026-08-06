# ADR-033: Connector Configuration And Connectivity Validation Contract

- Status: Accepted
- Date: 2026-08-06
- Owners: Product Owner, Solution Architecture, Security Architecture

## Context

ADR-032 assigns governed credential metadata to an exact disabled connector instance without
resolving a secret or connecting to a target. The next lifecycle decision must establish that the
bound configuration is internally coherent and that a separately governed, isolated probe observed
the expected target through read-only authentication. This decision must not turn Atlas web/API,
ordinary persistence, audit, or LLM contexts into secret or network execution paths.

## Decision

Atlas introduces an immutable configuration-validation record that verifies one exact current
credential assignment, one signed bounded probe-evidence snapshot, and one signed validation
policy. The validation service is an evidence verifier. It does not perform DNS, open a socket,
resolve a credential, execute a connector package, authenticate to a target, or invoke a capability.

### Request Boundary

The caller supplies only exact credential-assignment ID/digest, package digest, validation-evidence
ID/digest, validation-policy ID/digest, purpose, acknowledgement, idempotency, and correlation.
Endpoint, URL, host, IP, port, protocol configuration, username, password, token, key, certificate,
secret reference/store path, raw probe output, command, capability, runtime, enablement, deployment,
and mutation fields are forbidden.

### Signed Probe Evidence

The independently produced evidence binds organization, environment, assignment, package,
instance, target profile, credential profile, isolated probe runner and network zone. It reports
only bounded classifications for configuration, reachability, TLS trust, endpoint identity,
authentication, read-only authorization, product identity, latency, and required checks. It carries
observation/issue/expiry time, signer, signature-verification state, and canonical digest.

The evidence contains no target coordinates, secret reference or value, username, token, key,
certificate content, session material, request/response body, command output, stack trace, or raw
vendor error. Those values must remain inside the isolated probe boundary and its restricted
operational evidence store.

### Independent Verification

The service independently reloads and completely revalidates the current credential assignment and
all of its package, installation, instance, target, profile, and policy lineage through owning
services. It verifies exact digests and scope, assignment state, evidence signature/freshness,
allowed runner/network zone, expected target/product identity, read-only authentication and
authorization classifications, required checks, policy signature/freshness, and no-later-authority
state.

Only a dedicated exact-tenant MFA human with C3 permission may create the record. The actor must be
distinct from every upstream actor plus evidence and policy signers. AI, service, shared,
wrong-scope, and insufficient-assurance identities fail closed without discovery.

### Resulting Authority

A valid record sets only `configuration_validated`, `connectivity_evidence_verified`, and
`eligible_for_capability_governance`, with effective state `disabled_configuration_validated`.
It keeps `credentials_resolved`, `connector_enabled`, `runtime_trust_granted`,
`execution_authorized`, `deployment_approved`, and `infrastructure_mutation_performed` false.

The validation result is not reusable as a credential, session, network route, health result,
runtime grant, capability grant, execution approval, deployment approval, or change approval.

### Persistence, Audit, And API

Records are immutable, one-to-one per credential assignment for version one, deterministic,
idempotent, concurrency-safe, and equivalent in memory/PostgreSQL. Required intent and completion
audit succeed before persistence. APIs use dedicated default-deny RBAC, exact scope, MFA, browser
session, CSRF on mutation, strict schemas, no-store responses, safe errors, and minimized evidence.

Audit and web output exclude target coordinates, secret/reference/store internals, credential or
session material, raw probe data, signatures, request fingerprints, and idempotency keys.

## Consequences

### Positive

- Atlas can prove bounded configuration/connectivity posture without becoming a secret or network
  execution path.
- Evidence provenance, freshness, runner identity, scope, and read-only authority are explicit.
- Connector enablement, runtime trust, capability policy, and invocation remain independent.

### Costs

- A separately governed isolated probe producer and restricted evidence store are required.
- Probe evidence must be refreshed after configuration, credential, target, or policy changes.
- Live health, capability enablement, runtime trust, and invocation remain pending.

## Rejected Alternatives

### Connect From The Web/API Service

Rejected because it would combine caller input, secret resolution, network reachability, and
lifecycle promotion in one high-risk boundary.

### Accept Raw Endpoint Or Probe Output

Rejected because target coordinates and raw output may expose credentials, topology, vendor data,
or attacker-controlled content to audit, logs, persistence, and LLM contexts.

### Treat Reachability As Enablement

Rejected because reachability does not establish allowed capabilities, runtime trust, execution
authorization, deployment approval, or change safety.

## Follow-Up

The next independent lifecycle contracts cover capability governance and enablement, runtime trust,
health evidence, and governed invocation.
