# ADR-050: Governed Operational Knowledge Correction And Resubmission Contract

- Status: Accepted
- Date: 2026-08-07
- Owners: Product Owner, Solution Architecture, Security Architecture, Knowledge Management,
  Identity Governance, Data Governance
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-025, ATLAS-027, ATLAS-030, ATLAS-031,
  ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-052, ATLAS-053,
  ATLAS-054, ATLAS-055, ATLAS-056, ADR-009 through ADR-049

## Context

ADR-049 records immutable domain and security track decisions. A `changes-required` decision is
only an accountable review outcome; it does not edit the reviewed draft or create replacement
content. Atlas now needs a bounded path that preserves the complete rejected review generation,
accepts only a correction staged in a trusted editing boundary, and creates a new immutable draft
version plus a new unassigned review generation without granting approval or publication authority.

## Decision

Atlas will implement one dedicated correction-and-resubmission service. One audited `POST` binds a
trusted correction submission to the exact completed review generation, creates a new immutable
draft version for the same knowledge item, and creates a new immutable review request generation.
An audited `GET` returns only minimized lifecycle metadata.

### Eligibility

The service proceeds only when:

- the exact domain and security decisions exist for the same immutable review request, assignment
  set, draft, and policy generation;
- both tracks are decided and at least one decision is `review-disposition.changes-required`;
- no prior correction claim or completed correction exists for that review request; and
- the source draft, request, decisions, governance, classification, access, retention, encryption,
  organization, environment, and knowledge-item lineage remain exact and internally consistent.

A single-track decision, mixed generation, duplicate track, all-passed result, missing lineage, or
caller-selected lifecycle state fails before claim creation.

### Caller Contract

The caller may provide only:

- exact source review-request ID and canonical digest;
- exact source decision IDs and canonical digests for both tracks;
- an opaque trusted correction-submission ID and canonical digest;
- exact signed correction-policy ID and digest;
- a bounded correction purpose;
- acknowledgements that the exact change requirements were addressed in the trusted editor, that
  a new immutable draft and review generation will be created, and that no approval, publication,
  retrieval, workflow, execution, deployment, or mutation authority is granted;
- idempotency and correlation identifiers.

The caller cannot provide identity, tenant, correction owner, track, findings, free-form corrected
content, artifact location, draft or request metadata, governance labels, review outcome, approval,
publication, index, model context, target, credential, command, schedule, workflow, execution,
deployment, or mutation fields. Corrected content never crosses the ordinary application API.

### Identity And Authorization

The actor must be the original accountable curator, in the exact tenant, using a current enterprise
human identity with recent hardware-backed MFA and dedicated C2 correction-create plus lineage-read
permissions. Reviewers, policy signers, and trusted adapter identities cannot perform the correction.
The normal browser session, mutation CSRF, current policy, and exact tenant scope are revalidated.

### Trusted Correction Boundary

The opaque correction submission is resolved only by an approved trusted correction adapter. The
adapter receives immutable lineage digests, policy constraints, the opaque submission binding, and
the new deterministic identifiers. It returns one signed minimized receipt for:

- a new encrypted immutable draft artifact and version for the same knowledge item; and
- a new encrypted immutable review manifest with both tracks reset to `awaiting_reviewer`.

The adapter must confirm that transient buffers were erased and artifact channels were closed.
Production fails closed without an approved adapter. Development may use a deterministic synthetic
adapter that cannot contact models, vector stores, workflows, connectors, credential brokers, or
infrastructure targets.

### Atomic Claim And Replay

Required intent audit succeeds before a unique immutable source-review-request claim is created.
The claim is the point of no return. Exact completed idempotent reuse is allowed only when source,
decision aggregate, correction submission, actor, policy, purpose, and request-binding digests match.
Failure or uncertainty after claim creation remains claimed and is never retried automatically.
Concurrent or conflicting corrections cannot replace the first claim.

### Persistence And Lifecycle Semantics

Application persistence stores only immutable metadata and integrity digests. It stores no finding
narrative, corrected content, patch, artifact coordinate, cookie, raw identity, secret, or model
output. The result state is `operational_knowledge_correction_resubmitted` and records:

- complete source request, source draft, and both-decision lineage;
- salted accountable curator and browser bindings;
- opaque correction submission and policy bindings;
- new draft-version and new review-request metadata and receipts; and
- explicit lifecycle flags.

The old draft, review request, assignments, leases, presentations, findings, and decisions remain
immutable. The new generation resets reviewer assignment, inspection, findings, and both track
decisions. It grants no knowledge approval, publication, chunking, embedding, retrieval, model
context, graph update, scheduling, workflow continuation, execution, deployment, or infrastructure
mutation authority.

### Read, Failure, And Audit

Only the accountable curator may read minimized result metadata while identity, tenant, policy, and
browser authority remain current. Responses use strict `no-store`, `nosniff`, no-referrer, and a
restrictive content-security policy.

Intent, claim, trusted-adapter completion, persistence completion, and read are separately audited.
Audit excludes findings, corrected content, artifact coordinates, cookies, raw identity, and secrets.
Policy, lineage, permission, MFA, browser, adapter, receipt, persistence, audit, concurrency, or
integrity uncertainty fails closed.

## Consequences

### Positive

- Review history remains immutable and attributable across correction generations.
- Corrected content stays inside a trusted protected-content boundary.
- Every resubmission receives fresh independent domain and security review.
- A correction cannot be mistaken for approval, publication, or operational authorization.

### Costs

- Production requires an approved trusted correction adapter/editor.
- Both review tracks must complete before one consolidated correction can begin.
- Corrections are append-only and therefore consume additional artifact and metadata storage.

## Rejected Alternatives

### Edit The Existing Draft Or Decision

Rejected because it destroys the exact evidence reviewed and invalidates audit history.

### Accept Corrected Content In The Ordinary API

Rejected because sensitive operational content would cross application persistence, logging, and
telemetry boundaries that intentionally hold metadata only.

### Reuse Prior Track Passes

Rejected because every corrected draft version requires fresh independent review of both tracks.

### Treat Resubmission As Approval

Rejected because review readiness and final knowledge approval are separate human authorities.

## Follow-Up

Later independent lifecycle contracts cover final approval or rejection, chunking and embedding,
retrieval-index validation and publication, suspension, supersession, retention, and deletion.
