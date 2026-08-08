# ADR-066: Governed Deterministic Protected Recommendation Adjudication Contract

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-08 |
| Owners | Product Owner, Architecture Owner, AI Architecture, Security Architecture |
| Decision Scope | Protected recommendation comparison and preference adjudication |
| Related Documents | ATLAS-003, ATLAS-010, ATLAS-014, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-026, ATLAS-027, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-041, ATLAS-042, ATLAS-043, ATLAS-044, ATLAS-046, ATLAS-047, ATLAS-050, ATLAS-053, ATLAS-056, ADR-063, ADR-064, ADR-065 |

## Context

ADR-065 completes risk, duration, interruption, and recovery analysis for every exact protected
candidate. It deliberately does not compare candidates, establish a preference, present candidate
content, create a recommendation artifact, declare review readiness, or grant operational
authority.

Project Atlas now needs an independent deterministic boundary that applies non-overridable policy,
compares every candidate across explicit dimensions, preserves ties and unsupported outcomes, and
records whether a supportable preference exists. An LLM must not rank candidates, policy cannot be
replaced by one opaque score, and the caller must not shape candidate values or select an outcome.

Adjudication remains an internal protected stage. Candidate identity, content, eligibility,
exclusions, dimension values, preference rationale, and tradeoffs have not yet passed the separate
accountable presentation boundary and must not reach the ordinary API or browser.

## Decision

Atlas will add one governed deterministic protected recommendation adjudication service. The
service accepts only one exact completed protected risk-recovery result and one exact signed
adjudication policy. It rehydrates the complete protected candidate, impact, completion, evidence,
and receipt lineage inside the trusted boundary and runs a deterministic no-network, no-model
adjudicator.

Success establishes only that recommendation comparison and preference adjudication are complete.
It may internally identify exactly one preferred candidate, preserve a policy-defined tie, or
record that no candidate is supportable. It does not disclose candidate-level output, present a
recommendation, create an existing-domain `RecommendationArtifact`, declare readiness, approve a
choice, create a workflow, authorize execution, deploy anything, or mutate infrastructure.

### Entry Contract

Only the same eligible enterprise human consumer may enter adjudication. The consumer must use a
current browser-bound session with hardware-backed MFA and current C1 create permission in the
same organization and environment.

The source must be one exact, completed, unexpired, integrity-valid risk-recovery result. The
service rehydrates and verifies the unchanged:

- completion record, protected completion receipt and report;
- impact analysis, protected impact report and graph-snapshot lineage;
- candidate set, protected answer, adjudication, invocation, context, retrieval, source,
  classification, citation, unknown and safety lineage;
- operational-evidence snapshot, completion policy and retention window;
- consumer, browser, tenant, environment and purpose bindings; and
- all canonical digests and protected-vault artifacts.

The caller supplies only:

- exact completion ID and canonical digest;
- signed adjudication-policy ID and digest;
- unchanged purpose;
- acknowledgements that deterministic preference is not approval, that ties or no-support outcomes
  are valid, and that adjudication grants no presentation, workflow or operational authority;
- idempotency key and correlation context.

Candidate IDs, categories, titles, content, evidence, comparison values, criteria weights, scores,
eligibility, exclusions, preference, target, capability, operation, workflow, approval, deployment,
and mutation controls are forbidden request fields.

### Adjudication Policy

The immutable signed policy defines:

- required source schemas and completed source state;
- required deterministic adjudicator and attestor identities;
- required comparison dimensions and strict precedence order;
- non-overridable eligibility and exclusion rules;
- allowed candidate categories and capability ceiling;
- conservative risk and unknown handling;
- tie and no-support behavior;
- maximum candidates, dimensions, exclusions, unknowns, output bytes and retention;
- protected report and receipt schemas;
- browser-binding, safety-profile and preference-profile digests; and
- issue, expiry, organization and environment bindings.

The initial comparison dimensions are:

1. policy eligibility;
2. evidence applicability and completeness;
3. risk and uncertainty;
4. capability class;
5. interruption;
6. recovery feasibility and reversibility;
7. work duration;
8. expected evidence value or outcome fitness; and
9. category precedence for the exact decision horizon.

The engine keeps each dimension separate. It may derive a lexicographic policy key but must not
replace visible tradeoffs with one unexplained aggregate score.

### Deterministic Adjudication

The trusted adjudicator receives one immutable instruction plus the exact protected candidate set,
impact report, risk-recovery report, and operational-evidence snapshot. It must:

- cover every candidate exactly once and reject duplicates, omissions or unexpected candidates;
- verify all protected inputs and canonical digests independently;
- evaluate non-overridable policy before preference;
- retain unknown, stale, conflicting or incomplete evidence conservatively;
- produce typed comparison values, eligibility, exclusion reasons and policy outcome per candidate;
- preserve ties where policy cannot justify one candidate;
- produce a no-support outcome when all candidates are excluded or evidence is inadequate;
- select at most one preferred candidate in the first implementation;
- mark every non-preferred eligible candidate as an alternative without declaring it unsafe;
- use no network, model, connector, shell, workflow or infrastructure operation; and
- emit a signed receipt proving complete coverage, deterministic policy application, no caller
  preference, no model use, protected cleanup and no operational authority.

The deterministic development policy prefers an evidence-gathering read-only candidate when the
current warning remains unresolved and additional current evidence has material value. Escalation
and defer/no-action remain alternatives when they are eligible. This fixture rule demonstrates
the contract only and is not a production recommendation policy.

### Protected Result

The protected report contains, for every candidate:

- candidate and upstream protected digests;
- policy eligibility and exclusion reasons;
- ordered comparison dimensions and normalized typed values;
- risk, interruption, recovery, duration, evidence and capability summaries;
- preference state: preferred, alternative or ineligible;
- preference or non-preference rationale;
- ties, conflicts, unknowns and residual limitations; and
- canonical digest and expiry.

Candidate-specific output and the adjudicator receipt remain only in a tenant-isolated protected
vault. Ordinary persistence contains immutable IDs, upstream lineage, salted subject and browser
bindings, policy and adjudicator identities, aggregate counts, outcome labels, canonical digests,
timestamps, purpose, state and fixed no-authority flags.

### Minimized Disclosure

Ordinary API responses and UI may disclose only:

- adjudication, completion, impact, candidate-set and upstream lineage IDs;
- adjudication-policy and adjudicator IDs, versions and canonical digests;
- candidate, comparison-dimension, eligible, excluded, preferred and alternative counts;
- aggregate tie and no-support booleans;
- aggregate risk ceiling, interruption-possible, recovery-feasible, gap and unknown counts inherited
  from the verified completion;
- comparison, eligibility, exclusion, preference and safety digests without candidate mapping;
- timestamps, expiry, purpose and the completed instance state;
- `recommendation_complete=true` while presentation, review readiness, approval, workflow,
  execution, deployment and infrastructure mutation remain false; and
- a fixed notice that deterministic preference is protected decision support, not approval or
  authority to act.

The API and browser never receive a preferred candidate ID, category, title, option value,
exclusion reason, evidence reference, comparison key or preference rationale at this stage.

### Existing Recommendation Domain Boundary

Adjudication does not create or update
`atlas.modules.recommendations.domain.RecommendationArtifact`. The protected result first requires
an independent accountable presentation contract. A later promotion contract may map one exact
presented protected adjudication into the existing recommendation domain without bypassing its
schema, evidence, policy, human review and audit rules.

### Claim, Replay And Failure

One immutable claim is unique per completion. Exact idempotent replay verifies current access,
policy, source retention, protected vault content and every digest, then returns the same minimized
result without rerunning comparison against newer policy or evidence.

Authorization denial occurs before protected rehydration. Source, policy, adjudicator, audit,
receipt, vault, persistence, cleanup, integrity or replay uncertainty fails closed. No partial
comparison, preferred candidate, complete-looking metadata or operational implication is returned.

Intent, claim, completion and read audits contain accountable subject, policy, source IDs and
outcome only. Audit, logs, errors, traces, metrics, events, browser storage, vector stores,
retrieval indexes and ordinary graph records contain no candidate-level adjudication content.

### Production Boundary

Production has no synthetic policy, source, adjudicator, attestor or protected-vault fallback.
Missing trusted configuration makes adjudication unavailable. The development adapter is
deterministic, synthetic, no-network and no-model and performs no infrastructure operation.

## Consequences

### Positive

- Preference becomes reproducible, policy-bound and independent of LLM wording.
- Ties and unsupported outcomes remain first-class instead of forcing false certainty.
- Candidate tradeoffs stay protected until accountable presentation.
- Existing recommendation, approval, workflow and execution boundaries remain intact.

### Costs

- Policy precedence and tie behavior require careful versioning and domain review.
- Protected report custody must survive replay without exposing preferred identity.
- Adjudication alone still cannot present a recommendation to a human.

## Rejected Alternatives

### Ask The LLM To Rank Candidates

Rejected because model preference is not deterministic policy evidence and can vary across runs.

### Let The Caller Supply Weights Or Select A Candidate

Rejected because caller-shaped comparison can bypass non-overridable policy and auditability.

### Publish The Preferred Candidate Immediately

Rejected because candidate-level content has not passed the independent accountable presentation
boundary.

### Create RecommendationArtifact Directly

Rejected because it would bypass protected presentation, promotion and existing-domain validation.

## Follow-Up

Later independent contracts cover protected recommendation presentation; promotion into the
existing recommendation domain; human feedback; suspension, supersession, retention and controlled
export; workflow planning; approval; and any human-approved automation.
