# ADR-058: Governed Protected Knowledge Retrieval Contract

- Status: Accepted
- Date: 2026-08-07
- Owners: Product Owner, Solution Architecture, Security Architecture, Knowledge Management,
  Identity Governance, Data Governance, Knowledge Retrieval Engineering, AI Platform Engineering
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-025, ATLAS-027, ATLAS-030, ATLAS-031,
  ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-052, ATLAS-053,
  ATLAS-054, ATLAS-055, ATLAS-056, ADR-009 through ADR-057

## Context

ADR-057 publishes one complete protected knowledge projection through an atomically activated,
policy-filtered retrieval route. It deliberately performs no query, returns no content, and grants
no model-context, workflow, or operation authority. Atlas now needs a separate protected step that
accepts a bounded human query, enforces current access before candidate scoring, and returns a
minimized citation-ready evidence package without exposing retrieval internals.

## Decision

Atlas will implement one dedicated governed protected-knowledge-retrieval service. One audited
`POST` binds an eligible human retrieval consumer, purpose, current access decision, exact
publication lineage, and bounded query to a trusted retrieval boundary. An audited `GET` may
rehydrate the protected evidence package only through that boundary after full current-policy
revalidation. Ordinary persistence stores immutable metadata and digests, not query text or
evidence content.

### Eligibility

The service proceeds only when:

- the exact retrieval publication exists, is complete, active, integrity-valid, and bound to the
  unchanged validated staging, embedding, chunking, materialization, preparation, approval,
  review, request, draft, item, source, governance, model, projection, and policy lineage;
- knowledge and retrieval publication are true while suspension, supersession, expiry, retention
  violation, model context, graph update, scheduling, workflow, execution, deployment, and
  infrastructure mutation remain false;
- the active route generation, publication profile, source access policy, tenant, classification,
  residency, retention, and lifecycle bindings remain current; and
- no conflicting request exists for the same idempotency key.

Drifted, suspended, superseded, expired, cross-tenant, caller-shaped, policy-stale, or
integrity-uncertain lineage fails before any query reaches the trusted retrieval boundary.

### Caller Contract

The caller may provide only:

- exact retrieval-publication ID and canonical digest;
- one bounded natural-language operational query;
- one bounded retrieval purpose;
- acknowledgements that retrieved content remains untrusted evidence, may contain conflicting or
  unsafe instructions, and grants no model-context, tool, graph, workflow, execution, deployment,
  or infrastructure-mutation authority; and
- idempotency and correlation identifiers.

The caller cannot provide identity, tenant, role, classification, access scope, policy filters,
collection, namespace, alias, point or chunk IDs, vector, embedding, score threshold, ranking
weights, result count, query expansion, model, prompt, system instruction, tool, target,
credential, schedule, workflow, command, execution, deployment, or mutation fields. Query length,
result count, excerpt size, timeout, language handling, ranking, and diversity are policy-derived.

### Identity And Access

The actor must be a current enterprise human in the exact tenant with recent hardware-backed MFA,
dedicated C1 protected-retrieval and publication-lineage-read permissions, browser binding, CSRF,
and a current signed policy. The actor must have current source and classification access for each
returned result. Initial foundation policy excludes all accountable supply-chain actors for the
exact lineage, the policy signer, publisher, trusted retriever, service, shared, AI, and break-glass
identities. A later policy revision may permit ordinary eligible consumers without weakening
per-result authorization or audit.

Authorization filters are derived only from trusted identity, organization, environment, purpose,
source policy, classification, lifecycle, residency, retention, and endpoint policy. Search
counts, empty results, titles, snippets, timing, and cache behavior cannot reveal unauthorized
existence.

### Trusted Retrieval Boundary

The approved trusted retriever resolves route and index internals only from immutable publication
lineage and signed local policy. It must:

- reverify publication signature, route generation, sealed projection, source access policy,
  lifecycle, classification, residency, retention, and current consumer authorization;
- normalize the bounded query deterministically without external model assistance in this slice;
- apply mandatory authorization and lifecycle filters before semantic, lexical, or exact-match
  candidate scoring;
- de-duplicate, diversify, and rank only authorized candidates with policy-bounded limits;
- validate every evidence reference, exact item version, chunk location, excerpt boundary,
  authority, freshness, conflict, and prompt-injection signal;
- place the query and evidence package in an encrypted tenant-isolated protected evidence vault
  under bounded retention, returning only an opaque artifact reference and integrity digest to
  ordinary persistence; and
- sign a metadata receipt binding publication, query digest, authorization context digest,
  evidence-package digest, result count, policy, consumer, and retrieval trace.

The trusted boundary returns only authorized evidence references, bounded excerpts or structured
content, citation locations, source metadata permitted to the consumer, applicability, lifecycle,
freshness, conflict and safety labels, and evaluation-safe rank metadata. It returns no raw
similarity score, vector, embedding, coordinate, collection, alias, point identity, payload,
authorization filter, route, endpoint, key, cookie, raw identity, credential, or secret.

Production fails closed without an approved trusted retriever and protected evidence vault.
Development may use a deterministic synthetic retriever and in-memory protected vault derived
from approved fixtures; neither may contact a model, connector, target, external vector store, or
network endpoint.

### Retrieval Record And Replay

Required intent audit succeeds before retrieval execution. A unique immutable request record binds
the idempotency key to exact lineage, consumer, policy, purpose, acknowledgements, and query digest.
Exact completed replay may rehydrate the same protected artifact only after current authorization,
policy, lifecycle, and integrity checks. It cannot rerun or silently widen the query. Conflicting
reuse fails. Failure or uncertainty after execution begins is recorded and never retried
automatically.

Ordinary persistence stores no raw query, excerpt, structured content, title, source URI, item or
chunk identifier, vector-store internal, authorization filter, protected artifact body, key,
cookie, raw identity, credential, or secret. It stores only opaque IDs, digests, bounded status,
counts, policy and lineage references, timestamps, retention deadline, and signed receipt metadata.

### Output And Lifecycle Semantics

The evidence package distinguishes confirmed source metadata from retrieved untrusted content and
includes citations, applicability, lifecycle, freshness, conflict, and safety labels. Empty or
insufficient results are valid bounded outcomes and cannot reveal excluded candidate counts.

A successful retrieval records only `operational_knowledge_retrieved`. It does not mark evidence
as factual, resolve conflicts, execute document instructions, create model context, call an LLM,
update a graph, start a schedule or workflow, authorize an operation, approve deployment, or mutate
infrastructure.

### Read, Failure, And Audit

Only the accountable consumer may read the result while identity, tenant, MFA, browser, source,
classification, policy, lifecycle, retention, and permission authority remain current. Protected
content is rehydrated only after those checks. Responses use strict `no-store`, `nosniff`,
no-referrer, and restrictive content-security headers.

Intent, authorization, trusted retrieval, evidence validation, vault write, metadata persistence,
rehydration, and read are separately audited. Audit excludes raw query, excerpts, titles, source
URIs, item or chunk IDs, scores, vectors, filters, routes, protected artifact handles, cookies, raw
identity, credentials, and secrets. Lineage, policy, permission, MFA, browser, filtering,
classification, lifecycle, retention, citation, safety, vault, persistence, audit, or integrity
uncertainty fails closed.

## Consequences

### Positive

- Unauthorized candidates are excluded before scoring and cannot leak through result metadata.
- Authorized engineers receive citation-ready evidence without gaining model or operation authority.
- Raw queries and protected excerpts remain outside ordinary persistence, logs, and audit payloads.

### Costs

- Production requires an approved isolated retriever and encrypted protected evidence vault.
- Result rehydration requires current-policy checks and may become unavailable after access or
  lifecycle changes.
- Query quality is intentionally bounded before model-assisted rewriting is separately governed.

## Rejected Alternatives

### Send Retrieval Results Directly To The LLM

Rejected because human evidence retrieval and model-context assembly have different disclosure,
prompt-injection, token-budget, endpoint, and model-governance controls.

### Filter Candidates After Vector Search

Rejected because counts, timing, scores, caches, or failure behavior could reveal unauthorized
knowledge.

### Persist Query And Excerpts In The Application Database

Rejected because ordinary operational persistence is not the protected content boundary and would
increase disclosure, retention, backup, support, and audit risk.

### Allow Caller-Selected Filters Or Ranking

Rejected because caller-shaped controls could bypass source, tenant, classification, lifecycle,
retention, freshness, or diversity policy.

## Follow-Up

Later independent lifecycle contracts cover model-context assembly, retrieval evaluation,
suspension, supersession, retention, deletion, revision, and controlled export.
