# ADR-125: Durable Technical Reports and Restart Revalidation

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-13 |
| Owners | Product Architecture, Security Architecture, Operations Architecture |
| Related | ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-016, ATLAS-032, ATLAS-036, ATLAS-047, ATLAS-050, ATLAS-052, ATLAS-053, ATLAS-055, ATLAS-056, ADR-124 |

## Context

ADR-124 makes the human decision on a report-bound ITSM handoff durable, but the technical report
that supplies its exact source remains process-local. A restart can therefore leave valid review
evidence without the report, rendered content and handoff draft needed to revalidate it. Atlas must
fail closed in that state, which prevents operators from recovering the report or using the review
evidence after restart.

## Decision

Atlas will persist each immutable technical report as a complete JSONB artifact plus indexed binding
columns. The artifact contains its sections, recommendation and RCA lineage, review state, rendered
Markdown, content digest, classification, expiry, component versions, ITSM handoff draft and all
no-authority fields. Indexed columns retain report identity, organization, environment, site,
requester, target, version, prior version, expiry and digest.

A canonical request fingerprint provides exact create idempotency across processes. A separate
lineage fingerprint supports monotonic report versions and exact prior-version references. Database
constraints make report ID, request fingerprint and lineage/version immutable and unique. Conflicts
fail closed; Atlas does not overwrite a report or silently select a different artifact.

An exact persisted request may be reused before consulting the process-local recommendation source,
provided its scope, requester, source ID/version, report options, expiry, digest and authority
boundaries all revalidate. Creating a new report still requires the exact live recommendation source.
This preserves safe retry after restart without allowing stale source material to create new output.

Protected report lookup uses a dedicated default-deny C1 permission, exact
organization/environment/site/requester scope, classification ceiling, expiry and content-integrity
checks. Successful recovery is attributable in audit and returned with `Cache-Control: no-store`.
The UI stores only the opaque report ID in the URL and uses the protected lookup to restore the
report and its separately durable human-review evidence after reload.

Without a database URL Atlas continues to use an in-memory repository. With PostgreSQL configured,
the report repository follows the platform's async engine, migration and close lifecycle. The ITSM
review service always reloads and revalidates the exact report source, so durable reviews become
restart-safe without weakening their existing MFA, separation or binding checks.

## Safety Boundary

Persistence and recovery do not authorize report execution, ITSM dispatch, external record
mutation, workflow or change approval, agent action or infrastructure mutation. The restored report
and handoff retain false authority fields, remain review-only and cannot carry endpoints or
credentials. Any outbound ITSM adapter remains a separate future architecture decision.

## Consequences

- Operators can recover generated reports and review evidence after reload and configured-database
  process restart.
- Exact retries return the same immutable report without depending on process-local recommendation
  memory.
- New report generation still requires current, unexpired, exact-scope recommendation evidence.
- PostgreSQL constraints surface cross-process version races as conflicts rather than overwrites.
- Development remains usable without an external database, but in-memory artifacts are intentionally
  non-durable.

## Validation

- Repository round-trip, idempotency, conflict, scope, expiry, digest and no-authority tests
- API no-store, permission and attributable recovery audit tests
- Restart reconstruction tests for report reuse and ITSM review source revalidation
- Frontend URL recovery tests and live reload/restart validation
- Complete backend/frontend gates, one Alembic head and production build
