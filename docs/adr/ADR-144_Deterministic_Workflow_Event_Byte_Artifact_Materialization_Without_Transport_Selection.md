# ADR-144: Deterministic Workflow Event Byte Artifact Materialization Without Transport Selection

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-14 |
| Owners | Workflow Platform, Security Architecture, Event Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-136, ADR-137, ADR-138, ADR-139, ADR-140, ADR-141, ADR-142, ADR-143 |

## Context

Atlas now records immutable policy admission for the exact prepared
`WorkflowStepDispatchRequested` envelope under the current fenced publication lease. Admission
proves that the event meaning, schema, classification, canonical representation and size satisfy a
code-owned policy, but no byte artifact exists. Combining byte creation with provider or route
selection would make deterministic content integrity depend on transport configuration.

## Decision

Atlas will materialize one immutable provider-neutral canonical byte artifact for each exact
admitted workflow event. A dedicated service identity authenticated for
`audience.workflow-outbox-publisher` may request materialization only while holding the same current
active publication lease and source orchestration lease bound by the envelope and admission.
Browser sessions and ordinary API tokens cannot create byte artifacts.

The materializer uses the admitted policy's exact `canonical-json` representation and UTF-8
encoding. It serializes the prepared envelope's canonical value deterministically, verifies the
resulting byte count against both the admission and policy maximum, computes a SHA-256 content
digest and persists the bytes with minimized immutable lineage. No alternate serializer, content
transformation, compression or encryption profile is selected in this boundary.

The artifact binds the exact event, admission, policy, outbox and workflow lineage,
organization/environment/site/target scope, publisher subject, source orchestration lease,
publication lease and both fencing tokens. Its state is `materialized` and all publication,
delivery, dispatch and execution authority fields remain false. Changed, stale, competing,
tampered or non-deterministic evidence fails closed and creates no partial record.

Every materialization locks and revalidates the planned plan, pending outbox, current source lease,
current publication lease, prepared event envelope and admitted decision. The artifact and its
immutable idempotency claim are persisted atomically. Production persistence never falls back to
memory.

This boundary records no provider, broker, endpoint, queue, topic, partition, routing key,
transport credential, provider message, publication attempt, retry schedule, receipt, delivery
acknowledgement, worker reservation or execution result. It makes no network call, mutates no
workflow state and grants no authority to publish or deliver the bytes.

Humans may inspect minimized artifact metadata through the existing workflow read permission and
normal username/password session. Raw canonical bytes and payload content are not returned to the
browser. The UI exposes no materialize, serialize, download, publish, deliver, dispatch or execute
action and requires no additional login or MFA ceremony.

## Consequences

- Event bytes, byte count and SHA-256 integrity become deterministic durable evidence before any
  transport configuration exists.
- Provider adapters can later consume an exact immutable artifact rather than reserializing event
  meaning independently.
- Materialized means bytes exist in Atlas storage only; it does not mean a provider, route or
  message exists or that publication is authorized.
- Provider profiles, route selection, transport credentials, publication attempts, receipts,
  retries, quarantine, worker dispatch and all external execution remain deferred.

## Validation

- Domain and application tests cover deterministic bytes and digest, exact lineage, idempotent
  replay, changed-request conflict, byte-count mismatch, stale leases, tampered evidence, audit
  failure and zero authority.
- PostgreSQL tests cover locked revalidation and atomic artifact/idempotency persistence using a
  binary column that is never exposed by the read API.
- API tests prove workload-token-only materialization and username/password read access to minimized
  metadata.
- Web tests prove exact metadata, empty and error states, no raw bytes or payload, no mutation
  controls and no second-login or MFA text.
- Full backend/frontend suites, Alembic single-head validation and live browser inspection are
  required before merge.
