# ADR-075: Governed Recommendation Protected Finding Presentation Contract

- Status: Accepted
- Date: 2026-08-10
- Owners: Product Owner, Solution Architecture, Security Architecture, Infrastructure Operations,
  Identity Governance, Data Governance
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-026, ATLAS-027,
  ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-040, ATLAS-041, ATLAS-042,
  ATLAS-043, ATLAS-044, ATLAS-046, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-052, ATLAS-053,
  ATLAS-054, ATLAS-055, ATLAS-056, ADR-009 through ADR-074

## Context

ADR-074 lets the exact assigned technical or service-impact reviewer record one immutable packet
of bounded findings after inspecting an exact recommendation presentation. Atlas persists only
metadata while a trusted recorder places finding narratives in an encrypted immutable artifact.
No accountable decision may rely on browser memory, caller-supplied copies or plaintext
application persistence. The next stage must therefore redisplay that exact packet inside a
separately governed boundary before a later independent decision contract can use it.

## Decision

Atlas will implement a dedicated recommendation protected-finding presentation service. A first
audited `POST` creates one immutable presentation record for an existing finding packet and
returns the exact bounded inert findings from the sealed artifact. A later audited `GET` may
reproduce only that same snapshot while the original recommendation lineage, assignment, lease,
browser session, selected track and presentation policy remain current.

### Caller Contract

The first-presentation caller may provide only:

- the exact finding packet canonical digest;
- the exact signed finding-presentation-policy ID and digest;
- a bounded review purpose;
- acknowledgement that findings are sensitive observations and not decisions;
- idempotency and correlation identifiers.

Recommendation, lease, protected-content presentation and finding IDs come from the path. The
caller cannot provide or override identity, tenant, assignment, track, browser binding, finding
count or content, category, severity, artifact location, key, decryption material,
classification, governance labels, limits, decision, disposition, correction, approval,
workflow, ITSM, command, schedule, execution, deployment or mutation fields.

The replay caller supplies only the opaque finding-presentation ID in the path. Atlas derives all
source, policy, access and browser bindings from trusted records and cookies.

### Authorization And Lineage Proof

Before artifact access the service revalidates:

- complete immutable connector, recommendation, promotion, readiness, review request, assignment,
  inspection lease, protected-content presentation and human-finding lineage;
- exact canonical digests, selected technical or service-impact track, artifact and content
  digests, policy catalogs, classification, access, retention, encryption and cleanup labels;
- a signed presentation policy with trusted presenter identity and attestor, required source
  state and schema, receipt schema, item and byte limits, permitted media type and cleanup rules;
- a current enterprise human identity with recent hardware-backed MFA, exact tenant scope and
  dedicated C2 finding-presentation plus C1 finding-metadata, content-presentation and lease-read
  permissions;
- the salted current-subject digest equals the exact lease holder and assigned reviewer;
- the browser session hashes to the lease browser binding and the track-specific HttpOnly lease
  cookie hashes to the stored lease-secret digest;
- lease, assignment, subject, account and session remain active and no decision, correction,
  approval, workflow, ITSM, execution, deployment or mutation authority exists.

Missing, malformed, expired, revoked, transferred, cross-track or mismatched proofs fail before
claim creation and before finding content crosses the trusted presenter boundary.

### Atomic Presentation Claim

Required intent audit succeeds before a unique immutable source-finding claim is created. Claim
creation is the point of no return. An existing claim is reusable only when exact subject,
browser, lease, finding, request binding and idempotency digests match a completed record.

Failure or uncertainty after claim creation remains claimed and is never retried automatically by
the first-presentation endpoint. Concurrent attempts cannot disclose another snapshot or
overwrite the first result.

### Trusted Recommendation Finding Presenter

The application sends only trusted immutable recommendation and finding lineage, expected
artifact and content digests, inherited governance labels, derived track, signed limits,
subject/session binding digests and an opaque presentation ID. The trusted presenter must:

1. resolve only the encrypted immutable finding artifact bound to the source packet;
2. validate artifact identity, protected-content presentation, track, tenant, classification,
   access, retention, encryption, category/severity catalogs and content digests;
3. decrypt only inside the protected presenter boundary;
4. reject active payloads, executable content, external references, unsupported schemas, unknown
   categories or severities and excess item or byte limits;
5. normalize the packet deterministically as ordered inert UTF-8 structured findings;
6. preserve exact category, severity, summary and detail values without model transformation;
7. compute content, metadata, lineage, access, retention, encryption and cleanup digests;
8. erase plaintext working buffers and close artifact and decryption channels in every outcome;
9. return the bounded findings plus a signed minimized receipt to the application boundary.

Production fails closed when no trusted presenter is configured. Development may use a
deterministic synthetic presenter bound only to synthetic recommendation finding lineage; it
cannot contact an infrastructure target, connector, directory, model, vector store, workflow,
ITSM system, deployment system or command executor.

### Response And Persistence Boundary

The API may return only opaque lineage identifiers, selected track, title, classification, safe
policy labels, ordered structured findings, item and byte counts, expiry, content and receipt
digests and explicit flags that disclosure is read-only and no decision exists. It never returns
artifact location, storage coordinates, keys, cookies, session bindings, raw identities or
operational authority.

Responses use `Cache-Control: no-store`, `Pragma: no-cache`, `X-Content-Type-Options: nosniff`, a
restrictive content security policy and no referrer policy. Finding content never appears in URLs,
cookies, audit, logs, exceptions, traces, metrics, events, database records, browser local or
session storage, server-side session storage, model context, vector stores, retrieval indexes or
graph records. The frontend renders every finding value as text, never as HTML.

The immutable application record uses state
`recommendation_human_review_finding_presented`. It contains metadata and integrity evidence only:
exact source lineage, claim and presentation IDs, derived track, salted holder and browser
bindings, policy and presenter identities, inherited governance labels, counts, digests,
timestamps, expiry, purpose and canonical digest. It contains no finding narrative or artifact
location.

### Replay Within The Same Lease

An audited `GET` may ask the trusted presenter to reproduce the exact snapshot while every proof
remains current. Reproduced content, metadata, item count and byte count must match the immutable
presentation record. Drift, missing artifacts, uncertainty, expiry or changed authority fails
closed and returns no partial findings.

Replay never extends the lease, creates another finding packet or presentation, changes content,
widens access or grants cross-track authority.

### Presentation Is Not A Decision

Successful disclosure sets only `human_findings_presented=true` and the matching technical or
service-impact presentation flag. Human review completion, disposition, correction,
recommendation approval, workflow, ITSM, scheduling, execution, deployment and infrastructure
mutation remain false. Finding absence, presence, category or severity cannot be interpreted as
acceptance, rejection, priority or approval.

### Failure And Audit

Intent audit precedes claim creation; claim audit follows a successful claim; content-read audit
must succeed before any content response; completion audit succeeds before metadata persistence;
and every replay has a separate read audit. Audit identifies the accountable enterprise subject
and safe track but never includes finding content, artifact coordinates, cookies or secrets.

Failures before claim creation do not read the artifact. Failures after claim creation remain
claimed and return no partial findings. Presenter, audit, persistence, integrity, cleanup, replay
or authorization uncertainty fails closed.

### Persistence And API

Claims and records are immutable, deterministic, concurrency-safe and equivalent in memory and
PostgreSQL. The API uses the normal browser session, track-specific lease cookie, mutation CSRF
for first presentation, strict schemas, dedicated default-deny RBAC, C2 classification, recent
hardware MFA, exact tenant and assignee scope, minimized no-store responses and safe errors.

## Consequences

### Positive

- Later review decisions can use the exact sealed observations rather than caller-supplied copies.
- Sensitive narratives remain outside application persistence and telemetry.
- Same-reviewer, same-track and same-browser accountability survives redisplay.
- Content drift or artifact substitution fails before a decision can rely on findings.

### Costs

- Production requires an independent trusted finding presenter and encrypted artifact access.
- The original short-lived inspection lease must remain active; expiry requires a newly governed
  review cycle rather than lease extension.
- Finding presentation cannot use generic caches, analytics, client storage or model context.

## Rejected Alternatives

### Return Findings From The Metadata Endpoint

Rejected because it collapses the trusted artifact boundary and creates uncontrolled plaintext
copies.

### Let A Decision Request Repeat Finding Text

Rejected because caller-supplied observations are not evidence of the sealed packet actually
recorded by the accountable reviewer.

### Treat Presentation As Review Completion

Rejected because evidence access and accountable judgment require separate authority and audit.

### Extend The Lease During Replay

Rejected because redisplay must not silently expand the original inspection authority.

## Follow-Up

Later independent contracts cover track-specific review decisions, correction, final
recommendation disposition, workflow/ITSM handoff and any separately approved operation.
