# ADR-048: Governed Operational Knowledge Protected Finding Presentation Contract

- Status: Accepted
- Date: 2026-08-07
- Owners: Product Owner, Solution Architecture, Security Architecture, Knowledge Management,
  Identity Governance, Data Governance
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-025, ATLAS-027, ATLAS-030, ATLAS-031,
  ATLAS-032, ATLAS-033, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-053, ATLAS-054, ATLAS-055,
  ATLAS-056, ADR-009 through ADR-047

## Context

ADR-047 lets the exact assigned reviewer record one immutable, track-specific packet of bounded
findings after inspecting the exact draft presentation. Atlas persists only metadata while a
trusted recorder places finding narratives in an encrypted immutable artifact. A later decision
cannot safely depend on browser memory, caller-supplied findings, or plaintext application
persistence. The next stage must therefore redisplay that exact sealed packet inside a separately
governed boundary before any accountable decision is recorded.

## Decision

Atlas will implement a dedicated protected-finding presentation service. A first audited `POST`
creates one immutable presentation record for an existing finding packet and returns the exact
bounded, inert findings from the sealed artifact. A later audited `GET` may reproduce only that
same snapshot while the original lease, browser session, assignee, track cookie, source artifact,
and presentation policy remain current.

### Caller Contract

The first-presentation caller may provide only:

- exact finding packet ID and canonical digest;
- exact signed finding-presentation-policy ID and digest;
- a bounded review purpose;
- acknowledgement that findings are sensitive observations and not decisions;
- idempotency and correlation identifiers.

The caller cannot provide or override reviewer identity, tenant, assignment, track, lease,
browser binding, finding count or content, category, severity, summary, detail, artifact location,
key, decryption material, classification, access, retention, redaction, renderer, limit, decision,
disposition, correction, approval, publication, indexing, retrieval, model context, target,
credential, command, schedule, workflow, execution, deployment, or mutation fields.

The replay caller supplies only the opaque finding-presentation ID in the path. Atlas derives all
source, policy, access, and browser bindings from trusted records and cookies.

### Authorization And Lease Proof

Before artifact access the service revalidates:

- complete immutable connector, evidence, draft, review request, assignment, lease, content
  presentation, and finding lineage;
- exact finding packet, source presentation, lease, assignment, track, artifact, content,
  category/severity catalog, classification, access, retention, encryption, and cleanup digests;
- the signed presentation policy, trusted presenter identity and attestor, required source schema
  and state, receipt schema, item and byte limits, permitted media type, and cleanup rules;
- a current enterprise human identity with recent hardware-backed MFA, exact tenant scope, and
  dedicated C2 finding-presentation, finding-metadata-read, presentation-read, and lease-read
  permissions;
- the salted current-subject digest equals both the lease holder and exact assigned reviewer;
- the normal browser session hashes to the lease browser binding and the track-specific HttpOnly
  lease cookie hashes to the stored lease-secret digest;
- lease, assignment, subject, account, and session remain active and no later decision,
  correction, approval, publication, workflow, execution, deployment, or mutation authority
  exists.

Missing, malformed, expired, revoked, transferred, cross-track, or mismatched proofs fail before
claim creation and before finding content crosses the trusted presenter boundary.

### Atomic Presentation Claim

Required intent audit succeeds before a unique immutable source-finding claim is created. Claim
creation is the point of no return. An existing claim is reusable only when exact subject,
browser, lease, finding, request binding, and idempotency digests match a completed record.

Failure or uncertainty after claim creation remains claimed and is never retried automatically by
the first-presentation endpoint. Concurrent attempts cannot disclose another snapshot or
overwrite the first result.

### Trusted Finding Presenter Boundary

The application sends the presenter only trusted immutable finding lineage, expected artifact and
content digests, governance labels, derived track, limits, subject/session binding digests, and an
opaque finding-presentation ID. The trusted presenter must:

1. resolve only the encrypted immutable finding artifact bound to the source packet;
2. validate artifact identity, source presentation, track, tenant, classification, access,
   retention, encryption, category/severity catalogs, and content digests;
3. decrypt only inside the protected presenter boundary;
4. reject active payloads, executable content, external references, unsupported schemas, unknown
   categories or severities, and excess item or byte limits;
5. normalize the packet deterministically as ordered inert UTF-8 structured findings;
6. preserve exact category, severity, summary, and detail values without model transformation;
7. compute content, metadata, lineage, access, retention, encryption, and cleanup digests;
8. erase plaintext working buffers and close artifact and decryption channels in every outcome;
9. return the bounded findings plus a signed minimized receipt to the application boundary.

Production fails closed when no trusted presenter is configured. Development may use a
deterministic synthetic presenter bound only to synthetic finding lineage; it cannot contact an
infrastructure target, directory, model, vector store, workflow, deployment system, or command
executor.

### Response And Persistence Boundary

The API may return only opaque lineage identifiers, selected track, title, classification, safe
policy labels, ordered structured findings, item and byte counts, expiry, content and receipt
digests, and explicit flags that disclosure is read-only and no decision exists. It never returns
artifact location, storage coordinates, keys, cookies, session bindings, raw identities, or
operational authority.

Responses use `Cache-Control: no-store`, `Pragma: no-cache`, `X-Content-Type-Options: nosniff`, a
restrictive content security policy, and no referrer policy. Finding content never appears in
URLs, cookies, audit, logs, exceptions, traces, metrics, events, database records, browser local
or session storage, server-side session storage, model context, vector stores, retrieval indexes,
or graph records. The frontend renders all finding values as text, never as HTML.

The immutable application record uses state
`operational_knowledge_review_finding_presented`. It contains metadata and integrity evidence
only: exact source lineage, claim and presentation IDs, derived track, salted holder and browser
bindings, policy/presenter identities, classification and governance labels, counts, digests,
timestamps, expiry, purpose, and canonical digest. It contains no finding narrative or artifact
location.

### Replay Within The Same Lease

An audited `GET` may ask the trusted presenter to reproduce the exact snapshot while every proof
remains current. Reproduced content, metadata, item count, and byte count must match the immutable
presentation record. Drift, missing artifacts, uncertainty, expiry, or changed authority fails
closed and returns no partial findings.

Replay never extends the lease, creates another finding packet or presentation, changes content,
widens access, or grants cross-track authority.

### Presentation Is Not A Decision

Successful disclosure sets only `finding_presented=true`. The source finding flags remain true,
but domain and security review completion, disposition, correction, approval, publication,
chunks, embeddings, retrieval, model context, graph update, scheduling, workflow, execution,
deployment, and infrastructure mutation remain false. Finding absence, presence, category, or
severity cannot be interpreted as acceptance, rejection, or approval.

### Failure And Audit

Intent audit precedes claim creation; claim audit follows a successful claim; content-read audit
must succeed before any content response; completion audit succeeds before metadata persistence;
and every replay has a separate read audit. Audit identifies the accountable enterprise subject
and safe track but never includes finding content, artifact coordinates, cookies, or secrets.

Failures before claim creation do not read the artifact. Failures after claim creation remain
claimed and return no partial findings. Presenter, audit, persistence, integrity, cleanup, replay,
or authorization uncertainty fails closed.

### Persistence And API

Claims and records are immutable, deterministic, concurrency-safe, and equivalent in memory and
PostgreSQL. The API uses the normal browser session, track-specific lease cookie, mutation CSRF
for first presentation, strict schemas, dedicated default-deny RBAC, C2 classification, recent
hardware MFA, exact tenant and assignee scope, minimized no-store responses, and safe errors.

## Consequences

### Positive

- Review decisions can use the exact sealed observations rather than caller-supplied copies.
- Sensitive narratives remain outside application persistence and telemetry.
- Same-reviewer, same-track, same-browser accountability is preserved through redisplay.
- Content drift or artifact substitution fails before a decision stage can rely on it.

### Costs

- Production requires an independent trusted finding presenter and encrypted artifact access.
- The original short-lived inspection lease must remain active; expiry requires a newly governed
  review cycle rather than lease extension.
- Finding presentation cannot use generic caches, analytics, client storage, or model context.

## Rejected Alternatives

### Return Findings From The Metadata Endpoint

Rejected because it collapses the trusted artifact boundary and creates uncontrolled plaintext
copies.

### Let The Decision Request Repeat Finding Text

Rejected because caller-supplied observations are not evidence of the sealed packet that was
actually recorded.

### Treat Finding Presentation As Track Completion

Rejected because evidence access and accountable judgment require separate authority and audit.

### Extend The Lease During Replay

Rejected because redisplay must not silently expand the original inspection authority.

## Follow-Up

Later independent lifecycle contracts cover track-specific review decisions, correction and
resubmission, approval or rejection, chunking and embedding, retrieval-index validation and
publication, suspension, supersession, retention, and deletion.
