# ADR-064: Governed Protected Candidate Service-Impact Enrichment Contract

- Status: Accepted
- Date: 2026-08-08
- Owners: Product Owner, Solution Architecture, Security Architecture, AI Platform Engineering,
  Decision Intelligence, Infrastructure Graph Engineering, Identity Governance, Data Governance
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-026, ATLAS-027,
  ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-040, ATLAS-041, ATLAS-042,
  ATLAS-043, ATLAS-044, ATLAS-046, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-052, ATLAS-053,
  ATLAS-054, ATLAS-055, ATLAS-056, ADR-009 through ADR-063

## Context

ADR-063 creates one immutable protected set of grounded recommendation candidates. The set is an
incomplete decision-support input. Candidate content is not disclosed, no candidate is preferred,
and service impact, interruption, duration, recovery, policy readiness, approval, and operational
authority remain unestablished.

Atlas already has a bounded infrastructure graph that can return authorized dependency paths from
one storage system to technical and business services. That graph is an evidence model: it carries
snapshot identity, freshness, completeness, provenance, classification, known gaps, and unknowns.
Graph reachability is not proof of an outage or proof that a proposed action would interrupt a
service.

A separate enrichment boundary is required to bind every candidate in one exact protected set to
one exact authorized graph snapshot. The boundary must preserve protected candidate content while
recording enough minimized evidence for later risk, recovery, deterministic adjudication, and
presentation stages.

## Decision

Atlas will implement one governed protected candidate service-impact enrichment service. A
human-initiated `POST` may create one immutable impact-analysis record for one exact eligible
candidate set. The service first authorizes against ordinary minimized metadata, then rehydrates
the exact protected candidate set through the existing trusted boundary and evaluates each
candidate against one policy-selected immutable graph snapshot.

The result is protected graph context attached to provisional candidates. It is not a confirmed
change impact, outage statement, risk score, duration estimate, recovery plan, recommendation,
preference, approval, workflow, execution plan, or authority to act.

### Source Eligibility

Enrichment proceeds only when:

- the exact candidate-set record exists, completed successfully, remains unexpired and
  integrity-valid, and is still bound to the same consumer, browser, tenant, environment, purpose,
  generation policy, presentation, answer, adjudication, invocation, context, retrieval, source,
  citation, unknown, safety, and protected-vault lineage;
- candidate generation remains the only completed downstream state and no impact analysis,
  recommendation completion, presentation, approval, workflow, execution, deployment, or
  infrastructure mutation has been recorded;
- current authorization can still rehydrate and independently verify the exact protected
  candidate set and generation receipt without content drift;
- a current signed impact policy resolves the trusted analyzer, graph snapshot source, starting
  entity, maximum depth, allowed relationship and service classes, schemas, limits, retention,
  cleanup, disclosure profile, and required unknown handling; and
- no conflicting claim exists for the candidate set's unique impact-analysis boundary or
  idempotency key.

Expired, cross-tenant, caller-shaped, policy-stale, graph-unavailable, graph-stale beyond policy,
artifact-missing, source-divergent, access-denied, classification-incompatible, partial-looking,
or integrity-uncertain state fails before protected candidate content is read or analyzed.

### Caller Contract

The caller may provide only:

- exact candidate-set ID and canonical digest;
- exact signed impact-policy ID and digest;
- the unchanged purpose;
- acknowledgements that graph reachability is not outage evidence, impact remains provisional,
  and no recommendation or operational authority is created; and
- idempotency and correlation identifiers.

The caller cannot provide identity, tenant, role, candidate content, candidate selection, target
entity, graph snapshot, relationship type, traversal depth, service list, impact classification,
risk, duration, interruption, redundancy, recovery, preference, score, capability, connector,
credential, command, model, endpoint, workflow, approval, deployment, or mutation fields.

### Identity And Access

The actor must be the same current enterprise human consumer that owns the protected candidate
lineage, in the exact tenant and environment, with recent hardware-backed MFA, browser binding,
CSRF, dedicated C1 impact create and read permissions, graph-read authority, and current source and
classification access.

Service, shared, AI, break-glass, cross-tenant, policy-signer, graph-source, analyzer, candidate
generator, attestor, recommendation reviewer, workflow, and execution identities cannot act as the
human caller. Derived impact inherits the most restrictive classification and access constraints
of the candidate set and traversed graph evidence.

### Atomic Claim And Replay

Required intent audit succeeds before an immutable claim is created with a unique constraint on
candidate-set ID. Claim creation is the point of no return. Exact idempotent reuse is permitted only
when subject, browser, request, candidate set, purpose, policy, graph snapshot, protected report,
and completed record evidence match.

Failure or uncertainty after claim creation remains claimed and returns no partial result. The
service never automatically retries analysis, changes the graph snapshot, creates a second impact
record, extends retention, or silently falls back to another analyzer, policy, target, or graph.

An audited metadata `GET` may return the same minimized record while all access, source, policy,
retention, graph, protected-vault, and integrity proofs remain current. Protected candidate-to-path
content is not returned by this stage.

### Trusted Analyzer Boundary

The application sends only the exact protected candidate set and receipt, signed policy controls,
expected lineage and authorization digests, one policy-selected graph snapshot, and an opaque
analysis ID. The trusted analyzer must:

1. verify the exact candidate set, generation receipt, source lineage, policy, and graph snapshot;
2. reject any candidate or graph content not covered by current authorization and classification;
3. use only the policy-selected starting entity and bounded graph traversal;
4. preserve graph freshness, completeness, evidence paths, known gaps, unknowns, and hidden-node
   non-disclosure;
5. produce one protected impact entry for every candidate, including candidates whose conceptual
   action does not support an impact conclusion;
6. label directly connected and transitively reachable entities only as modeled dependencies;
7. identify reachable technical and business services without claiming current unavailability;
8. state that redundancy, failover, runtime health, duration, interruption, recovery, and business
   consequence remain unknown unless separately established by later governed contracts;
9. compute report, graph-binding, coverage, unknown, safety, cleanup, and receipt digests within
   policy budgets;
10. erase plaintext working buffers and close protected artifact channels in every outcome; and
11. return the protected report plus a signed minimized receipt to the application boundary.

The first implementation uses the deterministic no-network, no-model development graph and a
trusted synthetic analyzer. Production fails closed without an approved signed policy, immutable
graph snapshot provider, protected candidate source, analyzer and attestor, and encrypted impact
report vault.

### Protected Impact Contract

Each protected candidate-impact entry contains:

- exact candidate ID and digest;
- policy-selected start entity and bounded traversal depth;
- direct and possible modeled entity identifiers;
- reachable technical and business service identifiers;
- exact dependency paths and authorized graph evidence references;
- snapshot freshness, completeness, graph maturity, known gaps, and unknowns;
- explicit statements that outage, interruption, duration, risk, and recovery are unconfirmed;
- no preferred, ready, approved, executable, deployable, or mutation state; and
- source, policy, analyzer, graph, schema, and canonical digests.

The report covers every candidate in deterministic source order. It does not rewrite candidate
content, infer candidate preference, rank candidates, or transform graph reachability into a
causal or outage assertion.

### Minimized Record And Disclosure

Full candidate-impact entries, paths, entity identifiers, service identifiers, evidence
references, unknown text, and the analyzer receipt remain only in a tenant-isolated protected
vault. Ordinary in-memory or PostgreSQL records contain only immutable IDs, upstream lineage,
salted subject and browser bindings, policy and analyzer identities, graph snapshot identity and
digest, bounded counts, freshness and completeness labels, coverage and safety digests,
timestamps, expiry, purpose, state, and explicit no-authority flags.

Ordinary API responses and UI may disclose only:

- analysis, candidate-set, and upstream lineage IDs;
- impact-policy and analyzer IDs and canonical digests;
- graph snapshot ID, digest, generation time, freshness, completeness, and maturity label;
- candidate, path, modeled entity, technical-service, business-service, gap, and unknown counts;
- `service_impact_analyzed=true` and explicit false flags for outage, interruption, duration, risk,
  recovery, recommendation completion, presentation, readiness, approval, workflow, execution,
  deployment, and infrastructure mutation; and
- a fixed safety notice that dependencies show possible reachability, not an outage or authority.

Audit, logs, errors, traces, metrics, events, browser storage, vector stores, retrieval indexes, and
ordinary graph records contain no protected candidate content or protected impact details.

### Existing Recommendation Domain Boundary

Impact enrichment does not create or update
`atlas.modules.recommendations.domain.RecommendationArtifact`. Approval, reporting, workflow,
ITSM, and execution interfaces cannot consume the protected impact report. Later services must
complete risk, duration, interruption, recovery, policy, completeness, preference, accountable
presentation, and human review before a new auditable promotion into the existing recommendation
domain can occur.

### Failure And Audit

Intent audit precedes claim creation; claim audit follows a successful claim; protected candidate
and graph-source read audits succeed before analysis; analysis completion audit succeeds before
metadata persistence; and every metadata replay has a separate read audit. Audit identifies the
accountable subject, policies, source IDs, graph snapshot, and outcome but never contains protected
content, paths, entity or service IDs, evidence references, or vault handles.

Authorization denial occurs before protected content rehydration. Graph-source, analyzer, audit,
persistence, cleanup, receipt, vault, integrity, or replay uncertainty fails closed and returns no
partial content or misleading complete-looking metadata.

## Consequences

### Positive

- Every provisional candidate receives the same exact time-aware graph context.
- Graph evidence can support later impact reasoning without exposing incomplete candidate content.
- Missing topology and stale mappings remain explicit instead of becoming false certainty.
- Recommendation, risk, recovery, approval, and execution domains retain independent boundaries.

### Costs

- Protected candidate-to-path reports require a dedicated encrypted vault and replay validation.
- Snapshot immutability and exact graph provenance add storage and operational requirements.
- The result remains intentionally incomplete until risk and recovery stages succeed.

## Rejected Alternatives

### Reuse The Public Storage Impact API Directly

Rejected because caller-selected targets and browser-visible paths would bypass candidate lineage,
policy selection, protected disclosure, and atomic analysis controls.

### Treat Reachable Services As Impacted Services

Rejected because graph reachability alone does not establish runtime state, redundancy behavior,
outage, interruption, duration, or business consequence.

### Store Impact Details In Ordinary Recommendation Tables

Rejected because incomplete protected candidates must not enter the authoritative recommendation,
approval, reporting, workflow, or execution domains.

### Let The Model Infer Missing Topology

Rejected because ungoverned inferred edges would make impact claims non-reproducible and could
leak or fabricate infrastructure relationships.

## Follow-Up

Later independent contracts cover risk, duration, interruption and recovery completion;
deterministic recommendation adjudication; protected recommendation presentation; promotion into
the existing recommendation domain; human feedback; suspension, supersession, retention and
controlled export; workflow planning; approval; and any human-approved automation.
