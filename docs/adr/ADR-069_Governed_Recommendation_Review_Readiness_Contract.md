# ADR-069: Governed Recommendation Review Readiness Contract

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-09 |
| Owners | Product Owner, Architecture Owner, AI Architecture, Security Architecture |
| Decision Scope | Deterministic review-readiness evaluation of one promoted recommendation draft |
| Related Documents | ATLAS-003, ATLAS-014, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-026, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-037, ATLAS-043, ATLAS-044, ATLAS-046, ATLAS-047, ATLAS-050, ATLAS-052, ATLAS-053, ATLAS-056, ADR-063 through ADR-068 |

## Context

ADR-068 permits one exact protected recommendation presentation to become an immutable,
minimized recommendation-domain artifact in `draft`. Promotion deliberately does not establish
that the draft is complete, current or eligible for accountable human review.

Atlas needs a separate deterministic gate between promotion and human review. The gate must prove
that one unchanged draft satisfies an explicit signed readiness policy without interpreting the
draft as approved advice, choosing an option, expanding content or granting operational authority.
Readiness is a structural and governance result, not a human decision or technical endorsement.

## Decision

Atlas will add one governed recommendation review-readiness service. It accepts one exact promoted
recommendation draft and one signed readiness policy, rehydrates and verifies the complete
promotion and protected source lineage, and emits one immutable minimized readiness assessment.

The assessment outcome is `ready` or `blocked`. A ready assessment permits a later independent
human-review request to reference the exact draft and assessment. It does not create that request,
assign a reviewer, record a review decision, approve planning, create an ITSM record or workflow,
or authorize execution, deployment or infrastructure mutation.

### Entry Contract

Only the same eligible enterprise human consumer may request or read an assessment. The consumer
must use the same current browser-bound session with hardware-backed MFA, current C1 create/read
permissions and unchanged organization, environment and purpose.

The source must be one exact, unexpired, integrity-valid promoted recommendation artifact in
`draft`. The service rehydrates and verifies the unchanged:

- promotion claim, artifact, receipt and signed promotion policy;
- protected presentation, adjudication, candidate, impact and risk-recovery lineage;
- evidence, graph, answer, model, retrieval and source lineage;
- outcome, displayed options, evidence needs and safe content;
- tenant, consumer, browser, purpose, classification and retention bindings; and
- every canonical digest and protected-vault artifact required by the promotion contract.

The caller supplies only exact recommendation and policy identifiers and digests, unchanged
purpose, explicit no-authority acknowledgements, idempotency and correlation. Outcome, option,
readiness result, reason codes, content, reviewer, decision, approval, workflow, command,
execution and mutation controls are forbidden.

### Readiness Policy

The immutable signed policy defines required source schemas and state, trusted evaluator and
attestor identities, supported outcomes, required option and evidence fields, freshness and
retention limits, bounded reason taxonomy, browser binding, and output schema. Caller values never
weaken policy.

Production has no synthetic policy or evaluator fallback and fails closed when an approved signed
policy or trusted evaluator is unavailable.

### Deterministic Evaluation

The trusted evaluator performs no model or network call. It validates:

- exact source and policy integrity and freshness;
- outcome and option-role consistency for preferred, tie and no-support;
- bounded safe option content and contiguous conceptual step order;
- non-empty rationale, confidence rationale, safety notice and purpose;
- risk, impact, duration, interruption and recovery presentation fields;
- visible assumptions, unknowns, gaps, applicability limits and evidence needs;
- absence of protected identifiers, commands, endpoints, tool calls and authority fields; and
- all no-review, no-approval, no-workflow, no-execution and no-mutation source flags.

Missing or inconsistent requirements produce `blocked` with deterministic bounded reason codes.
The evaluator never repairs, supplements, reranks or rewrites the draft. A blocked draft requires a
later governed correction or new upstream version; acknowledgement cannot waive a failed gate.

### Readiness Assessment

The immutable assessment contains:

- stable assessment, recommendation and promotion IDs and version;
- organization, environment, consumer, purpose and expiry bindings;
- exact source artifact, claim, receipt and policy digests;
- evaluator, attestor, schema and readiness-policy versions;
- `ready` or `blocked`, bounded reason codes and aggregate completeness counts;
- source outcome and option count;
- assessment and source-binding digests; and
- fixed false flags for human review, approval, workflow, ITSM, execution and mutation.

Ordinary API and UI output omit consumer, browser, authorization, claim, receipt, source-binding and
protected-vault identifiers. They expose only the safe outcome, counts, bounded reason codes,
timestamps, policy/evaluator versions and no-authority flags.

### Idempotency And Replay

One immutable claim exists per promoted recommendation version. Exact idempotent replay
reauthorizes the caller and revalidates claim, policy, source, browser, retention, vault and every
digest before returning the same assessment. Changed input under the same idempotency key fails.
Another assessment requires a new upstream recommendation version; readiness is never silently
recomputed against changed evidence.

### State Boundary

A `ready` assessment establishes only `recommendation_ready_for_review=true` for the exact assessed
draft lineage. It leaves `human_review_completed`, `recommendation_approved`, `workflow_created`,
`itsm_record_created`, `execution_authorized`, `deployment_authorized` and
`infrastructure_mutated` false.

A `blocked` assessment leaves every lifecycle authority flag false, including
`recommendation_ready_for_review`.

### Failure And Audit

Authorization denial occurs before source rehydration. Intent audit precedes claim creation; claim
audit follows a successful claim; evaluation completion audit precedes ordinary persistence; and
every replay has a separate read audit. Audit contains identifiers, outcome and bounded reason
codes only, never safe option prose, protected content, handles or credentials.

Policy, source, evaluator, attestation, audit, persistence, cleanup, integrity or replay uncertainty
fails closed and returns no partial assessment. A claimed uncertain outcome requires governed
investigation and is not automatically evaluated again.

## Consequences

### Positive

- A promoted draft cannot enter human review merely because it exists.
- Readiness remains deterministic, explainable, replayable and separate from human judgement.
- Preferred, tie and no-support outcomes remain valid review subjects without forced selection.
- Missing safety information blocks review without allowing acknowledgements to waive policy.
- Approval and execution domains cannot consume an unassessed or blocked draft.

### Costs

- Readiness adds another immutable artifact, policy, claim and persistence boundary.
- Material corrections require a new upstream recommendation version and new assessment.
- Production requires an independently trusted evaluator and signed policy source.

## Rejected Alternatives

### Mark Every Promoted Draft Ready

Rejected because promotion proves lineage preservation, not review completeness or freshness.

### Let A Reviewer Decide Readiness While Reviewing

Rejected because missing structural safety data must block reviewer assignment before disclosure
and cannot be normalized into a discretionary review decision.

### Use An LLM To Judge Completeness

Rejected because readiness requirements are explicit deterministic policy gates and must not vary
with model output.

### Update The Promoted Artifact In Place

Rejected because recommendation artifacts and lifecycle evidence are immutable. Readiness is a
separate version-bound assessment.

## Follow-Up

Later independent contracts cover accountable human review request and assignment, review
decision and correction, suspension, supersession, retention, controlled export, planning
approval, workflow or ITSM handoff and any human-approved automation.
