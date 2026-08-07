# ADR-051: Governed Operational Knowledge Final Resolution Contract

- Status: Accepted
- Date: 2026-08-07
- Owners: Product Owner, Solution Architecture, Security Architecture, Knowledge Management,
  Identity Governance, Data Governance
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-025, ATLAS-027, ATLAS-030, ATLAS-031,
  ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-052, ATLAS-053,
  ATLAS-054, ATLAS-055, ATLAS-056, ADR-009 through ADR-050

## Context

ADR-049 records independent domain and security decisions, while ADR-050 creates a fresh immutable
draft and review generation when either track requires correction. Atlas now needs an accountable
human resolution for a generation whose two exact tracks both passed. This resolution must remain
separate from curation, review, publication, indexing, retrieval, and operational authority.

## Decision

Atlas will implement one dedicated final-resolution service. One audited `POST` binds an eligible
human approver's `approved` or `rejected` decision to the exact completed, unchanged review
generation. An audited `GET` returns minimized immutable resolution metadata.

### Eligibility

The service proceeds only when:

- the exact domain and security decisions exist for the same immutable review request, assignment
  set, draft, review generation, and policy generation;
- both track dispositions are `review-disposition.passed` and neither requires correction;
- no correction, replacement generation, prior resolution claim, or completed resolution exists
  for the review request; and
- source, governance, classification, access, retention, encryption, organization, environment,
  and knowledge-item lineage remain exact and internally consistent.

A missing track, duplicate track, mixed generation, `changes-required` result, corrected or
superseded request, caller-shaped lifecycle state, or lineage drift fails before claim creation.

### Caller Contract

The caller may provide only:

- exact review-request ID and canonical digest;
- exact decision IDs and canonical digests for both tracks;
- `final-resolution.approved` or `final-resolution.rejected`;
- policy-approved structured basis codes;
- exact signed final-resolution-policy ID and digest;
- a bounded resolution purpose;
- acknowledgements that the reviewed generation is immutable, that approval is publication
  readiness only, and that no publication, retrieval, workflow, execution, deployment, or
  infrastructure mutation authority is granted; and
- idempotency and correlation identifiers.

The caller cannot provide identity, tenant, approver, reviewer, curator, content, findings,
free-form rationale, governance labels, approval state, publication state, artifact location,
index, model context, target, credential, command, schedule, workflow, execution, deployment, or
mutation fields.

### Identity And Separation

The actor must be a current enterprise human in the exact tenant with recent hardware-backed MFA,
dedicated C2 final-resolution-create and lineage-read permissions, browser binding, CSRF, and a
current signed policy. The actor cannot be the curator, either track reviewer, policy signer,
trusted attestor, or a service, shared, AI, or break-glass identity.

### Trusted Attestation Boundary

An approved trusted attestor signs the exact request, draft, assignment aggregate, both decision
bindings, approver binding, disposition, basis codes, purpose, policy, and deterministic resolution
identifier. Production fails closed without an approved attestor. Development may use a
deterministic synthetic attestor with no model, connector, workflow, credential, target, index, or
infrastructure access.

### Atomic Claim And Replay

Required intent audit succeeds before a unique immutable review-request claim is created. The claim
is the point of no return. Exact completed idempotent reuse is permitted only when lineage,
approver, disposition, basis, policy, purpose, and request-binding digests match. Failure or
uncertainty after claim creation remains claimed and is never retried automatically. Concurrent or
conflicting resolutions cannot replace the first claim.

### Persistence And Lifecycle Semantics

Application persistence stores immutable metadata and integrity digests only. It stores no content,
finding narrative, free-form rationale, artifact coordinate, cookie, raw identity, secret, or
model output.

An approved result records `operational_knowledge_final_approved`, sets knowledge approval and
publication-readiness evidence true, and leaves publication, chunking, embedding, retrieval,
model-context, graph, workflow, execution, deployment, and mutation false. A rejected result records
`operational_knowledge_final_rejected` and leaves both approval and publication readiness false.
Neither result publishes content, creates an index, starts a workflow, or authorizes an operation.

All drafts, requests, assignments, leases, presentations, findings, track decisions, and corrections
remain immutable. Rejection is final for that exact generation and creates no correction or
replacement draft; any later revision requires a separate approved lifecycle contract.

### Read, Failure, And Audit

Only the accountable final approver may read minimized resolution metadata while identity, tenant,
policy, browser, and permission authority remain current. Responses use strict `no-store`,
`nosniff`, no-referrer, and restrictive content-security headers.

Intent, claim, attestation, persistence completion, and read are separately audited. Audit excludes
content, findings, free-form rationale, artifact coordinates, cookies, raw identity, and secrets.
Policy, lineage, permission, MFA, separation, browser, attestor, persistence, audit, concurrency, or
integrity uncertainty fails closed.

## Consequences

### Positive

- Final knowledge approval is attributable, immutable, and distinct from curation and review.
- Passing reviewers cannot publish or approve their own generated knowledge.
- Rejection remains first-class and cannot be converted into approval by replay or concurrency.
- Publication receives explicit readiness evidence without being coupled to this decision.

### Costs

- Production requires an approved trusted final-resolution attestor.
- A separate eligible approver and recent hardware MFA are required after both reviews pass.
- Rejected generations require a later explicit revision contract rather than silent reuse.

## Rejected Alternatives

### Treat Two Review Passes As Final Approval

Rejected because independent review and accountable knowledge approval are separate authorities.

### Approve And Publish In One Operation

Rejected because publication, index validation, and retrieval eligibility require separate atomic
controls and rollback semantics.

### Permit Curator Or Reviewer Self-Approval

Rejected because generated or curated organizational knowledge requires separation of duties.

### Accept Free-Form Approval Rationale

Rejected because sensitive operational content could leak into metadata, logs, audit, or telemetry.

## Follow-Up

Later independent lifecycle contracts cover publication preparation, chunking and embedding,
retrieval-index validation and atomic publication, suspension, supersession, retention, deletion,
and revision after final rejection.
