# ADR-067: Governed Protected Recommendation Presentation Contract

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-09 |
| Owners | Product Owner, Architecture Owner, AI Architecture, Security Architecture |
| Decision Scope | Accountable presentation of protected recommendation adjudication outcomes |
| Related Documents | ATLAS-003, ATLAS-010, ATLAS-014, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-026, ATLAS-027, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-041, ATLAS-042, ATLAS-043, ATLAS-044, ATLAS-046, ATLAS-047, ATLAS-050, ATLAS-052, ATLAS-053, ATLAS-056, ADR-062, ADR-063, ADR-064, ADR-065, ADR-066 |

## Context

ADR-066 deterministically compares every exact protected candidate and establishes one of three
governed outcomes: exactly one protected preference, a preserved tie, or no supportable candidate.
Candidate identity, content, comparison values, eligibility, exclusions, impact, risk, duration,
interruption, recovery and preference rationale deliberately remain inside the protected vault.

An accountable human cannot make an informed decision from aggregate counts alone. Atlas now
needs an independent presentation boundary that renders the exact adjudication outcome as bounded,
inert, evidence-linked decision support. Presentation must give the human enough information to
understand the recommendation, likely service impact, estimated work and interruption, recovery,
alternatives, gaps and unknowns without exposing raw protected artifacts or creating authority.

Presentation is not promotion into the existing recommendation domain. It does not create a
`RecommendationArtifact`, declare review readiness, request approval, create a workflow, invoke a
connector, issue a command, deploy software or mutate infrastructure.

## Decision

Atlas will add one governed protected recommendation-presentation service. The service accepts one
exact completed protected adjudication and one exact signed presentation policy. It rehydrates the
complete protected candidate, impact, risk-recovery, evidence and adjudication lineage inside the
trusted boundary and invokes a deterministic no-network, no-model presenter.

The presenter produces one bounded `text/plain` presentation for the same eligible enterprise
human consumer. It supports all valid adjudication outcomes:

- `preferred`: present exactly one selected candidate and bounded alternatives;
- `tie`: present the tied supportable candidates without choosing between them; and
- `no-support`: explain that no candidate is supportable without inventing a recommendation.

Success establishes only that the protected adjudication outcome has been presented. Review
readiness, approval, domain promotion, workflow, execution, deployment and infrastructure mutation
remain false.

### Entry Contract

Only the same eligible enterprise human consumer may request or read the presentation. The
consumer must use the same current browser-bound session with hardware-backed MFA, current C1
create/read permissions and the same organization and environment.

The source must be one exact, completed, unexpired, integrity-valid protected adjudication. The
service rehydrates and verifies the unchanged:

- adjudication record, protected receipt, comparison report and selected outcome;
- candidate set and candidate content;
- candidate impact paths, graph snapshot and service-reachability evidence;
- risk, duration, interruption and recovery completion report;
- operational-evidence snapshot and all signed policies;
- answer presentation, draft adjudication, model invocation, model context and retrieval lineage;
- source, classification, citations, unknowns, safety, purpose, consumer and browser bindings; and
- every canonical digest, retention window and protected-vault artifact.

The caller supplies only:

- exact adjudication ID and canonical digest;
- exact signed presentation-policy ID and digest;
- unchanged purpose;
- acknowledgements that presentation is decision support, estimates and impacts remain
  evidence-bounded, and no review, approval, workflow or operational authority is created;
- idempotency key and correlation context.

Candidate IDs, selected candidate, categories, titles, content, steps, evidence, comparison values,
scores, eligibility, exclusions, impact, risk, duration, interruption, recovery, alternative order,
target, capability, operation, command, workflow, approval, deployment and mutation controls are
forbidden request fields.

### Presentation Policy

The immutable signed policy defines:

- required source schemas and completed adjudication state;
- required presenter and attestor identities;
- the three allowed adjudication outcomes and exact outcome-preservation rules;
- classification ceiling and inert `text/plain` rendering profile;
- allowed presented fields and prohibited secret, endpoint, command and active-content profiles;
- maximum candidate, alternative, step, service, citation, gap and unknown counts;
- maximum title, summary, rationale and item character lengths;
- maximum output bytes and retention window;
- service-label and evidence-reference redaction profiles; and
- browser-binding and source-binding requirements.

Caller values never override policy. Production has no synthetic policy or presenter fallback and
fails closed when an approved signed policy or trusted presenter is unavailable.

### Presented Content

For a single preferred outcome, the bounded presentation may contain:

- safe candidate title and recommendation category;
- concise evidence-linked rationale and confidence label;
- ordered conceptual implementation steps without raw commands, parameters, credentials,
  endpoints or executable payloads;
- maximum risk and uncertainty labels;
- estimated work, interruption and recovery ranges;
- recovery feasibility, rollback or recovery summary and point-of-no-return warning when present;
- bounded affected technical and business-service display labels;
- evidence references, gaps, unknowns and assumptions; and
- bounded alternative summaries and policy reasons they were not preferred.

For a tie, the presentation contains each tied supportable option under equal visual and semantic
weight and explicitly states that Atlas selected none. For no-support, it presents bounded policy
reasons, gaps and next evidence needs and contains no selected candidate.

Raw candidate IDs, entity IDs, graph paths, protected comparison dimensions, internal scores,
authorization digests, secret references, credentials, vendor endpoints, commands, tool calls,
HTML, Markdown, scripts and executable content never cross the presentation boundary.

### Trusted Presentation Boundary

The presenter must:

1. verify the instruction and complete protected source lineage independently;
2. preserve the exact adjudication outcome without ranking or generating candidates;
3. select content only from source-bound protected artifacts;
4. redact prohibited identifiers and active or operational content;
5. enforce all count, character, byte, classification and retention limits;
6. preserve risk, interruption, recovery, gaps and unknowns conservatively;
7. render inert `text/plain` structured content;
8. produce a signed receipt binding source, outcome, content, redaction and cleanup digests; and
9. retain raw source artifacts only in the protected vault.

No LLM, vendor network, connector invocation or external service participates in presentation.

### Persistence and API Boundary

One immutable claim is unique by adjudication and by consumer/idempotency binding. Exact replay
returns the same verified presentation after current authorization, policy, browser, source,
retention, vault and digest checks and never re-renders against changed inputs.

Ordinary persistence stores minimized lineage, policy/presenter bindings, outcome, counts, digests,
timestamps, fixed safety flags and the already-redacted presented content. Full protected reports,
raw candidates, graph paths, comparison dimensions, evidence payloads and receipts remain in the
tenant-isolated presenter vault.

The browser API is CSRF-protected, no-store and browser-session-bound. The response exposes only
the bounded presented content plus minimized metadata. Audit, logs and metrics contain no raw
protected candidate or evidence content.

### State Boundary

Successful presentation sets:

- candidate, impact, risk, duration, interruption, recovery and adjudication completion true; and
- recommendation presentation true.

It leaves false:

- existing-domain recommendation promotion;
- recommendation review readiness and approval;
- approval request or change-review creation;
- workflow or ITSM creation;
- connector invocation or execution authorization;
- deployment authorization; and
- infrastructure mutation.

### Failure and Replay

The service fails closed on missing permission, subject or browser mismatch, expired source,
policy mismatch, vault loss, outcome drift, source/digest failure, over-limit rendering,
prohibited content, presenter unavailability, attestation failure or uncertain persistence.

Intent is audited before claim acquisition. Claim acquisition, completion, exact replay and denied
or failed attempts emit metadata-only audit events. A claim without a durable presentation is not
reported as success and requires governed recovery rather than silent re-presentation.

## Consequences

Humans receive actionable and explainable recommendation evidence while protected internals and
operational authority remain separated. Tie and no-support outcomes remain honest rather than
being forced into a recommendation. The extra policy, vault, receipt and replay boundaries add
implementation cost but preserve enterprise auditability and the immutable principle that Atlas
advises while humans decide.

## Required Verification

- domain invariants for preferred, tie and no-support presentations;
- complete source, policy, consumer, browser, tenant, retention and digest verification;
- deterministic outcome preservation and no-model/no-network enforcement;
- prohibited content, active rendering, redaction, size and classification tests;
- unique claim, idempotency, exact replay and uncertain persistence tests;
- permission denial before protected source access;
- memory/PostgreSQL parity and one Alembic head;
- strict minimized request/response and CSRF/no-store API tests;
- production fail-closed tests;
- frontend tests for all three outcomes and no-authority state; and
- full backend/frontend, migration, live desktop/mobile and GitHub CI validation.

## Follow-on Decisions

Later independent contracts cover promotion into the existing recommendation domain, accountable
human feedback and review readiness, approval/change governance, workflow or ITSM handoff and any
separately authorized assisted execution. None is authorized by this ADR.
