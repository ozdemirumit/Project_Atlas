# ADR-077: Governed Recommendation Correction And Resubmission Contract

- Status: Accepted
- Date: 2026-08-10
- Owners: Product Owner, Solution Architecture, Security Architecture, Infrastructure Operations,
  Service Management, Identity Governance, Data Governance
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-026, ATLAS-027,
  ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-040, ATLAS-041, ATLAS-042,
  ATLAS-043, ATLAS-044, ATLAS-046, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-052, ATLAS-053,
  ATLAS-054, ATLAS-055, ATLAS-056, ADR-009 through ADR-076

## Context

ADR-076 records immutable technical and service-impact decisions for one exact recommendation
review generation. A `changes-required` decision is accountable evidence but does not edit the
promoted recommendation, create corrected content, reopen the review request or grant approval.
ADR-069 additionally requires every material correction to become a new upstream recommendation
version and receive a new readiness assessment. Atlas therefore needs a correction boundary that
preserves the complete rejected generation and creates a new immutable promoted recommendation
version without carrying forward readiness, reviewer assignment, findings, decisions or authority.

## Decision

Atlas will implement one dedicated recommendation correction-and-resubmission service. One audited
`POST` binds an opaque trusted correction submission to the exact completed review generation and
creates one new immutable promoted recommendation version. An audited `GET` returns minimized
correction lifecycle metadata. The new version re-enters the existing readiness-assessment boundary;
the correction service does not create a readiness result or review request itself.

### Eligibility

The service proceeds only when:

- exact technical and service-impact decisions exist for the same immutable review request,
  assignment set, readiness assessment, promoted recommendation version and policy generation;
- both tracks are decided and at least one exact decision is `changes-required`;
- no prior correction claim, completed correction, final disposition, approval, workflow, ITSM,
  execution, deployment or infrastructure mutation exists for that review request; and
- recommendation, promotion, readiness, request, assignment, governance, classification,
  organization, environment and artifact lineage remain exact and internally consistent.

A single track, duplicate track, mixed generation, all-passed result, missing source, expired
policy, caller-shaped state or changed integrity proof fails before claim creation.

### Caller Contract

The caller may provide only:

- exact source recommendation and review-request IDs and canonical digests;
- exact decision IDs and canonical digests for both tracks;
- an opaque trusted correction-submission ID and canonical digest;
- exact signed correction-policy ID and digest;
- a bounded correction purpose;
- acknowledgements that the exact change requirements were addressed in the trusted editor, that
  a new immutable promoted recommendation version requiring fresh readiness assessment will be
  created, and that no review, approval or operational authority is granted; and
- idempotency and correlation identifiers.

The caller cannot provide identity, tenant, owner, reviewer, track, findings, corrected content,
patch, recommendation options, artifact location, new identifiers, governance labels, readiness,
review state, approval, workflow, ITSM, target, credential, command, schedule, execution, deployment
or mutation fields. Corrected recommendation content never crosses the ordinary correction API.

### Identity And Separation

The actor must be the original accountable recommendation consumer represented by the immutable
promotion and readiness lineage, in the exact tenant, using a current enterprise human identity with
recent hardware-backed MFA and dedicated C2 correction-create plus lineage-read permissions. The
actor cannot be either track reviewer, a policy signer, trusted adapter identity, service, shared,
AI or break-glass identity. The normal browser session, mutation CSRF and signed policy are current;
the correction operation receives a new browser binding and never reuses reviewer lease cookies.

### Trusted Correction Boundary

The opaque submission is resolved only by an approved trusted correction adapter. The adapter
receives immutable source and decision digests, policy limits, the opaque submission binding,
deterministic new identifiers and the protected source artifact through an internal port. It returns:

- a signed minimized receipt bound to the exact instruction; and
- one new immutable promoted recommendation artifact with a new recommendation ID, promotion ID,
  artifact digest and source binding while preserving tenant, classification and safe schema rules.

The adapter confirms source integrity, corrected-version immutability, safe-content validation,
transient-buffer erasure, closed artifact channels, no model use, no network use and no operational
authority. Production fails closed without an approved adapter and durable protected artifact
provider. Development may use a deterministic synthetic adapter that contacts no model, vector
store, workflow, ITSM system, connector, credential broker or infrastructure target.

### Atomic Claim And Replay

Required intent audit succeeds before a unique immutable source-review-request claim is created.
The claim is the point of no return. Exact completed idempotent reuse is allowed only when source,
both decisions, correction submission, actor, browser, policy, purpose and request-binding digests
match. Failure or uncertainty after claim creation remains claimed and is never retried
automatically. Concurrent or conflicting corrections cannot replace the first claim.

### Persistence And Artifact Boundary

Ordinary correction persistence stores immutable metadata and integrity digests only. It stores no
finding narrative, corrected content, patch, recommendation option, artifact coordinate, cookie,
raw identity, secret or model output. The trusted adapter owns protected corrected-artifact material
and must reproduce the exact artifact by its signed binding for readiness consumption.

The result state is `recommendation_correction_resubmitted`. It records complete source request,
promotion, readiness and decision lineage; salted owner and browser bindings; opaque submission and
policy bindings; new recommendation and promotion metadata; signed receipt; and explicit lifecycle
flags.

### Lifecycle Semantics

The source recommendation, readiness assessment, request, assignments, leases, presentations,
findings and decisions remain immutable. The new corrected version sets only
`recommendation_promoted=true` and `correction_created=true`. It resets readiness, request,
assignment, inspection, findings and track decisions and sets recommendation approval, final
disposition, workflow, ITSM, execution, deployment and infrastructure mutation false.

The new promoted artifact is eligible only for the existing deterministic readiness service through
an internal correction-aware source. Readiness revalidates the exact protected artifact and policy;
no prior readiness check, reviewer assignment, pass result or finding is inherited. A failed or
blocked new readiness assessment does not reopen the prior review generation.

### Read, Failure And Audit

Only the accountable correction owner may read minimized metadata while identity, tenant, browser,
policy and permission authority remain current. Internal artifact reads require the same owner
authority for interactive readiness creation and exact integrity proof for downstream lineage.
Responses use strict `no-store`, `nosniff`, no-referrer and restrictive content-security headers.

Intent, claim, trusted-adapter completion, persistence completion and read are separately audited.
Audit excludes findings, corrected content, artifact coordinates, cookies, raw identity and secrets.
Policy, lineage, permission, MFA, separation, browser, adapter, receipt, artifact rehydration,
persistence, audit, concurrency or integrity uncertainty fails closed.

## Consequences

### Positive

- Rejected review evidence remains immutable and attributable.
- Every material correction becomes a new recommendation version and new readiness assessment.
- Prior track passes, findings and leases cannot leak into the corrected generation.
- Corrected content remains inside a trusted protected-artifact boundary.

### Costs

- Production requires an approved durable correction adapter and protected artifact provider.
- Both review tracks must finish before one consolidated correction can begin.
- Append-only corrected versions consume additional protected artifact and metadata storage.

## Rejected Alternatives

### Edit The Existing Recommendation Or Decision

Rejected because it destroys the exact artifact and evidence that reviewers assessed.

### Accept Corrected Content In The Ordinary API

Rejected because sensitive infrastructure guidance would enter request logs, audit, telemetry and
ordinary metadata persistence.

### Reuse Prior Readiness Or Track Passes

Rejected because changed content invalidates structural safety checks and every human observation.

### Create A New Review Request Directly

Rejected because ADR-069 requires the corrected upstream artifact to pass a fresh deterministic
readiness assessment before human review can be requested.

### Treat Resubmission As Approval

Rejected because correction, review readiness, final recommendation disposition and operational
authorization are independent accountable boundaries.

## Follow-Up

Later independent contracts cover final recommendation disposition after both tracks pass,
workflow and ITSM handoff, suspension, supersession, retention, controlled export and any
separately approved operation.
