# ADR-134: Versioned Workflow Definition and Non-Executable Run Plan

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-13 |
| Owners | Workflow Platform, Security Architecture, Operations Architecture |
| Related | ATLAS-002 FR-014, ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-025, ATLAS-032, ATLAS-037 |

## Context

Atlas has durable domain-specific processes but no general workflow state authority. FR-014 requires
versioned workflows whose state is deterministic and never delegated to an LLM. Implementing worker
dispatch, retries and compensation before establishing a validated definition and identity model
would create unsafe and unverifiable execution semantics.

## Decision

Atlas will first implement a code-owned registry of immutable, versioned C0-C2 workflow definitions
and durable non-executable run plans. A definition contains stable identity, purpose, ordered typed
steps, dependencies, bounded timeouts, capability class and input schema version. Validation rejects
cycles, duplicate identifiers, missing dependencies, unsupported step kinds and C3-C5 authority.

An authorized human may create an idempotent run plan bound to one exact definition version and
digest, organization/environment/site, supported target and canonical input digest. The plan is
state `planned`; every step is `not_started`. It records no worker lease, attempt, signal, approval,
connector call, ITSM mutation, runbook execution or infrastructure change. All authority flags are
structurally false.

Production persistence is PostgreSQL and must fail closed when unavailable. Explicit development
mode may use a labeled non-durable memory repository. Audit persistence is required before a plan
is returned. API responses use no-store and tenant-scoped authorization.

The first registry entries model existing MVP analytical flows such as evidence-grounded query,
scheduled health assessment and report generation, but registering a definition does not claim that
its future execution adapters are implemented.

## Consequences

- Atlas gains a stable workflow contract and user-visible planning surface without increasing
  operational authority.
- Worker queues, leases, timers, retries, cancellation, approval waits and compensation can be
  added against canonical plan identity in later ADRs.
- Definitions remain code-reviewed; arbitrary declarative production workflows are excluded.
- A plan is evidence of intent and validation only, never evidence that work ran or succeeded.

## Validation

- Domain validation covers graph integrity, capability and authority rejection.
- Service/API tests cover authorization, scope, idempotency, conflict, audit and persistence mode.
- PostgreSQL mapping and migration tests preserve exact canonical payloads.
- Frontend tests cover registry, plan creation and explicit non-execution presentation.
- Full quality gates and live username/password validation pass before delivery.
