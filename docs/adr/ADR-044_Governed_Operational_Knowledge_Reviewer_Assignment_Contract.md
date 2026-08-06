# ADR-044: Governed Operational Knowledge Reviewer Assignment Contract

- Status: Accepted
- Date: 2026-08-06
- Owners: Product Owner, Solution Architecture, Security Architecture, Knowledge Management,
  Identity Governance, Data Governance
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-025, ATLAS-027, ATLAS-030, ATLAS-031,
  ATLAS-032, ATLAS-033, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-053, ATLAS-054, ATLAS-055,
  ATLAS-056, ADR-009 through ADR-043

## Context

ADR-043 creates one immutable review manifest with required domain and security tracks routed to
policy-selected queues. Both tracks remain `awaiting_reviewer`. The request exposes no content,
selects no person, and grants no review or approval authority.

Atlas must assign accountable humans before protected content inspection can open. Assignment must
not allow self-selection, reveal organization identities to the requester, collapse domain and
security review into one actor, or make assignment equivalent to a review decision.

## Decision

Atlas will implement a dedicated operational knowledge reviewer-assignment service. It atomically
claims one completed ADR-043 review request, instructs a narrow trusted directory-and-routing
adapter to select two eligible and distinct human reviewers, validates a signed minimized receipt,
and records immutable domain and security assignments without exposing reviewer identities.

### Caller Contract

The caller may provide only:

- exact review-request ID and canonical digest;
- exact signed reviewer-assignment policy ID and digest;
- a bounded assignment purpose;
- acknowledgement that assignment neither opens content nor records a decision;
- idempotency and correlation identifiers.

The caller cannot provide or override draft/evidence content, reviewer identity, username, email,
group, role, directory query, queue, track, assignment result, workload, priority, due date,
delegation, finding, decision, correction, approval, publication, parser, chunker, embedding model,
index, retrieval, model context, target, credential, secret, session, command, schedule, workflow,
execution, deployment, or mutation fields.

### Authorization And Lineage

Before claim creation the service revalidates:

- complete immutable connector, evidence, draft, and review-request lineage through ADR-043;
- exact review-request ID, digest, schema, state, tenant, manifest, routing, governance, artifact,
  track, queue, assignment strategy, policy, immutable-storage, and cleanup bindings;
- exact signed assignment policy, signer, schema, scope, directory source, eligibility rules,
  separation rules, workload limits, assignment TTL, adapter, and freshness bindings;
- hardware-backed human assurance, exact tenant scope, dedicated C3 assignment-request and
  review-request-read permissions;
- both tracks remain unassigned and no inspection, decision, correction, approval, publication,
  chunks, embeddings, retrieval, model context, graph update, scheduling, workflow, execution,
  deployment, or mutation authority exists.

The request actor may be the curator or review-request creator because requesting policy-controlled
assignment is not reviewing. The adapter must exclude the curator, evidence ingester, assignment
requester, review-request creator, upstream operational actors, policy signers, adapter attestors,
and any later approver/publisher exclusion list supplied by trusted policy lineage.

### Atomic One-Way Assignment Claim

After required intent audit succeeds and before directory resolution, the repository creates an
immutable claim with a unique constraint on the source review-request ID. Claim creation is the
point of no return.

An existing claim returns the same completed record only when actor, idempotency key, request
binding, and completion evidence match. Otherwise it fails as already claimed. A claim is not
released after cancellation, timeout, directory failure, audit failure, partial write, or uncertain
outcome. Atlas does not retry automatically. Later reconciliation may attach proven committed
assignments without reopening the draft or reading infrastructure.

### Trusted Assignment Adapter Boundary

The application sends only trusted lineage IDs and digests, opaque queue IDs, signed policy
references, exclusion-subject digests, limits, and the assignment ID. The adapter resolves identity
directory entries internally. Raw identity attributes never cross into the application service,
API, browser, logs, or audit stream.

The adapter must:

1. verify the instruction and exact ADR-043 review-manifest binding;
2. resolve current eligible hardware-MFA human members for each policy-selected queue;
3. validate tenant, employment/identity status, role, permission, domain competence, security
   clearance, workload, conflict, and assignment freshness;
4. exclude every upstream, request, policy, attestation, approval, and publication actor digest;
5. select one domain and one security reviewer deterministically under policy and ensure they are
   distinct;
6. create immutable opaque assignment IDs with bounded expiry and status `assigned`;
7. store reviewer identity references encrypted and return only salted subject digests;
8. compute assignment, routing, eligibility, separation, and artifact digests;
9. close directory/artifact channels and erase transient identity buffers in every outcome;
10. return only a signed minimized receipt without names, usernames, email, groups, directory
    attributes, raw subject IDs, content, storage coordinates, keys, tokens, signatures, or mutable
    handles.

Production fails closed when no trusted assignment adapter is configured. Development may use a
deterministic synthetic adapter with fixed non-user-facing reviewer subjects and no external
directory, target, secret-store, network, model, vector, workflow, deployment, or infrastructure
operation.

### Assignment Record

A successful immutable record uses state `operational_knowledge_reviewers_assigned` and contains:

- review-request, draft, knowledge item/version, evidence, invocation, connector, instance, and
  capability lineage IDs and digests;
- assignment set ID, domain/security opaque assignment IDs, salted reviewer-subject digests,
  assignment/routing/eligibility/separation/artifact digests, and bounded expiry;
- policy ID/digest/version and opaque adapter identity;
- inherited domain, classification, access, retention, encryption, track, queue, assignment
  strategy, and SLA labels;
- domain and security status `assigned`, request actor, purpose, timestamps, cleanup proof, and
  canonical digest.

It records `reviewer_assigned=true` while `content_inspection_opened`,
`domain_review_completed`, `security_review_completed`, `correction_created`,
`knowledge_approved`, `knowledge_published`, `chunks_created`, `embeddings_created`,
`retrieval_published`, `model_context_available`, `graph_updated`, `scheduled`,
`workflow_continued`, `execution_authorized`, `deployment_approved`, and
`infrastructure_mutation_performed` remain false.

The API may expose safe lineage, lifecycle, opaque assignment IDs, salted identity digests, track,
queue, SLA, assigned status, expiry, policy references, timestamps, and non-sensitive digests. It
never exposes content, identity attributes, raw subject IDs, directory data, findings, target
details, storage coordinates, ACL principals, keys, request fingerprints, or idempotency material.

### Assignment Is Not Inspection Or Review

Assignment does not open draft content, create a reusable session, record technical correctness,
approve knowledge, or grant retrieval eligibility. Only the exact assigned subject may later
request a short-lived track-specific inspection lease under a separate contract. Assignment expiry
requires explicit re-assignment governance; it does not silently delegate.

### Failure And Audit

Failures before claim creation perform no directory query or assignment write. Failures after claim
creation remain claimed and emit safe failed or uncertain outcomes. No completion record is created
unless receipt identity, lineage, policy, eligibility, separation, routing, expiry, immutable-write,
and cleanup evidence validate.

Required intent audit precedes the claim. Claim audit follows successful atomic claim creation.
Completion audit succeeds before completion persistence. Audit contains only stable IDs, result
codes, track codes, opaque queue/assignment IDs, salted subject digests, state labels, and
non-sensitive digests.

### Persistence And API

Claims and assignment records are immutable, deterministic, concurrency-safe, and equivalent in
memory and PostgreSQL. The API uses browser session, mutation CSRF, strict schemas, no-store,
dedicated default-deny RBAC, hardware MFA, exact tenant scope, safe errors, and minimized responses.

## Consequences

### Positive

- Domain and security review are bound to distinct accountable humans without caller selection.
- Identity attributes stay inside the trusted assignment boundary.
- Assignment can be audited without opening content or implying a decision.
- Uncertain directory or assignment outcomes cannot silently duplicate work.

### Costs

- Production requires trusted directory/routing integration and reviewer eligibility data.
- The current operator cannot inspect content merely because they requested assignment.
- Assignment expiry and uncertainty require explicit reconciliation or reassignment governance.

## Rejected Alternatives

### Let The Caller Select Reviewers

Rejected because it enables self-review, collusion, identity disclosure, and queue bypass.

### Use One Reviewer For Both Tracks

Rejected because domain correctness and security/data handling are independent accountabilities.

### Return Raw Reviewer Identity

Rejected because the requester does not need personal or directory attributes to observe state.

### Open Content During Assignment

Rejected because identity assignment and content disclosure require separate authorization and
audit boundaries.

## Follow-Up

Later independent lifecycle contracts cover uncertain-assignment reconciliation, assignment expiry
and reassignment, short-lived track-specific protected inspection leases, domain/security decisions,
correction and resubmission, approval or rejection, chunking and embedding, retrieval-index
validation and publication, suspension, supersession, retention, and deletion execution.
