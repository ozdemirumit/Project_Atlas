# ADR-109: Connector Upgrade Change-Context Draft

## Status

Accepted - 2026-08-12

## Context

ADR-108 correctly keeps ITSM change, maintenance-window and audit-readiness evidence blocked. Atlas
needs a bounded way to prepare the exact connector upgrade context before integrating an external
ITSM authority. The existing platform change-review module is bound to Atlas platform release and
rollback-simulation evidence; reusing it for connector package lineage would create false binding.

## Decision

Atlas will create an immutable connector-upgrade change-context draft bound to one exact current
handoff-readiness assessment.

- Only the independent verifier who owns the latest current revalidation may create the draft.
- The request binds the exact readiness digest, a proposed future window, bounded justification,
  idempotency key and explicit no-authority acknowledgement.
- The service regenerates and rechecks current approval, revalidation, policy and plan evidence
  before accepting the draft.
- Proposed windows begin at least 15 minutes in the future, no more than 90 days ahead and last from
  15 minutes through four hours.
- The append-only record contains a safe ITSM title and digest but no external ticket identifier,
  endpoint, credential, secret or dispatch token.
- PostgreSQL persistence uses a dedicated table and actor-idempotency constraint. Create and latest
  read endpoints are no-store and audit recorded.

## Authority Boundary

The record is an internal draft only. `itsm_dispatched`, `window_approved`, `handoff_ready`, handoff
artifact issuance, approval consumption, execution authorization and infrastructure mutation remain
false. Target contact, package rebinding and connector configuration mutation also remain false.
Creating a draft does not satisfy the ITSM or maintenance-window readiness blockers. A draft is
readable as current only while its exact latest revalidation remains current and unexpired.

An external authoritative ITSM adapter, reconciliation contract and approval/window evidence model
require a separate accepted decision.

## User Experience

The handoff panel allows the eligible verifier to enter a proposed start, end and justification,
then explicitly acknowledge the no-authority boundary. A restored draft displays "Not dispatched.
Window not approved. Handoff remains blocked." No install, apply, execute or handoff control is
introduced.

## Verification

- Domain and service tests cover exact binding, verifier ownership, window bounds, idempotency and
  all false authority flags.
- Repository and migration tests cover durable mapping and one linear migration head.
- API tests cover CSRF, permissions, no-store response and safe projection.
- Frontend tests cover draft creation/restoration and absence of consequential controls.
- Full regression, production build and live desktop/mobile validation are required.
