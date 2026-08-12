# ADR-124: Governed ITSM Handoff Human Review

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-13 |
| Owners | Product Architecture, Security Architecture, Operations Architecture |
| Related | ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-016, ATLAS-032, ATLAS-036, ATLAS-037, ATLAS-047, ATLAS-050, ATLAS-052, ATLAS-055, ATLAS-056, ADR-123 |

## Context

Atlas generates an immutable technical decision report and an optional review-only ITSM handoff
draft. The draft is deliberately provider-neutral and cannot contact or mutate an external ITSM
system. Its embedded review state remains pending, so the platform cannot yet preserve separately
attributable evidence that an eligible human reviewed the exact generated handoff.

ATLAS-036 requires accountable human or policy-authorized review before consequential outbound
submission. No ITSM vendor, endpoint, credential, production field mapping or sandbox has been
selected. Atlas therefore needs a provider-neutral review record without implying that dispatch is
configured, approved or authorized.

## Decision

Atlas will store one immutable human review decision for an exact ITSM handoff draft. The decision
binds organization, environment, site, report ID, report version, report digest, handoff draft ID,
canonical handoff digest, handoff idempotency key, incident reference, operation, requester,
reviewer, rationale, outcome and expiry.

The supported outcomes are accept, needs evidence and reject. Accept sets only `review_complete`.
All decisions retain false values for dispatch authorization, external-record mutation, ITSM
approval, workflow approval, infrastructure execution and infrastructure mutation.

The reviewer must be a separately attributable human using a browser session backed by multi-factor
or hardware-backed authentication and the dedicated `role.itsm-reviewer` role. Exact-scope C1 read
and C2 decision permissions remain default deny. Self-review, changed or expired source material,
wrong scope, missing acknowledgement, invalid rationale and conflicting idempotency replay fail
closed. An exact retry returns the original immutable record.

The API applies CSRF protection to decisions, no-store response headers and attributable audit. The
repository is in memory without a database URL and PostgreSQL-backed when persistence is configured.
The current technical-report source is process-local. After a process restart, a durable review can
remain in PostgreSQL but source revalidation is unavailable until durable report storage is added;
read or decision attempts therefore fail closed instead of trusting an orphaned record.

The Health governance workspace presents the pending or completed review, exact-source status,
reviewer identity, rationale, canonical digest and explicit authority boundaries. Decision controls
appear only to an apparently eligible session, while the API remains authoritative. No endpoint,
credential, arbitrary field, ticket mutation or dispatch control is exposed.

## Safety Boundary

This decision records review evidence only. It does not select an ITSM provider, create or update a
ticket, enqueue outbound work, satisfy an ITSM or change approval, approve a workflow, authorize an
agent, contact infrastructure, disclose credentials or grant execution authority. Any future
dispatch capability requires a separate architecture decision, deployment inputs, sandbox evidence,
policy controls, approval semantics and independent authorization.

## Consequences

- Atlas can prove who reviewed the exact report-bound handoff draft and what outcome they recorded.
- Review evidence remains useful before a vendor adapter is selected and cannot be mistaken for a
  successful external submission.
- Separation of duties and MFA requirements prevent the report requester from self-attesting.
- Durable report persistence remains a prerequisite for revalidating review records after restart.
- A future dispatch slice can consume review completeness as one input but must not treat it as
  sufficient approval or authority.

## Validation

- Domain, service, API authorization, CSRF, idempotency, separation and PostgreSQL mapping tests
- Frontend eligibility, acknowledgement, completed-record and no-authority presentation tests
- Complete backend and frontend quality gates, one Alembic head and production build
- Live desktop and mobile validation with no dispatch or execution controls present
