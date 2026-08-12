# ADR-117: Connector Upgrade Signing-Provider Conformance Assessment

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-12 |
| Owners | MCP Platform Architecture, Security Architecture |
| Related | ATLAS-001, ATLAS-003, ATLAS-020, ATLAS-025, ATLAS-031, ATLAS-032, ATLAS-047, ATLAS-055, ADR-114, ADR-115, ADR-116 |

## Context

ADR-116 exposes provider and signing-key trust metadata, but metadata does not prove that the
configured provider can currently complete its sign-and-verify contract. Production KMS or HSM
selection remains deployment-specific, while Atlas still needs provider-neutral diagnostic evidence
before a concrete provider is approved.

## Decision

Atlas will persist an immutable, exact-scope signing-provider conformance assessment. The service
generates one inert challenge digest bound to organization, environment, assessment nonce and policy
version. Callers cannot provide a payload, digest, signature, key reference, algorithm or provider
parameter.

The authenticity-provider adapter owns a dedicated `diagnostic_sign_and_verify` operation. Signing
and verification happen inside that adapter method. Raw signatures, key material, credentials,
tokens, endpoints and provider-native diagnostics never cross the adapter boundary. The application
receives only provider metadata, the selected public key reference and a bounded result state.

Assessment states are `conformant`, `unavailable`, `ineligible_key`, `sign_failed`, `verify_failed`
or `policy_blocked`. Stable reason codes explain the result without exposing provider errors. The
assessment expires after five minutes or when the selected key expires, whichever occurs first.

## Authorization And Persistence

Creation requires a dedicated default-deny C2 permission, a browser session and CSRF in production,
an explicit no-authority acknowledgement and an idempotency key. Latest-read requires a separate C1
permission. The local development identity is accepted only while development mode is explicitly
enabled. Both APIs are exact organization/environment scope, audited and `no-store`.

Assessments are stored through the connector-upgrade repository with actor/idempotency uniqueness.
Canonical integrity is verified on replay and read. A reused idempotency key returns the original
assessment and never repeats the diagnostic.

## Safety Boundary

The assessment is diagnostic evidence only. It cannot manage a key, sign an upgrade receipt, approve
or hand off an upgrade, contact infrastructure, execute a command or mutate infrastructure. A
conformant non-production adapter is not production approval. Production remains unavailable until a
separately reviewed KMS/HSM adapter and policy are configured.

## Consequences

- Operators can distinguish trusted metadata from demonstrated adapter contract conformance.
- Provider failures are observable without leaking cryptographic or connection material.
- Every assessment is short-lived, attributable, replay-safe and independently readable.
- Vendor onboarding, key lifecycle management and production approval remain future decisions.

## Validation

- Conformant, unavailable, ineligible-key, sign-failed and verify-failed provider tests
- Adapter-boundary, exact-schema, idempotency, persistence round-trip and integrity tests
- Browser-session, CSRF, default-deny RBAC, audit and `no-store` tests
- Complete backend/frontend regressions, one Alembic head, production build and live responsive UI
