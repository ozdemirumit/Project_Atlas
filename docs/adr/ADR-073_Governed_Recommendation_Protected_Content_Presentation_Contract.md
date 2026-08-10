# ADR-073: Governed Recommendation Protected Content Presentation Contract

- Status: Accepted
- Date: 2026-08-10
- Owners: Product Owner, Solution Architecture, Security Architecture, AI Governance,
  Identity Governance, Data Governance
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-026, ATLAS-027,
  ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-040, ATLAS-041, ATLAS-042,
  ATLAS-043, ATLAS-044, ATLAS-046, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-052, ATLAS-053,
  ATLAS-054, ATLAS-055, ATLAS-056, ADR-009 through ADR-072

## Context

ADR-072 creates a maximum-ten-minute, browser-bound, track-specific inspection lease for the
exact assigned recommendation reviewer. Lease issuance deliberately returns no recommendation
content and records no finding or decision. The next stage must disclose only the exact immutable
promoted recommendation version inside that lease boundary without creating reusable artifact
access or widening review authority.

Recommendation content includes the outcome, headline, safety notice, candidate options, evidence
needs, impact, interruption, duration, recovery and uncertainty statements. It must cross a trusted
presentation boundary, be deterministically minimized and redacted, and never be persisted as
plaintext by the presentation service.

## Decision

Atlas will implement a dedicated recommendation protected-content presentation service. A first
audited `POST` creates one immutable presentation record for an active lease and returns one
bounded redacted plain-text snapshot. An audited `GET` may reproduce only that exact snapshot while
the same lease, browser session, assignee, track cookie, source recommendation and policies remain
current.

### Caller Contract

The first-presentation caller may provide only:

- exact lease ID and canonical digest;
- exact signed presentation-policy ID and digest;
- a bounded inspection purpose;
- acknowledgement that content is sensitive and read-only;
- acknowledgement that presentation grants no finding, decision, approval or operational authority;
- idempotency and correlation identifiers.

The caller cannot provide or override identity, assignment, track, recommendation content, option,
field selection, range, query, source location, artifact digest, presenter, redaction rule, byte
limit, cookie, secret, finding, decision, correction, approval, workflow, ITSM, credential, command,
schedule, execution, deployment or mutation fields.

Replay supplies only recommendation, lease and opaque presentation IDs in the path. Atlas derives
all content and access context from immutable trusted records and the track-specific cookie.

### Authorization And Lease Proof

Before any content access, the service revalidates:

- the immutable promotion, readiness, review-request, reviewer-assignment and lease lineage;
- exact recommendation, promotion, assessment, request, assignment, lease, track and opaque
  assignment bindings and canonical digests;
- the active lease, signed inspection and presentation policies, trusted presenter identity,
  classification, output format, maximum bytes, redaction profile and replay requirements;
- a current enterprise human identity with hardware-backed MFA, exact tenant scope, dedicated C2
  presentation and lease-read permissions, and authentication no older than policy permits;
- the salted current-subject digest equals the lease holder and selected-track assignee;
- the browser session hashes to the lease binding and the track cookie hashes to the stored secret;
- source records remain current and no later finding, decision, approval, workflow, ITSM,
  execution, deployment or mutation authority exists.

Missing, malformed, expired, transferred, cross-track or mismatched proof fails closed without
content. A technical cookie cannot open service-impact content and vice versa.

### Atomic Presentation Claim

After intent audit succeeds and before content is resolved, the repository creates an immutable
claim with a unique constraint on lease ID. Claim creation is the point of no return.

An existing claim is reusable only when subject, browser, request and idempotency bindings match
and an exact completed presentation exists. Any uncertainty after claim creation remains claimed
and is not retried automatically by the first-presentation endpoint.

### Trusted Presenter Boundary

The application sends only trusted immutable recommendation lineage, classification, outcome,
bounded recommendation fields, lease and subject binding digests, output media type, language,
redaction profile, byte limit, presentation policy digest and presentation ID.

The trusted presenter must:

1. verify the exact promoted recommendation artifact and source-binding digest;
2. reject active content, executable payloads and external references;
3. apply the policy-selected deterministic minimization and redaction profile;
4. normalize the result as bounded UTF-8 plain text with stable ordered sections;
5. enforce the byte limit after redaction without splitting UTF-8 sequences;
6. compute content, source-binding, redaction, truncation and cleanup digests;
7. erase plaintext working buffers and close protected channels in every outcome; and
8. return content plus a signed minimized receipt.

Production fails closed when no trusted presenter is configured. Development may use a
deterministic synthetic presenter bound to synthetic recommendation lineage and may not contact a
target, connector, directory, model, vector store, workflow, ITSM or infrastructure endpoint.

### Response And Replay Boundary

The API may return only opaque lineage IDs, track, classification, outcome, safe policy labels,
bounded redacted plain text, byte count, content and receipt digests, redaction/truncation state,
expiry and explicit decision-support boundary flags.

Responses use `Cache-Control: no-store`, `Pragma: no-cache`, `X-Content-Type-Options: nosniff`, a
restrictive content security policy and no-referrer policy. Content never enters URLs, cookies,
audit, logs, exceptions, traces, metrics, events, database records, browser local storage or
server-side session storage. The frontend renders it only as text.

Replay revalidates every authorization and cookie proof, reproduces the exact snapshot through the
trusted presenter and requires digest and byte-count equality with the immutable record. Replay
never extends the lease, changes redaction, widens content or creates a new presentation.

### Persistence And State

Claims and presentation metadata are immutable, deterministic, concurrency-safe and equivalent in
memory and PostgreSQL. The successful record contains no plaintext content, option text, cookie,
secret, browser identifier, storage coordinate, key or raw identity.

Success records `content_inspection_opened=true`, `content_disclosed=true` and a positive bounded
`protected_content_bytes_returned`. It leaves human findings, review completion, recommendation
approval, workflow, ITSM, execution, deployment and infrastructure mutation false.

### Failure And Audit

Required intent audit precedes claim creation. Claim, content-read and completion audit boundaries
identify the accountable subject without content or secret material. Failures before claim creation
read no content. Failures after claim creation remain claimed and return no partial content.
Presenter, persistence, audit, integrity, truncation or replay uncertainty fails closed.

## Consequences

### Positive

- Plaintext recommendation content exists only at the trusted presenter and current response boundary.
- Every disclosure is bound to exact immutable lineage, reviewer, track, browser and policy evidence.
- Refresh during an active lease can reproduce only the same verified snapshot.
- Presentation cannot silently become review or operational authority.

### Costs

- Production requires an isolated trusted presenter with deterministic redaction and cleanup.
- Expired leases cannot recover content and require a newly governed review cycle.
- Content is intentionally unavailable to caching, analytics, logs and client storage.

## Rejected Alternatives

### Return The Promoted Artifact Directly

Rejected because it bypasses lease proof, minimization, redaction, replay and disclosure audit.

### Persist Plaintext Presented Content

Rejected because it creates a second unmanaged copy outside the protected recommendation boundary.

### Let The Browser Select Fields Or Ranges

Rejected because caller-selected disclosure can bypass policy-defined minimization.

### Treat Presentation As A Review Decision

Rejected because evidence access and accountable human judgement require separate authority and audit.

## Follow-Up

Later independent contracts cover track-specific structured findings, finding presentation, review
decisions and correction, recommendation approval, workflow and ITSM handoff, suspension,
supersession, retention, controlled export and deletion.
