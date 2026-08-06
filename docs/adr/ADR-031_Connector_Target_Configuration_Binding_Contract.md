# ADR-031: Connector Target and Configuration Binding Contract

**Status:** Accepted
**Date:** 2026-08-06
**Decision Owners:** Product Owner, Solution Architecture, Security Architecture

## Context

ADR-030 creates a connector instance identity in `disabled_unconfigured` state. The record has exact
installed-package lineage and accountable ownership, but intentionally contains no target,
endpoint, certificate trust, route, proxy, credential, capability, health, runtime, or execution
configuration.

Target configuration introduces material SSRF, tenant-escape, trust-substitution, and credential
exposure risks. A caller-provided URL, IP address, certificate, proxy, or route cannot be accepted as
authoritative configuration. Target and network facts must instead come from separately governed,
signed inventory evidence.

## Decision

Atlas will bind an instance to one exact immutable target profile and one exact immutable
configuration policy. The resulting version-one binding advances the effective instance state only
to `disabled_target_configured` and grants eligibility for later credential governance.

### Request Contract

The request contains only exact instance-record ID/digest, package digest, target-profile ID/digest,
configuration-policy ID/digest, bounded purpose, explicit no-runtime-authority acknowledgement,
idempotency, and correlation. The caller cannot provide endpoint, host, IP, port, URL, protocol,
certificate, trust material, route, proxy, site, target identity, product, secret, credential,
capability, schedule, health result, runtime option, command, enablement, or deployment data.

### Target Profile

An immutable signed target profile is owned by trusted inventory governance and contains:

- organization, environment, site, and opaque target identity;
- target type, vendor/product, and bounded version evidence;
- normalized HTTPS endpoint origin using an allowlisted DNS suffix and port;
- certificate-trust profile reference;
- network-route and optional proxy profile references;
- allowed connector identities and release constraints;
- classification, issue/expiry time, signer, signature status, and canonical digest.

Profiles reject userinfo, paths beyond `/`, query, fragment, wildcard host, IP literals, loopback,
link-local, multicast, metadata-service destinations, public suffix escape, non-HTTPS transport,
and caller-selected trust. No network connection or DNS resolution occurs during binding.

### Configuration Policy

An immutable signed policy fixes source schemas and age, assurance, allowed target types/products,
allowed endpoint suffixes and ports, required trust/route/proxy profiles, target-profile signer,
separation identities, output state, and record schema. Customer input cannot weaken platform
controls.

### Source And Separation

The service reloads and verifies the current instance record and complete package/installation
lineage through the owning service. It independently verifies the current target profile and policy,
all exact digests, scope, compatibility, freshness, and no-later-authority state.

Only a dedicated exact-tenant MFA human with C3 permission may bind configuration. The actor must be
distinct from every upstream package, installation, instance, policy, target-profile, workload,
publisher, installer, and custody actor. AI, service, shared, wrong-scope, and insufficient-assurance
identities fail closed without discovery.

### Resulting Authority

A valid immutable binding sets only `target_configured` and
`eligible_for_credential_governance`, with effective state `disabled_target_configured`. It keeps
`credentials_resolved`, `connector_enabled`, `runtime_trust_granted`, `execution_authorized`,
`deployment_approved`, and `infrastructure_mutation_performed` false.

The record stores target/profile identity and digest evidence but not endpoint origin, certificate
material, proxy address, route details, raw inventory, secrets, or credentials. Later authorized
components must reload the exact profile by ID and digest.

### Persistence, Audit, And API

Bindings are immutable, one-to-one per instance for configuration version one, deterministic,
idempotent, concurrency-safe, and equivalent in memory/PostgreSQL. Intent and completion audit must
succeed before persistence. APIs use dedicated default-deny RBAC, exact scope, MFA, browser session,
CSRF on mutation, strict schemas, no-store responses, safe errors, and minimized evidence.

Audit and web output exclude endpoint, host, port, trust material, route/proxy details, internal
profile payload, signatures, keys, credentials, secrets, request fingerprints, and idempotency keys.

## Consequences

### Positive

- Callers cannot turn connector configuration into an SSRF or trust-substitution channel.
- Target identity, network path, and package compatibility are independently governed and auditable.
- Sensitive endpoint details remain outside model-visible and ordinary web evidence.
- Credential assignment and runtime activation remain separate reviewable boundaries.

### Costs

- Trusted target-profile inventory and signing are required.
- Profile lifecycle, rotation, revocation, and configuration versioning require later work.
- Credential assignment, health validation, capability enablement, and runtime trust remain pending.

## Rejected Alternatives

### Accept Raw Endpoint Configuration

Rejected because input validation alone cannot establish target ownership, route authorization,
certificate trust, or tenant scope.

### Resolve DNS or Test Connectivity During Binding

Rejected because it introduces network side effects and time-of-check/time-of-use ambiguity before
credentials and isolated runtime controls exist.

### Bind Credentials with the Target

Rejected because secret-reference access has distinct identity, classification, rotation, and audit
requirements.

### Enable After Configuration

Rejected because complete credentials, health validation, capability policy, runtime trust, and
additional human governance are still absent.

## Follow-Up

The next independent lifecycle contracts cover credential-reference assignment, configuration
validation, capability enablement, runtime trust, and governed invocation.
