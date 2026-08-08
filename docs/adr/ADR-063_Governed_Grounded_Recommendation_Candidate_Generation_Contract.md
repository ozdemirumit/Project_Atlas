# ADR-063: Governed Grounded Recommendation Candidate Generation Contract

- Status: Accepted
- Date: 2026-08-08
- Owners: Product Owner, Solution Architecture, Security Architecture, AI Platform Engineering,
  Decision Intelligence, Knowledge Retrieval Engineering, Identity Governance, Data Governance
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-027, ATLAS-030,
  ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-040, ATLAS-041, ATLAS-042, ATLAS-043,
  ATLAS-044, ATLAS-046, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-052, ATLAS-053, ATLAS-054,
  ATLAS-055, ATLAS-056, ADR-009 through ADR-062

## Context

ADR-062 permits one exact eligible protected answer to be shown as bounded decision support. The
answer preserves its citations and unknowns but is explicitly not a root cause, service-impact
claim, operational recommendation, approval, workflow instruction, or authority to act.

Atlas also has an established recommendation domain from the storage decision-support vertical
slice. Its `RecommendationArtifact` is the authoritative durable recommendation contract and is
consumed by approval and reporting. The protected AI path must enrich that domain rather than
create a parallel recommendation system or silently promote conversational prose into an
operational recommendation.

A separate generation boundary is therefore required. It must derive a bounded set of provisional
candidate options from the exact governed answer, its upstream evidence, and signed policy while
keeping candidate content protected until independent impact, policy, completeness, and review
stages have run.

## Decision

Atlas will implement one governed grounded-recommendation candidate-generation service. A
human-initiated `POST` may create one immutable candidate-set record for one exact eligible answer
presentation. The service rehydrates the exact presentation, adjudication, model draft, context,
retrieval package, and evidence only after current authorization and then asks one trusted bounded
generator to produce a closed protected candidate set.

The result is an upstream candidate artifact, not a `RecommendationArtifact`. It cannot be shown
as recommended advice, preferred, ready for review, approved for planning, executable, or safe.
Later independent services must add service-impact analysis, duration and interruption estimates,
recovery evidence, deterministic policy evaluation, completeness adjudication, presentation, and
human review before promotion into the existing recommendation domain.

This stage does not invoke a connector, select a credential, schedule work, create a workflow,
request approval, create an ITSM change, call a target, execute a tool, deploy software, or mutate
infrastructure.

### Source Eligibility

Generation proceeds only when:

- the exact answer-presentation record exists, completed successfully, is integrity-valid and
  unexpired, and remains bound to the same consumer, browser, purpose, policy, adjudication,
  invocation, context, retrieval, publication, source, classification, citation, unknown, safety,
  destination, and protected-artifact lineage;
- the source adjudication outcome is still `adjudication-outcome.eligible`, every upstream policy
  and access decision remains current, and the exact answer can still be reproduced by the trusted
  presenter without content drift;
- the exact protected report, draft, context package, retrieval package, and evidence package can
  be rehydrated through their existing trusted boundaries after current permission checks;
- a current signed generation policy resolves allowed candidate categories, capability ceiling,
  required schemas, trusted generator and attestor, item and byte limits, prohibited outputs,
  required candidate diversity, retention, cleanup, and downstream completeness requirements; and
- no conflicting claim exists for the presentation's unique generation boundary or idempotency
  key.

Expired, rejected, superseded, suspended, cross-tenant, caller-shaped, policy-stale,
artifact-missing, source-divergent, citation-incomplete, or integrity-uncertain state fails before
candidate content is read or generated.

### Caller Contract

The caller may provide only:

- exact presentation ID and canonical digest;
- exact signed candidate-generation-policy ID and digest;
- the unchanged purpose;
- acknowledgements that candidates are incomplete decision-support inputs, service impact and
  recovery remain unverified, and no recommendation or operational authority is created; and
- idempotency and correlation identifiers.

The caller cannot provide identity, tenant, role, answer text, prompt, draft, evidence, citation,
unknown, target override, option title, candidate category, candidate count, preference, score,
risk, impact, duration, interruption, recovery, executable step, capability, connector, credential,
command, model, endpoint, secret, policy outcome, workflow, approval, deployment, or mutation
fields.

The unchanged source purpose is the initial decision question. A later recommendation-request
contract may add accountable audience, horizon, constraints, and target selection only through a
separate validated and attributable boundary.

### Identity And Access

The actor must be the same current enterprise human consumer that owns the protected invocation,
adjudication, and presentation, in the exact tenant and environment, with recent hardware-backed
MFA, browser binding, CSRF, dedicated C1 generation and lineage-read permissions, and current
source and classification access.

Service, shared, AI, break-glass, cross-tenant, policy-signer, model gateway, endpoint owner or
evaluator, context assembler, adjudicator, presenter, candidate generator, generator attestor, and
downstream recommendation reviewer identities cannot act as the human caller. Generation authority
is the intersection of current human access and every upstream authority and cannot widen access
or retention.

### Atomic Claim And Replay

Required intent audit succeeds before an immutable claim is created with a unique constraint on
presentation ID. Claim creation is the point of no return. Exact idempotent reuse is permitted only
when subject, browser, request, presentation, purpose, policy, and completed candidate-set evidence
match.

Failure or uncertainty after claim creation remains claimed and returns no partial content. The
service never automatically retries generation, creates a second set, extends retention, or
silently falls back to a different generator, policy, source, or model.

An audited metadata `GET` may return the same minimized record while all access, source, policy,
retention, and integrity proofs remain current. Candidate content is not returned by this stage.

### Trusted Candidate Generator Boundary

The application sends only trusted upstream artifacts and lineage, signed policy controls,
expected digests, governance labels, subject and browser binding digests, and an opaque candidate
set ID. The trusted generator must:

1. resolve only the exact protected answer, adjudication report, draft, context, and evidence bound
   to the presentation;
2. verify all source content, citation, unknown, policy, authorization, retention, protected-vault,
   schema, and canonical digests independently;
3. preserve every material source unknown and conflict and reject unsupported factual, causal,
   impact, success, duration, or safety claims;
4. produce a closed bounded set containing at least one read-only diagnostic candidate, one
   escalation candidate, and one defer or no-action candidate when policy and evidence permit;
5. mark restoration or remediation planning candidates blocked when impact, rollback, maintenance
   window, redundancy, recovery, or policy evidence is incomplete;
6. emit only conceptual non-executable steps and policy-approved C0 or C1 capability references;
7. assign no preferred option, readiness state, approval state, executable command, free-form
   shell, credential, secret, endpoint, connector session, or target operation;
8. compute candidate-content, source-binding, citation-set, unknown-set, safety, cleanup, and receipt
   digests and enforce all item and byte budgets;
9. erase plaintext working buffers and close protected artifact channels in every outcome; and
10. return the protected candidate set plus a signed minimized receipt to the application boundary.

The first implementation uses a deterministic no-network, no-model synthetic generator over
approved fixtures. Production fails closed without an approved policy registry, trusted generator
and attestor, protected source access, and encrypted candidate vault. A later model-assisted
generator must reuse the governed model gateway and independent adjudication boundaries rather than
bypass them.

### Protected Candidate Contract

Each candidate contains only the fields required for later enrichment:

- opaque candidate ID, version, category, and protected title and intended outcome;
- conceptual non-executable steps with optional approved C0 or C1 capability references;
- exact supporting and contradicting citation references;
- explicit assumptions, unknowns, source conflicts, applicability limits, and evidence gaps;
- provisional confidence category with evidence-based rationale;
- explicit flags that impact, duration, interruption, recovery, policy, readiness, preference,
  approval, and execution have not been established; and
- source, policy, generator, schema, and canonical digests.

Candidate categories are bounded to diagnostic investigation, escalation, defer or no action,
restoration planning, and remediation planning. Restoration and remediation candidates remain
blocked planning inputs until downstream impact and recovery contracts succeed.

### Existing Recommendation Domain Boundary

The candidate set is not stored in or returned as
`atlas.modules.recommendations.domain.RecommendationArtifact`. It cannot be consumed by approval,
reporting, workflow, ITSM, or execution interfaces.

A later promotion service may create a versioned existing-domain recommendation only after exact
candidate lineage, service impact, risk, duration, interruption, recovery, policy, completeness,
human accountability, and presentation requirements are satisfied. Promotion creates a new
auditable domain transition; it never edits or reinterprets the candidate set in place.

### Persistence And Disclosure

Full candidate content and the generation receipt remain only in a tenant-isolated protected vault.
Ordinary in-memory or PostgreSQL records contain only immutable claim and candidate-set IDs,
upstream lineage, salted subject and browser bindings, policy and generator identities, category
and bounded item counts, capability ceiling, content and source digests, timestamps, expiry,
purpose, state, and explicit no-authority flags.

Ordinary API responses, audit, logs, errors, traces, metrics, events, browser storage, vector stores,
retrieval indexes, and graph records contain no candidate title, intended outcome, conceptual step,
assumption, unknown text, confidence rationale, citation content, source content, protected handle,
credential, secret, prompt, or model output.

Success sets only `recommendation_candidates_generated=true`. It leaves
`service_impact_analyzed`, `recommendation_complete`, `recommendation_presented`,
`recommendation_ready_for_review`, `recommendation_approved`, `workflow_created`,
`execution_authorized`, `deployment_authorized`, and `infrastructure_mutated` false.

### Failure And Audit

Intent audit precedes claim creation; claim audit follows a successful claim; protected-source read
audit succeeds before candidate generation; generation completion audit succeeds before metadata
persistence; and every metadata replay has a separate read audit. Audit identifies the accountable
subject, policy, source record, and outcome but never contains protected content or handles.

Authorization denial occurs before protected source rehydration. Generator, audit, persistence,
cleanup, receipt, vault, integrity, or replay uncertainty fails closed and returns no partial
candidate content. A claimed uncertain outcome requires explicit governed investigation; it is not
automatically regenerated.

## Consequences

### Positive

- Conversational answer text cannot silently become operational advice.
- AI-derived candidate options remain tied to exact current evidence, citations, unknowns, and
  accountable human intent.
- Existing recommendation, approval, report, and workflow domains retain one authoritative
  contract instead of gaining a competing AI recommendation model.
- Impact, recovery, policy, preference, and readiness cannot be inferred from fluent candidate
  prose.

### Costs

- A candidate set is intentionally not useful as a final recommendation until later stages finish.
- Production requires a protected candidate vault and independently attested generator boundary.
- Recommendation promotion requires explicit mapping and validation against the existing domain.

## Rejected Alternatives

### Treat The Presented Answer As A Recommendation

Rejected because answer eligibility proves bounded content conformance, not operational
correctness, impact, recovery, policy, or readiness.

### Generate A Second Recommendation Domain

Rejected because approval, reporting, audit, and operators would face incompatible sources of
truth.

### Return Candidate Content Directly To The Browser

Rejected because incomplete candidates could be mistaken for safe or preferred advice before
impact and policy validation.

### Let The Caller Select Options Or Capabilities

Rejected because caller-shaped options bypass evidence grounding, policy budgets, and trusted
generation controls.

### Invoke A Model Directly From The Recommendation Service

Rejected because it would bypass the model gateway, endpoint policy, protected output, and
independent adjudication contracts.

## Follow-Up

Later independent contracts cover candidate service-impact enrichment, risk and recovery
completion, deterministic recommendation adjudication, protected recommendation presentation,
promotion into the existing recommendation domain, human feedback, suspension, supersession,
retention, controlled export, workflow planning, approval, and any human-approved automation.
