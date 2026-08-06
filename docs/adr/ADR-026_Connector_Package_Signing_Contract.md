# ADR-026: Connector Package Signing Contract

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-06 |
| Owners | MCP Platform Architecture, Security Architecture |
| Related | ATLAS-003, ATLAS-020, ATLAS-021, ATLAS-022, ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-047, ADR-009, ADR-024, ADR-025 |

## Context

ADR-025 independently verifies publisher identity, ownership, support responsibility, and release
provenance for one exact approved package. Its verified result sets only
`eligible_for_package_signing_governance=true`; it creates no signature and exposes no key.

Atlas needs a separately governed signing boundary that can issue integrity evidence for the exact
package without placing private key material in the API, model, workflow, database, package builder,
or connector process. Signing is artifact governance, not installation or runtime authorization.

## Decision

Atlas will create one immutable package-signing receipt from one exact current verified ADR-025
report and one immutable signed signing-policy snapshot. The service constructs a canonical signing
envelope and invokes a policy-selected signer through a bounded port. The caller cannot select a
signer, key, algorithm, signature, registry, target, or lifecycle result.

Production signer implementations use an external KMS, HSM, or equivalent isolated signing service.
The first local profile may use a clearly named non-production deterministic HMAC signer only for
contract validation. Production configuration has no fallback to that signer or policy.

## Canonical Signing Envelope

The immutable envelope binds at least:

- envelope schema and canonicalization version;
- exact publisher-attestation report ID/digest and verification time;
- exact approval request/decision IDs and digests;
- exact package, publisher, connector, release, and provenance identity;
- exact publisher claim and attestation-policy IDs/digests;
- signing-policy ID/digest/version and selected signer profile;
- organization, environment, requested purpose, correlation-safe request identity, and creation time;
- explicit declarations that signing does not register, install, enable, execute, or deploy.

Package bytes, private or symmetric key material, credentials, target coordinates, commands,
payloads, model context, raw evidence, and unrestricted contact data are excluded.

## Signing Policy

One immutable, signed, verified, unexpired, tenant-scoped policy fixes accepted attestation schema,
maximum evidence age, minimum human assurance, signer profile, key ID, algorithm, envelope schema,
signature lifetime, actor separation, required no-authority declarations, and receipt schema.

Customer policy may strengthen but cannot weaken exact binding, key isolation, signer allowlisting,
separation, audit, no-authority, deterministic replay, or fail-closed behavior.

## Identity And Separation

Only an exact-tenant, multi-factor human with dedicated request permission may request signing. The
requester must be distinct from every acquisition, validation, review, approval, publisher claim,
attestation verification, and policy-signing actor in the lineage. The signer is a dedicated
workload identity selected by policy and cannot be supplied by the requester.

The signing-policy signer, package-signing requester, signing workload, key custodian, publisher,
claim issuer, approver, and attestation verifier remain distinguishable identities. AI, anonymous,
shared, wrong-scope, disabled, insufficient-assurance, or ineligible identities fail closed.

## Signer Port

The signer receives only the canonical envelope bytes, envelope digest, policy-selected key ID,
algorithm, signer profile, tenant/environment scope, expiry, and idempotency reference. It returns a
bounded signature result containing signer workload identity, key ID, algorithm, signature bytes,
signature digest, issue/expiry time, and verification state.

The signer never returns key material. Atlas verifies the result binding, algorithm, key/profile,
identity, timestamps, signature bounds, and deterministic replay before accepting it. Signer timeout,
unavailability, mismatch, invalid verification, or ambiguous outcome fails closed.

## Audit, Persistence, And Replay

A required audit intent succeeds before signer invocation. A required completion audit succeeds
after result verification and before receipt persistence. Signatures are deterministic for the exact
envelope and idempotency reference in the first profile, so retry after partial failure cannot sign
different content.

Receipts are immutable, one-to-one with exact attestation reports, idempotent, concurrency-safe,
audit-before-persist, and equivalent in memory and PostgreSQL. Persistence stores the bounded
signature result for later internal registry verification but public API responses expose only safe
identity, algorithm, key reference, signature digest, timestamps, and verification state.

## Lifecycle Effect

A valid receipt sets only:

- `publisher_attested=true`;
- `package_signed=true`; and
- `eligible_for_registry_governance=true`.

It keeps `connector_registered`, `connector_installed`, `connector_enabled`, `target_configured`,
`credentials_resolved`, `runtime_trust_granted`, `execution_authorized`, `deployment_approved`, and
`infrastructure_mutation_performed` false. It creates no registry entry, installation package,
runtime token, target reference, credential handle, command, deployment approval, or mutation.

## API And Web Contract

Strict create/read APIs require dedicated default-deny RBAC, browser sessions, CSRF on mutation,
exact tenant scope, MFA, acknowledgement, correlation, bounded schemas, safe errors, no-store, and
non-disclosing lookup. Responses never expose signature bytes or key material.

The web view shows exact attestation/package/publisher/policy/envelope/signer/signature-digest
evidence and explicit no-authority scope. It contains no registry, install, enable, target, secret,
execution, or deployment control.

## Consequences

- Package integrity is signed only after independent validation, approval, and publisher attestation.
- Key custody remains outside ordinary Atlas services and user input.
- Signing cannot silently become registry publication or runtime trust.
- Registry publication requires a later independent ADR and current verification.

## Rejected Alternatives

- Let the package builder sign: rejected because generated code cannot establish its own trust.
- Accept a caller-supplied signature or key: rejected because it bypasses policy-selected custody.
- Store private keys in Atlas configuration or database: rejected because key isolation is mandatory.
- Publish automatically after signing: rejected because registry governance remains independent.
- Treat a digest as a signature: rejected because integrity identity alone does not prove signer
  authorization or key possession.

## Validation

- Exact attestation, approval, package, publisher, claim, provenance, policy, envelope, signer,
  algorithm, key, tenant, environment, timestamp, signature, and digest binding tests
- Complete actor separation, MFA, scope, no-discovery, signer failure, tamper, replay, concurrency,
  partial-failure, and fail-closed tests
- Required audit intent before signer and completion audit before persistence
- Immutable, idempotent, memory/PostgreSQL, minimized API, CSRF, no-store, and Alembic-head tests
- Proof that keys/signature bytes do not reach API/log/model and that no result registers, installs,
  enables, accesses targets or secrets, executes, deploys, or mutates infrastructure
- Web, desktop, 390-pixel mobile, browser-log, live HTTP, and GitHub CI validation
