# ADR-119: Connector Upgrade Signing-Provider Onboarding Policy Governance

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-12 |
| Owners | MCP Platform Architecture, Security Architecture, Deployment Architecture |
| Related | ATLAS-003, ATLAS-020, ATLAS-025, ATLAS-031, ATLAS-032, ATLAS-047, ADR-116, ADR-117, ADR-118 |

## Context

ADR-118 derives an exact-scope provider-onboarding dossier, but policy identity, production
algorithms and required evidence were application constants. A deployment could not independently
govern those decisions, expire them or prove which rules produced a dossier. Atlas still has no
approved production KMS/HSM selection.

## Decision

Atlas will obtain signing-provider onboarding policy only through an injected policy source. Each
immutable snapshot binds organization and environment scope, permitted provider classes and
algorithms, ordered requirement identifiers, maximum conformance age, issuer, issue/effective/expiry
times and a canonical digest.

The service verifies exact scope, canonical integrity, supported requirement identifiers and the
validity window. Exactly one policy must be active. Missing, expired, future, ambiguous,
scope-mismatched, integrity-invalid or unsupported policy state fails closed with stable reason
codes. Production receives an empty source unless deployment owners explicitly configure a reviewed
adapter. There is no implicit production policy.

A deterministic development snapshot supports tests and local UI inspection. It permits only the
synthetic production-provider test class and production-grade algorithm identifiers; it cannot make
the non-production HMAC adapter ready.

## Dossier Binding

The readiness dossier records policy ID, version, digest, issuer and expiry and evaluates only the
requirements and algorithms selected by the active policy. Conformance freshness is constrained by
both the assessment validity and the policy maximum age. The API accepts no policy, provider,
algorithm, key, endpoint, credential, evidence or approval assertions from callers.

## Safety Boundary

Policy validity and onboarding readiness are evidence claims only. They do not configure a provider,
create or rotate keys, sign receipts, approve upgrades, authorize execution or mutate infrastructure.
All corresponding authority flags remain false.

## Consequences

- Security and deployment owners can govern onboarding criteria independently from service releases.
- Every readiness result identifies the exact current policy that produced it.
- Policy drift, stale snapshots and multiple active snapshots block readiness deterministically.
- Production remains unavailable until an authoritative policy source and production provider are
  separately reviewed and configured.

## Validation

- Missing, expired, ambiguous, scope-mismatched and digest-invalid policy service tests
- Exact API schema and frontend runtime-contract tests for policy identity, digest and expiry
- Read-only desktop/mobile UI validation with no policy editing or provider/key/signing controls
- Full backend/frontend regression, single Alembic head, production build and GitHub CI
