# ADR-131: Durable Chat-Centered Operations Workspace

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-13 |
| Owners | Product Architecture, AI Architecture, Security Architecture, Platform Architecture |
| Related | ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-014, ATLAS-031, ATLAS-032, ATLAS-041, ATLAS-047, ATLAS-050, ATLAS-052, ATLAS-055, ATLAS-056, ADR-123 |

## Context

Atlas already provides protected grounded queries, investigations, graph impact, RCA,
recommendations, approvals and reports, but the web Workspace remains a capability landing page.
Operators cannot create, resume and continue durable scoped work through the chat-centered experience
required by FR-001. Existing one-shot query and investigation calls also do not provide a durable
conversation authority.

The first conversation slice must reuse existing protected evidence and model boundaries without
turning natural language into an execution channel. No production connector, model, vector-store or
ITSM provider is selected by this decision.

## Decision

Atlas will add an operational conversation aggregate with immutable ordered turns. A conversation is
bound to one exact organization, environment, site, owner subject and authorized infrastructure
target. It has a stable identifier, integer version, open or closed lifecycle, title, creation and
update identities/times, persistence indicator and canonical digest.

Each turn records a stable identifier and ordinal, user or assistant role, completed, partial or
failed status, bounded text, observation time, evidence references, artifact references, assumptions,
unknowns, confidence basis, failure code when applicable, safety notice and canonical digest.
Assistant claims must remain attributable to the existing protected grounded-answer contract.

Conversation create and turn append operations require server-issued scope and subject context,
unique idempotency keys and exact expected versions. An exact replay returns the original result;
different content under a reused idempotency key, stale version, wrong owner, wrong scope, unknown
target or mismatched response fails closed. There is no caller-shaped evidence, confidence, artifact,
model, authority or safety assertion.

Authorized targets come from a server-side target-access source evaluated for the exact authenticated
subject, normalized role and group identifiers, and organization/environment/site scope. The browser
must not invent, widen or cache an unbound target allowlist. Appending a question requires both the
conversation-mutation permission and an independently recorded grounded-generation authorization
decision; either denial blocks generation and persistence.

The first API surface is provider-neutral:

- `POST /api/v1/conversations` creates one open target-bound conversation.
- `GET /api/v1/conversations` lists only the caller's authorized scope and ownership boundary.
- `GET /api/v1/conversations/{conversation_id}` returns the exact aggregate and ordered turns.
- `POST /api/v1/conversations/{conversation_id}/turns` appends one question and one bounded assistant
  outcome under one idempotent version transition.

PostgreSQL is the durable production authority. A memory repository may support explicit development
fixtures, but responses and the UI must label it non-durable and production must not silently fall
back to it. Conversation and turn persistence uses the existing SQLAlchemy and Alembic patterns.

## Generation Boundary

The append workflow may call only the existing protected retrieval and model-gateway application
boundary. It may produce an evidence-grounded answer, explicit partial answer or stable failed turn.
Missing authorized evidence, model unavailability, malformed output, citation mismatch or audit
failure cannot be converted into a confident answer.

Evidence references preserve the source type, source reference, observation time, artifact identity
and opaque artifact version exactly as supplied by the authorized evidence boundary. Vendor version
labels are not coerced to integers. Conversation context supplied to retrieval remains bounded to the
authorized target, current question and a limited number of prior turns.

The first slice does not provide token streaming, autonomous follow-up, cross-target conversations,
conversation sharing, file upload, knowledge ingestion, recommendation promotion or workflow
execution. Those require later decisions and tests.

## Safety Boundary

Conversation text is input to decision support only. It cannot invoke an MCP capability, contact a
target, access a credential, create or approve an operational action, mutate an ITSM record, execute
a runbook, dispatch a workflow or change infrastructure. Every response exposes this boundary.

Navigation may open existing inventory, evidence, topology, investigation, recommendation, approval
or report views, but navigation does not create or mutate those artifacts. Any later promotion must
be an explicit typed user command with its own authorization, policy, review and audit contract.

## Security and Audit

- Authorization filters by organization, environment, site and owner before lookup and again before
  output. Cross-scope and foreign-owner identifiers do not disclose record existence.
- Bounded text, list counts and result sizes are enforced before persistence and generation.
- Ordinary API, audit and UI payloads contain no credentials, tokens, cookies, model secrets or raw
  provider requests.
- Create, read, list, append, replay, denied access, generation failure and close transitions are
  auditable. Required audit failure blocks protected mutation or response according to the existing
  fail-closed audit boundary.
- Logout clears identity-bound conversation queries from the browser cache.

## Consequences

- Workspace becomes the durable center of an operator's investigation context rather than a static
  capability catalog.
- Existing reasoning services remain evidence authorities; conversation persistence does not become
  a second source of truth for infrastructure state.
- Production deployment now requires a durable conversation repository.
- Change-impact authoring, durable audit-ledger hardening and streaming remain separate follow-up
  slices.

## Validation

- Domain and repository tests for exact scope/owner binding, ordering, lifecycle, replay, conflicts,
  version races, bounds, digests and restart-safe PostgreSQL recovery
- API tests for RBAC, non-disclosure, caller-input minimization, grounded/partial/failed outcomes,
  audit failure and zero execution authority
- Frontend contract tests for create/list/reopen/append, cache isolation, loading/error/empty states,
  keyboard navigation and evidence/unknown/safety presentation
- One Alembic head, complete backend/frontend gates, production build and live desktop/mobile reload
  validation
