# ADR-061: Governed Protected Model Draft Adjudication Contract

- Status: Accepted
- Date: 2026-08-07
- Owners: Product Owner, Solution Architecture, Security Architecture, AI Platform Engineering,
  Knowledge Retrieval Engineering, Identity Governance, Data Governance
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-025, ATLAS-027, ATLAS-030, ATLAS-031,
  ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-040, ATLAS-041, ATLAS-046, ATLAS-047, ATLAS-050,
  ATLAS-051, ATLAS-052, ATLAS-053, ATLAS-054, ATLAS-055, ATLAS-056, ADR-009 through ADR-060

## Context

ADR-060 permits one approved local model to process an exact protected context and stores one
structured, citation-bearing response draft in a protected result vault. The draft remains
untrusted model output and is not returned to the browser. Model-invocation validation proves
schema, identity, citation membership, usage, finish reason, and basic safety, but it does not
establish that every material statement is supported, that unknowns and conflicts are preserved,
or that the draft is eligible for later human presentation.

Atlas needs an independent, non-model adjudication step before any response content can enter a
presentation boundary.

## Decision

Atlas will implement one dedicated governed protected model-draft adjudication service. One audited
`POST` binds the same accountable invocation consumer, exact completed protected invocation, signed
adjudication policy, and current authorization state to a trusted deterministic adjudicator. An
audited `GET` returns only a minimized adjudication manifest after full current-policy
revalidation. Invocation context, evidence, and draft content remain inside protected boundaries.

This step does not invoke an LLM, rewrite the draft, publish an answer, select a tool, call a
connector, update a graph, start a workflow, authorize an operation, approve deployment, or mutate
infrastructure.

### Eligibility

Adjudication proceeds only when:

- the exact invocation exists, completed successfully, is integrity-valid and unexpired, and is
  bound to unchanged context, retrieval, publication, source, access, classification, purpose,
  context policy, invocation policy, endpoint evaluation, model, schema, citation, safety, budget,
  destination, and protected-artifact lineage;
- the exact protected draft and context package can be rehydrated through their existing trusted
  boundaries after current consumer, tenant, MFA, browser, permission, lifecycle, retention, and
  integrity checks;
- a current signed adjudication policy resolves the approved deterministic adjudicator, validation
  profile, required schemas, classification ceiling, evidence-coverage rules, unknown/conflict
  rules, prohibited-output rules, and protected adjudication vault; and
- no conflicting request exists for the same idempotency key.

Any drifted, expired, suspended, cross-tenant, caller-shaped, policy-stale, artifact-missing, or
integrity-uncertain state fails before protected content is inspected.

### Caller Contract

The caller may provide only:

- exact invocation ID and canonical digest;
- exact signed adjudication-policy ID and digest;
- the unchanged purpose;
- acknowledgements that model output remains untrusted, adjudication does not publish content, and
  adjudication grants no answer, tool, workflow, deployment, or operational authority; and
- idempotency and correlation identifiers.

The caller cannot provide identity, tenant, role, context, prompt, draft, evidence, citation,
validation result, acceptance threshold, adjudicator, model, endpoint, secret, tool, target,
command, schedule, workflow, approval, execution, deployment, or mutation fields.

### Identity And Access

The actor must be the same current enterprise human consumer that owns the invocation, in the exact
tenant and environment, with recent hardware-backed MFA, dedicated C1 adjudication and lineage-read
permissions, browser binding, CSRF, and current source and classification access. Service, shared,
AI, break-glass, cross-tenant, policy-signer, model gateway, endpoint owner/evaluator, context
assembler, invocation supply-chain, adjudicator, and adjudicator-attestor identities cannot act as
the human caller.

Adjudication authority is the intersection of current human access and every upstream context and
invocation authority. It cannot widen content access or extend retention.

### Trusted Deterministic Adjudicator

The approved adjudicator operates inside the protected boundary without network access or an LLM.
It must independently:

- verify invocation record, receipt, draft, context, evidence-set, citation-set, safety, policy,
  destination, authorization, protected-artifact, and canonical digests;
- parse the exact closed draft schema and reject extra, malformed, oversized, or missing fields;
- verify every citation reference against the exact context and require policy-defined citation
  coverage for each material draft statement;
- verify explicit unknowns, evidence conflicts, freshness limits, and uncertainty language are
  preserved according to policy;
- reject secrets, credentials, hidden instructions, tool/function requests, executable commands,
  autonomous-action claims, unsupported certainty, fabricated citations, and claims that an
  infrastructure operation occurred;
- produce immutable check results and one outcome: `eligible-for-presentation` or `rejected`; and
- write the full adjudication evidence to a tenant-isolated protected vault before success.

The adjudicator cannot summarize, repair, rewrite, supplement, or retry the model draft. A rejected
draft requires a later explicit lifecycle decision; Atlas does not automatically invoke another
model.

Production fails closed without an approved policy registry, deterministic adjudicator, protected
draft/context access, and encrypted adjudication vault. Development may use a deterministic
synthetic adjudicator over approved fixtures and cannot contact a model, network endpoint,
connector, target, tool, workflow, or infrastructure operation.

### Record, Manifest, And Retention

Ordinary persistence and API responses contain only opaque IDs, lineage and policy references,
digests, bounded check counts, outcome, timestamps, expiry, and safety status. They exclude context,
draft, summary, unknown text, evidence, source title, citation location, validation excerpts,
protected handles, endpoint URL, secret reference, credential, cookie, token, and raw identity.

Required intent audit and a unique immutable claim precede protected artifact access. Exact
completed replay rehydrates no new content and returns the same minimized manifest only after all
current authorization, lineage, retention, and integrity checks. Conflicting idempotency reuse
fails. Uncertain adjudication outcomes are recorded and never retried automatically.

Retention cannot exceed the invocation, context, retrieval, publication, source, classification,
policy, endpoint evaluation, or session deadline. Upstream expiry or revocation makes adjudication
evidence unavailable while minimized audit metadata remains.

### Output And Lifecycle Semantics

Success records `protected_model_draft_adjudicated` with an eligible or rejected outcome. An
eligible outcome sets only protected adjudication availability. It does not set answer generation
or publication and does not make draft content browser-readable.

Neither outcome establishes truth, operational recommendation, approval, service impact, root
cause, final answer, or permission to execute. A later independent contract governs safe answer
presentation to the same authorized human.

### Audit And Failure

Intent, authorization, invocation revalidation, draft/context rehydration, lineage verification,
schema checks, citation coverage, unknown/conflict preservation, prohibited-output checks, outcome,
vault write, persistence, replay, and read are separately audited without protected content. Any
authorization, lineage, policy, adjudicator, schema, citation, safety, vault, persistence, audit,
retention, or integrity uncertainty fails closed.

## Consequences

### Positive

- Model output cannot move directly from provider validation to user presentation.
- Adjudication is deterministic, reproducible, model-independent, and citation-bound.
- Rejection cannot trigger hidden rewriting or another model call.

### Costs

- Production needs a protected adjudication vault and approved deterministic validation profiles.
- Semantic claims that cannot be proven by deterministic evidence bindings remain ineligible.
- User-visible answers remain unavailable until a later presentation contract is implemented.

## Rejected Alternatives

### Use A Second LLM As Judge

Rejected because it adds another probabilistic disclosure and cannot provide an independent,
deterministic trust boundary.

### Let The Browser Validate Or Display The Draft

Rejected because browser access would disclose content before eligibility and weaken protected
artifact and policy integrity.

### Automatically Rewrite Rejected Drafts

Rejected because rewriting is another model invocation and could silently alter citations,
unknowns, or operational meaning.

## Follow-Up

Later independent contracts cover authorized answer presentation, recommendation generation,
impact analysis, human feedback, draft suspension and supersession, retention, deletion, revision,
controlled export, and any human-approved automation.
