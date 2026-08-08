# ADR-065: Governed Protected Candidate Risk, Interruption, Duration, And Recovery Completion Contract

- Status: Accepted
- Date: 2026-08-08
- Owners: Product Owner, Solution Architecture, Security Architecture, AI Platform Engineering,
  Decision Intelligence, Service Reliability Engineering, Identity Governance, Data Governance
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-026, ATLAS-027,
  ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-040, ATLAS-041, ATLAS-042,
  ATLAS-043, ATLAS-044, ATLAS-046, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-052, ATLAS-053,
  ATLAS-054, ATLAS-055, ATLAS-056, ADR-009 through ADR-064

## Context

ADR-064 binds every candidate in one exact protected candidate set to one immutable authorized
infrastructure-graph snapshot. That result establishes modeled dependency reachability only. It
does not establish whether a conceptual action will interrupt a service, how long work or
interruption may last, how risk should be classified, or whether recovery is credible.

Graph reachability alone cannot answer those questions. A governed assessment also needs current,
immutable and policy-selected evidence about capability semantics, runtime health, redundancy,
failover, vendor procedure applicability, historical duration ranges, recovery paths, data
protection, service criticality and evidence uncertainty. Missing evidence must increase or block
the assessment; it must never be silently invented by an LLM or supplied by the caller.

A separate protected boundary is required before deterministic candidate adjudication. It must
complete the risk, interruption, duration and recovery evidence for every candidate while keeping
candidate-specific reasoning protected and preserving the rule that completion is not preference,
recommendation, approval or authority to act.

## Decision

Atlas will implement one governed protected candidate risk, interruption, duration and recovery
completion service. A human-initiated `POST` may create one immutable completion record for one
exact eligible protected candidate-impact analysis. The service authorizes against minimized
metadata before rehydrating the protected candidate set and impact report through trusted source
boundaries.

A policy-selected immutable operational-evidence snapshot and a deterministic trusted assessor
produce one protected completion entry for every candidate. The completed report is an input to a
later adjudication stage. It is not a preferred option, final recommendation, user-visible
candidate, approval packet, workflow, execution plan, deployment instruction or authority to act.

### Source Eligibility

Completion proceeds only when:

- the exact impact-analysis record exists, completed successfully, remains unexpired and
  integrity-valid, and is bound to the same human consumer, browser, tenant, environment, purpose,
  candidate set, graph snapshot, policies, analyzer, receipts and protected-vault lineage;
- impact analysis is the latest completed downstream state and risk, interruption, duration,
  recovery, adjudication, presentation, promotion, approval, workflow, execution, deployment and
  infrastructure mutation remain absent;
- current authorization can independently rehydrate and verify the exact protected candidate set,
  impact report and both upstream receipts without content drift;
- a current signed completion policy resolves the assessor, required risk dimensions, risk floor
  rules, operational-evidence source, accepted evidence kinds, freshness limits, duration and
  interruption models, recovery requirements, schemas, budgets, retention, cleanup, disclosure
  profile and unknown handling; and
- no conflicting completion claim exists for the impact analysis or idempotency key.

Expired, cross-tenant, caller-shaped, policy-stale, source-divergent, evidence-missing beyond policy,
freshness-incompatible, artifact-missing, access-denied, classification-incompatible,
partial-looking or integrity-uncertain state fails before protected content is assessed.

### Caller Contract

The caller may provide only:

- exact impact-analysis ID and canonical digest;
- exact signed completion-policy ID and digest;
- the unchanged purpose;
- acknowledgements that estimates are evidence-bounded rather than guarantees, unknown evidence
  cannot lower risk, and completion creates no preference or operational authority; and
- idempotency and correlation identifiers.

The caller cannot provide identity, tenant, role, candidate content or selection, graph target,
service, evidence snapshot, risk dimension, risk level, score, duration, interruption, outage,
redundancy, recovery, rollback, point of no return, confidence, preference, capability, connector,
credential, command, model, endpoint, workflow, approval, deployment or mutation fields.

### Identity And Access

The actor must be the same current enterprise human consumer that owns the protected lineage, in
the exact tenant and environment, with recent hardware-backed MFA, browser binding, CSRF,
dedicated C1 completion create and read permissions, and current source, evidence and
classification access.

Service, shared, AI, break-glass, cross-tenant, policy-signer, evidence-source, assessor, candidate
generator, impact analyzer, recommendation reviewer, workflow and execution identities cannot act
as the human caller. The completion inherits the most restrictive classification and access
constraints of every source artifact and accepted operational-evidence item.

### Operational-Evidence Snapshot

The completion policy selects one immutable evidence snapshot. It may contain only signed,
authorized and time-bounded evidence in these classes:

- capability semantics and declared side-effect class;
- runtime health and active fault observations;
- redundancy, multipath, quorum, replica and failover state;
- vendor procedure applicability and version constraints;
- historical bounded task and interruption observations with sample counts;
- service criticality, availability objective and approved maintenance constraints;
- data-protection state and recovery-point constraints;
- rollback or forward-recovery prerequisites, checkpoints and verification criteria; and
- explicit gaps, conflicts, stale observations and unsupported assumptions.

The snapshot includes identity, version, generation time, expiry, classification, provenance,
coverage and canonical digest. Evidence does not become true because it appears in a document; the
snapshot records whether each assertion is observed, declared, simulated or historical. Free-form
caller evidence, live network discovery during assessment and model-generated evidence are
forbidden.

### Atomic Claim And Replay

Required intent audit succeeds before one immutable claim is created with a unique constraint on
impact-analysis ID. Claim creation is the point of no return. Exact idempotent reuse is permitted
only when subject, browser, request, impact analysis, candidate set, graph, purpose, completion
policy, evidence snapshot, protected report and completed record all match.

Failure or uncertainty after claim creation remains claimed and returns no partial result. The
service never automatically retries assessment, selects fresher evidence, creates a second record,
extends retention or silently falls back to another assessor, policy or evidence source.

An audited metadata `GET` may return the same minimized record while all authorization, source,
policy, evidence, retention, protected-vault and integrity proofs remain current. Protected
candidate-specific risk and recovery content is not returned by this stage.

### Trusted Deterministic Assessor

The application sends only the exact protected candidate set and impact report, their receipts,
the signed completion policy, one policy-selected operational-evidence snapshot, expected lineage
and authorization digests, and an opaque completion ID. The assessor must:

1. verify every source artifact, receipt, policy and evidence snapshot before assessment;
2. cover every candidate exactly once in deterministic source order;
3. preserve candidate, impact, graph, evidence, assumption, conflict, gap and unknown lineage;
4. classify availability, data, security, performance, operational-complexity, reversibility and
   evidence-uncertainty risk dimensions using policy tables rather than model judgement;
5. prevent any unknown, stale, conflicting or incomplete evidence from lowering a risk dimension
   or overall risk below the policy floor;
6. produce bounded work-duration and expected/worst-credible interruption ranges with basis,
   confidence and evidence lineage, never point estimates or guarantees;
7. distinguish no-action, read-only diagnostic, escalation and change-planning candidates without
   treating conceptual candidate text as an executable command;
8. establish a recovery classification, rollback feasibility state, point-of-no-return status,
   trigger conditions, bounded recovery duration, verification requirements and unresolved gaps;
9. mark unsupported conclusions as unknown or blocked and retain the most conservative credible
   consequence;
10. compute report, evidence-binding, coverage, risk, duration, interruption, recovery, unknown,
    safety, cleanup and receipt digests within policy budgets;
11. erase plaintext working buffers and close protected artifact channels in every outcome; and
12. return the protected report plus a signed minimized receipt to the application boundary.

The first implementation uses a deterministic no-network, no-model development evidence snapshot
and trusted synthetic assessor. Production fails closed without an approved signed policy,
immutable operational-evidence provider, protected upstream sources, assessor and attestor, and an
encrypted completion-report vault.

### Protected Completion Contract

Each protected candidate completion entry contains:

- exact candidate and impact-entry IDs and digests;
- all required typed risk dimensions, levels, rationales and evidence references;
- conservative overall risk, policy floor, confidence, assumptions, conflicts and unknowns;
- bounded work-duration range, basis, confidence and applicability;
- expected and worst-credible interruption modes and ranges;
- possibly affected service IDs inherited from the verified impact report;
- recovery strategy classification, rollback feasibility, point of no return, trigger conditions,
  bounded recovery duration, data implications, verification criteria and gaps;
- evidence-snapshot lineage and per-section completeness indicators; and
- explicit no-preference, no-approval, no-workflow and no-operation state.

Completion means the governed assessment process covered every required field. An `unknown` or
`blocked` typed result is a valid conservative completion when policy permits it; it does not mean
the underlying operational fact is known. No candidate may be omitted because its evidence is
unfavorable or incomplete.

### Minimized Record And Disclosure

Full candidate completion entries, per-candidate risk dimensions, service IDs, duration and
interruption details, recovery instructions, evidence references, assumptions, conflicts,
unknown text and assessor receipt remain only in a tenant-isolated protected vault. Ordinary
in-memory or PostgreSQL records contain only immutable IDs, upstream lineage, salted subject and
browser bindings, policy, assessor and evidence-snapshot identities, bounded aggregate counts,
conservative aggregate labels and ranges, canonical digests, timestamps, expiry, purpose, state
and explicit no-authority flags.

Ordinary API responses and UI may disclose only:

- completion, impact-analysis, candidate-set and upstream lineage IDs;
- completion-policy, assessor and evidence-snapshot IDs, versions and canonical digests;
- evidence generation time, freshness, completeness and coverage labels;
- candidate count, risk-level counts, interruption-possible count, recovery-feasible/unknown/blocked
  counts, gap and unknown counts;
- the conservative maximum risk label and aggregate bounded work, interruption and recovery
  ranges, without candidate-to-value mapping;
- `impact_complete=true`, `risk_completed=true`, `duration_established=true`,
  `interruption_established=true` and `recovery_completed=true`, while outage confirmation,
  recommendation completion, preference, presentation, readiness, approval, workflow, execution,
  deployment and infrastructure mutation remain false; and
- a fixed notice that estimates are evidence-bounded decision-support outputs, not guarantees or
  authority to act.

Audit, logs, errors, traces, metrics, events, browser storage, vector stores, retrieval indexes and
ordinary graph records contain no protected candidate content or candidate-specific assessment.

### Existing Recommendation Domain Boundary

Completion does not create or update
`atlas.modules.recommendations.domain.RecommendationArtifact`. It does not choose a preferred
candidate or expose candidate content. A later deterministic adjudication service must compare the
exact protected candidates using this completion report, policy constraints and preserved evidence
before presentation or promotion into the existing recommendation domain can be considered.

### Failure And Audit

Intent audit precedes claim creation; claim audit follows a successful claim; protected source and
operational-evidence read audits succeed before assessment; completion audit succeeds before
metadata persistence; and every replay has a separate read audit. Audit contains accountable
subject, policies, source IDs, evidence-snapshot ID and outcome, but no protected content,
candidate-specific values, evidence references or vault handles.

Authorization denial occurs before protected content rehydration. Source, policy, evidence,
assessor, audit, persistence, cleanup, receipt, vault, integrity or replay uncertainty fails closed
and returns no partial content or misleading complete-looking metadata.

## Consequences

### Positive

- Risk and recovery claims become reproducible, policy-bound and evidence-aware.
- Conservative unknown handling prevents missing topology or runtime evidence from appearing safe.
- Duration and interruption remain ranges with provenance instead of unsupported promises.
- Candidate-specific operational detail stays protected until governed presentation.

### Costs

- Evidence snapshots require additional source adapters, retention and cryptographic custody.
- Deterministic policy tables require versioning and validation across vendor and capability types.
- Completion still cannot answer which candidate should be preferred.

## Rejected Alternatives

### Let The LLM Estimate Risk And Downtime

Rejected because unbounded model judgement is not reproducible evidence and can fabricate
operational certainty.

### Let The Caller Supply Missing Recovery Data

Rejected because caller-shaped risk and recovery inputs could lower safeguards or bypass evidence
governance.

### Expose Candidate-Level Completion In This UI Stage

Rejected because protected candidate content has not passed adjudication and accountable
presentation controls.

### Treat Completion As Approval Readiness

Rejected because evidence completion does not select an option, accept residual risk or create an
accountable decision.

## Follow-Up

Later independent contracts cover deterministic recommendation adjudication; protected
recommendation presentation; promotion into the existing recommendation domain; human feedback;
suspension, supersession, retention and controlled export; workflow planning; approval; and any
human-approved automation.
