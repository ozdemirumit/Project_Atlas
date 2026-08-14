# ADR-142: Canonical Workflow Dispatch Event Envelope Without Transport Authority

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-14 |
| Owners | Workflow Platform, Security Architecture, Event Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-025, ATLAS-032, ADR-136, ADR-137, ADR-138, ADR-139, ADR-140, ADR-141 |

## Context

Atlas now persists one provider-neutral pending-publication outbox entry and coordinates one
publisher through an independently fenced, bounded lease. The logical event that a future transport
adapter would receive is still implicit in workflow lineage. Transport selection before a stable
canonical event contract would couple domain meaning to a broker and make retries, audit and schema
evolution ambiguous.

## Decision

Atlas will prepare one immutable canonical `WorkflowStepDispatchRequested` event envelope for each
exact pending workflow outbox entry. A dedicated service identity authenticated for
`audience.workflow-outbox-publisher` may prepare the envelope only while holding the current active
publication lease for that entry. Browser sessions and ordinary API tokens cannot prepare it.

The canonical envelope records a deterministic event identifier, stable event type and version,
UTC occurrence and recording times, producer and producer version, subject type and identifier,
organization and environment, correlation and causation identifiers, workflow reference, data
classification, schema URI, minimized structured payload, empty namespaced extensions and a
canonical envelope digest. The minimized payload contains exact workflow plan, run, step-run,
attempt, target, scope, dispatch-intent and outbox references and digests. It contains no credential
or unrestricted secret material.

Envelope preparation evidence additionally binds the exact source orchestration lease, exact
publication lease and both fencing tokens, publisher subject, preparation time, lifecycle state and
an all-false authority object. One outbox entry can have only one envelope. Preparation is
idempotent for the same request and rejects changed requests, competing identities, stale fences,
expired or released leases, changed lineage, cancelled plans or non-pending outbox state.

Every preparation locks and revalidates the planned plan, exact pending outbox entry, current active
source orchestration lease and current active publication lease. The envelope and immutable
idempotency claim are written atomically. Production persistence never falls back to memory.

This boundary has no broker, endpoint, queue, topic, partition, routing key, transport credential,
wire payload, serialization format, publication attempt, delivery acknowledgement, worker
reservation or execution result. It does not send or deliver a message, mutate workflow state,
dispatch a worker, invoke a connector or model, create an approval, mutate ITSM, execute a runbook
or change infrastructure. Publication, delivery, dispatch and execution authority remain
structurally false.

Humans may inspect envelope evidence through the existing workflow read permission and normal
username/password browser session. The UI exposes no envelope-preparation or operational action and
requires no additional login or MFA ceremony.

## Consequences

- Event meaning and schema identity become durable before any transport is selected.
- The same logical event identifier and envelope digest can survive later publication retries.
- A prepared envelope means only that canonical provider-neutral data exists; it does not mean that
  bytes were serialized, a broker accepted a message, delivery occurred or a worker was dispatched.
- Transport profiles, routing, serialization, publication attempts, receipts, retries, quarantine,
  worker dispatch, running states, results, timers and all external execution remain deferred.

## Validation

- Domain and application tests cover canonical stability, exact lineage, minimized payload,
  idempotent replay, changed-request conflict, stale fences, lease expiry/release and zero authority.
- PostgreSQL tests cover complete locked revalidation and atomic envelope/idempotency persistence.
- API tests prove workload-token-only preparation and username/password browser-session read access.
- Web tests prove exact envelope/lineage validation, empty and error states, no mutation controls and
  no second-login or MFA text.
- Full backend/frontend suites, Alembic single-head validation and live browser inspection are
  required before merge.
