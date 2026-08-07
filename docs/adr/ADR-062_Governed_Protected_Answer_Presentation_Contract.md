# ADR-062: Governed Protected Answer Presentation Contract

- Status: Accepted
- Date: 2026-08-07
- Owners: Product Owner, Solution Architecture, Security Architecture, AI Platform Engineering,
  Knowledge Retrieval Engineering, Identity Governance, Data Governance
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-025, ATLAS-027, ATLAS-030, ATLAS-031,
  ATLAS-032, ATLAS-033, ATLAS-037, ATLAS-040, ATLAS-041, ATLAS-046, ATLAS-047, ATLAS-050,
  ATLAS-051, ATLAS-052, ATLAS-053, ATLAS-054, ATLAS-055, ATLAS-056, ADR-009 through ADR-061

## Context

ADR-061 independently adjudicates one exact protected model draft against its exact context and
evidence bindings without returning draft content to the browser. An eligible outcome proves that
the deterministic validation profile passed, but the draft and full adjudication report remain in
protected vaults. Atlas needs a separate disclosure boundary before the same authorized human can
read the bounded answer.

Presentation must preserve the exact adjudicated summary, citation references, and unknowns. It
must not transform eligibility into truth, recommendation, workflow continuation, tool authority,
approval, or evidence that an infrastructure action occurred.

## Decision

Atlas will implement one dedicated governed protected-answer presentation service. A first audited
`POST` creates one immutable presentation record for an exact eligible adjudication and returns one
bounded inert answer snapshot. A later audited `GET` may reproduce only that same snapshot while
the consumer, browser, policies, retention, invocation, context, draft, adjudication, and protected
artifacts remain current.

This stage does not invoke a model, rewrite content, retrieve new evidence, generate a
recommendation, select a tool, call a connector, update a graph, schedule work, continue a workflow,
authorize execution, approve deployment, or mutate infrastructure.

### Eligibility

Presentation proceeds only when:

- the exact adjudication exists, completed successfully with outcome
  `adjudication-outcome.eligible`, is integrity-valid and unexpired, and is bound to unchanged
  invocation, context, retrieval, publication, source, access, classification, purpose, model,
  endpoint, policy, citation, unknown, safety, destination, and protected-artifact lineage;
- the exact protected adjudication report, model draft, context package, and evidence package can
  be rehydrated through their existing trusted boundaries after current consumer, tenant, MFA,
  browser, permission, lifecycle, retention, and integrity checks;
- a current signed presentation policy resolves the approved trusted presenter, required source
  and receipt schemas, classification ceiling, maximum summary/unknown/citation/byte limits,
  permitted media type, inert rendering profile, replay rule, and cleanup requirements; and
- no conflicting request exists for the adjudication's unique presentation claim or idempotency
  key.

Rejected, expired, superseded, suspended, cross-tenant, caller-shaped, policy-stale,
artifact-missing, or integrity-uncertain state fails before answer content is disclosed.

### Caller Contract

The first-presentation caller may provide only:

- exact adjudication ID and canonical digest;
- exact signed answer-presentation-policy ID and digest;
- the unchanged purpose;
- acknowledgements that the answer is bounded decision support, citations and unknowns remain
  material, and presentation grants no recommendation or operational authority; and
- idempotency and correlation identifiers.

The caller cannot provide identity, tenant, role, invocation, context, prompt, draft, summary,
unknown, evidence, citation, field selection, renderer, redaction, limit, presenter, model,
endpoint, secret, recommendation, target, credential, command, tool, schedule, workflow, approval,
execution, deployment, or mutation fields.

The replay caller supplies only the opaque presentation ID in the path. Atlas derives all source,
policy, access, purpose, and browser bindings from trusted records.

### Identity And Access

The actor must be the same current enterprise human consumer that owns the invocation and
adjudication, in the exact tenant and environment, with recent hardware-backed MFA, dedicated C1
answer-presentation and lineage-read permissions, browser binding, CSRF for first presentation,
and current source and classification access.

Service, shared, AI, break-glass, cross-tenant, policy-signer, model gateway, endpoint owner or
evaluator, context assembler, adjudicator, presenter, and presenter-attestor identities cannot act
as the human caller. Presentation authority is the intersection of current human access and every
upstream authority; it cannot widen content access or extend retention.

### Atomic Presentation Claim

Required intent audit succeeds before the repository creates an immutable claim with a unique
constraint on adjudication ID. Claim creation is the point of no return. An existing claim is
reusable only when exact subject, browser, request, adjudication, policy, idempotency, and completed
presentation evidence match.

Failure or uncertainty after claim creation remains claimed and returns no partial answer. The
first-presentation endpoint never retries presentation automatically or creates a second snapshot.

### Trusted Presenter Boundary

The application sends only trusted adjudication, invocation, draft, context, and evidence lineage;
expected content and artifact digests; governance labels; policy limits; subject/browser binding
digests; and an opaque presentation ID. The trusted presenter must:

1. resolve only the exact protected report and draft bound to the eligible adjudication;
2. verify report, draft, invocation, context, citation, unknown, safety, policy, authorization,
   retention, protected-artifact, and canonical digests;
3. reject any outcome other than eligible and any schema, count, citation, unknown, or content
   drift from the adjudicated snapshot;
4. preserve the exact bounded summary, ordered citation references, and ordered explicit unknowns
   without model transformation, supplementation, repair, or omission;
5. reject HTML, active content, executable payloads, external resource loading, tool or function
   requests, credentials, secrets, and claims that an operation was performed;
6. normalize output as a closed inert UTF-8 structure and enforce policy item and byte limits
   without splitting a UTF-8 sequence;
7. compute answer-content, citation, unknown, source-binding, rendering, and cleanup digests;
8. erase plaintext working buffers and close protected artifact channels in every outcome; and
9. return the bounded answer plus a signed minimized receipt to the application boundary.

Production fails closed without an approved policy registry, trusted presenter, protected
adjudication/draft access, and encrypted vault boundaries. Development may use a deterministic
synthetic presenter over approved fixtures and cannot contact a model, target, connector, tool,
workflow, deployment system, or infrastructure operation.

### Response Boundary

The API may return only:

- opaque presentation, adjudication, invocation, and context IDs;
- safe classification and policy labels, plain-text media type, timestamps, and expiry;
- the exact bounded summary, ordered authorized citation reference IDs, and ordered explicit
  unknowns;
- bounded item/byte counts and content, citation, unknown, source, rendering, cleanup, and receipt
  digests; and
- explicit flags showing content was disclosed as decision support and no recommendation,
  workflow, execution, deployment, or infrastructure mutation occurred.

Responses use `Cache-Control: no-store`, `Pragma: no-cache`, `X-Content-Type-Options: nosniff`, a
restrictive content security policy, and no referrer policy. Answer content never appears in URLs,
cookies, audit, logs, exceptions, traces, metrics, events, PostgreSQL records, browser local or
session storage, server-side session storage, vector stores, retrieval indexes, or graph records.
The frontend renders every value as text and never as HTML or executable Markdown.

### Record And Replay

The immutable application record uses state `protected_answer_presented` and contains metadata and
integrity evidence only: exact upstream lineage, claim and presentation IDs, salted consumer and
browser bindings, policy/presenter identities, governance labels, counts, digests, timestamps,
expiry, purpose, and canonical digest. It contains no summary, unknown text, evidence, source title,
citation location, artifact coordinate, secret, cookie, token, or raw identity.

An audited `GET` may ask the trusted presenter to reproduce the exact snapshot while every proof
remains current. Reproduced content, ordering, counts, byte count, and digests must equal the
immutable presentation record. Replay never extends retention, changes content, invokes a model,
creates a new presentation, or widens access. Drift, expiry, revocation, missing artifacts, or
uncertainty fails closed and returns no partial answer.

### Presentation Is Not Operational Advice

Success sets only `answer_presented=true`. It does not establish truth, root cause, service impact,
recommended remediation, change approval, rollback validity, or permission to act. Recommendation
generation, impact analysis, workflow planning, approval, tool selection, connector invocation,
execution, deployment, and infrastructure mutation require later independent contracts.

### Failure And Audit

Intent audit precedes claim creation; claim audit follows a successful claim; content-read audit
must succeed before any answer response; completion audit succeeds before metadata persistence;
and every replay has a separate read audit. Audit identifies the accountable enterprise subject
but never contains answer content, protected handles, cookies, or secrets.

Failures before claim creation read no protected artifact. Failures after claim creation remain
claimed and return no partial answer. Presenter, audit, persistence, cleanup, integrity, replay, or
authorization uncertainty fails closed.

### Persistence And API

Claims and records are immutable, deterministic, concurrency-safe, and equivalent in memory and
PostgreSQL. The API uses normal browser session, mutation CSRF for first presentation, strict
schemas, dedicated default-deny RBAC, C1 classification, recent hardware MFA, exact tenant and
consumer scope, minimized no-store responses, and safe errors.

## Consequences

### Positive

- Protected model output cannot reach a browser before independent eligibility adjudication.
- The user sees the exact citation-bound, unknown-preserving snapshot that was adjudicated.
- Plaintext answer content remains outside ordinary persistence and telemetry.
- Refresh can reproduce only the same verified snapshot while all authority remains current.

### Costs

- Production requires an independent trusted presenter and protected artifact access.
- Browser refresh after expiry cannot recover content and requires a new governed analysis cycle.
- Answer content cannot use generic caches, analytics, client storage, or server-side sessions.

## Rejected Alternatives

### Return The Draft From The Adjudication Endpoint

Rejected because it collapses independent validation and disclosure into one boundary.

### Persist The Presented Answer In PostgreSQL

Rejected because it creates an unmanaged plaintext copy outside protected vault controls.

### Let The Browser Render Model Markdown Or HTML

Rejected because active content, unsafe links, and hidden markup create an avoidable execution and
exfiltration boundary.

### Treat Eligibility As A Recommendation Or Approval

Rejected because deterministic content checks do not establish operational correctness, impact,
change authority, or permission to execute.

## Follow-Up

Later independent contracts cover grounded recommendation generation, service-impact analysis,
confidence and evidence explanation, human feedback, draft suspension and supersession, retention,
deletion, controlled export, workflow planning, approval, and any human-approved automation.
