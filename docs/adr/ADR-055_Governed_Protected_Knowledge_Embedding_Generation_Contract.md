# ADR-055: Governed Protected Knowledge Embedding Generation Contract

- Status: Accepted
- Date: 2026-08-07
- Owners: Product Owner, Solution Architecture, Security Architecture, Knowledge Management,
  Identity Governance, Data Governance, AI Platform Engineering
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-025, ATLAS-027, ATLAS-030, ATLAS-031,
  ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-052, ATLAS-053,
  ATLAS-054, ATLAS-055, ATLAS-056, ADR-009 through ADR-054

## Context

ADR-054 records one immutable deterministic protected chunk set without exposing chunk content or
coordinates. It deliberately creates no embedding, vector-store record, index, or retrieval
visibility. Atlas now needs a separate protected step that processes the exact chunk set with one
approved local embedding model profile and writes one immutable encrypted embedding set for later
index staging.

## Decision

Atlas will implement one dedicated protected-knowledge-embedding-generation service. One audited
`POST` binds an eligible human embedding steward to the exact completed chunk set and obtains a
signed metadata-only receipt from an approved trusted embedder. An audited `GET` returns minimized
immutable embedding-set metadata.

### Eligibility

The service proceeds only when:

- the exact chunk set exists and remains bound to one source materialization, completed publication
  preparation, approved final resolution, unchanged passed review lineage, approved knowledge
  item, and publication-ready generation;
- the ordered chunk manifest, protected material, source artifact, chunking and algorithm profiles,
  governance and structure manifests, count/size evidence, and determinism evidence remain exact
  and internally consistent;
- chunk creation is complete while embedding, index staging, index validation, publication,
  retrieval, model context, graph update, scheduling, workflow, execution, deployment, and
  infrastructure mutation remain false; and
- no prior embedding claim or completed embedding set exists for that chunk set.

Rejected, corrected, superseded, drifted, already processed, published, caller-shaped, or
cross-generation lineage fails before claim creation.

### Caller Contract

The caller may provide only:

- exact chunk-set ID and canonical digest;
- exact signed embedding-policy ID and digest;
- a bounded embedding purpose;
- acknowledgements that protected chunks remain inside the trusted boundary, the approved model
  profile is immutable, and no indexing, retrieval, workflow, execution, deployment, or
  infrastructure-mutation authority is granted; and
- idempotency and correlation identifiers.

The caller cannot provide identity, tenant, steward, chunk content, excerpt, title, coordinate,
chunk ID, vector value, model ID, model endpoint, tokenizer, dimension, normalization, distance
metric, batch parameters, key, index, collection, retrieval state, lifecycle state, target,
credential, command, schedule, workflow, execution, deployment, or mutation fields.

### Identity And Separation

The actor must be a current enterprise human in the exact tenant with recent hardware-backed MFA,
dedicated C2 embedding-create and lineage-read permissions, browser binding, CSRF, and a current
signed policy. The actor cannot be the curator, either reviewer, final approver, publication
steward, materialization steward, chunking steward, policy signer, trusted preparer, materializer,
chunker, embedder, model owner, or a service, shared, AI, or break-glass identity.

### Trusted Embedding Boundary

The approved trusted embedder resolves chunks only from sealed internal lineage and the model only
from a signed approved local profile. The caller and ordinary application cannot select or observe
chunk coordinates, model endpoints, or vectors. Inside the trusted boundary it must:

- verify the exact encrypted chunk set, ordered manifest, governance binding, classification,
  residency, model/profile approval, immutable model artifact digest, tokenizer, dimension,
  normalization, distance metric, and bounded resource policy;
- operate without public-network fallback, external telemetry, model training, cross-tenant cache,
  truncation, mixed model spaces, or unapproved content retention;
- embed every exact chunk once under bounded batch, token, memory, time, and accelerator limits;
- validate finite numeric values, exact dimensions and count, normalization bounds, stable ordered
  chunk-to-vector mapping, and a second manifest calculation; and
- atomically write one immutable encrypted embedding set under internal opaque identities and sign
  a receipt binding all lineage, model/profile, vector-manifest, validation, policy, and steward
  evidence.

The trusted boundary returns no chunk content, excerpt, coordinate, chunk ID map, model endpoint,
token stream, vector value, key, raw identity, secret, or model output. Production fails closed
without an approved trusted embedder. Development may use a deterministic synthetic embedder that
derives fixed metadata from sealed digests and returns only a metadata receipt; it has no external
model, connector, workflow, credential, target, vector store, index, or network access.

### Atomic Claim And Replay

Required intent audit succeeds before a unique immutable chunk-set claim is created. The claim is
the point of no return. Exact completed idempotent reuse is permitted only when lineage, steward,
policy, purpose, acknowledgements, and request-binding digests match. Failure or uncertainty after
claim creation remains claimed and is never retried automatically. Concurrent or conflicting
embedding attempts cannot replace the first claim.

### Persistence And Lifecycle Semantics

Ordinary application persistence stores immutable metadata and integrity digests only. It stores
no chunk content, excerpt, title, coordinate, chunk ID map, model endpoint, key, cookie, raw
identity, secret, token stream, vector value, signature material, index point, or model output.

A successful result records `operational_knowledge_embeddings_created`, preserves approval,
publication readiness, preparation, source materialization, and chunk creation, and sets embedding
creation true. Index staging, index validation, atomic publication, retrieval visibility,
model-context availability, graph update, scheduling, workflow continuation, execution authority,
deployment approval, and infrastructure mutation remain false.

The record proves that one governed immutable embedding set exists. It does not expose a vector,
stage or validate an index, publish an item, enable retrieval, start a workflow, or authorize an
operation.

### Read, Failure, And Audit

Only the accountable embedding steward may read minimized metadata while identity, tenant, policy,
browser, and permission authority remain current. Responses use strict `no-store`, `nosniff`,
no-referrer, and restrictive content-security headers.

Intent, claim, trusted embedding, persistence completion, and read are separately audited. Audit
excludes content, coordinates, chunk maps, token streams, vector values, endpoints, keys, profile
internals, cookies, raw identity, and secrets. Policy, lineage, permission, MFA, separation,
browser, embedder, model, persistence, audit, concurrency, numerical validation, or integrity
uncertainty fails closed.

## Consequences

### Positive

- Approved chunks become one immutable model-bound embedding set without leaking protected content
  or vector values through ordinary APIs, persistence, logs, audit, or web output.
- Model-space identity and complete chunk coverage are explicit before any index write.
- Model or preprocessing changes create a new governed generation instead of mixing vector spaces.

### Costs

- Production requires an approved isolated embedding runtime, signed model artifact, and encrypted
  embedding store.
- A separate eligible human steward and recent hardware MFA are required.
- Failed or uncertain post-claim generation requires governance intervention rather than automatic
  replay.

## Rejected Alternatives

### Return Vectors Through The API

Rejected because vectors are sensitive derived data and ordinary application/browser surfaces are
not approved vector boundaries.

### Generate Embeddings During Chunking

Rejected because segmentation and model inference require separate claims, profiles, resource
controls, receipts, and failure domains.

### Accept Caller-Supplied Model Or Endpoint

Rejected because callers could bypass residency, evaluation, model-space, telemetry, and supply
chain controls.

### Reuse The Chunking Steward

Rejected because deterministic segmentation and model processing are separate accountable
authorities.

## Follow-Up

Later independent lifecycle contracts cover retrieval-index staging and validation, atomic
publication, suspension, supersession, retention, deletion, and revision after final rejection.
