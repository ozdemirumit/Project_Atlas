# ADR-115: Connector Upgrade Evidence Receipt Authenticity

**Status:** Accepted  
**Date:** 2026-08-12  
**Decision Owners:** Security Architecture, Connector Platform Architecture

## Context

ADR-113 defines a minimized, non-executable connector-upgrade evidence receipt. ADR-114 verifies
its canonical digest and current authoritative state, while correctly reporting that an unkeyed
SHA-256 digest does not prove who issued the receipt.

Enterprise audit exchange requires a distinct origin-authentication layer. That layer must support
key rotation and revocation without turning an evidence record into an approval, handoff token or
runtime credential.

## Decision

Atlas will introduce a versioned signed-receipt envelope. The envelope binds the complete canonical
v1 evidence receipt to its organization, environment, request, signer workload, signer profile,
algorithm, key identifier, key version and bounded signature lifetime.

Signing and verification are accessed only through an injected key-provider port. Application and
API code never receives private key material. Production fails closed when no approved KMS or HSM
adapter is configured. Development and tests may use the explicitly labelled
`algorithm.hmac-sha256-nonproduction` adapter with deterministic, environment-scoped key material.
HMAC validation proves origin only to the Atlas deployment that controls the shared secret; it is
not represented as publicly verifiable authorship.

Verification reports canonical integrity, cryptographic origin authenticity and current
authoritative-state consistency as separate dimensions. Unknown, disabled, expired, revoked,
scope-mismatched or algorithm-mismatched keys fail closed. Legacy unsigned v1 receipts remain
accepted by the ADR-114 verifier and continue to report `authenticity_proven=false`.

The signed envelope and every verification result preserve the non-execution boundary. They grant
no approval, handoff, target, configuration, runtime, execution or infrastructure-mutation
authority, and no runtime accepts either schema as a credential.

## Consequences

- Auditors can distinguish an intact unsigned receipt from an Atlas-origin-authenticated receipt.
- Key identifiers and lifecycle metadata are visible; secret key material is never serialized.
- Key rotation and revocation can invalidate authenticity without mutating the original receipt.
- Production deployments require a separately reviewed KMS or HSM provider before signing works.
- Public-key offline verification remains a future provider and trust-distribution decision.

