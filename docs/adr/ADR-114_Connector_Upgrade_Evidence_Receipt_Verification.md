# ADR-114: Connector Upgrade Evidence Receipt Verification

## Status

Accepted - 2026-08-12

## Context

ADR-113 creates a deterministic, non-executable connector-upgrade evidence receipt. A downloaded
JSON record needs a governed verification path, but a SHA-256 digest is not a digital signature and
must not be presented as proof of author identity, approval or runtime authority.

## Decision

Atlas will provide an authenticated, exactly scoped and read-only receipt verifier. The browser
first enforces a 64 KB limit and the minimized receipt allowlist. After explicit acknowledgement,
the API reconstructs the canonical payload, verifies its digest-derived identifier and compares its
request, decision, revalidation, immutable plan, evidence references, checks and validity bounds
with current authoritative state.

Verification returns one of four states:

- `current`: canonical integrity is valid and every authoritative binding is current.
- `stale`: integrity is valid, comparison completed and one or more current bindings differ.
- `expired`: integrity is valid but the receipt validity bound has elapsed; no current comparison is
  claimed.
- `unverifiable`: integrity is valid but authoritative current state cannot be safely established.

Malformed, oversized, authority-bearing, cross-scope or canonical-digest-mismatched input is
rejected rather than represented as one of these states.

## Authority Boundary

Verification proves canonical self-consistency and reports current-state agreement. It does not
prove author authenticity because the receipt is not digitally signed. It never consumes approval,
issues a handoff artifact, contacts a target, rebinds a package, changes configuration, authorizes
execution or mutates infrastructure.

No runtime accepts either the receipt or verification-result schema as an authorization token.

## Consequences

- Auditors can distinguish intact/current evidence from stale, expired or unavailable state.
- An attacker cannot extend validity or replace authoritative lineage and still receive `current`.
- Cryptographic origin authentication remains a future key-management and signing decision.
- Verification is a dedicated C2 evidence operation with CSRF, RBAC, no-store and mandatory audit.

## Verification

- Domain and service tests cover current independent review, tampering, stale evidence, expiry,
  unavailable integrity state and every no-authority flag.
- API tests cover CSRF, exact scope, authority-bearing input rejection and safe errors.
- Browser tests cover size/schema/request filtering, explicit acknowledgement and separated
  integrity, current-state and authenticity claims.
