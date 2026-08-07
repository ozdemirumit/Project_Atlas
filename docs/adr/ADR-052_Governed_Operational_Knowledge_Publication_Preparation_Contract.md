# ADR-052: Governed Operational Knowledge Publication Preparation Contract

- Status: Accepted
- Date: 2026-08-07
- Owners: Product Owner, Solution Architecture, Security Architecture, Knowledge Management,
  Identity Governance, Data Governance
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-025, ATLAS-027, ATLAS-030, ATLAS-031,
  ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-052, ATLAS-053,
  ATLAS-054, ATLAS-055, ATLAS-056, ADR-009 through ADR-051

## Context

ADR-051 records an immutable final approval and publication-readiness signal for an exact reviewed
knowledge generation. It deliberately creates no publication artifact, chunk, embedding, index, or
retrieval authority. Atlas needs a separate step that binds the approved generation to a governed,
immutable publication plan before any content-processing stage can begin.

## Decision

Atlas will implement one dedicated publication-preparation service. One audited `POST` binds an
eligible human publication steward to the exact approved final resolution and obtains a signed,
metadata-only preparation manifest from an approved trusted preparer. An audited `GET` returns
minimized immutable preparation metadata.

### Eligibility

The service proceeds only when:

- the exact final resolution exists, is `final-resolution.approved`, and remains bound to one
  unchanged review request, draft, assignment set, two passed track decisions, and knowledge item;
- knowledge approval and publication readiness are true while publication, chunking, embedding,
  indexing, retrieval, model-context, graph, workflow, execution, deployment, and mutation state
  remain false;
- no prior publication-preparation claim or completed preparation exists for the final resolution;
  and
- organization, environment, classification, access, retention, source, policy, and generation
  lineage remain exact and internally consistent.

A rejected, corrected, superseded, mixed-generation, caller-shaped, already processed, published,
or lineage-drifted source fails before claim creation.

### Caller Contract

The caller may provide only:

- exact final-resolution ID and canonical digest;
- exact signed publication-preparation-policy ID and digest;
- a bounded preparation purpose;
- acknowledgements that the approved generation and selected policy are immutable, that preparation
  creates metadata only, and that no content processing, retrieval, workflow, execution,
  deployment, or infrastructure mutation authority is granted; and
- idempotency and correlation identifiers.

The caller cannot provide identity, tenant, steward, approver, reviewer, curator, content, title,
summary, classification, access control, retention, artifact location, chunking profile, embedding
model, index, destination, retrieval state, governance label, lifecycle state, target, credential,
command, schedule, workflow, execution, deployment, or mutation fields.

### Identity And Separation

The actor must be a current enterprise human in the exact tenant with recent hardware-backed MFA,
dedicated C2 publication-preparation-create and lineage-read permissions, browser binding, CSRF,
and a current signed policy. The actor cannot be the curator, either track reviewer, final approver,
policy signer, trusted preparer, or a service, shared, AI, or break-glass identity.

### Trusted Preparation Boundary

An approved trusted preparer signs the exact final-resolution lineage, publication steward binding,
preparation policy, purpose, and deterministic preparation identifier. The receipt binds immutable
digests for the approved source artifact, metadata manifest, access manifest, retention manifest,
chunking profile, embedding profile, index profile, and publication-validation profile. The ordinary
application receives no content, artifact coordinate, key, secret, raw identity, or model output.

Production fails closed without an approved trusted preparer. Development may use a deterministic
synthetic preparer that derives metadata-only receipts and has no model, connector, workflow,
credential, target, vector store, index, or infrastructure access.

### Atomic Claim And Replay

Required intent audit succeeds before a unique immutable final-resolution claim is created. The
claim is the point of no return. Exact completed idempotent reuse is permitted only when lineage,
steward, policy, purpose, and request-binding digests match. Failure or uncertainty after claim
creation remains claimed and is never retried automatically. Concurrent or conflicting preparation
attempts cannot replace the first claim.

### Persistence And Lifecycle Semantics

Application persistence stores immutable metadata and integrity digests only. It stores no content,
excerpt, title, free-form rationale, artifact coordinate, cookie, raw identity, secret, token,
signature material, embedding, or model output.

A successful result records `operational_knowledge_publication_prepared`, preserves knowledge
approval and publication readiness, and sets publication preparation true. Knowledge publication,
chunk creation, embedding creation, index staging, index validation, retrieval publication,
model-context availability, graph update, scheduling, workflow continuation, execution authority,
deployment approval, and infrastructure mutation remain false.

The preparation record is an immutable plan and lineage proof. It does not read or transform the
source content, reserve production retrieval visibility, create a vector entry, publish an item,
start a workflow, or authorize an operation.

### Read, Failure, And Audit

Only the accountable publication steward may read minimized preparation metadata while identity,
tenant, policy, browser, and permission authority remain current. Responses use strict `no-store`,
`nosniff`, no-referrer, and restrictive content-security headers.

Intent, claim, trusted preparation, persistence completion, and read are separately audited. Audit
excludes content, title, artifact coordinates, profile internals, cookies, raw identity, and secrets.
Policy, lineage, permission, MFA, separation, browser, preparer, persistence, audit, concurrency, or
integrity uncertainty fails closed.

## Consequences

### Positive

- Publication planning is attributable, immutable, and separate from final approval.
- Callers cannot select content-processing or retrieval authority through request fields.
- Later chunking, embedding, validation, and publication stages receive exact signed profile and
  lineage digests without gaining premature access.

### Costs

- Production requires an approved trusted publication preparer.
- A separate eligible human steward and recent hardware MFA are required after approval.
- Failed or uncertain post-claim preparations require governance intervention rather than replay.

## Rejected Alternatives

### Start Chunking During Preparation

Rejected because plan authorization and content transformation require separate atomic controls.

### Let The Caller Select Models Or Indexes

Rejected because caller-selected processing profiles could bypass governance and isolation policy.

### Reuse The Final Approver As Publication Steward

Rejected because approval and publication preparation are separate accountable authorities.

### Store Content Or Artifact Coordinates In Application Records

Rejected because operational knowledge could leak through metadata, logs, audit, or telemetry.

## Follow-Up

Later independent lifecycle contracts cover protected source materialization, deterministic chunking,
embedding generation, retrieval-index staging and validation, atomic publication, suspension,
supersession, retention, deletion, and revision after final rejection.
