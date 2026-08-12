# ADR-116: Connector Upgrade Signing-Key Trust Inventory

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-12 |
| Owners | MCP Platform Architecture, Security Architecture |
| Related | ATLAS-001, ATLAS-003, ATLAS-020, ATLAS-025, ATLAS-031, ATLAS-032, ATLAS-047, ATLAS-055, ADR-026, ADR-114, ADR-115 |

## Context

ADR-115 authenticates one connector-upgrade evidence receipt through an injected signing provider.
The receipt identifies its key and signer, but an operator cannot inspect the current trust posture
before creating or verifying evidence. Production KMS or HSM selection remains deployment-specific
and cannot be assumed by the core platform.

## Decision

Atlas will expose an immutable, exact-scope signing-key trust inventory through the existing
provider boundary. The provider returns metadata only. The application derives time-dependent
effective state and produces a versioned, audited snapshot.

The inventory contains provider class and availability plus each key's ID, version, signer profile,
signer workload, algorithm, configured state, validity window, effective state, signing eligibility
and verification trust. It never contains private or symmetric key material, signatures,
credentials, provider tokens, endpoints or unrestricted provider diagnostics.

Effective state is one of `active`, `not_yet_valid`, `expired`, `disabled` or `revoked`. Provider
unavailability is represented independently so an empty production provider remains observable and
fail-closed. Configured disablement or revocation takes precedence over time-derived state.

## Authorization And Audit

The read API requires a dedicated default-deny C1 permission, an authenticated browser session and
the exact organization/environment scope. A direct development identity is accepted only while the
server is explicitly running in development mode so the local UI remains testable; production keeps
the browser-session requirement. A required audit record is written before the protected response is
returned. Responses are `no-store` and errors do not disclose foreign-scope keys.

## Safety Boundary

The inventory is security evidence only. It provides no create, import, rotate, enable, disable,
revoke, delete, export or signing operation. It grants no approval, handoff, target, configuration,
runtime, execution or infrastructure-mutation authority. Production signing remains unavailable
until a separately reviewed KMS/HSM adapter is configured.

## Consequences

- Operators can distinguish a healthy non-production trust fixture from unavailable production
  signing without seeing key material.
- Disabled, revoked, expired and not-yet-valid states are explicit and testable.
- Concrete provider onboarding, key lifecycle mutation and public trust distribution remain future
  decisions.

## Validation

- Exact-scope, provider-unavailable and all effective-state derivation tests
- Secret/key-material absence and strict response-schema tests
- Default-deny RBAC, no-store and required-audit tests
- Frontend contract, empty/error, desktop and 390-pixel mobile checks
- Proof that no key-management or operational authority control is introduced
