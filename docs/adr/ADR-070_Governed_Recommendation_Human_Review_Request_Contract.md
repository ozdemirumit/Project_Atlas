# ADR-070: Governed Recommendation Human Review Request Contract

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-09 |
| Owners | Product Owner, Architecture Owner, Security Architecture, Governance and Workflow Owner |
| Decision Scope | Creation of one non-decisional human-review request from an exact ready recommendation |
| Related Documents | ATLAS-003, ATLAS-014, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-037, ATLAS-043, ATLAS-044, ATLAS-046, ATLAS-047, ATLAS-050, ATLAS-052, ATLAS-053, ATLAS-056, ADR-063 through ADR-069 |

## Context

ADR-069 permits one exact promoted recommendation draft to receive an immutable deterministic
`ready` or `blocked` assessment. A ready assessment proves only that explicit structural,
freshness, evidence, impact, risk, interruption, recovery and authority-boundary checks passed.
It does not create accountable human-review work, select a reviewer or record a decision.

Atlas needs a separate transition from `ready_for_review` to `review_requested`. The transition
must preserve the complete recommendation and readiness lineage while preventing the requester,
AI or an integration from choosing reviewers, weakening required review tracks, opening protected
content, recording a review outcome or creating approval and operational authority.

## Decision

Atlas will add one governed recommendation human-review request service. It accepts one exact,
unexpired, integrity-valid ready assessment and one signed review-request policy, rehydrates the
unchanged promoted recommendation and complete protected lineage through ADR-069, and creates one
immutable minimized review-request record.

The record places policy-selected review tracks in `awaiting_reviewer`. It does not assign an
identity, disclose additional content, create an approval request, open an ITSM record or workflow,
or authorize execution, deployment or infrastructure mutation.

### Caller Contract

The caller may provide only:

- exact recommendation, readiness assessment and canonical digest bindings;
- exact signed review-request policy ID and digest;
- the unchanged bounded review purpose;
- acknowledgements that request creation is not assignment or review, does not select routing,
  and creates no approval or operational authority;
- browser-bound session, idempotency and correlation identifiers.

The caller cannot provide or override outcome, option, recommendation content, readiness result,
reason code, track, queue, reviewer identity, reviewer group, assignment strategy, priority, due
date, decision, rationale, correction, approval, workflow, ITSM, target, capability, command,
execution, deployment or mutation fields.

### Authorization And Actor Separation

Only the same current enterprise human consumer bound to the recommendation and readiness lineage
may create or read the request. The consumer requires hardware-backed MFA, a current browser-bound
session, exact tenant and environment scope and dedicated default-deny C1 create/read permissions.

The requester may initiate review orchestration because request creation is not a review decision.
The request does not make the requester a reviewer, approver or operator. Later assignment and
decision contracts enforce eligibility, separation of duties, scope, stage and quorum independently.

Production has no synthetic policy or orchestration fallback. Missing policy, source, permission,
trusted adapter or verification evidence fails closed.

### Source And Lineage Contract

The source must be one exact readiness assessment with:

- `evaluation_outcome=ready`, `state=ready_for_review` and
  `recommendation_ready_for_review=true`;
- all human review, approval, workflow, ITSM, execution, deployment and mutation flags false;
- current retention, browser, tenant, consumer, policy, evaluator, receipt and canonical bindings;
- an exact unchanged promoted recommendation and complete presentation, adjudication, candidate,
  impact, risk-recovery, evidence, graph, answer, model, retrieval and source lineage; and
- unchanged outcome, option count, preferred count, purpose and source artifact digest.

A blocked, expired, superseded, changed or integrity-invalid assessment cannot create a request.
Acknowledgement cannot waive a failed readiness gate.

### Signed Review-Request Policy

The immutable policy defines:

- source and output schemas, state and retention limits;
- trusted orchestration adapter and attestor identities;
- required review-track codes, opaque queue IDs, routing profile and SLA class;
- supported source outcomes and maximum track count;
- browser, tenant, consumer and no-authority bindings; and
- required receipt, immutable-storage and audit proofs.

Track and queue routing is policy-owned. The caller, model and source recommendation cannot choose
or remove a review track.

### Atomic One-Way Claim

After authorization, source verification and intent audit, Atlas creates one immutable claim with
a unique constraint on the exact readiness assessment and recommendation version. Claim creation
precedes orchestration and is the point of no return.

Exact idempotent replay reauthorizes the caller and verifies claim, request, browser, policy,
source, retention, routing, receipt and every canonical digest before returning the same record.
Changed input conflicts. A claimed uncertain outcome is reconciled separately and is never retried
automatically or converted into a second request.

### Trusted Orchestration Boundary

The trusted deterministic adapter receives only immutable identifiers, digests, policy-selected
track and queue metadata, limits and timestamps. It performs no model call, network call,
notification, external workflow, ITSM operation or infrastructure action in this foundation.

The adapter verifies the exact instruction, creates one immutable review manifest, sets every
required track to `awaiting_reviewer`, writes the bounded manifest atomically and returns one
signed minimized receipt. It cannot assign a reviewer, open protected content, change the
recommendation, record a decision or expand authority.

### Review Request Record

The minimized record contains:

- review-request, recommendation, promotion and readiness assessment identifiers;
- organization, environment, classification, source outcome and bounded aggregate counts;
- signed policy ID/version, opaque orchestrator identity and manifest digest;
- policy-selected track codes, opaque queue IDs, routing profile, SLA class and per-track status;
- requester subject digest, purpose, timestamps, immutable-storage proof and canonical digest.

The record sets `review_requested=true` and `state=review_requested`. `reviewer_assigned`,
`content_inspection_opened`, `human_review_completed`, `recommendation_approved`,
`workflow_created`, `itsm_record_created`, `execution_authorized`, `deployment_authorized` and
`infrastructure_mutated` remain false.

Ordinary persistence and API/UI omit raw subject identity, browser binding, claim, receipt,
authorization, protected-vault and complete protected-lineage details. Responses expose only safe
catalog identifiers, routing codes, aggregate counts, status, timestamps and non-sensitive digests.

### Failure And Audit

Authorization denial occurs before source rehydration. Intent audit precedes claim creation; claim
audit follows successful claim persistence; completion audit precedes record persistence; and each
replay emits a separate read audit. Audit uses stable identifiers, track codes, states and result
codes only.

Policy, source, adapter, attestation, audit, persistence, integrity, cleanup or replay uncertainty
fails closed and returns no partial record. No failure grants assignment, review, approval,
workflow, ITSM or operational authority.

## Consequences

### Positive

- Only structurally ready, unchanged recommendation versions can enter human-review orchestration.
- Review routing is deterministic, policy-owned and separate from requester preference.
- Request creation is auditable without being confused with reviewer assignment or a decision.
- Uncertain outcomes cannot silently create duplicate review work.

### Costs

- The lifecycle gains another immutable claim, policy, receipt and persistence boundary.
- Production requires a separately trusted orchestration adapter and signed policy source.
- Reviewer assignment and decision remain unavailable until later independent contracts land.

## Rejected Alternatives

### Assign A Reviewer During Request Creation

Rejected because requester-controlled or implicit assignment collapses routing and accountable
eligibility checks and can enable self-review.

### Treat Readiness As An Open Review Request

Rejected because readiness proves deterministic completeness, not organizational routing or human
accountability.

### Reuse Operational Approval Requests

Rejected because recommendation review evaluates decision-support quality and uncertainty, while
operational approval binds consequential action authority. Combining them would misrepresent both.

### Create An External Workflow Or ITSM Record

Rejected because local immutable review orchestration is not external side-effect authority.

## Follow-Up

Later independent contracts cover reviewer assignment and protected inspection, recommendation
review decision and correction, suspension, supersession, retention, controlled export, planning
approval, workflow or ITSM handoff and any human-approved automation.
