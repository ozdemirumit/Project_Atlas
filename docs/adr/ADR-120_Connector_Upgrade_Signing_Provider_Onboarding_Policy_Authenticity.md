# ADR-120: Connector Upgrade Signing-Provider Onboarding Policy Authenticity

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-12 |
| Owners | MCP Platform Architecture, Security Architecture, Identity Architecture |
| Related | ATLAS-003, ATLAS-020, ATLAS-025, ATLAS-031, ATLAS-032, ATLAS-047, ADR-116, ADR-118, ADR-119 |

## Context

ADR-119 provides exact-scope, expiring and canonical-digest-protected onboarding policies. Canonical
integrity detects accidental or partial mutation, but does not prove that the named issuer authorized
the snapshot when an attacker can replace both payload and digest.

The workspace has no approved production issuer trust store, signing key, cryptographic algorithm or
secret/public-key delivery mechanism. Atlas must not invent any of those deployment inputs.

## Decision

Atlas will require independently supplied policy attestation, issuer trust and cryptographic
verification ports before an onboarding policy can produce a readiness dossier.

The immutable attestation binds policy ID, version and digest, exact organization/environment,
issuer, trust-key ID/version, algorithm and issue/expiry time. Its signature digest and canonical
digest are verified before use. The raw signature remains inside the backend verification boundary
and is never returned by the readiness API.

An independently supplied trust key binds exact scope, issuer, key ID/version, algorithm, lifecycle
state and validity window. Exactly one active attestation and one active matching trust key are
required. Missing, expired, future, ambiguous, scope-mismatched, binding-mismatched,
integrity-invalid, revoked, disabled or cryptographically unverified provenance fails closed with
stable codes.

Production receives empty attestation and trust sources plus an unavailable verifier. A deterministic
non-production HMAC verifier exists only for local tests and development UI inspection. It is not a
production trust mechanism and cannot approve the non-production infrastructure signing provider.

## API And UI

The readiness dossier exposes only policy provenance status, attestation ID/digest, issuer, trust-key
reference and algorithm. It exposes no signature, key material, endpoint, credential, token or
provider configuration. The Connector inventory presents this evidence read-only.

## Safety Boundary

Verified provenance proves only that the active policy snapshot matches an attestation accepted by
the configured verifier. It does not grant policy-authoring, issuer-trust management, key-management,
provider configuration, receipt signing, upgrade approval, execution or infrastructure-mutation
authority. All such authority remains false.

## Consequences

- Onboarding readiness can no longer trust a self-asserted issuer field or digest alone.
- Production remains fail-closed until security owners configure reviewed trust and verification
  adapters.
- Verifier technology and production key custody can be selected later without changing the
  provider-neutral readiness API.

## Validation

- Missing, stale, ambiguous, wrong-scope, binding-invalid, trust-invalid and signature-unverified
  service tests
- Exact API schema and frontend runtime-contract tests with signature/key-material exclusion
- Complete backend/frontend regression, one Alembic head, production build and responsive live UI
