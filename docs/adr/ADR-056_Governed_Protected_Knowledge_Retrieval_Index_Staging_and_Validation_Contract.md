# ADR-056: Governed Protected Knowledge Retrieval Index Staging And Validation Contract

- Status: Accepted
- Date: 2026-08-07
- Owners: Product Owner, Solution Architecture, Security Architecture, Knowledge Management,
  Identity Governance, Data Governance, Knowledge Retrieval Engineering, AI Platform Engineering
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-025, ATLAS-027, ATLAS-030, ATLAS-031,
  ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-052, ATLAS-053,
  ATLAS-054, ATLAS-055, ATLAS-056, ADR-009 through ADR-055

## Context

ADR-055 records one immutable model-bound protected embedding set without exposing chunk content,
coordinates, vector values, or model endpoints. It deliberately creates no vector-store point,
validated retrieval index, publication authority, or retrieval visibility. Atlas now needs a
separate protected step that stages the exact embedding set into one isolated index projection and
validates its completeness, compatibility, authorization metadata, and integrity before any later
publication decision.

## Decision

Atlas will implement one dedicated protected-knowledge-retrieval-index-staging-and-validation
service. One audited `POST` binds an eligible human index steward to the exact completed embedding
set and obtains a signed metadata-only receipt from an approved trusted indexer. An audited `GET`
returns minimized immutable staging-record metadata.

### Eligibility

The service proceeds only when:

- the exact embedding set exists and remains bound to one completed chunk set, source
  materialization, publication preparation, approved final resolution, unchanged passed review
  lineage, approved knowledge item, and publication-ready generation;
- the protected material, ordered chunk manifest, governance binding, model/profile, immutable
  model artifact, tokenizer, dimension, normalization, distance metric, vector manifest,
  chunk-vector binding, numerical validation, coverage validation, and resource evidence remain
  exact and internally consistent;
- embedding creation is complete while index staging, index validation, publication, retrieval,
  model context, graph update, scheduling, workflow, execution, deployment, and infrastructure
  mutation remain false; and
- no prior index-staging claim or completed staging record exists for that embedding set.

Rejected, corrected, superseded, drifted, already processed, published, caller-shaped, or
cross-generation lineage fails before claim creation.

### Caller Contract

The caller may provide only:

- exact embedding-set ID and canonical digest;
- exact signed index-policy ID and digest;
- a bounded staging and validation purpose;
- acknowledgements that vectors remain inside the trusted boundary, the projection is isolated
  and inactive, and no publication, retrieval, workflow, execution, deployment, or
  infrastructure-mutation authority is granted; and
- idempotency and correlation identifiers.

The caller cannot provide identity, tenant, steward, content, excerpt, coordinate, chunk ID,
vector value, model or endpoint, collection, namespace, point ID, payload, filter, access scope,
index algorithm or parameters, target, credential, publication or retrieval state, lifecycle
state, command, schedule, workflow, execution, deployment, or mutation fields.

### Identity And Separation

The actor must be a current enterprise human in the exact tenant with recent hardware-backed MFA,
dedicated C2 index-stage, index-validate, and lineage-read permissions, browser binding, CSRF, and
a current signed policy. The actor cannot be any curator, reviewer, final approver, publication,
materialization, chunking, or embedding steward, policy signer, trusted preparer, materializer,
chunker, embedder, indexer, model owner, index-profile owner, or a service, shared, AI, or
break-glass identity.

### Trusted Index Boundary

The approved trusted indexer resolves vectors and chunk bindings only from sealed internal lineage
and resolves one staging destination only from a signed approved local index profile. The caller
and ordinary application cannot select or observe collection names, point identities, payloads,
vectors, or index parameters. Inside the trusted boundary it must:

- verify the exact encrypted embedding set, complete vector manifest and chunk-vector binding,
  compatible model space, dimension, normalization, distance metric, classification, residency,
  retention, source access policy, lifecycle, and signed index profile;
- create or exclusively claim one encrypted tenant-isolated inactive staging projection with no
  query route, active alias, public network fallback, external telemetry, cross-tenant cache, or
  unapproved retention;
- derive opaque deterministic point identities internally and write every exact vector once with
  mandatory authorization, provenance, lifecycle, model-space, and integrity metadata;
- enforce bounded batch, time, memory, storage, and retry behavior without exposing partial data;
- reconcile expected and stored counts, unique point identities, model/dimension compatibility,
  payload schema, tenant and classification boundaries, ACL and retention bindings, ordered vector
  manifest, and a second projection-manifest calculation; and
- atomically seal the inactive projection and sign a receipt binding all lineage, index profile,
  staging, validation, reconciliation, policy, and steward evidence.

The trusted boundary returns no content, excerpt, coordinate, chunk map, point ID, collection name,
model endpoint, token stream, vector value, payload, key, raw identity, secret, or query result.
Production fails closed without an approved trusted indexer. Development may use a deterministic
synthetic indexer that derives fixed metadata from sealed digests and returns only a metadata
receipt; it has no connector, workflow, credential, external vector store, query route, target, or
network access.

### Atomic Claim And Replay

Required intent audit succeeds before a unique immutable embedding-set claim is created. The claim
is the point of no return. Exact completed idempotent reuse is permitted only when lineage,
steward, policy, purpose, acknowledgements, and request-binding digests match. Failure or
uncertainty after claim creation remains claimed and is never retried automatically. Concurrent or
conflicting staging attempts cannot replace the first claim.

### Persistence And Lifecycle Semantics

Ordinary application persistence stores immutable metadata and integrity digests only. It stores
no content, excerpt, coordinate, chunk map, point ID, collection name, model endpoint, key, cookie,
raw identity, secret, token stream, vector value, payload, signature material, or query result.

A successful result records `operational_knowledge_index_validated`, preserves approval,
publication readiness, preparation, source materialization, chunks, and embeddings, and sets both
index staging and index validation true. Atomic publication, retrieval visibility, model-context
availability, graph update, scheduling, workflow continuation, execution authority, deployment
approval, and infrastructure mutation remain false.

The record proves that one governed inactive index projection is complete and internally
validated. It does not activate an alias, publish an item, permit search, expose content, start a
workflow, or authorize an operation.

### Read, Failure, And Audit

Only the accountable index steward may read minimized metadata while identity, tenant, policy,
browser, and permission authority remain current. Responses use strict `no-store`, `nosniff`,
no-referrer, and restrictive content-security headers.

Intent, claim, trusted staging, validation completion, persistence completion, and read are
separately audited. Audit excludes content, coordinates, chunk maps, point IDs, collection names,
payloads, token streams, vector values, endpoints, keys, profile internals, cookies, raw identity,
and secrets. Policy, lineage, permission, MFA, separation, browser, indexer, model-space,
persistence, audit, concurrency, reconciliation, or integrity uncertainty fails closed.

## Consequences

### Positive

- Complete model-compatible vectors enter one isolated projection without exposing protected
  content or vector-store internals through ordinary APIs, persistence, logs, audit, or web output.
- Required authorization and lifecycle metadata are validated before any retrieval publication.
- Point coverage and projection integrity are explicit and reproducible before alias activation.

### Costs

- Production requires an approved isolated vector-store boundary, signed index profile, encrypted
  staging capacity, and reconciliation support.
- A separate eligible human steward and recent hardware MFA are required.
- Failed or uncertain post-claim staging requires governance intervention rather than automatic
  replay.

## Rejected Alternatives

### Publish Directly During Upsert

Rejected because projection creation and retrieval activation require separate evidence,
authorities, failure domains, and rollback semantics.

### Accept Caller-Supplied Collection Or Point Metadata

Rejected because callers could bypass tenant isolation, authorization payloads, model-space
compatibility, retention, and lifecycle controls.

### Validate Counts Only

Rejected because equal counts do not prove unique coverage, ACL correctness, model compatibility,
payload safety, or vector-manifest integrity.

### Reuse The Embedding Steward

Rejected because model inference and vector-store projection are separate accountable authorities.

## Follow-Up

Later independent lifecycle contracts cover atomic retrieval publication, suspension,
supersession, retention, deletion, and revision after final rejection.
