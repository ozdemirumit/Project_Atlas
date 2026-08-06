# ADR-042: Governed Operational Evidence Knowledge-Draft Curation Contract

- Status: Accepted
- Date: 2026-08-06
- Owners: Product Owner, Solution Architecture, Security Architecture, Knowledge Management,
  Data Governance
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-025, ATLAS-027, ATLAS-030, ATLAS-031,
  ATLAS-032, ATLAS-033, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-053, ATLAS-054, ATLAS-055,
  ATLAS-056, ADR-009 through ADR-041

## Context

ADR-041 preserves one validated connector invocation result as immutable, encrypted operational
evidence. The evidence remains unreviewed and is not a knowledge item, retrieval source, model
context, confirmed fact, root cause, recommendation, or runbook.

Atlas needs a controlled bridge from preserved evidence into the Knowledge Engine lifecycle. That
bridge must not silently treat system observations as organizational truth, expose evidence content
to the web application, allow a caller to weaken governance, or combine draft creation with human
review, approval, indexing, or publication.

## Decision

Atlas will implement a dedicated operational-evidence knowledge-draft curation service. It
atomically claims one completed ADR-041 evidence package, instructs a narrow trusted curation
adapter to derive one immutable draft knowledge artifact internally, validates a signed minimized
receipt, and records a draft catalog entry that is ineligible for retrieval.

### Caller Contract

The caller may provide only:

- exact evidence-ingestion ID and canonical digest;
- exact signed curation-policy ID and digest;
- a bounded curation purpose;
- acknowledgement that the result is an unapproved, non-retrievable draft;
- idempotency and correlation identifiers.

The caller cannot provide or override evidence content, excerpts, observations, draft content,
title, summary, language, source authority, domain, content type, classification, ACLs, principals,
retention, legal hold, encryption, storage location, owner, reviewer, approver, quality outcome,
applicability, parser, chunker, embedding model, index, publication state, target, credential,
secret, session, capability, command, schedule, workflow, execution, deployment, or mutation fields.

### Authorization And Lineage

Before claim creation the service revalidates:

- the complete immutable connector lifecycle lineage through ADR-041;
- exact evidence-ingestion ID, digest, schema, state, tenant, invocation, package, policy, adapter,
  classification, access-policy, retention, encryption, content, metadata, and source-time bindings;
- successful immutable evidence storage and complete artifact-channel and transient-buffer cleanup;
- exact signed curation policy, signer, schema, scope, draft domain, content type, source authority,
  language, title template, classification inheritance, access-policy inheritance, retention
  inheritance, adapter, limits, and freshness bindings;
- hardware-backed human assurance, exact tenant scope, dedicated C3 knowledge-draft curation and
  evidence-read permissions, and separation from upstream actors and policy or adapter attestors;
- absence of a prior curation claim and absence of knowledge approval, retrieval publication,
  model-context availability, graph update, scheduling, workflow continuation, execution,
  deployment, or infrastructure-mutation authority.

Wrong-scope, altered, ambiguous, reused, insufficient-assurance, unauthorized, stale, or
later-authority-bearing requests fail closed before evidence artifact access or draft creation.

### Atomic One-Way Curation Claim

After required intent audit succeeds and before the adapter reads the evidence package, the
repository creates an immutable claim with a unique constraint on the source evidence-ingestion ID.
Claim creation is the point of no return.

An existing claim returns the same completed record only when actor, idempotency key, request
binding, and completion evidence match. Otherwise it fails as already claimed. A claim is not
released after cancellation, timeout, adapter failure, audit failure, partial write, or uncertain
outcome. Atlas does not retry automatically and never re-invokes the connector. Later reconciliation
may attach a proven committed draft without re-reading infrastructure.

### Trusted Curation Adapter Boundary

The application sends only trusted lineage IDs and digests, signed policy references, limits, and
the draft ID. The adapter internally resolves the exact immutable evidence package from the trusted
evidence store. Evidence content never crosses into the application service, API, browser, logs, or
audit stream.

The adapter must:

1. verify the instruction and exact ADR-041 evidence-package binding;
2. validate artifact integrity, schema, redaction proof, size, item count, and content safety;
3. derive title and structured draft content deterministically from the signed policy and evidence;
4. label the source as `system-generated`, the domain as `operational`, and the lifecycle as `draft`;
5. inherit classification, access policy, retention, legal-hold eligibility, and source times
   without downgrade or invention;
6. preserve evidence, connector, capability, occurrence, observation, invocation, ingestion, and
   curation lineage;
7. write an encrypted immutable draft artifact and versioned catalog metadata atomically or return
   uncertainty;
8. compute draft-content, metadata, provenance, access, retention, and artifact digests;
9. close artifact channels and erase transient buffers in every outcome;
10. return only a signed minimized receipt without content, excerpts, storage coordinates, ACL
    principals, keys, tokens, signatures, or mutable handles.

Production fails closed when no trusted curation adapter is configured. Development may use a
deterministic synthetic adapter that performs no target, secret-store, network, model, vector,
external storage, workflow, deployment, or infrastructure operation.

### Draft Catalog Record

A successful immutable record uses state `draft_operational_knowledge_created` and contains only:

- source evidence, invocation, connector, instance, and capability lineage IDs and digests;
- stable knowledge-item ID, immutable draft-version ID, schema/version, artifact ID, and content,
  metadata, provenance, access, and retention digests;
- policy ID/digest/version and opaque adapter identity;
- generated title, domain, content type, language, source authority, classification, access-policy,
  retention-policy, encryption-profile, bounded item/byte counts, and source-time metadata;
- curation actor, purpose, timestamps, cleanup proof, and canonical digest.

It records `knowledge_item_created=true` and `knowledge_lifecycle=draft` while
`domain_review_completed`, `security_review_completed`, `knowledge_approved`,
`knowledge_published`, `chunks_created`, `embeddings_created`, `retrieval_published`,
`model_context_available`, `graph_updated`, `scheduled`, `workflow_continued`,
`execution_authorized`, `deployment_approved`, and `infrastructure_mutation_performed` remain false.

The API may expose safe catalog metadata, lineage, lifecycle, classification label, policies,
counts, timestamps, and digests. It never exposes evidence or draft content, excerpts, observation
values, target details, storage coordinates, ACL principals, keys, secret or session identities,
request fingerprints, or idempotency material.

### Draft Is Not Published Knowledge

Draft creation does not imply correctness, applicability, approval, or retrieval eligibility. The
draft is non-authoritative and cannot be returned by KnowledgeRetriever, cited to a model, used as
model context, exported as an approved runbook, or treated as a confirmed fact.

Separate contracts must implement content inspection, domain review, security review, correction,
approval, rejection, expiry, conflict handling, supersession, chunking, embedding, index validation,
atomic publication, suspension, retirement, and deletion. No single actor may curate, review, approve,
and publish the same draft where separation policy applies.

### Failure And Audit

Failures before claim creation produce no artifact read or draft write. Failures after claim
creation remain claimed and emit safe failed or uncertain outcomes. No completion record is created
unless receipt identity, lineage, policy, inherited governance, content/metadata/provenance digests,
limits, lifecycle, timestamps, immutable-storage proof, and cleanup validate.

Required intent audit precedes the claim. Claim audit follows successful atomic claim creation.
Completion audit succeeds before completion persistence. Audit contains only stable IDs, result
codes, bounded counts, lifecycle labels, and non-sensitive digests.

### Persistence And API

Claims and draft records are immutable, deterministic, concurrency-safe, and equivalent in memory
and PostgreSQL. The API uses browser session, mutation CSRF, strict schemas, no-store, dedicated
default-deny RBAC, hardware MFA, exact tenant scope, safe errors, and minimized responses.

## Consequences

### Positive

- Preserved operational evidence can enter a visible, governed Knowledge Engine draft lifecycle.
- Draft content and governance cannot be substituted or downgraded by the caller.
- Human review, approval, retrieval publication, and model use remain explicit later boundaries.
- Uncertain curation cannot silently duplicate evidence or re-invoke infrastructure.

### Costs

- Production requires a trusted evidence-store-to-draft-store adapter.
- Humans cannot review content through this minimized foundation until a separate controlled review
  surface is implemented.
- A claimed uncertain draft requires reconciliation rather than automatic retry.

## Rejected Alternatives

### Publish Evidence Directly To Retrieval

Rejected because valid observations are not automatically reviewed, current, applicable, or safe as
organizational knowledge.

### Let The Caller Submit Draft Content Or Governance

Rejected because it permits content substitution, injection, misclassification, access widening,
and retention downgrade.

### Use An LLM During Draft Creation

Rejected for this foundation because model use introduces a separate authorization, disclosure,
prompt-injection, provenance, and evaluation boundary.

### Combine Curation, Review, Approval, And Publication

Rejected because it removes meaningful human review and separation of duties.

## Follow-Up

Later independent lifecycle contracts cover uncertain-draft reconciliation, controlled content
inspection and correction, domain and security review, approval or rejection, chunking and
embedding, retrieval-index validation and publication, suspension, supersession, retention, and
deletion execution.
