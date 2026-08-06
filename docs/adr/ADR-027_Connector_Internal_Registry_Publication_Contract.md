# ADR-027: Connector Internal Registry Publication Contract

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-06 |
| Owners | MCP Platform Architecture, Security Architecture |
| Related | ATLAS-003, ATLAS-020, ATLAS-021, ATLAS-022, ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-047, ADR-009, ADR-025, ADR-026 |

## Context

ADR-026 signs one exact approved and publisher-attested connector package. Its receipt sets only
`eligible_for_registry_governance=true`; it does not copy package bytes to a registry, register a
connector, install code, configure an instance, or grant runtime authority.

Atlas needs a separately governed boundary that republishes the exact signed package from immutable
quarantine custody into a policy-selected internal registry. Publication is supply-chain custody,
not connector registration or deployment.

## Decision

Atlas will create one immutable internal-registry publication receipt from one exact, current,
cryptographically reverified ADR-026 signing receipt and one immutable signed publication-policy
snapshot. The service reloads the complete approval and validation lineage, recovers the exact
quarantined package bytes, verifies size and SHA-256 digest, and invokes a policy-selected registry
publisher through a bounded port.

The caller cannot supply a registry address, artifact path, channel, tag, overwrite instruction,
package bytes, signature, verifier, publisher workload, installation target, or lifecycle result.
Production uses an approved internal registry adapter and external signature-verification service.
The first local publisher and verifier are explicitly non-production; production has no fallback.

## Publication Policy

One immutable, signed, verified, unexpired, tenant-scoped policy fixes:

- accepted signing receipt/envelope schemas and maximum signing age;
- required signing profile, key reference, algorithm, and signature-verifier profile;
- internal registry profile, publisher workload, registry custodian, and artifact-reference schema;
- maximum package size, immutable digest addressing, no overwrite, and atomic publication;
- publication receipt schema, actor separation, required audit, and safe disclosure.

Customer policy may strengthen but cannot weaken exact lineage, signature verification, package
integrity, immutable addressing, separation, audit, no-authority, replay, or fail-closed behavior.

## Source And Signature Verification

The service independently reloads and verifies the signing receipt, signing policy, publisher
attestation, approval decision, final validation, acquisition record, and all upstream evidence.
Every tenant, environment, package, approval, publisher, connector, release, provenance, policy,
envelope, signature, and digest binding must remain exact and current.

The registry verifier receives only the bounded signed envelope and policy-selected verification
metadata. It must cryptographically verify the stored signature without returning key material.
Expired, unknown, revoked, mismatched, unverifiable, or malformed signatures fail closed.

The package is read only from governed quarantine custody using the lineage-derived acquisition
record. Its exact size and SHA-256 digest are rechecked before publication. Package bytes never enter
HTTP responses, audit metadata, logs, model context, workflow variables, or database receipts.

## Identity And Separation

Only an exact-tenant, multi-factor human with dedicated publication permission may request the
operation. The requester must be distinct from every upstream acquisition, validation, review,
approval, attestation, signing, policy, key-custody, registry-custody, and publisher actor.

The registry publisher is a dedicated workload selected by policy. AI, anonymous, shared,
wrong-scope, disabled, insufficient-assurance, or ineligible identities fail closed without
revealing whether a protected receipt or package exists.

## Registry Publisher Port

The publisher receives the exact verified package bytes, package digest and size, immutable signing
receipt digest, policy-selected registry profile, artifact-reference schema, publisher workload,
tenant/environment scope, and idempotency reference. It may only perform atomic create-if-absent
publication under the package digest.

The publisher returns a bounded result with registry profile, publisher workload, opaque immutable
artifact reference, package digest and size, publication digest, timestamp, and integrity state. It
cannot overwrite, delete, tag, promote, install, enable, execute, deploy, or contact infrastructure.
An existing identical artifact is reusable; any conflicting or ambiguous result fails closed.

## Audit, Persistence, And Replay

All source and artifact checks complete before the external side effect. A required audit intent
succeeds immediately before registry publication. A required completion audit succeeds after result
verification and before receipt persistence.

Receipts are immutable, one-to-one with exact signing receipts, idempotent, concurrency-safe,
audit-before-persist, and equivalent in memory and PostgreSQL. A retry may reuse only the identical
digest-addressed artifact and exact request fingerprint; it cannot create a different publication.

## Lifecycle Effect

A valid receipt sets only:

- `publisher_attested=true`;
- `package_signed=true`;
- `package_published=true`; and
- `eligible_for_registration_governance=true`.

It keeps `connector_registered`, `connector_installed`, `connector_enabled`, `target_configured`,
`credentials_resolved`, `runtime_trust_granted`, `execution_authorized`, `deployment_approved`, and
`infrastructure_mutation_performed` false. Publication creates no connector instance, runtime token,
target reference, credential handle, command, deployment approval, or infrastructure mutation.

## API And Web Contract

Strict create/read APIs require dedicated default-deny RBAC, browser sessions, CSRF on mutation,
exact tenant scope, MFA, acknowledgement, correlation, bounded schemas, safe errors, no-store, and
non-disclosing lookup. Responses expose only safe registry profile/workload/reference and digest
evidence; package bytes, signature bytes, keys, custody paths, and registry coordinates are hidden.

The web view shows exact signing/package/policy/publication evidence and the explicit no-authority
scope. It contains no registration, install, enable, target, secret, execution, deployment,
overwrite, deletion, tag, channel, or promotion control.

## Consequences

- Only a cryptographically verified, fully governed package can enter the internal registry.
- Registry coordinates, package custody, key custody, and publisher identity remain policy-owned.
- Publication cannot silently become connector registration, installation, or runtime trust.
- Connector registration requires a later independent ADR and current publication verification.

## Rejected Alternatives

- Publish automatically after signing: rejected because publication has an independent side effect
  and custody boundary.
- Accept caller-supplied package bytes or registry coordinates: rejected because this breaks exact
  lineage and target governance.
- Trust a persisted `signature_verified` flag: rejected because publication requires current
  cryptographic reverification.
- Overwrite or retag an existing artifact: rejected because immutable digest addressing is required.
- Treat publication as registration or installation: rejected because these are separate lifecycle
  decisions with different authority and risk.

## Validation

- Exact signing, attestation, approval, final-validation, acquisition, archive, policy, signature,
  registry result, tenant, environment, package, publisher, and digest binding tests
- Complete actor separation, MFA, scope, no-discovery, verifier/publisher failure, tamper, expiry,
  replay, concurrency, partial-failure, immutable conflict, and fail-closed tests
- Required audit intent before publisher and completion audit before persistence
- Immutable, idempotent, memory/PostgreSQL, minimized API, CSRF, no-store, and Alembic-head tests
- Proof that bytes, signature values, keys, custody paths, and registry coordinates do not reach API,
  logs, audit, or model context and that no result registers, installs, enables, executes, deploys,
  accesses targets/secrets, or mutates infrastructure
- Web, desktop, 390-pixel mobile, browser-log, live HTTP, and GitHub CI validation
