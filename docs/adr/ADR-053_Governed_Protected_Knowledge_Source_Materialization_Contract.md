# ADR-053: Governed Protected Knowledge Source Materialization Contract

- Status: Accepted
- Date: 2026-08-07
- Owners: Product Owner, Solution Architecture, Security Architecture, Knowledge Management,
  Identity Governance, Data Governance
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-025, ATLAS-027, ATLAS-030, ATLAS-031,
  ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-052, ATLAS-053,
  ATLAS-054, ATLAS-055, ATLAS-056, ADR-009 through ADR-052

## Context

ADR-052 records an immutable metadata-only publication-preparation manifest for one approved
knowledge generation. It intentionally does not read or transform source content and exposes no
artifact coordinate. Atlas now needs a separate protected step that obtains the exact approved
source inside a trusted boundary, validates its integrity and governance bindings, and writes one
immutable protected source material for later deterministic chunking.

## Decision

Atlas will implement one dedicated protected-source-materialization service. One audited `POST`
binds an eligible human materialization steward to the exact completed publication preparation and
obtains a signed metadata-only receipt from an approved trusted materializer. An audited `GET`
returns minimized immutable materialization metadata.

### Eligibility

The service proceeds only when:

- the exact preparation exists and remains bound to one approved final resolution, unchanged passed
  review lineage, approved knowledge item, and publication-ready generation;
- the preparation receipt, source-artifact digest, metadata, access, retention, chunking, embedding,
  index, and validation profile digests remain exact and internally consistent;
- preparation is complete while source materialization, chunking, embedding, index staging,
  validation, publication, retrieval, model context, graph update, workflow, execution, deployment,
  and infrastructure mutation remain false; and
- no prior source-materialization claim or completed materialization exists for the preparation.

Rejected, corrected, superseded, drifted, already processed, published, caller-shaped, or
cross-generation lineage fails before claim creation.

### Caller Contract

The caller may provide only:

- exact publication-preparation ID and canonical digest;
- exact signed materialization-policy ID and digest;
- a bounded materialization purpose;
- acknowledgements that the approved source and governance bindings are immutable, protected
  content remains inside the trusted boundary, and no chunking, retrieval, workflow, execution,
  deployment, or infrastructure mutation authority is granted; and
- idempotency and correlation identifiers.

The caller cannot provide identity, tenant, steward, source content, excerpt, title, summary,
classification, access control, retention, source or destination coordinate, decryption material,
normalization rules, media type, chunking profile, embedding model, index, retrieval state,
governance label, lifecycle state, target, credential, command, schedule, workflow, execution,
deployment, or mutation fields.

### Identity And Separation

The actor must be a current enterprise human in the exact tenant with recent hardware-backed MFA,
dedicated C2 materialization-create and lineage-read permissions, browser binding, CSRF, and a
current signed policy. The actor cannot be the curator, either reviewer, final approver,
publication steward, policy signer, trusted preparer, trusted materializer, or a service, shared,
AI, or break-glass identity.

### Trusted Materialization Boundary

The approved trusted materializer resolves the protected source only from sealed internal lineage;
the caller and ordinary application cannot select or observe a source coordinate. Inside the
trusted boundary it must:

- acquire exactly one source artifact without public-network fallback;
- verify source digest, classification, access, retention, encryption, media-type allowlist,
  active-content rejection, and configured malware-scan evidence;
- decode and canonically normalize only an approved textual format under bounded byte and character
  limits, rejecting malformed, empty, ambiguous, encrypted-without-key, or unsupported input;
- atomically write one immutable encrypted protected material under an internal opaque identity;
  and
- sign a receipt binding the source digest, protected-material digest, canonicalization profile,
  media type, byte and character counts, governance-manifest digests, policy, steward, and exact
  preparation lineage.

The trusted boundary returns no content, excerpt, source or destination coordinate, encryption key,
malware details, raw identity, secret, or model output. Production fails closed without an approved
trusted materializer. Development may use a deterministic synthetic materializer that validates
fixed synthetic bytes and returns only a metadata receipt; it has no model, connector, workflow,
credential, target, vector store, index, or external-network access.

### Atomic Claim And Replay

Required intent audit succeeds before a unique immutable preparation claim is created. The claim is
the point of no return. Exact completed idempotent reuse is permitted only when lineage, steward,
policy, purpose, acknowledgements, and request-binding digests match. Failure or uncertainty after
claim creation remains claimed and is never retried automatically. Concurrent or conflicting
materialization attempts cannot replace the first claim.

### Persistence And Lifecycle Semantics

Ordinary application persistence stores immutable metadata and integrity digests only. It stores no
content, excerpt, title, free-form rationale, source or destination coordinate, key, cookie, raw
identity, secret, token, signature material, embedding, chunk, or model output.

A successful result records `operational_knowledge_source_materialized`, preserves approval,
publication readiness, and preparation, and sets source materialization true. Chunk creation,
embedding creation, index staging, index validation, atomic publication, retrieval visibility,
model-context availability, graph update, scheduling, workflow continuation, execution authority,
deployment approval, and infrastructure mutation remain false.

The record proves that a governed protected source exists. It does not expose that source, create a
chunk or vector, reserve an index, publish an item, start a workflow, or authorize an operation.

### Read, Failure, And Audit

Only the accountable materialization steward may read minimized metadata while identity, tenant,
policy, browser, and permission authority remain current. Responses use strict `no-store`,
`nosniff`, no-referrer, and restrictive content-security headers.

Intent, claim, trusted materialization, persistence completion, and read are separately audited.
Audit excludes content, title, coordinates, keys, scan details, profile internals, cookies, raw
identity, and secrets. Policy, lineage, permission, MFA, separation, browser, materializer,
persistence, audit, concurrency, or integrity uncertainty fails closed.

## Consequences

### Positive

- Approved operational knowledge enters a protected immutable content boundary without leaking
  through ordinary APIs, persistence, logs, audit, or web output.
- Integrity and governance are independently revalidated before any later content processing.
- Deterministic chunking receives one exact protected-material digest and profile binding.

### Costs

- Production requires an approved isolated materializer and protected encrypted artifact store.
- A separate eligible human steward and recent hardware MFA are required.
- Failed or uncertain post-claim materializations require governance intervention rather than
  automatic replay.

## Rejected Alternatives

### Return Materialized Content Through The API

Rejected because ordinary application and browser surfaces are not approved content boundaries.

### Combine Materialization And Chunking

Rejected because source integrity and content segmentation require separate claims, receipts, and
failure domains.

### Accept A Caller-Supplied Artifact Coordinate Or Profile

Rejected because callers could redirect acquisition, bypass governance, or select unsafe processing.

### Reuse The Publication Steward

Rejected because preparation and content materialization are separate accountable authorities.

## Follow-Up

Later independent lifecycle contracts cover deterministic chunking, embedding generation,
retrieval-index staging and validation, atomic publication, suspension, supersession, retention,
deletion, and revision after final rejection.
