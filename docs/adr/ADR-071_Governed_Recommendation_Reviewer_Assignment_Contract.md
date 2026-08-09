# ADR-071: Governed Recommendation Reviewer Assignment Contract

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-10 |
| Owners | Product Owner, Architecture Owner, Security Architecture, Identity Governance, Governance and Workflow Owner |
| Decision Scope | Assignment of distinct accountable humans to one exact recommendation review request |
| Related Documents | ATLAS-003, ATLAS-014, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-037, ATLAS-043, ATLAS-044, ATLAS-046, ATLAS-047, ATLAS-050, ATLAS-052, ATLAS-053, ATLAS-056, ADR-063 through ADR-070 |

## Context

ADR-070 creates one immutable recommendation review request with policy-selected technical and
service-impact tracks. Both tracks remain `awaiting_reviewer`; the request assigns no identity,
opens no protected content and records no human judgement.

Atlas must bind each track to an accountable eligible human before any protected inspection can
open. Assignment must not permit caller selection, self-review, one person controlling both
tracks, identity disclosure, content access, review decisions or operational authority.

## Decision

Atlas will add one governed recommendation reviewer-assignment service. It atomically claims one
exact completed ADR-070 request, instructs a narrow trusted directory-and-routing adapter to select
two distinct eligible enterprise humans, verifies a signed minimized receipt and stores immutable
track assignments containing only opaque assignment IDs and salted subject digests.

Success changes only the local review lifecycle from `review_requested` to `reviewers_assigned`.
It does not open content, record a finding or decision, approve a recommendation, create workflow
or ITSM state, or authorize execution, deployment or infrastructure mutation.

### Caller Contract

The caller may provide only:

- exact review-request ID and canonical digest;
- exact signed reviewer-assignment policy ID and digest;
- the unchanged bounded review purpose;
- acknowledgements that the caller cannot choose reviewers, both tracks require distinct eligible
  humans, and assignment grants no inspection, decision, approval or operational authority;
- browser-bound session, idempotency and correlation identifiers.

The caller cannot provide or override reviewer identity, username, email, group, role, directory
query, track, queue, eligibility rule, exclusion, workload, priority, due date, assignment outcome,
delegation, content, evidence, finding, decision, rationale, correction, approval, workflow, ITSM,
target, capability, command, execution, deployment or mutation fields.

### Authorization And Actor Separation

Creation requires a current enterprise human with hardware-backed MFA, exact browser, tenant and
environment scope and a dedicated default-deny C3 permission. Reading minimized assignment state
requires a dedicated C1 permission.

The request creator may ask Atlas to run policy-controlled assignment because this action does not
select a person or perform review. The adapter must exclude the recommendation consumer, review
requester, assignment requester, signed-policy actor, adapter attestor and every trusted upstream
exclusion subject. Neither assigned reviewer may be the other track's reviewer.

Production has no synthetic policy, directory or assignment fallback. Missing policy, source,
permission, trusted adapter, current directory evidence or separation proof fails closed.

### Source And Lineage Contract

The source must be one exact, unexpired and integrity-valid ADR-070 record with:

- `state=review_requested` and `review_requested=true`;
- technical and service-impact tracks both `awaiting_reviewer` with unchanged policy-owned queues;
- `reviewer_assigned=false` and all inspection, review, approval, workflow, ITSM, execution,
  deployment and mutation flags false;
- current request, readiness, recommendation, promotion, presentation and complete protected
  evidence lineage; and
- unchanged tenant, browser, requester, purpose, routing, policy, receipt, retention and canonical
  digest bindings.

Expired, superseded, already assigned, changed or integrity-invalid requests cannot be assigned.

### Signed Assignment Policy

The immutable policy defines:

- required source/output schemas, source state, exact track and opaque queue codes;
- directory snapshot source, freshness, eligibility, competence, clearance and workload limits;
- requester, upstream actor, signer, attestor, conflict and cross-track separation rules;
- assignment strategy, TTL, retention, browser binding and subject-digest salt;
- trusted adapter and attestor IDs, receipt schema and required cleanup proofs.

Policy owns every selection input. The caller, model and source recommendation cannot alter the
candidate pool or influence which eligible person is chosen.

### Atomic One-Way Claim

After authorization, source verification and intent audit, Atlas creates one immutable claim with
a unique constraint on the exact review-request version. Claim persistence precedes directory
resolution and is the point of no return.

Exact idempotent replay reauthorizes the actor and verifies claim, source, browser, policy,
assignment, retention, receipt and canonical digests before returning the same record. Changed
input conflicts. A claimed uncertain result is not retried or converted into a second assignment.

### Trusted Assignment Boundary

The adapter receives only immutable IDs and digests, policy-selected track and queue metadata,
salted exclusion-subject digests, limits and timestamps. Raw recommendation content, evidence,
credentials, prompts, model output and infrastructure coordinates never enter the adapter.

The adapter must:

1. verify the exact instruction, request manifest, policy and routing bindings;
2. resolve a current directory snapshot of eligible hardware-MFA humans for each queue;
3. enforce tenant, identity status, role, competence, clearance, workload and conflict rules;
4. exclude every requester, upstream, policy and attestation actor digest;
5. select one technical and one service-impact reviewer deterministically and prove distinction;
6. create immutable opaque assignment IDs with status `assigned` and bounded expiry;
7. retain identity references only in an approved encrypted protected store and return salted
   subject digests to the application;
8. compute routing, eligibility, separation, assignment and artifact digests;
9. close directory and protected-store channels and erase transient identity buffers;
10. return one signed minimized receipt without raw subject IDs or identity attributes.

Development may use a fixed deterministic no-network synthetic directory and adapter. It must not
use a model, contact external systems, open content, create workflow or perform infrastructure
operations.

### Assignment Record

The minimized immutable record contains:

- assignment-set, review-request, recommendation, readiness and promotion identifiers;
- technical/service-impact opaque assignment IDs, salted reviewer digests, track/queue codes and
  `assigned` statuses;
- signed policy ID/version, opaque adapter identity, assignment/routing/eligibility/separation and
  manifest digests;
- tenant, environment, classification, purpose, timestamps, expiry and cleanup proofs; and
- canonical digest and safe lifecycle flags.

It sets `reviewer_assigned=true` and `state=reviewers_assigned` while
`content_inspection_opened`, `human_review_completed`, `recommendation_approved`,
`workflow_created`, `itsm_record_created`, `execution_authorized`, `deployment_authorized` and
`infrastructure_mutated` remain false.

Ordinary persistence and API/UI omit raw identities, usernames, email, group membership,
directory attributes, protected-store coordinates, claim, receipt, authorization, browser and
complete protected-lineage details. Assignment does not create a reusable content-access handle.

### Failure And Audit

Authorization denial occurs before source rehydration or directory access. Intent audit precedes
claim creation; claim audit follows persistence; completion audit precedes record persistence; and
each replay emits a separate read audit.

Any policy, source, directory, eligibility, separation, adapter, attestation, audit, persistence,
cleanup, integrity or replay uncertainty fails closed. A failure returns no partial identity or
assignment record and grants no inspection, review, approval or operational authority.

## Consequences

### Positive

- Technical correctness and service-impact review are bound to distinct accountable humans.
- Requesters cannot select themselves, collude through caller-supplied routing or observe raw
  identity attributes.
- Assignment is auditable without opening protected content or implying a decision.
- Uncertain directory outcomes cannot silently duplicate assignments.

### Costs

- Production requires trusted directory/routing integration and current eligibility data.
- Assignment expiry and uncertainty require explicit reconciliation or reassignment governance.
- Protected inspection remains unavailable until a separate assignee-bound lease contract lands.

## Rejected Alternatives

### Let The Caller Select Reviewers

Rejected because it enables self-review, collusion, identity disclosure and queue bypass.

### Use One Reviewer For Both Tracks

Rejected because technical correctness and service impact are independent accountabilities.

### Return Raw Reviewer Identity

Rejected because lifecycle observers need assignment state, not directory attributes.

### Open Content During Assignment

Rejected because identity assignment and protected disclosure require separate authorization,
freshness and audit boundaries.

## Follow-Up

Later independent contracts cover uncertain-assignment reconciliation, expiry and reassignment,
track-specific protected inspection leases, findings, recommendation review decisions and
correction, approval, workflow or ITSM handoff and any human-approved automation.
