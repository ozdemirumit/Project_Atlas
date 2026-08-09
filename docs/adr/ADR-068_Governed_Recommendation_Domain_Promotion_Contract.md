# ADR-068: Governed Recommendation Domain Promotion Contract

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-09 |
| Owners | Product Owner, Architecture Owner, AI Architecture, Security Architecture |
| Decision Scope | Promotion of one protected recommendation presentation into the recommendation domain |
| Related Documents | ATLAS-003, ATLAS-010, ATLAS-014, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-026, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-037, ATLAS-043, ATLAS-044, ATLAS-046, ATLAS-047, ATLAS-050, ATLAS-052, ATLAS-053, ATLAS-056, ADR-063 through ADR-067 |

## Context

ADR-067 permits one eligible enterprise human to receive a bounded, inert and evidence-linked
presentation of an exact protected recommendation adjudication. That presentation is deliberately
separate from the existing recommendation domain and does not establish review readiness.

Atlas now needs a governed bridge into the durable recommendation lifecycle. The bridge must
preserve the exact preferred, tie or no-support outcome and create an immutable domain artifact
without exposing protected candidate records, inventing executable detail or granting authority.
Promotion is a provenance-preserving state transition, not a second recommendation-generation or
ranking pass.

## Decision

Atlas will add one governed recommendation-domain promotion service. It accepts one exact,
completed protected presentation and one signed promotion policy. Inside the trusted boundary it
rehydrates and independently verifies the complete presentation, adjudication, candidate, impact,
risk-recovery and evidence lineage. It then creates one immutable, minimized recommendation-domain
artifact whose content is derived only from the verified presentation and protected source.

The promoted artifact starts in `draft`. It is not ready for review, approved, planned, dispatched
or executable. A later independent contract may evaluate review readiness.

### Entry Contract

Only the same eligible enterprise human consumer may request or read the promoted artifact. The
consumer must use the same current browser-bound session with hardware-backed MFA, current C1
create/read permissions and unchanged organization, environment and purpose.

The source must be one exact, completed, unexpired, integrity-valid presentation. The service
rehydrates and verifies the unchanged:

- presentation record, redacted content and protected receipt;
- presentation, adjudication, candidate, impact and risk-recovery policies;
- protected adjudication outcome and complete candidate set;
- evidence snapshot, graph, answer, model, retrieval and source lineage;
- tenant, consumer, browser, purpose, classification and retention bindings; and
- every canonical digest and protected-vault artifact.

The caller supplies only exact presentation and policy identifiers and digests, unchanged purpose,
explicit acknowledgements that promotion creates no review, approval or operational authority,
an idempotency key and correlation context. Outcome, preferred option, content, plan, target,
capability, approval, workflow, command, execution and mutation controls are forbidden.

### Promotion Policy

The immutable signed policy defines required source schemas and states, trusted promoter identity,
allowed outcomes, domain schema version, redaction and classification rules, count and size limits,
retention, expiry, source binding and browser binding. Caller values never weaken policy.

Production has no synthetic policy or promoter fallback and fails closed when an approved signed
policy or trusted promoter is unavailable.

### Promoted Artifact

The immutable artifact contains:

- stable promotion and recommendation IDs, version, owner and `draft` state;
- organization, environment, site, audience, purpose and expiry;
- exact presentation and protected-source lineage digests;
- preserved `preferred`, `tie` or `no-support` outcome;
- safe displayed options, rationale, risk, impact, duration, interruption and recovery summaries;
- bounded evidence references, assumptions, gaps and unknowns;
- policy, promoter and schema versions; and
- fixed false flags for review readiness, approval, workflow, ITSM, execution and mutation.

Raw protected candidates, graph paths, comparison values, scores, evidence payloads, commands,
endpoints, credentials, tool calls and authorization material do not enter ordinary recommendation
persistence or browser output.

### Outcome Preservation

- `preferred` promotes exactly the displayed preferred option and displayed alternatives.
- `tie` promotes co-equal displayed options and no preferred option.
- `no-support` promotes an explicit no-support artifact and no preferred option.

Promotion cannot add, remove, reorder, rerank or rewrite options. It cannot turn uncertainty into
confidence or a gap into a satisfied precondition.

### Persistence and Replay

One immutable claim is unique by presentation and consumer/idempotency binding. Exact replay
returns the same artifact after current authorization, policy, browser, source, retention, vault and
digest checks. Changed or missing source never causes silent regeneration.

Ordinary persistence stores only the minimized artifact, claim and lineage. Protected receipts and
source records remain in the tenant-isolated vault. Intent, claim, completion, replay and failure
emit metadata-only audit events.

### State Boundary

Successful promotion sets recommendation-domain promotion true and leaves false:

- recommendation review readiness or human review decision;
- approval or change-review request;
- workflow or ITSM creation;
- connector invocation or execution authorization;
- deployment authorization; and
- infrastructure mutation.

The API is browser-session-bound, CSRF-protected and `no-store`. Failure of authorization, audit,
policy, source integrity, retention, vault, attestation or persistence stops promotion.

## Consequences

Atlas gains a durable recommendation-domain record without collapsing protected analysis into
ordinary storage or implying operational authority. The additional policy, claim, vault and replay
checks increase implementation cost but make promotion reproducible, tenant-isolated and auditable.

## Required Verification

- preferred, tie and no-support outcome-preservation invariants;
- complete source, policy, tenant, purpose, consumer, browser, retention and digest verification;
- no generation, ranking, network or model call during promotion;
- prohibited content, redaction, classification, count and size tests;
- unique claim, idempotency, exact replay and uncertain-persistence tests;
- permission denial before protected source access;
- memory/PostgreSQL parity and one Alembic head;
- strict minimized CSRF/no-store API tests and production fail-closed tests;
- frontend tests for draft state and the absence of review, approval and execution controls; and
- full backend/frontend, migration, live desktop/mobile and GitHub CI validation.

## Follow-on Decisions

Later independent contracts cover recommendation review-readiness evaluation, accountable human
feedback and review, approval/change governance, workflow or ITSM handoff and any separately
authorized assisted execution. None is authorized by this ADR.
