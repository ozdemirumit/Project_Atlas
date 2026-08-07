# ADR-060: Governed Protected Model Invocation Contract

- Status: Accepted
- Date: 2026-08-07
- Owners: Product Owner, Solution Architecture, Security Architecture, AI Platform Engineering,
  Knowledge Retrieval Engineering, Identity Governance, Data Governance
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-025, ATLAS-027, ATLAS-030, ATLAS-031,
  ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-040, ATLAS-041, ATLAS-046, ATLAS-047, ATLAS-050,
  ATLAS-051, ATLAS-052, ATLAS-053, ATLAS-054, ATLAS-055, ATLAS-056, ADR-009 through ADR-059

## Context

ADR-059 permits one eligible human consumer to assemble an exact protected retrieval into a
bounded, citation-bound, injection-resistant model context. The context remains inside a protected
vault and grants no authority to select or invoke a model. Atlas now needs a separate lifecycle
step that can disclose that exact context to one locally approved OpenAI-compatible model endpoint,
validate a structured grounded draft, and retain the draft without publishing it as an answer.

Model invocation introduces an external processing boundary even when the endpoint is local. It
therefore requires a fresh authorization decision, explicit destination and classification policy,
approved model evaluation, protected secret resolution, deterministic request controls, strict
output validation, and an immutable non-content audit trail.

## Decision

Atlas will implement one dedicated governed protected model-invocation service. One audited `POST`
binds the same accountable context consumer, exact completed protected context, signed invocation
policy, current endpoint registry state, and current authorization state to a trusted model gateway.
An audited `GET` returns only a minimized invocation manifest after full current-policy
revalidation. Context and draft content remain in protected vaults and never enter ordinary
persistence, logs, audit payloads, browser storage, or telemetry.

This step invokes one approved text model but does not publish an answer, accept model-selected
tools, call a connector, update a graph, start a workflow, authorize an operation, approve a
deployment, or mutate infrastructure.

### Eligibility

Invocation proceeds only when:

- the exact context exists, is assembled, integrity-valid, unexpired, and bound to unchanged
  retrieval, publication, source, access, classification, purpose, policy, citation, safety,
  budget, destination, and protected-artifact lineage;
- the protected context package can be rehydrated through the approved context boundary after
  current consumer, tenant, MFA, browser, permission, lifecycle, retention, and integrity checks;
- a signed invocation policy resolves exactly one active endpoint profile and approved model,
  provider contract, task class, output schema, network boundary, classification ceiling, context
  limit, output limit, timeout, and secret reference;
- the endpoint evaluation is currently approved and all effective limits are at least as
  restrictive as the context and invocation policies; and
- no conflicting request exists for the same idempotency key.

Drifted, suspended, expired, cross-tenant, caller-shaped, policy-stale, evaluation-stale,
classification-incompatible, secret-unavailable, artifact-missing, or integrity-uncertain state
fails before disclosure to the model endpoint.

### Caller Contract

The caller may provide only:

- exact protected context ID and canonical digest;
- exact signed invocation-policy ID and digest;
- the unchanged purpose;
- acknowledgements that model output is an untrusted draft, citations and unknowns require
  validation, and invocation grants no answer-publication or operational authority; and
- idempotency and correlation identifiers.

The caller cannot provide identity, tenant, role, prompt, message, evidence, citation, endpoint,
base URL, provider, model ID, secret, temperature, token allocation, response schema, tool,
function, target, command, schedule, workflow, approval, execution, deployment, or mutation fields.
All model and request controls are derived from signed local policy and the approved registry.

### Identity And Access

The actor must be the same current enterprise human consumer that owns the context, in the exact
tenant and environment, with recent hardware-backed MFA, dedicated C1 invocation and lineage-read
permissions, browser binding, CSRF, and current source and classification access. Service, shared,
AI, break-glass, cross-tenant, context-supply-chain, policy-signer, endpoint-owner, evaluator,
gateway, and result-vault identities cannot act as the human caller.

The effective authority is the intersection of current human access, context authority, source
policy, classification, purpose, retention, signed invocation policy, endpoint evaluation, model
allowlist, task class, output contract, and network boundary. Invocation cannot widen context
authority or retain content after any upstream authority expires.

### Trusted Invocation Boundary

The approved boundary resolves every destination and request control from trusted local state. It
must:

- rehydrate the exact protected context package without exposing its protected handle or content;
- independently verify context record, package, artifact, authorization, evidence-set,
  citation-set, safety, budget, destination, and canonical digests;
- resolve the active endpoint, exact model, secret reference, limits, timeout, task, and schema from
  signed policy and the approved endpoint registry;
- verify endpoint lifecycle, evaluation, ownership separation, provider type, classification
  ceiling, network boundary, context capacity, and output capacity immediately before disclosure;
- resolve credentials only inside the transport boundary and never persist or return them;
- send immutable safety, task, untrusted-objective, evidence, and output-contract layers without
  caller alteration, with temperature zero, streaming disabled, and tool/function calling disabled;
- accept only one bounded structured response and reject oversized, malformed, partial,
  tool-bearing, or identity-mismatched provider responses; and
- write the validated draft to a tenant-isolated protected result vault before recording success.

Production fails closed without an approved endpoint registry, invocation policy, secret resolver,
trusted gateway, provider transport, and encrypted protected result vault. Development may use one
deterministic synthetic endpoint and transport over approved fixtures. Synthetic mode cannot call a
network endpoint, connector, target, tool, workflow, or infrastructure operation.

### Structured Draft Validation

The protected draft contains a bounded summary, citation reference IDs, explicit unknowns, model
identity, finish reason, schema version, and measured token usage. Validation requires:

- the returned model identity exactly matches policy;
- the response matches the approved closed schema and contains no tool or function request;
- every citation reference belongs to the exact protected context and at least one citation is
  present for an evidence-based draft;
- unknowns are explicit and non-empty;
- input and output usage are non-negative and within policy and endpoint limits;
- finish reason is accepted by policy and truncation is never treated as success; and
- output safety checks find no credential disclosure, operational execution claim, hidden
  instruction, or unsupported authority.

Validation failure produces no available draft and is never silently repaired by another model.

### Manifest, Replay, And Retention

Ordinary persistence and API responses contain only opaque IDs, lineage references, policy and
endpoint profile identifiers, model identifier, digests, bounded counts, token usage, finish
reason, outcome, timestamps, and safety status. They exclude prompt and draft content, objective,
evidence, source title, citation location, protected handles, endpoint URL, secret reference,
credential, cookie, token, and raw identity.

Required intent audit and a unique immutable request claim precede context rehydration or model
disclosure. Exact completed replay may return the same minimized manifest only after current
identity, MFA, browser, permission, context, source, classification, purpose, policy, endpoint,
evaluation, retention, and integrity checks. It never calls the model again. Conflicting
idempotency reuse fails. An uncertain provider outcome is recorded and is not automatically
retried because duplicate invocation cannot be proven safe.

The invocation and draft retention deadline cannot exceed the context, retrieval, publication,
source, classification, policy, endpoint evaluation, or session deadline. Expiry or upstream
revocation makes the protected draft unavailable while minimized evidence-chain metadata remains.

### Output And Lifecycle Semantics

A successful result records `protected_model_invoked` and makes one protected response draft
available. It sets `model_invoked` true but leaves answer publication, graph update, scheduling,
workflow continuation, tool selection, execution authorization, deployment approval, and
infrastructure mutation false.

The draft is model output, not a trusted fact, recommendation, approval, final user answer, or
operational instruction. A later independent contract must validate and present any user-visible
answer.

### Audit And Failure

Intent, authorization, context rehydration, lineage verification, endpoint resolution, evaluation
verification, secret resolution, disclosure, provider outcome, schema validation, citation
validation, safety validation, vault write, persistence, replay, and read are separately audited.
Audit excludes all protected content and secrets. Any authorization, lineage, destination,
evaluation, transport, provider, schema, citation, safety, vault, persistence, audit, retention, or
integrity uncertainty fails closed.

## Consequences

### Positive

- A caller cannot redirect protected context to an arbitrary model or endpoint.
- Model output is citation-bound, schema-validated, retained privately, and independently audited.
- Tool use, answer presentation, recommendations, and operations remain separate authorization
  decisions.

### Costs

- Production requires approved endpoint and policy registries, secret resolution, a trusted
  gateway, transport controls, and a protected result vault.
- Uncertain provider outcomes cannot be retried automatically.
- Model output remains unavailable to end users until a later presentation contract is completed.

## Rejected Alternatives

### Extend The Existing Grounded-Answer Endpoint

Rejected because its caller-supplied query and direct retrieval-to-model flow do not enforce the
new protected context, destination, replay, retention, and result-vault boundaries.

### Let The Caller Choose The Endpoint Or Model

Rejected because it would permit destination redirection, classification-policy bypass, evaluation
bypass, and uncontrolled data disclosure.

### Return The Model Draft Directly To The Browser

Rejected because invocation success does not establish truth, final-answer safety, presentation
authority, or permission to expose protected response content.

### Retry Provider Failures Automatically

Rejected because a timeout or transport failure may occur after the provider processed the
request, making duplicate disclosure and duplicate invocation uncertain.

## Follow-Up

Later independent lifecycle contracts cover grounded draft adjudication, final answer presentation,
recommendation generation, impact analysis, context and draft evaluation, suspension,
supersession, retention, deletion, revision, controlled export, and any human-approved automation.
