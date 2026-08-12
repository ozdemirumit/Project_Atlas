# ADR-121: Connector Upgrade Onboarding-Policy Provenance Diagnostics

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-12 |
| Owners | MCP Platform Architecture, Security Architecture, Identity Architecture |
| Related | ATLAS-003, ATLAS-020, ATLAS-025, ATLAS-031, ATLAS-032, ATLAS-047, ADR-118, ADR-119, ADR-120 |

## Context

ADR-120 makes policy provenance mandatory for signing-provider onboarding readiness. Its fail-closed
service contract intentionally returns no readiness dossier when policy, attestation, trust-key or
cryptographic evidence is unavailable or invalid. That protects the decision boundary, but leaves an
operator with only a general failure and no safe way to identify the evidence owner that must act.

Atlas must explain the blocked posture without disclosing raw signatures, public or private key
material, credentials, endpoints, provider parameters or mutable trust controls.

## Decision

Atlas will expose a separate, read-only, exact-scope policy-provenance diagnostic. A single internal
evaluation engine will produce both the diagnostic and the verified evidence consumed by onboarding
readiness, preventing the diagnostic and decision paths from applying different trust rules.

The diagnostic contains five ordered checks:

1. active policy integrity and lifecycle;
2. active attestation integrity and lifecycle;
3. exact policy-to-attestation binding;
4. current issuer trust-key integrity and lifecycle;
5. cryptographic signature verification.

Each check is `verified`, `blocked` or `unavailable` and carries a stable reason code. Later checks are
reported as unavailable when an earlier prerequisite prevents safe evaluation. Safe policy,
attestation and trust-key identifiers or canonical digests may be returned only after their own
integrity and scope checks pass.

The diagnostic has dedicated default-deny C1 authorization, a no-store API response and a required
audit record. Audit failure blocks the response. It is computed on read and does not persist or alter
trust state.

## Safety Boundary

A verified diagnostic proves only that the current onboarding-policy snapshot has acceptable
provenance at the recorded evidence time. A blocked diagnostic does not relax readiness. Neither
state grants policy-authoring, trust-store management, provider configuration, key management,
receipt signing, upgrade approval, execution or infrastructure-mutation authority.

## Consequences

- Operators can distinguish missing inputs from invalid, stale, revoked or unverified evidence.
- Production remains fail-closed with empty sources and the unavailable verifier.
- Diagnostic and readiness decisions share one evaluator and stable failure semantics.
- Production trust-store and verifier selection remains an external deployment decision.

## Validation

- Verified, missing, expired, future, ambiguous, binding-invalid, disabled, revoked,
  integrity-invalid and signature-unverified service tests
- Dedicated RBAC, required-audit failure, no-store and exact-schema API tests
- Frontend runtime-contract and read-only blocked/verified presentation tests
- Complete backend/frontend regression, one Alembic head, production build and responsive live UI
