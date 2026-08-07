# ADR-049: Governed Operational Knowledge Track Review Decision Contract

- Status: Accepted
- Date: 2026-08-07
- Owners: Product Owner, Solution Architecture, Security Architecture, Knowledge Management,
  Identity Governance, Data Governance
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-025, ATLAS-027, ATLAS-030, ATLAS-031,
  ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-053, ATLAS-054,
  ATLAS-055, ATLAS-056, ADR-009 through ADR-048

## Context

ADR-048 lets the exact assigned domain or security reviewer redisplay the exact sealed finding
packet created from an immutable protected-content snapshot. Atlas still records no accountable
review judgment. A later workflow cannot infer a decision from finding presence, severity, browser
state, inactivity, or AI output. The next stage must bind one explicit human track decision to the
exact immutable presentation without turning that decision into knowledge approval, publication,
or operational authority.

## Decision

Atlas will implement a dedicated track-review-decision service. One audited `POST` records one
immutable decision for the exact presented finding packet and exact assignment track. An audited
`GET` returns only the minimized decision metadata while its protected read authority remains
current.

### Decision Vocabulary

The only initial dispositions are:

- `review-disposition.passed`: the exact reviewer considers this track ready for later approval
  evaluation; and
- `review-disposition.changes-required`: the exact reviewer requires a separately governed
  correction and resubmission cycle.

`passed` is not approval. `changes-required` creates no correction itself. Findings remain
observations and cannot be converted to a decision automatically. A policy-controlled set of
track-specific basis codes provides structured rationale without copying finding narratives into
application persistence.

### Caller Contract

The caller may provide only:

- exact finding-presentation ID and canonical digest;
- exact signed decision-policy ID and digest;
- one allowed disposition and one or more policy-allowed basis codes;
- a bounded review purpose;
- acknowledgement that the exact findings were reviewed, that this is a human track decision,
  and that the result is neither knowledge approval nor operational authorization;
- idempotency and correlation identifiers.

The caller cannot provide or override reviewer identity, tenant, assignment, track, lease,
browser binding, finding content, category, severity, artifact location, governance labels,
decision time, completion flags, correction content, approver, approval, publication, indexing,
retrieval, model context, target, credential, command, schedule, workflow, execution, deployment,
or mutation fields.

The read caller supplies only the opaque review-decision ID in the path. Atlas derives every
source, policy, subject, track, and browser binding from trusted records and cookies.

### Authorization And Current Proof

Before a claim is created the service revalidates:

- complete immutable connector, evidence, draft, request, assignment, lease, protected-content,
  finding, and finding-presentation lineage;
- exact source schemas, states, canonical digests, organization, environment, knowledge item,
  draft version, classification, access, retention, encryption, and track;
- the signed decision policy, allowed dispositions and basis codes, required attestor identity,
  receipt schema, assurance level, and authentication age;
- a current enterprise human identity with recent hardware-backed MFA, exact tenant scope, and
  dedicated C2 decision-create plus protected lineage-read permissions;
- the salted current-subject digest equals the lease holder and exact assigned reviewer;
- the normal browser session and track-specific HttpOnly lease cookie match the active lease;
- the presentation remains unexpired and no prior decision, correction, approval, publication,
  workflow, execution, deployment, or mutation authority exists for the track.

Missing, expired, revoked, transferred, cross-track, malformed, or mismatched proof fails before
claim creation. The service never accepts identity, track, completion, or authority flags from the
caller.

### Atomic Decision Claim

Required intent audit succeeds before a unique immutable finding-presentation claim is created.
The claim is the point of no return. An existing claim is reusable only when exact source,
subject, browser, lease, track, disposition, basis, request binding, and idempotency digests match
a completed record.

Failure or uncertainty after claim creation remains claimed and is never retried automatically.
Concurrent or conflicting decisions cannot overwrite the first accountable judgment.

### Trusted Decision Attestation

After claim creation Atlas sends a trusted attestor only immutable lineage digests, salted subject
and browser bindings, the policy-approved disposition and basis codes, purpose digest, decision ID,
and decision time. Finding narratives, artifact coordinates, cookies, raw identities, credentials,
and operational data never cross this boundary.

The attestor returns a signed minimized receipt bound to the exact instruction. Production fails
closed when no approved attestor is configured. Development may use a deterministic synthetic
attestor that cannot contact a directory, model, vector store, workflow, deployment system,
connector, credential broker, or infrastructure target.

### Persistence And Response Boundary

The immutable application record uses state `operational_knowledge_track_review_decided`. It stores
only exact source lineage, salted subject/browser bindings, track, structured disposition and basis
codes, policy/attestor identity, purpose, timestamps, integrity digests, and safe lifecycle flags.
It stores no finding category, severity, summary, detail, artifact location, cookie, raw identity,
secret, or free-form decision narrative.

The API returns only opaque IDs, title, classification, track, disposition, basis codes, safe policy
labels, decision time, expiry, canonical and receipt digests, track-completion state, correction
requirement, and explicit no-authority flags. Responses use strict `no-store`, `nosniff`, no-referrer,
and restrictive content-security-policy headers.

### Track And Aggregate Semantics

A successful decision sets only the matching domain or security review-completed flag. The other
track is not inferred. `changes-required` additionally sets `correction_required=true` but never
creates or edits a draft. `passed` sets only that track's pass flag.

Both track decisions may be aggregated only when they bind the same immutable review request,
assignment set, draft, and policy generation. `all_tracks_passed=true` is readiness evidence for a
later approval stage; it is not approval, publication eligibility, retrieval availability, workflow
authority, or execution authority. Any `changes-required` result keeps approval readiness false.

### Read And Replay

The exact current assignee may read the minimized decision metadata while the original lease,
browser session, track cookie, account, subject, and policy remain valid. Read never changes the
decision, extends the lease, exposes findings, creates a correction, or grants cross-track access.
Later approval and correction services consume the immutable decision through internal lineage
ports under their own independent authorization contracts.

### Failure And Audit

Intent audit precedes claim creation; claim audit follows a successful claim; attestation and
completion audit must succeed before persistence; and each read has a separate audit event. Audit
identifies the accountable enterprise subject and safe track/disposition but excludes findings,
artifact coordinates, cookies, raw identity, and secrets.

Failures before claim creation leave no claim. Failures after claim creation remain claimed and
return no partial decision. Policy, lineage, permission, cookie, attestation, persistence, audit,
concurrency, or integrity uncertainty fails closed.

### Persistence And API

Claims and records are immutable, deterministic, concurrency-safe, and equivalent in memory and
PostgreSQL. The API uses the normal browser session, track-specific lease cookie, mutation CSRF,
strict schemas, dedicated default-deny RBAC, C2 classification, recent hardware MFA, exact tenant
and assignee scope, minimized responses, and safe errors.

## Consequences

### Positive

- Decisions are explicit human judgments bound to the exact sealed findings actually reviewed.
- Domain and security tracks remain independent and accountable.
- Structured decision metadata is durable without persisting sensitive finding narratives.
- Correction and later approval stages receive immutable, integrity-bound inputs.

### Costs

- Production requires an approved decision attestor.
- The short-lived protected inspection authority must remain current at decision time.
- Correction and final approval require separate lifecycle contracts and user actions.

## Rejected Alternatives

### Infer A Decision From Findings

Rejected because finding presence, count, category, or severity is not human judgment.

### Let The Caller Submit A Narrative Decision

Rejected because it duplicates sensitive observations into ordinary application persistence and
weakens the sealed-artifact boundary.

### Treat Both Track Passes As Knowledge Approval

Rejected because accountable review and final approval require different roles and authority.

### Permit Decision Replacement

Rejected because changing an accountable decision in place destroys audit history. A later
correction and resubmission creates a new governed review generation.

## Follow-Up

Later independent lifecycle contracts cover correction and resubmission, final approval or
rejection, chunking and embedding, retrieval-index validation and publication, suspension,
supersession, retention, and deletion.
