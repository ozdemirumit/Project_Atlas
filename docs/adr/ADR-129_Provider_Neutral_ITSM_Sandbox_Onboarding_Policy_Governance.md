# ADR-129: Provider-Neutral ITSM Sandbox Onboarding Policy Governance

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-13 |
| Owners | Enterprise Integration Architecture, Security Architecture, Deployment Architecture |
| Related | ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-013, ATLAS-016, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-036, ATLAS-047, ATLAS-050, ATLAS-052, ATLAS-055, ATLAS-056, ATLAS-057, ADR-124, ADR-125, ADR-126, ADR-127, ADR-128 |

## Context

ADR-128 derives an exact-profile sandbox-adapter onboarding dossier, but policy identity, ordered
requirements, adapter eligibility and freshness limits remain application constants. A deployment
cannot independently govern or expire those decisions or prove which rules produced a dossier.

No production ITSM vendor, sandbox adapter, policy issuer or policy distribution mechanism is
selected in this workspace. An implicit application fallback or browser-supplied policy would create
false production assurance.

## Decision

Atlas will obtain onboarding policy only through an injected authoritative policy source. Each
immutable snapshot binds exact organization, environment and site scope, policy ID and integer
version, issuer, ordered requirement identifiers, approved adapter ID/version pairs, maximum
conformance and deployment-evidence ages, production-eligibility requirements, issue/effective/
expiry times and a canonical digest.

Exactly one policy must be current. The service verifies canonical integrity, exact scope, supported
and complete ordered requirements, positive bounded freshness limits and current lifecycle. Missing,
future, expired, ambiguous, scope-mismatched, integrity-invalid or unsupported policy state fails
closed with stable errors. There is no application-constant fallback.

Production uses an empty source until deployment and security owners configure a reviewed policy
source. Local development uses an explicitly labeled deterministic policy. It may name the synthetic
adapter solely to exercise binding; the adapter and evidence remain non-production and therefore
cannot satisfy onboarding readiness.

## Dossier Binding

The readiness dossier records policy ID, version, digest, issuer and expiry. Conformance and
deployment evidence must be current under both their own validity windows and the policy maximum
ages. Adapter ID/version must be policy-approved and all eligibility requirements remain satisfied.

The API accepts only the profile identifier. It accepts no policy, issuer, adapter, endpoint,
credential, secret, requirement result, freshness limit or approval assertion from callers.

## Safety Boundary

Policy validity and onboarding readiness are evidence claims only. They do not author or approve a
policy, configure or contact an adapter, dispatch or mutate an ITSM record, approve a workflow,
authorize infrastructure execution or mutate infrastructure. Every authority field remains false.

Policy provenance and authenticity, vendor transport, dispatch workflows and production activation
require independent architecture decisions and validation slices.

## Consequences

- Security and deployment owners can govern readiness criteria independently from service releases.
- Each dossier proves the exact policy and freshness limits used for evaluation.
- Policy absence, drift, ambiguity and expiry block readiness deterministically.
- Production cannot inherit a permissive local or application-default policy.

## Validation

- Missing, future, expired, ambiguous, wrong-scope, digest-invalid and unsupported policy tests
- Adapter eligibility and policy freshness service tests
- Exact API/frontend policy-binding contracts with no authoring or operational controls
- Complete backend/frontend gates, one Alembic head, production build and responsive live UI
