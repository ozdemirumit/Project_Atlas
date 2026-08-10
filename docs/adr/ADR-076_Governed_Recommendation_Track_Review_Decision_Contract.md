# ADR-076: Governed Recommendation Track Review Decision Contract

- Status: Accepted
- Date: 2026-08-10
- Owners: Product Owner, Solution Architecture, Security Architecture, Infrastructure Operations,
  Service Management, Identity Governance, Data Governance
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-026, ATLAS-027,
  ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-040, ATLAS-041, ATLAS-042,
  ATLAS-043, ATLAS-044, ATLAS-046, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-052, ATLAS-053,
  ATLAS-054, ATLAS-055, ATLAS-056, ADR-009 through ADR-075

## Context

ADR-075 lets the exact assigned technical or service-impact reviewer redisplay the exact sealed
finding packet created from one immutable protected recommendation snapshot. Atlas still records no
accountable human judgment. A later service cannot infer a decision from finding presence, count,
category, severity, browser state, inactivity or AI output. The next boundary must bind one explicit
track decision to the exact finding presentation without turning it into recommendation approval,
change authorization, workflow state or operational authority.

## Decision

Atlas will implement a dedicated recommendation track-review-decision service. One audited `POST`
records one immutable decision for the exact presented finding packet and exact assignment track. An
audited `GET` returns minimized decision metadata only while the protected read authority remains
current.

### Decision Vocabulary

The only initial dispositions are:

- `review-disposition.passed`: the exact reviewer considers the assigned track ready for later
  recommendation-disposition evaluation; and
- `review-disposition.changes-required`: the exact reviewer requires a separately governed
  correction and new review generation.

`passed` is not recommendation approval. `changes-required` creates no correction. Findings remain
observations and cannot be converted to a decision automatically. Signed policy owns distinct,
bounded basis-code catalogs for technical and service-impact review so structured rationale does not
copy finding narratives into application persistence.

### Caller Contract

The caller may provide only:

- exact finding-presentation ID and canonical digest;
- exact signed decision-policy ID and digest;
- one allowed disposition and one or more policy-allowed basis codes;
- a bounded review purpose;
- acknowledgement that the exact findings were reviewed, that this is an accountable human track
  decision and that it grants neither recommendation approval nor operational authority; and
- idempotency and correlation identifiers.

The caller cannot provide or override reviewer identity, tenant, assignment, track, lease, browser
binding, recommendation or finding content, category, severity, artifact location, governance
labels, decision time, completion flags, correction content, approver, approval, workflow, ITSM,
target, credential, command, schedule, execution, deployment or mutation fields.

The read caller supplies only the opaque decision ID in the path. Atlas derives all source, policy,
subject, track and browser bindings from trusted records and cookies.

### Authorization And Current Proof

Before claim creation the service revalidates:

- complete immutable connector, recommendation, promotion, readiness, review request, assignment,
  lease, protected-content, finding and finding-presentation lineage;
- exact source schemas, states, canonical digests, organization, environment, recommendation
  version, classification, access, retention, encryption and track;
- the signed decision policy, allowed dispositions and track-specific basis codes, required attestor
  identity, receipt schema, assurance level and authentication age;
- a current enterprise human identity with recent hardware-backed MFA, exact tenant scope and
  dedicated C2 decision-create plus protected lineage-read permissions;
- the salted current-subject digest equals the lease holder and exact assigned reviewer;
- the normal browser session and track-specific HttpOnly lease cookie match the active lease; and
- the finding presentation remains unexpired and no prior decision, correction, approval, workflow,
  ITSM, execution, deployment or mutation authority exists for the track.

Missing, expired, revoked, transferred, cross-track, malformed or mismatched proof fails before
claim creation. The service never accepts identity, track, completion or authority flags from the
caller.

### Atomic Decision Claim

Required intent audit succeeds before a unique immutable finding-presentation claim is created. The
claim is the point of no return. An existing claim is reusable only when exact source, subject,
browser, lease, track, disposition, basis, request binding and idempotency digests match a completed
record.

Failure or uncertainty after claim creation remains claimed and is never retried automatically.
Concurrent or conflicting decisions cannot overwrite the first accountable judgment.

### Trusted Decision Attestation

After claim creation Atlas sends an approved attestor only immutable lineage digests, salted subject
and browser bindings, the policy-approved disposition and basis codes, purpose digest, decision ID
and decision time. Recommendation content, finding narratives, artifact coordinates, cookies, raw
identities, credentials and operational data never cross this boundary.

The attestor returns a signed minimized receipt bound to the exact instruction. Production fails
closed when no approved attestor is configured. Development may use a deterministic synthetic
attestor that cannot contact a directory, model, vector store, workflow, ITSM system, deployment
system, connector, credential broker or infrastructure target.

### Persistence And Response Boundary

The immutable application record uses state `recommendation_track_review_decided`. It stores exact
source lineage, salted subject and browser bindings, track, structured disposition and basis codes,
policy and attestor identity, purpose, timestamps, integrity digests and safe lifecycle flags. It
stores no recommendation or finding content, category, severity, summary, detail, artifact location,
cookie, raw identity, secret or free-form decision narrative.

The API returns only opaque IDs, classification, source outcome, track, disposition, basis codes,
safe policy labels, decision time, expiry, canonical and receipt digests, track-completion state,
correction requirement and explicit no-authority flags. Responses use strict `no-store`, `nosniff`,
no-referrer and restrictive content-security-policy headers.

### Track And Aggregate Semantics

A successful decision sets only the matching technical or service-impact review-completed flag. The
other track is not inferred. `changes-required` additionally sets `correction_required=true` but
never creates or edits a recommendation. `passed` sets only that track's pass flag.

Both decisions may be aggregated only when they bind the same immutable review request, assignment
set, promoted recommendation version and policy generation. `all_tracks_passed=true` is readiness
evidence for a later final recommendation disposition; it is not recommendation approval, workflow
or ITSM authority, execution authorization, deployment authorization or infrastructure mutation.
Any `changes-required` result keeps final-disposition readiness false.

### Read And Replay

The exact current assignee may read minimized decision metadata while the original lease, browser
session, track cookie, account, subject and policy remain valid. Read never changes the decision,
extends the lease, exposes findings, creates a correction or grants cross-track access. Later
correction and final-disposition services consume immutable decisions through internal lineage
ports under independent authorization contracts.

### Failure And Audit

Intent audit precedes claim creation; claim audit follows a successful claim; attestation and
completion audit must succeed before persistence; and each read has a separate audit event. Audit
identifies the accountable enterprise subject and safe track and disposition but excludes findings,
artifact coordinates, cookies, raw identity and secrets.

Failures before claim creation leave no claim. Failures after claim creation remain claimed and
return no partial decision. Policy, lineage, permission, cookie, attestation, persistence, audit,
concurrency or integrity uncertainty fails closed.

### Persistence And API

Claims and records are immutable, deterministic, concurrency-safe and equivalent in memory and
PostgreSQL. The API uses the normal browser session, track-specific lease cookie, mutation CSRF,
strict schemas, dedicated default-deny RBAC, C2 create and C1 read classification, recent hardware
MFA, exact tenant and assignee scope, minimized responses and safe errors.

## Consequences

### Positive

- Decisions are explicit accountable human judgments bound to the exact sealed findings reviewed.
- Technical correctness and service-impact tracks remain independent and attributable.
- Structured decision metadata is durable without persisting sensitive narratives.
- Correction and final recommendation disposition receive immutable integrity-bound inputs.

### Costs

- Production requires an approved decision attestor.
- The short-lived protected inspection authority must remain current at decision time and read.
- Correction and final recommendation disposition require separate lifecycle contracts and actions.

## Rejected Alternatives

### Infer A Decision From Findings

Rejected because finding presence, count, category or severity is not human judgment.

### Let The Caller Submit A Narrative Decision

Rejected because it duplicates sensitive observations into ordinary persistence and weakens the
sealed-artifact boundary.

### Treat Both Track Passes As Recommendation Approval

Rejected because accountable review and final approval require distinct roles and authority.

### Permit Decision Replacement

Rejected because changing an accountable decision in place destroys audit history. A later
correction creates a new governed recommendation and review generation.

## Follow-Up

Later independent contracts cover correction and resubmission, final recommendation disposition,
workflow and ITSM handoff, suspension, supersession, retention, controlled export and any separately
approved operation.
