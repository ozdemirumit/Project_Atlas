# ADR-043: Governed Operational Knowledge Draft Review Request Contract

- Status: Accepted
- Date: 2026-08-06
- Owners: Product Owner, Solution Architecture, Security Architecture, Knowledge Management,
  Data Governance
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-025, ATLAS-027, ATLAS-030, ATLAS-031,
  ATLAS-032, ATLAS-033, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-053, ATLAS-054, ATLAS-055,
  ATLAS-056, ADR-009 through ADR-042

## Context

ADR-042 creates one immutable operational knowledge draft from exact governed connector evidence.
The draft remains non-authoritative, non-retrievable, and unavailable as model context. No human
review work item exists and the browser cannot inspect draft content.

Atlas needs a controlled transition from `draft` to `review_requested`. That transition must not
let the requester select reviewers, expose content, record a review decision, approve knowledge,
or combine review orchestration with publication authority.

## Decision

Atlas will implement a dedicated operational knowledge draft review-request service. It atomically
claims one completed ADR-042 draft, instructs a narrow trusted orchestration adapter to validate the
immutable draft internally and create one immutable review manifest, validates a signed minimized
receipt, and records required domain and security review tracks in policy-selected queues.

### Caller Contract

The caller may provide only:

- exact draft ID and canonical digest;
- exact signed review-orchestration policy ID and digest;
- a bounded review purpose;
- acknowledgement that the result is only a review request;
- idempotency and correlation identifiers.

The caller cannot provide or override draft or evidence content, excerpts, title, summary,
classification, ACL, retention, encryption, storage location, applicability, reviewer identity,
reviewer group, queue, assignment, due date, priority, review type, findings, decision, correction,
approval, publication, parser, chunker, embedding model, index, retrieval, model context, target,
credential, secret, session, command, schedule, workflow, execution, deployment, or mutation fields.

### Authorization And Lineage

Before claim creation the service revalidates:

- the complete immutable connector, evidence-ingestion, and knowledge-draft lineage through
  ADR-042;
- exact draft ID, digest, schema, lifecycle, tenant, knowledge item/version, source evidence,
  policy, adapter, inherited governance, artifact, content, metadata, provenance, access,
  retention, immutable-storage, and cleanup bindings;
- exact signed review-orchestration policy, signer, schema, scope, required domain and security
  tracks, queue identifiers, assignment strategy, SLA class, adapter, and freshness bindings;
- hardware-backed human assurance, exact tenant scope, dedicated C3 review-request permission,
  and knowledge-draft read permission;
- absence of a prior review-request claim and absence of review decisions, corrections, approval,
  publication, chunks, embeddings, retrieval, model context, graph update, scheduling, workflow,
  execution, deployment, or infrastructure-mutation authority.

The request creator may be the curator because orchestration is not a review decision. The creator
cannot become a reviewer or approver through this request. Later contracts enforce actor separation
among curation, domain review, security review, approval, and publication.

### Atomic One-Way Review Claim

After required intent audit succeeds and before the adapter reads the draft artifact, the
repository creates an immutable claim with a unique constraint on the source draft ID. Claim
creation is the point of no return.

An existing claim returns the same completed record only when actor, idempotency key, request
binding, and completion evidence match. Otherwise it fails as already claimed. A claim is not
released after cancellation, timeout, adapter failure, audit failure, partial write, or uncertain
outcome. Atlas does not retry automatically. Later reconciliation may attach a proven committed
review manifest without reopening the draft or reading infrastructure.

### Trusted Review-Orchestration Adapter Boundary

The application sends only trusted lineage IDs and digests, signed policy references, limits, and
the review-request ID. The adapter internally resolves the exact encrypted immutable draft. Draft
content never crosses into the application service, API, browser, logs, or audit stream.

The adapter must:

1. verify the instruction and exact ADR-042 draft binding;
2. validate artifact integrity, decryptability, schema, inherited governance, size, item count,
   content-safety proof, and cleanup proof;
3. derive required domain and security review tracks and queue identifiers only from policy;
4. create one immutable review manifest containing lineage, governance, track, queue, SLA, and
   content-digest bindings without content or excerpts;
5. set both tracks to `awaiting_reviewer` without assignment or decision;
6. write the encrypted immutable manifest atomically or return uncertainty;
7. compute manifest, routing, governance, and artifact digests;
8. close artifact channels and erase transient buffers in every outcome;
9. return only a signed minimized receipt without content, storage coordinates, ACL principals,
   reviewer identities, keys, tokens, signatures, or mutable handles.

Production fails closed when no trusted review-orchestration adapter is configured. Development
may use a deterministic synthetic adapter that performs no target, secret-store, network, model,
vector, external workflow, deployment, or infrastructure operation.

### Review Request Record

A successful immutable record uses state `operational_knowledge_review_requested` and contains only:

- draft, knowledge item/version, evidence, invocation, connector, instance, and capability lineage
  IDs and digests;
- stable review-request ID, immutable manifest ID, schema/version, artifact ID, and manifest,
  routing, governance, and artifact digests;
- policy ID/digest/version and opaque adapter identity;
- inherited domain, content type, language, classification, access-policy, retention-policy, and
  encryption-profile labels;
- required track codes, opaque queue IDs, assignment strategy, SLA class, and status
  `awaiting_reviewer`;
- request actor, purpose, timestamps, cleanup proof, and canonical digest.

It records `review_requested=true` while `reviewer_assigned`, `content_inspection_opened`,
`domain_review_completed`, `security_review_completed`, `correction_created`,
`knowledge_approved`, `knowledge_published`, `chunks_created`, `embeddings_created`,
`retrieval_published`, `model_context_available`, `graph_updated`, `scheduled`,
`workflow_continued`, `execution_authorized`, `deployment_approved`, and
`infrastructure_mutation_performed` remain false.

The API may expose safe catalog lineage, lifecycle, track codes, queue IDs, SLA class, status,
policy references, bounded counts, timestamps, and non-sensitive digests. It never exposes draft or
evidence content, excerpts, observations, target details, storage coordinates, ACL principals,
reviewer identities, keys, secret or session identities, request fingerprints, or idempotency
material.

### Review Request Is Not Review Or Approval

Creating a review request does not assign a reviewer, open content, validate correctness, record a
decision, approve knowledge, or grant retrieval eligibility. The draft remains non-authoritative
and unavailable to KnowledgeRetriever and model context.

Separate contracts implement protected reviewer assignment and content inspection, independent
domain and security decisions, correction and resubmission, approval or rejection, chunking,
embedding, index validation, and atomic retrieval publication.

### Failure And Audit

Failures before claim creation produce no artifact read or manifest write. Failures after claim
creation remain claimed and emit safe failed or uncertain outcomes. No completion record is created
unless receipt identity, lineage, policy, inherited governance, track routing, limits, timestamps,
immutable-storage proof, and cleanup validate.

Required intent audit precedes the claim. Claim audit follows successful atomic claim creation.
Completion audit succeeds before completion persistence. Audit contains only stable IDs, result
codes, track codes, queue IDs, bounded counts, state labels, and non-sensitive digests.

### Persistence And API

Claims and review-request records are immutable, deterministic, concurrency-safe, and equivalent
in memory and PostgreSQL. The API uses browser session, mutation CSRF, strict schemas, no-store,
dedicated default-deny RBAC, hardware MFA, exact tenant scope, safe errors, and minimized responses.

## Consequences

### Positive

- Drafts enter explicit domain and security review queues without exposing content.
- Callers cannot route work to a preferred reviewer or weaken review policy.
- Review orchestration remains separate from inspection, decisions, approval, and publication.
- Uncertain orchestration cannot silently duplicate review work.

### Costs

- Production requires a trusted draft-store-to-review-manifest adapter.
- Reviewers still cannot inspect or decide through this foundation alone.
- A claimed uncertain request requires reconciliation rather than automatic retry.

## Rejected Alternatives

### Let The Caller Select Reviewers Or Queues

Rejected because it enables self-review, bypasses separation policy, and leaks organization
identity and routing details into an untrusted request surface.

### Return Draft Content With The Request

Rejected because request creation is not reviewer authorization or protected inspection.

### Combine Request, Assignment, Inspection, And Decision

Rejected because it collapses independent authorization, disclosure, and human-accountability
boundaries.

### Trigger External Workflow Directly

Rejected because review-request persistence is not ITSM or workflow execution authority.

## Follow-Up

Later independent lifecycle contracts cover uncertain-request reconciliation, protected reviewer
assignment and content inspection, domain and security decisions, correction and resubmission,
approval or rejection, chunking and embedding, retrieval-index validation and publication,
suspension, supersession, retention, and deletion execution.
