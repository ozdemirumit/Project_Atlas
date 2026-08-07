# ADR-057: Governed Protected Knowledge Retrieval Index Publication Contract

- Status: Accepted
- Date: 2026-08-07
- Owners: Product Owner, Solution Architecture, Security Architecture, Knowledge Management,
  Identity Governance, Data Governance, Knowledge Retrieval Engineering, AI Platform Engineering
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-025, ATLAS-027, ATLAS-030, ATLAS-031,
  ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-052, ATLAS-053,
  ATLAS-054, ATLAS-055, ATLAS-056, ADR-009 through ADR-056

## Context

ADR-056 records one complete, sealed, validated, and inactive protected retrieval-index projection.
It deliberately creates no active retrieval alias, searchable knowledge publication, query route,
model context, workflow authority, or infrastructure-operation authority. Atlas now needs a
separate protected step that revalidates the exact staging lineage and atomically publishes that
projection for policy-filtered retrieval without exposing vector-store internals.

## Decision

Atlas will implement one dedicated protected-knowledge-retrieval-index-publication service. One
audited `POST` binds an eligible human retrieval-publication steward to the exact validated staging
record and obtains a signed metadata-only publication receipt from an approved trusted publisher.
An audited `GET` returns minimized immutable publication-record metadata.

### Eligibility

The service proceeds only when:

- the exact staging record exists and remains bound to one completed embedding set, chunk set,
  source materialization, publication preparation, approved final resolution, unchanged passed
  review lineage, approved knowledge item, and publication-ready generation;
- the sealed projection, point coverage, authorization metadata, model compatibility, isolation,
  reconciliation, index profile, staging boundary, governance binding, model space, access policy,
  classification, residency, and retention evidence remain exact and internally consistent;
- embedding creation, index staging, and index validation are complete while knowledge
  publication, retrieval publication, model context, graph update, scheduling, workflow,
  execution, deployment, and infrastructure mutation remain false; and
- no prior publication claim or completed publication record exists for that staging record.

Rejected, corrected, superseded, suspended, drifted, already published, caller-shaped, or
cross-generation lineage fails before claim creation.

### Caller Contract

The caller may provide only:

- exact index-staging ID and canonical digest;
- exact signed retrieval-publication-policy ID and digest;
- a bounded publication purpose;
- acknowledgements that publication creates only policy-filtered retrieval visibility, does not
  expose content or vector-store internals, and grants no model-context, graph, scheduling,
  workflow, execution, deployment, or infrastructure-mutation authority; and
- idempotency and correlation identifiers.

The caller cannot provide identity, tenant, steward, content, excerpt, coordinate, chunk ID,
vector value, model or endpoint, collection, namespace, alias, point ID, payload, filter, access
scope, index parameters, target, credential, query, ranking, lifecycle override, command,
schedule, workflow, execution, deployment, or mutation fields.

### Identity And Separation

The actor must be a current enterprise human in the exact tenant with recent hardware-backed MFA,
dedicated C2 retrieval-publication and C1 lineage-read permissions, browser binding, CSRF, and a
current signed policy. The actor cannot be any curator, reviewer, final approver, preparation,
materialization, chunking, embedding, or index steward, policy signer, trusted preparer,
materializer, chunker, embedder, indexer, publisher, model owner, index-profile owner, alias-profile
owner, or a service, shared, AI, or break-glass identity.

### Trusted Publication Boundary

The approved trusted publisher resolves the sealed projection only from immutable internal
lineage and resolves one opaque retrieval route only from a signed approved local publication
profile. The caller and ordinary application cannot select or observe collection names, aliases,
point identities, payloads, vectors, filters, or routing internals. Inside the trusted boundary it
must:

- reverify the exact signed staging receipt, sealed projection manifest, point coverage,
  authorization metadata, model compatibility, isolation, reconciliation, classification,
  residency, retention, source access policy, lifecycle, and signed publication profile;
- exclusively claim one tenant-isolated inactive route generation with no public network fallback,
  external telemetry, cross-tenant cache, caller-selected routing, or unapproved retention;
- perform a zero-partial-visibility atomic route activation only after all preconditions pass;
- verify the active route generation, sealed projection digest, authorization filter enforcement,
  tenant and classification isolation, lifecycle filter, retention binding, and absence of any
  unapproved route;
- retain bounded rollback metadata for a later separately governed suspension or recovery action,
  without exposing or automatically invoking rollback; and
- sign a metadata-only receipt binding all lineage, publication profile, route generation,
  activation, verification, policy, and steward evidence.

The trusted boundary returns no content, excerpt, coordinate, chunk map, point ID, collection or
alias name, endpoint, token stream, vector value, payload, filter, key, raw identity, secret, or
query result. Production fails closed without an approved trusted publisher. Development may use
a deterministic synthetic publisher that derives fixed metadata from sealed digests and returns
only a metadata receipt; it has no connector, workflow, credential, external vector store, query,
target, or network access.

### Atomic Claim And Replay

Required intent audit succeeds before a unique immutable staging-record publication claim is
created. The claim is the point of no return. Exact completed idempotent reuse is permitted only
when lineage, steward, policy, purpose, acknowledgements, and request-binding digests match.
Failure or uncertainty after claim creation remains claimed and is never retried automatically.
Concurrent or conflicting publication attempts cannot replace the first claim.

### Persistence And Lifecycle Semantics

Ordinary application persistence stores immutable metadata and integrity digests only. It stores
no content, excerpt, coordinate, chunk map, point ID, collection or alias name, endpoint, key,
cookie, raw identity, secret, token stream, vector value, payload, filter, signature material, or
query result.

A successful result records `operational_knowledge_retrieval_published`, preserves approval,
publication readiness, preparation, source materialization, chunks, embeddings, index staging,
and index validation, and sets both knowledge publication and retrieval publication true.
Model-context availability, graph update, scheduling, workflow continuation, execution authority,
deployment approval, and infrastructure mutation remain false.

The record proves that one governed protected item is visible only through a policy-filtered
retrieval route. It does not perform a query, return content, assemble model context, update a
graph, start a workflow, or authorize an operation.

### Read, Failure, And Audit

Only the accountable publication steward may read minimized metadata while identity, tenant,
policy, browser, and permission authority remain current. Responses use strict `no-store`,
`nosniff`, no-referrer, and restrictive content-security headers.

Intent, claim, trusted activation, publication verification, persistence completion, and read are
separately audited. Audit excludes content, coordinates, chunk maps, point IDs, collection or
alias names, payloads, filters, token streams, vectors, endpoints, keys, profile internals,
cookies, raw identity, and secrets. Policy, lineage, permission, MFA, separation, browser,
publisher, projection, persistence, audit, concurrency, activation, route verification, or
integrity uncertainty fails closed.

## Consequences

### Positive

- Retrieval visibility is activated only from a complete validated projection and exact current
  governance lineage.
- Atomic route activation prevents partially searchable protected knowledge.
- Ordinary APIs, persistence, logs, audit, and web output reveal no protected content, vectors, or
  vector-store routing internals.

### Costs

- Production requires an approved isolated publication boundary, signed publication profile,
  atomic route activation, and route-verification support.
- A separate eligible human publication steward and recent hardware MFA are required.
- Failed or uncertain post-claim publication requires governance intervention rather than
  automatic replay.

## Rejected Alternatives

### Publish Automatically After Validation

Rejected because validation and retrieval visibility require separate accountable authorities,
audit evidence, and failure domains.

### Accept Caller-Supplied Alias Or Filters

Rejected because callers could bypass tenant, classification, lifecycle, retention, or source
access controls.

### Treat Publication As Model Context Availability

Rejected because retrieval eligibility and context assembly have separate purpose, disclosure,
prompt-injection, citation, and model-governance controls.

### Reuse The Index Steward

Rejected because projection construction and retrieval visibility are separate accountable
authorities.

## Follow-Up

Later independent lifecycle contracts cover governed retrieval, model-context assembly,
suspension, supersession, retention, deletion, and revision after final rejection.
