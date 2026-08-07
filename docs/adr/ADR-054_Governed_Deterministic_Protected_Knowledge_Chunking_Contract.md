# ADR-054: Governed Deterministic Protected Knowledge Chunking Contract

- Status: Accepted
- Date: 2026-08-07
- Owners: Product Owner, Solution Architecture, Security Architecture, Knowledge Management,
  Identity Governance, Data Governance
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-025, ATLAS-027, ATLAS-030, ATLAS-031,
  ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-052, ATLAS-053,
  ATLAS-054, ATLAS-055, ATLAS-056, ADR-009 through ADR-053

## Context

ADR-053 records that one exact approved source was materialized as immutable encrypted protected
material inside a trusted boundary. It deliberately creates no chunk or embedding and exposes no
content or artifact coordinate. Atlas now needs a separate protected step that deterministically
segments that material under the preparation-bound chunking profile and writes one immutable chunk
set for later embedding.

## Decision

Atlas will implement one dedicated deterministic protected-knowledge-chunking service. One audited
`POST` binds an eligible human chunking steward to the exact completed source materialization and
obtains a signed metadata-only receipt from an approved trusted chunker. An audited `GET` returns
minimized immutable chunk-set metadata.

### Eligibility

The service proceeds only when:

- the exact source materialization exists and remains bound to one completed publication
  preparation, approved final resolution, unchanged passed review lineage, approved knowledge
  item, and publication-ready generation;
- the materialization receipt, source-artifact and protected-material digests, canonicalization and
  security profiles, media type, bounded counts, scan evidence, governance binding, and
  preparation-bound chunking profile remain exact and internally consistent;
- source materialization is complete while chunking, embedding, index staging, validation,
  publication, retrieval, model context, graph update, scheduling, workflow, execution,
  deployment, and infrastructure mutation remain false; and
- no prior chunking claim or completed chunk set exists for that materialization.

Rejected, corrected, superseded, drifted, already processed, published, caller-shaped, or
cross-generation lineage fails before claim creation.

### Caller Contract

The caller may provide only:

- exact source-materialization ID and canonical digest;
- exact signed chunking-policy ID and digest;
- a bounded chunking purpose;
- acknowledgements that protected material remains inside the trusted boundary, the bound
  chunking profile is immutable, and no embedding, retrieval, workflow, execution, deployment, or
  infrastructure-mutation authority is granted; and
- idempotency and correlation identifiers.

The caller cannot provide identity, tenant, steward, content, excerpt, title, summary, source or
destination coordinate, key, token, parser or normalization rule, chunk size, overlap, boundary,
ordinal, section path, page, anchor, tokenization option, embedding model, index, retrieval state,
governance label, lifecycle state, target, credential, command, schedule, workflow, execution,
deployment, or mutation fields.

### Identity And Separation

The actor must be a current enterprise human in the exact tenant with recent hardware-backed MFA,
dedicated C2 chunking-create and lineage-read permissions, browser binding, CSRF, and a current
signed policy. The actor cannot be the curator, either reviewer, final approver, publication
steward, materialization steward, policy signer, trusted preparer, trusted materializer, trusted
chunker, or a service, shared, AI, or break-glass identity.

### Trusted Chunking Boundary

The approved trusted chunker resolves protected material only from sealed internal lineage. The
caller and ordinary application cannot select or observe protected-material or chunk coordinates.
Inside the trusted boundary it must:

- acquire exactly one immutable protected material and verify its digest, media type, governance
  binding, canonicalization profile, and chunking profile without public-network fallback;
- use one immutable versioned deterministic, content-aware algorithm with bounded chunk count,
  chunk characters, tokens, overlap, hierarchy depth, and total processing resources;
- preserve source structure and citation lineage internally, reject empty, ambiguous, malformed,
  profile-incompatible, resource-exceeding, or non-deterministic output, and verify a second
  execution produces the same ordered manifest digest;
- atomically write one immutable encrypted chunk set under internal opaque identities; and
- sign a receipt binding the exact materialization, protected-material, chunking-profile,
  algorithm, ordered chunk-manifest, governance, steward, policy, and count/size evidence digests.

The trusted boundary returns no content, excerpt, section path, page, anchor, ordinal map, chunk or
artifact coordinate, key, token stream, parser internals, raw identity, secret, or model output.
Production fails closed without an approved trusted chunker. Development may use a deterministic
synthetic chunker that derives fixed metadata from sealed digests and returns only a metadata
receipt; it has no model, connector, workflow, credential, target, vector store, index, or
external-network access.

### Atomic Claim And Replay

Required intent audit succeeds before a unique immutable source-materialization claim is created.
The claim is the point of no return. Exact completed idempotent reuse is permitted only when
lineage, steward, policy, purpose, acknowledgements, and request-binding digests match. Failure or
uncertainty after claim creation remains claimed and is never retried automatically. Concurrent or
conflicting chunking attempts cannot replace the first claim.

### Persistence And Lifecycle Semantics

Ordinary application persistence stores immutable metadata and integrity digests only. It stores
no content, excerpt, title, section path, page, anchor, ordinal map, source or destination
coordinate, key, cookie, raw identity, secret, token stream, signature material, embedding, vector,
or model output.

A successful result records `operational_knowledge_chunks_created`, preserves approval,
publication readiness, preparation, and source materialization, and sets chunk creation true.
Embedding creation, index staging, index validation, atomic publication, retrieval visibility,
model-context availability, graph update, scheduling, workflow continuation, execution authority,
deployment approval, and infrastructure mutation remain false.

The record proves that one governed immutable deterministic chunk set exists. It does not expose a
chunk, create an embedding or vector, reserve an index, publish an item, start a workflow, or
authorize an operation.

### Read, Failure, And Audit

Only the accountable chunking steward may read minimized metadata while identity, tenant, policy,
browser, and permission authority remain current. Responses use strict `no-store`, `nosniff`,
no-referrer, and restrictive content-security headers.

Intent, claim, trusted chunking, persistence completion, and read are separately audited. Audit
excludes content, title, coordinates, chunk maps, token streams, keys, profile internals, cookies,
raw identity, and secrets. Policy, lineage, permission, MFA, separation, browser, chunker,
persistence, audit, concurrency, determinism, or integrity uncertainty fails closed.

## Consequences

### Positive

- Approved protected material becomes an immutable reproducible chunk set without leaking content
  through ordinary APIs, persistence, logs, audit, or web output.
- Chunk identity and lineage remain stable inputs for embedding, citation, rebuild, and deletion.
- Chunking-profile changes create a new governed generation instead of silently rewriting output.

### Costs

- Production requires an approved isolated deterministic chunker and encrypted chunk artifact
  store.
- A separate eligible human steward and recent hardware MFA are required.
- Failed or uncertain post-claim chunking requires governance intervention rather than automatic
  replay.

## Rejected Alternatives

### Return Chunks Through The API

Rejected because ordinary application and browser surfaces are not approved content boundaries.

### Combine Chunking And Embedding

Rejected because deterministic segmentation and model processing require separate claims,
receipts, resource controls, and failure domains.

### Accept Caller-Supplied Chunk Parameters

Rejected because callers could produce unreproducible output, bypass approved evaluation, or
reshape security and citation boundaries.

### Reuse The Materialization Steward

Rejected because protected source acquisition and deterministic content segmentation are separate
accountable authorities.

## Follow-Up

Later independent lifecycle contracts cover embedding generation, retrieval-index staging and
validation, atomic publication, suspension, supersession, retention, deletion, and revision after
final rejection.
