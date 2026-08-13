# ADR-130: Provider-Neutral ITSM Onboarding Policy Provenance and Authenticity

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-13 |
| Owners | Enterprise Integration Architecture, Security Architecture, Deployment Architecture |
| Related | ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-013, ATLAS-016, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-036, ATLAS-047, ATLAS-050, ATLAS-052, ATLAS-055, ATLAS-056, ATLAS-057, ADR-124, ADR-125, ADR-126, ADR-127, ADR-128, ADR-129 |

## Context

ADR-129 binds onboarding readiness to one exact immutable policy and verifies its canonical digest,
scope and lifecycle. A digest proves internal consistency but not issuer authenticity. An attacker
able to replace both payload and digest could still supply a self-consistent unauthorized policy.

No production policy authority, key-management platform, trust registry, signing algorithm or key
material exists in this workspace. Browser-supplied signatures or an implicit local trust fallback
would create false production assurance.

## Decision

Atlas will require a detached policy-provenance envelope and a separately injected trust registry
before evaluating policy lifecycle or onboarding readiness. The immutable envelope binds exact
policy ID, integer version and digest, issuer, organization/environment/site scope, signing-key ID
and version, algorithm, signed/expiry times, signed-payload digest, signature digest and canonical
envelope digest.

The trust record independently binds issuer, key identity/version, algorithm, exact scope, active,
disabled or revoked state, validity interval and canonical digest. Verification key material remains
inside the verifier boundary and never enters policy, provenance, readiness, API, audit or browser
payloads.

Missing, failed, ambiguous, malformed, drifted, mismatched, future, expired, disabled, revoked,
unsupported or cryptographically invalid state fails closed with stable errors. The policy is not
considered current merely because its payload and digest agree.

Production uses empty provenance and trust sources plus an unavailable verifier. Development uses
an explicitly non-production deterministic HMAC-SHA256 fixture only to validate the contract. That
fixture is not a production algorithm decision and cannot make the synthetic adapter or synthetic
deployment evidence onboarding-ready.

## Dossier Binding

The readiness dossier records only minimized provenance identity, envelope digest, signing-key
identity/version, algorithm, signed time and verification time. It never returns signature value,
verification key material or trust-registry internals.

The API accepts only the profile identifier. It accepts no policy, provenance envelope, issuer,
key, algorithm, signature, trust decision, endpoint, credential, secret, requirement result or
approval assertion from callers.

## Safety Boundary

Authenticity is an evidence claim only. It does not author, distribute, sign, trust, rotate or revoke
policy or keys; configure or contact an adapter; dispatch or mutate an ITSM record; approve a
workflow; authorize infrastructure execution; or mutate infrastructure. Every authority field
remains false.

Production key custody, signer onboarding, rotation, revocation distribution, vendor transport and
dispatch activation require independent architecture decisions and validation slices.

## Consequences

- A self-consistent but unauthorized replacement policy no longer passes readiness evaluation.
- Policy issuer and signing-key lifecycle become independently governable and auditable inputs.
- Ordinary responses preserve proof metadata without exposing signatures or key material.
- Production remains unavailable until real policy and trust authorities are configured.

## Validation

- Missing, failed, ambiguous, malformed, mismatched and digest-drift provenance tests
- Missing, failed, ambiguous, wrong-scope, future, expired, disabled and revoked trust tests
- Unsupported algorithm, invalid signature and verifier-failure tests
- Exact API/frontend minimized provenance contracts with no trust or operational controls
- Complete backend/frontend gates, one Alembic head, production build and responsive live UI
