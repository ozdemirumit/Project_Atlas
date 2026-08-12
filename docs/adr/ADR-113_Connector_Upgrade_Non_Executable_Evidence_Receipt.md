# ADR-113: Connector Upgrade Non-Executable Evidence Receipt

## Status

Accepted - 2026-08-12

## Context

ADR-112 allows connector-upgrade review to reach `evidence_complete` without creating an execution
or handoff artifact. ATLAS-037 leaves an explicit MVP decision between issuing a non-executable
approval receipt and deferring every artifact. Operations and audit users need a portable record of
the exact completed review, but Atlas must not create a token that a runtime could accept.

## Decision

Atlas will create a versioned JSON evidence receipt only from a current `evidence_complete`
assessment. Creation requires an authenticated enterprise human, an explicit no-authority
acknowledgement and the exact current readiness digest.

The receipt binds the assessment, request, decision, revalidation and immutable plan digests. It
also binds the authoritative audit, ITSM change and maintenance-window evidence references, all
required and satisfied checks, applicability results, scope, creator and bounded validity. Its
canonical digest and deterministic identifier are derived from this minimized contract.

The source revalidation time is used as the stable receipt creation checkpoint. Repeating creation
against the same actor and exact readiness produces the same receipt. A changed readiness digest,
expired evidence, missing evidence or blocker fails closed.

## Authority Boundary

The receipt declares `evidence_receipt_only=true` and `runtime_acceptable=false`. Approval remains
unconsumed. Handoff readiness, handoff-artifact issuance, target contact, package rebinding,
configuration change, execution authorization and infrastructure mutation all remain false.

No Atlas runtime accepts this schema as authorization. The receipt includes no target, endpoint,
credential, secret, token, raw ticket content or infrastructure payload. Browser-side JSON download
does not change server state beyond the required audit event.

## Consequences

- Reviewers can preserve and inspect a portable, integrity-verifiable evidence record.
- A future controlled runtime must use a separately approved artifact schema and validator.
- Receipt creation is a C2 evidence operation with a dedicated permission and mandatory CSRF
  protection in browser sessions.
- The receipt is generated deterministically and does not require a new operational database table.

## Verification

- Domain tests reject incomplete checks, invalid digests and any authority-bearing flag.
- Service tests cover unconfirmed, blocked, exact-current, deterministic replay and stale-digest
  cases.
- API tests cover authorization, CSRF, no-store behavior and fail-closed blocked readiness.
- Browser validators reject extra token, credential, target or endpoint fields.
- UI tests cover explicit acknowledgement, receipt presentation, JSON download availability and the
  absence of install, apply, execute or handoff controls.
