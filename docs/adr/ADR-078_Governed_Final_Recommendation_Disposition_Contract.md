# ADR-078: Governed Final Recommendation Disposition Contract

- Status: Accepted
- Date: 2026-08-10
- Owners: Product Owner, Solution Architecture, Security Architecture, Infrastructure Operations,
  Identity Governance, Data Governance
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-026, ATLAS-027,
  ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-040, ATLAS-041, ATLAS-042,
  ATLAS-043, ATLAS-044, ATLAS-046, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-052, ATLAS-053,
  ATLAS-054, ATLAS-055, ATLAS-056, ADR-009 through ADR-077

## Context

ADR-076 records independent technical and service-impact decisions for one exact immutable
recommendation review generation. ADR-077 creates a fresh recommendation generation when either
track requires correction. Atlas now needs one accountable final disposition when both exact tracks
pass. That disposition must remain separate from review, correction, workflow planning, ITSM
handoff, change approval, execution, deployment and infrastructure mutation.

## Decision

Atlas will implement one dedicated final-recommendation-disposition service. One audited `POST`
binds an eligible human approver's `accepted` or `rejected` disposition to the exact completed,
unchanged recommendation review generation. An audited `GET` returns minimized immutable
disposition metadata.

### Eligibility

The service proceeds only when:

- exactly one technical and one service-impact decision exist for the same immutable review
  request, assignment set, readiness assessment, promoted recommendation version and review-policy
  generation;
- both track dispositions are `review-disposition.passed`, both tracks are complete and neither
  requires correction;
- the promoted recommendation and complete request/readiness lineage remain exact, current,
  integrity-valid and in the same tenant and environment;
- no correction, replacement generation, prior final-disposition claim or completed final
  disposition exists for the exact review request; and
- classification, retention, source binding, consumer binding and safe lifecycle flags remain
  internally consistent.

A missing track, duplicate track, mixed generation, `changes-required` result, caller-shaped
lifecycle state, prior correction, source drift or lineage uncertainty fails before claim creation.

### Dispositions And Basis

The only first-profile dispositions are:

- `recommendation-disposition.accepted`; and
- `recommendation-disposition.rejected`.

The signed policy owns the allowed structured basis codes and their disposition compatibility.
Accepted and rejected results require at least one compatible basis code. Free-form rationale,
finding narrative, severity and caller-defined governance labels are forbidden.

### Caller Contract

The caller may provide only:

- exact review-request ID and canonical digest;
- exact promoted-recommendation ID and canonical digest;
- exact decision IDs and canonical digests for both tracks;
- one allowed disposition and compatible structured basis codes;
- exact signed final-disposition-policy ID and canonical digest;
- a bounded purpose;
- acknowledgements that the reviewed generation is immutable, final disposition is recommendation-
  level decision support only, accepted status grants handoff eligibility rather than workflow or
  operational authority, and no change approval, ITSM record, execution, deployment or
  infrastructure mutation is created; and
- idempotency and correlation identifiers.

The caller cannot provide identity, tenant, approver, reviewer, recommendation content, findings,
free-form rationale, risk narrative, approval flags, handoff state, artifact coordinates, model
context, target, credential, command, schedule, workflow, ITSM, execution, deployment or mutation
fields.

### Identity And Separation

The actor must be a current enterprise human in the exact tenant with recent hardware-backed MFA,
dedicated C2 final-disposition-create and lineage-read permissions, a normal browser session,
mutation CSRF and a current signed policy. The actor must be distinct from:

- the original accountable recommendation consumer;
- both technical and service-impact reviewers;
- the final-disposition policy signer and trusted attestor; and
- every service, shared, AI and break-glass identity.

Reviewer lease cookies grant no final-disposition authority. The operation uses only the approver's
normal authenticated browser binding.

### Trusted Attestation Boundary

An approved trusted attestor signs the exact request, promotion, readiness, assignment aggregate,
both decision bindings, approver binding, disposition, basis, purpose, policy and deterministic
disposition identifier. Production fails closed without an approved attestor. Development may use
a deterministic synthetic attestor with no model, vector store, workflow, ITSM, connector,
credential, target or infrastructure access.

### Atomic Claim And Replay

Required intent audit succeeds before a unique immutable review-request claim is created. The claim
is the point of no return. Exact completed idempotent reuse is permitted only when lineage,
approver, browser, disposition, basis, policy, purpose and request-binding digests match. Failure or
uncertainty after claim creation remains claimed and is never retried automatically. Concurrent or
conflicting dispositions cannot replace the first claim.

### Persistence And Lifecycle Semantics

Application persistence stores immutable metadata and integrity digests only. It stores no
recommendation content, finding narrative, free-form rationale, risk narrative, artifact
coordinate, cookie, raw identity, secret or model output.

Both outcomes set `final_disposition_recorded=true` and preserve exact successful review evidence.
An accepted outcome records `recommendation_final_accepted`, sets
`recommendation_approved=true` and `workflow_handoff_eligible=true`. These flags mean only that the
exact recommendation may enter a later separately authorized workflow/ITSM planning boundary. They
are not change approval or permission to operate.

A rejected outcome records `recommendation_final_rejected`, keeps recommendation approval and
handoff eligibility false and is final for the exact generation. It creates no correction or
replacement version.

Both outcomes leave workflow creation, ITSM creation, change approval, execution authorization,
deployment authorization and infrastructure mutation false. All source artifacts, readiness
assessments, review requests, assignments, leases, presentations, findings, decisions and
corrections remain immutable.

### Read, Failure And Audit

Only the accountable final approver may read minimized disposition metadata while identity, tenant,
policy, browser and permission authority remain current. Responses use strict `no-store`,
`nosniff`, no-referrer and restrictive content-security headers.

Intent, claim, attestation, persistence completion and read are separately audited. Audit excludes
recommendation content, findings, free-form rationale, risk narrative, artifact coordinates,
cookies, raw identity and secrets. Policy, lineage, permission, MFA, separation, browser, attestor,
persistence, audit, concurrency or integrity uncertainty fails closed.

## Consequences

### Positive

- Recommendation acceptance or rejection is attributable, immutable and distinct from review.
- Passing reviewers and the original recommendation consumer cannot self-approve their output.
- Rejection remains first-class and cannot be converted into acceptance by replay or concurrency.
- A later handoff service receives explicit eligibility evidence without being coupled to this
  decision.

### Costs

- Production requires an approved trusted final-disposition attestor.
- A separate eligible approver and recent hardware MFA are required after both reviews pass.
- Rejected generations require a later explicit revision lifecycle rather than silent reuse.

## Rejected Alternatives

### Treat Two Review Passes As Final Acceptance

Rejected because independent review and accountable recommendation acceptance are separate
authorities.

### Accept And Create A Workflow In One Operation

Rejected because workflow planning, ITSM handoff and change governance require separate contracts,
roles and rollback semantics.

### Permit Consumer Or Reviewer Self-Approval

Rejected because generated recommendation ownership, independent review and final accountability
must remain separated.

### Accept Free-Form Final Rationale

Rejected because sensitive operational guidance could leak into metadata, logs, audit or telemetry.

## Follow-Up

Later independent contracts cover workflow and ITSM handoff, change-impact packet completion,
suspension, supersession, retention, controlled export and every separately approved operation.
