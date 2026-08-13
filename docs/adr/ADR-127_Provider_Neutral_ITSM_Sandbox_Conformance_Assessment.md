# ADR-127: Provider-Neutral ITSM Sandbox Conformance Assessment

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-13 |
| Owners | Enterprise Integration Architecture, Security Architecture, Operations Architecture |
| Related | ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-016, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-036, ATLAS-047, ATLAS-050, ATLAS-052, ATLAS-053, ATLAS-055, ATLAS-056, ADR-124, ADR-125, ADR-126 |

## Context

ADR-126 establishes immutable provider-neutral ITSM integration profiles and treats sandbox
validation as an independent readiness prerequisite. Atlas does not yet have a governed way to
demonstrate that an adapter can resolve the exact profile, establish its configured trust and
credential boundaries, apply the allowlisted mapping and complete an inert sandbox round trip.

No production vendor adapter, endpoint, credential or sandbox is selected in this workspace. A
browser-supplied test payload or generic HTTP client would bypass the profile, adapter and policy
boundaries and could be mistaken for external mutation authority.

## Decision

Atlas will persist an immutable, short-lived sandbox conformance assessment bound to one exact
active integration profile. The assessment records organization, environment, site, profile ID,
profile version and digest, mapping version, adapter identity and version, diagnostic contract
version, inert challenge digest, stable outcome, validity interval and canonical digest.

The application creates the challenge from server-owned scope, profile and random assessment seed.
Callers provide only the profile ID, expected profile version, acknowledgement and idempotency key.
They cannot provide or override an endpoint, credential, secret, token, mapping, operation, request
body or expected provider response.

The adapter owns credential-reference resolution, provider-specific endpoint selection, trust
establishment and any native request or response. The application receives only a bounded diagnostic
result with exact profile/challenge binding and one stable state: `conformant`, `unavailable`,
`profile_blocked`, `trust_failed`, `credential_failed`, `permission_failed`, `mapping_failed` or
`round_trip_failed`. Provider-native errors and sensitive exchange material never enter the domain,
API, audit record or UI.

Production uses an unavailable adapter until deployment owners configure a separately reviewed
vendor sandbox adapter. Local development and tests may use an explicitly labeled deterministic
no-network adapter. Its conformant result proves only the application/adapter contract and can never
establish production readiness.

## Authorization And Persistence

Assessment creation requires a dedicated default-deny C2 permission, an authenticated human browser
session, CSRF, explicit no-authority acknowledgement and an idempotency key. Latest assessment read
uses a separate C1 permission. Both operations enforce exact organization, environment, site and
profile scope, produce attributable audit events and return `Cache-Control: no-store`.

An idempotency key is bound to the complete request fingerprint and returns the original assessment
without repeating the diagnostic. PostgreSQL persistence stores the immutable artifact and
actor/idempotency uniqueness; no-database development remains process-memory-only. Reads and replays
verify canonical integrity and exact current profile binding.

## Safety Boundary

The assessment is diagnostic evidence only. A conformant state does not bind that evidence into a
new profile version, satisfy production onboarding, authorize dispatch, enqueue work, create or
update a ticket, approve an ITSM or Atlas workflow, authorize infrastructure execution or mutate
infrastructure. Every corresponding authority field remains false.

Future profile succession, trusted evidence activation, vendor sandbox transport, record mutation
and production enablement require independent architecture decisions and validation slices.

## Consequences

- Operators can distinguish a configured profile from demonstrated adapter-contract conformance.
- The UI can run one bounded profile diagnostic without becoming a generic endpoint test tool.
- Adapter and provider failures are visible through stable codes without leaking sensitive details.
- Results are short-lived, attributable, replay-safe, durable when PostgreSQL is configured and
  cannot be confused with dispatch or execution approval.
- Production remains fail-closed until real deployment inputs and a reviewed adapter exist.

## Validation

- Conformant, unavailable, blocked-profile, trust, credential, permission, mapping and round-trip
  outcome tests
- Exact profile/challenge binding, idempotency, integrity, expiry and PostgreSQL round-trip tests
- Browser-session, CSRF, default-deny RBAC, exact-scope audit and `no-store` API tests
- Frontend runtime-contract and governance presentation tests with no arbitrary endpoint, secret,
  ticket-mutation or execution control
- Complete backend/frontend gates, one Alembic head, production build and responsive live validation
