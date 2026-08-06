# ADR-041: Governed Connector Invocation Evidence Ingestion Contract

- Status: Accepted
- Date: 2026-08-06
- Owners: Product Owner, Solution Architecture, Security Architecture, Data Governance
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-025, ATLAS-027, ATLAS-030,
  ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-053,
  ATLAS-054, ATLAS-055, ATLAS-056, ADR-009 through ADR-040

## Context

ADR-040 consumes one exact authorization, invokes one bounded C0/C1 connector capability, validates
and redacts its result, proves cleanup, and persists only a minimized completion record. The
normalized redacted observations are not durably ingested, indexed, published to retrieval, or
made available to a model.

The next lifecycle boundary must preserve validated observations as governed operational evidence
without allowing the caller, application service, web client, logs, audit stream, or model context
to receive raw vendor output or choose classification, access, retention, storage, indexing, or
publication behavior. Durable evidence is a source artifact, not automatically organizational
truth or approved knowledge.

## Decision

Atlas will implement a dedicated connector invocation-evidence ingestion service. It atomically
claims one completed ADR-040 invocation, instructs a narrow trusted adapter to resolve and persist
the exact normalized redacted result internally, validates a signed minimized receipt, and records
an immutable evidence-ingestion completion.

### Caller Contract

The caller may provide only:

- exact bounded-invocation ID and canonical digest;
- exact signed evidence-ingestion policy ID and digest;
- a bounded evidence-preservation purpose;
- acknowledgement that ingestion is one-way and does not publish knowledge or grant authority;
- idempotency and correlation identifiers.

The caller cannot provide or override evidence content, observations, source timestamps,
classification, ACLs, principals, retention, legal hold, encryption, storage location, artifact
references, parser, chunker, embedding model, index, publication state, target, credential, secret,
lease/session, capability, command, schedule, workflow, execution, deployment, or mutation fields.

### Authorization And Lineage

Before claim creation the service revalidates:

- the complete immutable connector lifecycle lineage through ADR-040;
- exact invocation ID, digest, schema, state, tenant, package, instance, capability, profile,
  input-envelope, result-schema, result-policy, adapter, and redacted-result bindings;
- proven single capability invocation, result receipt, schema validation, redaction, and complete
  target-session, delivery-channel, and lease cleanup;
- bounded positive observation count and output size;
- exact signed ingestion policy, signer, schema, scope, classification, access-policy, retention,
  encryption, storage-adapter, and freshness bindings;
- hardware-backed human assurance, exact tenant scope, a dedicated C3 ingestion permission, the
  capability's exact read permission, and separation from all upstream actors and policy or adapter
  attestors;
- absence of prior ingestion, scheduling, retrieval publication, model-context availability,
  workflow continuation, execution, deployment, and infrastructure-mutation authority.

Wrong-scope, altered, ambiguous, reused-authority, insufficient-assurance, or unauthorized
requests fail closed without reading the result artifact or writing evidence.

### Atomic One-Way Ingestion Claim

After intent audit succeeds and before the adapter accesses the result package, the repository
creates an immutable claim with a unique constraint on the source invocation ID. Claim creation is
the point of no return.

An existing claim returns the same completed record only when actor, idempotency key, request
fingerprint, and completion evidence match. Otherwise it fails as already claimed. A claim is not
released after cancellation, timeout, adapter failure, audit failure, partial storage, or uncertain
outcome. Atlas does not retry automatically. A later governed reconciliation contract may prove and
attach an already committed artifact without re-reading a target or invoking a capability again.

### Trusted Evidence Adapter Boundary

The application sends only trusted lineage IDs and digests, policy references, limits, and the
ingestion ID. The adapter internally resolves the exact signed normalized-result package produced
by the trusted invocation runtime. Raw vendor output is never available at this boundary.

The adapter must:

1. verify the instruction and exact ADR-040 receipt/result-package binding;
2. validate signature, schema, redaction proof, size, item count, and structured content safety;
3. derive classification, ACL, retention, legal-hold eligibility, and encryption from signed policy;
4. preserve occurrence, observation, invocation, and ingestion times without inventing timestamps;
5. write an encrypted immutable artifact and versioned metadata atomically or return uncertainty;
6. compute evidence-package, content, metadata, ACL, and retention digests;
7. close artifact channels and erase transient buffers in all outcomes;
8. return only a signed minimized receipt without content, snippets, storage coordinates, keys,
   principals, tokens, signatures, or mutable handles.

Production fails closed when no trusted evidence adapter is configured. Development may use a
deterministic synthetic adapter that performs no target, secret-store, network, model, vector,
external storage, workflow, deployment, or infrastructure operation.

### Completion Record

A successful immutable record uses state `enabled_invocation_evidence_ingested` and contains only:

- source invocation and connector lineage IDs and digests;
- evidence package ID, schema/version, content and metadata digests, and bounded item/byte counts;
- signed policy ID/digest/version and opaque adapter identity;
- classification, access-policy, retention-policy, encryption-profile, and source-time metadata;
- ingestion actor, purpose, timestamps, cleanup proof, and canonical digest.

It records `evidence_ingested=true` while `knowledge_item_created`, `retrieval_published`,
`model_context_available`, `graph_updated`, `scheduled`, `workflow_continued`,
`execution_authorized`, `deployment_approved`, and `infrastructure_mutation_performed` remain false.

The API may expose lineage, classification label, retention policy, counts, timestamps, and digests.
It never exposes evidence content, excerpts, item values, target details, storage coordinates, ACL
principals, keys, secret or session identities, request fingerprints, or idempotency material.

### Evidence Versus Knowledge

An ingested package is immutable operational evidence with source authority `system-generated` and
an explicit unreviewed evidence lifecycle. It is not a retrievable knowledge item, approved fact,
confirmed health state, root cause, recommendation, runbook, or model memory.

ATLAS-015 and ATLAS-027 govern any later classification review, knowledge-item creation, chunking,
embedding, indexing, publication, suspension, supersession, deletion, and retrieval. Those actions
require their own authorization, policy, provenance, ACL, quality, and audit boundaries.

### Failure And Audit

Failures before claim creation produce no artifact access or storage write. Failures after claim
creation remain claimed and emit safe failed or uncertain audit outcomes. No completion record is
created unless receipt identity, lineage, policy, content/metadata digests, limits, classification,
retention, encryption, timestamps, immutable-storage proof, and transient-buffer cleanup validate.

Required intent audit precedes the claim. Claim audit follows successful atomic claim creation.
Completion audit succeeds before completion persistence. Audit contains only stable IDs, result
codes, bounded counts, and non-sensitive digests.

### Persistence And API

Claims and completion records are immutable, deterministic, concurrency-safe, and equivalent in
memory and PostgreSQL. The API uses browser session, mutation CSRF, strict schemas, no-store,
dedicated default-deny RBAC, exact capability permission re-evaluation, hardware MFA, safe errors,
and minimized responses.

## Consequences

### Positive

- Validated redacted connector observations gain durable, attributable provenance.
- Callers cannot inject evidence content or choose weaker classification, ACL, retention, or
  encryption behavior.
- Evidence remains separate from retrieval, model context, and approved organizational knowledge.
- Partial or uncertain storage cannot cause silent replay of the connector invocation.

### Costs

- Production requires a trusted result-package handoff and immutable encrypted artifact adapter.
- An uncertain ingestion claim requires reconciliation rather than automatic retry.
- Full knowledge publication still requires separate ingestion, review, indexing, and lifecycle
  implementation under ATLAS-015 and ATLAS-027.

## Rejected Alternatives

### Accept Evidence Content From The Caller

Rejected because it would permit result substitution, content injection, misclassification, and
loss of provenance.

### Publish Directly To RAG Or Model Context

Rejected because schema-valid observations are not automatically safe, authorized, current,
reviewed, or suitable as organizational knowledge.

### Reinvoke The Connector During Ingestion

Rejected because ADR-040 is single-use and ingestion must preserve the exact completed result.

### Let The Caller Choose Classification Or Retention

Rejected because callers may not downgrade governance controls attached to infrastructure data.

## Follow-Up

Later independent lifecycle contracts cover evidence reconciliation, knowledge-item curation and
publication, governed scheduling, workflow continuation, uncertainty investigation, and retention
or deletion execution.
