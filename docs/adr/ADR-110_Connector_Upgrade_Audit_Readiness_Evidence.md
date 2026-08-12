# ADR-110: Connector Upgrade Audit Readiness Evidence

## Status

Accepted - 2026-08-12

## Context

ADR-108 leaves audit readiness blocked before connector-upgrade handoff. Atlas currently has a
bounded in-memory audit projection and synthetic Syslog transport, but these do not satisfy the
ATLAS-032 requirement for a durable, authoritative, append-only ledger with verified integrity,
coverage, redaction and retention controls.

## Decision

Handoff readiness will accept only a versioned audit-readiness evidence snapshot from an explicit
source. The snapshot is bound to the exact organization, environment, approval request digest and
latest revalidation digest.

The evidence must assert all of the following:

- durable event acceptance;
- append-only authoritative storage;
- successful integrity verification and no detected gaps;
- current redaction and retention policies;
- complete required-producer coverage; and
- fail-closed blocking for consequential progress when audit durability is unavailable.

The service verifies the snapshot canonical digest, deterministic evidence ID, exact scope,
lineage and bounded validity period. Missing, stale, mismatched or corrupted evidence does not
satisfy the audit check. The default application source is empty because current synthetic and
in-memory components are not authoritative audit evidence.

## Authority Boundary

Valid audit evidence satisfies only the audit-readiness check. ITSM change and maintenance-window
checks remain blocked. Handoff readiness, artifact issuance, approval consumption, target contact,
package rebinding, configuration mutation, execution authorization and infrastructure mutation
remain false.

Any change in audit evidence changes the handoff-readiness digest and invalidates an older
change-context draft. Building the production durable audit ledger and its evidence producer is a
separate implementation concern governed by ATLAS-032.

## Verification

- Domain and browser validators enforce matching evidence ID/digest/current-state semantics.
- Service tests cover absent, exact current, corrupted and changed audit evidence.
- API projection exposes only safe evidence references and no ledger endpoint, token or secret.
- UI distinguishes verified audit readiness while continuing to display remaining blockers.
- Full regression, production build and responsive live validation are required.
