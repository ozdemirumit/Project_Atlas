# ADR-028: Connector Package Registration Contract

**Status:** Accepted  
**Date:** 2026-08-06  
**Decision Owners:** Product Owner, Solution Architecture, Security Architecture

## Context

ADR-027 permits one exact signed package to be copied into immutable internal registry custody. Its
receipt intentionally grants no connector registration, installation, configuration, enablement,
runtime trust, target access, execution, deployment, or infrastructure mutation authority.

The original foundation registry accepts a caller-supplied manifest and stores only an in-memory
package record. That contract remains useful for simulator and early framework tests, but it is not
an acceptable production registration boundary. A caller must not be able to replace the manifest,
capability declarations, risk classes, registry location, or package bytes after the governed
validation, approval, attestation, signing, and publication chain has completed.

Registration must therefore derive its catalog evidence from the exact immutable artifact already
published by IMP-071 and must create a separately governed, durable record. Registration is catalog
admission only. It is not installation and cannot create an instance or runtime authority.

## Decision

Atlas will implement a dedicated governed connector package registration boundary with the
following rules.

### 1. Minimal Request Contract

Only an authenticated, exact-tenant MFA human with the dedicated registration permission may submit:

- exact registry-publication receipt ID and canonical digest;
- exact package digest;
- signed registration-policy ID and canonical digest;
- a bounded operational purpose;
- acknowledgement that registration grants no installation or runtime authority;
- idempotency and correlation metadata.

The request cannot contain package bytes, registry coordinates, manifest content, capability
declarations, risk classes, permissions, target products, network destinations, lifecycle state,
approval outcome, installation options, configuration, endpoints, secret references, commands, or
execution controls. Unknown fields fail schema validation.

### 2. Current Publication Evidence

The registration service reloads the immutable IMP-071 receipt by ID and independently verifies:

- canonical receipt integrity and exact caller-supplied receipt/package digests;
- exact organization and environment scope;
- successful publisher attestation, signing, cryptographic reverification, and publication;
- publication integrity and registration-governance eligibility;
- no promotion block and no existing registration or later lifecycle authority;
- source policy, registry profile, artifact-reference schema, publisher workload, and actor lineage;
- registration-policy signature, scope, validity, schema, and digest.

Missing, stale, changed, ambiguous, cross-tenant, or tampered evidence fails closed without
disclosing whether an out-of-scope record exists.

### 3. Registry Artifact Recovery

A policy-selected internal-registry reader recovers the artifact using only the stored publication
result. The caller cannot select a registry, path, tag, version alias, or byte range.

The reader must return the exact immutable artifact or fail. Atlas compares byte length and SHA-256
to the publication receipt before inspection. Package bytes never enter API responses, logs, audit
metadata, model context, workflow state, or registration persistence. Production has no local
filesystem or in-memory fallback when an approved registry reader is unavailable.

### 4. Bounded Manifest Inspection

Atlas inspects the artifact without importing or executing package code. The first contract accepts
only the deterministic ZIP format already validated by the package pipeline and one UTF-8 JSON
manifest at `atlas-connector.yaml`. Despite the historical filename, no YAML parser or active tag is
used.

The inspector rejects:

- encrypted, compressed, duplicate, absolute, traversing, backslash, symlink, device, or excessive
  archive entries;
- missing, duplicate, oversized, malformed, non-object, or extra-field manifest content;
- unsupported manifest schema, status, SDK profile, capability class, or excessive declarations;
- embedded secret values, runtime trust, execution authority, or mutable lifecycle assertions;
- identity, release, package, capability, permission, target-product, or network-destination
  inconsistency with the exact governed evidence chain.

The signed registration policy fixes all accepted schemas, archive and manifest bounds, manifest
path, SDK profile, accepted source states, capability classes, declaration limits, registry profile,
reader workload, record schema, assurance, evidence age, and separation requirements. Customer
configuration cannot weaken mandatory platform controls.

### 5. Immutable Registration Record

A successful registration creates one immutable record containing:

- exact publication, signing, approval, final-validation, acquisition, package, publisher,
  connector, release, and provenance bindings;
- registration policy identity, version, and canonical digest;
- manifest digest, schema, SDK profile, source status, and bounded declaration snapshots;
- stable capability IDs, classes, and required permissions derived from the artifact;
- registrar identity and timestamp;
- explicit no-authority declarations and canonical record digest.

The record is one-to-one with the publication receipt, deterministic, idempotent, concurrency-safe,
audit-before-persist, and equivalent in memory and PostgreSQL. Historical records are never updated
in place. A package/version collision with a different digest fails closed.

### 6. Authority Boundary

A valid record sets only:

- `connector_registered = true`; and
- `eligible_for_installation_governance = true`.

It does not install a package, create or configure an instance, select a target, resolve credentials,
enable capabilities, grant runtime trust, authorize execution, approve deployment, invoke package
code, contact infrastructure, or mutate infrastructure. AI and service identities cannot request
registration. Later lifecycle stages require independent contracts, permissions, policies, evidence,
and human decisions.

### 7. Separation of Duties and Audit

The registrar must be distinct from every upstream requester, validator, approver, claim issuer,
publisher, signer, policy signer, key custodian, verifier workload, registry publisher, registry
custodian, and registry reader workload.

Required audit intent succeeds before registry artifact access or manifest inspection. Required
completion audit succeeds after all returned evidence has been verified and before persistence.
Audit failure cannot fabricate a registration record. Audit metadata contains only stable IDs,
digests, policy references, result codes, and bounded counts.

### 8. API and Web Disclosure

Create and read APIs use strict no-store responses, CSRF protection for mutation, dedicated RBAC,
bounded schemas, safe error mapping, exact-scope enforcement, and non-disclosing lookup behavior.

The web view may show bounded registration evidence, source identity, package digest, manifest
schema/status, capability declarations, target-product declarations, policy, registrar, timestamp,
and explicit no-authority state. It never exposes package bytes, signature values, key material,
custody paths, registry coordinates, request fingerprints, idempotency keys, raw manifest content,
configuration fields, or secret-reference names.

## Consequences

- Registration is traceable to one exact immutable artifact rather than caller-controlled metadata.
- The existing foundation registry remains isolated from the production registration API until a
  later migration deliberately consumes governed registration records.
- Artifact inspection is deterministic and non-executing, reducing parser and supply-chain risk.
- Installation and runtime work remain explicit future vertical slices instead of accidental side
  effects of catalog registration.
- Production deployment requires an approved internal-registry reader implementation and signed
  registration policy; absence fails closed.

## Rejected Alternatives

### Accept a Manifest in the Registration Request

Rejected because it permits post-validation substitution and breaks exact package lineage.

### Reuse the Foundation `register_package` Method as the Production API

Rejected because it accepts caller-supplied domain objects, has no durable governed receipt, and
combines validation assumptions that predate the controlled package pipeline.

### Import the Connector to Discover Capabilities

Rejected because registration must not execute untrusted package code or grant runtime authority.

### Treat Registry Publication as Registration

Rejected because artifact custody and catalog admission are separate trust decisions with different
policies, actors, evidence, and audit obligations.

### Register and Install in One Operation

Rejected because installation introduces filesystem, dependency, instance, target, secret, and
runtime effects that require an independent human-governed lifecycle boundary.
