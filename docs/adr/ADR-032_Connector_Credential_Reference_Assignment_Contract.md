# ADR-032: Connector Credential-Reference Assignment Contract

**Status:** Accepted
**Date:** 2026-08-06
**Decision Owners:** Product Owner, Solution Architecture, Security Architecture

## Context

ADR-031 binds a disabled connector instance to exact signed target and configuration evidence. The
result is eligible for credential governance but contains no credential reference, secret-store
location, secret value, capability, health, runtime, or execution authority.

Credential metadata can reveal privileged identities, vault structure, rotation state, and target
access. Accepting a caller-provided secret reference or resolving a secret during assignment would
permit tenant escape, credential substitution, and accidental disclosure to web, audit, or model
contexts.

## Decision

Atlas will assign one exact immutable credential profile to one exact target-configured connector
instance under one exact signed assignment policy. Version one advances the effective instance only
to `disabled_credentials_assigned` and grants eligibility for later configuration validation.

### Request Contract

The request contains only exact target-binding ID/digest, package digest, credential-profile
ID/digest, assignment-policy ID/digest, bounded purpose, explicit no-secret-access acknowledgement,
idempotency, and correlation. The caller cannot provide a secret reference, vault path, store name,
credential value, token, key, certificate, username, password, endpoint, target, capability, runtime
option, command, lifecycle state, enablement, execution, or deployment data.

### Credential Profile

An immutable signed credential profile is owned by trusted credential governance and contains:

- organization, environment, site, target-profile, and target identity bindings;
- an internal opaque secret-reference identifier and approved secret-store profile reference;
- credential class, authentication method, vendor role, and read/write privilege classification;
- allowed connector identities, release versions, target products, and target types;
- rotation, expiry, revocation, issue time, signer, signature state, and canonical digest evidence.

Profiles reject inline secret material, URI/userinfo credentials, unmanaged stores, unbounded target
scope, unsupported authentication, expired or revoked references, write-capable privilege where the
policy permits only read access, and cross-tenant or cross-target reuse.

The internal secret-reference identifier, store path, version selector, secret value, token, key,
certificate, username, and password never enter the request, response, audit event, log, model
context, or ordinary persistence record.

### Assignment Policy

An immutable signed policy fixes source schemas and age, assurance, allowed credential classes and
authentication methods, maximum privilege, allowed secret-store profiles, required rotation and
expiry posture, credential-profile signer, separation identities, output state, and record schema.
Customer input cannot weaken these controls.

### Source And Separation

The service reloads and verifies the current target-configuration binding and its complete package,
installation, instance, target-profile, and configuration-policy lineage through owning services.
It independently verifies the current credential profile and assignment policy, exact digests,
scope, compatibility, freshness, rotation/revocation posture, and no-later-authority state.

Only a dedicated exact-tenant MFA human with C3 permission may assign a credential profile. The
actor must be distinct from every upstream package, installation, instance, target, policy,
credential-profile, workload, publisher, installer, and custody actor. AI, service, shared,
wrong-scope, and insufficient-assurance identities fail closed without discovery.

### Resulting Authority

A valid immutable assignment sets only `credential_references_assigned` and
`eligible_for_configuration_validation`, with effective state `disabled_credentials_assigned`. It
keeps `credentials_resolved`, `connector_enabled`, `runtime_trust_granted`,
`execution_authorized`, `deployment_approved`, and `infrastructure_mutation_performed` false.

The record stores credential-profile identity/digest, classification, authentication method,
privilege class, rotation/expiry posture, and policy evidence. It stores no internal secret
reference, vault/store path, version selector, or secret material. Later isolated runtime
components must reload the exact profile and resolve its internal reference only for an authorized
invocation.

### No Secret Or Network Access

Assignment performs no secret-store call, credential resolution, token exchange, authentication,
target connection, DNS lookup, package execution, health check, or capability invocation. Profile
verification is metadata-only and deterministic.

### Persistence, Audit, And API

Assignments are immutable, one-to-one per target binding for version one, deterministic,
idempotent, concurrency-safe, and equivalent in memory/PostgreSQL. Intent and completion audit must
succeed before persistence. APIs use dedicated default-deny RBAC, exact scope, MFA, browser session,
CSRF on mutation, strict schemas, no-store responses, safe errors, and minimized evidence.

Audit and web output exclude internal secret-reference identifiers, secret-store paths and profile
internals, secret values, tokens, keys, certificates, usernames, passwords, target coordinates,
signatures, request fingerprints, and idempotency keys.

## Consequences

### Positive

- Callers and AI cannot inject, read, or infer secret-store locations or credential values.
- Credential suitability, least privilege, rotation, and target scope are independently governed.
- Rotation or revocation can replace the governed profile without rebuilding connector packages.
- Configuration validation, capability enablement, and runtime secret resolution remain separate.

### Costs

- A trusted credential-profile catalog and signed policy lifecycle are required.
- Rotation, revocation, target scope, and least-privilege metadata must remain current.
- Configuration validation, health checks, enablement, runtime trust, and invocation remain pending.

## Rejected Alternatives

### Accept A Caller-Provided Secret Reference

Rejected because an opaque string alone cannot establish tenant ownership, target scope, store
governance, privilege, rotation, or revocation posture.

### Accept Or Store Secret Values

Rejected because secret values must never enter Atlas web, API, audit, log, model, or ordinary
persistence contexts.

### Resolve The Secret During Assignment

Rejected because assignment needs only governed metadata and must not create secret-store or target
side effects before an authorized isolated invocation exists.

### Enable The Connector After Assignment

Rejected because configuration validation, health evidence, capability policy, runtime trust, and
additional human governance are still absent.

## Follow-Up

The next independent lifecycle contracts cover configuration/connectivity validation, capability
enablement, runtime trust, and governed invocation.
