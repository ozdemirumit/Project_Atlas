# ADR-059: Governed Protected Model-Context Assembly Contract

- Status: Accepted
- Date: 2026-08-07
- Owners: Product Owner, Solution Architecture, Security Architecture, AI Platform Engineering,
  Knowledge Retrieval Engineering, Identity Governance, Data Governance
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-025, ATLAS-027, ATLAS-030, ATLAS-031,
  ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-040, ATLAS-041, ATLAS-046, ATLAS-047, ATLAS-050,
  ATLAS-051, ATLAS-052, ATLAS-053, ATLAS-054, ATLAS-055, ATLAS-056, ADR-009 through ADR-058

## Context

ADR-058 allows one eligible human consumer to retrieve an authorized, citation-ready evidence
package through a trusted protected boundary. The package remains untrusted evidence and grants no
model-context or model-invocation authority. Atlas now needs a separate lifecycle step that can
assemble that exact package into a bounded, injection-resistant model context while preserving
classification, purpose, citation, retention, and access constraints.

## Decision

Atlas will implement one dedicated governed protected model-context assembly service. One audited
`POST` binds the same accountable retrieval consumer, exact completed retrieval, bounded task
objective, signed context policy, and current authorization state to a trusted deterministic
assembler. An audited `GET` returns a minimized context manifest only after full current-policy
revalidation. Context content remains in a tenant-isolated protected context vault and does not
enter ordinary persistence, logs, audit payloads, or browser storage.

This step does not call an LLM, select a runtime model endpoint, create a chat answer, authorize a
tool, start a workflow, or perform an infrastructure operation.

### Eligibility

Assembly proceeds only when:

- the exact retrieval exists, is complete, integrity-valid, unexpired, and bound to unchanged
  publication, staging, embedding, chunking, materialization, preparation, approval, review,
  knowledge-item, source, governance, model, projection, route, access, and policy lineage;
- the protected evidence artifact can be rehydrated through the approved retrieval boundary after
  current consumer, tenant, MFA, browser, purpose, permission, source, classification, lifecycle,
  retention, and integrity checks;
- knowledge, retrieval publication, and protected retrieval are true while model invocation,
  answer publication, graph update, scheduling, workflow, execution, deployment, and infrastructure
  mutation remain false; and
- no conflicting request exists for the same idempotency key.

Drifted, suspended, superseded, expired, cross-tenant, caller-shaped, policy-stale, access-stale,
artifact-missing, or integrity-uncertain lineage fails before context assembly.

### Caller Contract

The caller may provide only:

- exact retrieval ID and canonical digest;
- exact signed context-policy ID and digest;
- one bounded task objective and purpose compatible with the retrieval purpose;
- acknowledgements that user intent and retrieved content remain untrusted, citation boundaries
  must be preserved, and assembly grants no model, tool, workflow, deployment, or operation
  authority; and
- idempotency and correlation identifiers.

The caller cannot provide identity, tenant, role, source, classification, prompt layer, system or
developer instruction, prompt template, delimiter, evidence selection, citation rewrite, content
ordering, token allocation, truncation strategy, endpoint, provider, model ID, secret, tool,
target, command, schedule, workflow, approval, execution, deployment, or mutation fields. Task
class, output schema, destination constraints, context limits, layer ordering, separators,
sanitization, and evidence allocation are policy-derived.

### Identity And Access

The actor must be the same current enterprise human consumer that owns the retrieval, in the exact
tenant and environment, with recent hardware-backed MFA, dedicated C1 context-assembly and
lineage-read permissions, browser binding, CSRF, and a current signed policy. Service, shared, AI,
break-glass, cross-tenant, retrieval supply-chain, policy-signer, and trusted-assembler identities
cannot act as the human caller.

The effective context authority is the intersection of current human access, retrieval access,
source policy, classification, purpose, environment, retention, signed context policy, approved
task class, and destination profile. Assembly cannot widen retrieval scope or retain content after
any upstream authority expires.

### Trusted Context Assembler

The approved assembler resolves every prompt layer, separator, safety rule, output contract,
destination profile, and budget only from signed local policy and immutable lineage. It must:

- rehydrate the exact protected evidence artifact through the trusted retrieval boundary without
  exposing its protected handle to the caller;
- verify query, package, result, citation, authorization-context, retrieval-receipt, and protected
  artifact digests before using content;
- create distinct immutable layers for platform invariants, policy task contract, quoted user
  objective, and individually delimited evidence records;
- treat the user objective and every evidence field as untrusted data, never as system, developer,
  policy, tool, or authorization instructions;
- preserve evidence-reference and citation-location bindings, source authority, applicability,
  lifecycle, freshness, conflict, and safety labels;
- reject malformed delimiters, control characters, hidden active content, citation collisions,
  digest mismatch, unsupported safety state, or content that cannot be represented safely;
- apply deterministic policy-derived character and estimated-token budgets before assembly,
  allocating space to invariant and output-contract layers before evidence;
- include only complete evidence units, omit lower-priority units deterministically when required,
  and produce an insufficient-context outcome when mandatory grounding cannot fit;
- place the canonical context package in an encrypted tenant-isolated protected context vault with
  bounded retention; and
- sign a metadata receipt binding retrieval, consumer, authorization context, task class, purpose,
  policy, destination profile, included evidence digests, budgets, protected artifact digest,
  safety result, and assembly trace.

The assembler performs no model-assisted rewrite, summarization, translation, classification,
reranking, or token counting. The initial implementation uses a conservative deterministic token
estimate. A later model-invocation contract must revalidate the actual selected endpoint, model,
tokenizer, classification ceiling, and context limit before any content leaves the protected
boundary.

Production fails closed without an approved trusted assembler and encrypted protected context
vault. Development may use a deterministic synthetic assembler and in-memory protected vault over
approved fixtures; neither may contact a model, connector, target, tool, external service, or
network endpoint.

### Context Package And Manifest

The protected context package contains:

- schema, task class, output contract, policy, classification, purpose, and destination profile;
- immutable platform-safety and task-contract layers;
- the bounded user objective clearly marked as untrusted intent;
- zero or more complete evidence units, each delimited and bound to one authorized citation;
- explicit unknown, conflict, freshness, and prompt-injection handling instructions; and
- canonical layer, evidence-set, citation-set, safety, and package digests.

The ordinary API manifest contains only opaque IDs, lineage references, digests, task class,
classification, bounded counts, budget utilization, outcome, timestamps, and safety status. It
contains no raw query, objective, excerpt, source title, citation location, prompt text, delimiter,
protected artifact handle, endpoint URL, model identifier, key, cookie, raw identity, credential,
or secret.

### Record, Replay, And Retention

Required intent audit and a unique immutable request claim precede protected artifact creation.
Exact completed replay may rehydrate the same manifest only after current identity, MFA, browser,
permission, source, classification, purpose, policy, lifecycle, retention, and integrity checks.
It cannot rebuild, widen, reorder, or silently truncate context. Conflicting idempotency reuse
fails. Failure or uncertainty after assembly begins is recorded and never retried automatically.

The context retention deadline cannot exceed the retrieval artifact, publication, source,
classification, policy, or session deadline. Expiry or upstream revocation makes the context
unavailable even when ordinary metadata remains for audit and evidence-chain integrity.

### Output And Lifecycle Semantics

A successful result records only `protected_model_context_assembled`. An insufficient-evidence or
insufficient-budget result is a valid non-leaking outcome and does not create a model-ready context.

Assembly does not establish truth, resolve evidence conflicts, follow document instructions,
invoke a model, generate an answer, update a graph, select or call a tool, start a schedule or
workflow, authorize an operation, approve deployment, or mutate infrastructure.

### Read, Failure, And Audit

Only the accountable retrieval consumer may read the minimized manifest while current identity,
tenant, MFA, browser, permission, source, classification, purpose, policy, lifecycle, retention,
and integrity authority remain valid. Responses use strict `no-store`, `nosniff`, no-referrer, and
restrictive content-security headers.

Intent, authorization, retrieval rehydration, lineage verification, layer construction, safety
validation, budget allocation, citation binding, vault write, metadata persistence, replay, and
read are separately audited. Audit excludes raw query, objective, excerpt, title, citation
location, prompt layer, context body, delimiter, protected artifact handle, endpoint, model, token,
cookie, raw identity, credential, and secret. Any authorization, lineage, citation, safety, budget,
vault, persistence, audit, retention, or integrity uncertainty fails closed.

## Consequences

### Positive

- Retrieved text cannot silently become a higher-trust instruction layer.
- Context is reproducible, citation-bound, policy-budgeted, and independently auditable.
- Model invocation remains a separate authorization and destination-disclosure decision.

### Costs

- Production requires a second protected vault and an approved deterministic assembler.
- Context may become unavailable after upstream access or retention changes.
- Conservative deterministic budgeting can omit evidence that a model-specific tokenizer might fit.

## Rejected Alternatives

### Send Retrieval Results Directly To A Model Gateway

Rejected because retrieval authorization does not establish prompt-layer, injection, destination,
classification-ceiling, token-budget, or model-invocation authority.

### Let The Browser Build Or Inspect The Full Prompt

Rejected because it would disclose protected content and policy instructions, weaken integrity,
and introduce browser storage, extension, telemetry, and manipulation risks.

### Let The Caller Select Model, Prompt, Or Evidence

Rejected because caller-shaped controls could widen disclosure, remove safety layers, bias
citations, or bypass the independently governed model-invocation decision.

### Use An LLM To Sanitize Or Summarize Context

Rejected for this slice because it would itself be a model invocation before destination,
classification, evaluation, output, and failure semantics are governed.

## Follow-Up

Later independent lifecycle contracts cover governed model invocation, grounded structured-output
validation, answer presentation, context evaluation, suspension, supersession, retention,
deletion, revision, and controlled export.
