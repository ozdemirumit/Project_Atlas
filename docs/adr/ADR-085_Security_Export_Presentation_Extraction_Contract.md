# ADR-085: Security Export Presentation Extraction Contract

- Status: Accepted
- Date: 2026-08-10
- Owners: Product Owner, Solution Architecture, User Experience, Security Architecture,
  Infrastructure Operations
- Governing documents: ATLAS-001, ATLAS-002, ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013,
  ATLAS-016, ATLAS-020, ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-034,
  ATLAS-035, ATLAS-047, ATLAS-050, ATLAS-052, ATLAS-055, ATLAS-056, ADR-079, ADR-080,
  ADR-081, ADR-082, ADR-083, ADR-084

## Context

IMP-128 extracted scheduled health checks and reduced the transitional operational chunk to
830.62 KB. Security Export remains a contiguous presentation block in the operational parent. It
shows one configured Syslog/SIEM destination, TLS and certificate health, bounded delivery counts,
an RFC 5424 preview, transport handoff evidence and an explicitly unconfirmed SIEM-ingestion state.

The panel may request one authorized test event. It does not own destination configuration, TLS
trust, credentials, event mapping, retry policy, audit, external collector authority or SIEM
ingestion confirmation.

## Decision

Atlas will extract Security Export presentation into a dedicated static lazy Health feature. The
parent supplies the authorized overview, explicit query and test-request state, and one bounded
test-event callback.

### Presentation Ownership

- `SecurityExportWorkspace` owns destination, transport, certificate, queue, delivery, RFC 5424
  preview, handoff result, limitations and safety-notice presentation.
- The feature owns no API client, React Query cache, identity, RBAC, credential, TLS trust, mapping,
  retry, audit, collector or external-system authority.
- A test-event request delegates through one parent callback. The feature cannot construct or alter
  an event payload, destination, transport or retry policy.

### Loading And Failure Contract

- The feature loads through one static local import and mounts only while Health is active.
- Loading, unavailable and incomplete-overview states are explicit and fail closed.
- Connector routes must not download, evaluate or mount the feature.
- Test failure does not imply destination failure; success confirms only a transport handoff.

### Security And Evidence Contract

- The server and existing parent mutation remain authoritative for authentication, tenant scope,
  CSRF, destination eligibility, TLS verification, event normalization, classification, audit,
  queueing and delivery.
- Collector handoff does not confirm SIEM parsing, indexing, alerting or retention.
- Preview content is server-produced bounded evidence. Presentation grants no configuration,
  infrastructure-change or external-system mutation authority.

### Verification

- Focused tests cover loading, unavailable, incomplete and populated states, the bounded callback,
  pending/error/success states, handoff limitations and no-authority language.
- Existing application tests preserve query invalidation and test-event API behavior.
- ESLint, TypeScript, full Vitest and production build pass with a separate feature chunk.
- Live desktop/mobile checks cover test-event presentation, overflow, route isolation and final
  application logs.

## Consequences

### Positive

- Security delivery evidence gains one independently testable and loadable presentation owner.
- Transport handoff and SIEM-ingestion uncertainty remain visually explicit.
- The operational module shrinks without moving sensitive state or authority.

### Costs

- Query and mutation ownership remain in the transitional parent.
- Release/bootstrap presentation remains the next large operational ownership decision.

## Rejected Alternatives

### Move Query And Mutation State Into The Feature

Rejected because cache invalidation, identity scope, CSRF and audited external delivery are a larger
authority boundary than presentation extraction requires.

### Treat Test Delivery As SIEM Confirmation

Rejected because a collector transport handoff does not prove downstream parsing, indexing,
alerting or retention.

### Combine Security Export With Release And Bootstrap

Rejected because security-event delivery and deployment bootstrap have separate evidence, identity,
approval and operational-risk contracts.

## Follow-Up

Assess release/bootstrap presentation ownership as a separate multi-step authority decision, then
continue operational workspace visual consolidation.

