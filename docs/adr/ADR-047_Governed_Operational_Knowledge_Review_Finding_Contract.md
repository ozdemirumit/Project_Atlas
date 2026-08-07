# ADR-047: Governed Operational Knowledge Review Finding Contract

- Status: Accepted
- Date: 2026-08-07
- Owners: Product Owner, Solution Architecture, Security Architecture, Knowledge Management,
  Identity Governance, Data Governance
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-025, ATLAS-027, ATLAS-030, ATLAS-031,
  ATLAS-032, ATLAS-033, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-053, ATLAS-054, ATLAS-055,
  ATLAS-056, ADR-009 through ADR-046

## Context

ADR-046 lets the exact assigned reviewer inspect one immutable, redacted, bounded plain-text
snapshot inside an active browser-bound lease. Presentation deliberately records no finding or
review decision. The next stage must let that reviewer preserve observations from the inspected
snapshot without converting an observation into acceptance, rejection, correction, approval,
publication, workflow authority, or an operational action.

Finding narratives can contain sensitive operational knowledge. They must not become plaintext
application records, audit fields, logs, traces, metrics, events, browser storage, model context,
or retrieval content. Atlas therefore needs a separate trusted finding-recorder boundary and a
metadata-only application record.

## Decision

Atlas will implement an immutable, track-specific review-finding packet. One exact presentation
may produce at most one packet while its lease remains active. The packet contains one or more
bounded structured observations and is sealed by a trusted recorder into an encrypted artifact.
Atlas persists only lineage, policy, artifact, count, and integrity metadata.

### Caller Contract

The caller may provide only:

- exact presentation canonical digest and signed finding-policy ID and digest;
- one to twenty findings, each containing a policy-allowed category code, severity code, bounded
  summary, and bounded detail;
- a bounded review purpose;
- acknowledgement that the source evidence was inspected and that a finding is not a decision;
- idempotency and correlation identifiers.

Lease and presentation IDs come from the path. The caller cannot provide or override reviewer
identity, tenant, assignment, track, lease holder, browser binding, source artifact, content,
excerpt, range, redaction, category or severity catalogs, recorder, storage location, key,
classification, retention, access policy, decision, disposition, correction, approval,
publication, indexing, retrieval, model context, graph update, target, credential, command,
schedule, workflow, execution, deployment, or mutation fields.

### Finding Semantics

A finding is an accountable human observation about inspected evidence. It is not a verdict.

- Category describes the concern domain, such as accuracy, completeness, applicability,
  operational safety, evidence conflict, data exposure, privilege, prompt injection, malware,
  supply chain, policy compliance, or clarity.
- Severity expresses the reviewer-perceived importance of the observation using the signed
  policy catalog. It does not authorize priority, remediation, escalation, rejection, or action.
- Summary and detail are reviewer-authored evidence observations. They are untrusted sensitive
  input and never become executable instructions.
- A packet requires at least one finding. A reviewer with no finding proceeds to a later decision
  contract without creating an empty or implicit-approval packet.

Domain and security tracks use independently allowlisted category catalogs. The service derives
the track from immutable lease and presentation lineage. Cross-track category use fails closed.

### Authorization And Lease Proof

Before claim creation the service revalidates:

- complete immutable connector, evidence, draft, review request, assignment, lease, and
  presentation lineage;
- exact lease and presentation IDs and digests, organization, environment, track, artifact,
  classification, access, retention, encryption, source-content, and presentation-policy bindings;
- the signed finding policy, trusted recorder identity, receipt schema, category and severity
  catalogs, input limits, artifact integrity, encryption, immutable-write, and cleanup rules;
- a current enterprise human identity with recent hardware-backed MFA, exact tenant scope,
  dedicated C2 finding-create and presentation/lease-read permissions;
- the salted current-subject digest equals the lease holder and exact assigned reviewer;
- the normal browser session hashes to the lease browser binding;
- the track-specific HttpOnly lease cookie hashes to the stored lease-secret digest;
- lease, assignment, subject, account, and session remain active and no later finding, decision,
  correction, approval, publication, workflow, execution, deployment, or mutation authority exists.

Missing, malformed, expired, revoked, transferred, cross-track, or mismatched proofs fail before
claim creation and before finding content crosses the recorder boundary.

### Atomic Finding Claim

Required intent audit succeeds before a unique immutable source-presentation claim is created.
Claim creation is the point of no return. An existing claim is reusable only when exact subject,
browser, lease, presentation, request binding, and idempotency digests match a completed record.

Failure or uncertainty after claim creation remains claimed and is not retried automatically.
Concurrent second claims for the same presentation cannot create another packet or overwrite the
first result.

### Trusted Finding Recorder Boundary

Atlas sends the trusted recorder only exact immutable presentation and draft lineage, inherited
governance labels, derived track, policy limits, packet ID, and the bounded normalized findings.
The trusted recorder must:

1. validate packet, presentation, track, tenant, classification, and governance bindings;
2. reject unknown categories, severities, active payloads, embedded objects, and excess limits;
3. normalize findings deterministically as inert UTF-8 structured data;
4. write one immutable encrypted artifact in the policy-approved finding store;
5. compute finding-content, metadata, lineage, access, retention, encryption, and cleanup digests;
6. erase plaintext working buffers and close artifact and encryption channels in every outcome;
7. return only a signed minimized receipt to the application boundary.

Production fails closed when no trusted recorder is configured. Development may use a
deterministic synthetic recorder. It cannot contact a target, directory, model, vector store,
workflow, deployment system, or infrastructure endpoint.

### Persistence And Response Boundary

The immutable application record uses state `operational_knowledge_review_finding_recorded` and
contains exact source lineage, packet and claim IDs, derived track, salted holder and browser
bindings, inherited governance labels, opaque artifact ID, item and byte counts, safe category and
severity catalog digests, content and metadata digests, recorder and policy identities,
timestamps, purpose, and canonical digest.

It contains no finding summary or detail, raw content, excerpt, raw identity, cookie, secret,
browser identifier, storage coordinate, key, token, signature, request fingerprint, or
idempotency material. API responses further omit the artifact ID and return only minimized safe
metadata. Responses use no-store, no-cache, nosniff, no-referrer, and restrictive CSP controls.

Finding content never appears in audit, logs, exceptions, traces, metrics, events, browser local
or session storage, server-side session storage, model context, vector stores, retrieval indexes,
or graph records.

### A Finding Is Not A Decision

Recording a finding sets only `finding_recorded=true` and the derived domain or security finding
flag. Domain and security review completion, disposition, correction, approval, rejection,
publication, chunks, embeddings, retrieval, model context, graph update, scheduling, workflow,
execution, deployment, and infrastructure mutation remain false.

Later independent contracts may read the sealed finding artifact inside a protected boundary and
record accountable track decisions. They cannot reinterpret the existence, absence, category, or
severity of a finding as an automatic decision.

### Read And Replay

An audited `GET` may return only the immutable metadata record while the same lease, presentation,
assignee, browser session, track cookie, and policy remain current. It never returns finding
content or an artifact location, refreshes the lease, changes the packet, or grants cross-track
access.

### Failure And Audit

Intent audit precedes claim creation. Claim audit follows a successful claim. Completion audit
must succeed after a verified recorder receipt and before metadata persistence. Every metadata
read has a separate audit event. Audit identifies the accountable enterprise subject and safe
track but contains no finding content or secret material.

Authorization, audit, recorder, persistence, integrity, encryption, immutable-write, or cleanup
uncertainty fails closed. Failure after claim creation returns no partial receipt and remains
claimed.

### Persistence And API

Claims and records are immutable, deterministic, concurrency-safe, and equivalent in memory and
PostgreSQL. The API uses the normal browser session, the track-specific lease cookie, mutation
CSRF, strict schemas, dedicated default-deny RBAC, C2 classification, recent hardware MFA, exact
tenant and assignee scope, safe errors, and minimized no-store responses.

## Consequences

### Positive

- Reviewer observations become durable evidence without becoming implicit decisions.
- Sensitive narratives remain outside application persistence and telemetry.
- Track separation, exact-assignee accountability, and immutable source lineage are preserved.
- Later decision and correction stages can consume a sealed, integrity-bound finding artifact.

### Costs

- Production requires a trusted encrypted finding recorder and protected artifact store.
- Finding content needs a later separately governed presentation contract for redisplay.
- A claimed uncertain submission requires governed recovery instead of automatic retry.

## Rejected Alternatives

### Store Finding Narratives In PostgreSQL

Rejected because sensitive operational observations would become an unmanaged plaintext copy.

### Treat Severity As A Decision

Rejected because severity is a reviewer observation and cannot grant acceptance, rejection,
priority, remediation, escalation, or operational authority.

### Allow Findings After Lease Expiry

Rejected because accountable findings must remain bound to the exact evidence presentation and
current reviewer proof.

### Send Findings To An LLM Before Recording

Rejected because reviewer-authored observations do not require model mediation and must not enter
model context at this stage.

## Follow-Up

Later independent lifecycle contracts cover protected finding presentation, track-specific review
decisions, correction and resubmission, approval or rejection, chunking and embedding,
retrieval-index validation and publication, suspension, supersession, retention, and deletion.
