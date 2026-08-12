# ADR-111: Connector Upgrade Authoritative ITSM Change Evidence

## Status

Accepted - 2026-08-12

## Context

ADR-109 creates an internal connector-upgrade change-context draft but deliberately does not
dispatch it. ADR-110 satisfies only audit readiness. ATLAS-036 keeps the external ITSM platform
authoritative for service-management records and prohibits treating generic ticket state, comments,
email or webhook delivery as approval or execution authority.

## Decision

Handoff readiness will accept a versioned vendor-neutral ITSM change evidence snapshot only from an
explicit source. The snapshot is bound to the exact organization, environment, approval request,
latest revalidation and immutable upgrade plan.

Evidence must identify a validated adapter, adapter version, authoritative ITSM instance, external
record ID and external source version. It must assert current readable state, exact-plan binding,
active record state, conflict-free synchronization and absence of revocation. Atlas verifies the
canonical digest, deterministic evidence ID, scope, lineage and bounded validity period.

The default source is empty. Selecting and configuring a ServiceNow, Jira Service Management or
other vendor adapter requires separate environment-specific design and credentials. This ADR does
not infer that choice or fabricate an authoritative record.

## Authority Boundary

The contract is inbound and read-only. It does not create, update, comment on, approve, close or
otherwise modify an ITSM record. It exposes no endpoint, token, credential, description, attachment
or free-form ticket content.

Valid evidence satisfies only the ITSM-change check. Maintenance-window evidence remains blocked
because an active change record is not proof that the current time is inside an approved window.
Handoff readiness, artifact issuance, approval consumption, target contact, package rebinding,
configuration mutation, execution authorization and infrastructure mutation remain false.

Any ITSM evidence change alters the handoff-readiness digest and invalidates an older internal
change-context draft. Source-version conflict, inaccessible state, expiry, revocation, lineage
mismatch or digest corruption fails closed.

## Verification

- Domain and browser validators enforce matching ITSM evidence ID, digest and satisfied-check state.
- Service tests cover absent, exact current, corrupted and changed evidence.
- API projection exposes only safe evidence references.
- UI distinguishes verified authoritative ITSM change evidence from the remaining window blocker.
- Full regression, production build and responsive live validation are required.
