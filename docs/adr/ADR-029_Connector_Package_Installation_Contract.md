# ADR-029: Connector Package Installation Contract

- Status: Accepted
- Date: 2026-08-06
- Decision owners: Product Owner, Solution Architecture, Security Architecture
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-020, ATLAS-021, ATLAS-023,
  ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-047, ATLAS-050,
  ATLAS-051, ATLAS-053, ATLAS-055, ATLAS-056, ADR-009 through ADR-028

## Context

ADR-028 admits one exact published package into the governed connector catalog. Its immutable
registration record sets `connector_registered` and `eligible_for_installation_governance`, but it
intentionally creates no installed package, connector instance, target configuration, credential
access, enablement, runtime trust, execution, deployment, or infrastructure authority.

Installation is the next package lifecycle boundary. It places the exact registered package into a
policy-selected, immutable, non-executable installation store from which a later independently
governed instance lifecycle may be prepared. Installation must not be confused with importing or
executing package code, resolving dependencies, running package hooks, creating an instance, or
connecting to infrastructure.

The existing development connector registry has an `INSTALLED` lifecycle value, but it accepts
caller-selected manifests and mutates an in-memory package record. That early framework remains a
simulator aid and is not a production installation authority.

## Decision

### 1. Exact Human Request

Only a dedicated, authenticated, exact-tenant human with MFA and the installation permission may
request installation. The request contains only:

- exact package-registration record ID and canonical digest;
- exact package digest;
- signed installation-policy ID and canonical digest;
- a bounded operational purpose;
- acknowledgement that installation grants no instance, target, secret, runtime, enablement,
  execution, deployment, or infrastructure-mutation authority;
- idempotency and correlation metadata.

The request cannot contain package bytes, manifest content, registry or installation coordinates,
filesystem paths, image names, dependency sources, install commands, hooks, environment variables,
configuration, endpoints, targets, secret references, capability overrides, lifecycle overrides,
enablement, execution, or deployment controls. Unknown fields fail schema validation.

### 2. Current Registration and Publication Evidence

The service independently reloads the registration record and its current publication source. It
revalidates canonical integrity, exact tenant and environment, package, connector, release,
publisher, provenance, manifest, policy, and complete upstream lineage. The record must still be
registered, eligible for installation governance, unblocked, and within the installation policy's
freshness limits.

The caller cannot replace persisted evidence or select a weaker source, registry, reader, installer,
store, package format, or policy.

### 3. Exact Artifact Recovery and Manifest Reconciliation

A policy-selected registry reader recovers the artifact only from the immutable reference already
bound to the current publication receipt. The service checks exact byte length and SHA-256 before
installation. Production has no caller-supplied, filesystem, public-network, or development fallback.

The bounded non-executing inspector from ADR-028 reopens the exact artifact. The resulting manifest
and digest must exactly match the immutable registration snapshot. Package code is never imported,
compiled, initialized, or executed during this reconciliation.

### 4. Policy-Selected Non-Executing Installer

Installation is performed through an isolated installer port chosen by signed policy. The installer:

- accepts only the verified immutable package bytes and exact governed identities;
- writes create-if-absent under the package digest;
- uses a fixed internal installation-store profile and artifact-reference schema;
- verifies returned digest and byte length;
- never extracts executable content into an active runtime;
- never runs package metadata hooks, shell commands, or package code;
- never resolves or downloads dependencies;
- never contacts public networks, infrastructure targets, secret systems, or model endpoints;
- returns an opaque immutable installation reference that is retained only as internal evidence.

Identical replay is safe. Existing content with different identity, digest, size, reference schema,
or store binding fails closed. Delete, overwrite, tag, promote, activate, or mutable-latest behavior
is not part of this contract.

### 5. Signed Installation Policy

The immutable policy fixes at least:

- accepted registration, publication, manifest, package, and installation schemas;
- maximum registration age and package size;
- required authentication assurance;
- registry profile, reader workload, and artifact-reference schema;
- installer profile, installer workload, installation custodian, and installation-store profile;
- installation artifact-reference and receipt schemas;
- accepted SDK profiles, source statuses, and capability classes;
- separation-of-duty identities and policy validity;
- safe disclosure and audit behavior.

Customer configuration may tighten but cannot weaken these controls.

### 6. Immutable Installation Receipt

One successful installation creates one immutable receipt containing:

- exact registration, publication, signing, approval, validation, acquisition, package, connector,
  release, publisher, provenance, and manifest bindings;
- exact registration and installation policy identities and canonical digests;
- installer, custodian, store-profile, artifact schema, digest, and size evidence;
- installer human, purpose, timestamp, version, and canonical receipt digest;
- explicit authority-state booleans.

The internal receipt may retain the opaque installation reference for later trusted platform
services. Public APIs, audit events, logs, model context, and ordinary UI never expose that reference,
registry coordinates, filesystem paths, package bytes, raw manifests, signatures, keys, request
fingerprints, idempotency keys, configuration names, or secret-reference names.

Receipts are one-to-one with the exact registration, deterministic, idempotent, concurrency-safe,
append-only, and equivalent in memory and PostgreSQL. Package/release/store conflicts fail closed.

### 7. Authority Boundary

A valid receipt sets only:

- `connector_registered = true`;
- `package_installed = true`; and
- `eligible_for_instance_governance = true`.

It does not create or configure a connector instance, assign a target or credential, enable a
capability, grant runtime trust, authorize execution, approve deployment, invoke package code,
contact infrastructure, or mutate infrastructure. AI and service identities cannot request
installation. Every later stage requires a separate permission, policy, evidence set, audit trail,
and accountable human decision.

### 8. Audit Ordering and Separation of Duties

A required installation-intent audit succeeds before artifact recovery or installer invocation. A
required completion audit succeeds after returned evidence is verified and before receipt
persistence. Audit failure stops progress and cannot fabricate installation state.

The installer human is distinct from every upstream validation, approval, publisher, signing,
registry, registration, policy, reader, installer-workload, and custody actor. Shared, AI, service,
wrong-tenant, wrong-environment, and insufficient-assurance identities fail closed without resource
discovery.

### 9. API and Web Boundary

Create/read APIs use strict extra-field rejection, exact scope, dedicated RBAC, browser-session CSRF,
MFA, bounded identifiers, no-store responses, safe errors, and non-disclosing lookup behavior.

The web view may show bounded lineage, package/manifest digest, connector/release, policy, store
profile, installer, time, and explicit no-authority state. It provides no path, package, dependency,
instance, target, secret, enablement, execution, or deployment input or control.

## Consequences

### Positive

- Installation cannot silently replace or reinterpret approved package evidence.
- Package custody advances without granting runtime or infrastructure authority.
- Restricted-network and supply-chain controls are deterministic and auditable.
- Later instance creation and enablement receive one exact immutable installation anchor.

### Costs

- A trusted installation store and isolated installer adapter are required in production.
- Immutable installation evidence adds persistence and operational retention cost.
- Instance creation, configuration, enablement, runtime trust, and execution remain separate work.

## Rejected Alternatives

### Registration and Installation as One Operation

Rejected because catalog admission and installation custody have different actors, policies, effects,
audit ordering, and rollback concerns.

### Run Native Package Install Hooks

Rejected because arbitrary build/install hooks execute untrusted code and can resolve dependencies,
contact networks, read secrets, or mutate the host.

### Caller-Selected Installation Path or Runner

Rejected because it enables destination substitution, path traversal, tenant escape, and policy
bypass. Policy selects the installer and store profile; internal adapters own coordinates.

### Install and Enable in One Operation

Rejected because enablement requires instance configuration, exact target and credential bindings,
runtime trust, health verification, and additional human governance.

## Follow-Up

The next independent lifecycle contracts cover connector instance creation, target/configuration
binding, secret-reference assignment, capability enablement, runtime trust, and governed invocation.
