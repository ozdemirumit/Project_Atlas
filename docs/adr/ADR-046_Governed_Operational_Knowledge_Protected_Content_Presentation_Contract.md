# ADR-046: Governed Operational Knowledge Protected Content Presentation Contract

- Status: Accepted
- Date: 2026-08-06
- Owners: Product Owner, Solution Architecture, Security Architecture, Knowledge Management,
  Identity Governance, Data Governance
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-025, ATLAS-027, ATLAS-030, ATLAS-031,
  ATLAS-032, ATLAS-033, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-053, ATLAS-054, ATLAS-055,
  ATLAS-056, ADR-009 through ADR-045

## Context

ADR-045 creates a maximum-ten-minute, browser-bound, track-specific inspection lease for the
exact assigned reviewer. Lease issuance deliberately returns no draft content and records no
finding or decision. The next stage must disclose only the exact immutable draft version inside
that lease boundary without turning content delivery into reusable artifact access.

Atlas core records contain content and provenance digests, not plaintext operational knowledge.
Content must therefore cross a trusted presentation boundary, be bounded and redacted before it
reaches the browser, and never be persisted by the presentation service.

## Decision

Atlas will implement a dedicated protected-content presentation service. A first audited `POST`
creates one immutable presentation record for an active lease and returns one bounded redacted
snapshot. A later audited `GET` may reproduce only that exact snapshot while the same lease,
browser session, assignee, track cookie, and source artifact remain current.

### Caller Contract

The first-presentation caller may provide only:

- exact lease ID and canonical digest;
- exact signed presentation-policy ID and digest;
- a bounded inspection purpose;
- acknowledgement that content is sensitive, read-only, and grants no review authority;
- idempotency and correlation identifiers.

The caller cannot provide or override reviewer identity, subject digest, assignment, track,
content, excerpt, range, field selection, query, storage location, artifact key, decryption key,
cookie or lease secret, redaction rule, byte limit, renderer, decision, finding, correction,
approval, publication, parser, chunker, embedding model, retrieval, model context, target,
credential, command, schedule, workflow, execution, deployment, or mutation fields.

The replay caller supplies only the opaque presentation ID in the path. Atlas derives the lease,
track, policy, content boundary, and access context from trusted records and cookies.

### Authorization And Lease Proof

Before content access the service revalidates:

- the complete immutable connector, evidence, draft, review request, assignment, and lease lineage;
- exact lease ID/digest, schema, tenant, track, opaque assignment, holder digest, browser binding,
  artifact, manifest, governance, broker, expiry, immutable-write, and cleanup bindings;
- the signed presentation policy, trusted presenter identity, source schema/state, maximum bytes,
  permitted media type, redaction profile, replay rule, and content-integrity requirements;
- a current enterprise human identity with hardware-backed MFA, exact tenant scope, dedicated C2
  content-presentation and lease-read permissions, and authentication no older than the policy;
- the salted current-subject digest equals the lease holder and assigned reviewer for that track;
- the normal browser session hashes to the lease browser binding;
- the track-specific HttpOnly cookie secret hashes to the stored lease-secret digest;
- lease, assignment, subject, account, and session remain active and no later decision,
  correction, approval, publication, retrieval, workflow, execution, deployment, or mutation
  authority exists.

Missing, malformed, cross-track, expired, revoked, transferred, or mismatched cookies fail as a
safe not-found or authorization error. A domain cookie cannot open security content and a security
cookie cannot open domain content.

### Atomic Presentation Claim

After intent audit succeeds and before the presenter reads the artifact, the repository creates an
immutable claim with a unique constraint on lease ID. Claim creation is the point of no return.

An existing claim is reusable only when exact subject, browser binding, request binding,
idempotency, and completed presentation evidence match. Otherwise the request fails as already
claimed. Failure or uncertainty after claim creation remains claimed and is not retried
automatically by the first-presentation endpoint.

### Trusted Presenter Boundary

The application sends only trusted draft artifact lineage, expected artifact/content digests,
classification and policy labels, selected track, lease/subject/session binding digests, permitted
content type, redaction profile, maximum output bytes, and presentation ID.

The trusted presenter must:

1. resolve only the exact immutable encrypted draft artifact bound to the lease;
2. verify artifact identity, version, source digest, tenant, classification, and access labels;
3. decrypt only inside the protected presenter boundary;
4. reject active content, executable payloads, external references, and unsupported media types;
5. apply the policy-selected deterministic redaction profile before disclosure;
6. normalize output as bounded UTF-8 plain text with stable ordered sections;
7. enforce the maximum output-byte limit after redaction without splitting a UTF-8 sequence;
8. compute presented-content, source-binding, redaction, truncation, and cleanup digests;
9. erase plaintext working buffers and close artifact/decryption channels in every outcome;
10. return the bounded content plus a signed minimized receipt to the application boundary.

Production fails closed when no trusted presenter is configured. Development may use a
deterministic synthetic presenter bound to synthetic draft lineage; it cannot contact a target,
directory, model, vector store, workflow, deployment system, or infrastructure endpoint.

### Content Response Boundary

The API may return only:

- opaque presentation, lease, assignment, review request, draft, and knowledge version IDs;
- selected track, title, language, plain-text media type, classification, and safe policy labels;
- redacted bounded content;
- presented byte count, content digest, redaction/truncation flags, expiry, and safe receipt
  digests;
- explicit flags showing that content was disclosed read-only and no finding or decision exists.

Responses use `Cache-Control: no-store`, `Pragma: no-cache`, `X-Content-Type-Options: nosniff`, a
restrictive content security policy, and no referrer policy. Content never appears in URLs,
cookies, audit, logs, exceptions, traces, metrics, event payloads, database records, browser local
storage, or server-side session storage. The frontend renders content as text and never as HTML.

### Replay Within The Same Lease

After successful first presentation, `GET` may ask the trusted presenter to reproduce the exact
snapshot while the lease remains active. The service revalidates every authorization and cookie
proof, requires the reproduced digest and byte count to equal the immutable presentation record,
and audits each read. Drift, missing artifacts, uncertainty, or expired authority fails closed and
returns no partial content.

Replay never extends or refreshes the lease, creates another presentation, changes redaction,
widens content, or grants cross-track access.

### Presentation Record

A successful immutable record uses state `operational_knowledge_protected_content_presented` and
contains complete lease and draft lineage, presentation/lease/track identifiers, salted holder and
browser bindings, policy/presenter identities, classification and governance labels, presented
content digest and byte count, source/redaction/truncation/cleanup digests, timestamps, expiry,
purpose, and canonical digest.

The record contains no plaintext content, excerpt, token, cookie, secret, browser identifier,
storage coordinate, key, or raw identity. It records `content_inspection_opened=true`,
`content_disclosed=true`, and a positive bounded `content_bytes_read`. Domain/security findings and
decisions, correction, approval, publication, chunks, embeddings, retrieval, model context, graph
update, scheduling, workflow, execution, deployment, and infrastructure mutation remain false.

### Content Is Not A Review Decision

Presentation provides evidence for the assigned reviewer to inspect. It does not accept, reject,
approve, correct, annotate, publish, index, retrieve, call a model, continue a workflow, or
authorize any operational action. Domain and security findings and decisions require later
independent contracts.

### Failure And Audit

Required intent audit precedes first-presentation claim creation. Claim audit follows a successful
atomic claim. Content-read audit must succeed before any content response. Completion audit must
succeed before presentation metadata is persisted. Replay has a separate read audit on every
request. Audit identifies the accountable enterprise subject but never contains content or secret
material.

Failures before claim creation read no artifact. Failures after claim creation remain claimed and
return no partial content. Presenter, persistence, audit, integrity, truncation, or replay
uncertainty fails closed and is not reported as successful disclosure.

### Persistence And API

Claims and presentation metadata are immutable, deterministic, concurrency-safe, and equivalent
in memory and PostgreSQL. The API uses normal browser session, track-specific lease cookie,
mutation CSRF for first presentation, strict schemas, no-store, dedicated default-deny RBAC, C2
classification, recent hardware MFA, exact tenant and assignee scope, safe errors, and minimized
responses.

## Consequences

### Positive

- Plaintext knowledge exists only at the trusted presenter and current browser response boundary.
- A copied JSON response cannot be replayed to obtain future or cross-track access.
- Every disclosure is bound to exact immutable lineage and independently audited.
- Refresh during an active lease can reproduce only the same verified snapshot.

### Costs

- Production requires a trusted artifact presenter, decryption isolation, redaction, and cleanup.
- Browser refresh after lease expiry cannot recover content and requires a newly governed review
  cycle rather than silent lease extension.
- Content is intentionally unavailable to generic caching, analytics, logging, or client storage.

## Rejected Alternatives

### Store Plaintext Presentation Content In PostgreSQL

Rejected because it creates a second unmanaged copy outside the governed artifact boundary.

### Let The Browser Select Ranges Or Fields

Rejected because caller-selected disclosure can bypass policy-defined minimization and redaction.

### Render Markdown Or HTML Directly

Rejected because active content and unsafe links create an avoidable browser execution boundary.

### Treat Presentation As A Review Decision

Rejected because evidence access and accountable judgment require separate audit and authority.

## Follow-Up

Later independent lifecycle contracts cover track-specific findings and decisions, correction and
resubmission, approval or rejection, chunking and embedding, retrieval-index validation and
publication, suspension, supersession, retention, and deletion execution.
