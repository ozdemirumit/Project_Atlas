# ADR-145: Immutable Workflow Logical Publication Channel Binding Without Physical Transport Selection

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-14 |
| Owners | Workflow Platform, Security Architecture, Event Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-136, ADR-137, ADR-138, ADR-139, ADR-140, ADR-141, ADR-142, ADR-143, ADR-144 |

## Context

Atlas now stores one deterministic provider-neutral byte artifact for an admitted
`WorkflowStepDispatchRequested` event. The artifact proves exact content integrity but does not
state which logical event domain, delivery class, ordering boundary or retention class must carry
that content. Selecting a concrete broker, endpoint, topic or credential before those logical
requirements are immutable would couple domain meaning to deployment technology.

## Decision

Atlas will bind each exact workflow event byte artifact to one immutable code-owned logical
publication channel contract. The initial contract is `channel.workflow-dispatch.internal`
version `1.0`. It accepts only the exact `WorkflowStepDispatchRequested` version `1.0` schema with
`internal` classification and canonical JSON UTF-8 representation. It requires durable
at-least-once delivery, workflow-run ordering, workflow-operational retention and a maximum
65,536-byte artifact.

The binding stores the exact channel-contract digest, artifact/content digest, event, admission,
outbox and workflow lineage, organization/environment/site/target scope, publisher identity,
source orchestration lease, publication lease and both fencing tokens. Its ordering key is the
exact workflow run identifier already present in the authorized lineage. The binding state is
`bound`; it is immutable, idempotent and grants no publication, delivery, dispatch or execution
authority.

Only the dedicated publisher workload authenticated for
`audience.workflow-outbox-publisher` may create a binding, and only while the exact source and
publication leases remain current and active. The application and PostgreSQL adapter revalidate
and lock all authoritative lineage, including the exact byte artifact, before atomically writing
the binding and idempotency claim. Changed, stale, competing or tampered evidence fails closed.

This boundary does not select or store a transport provider, broker, cluster, endpoint, namespace,
topic, stream, queue, partition, routing key, credential, secret reference, encryption key,
provider message, publication attempt, retry schedule, receipt or delivery acknowledgement. It
makes no network call and does not mutate workflow, outbox, attempt or lease state. A later
deployment-owned physical transport profile may satisfy the logical contract without changing
event meaning.

Humans may inspect minimized binding metadata through the existing workflow read permission and
normal username/password session. The browser receives no raw bytes, payload content, physical
route or credential material and exposes no bind, select, publish, deliver, dispatch or execute
control. No additional login or MFA ceremony is required.

## Consequences

- Domain, classification, delivery, ordering and retention requirements become immutable before a
  physical transport implementation is chosen.
- Deployment-specific providers and routes can later prove compatibility with an exact logical
  contract instead of redefining event meaning.
- Bound means logical publication requirements exist in Atlas storage only; it does not mean a
  provider, route, message or publication attempt exists.
- Physical transport profiles, route compatibility admission, credentials, publication attempts,
  receipts, retries, quarantine, worker dispatch and all external execution remain deferred.

## Validation

- Domain and application tests cover the code-owned contract, exact lineage, deterministic
  ordering key, idempotent replay, changed-request conflict, stale leases, tampered evidence,
  artifact mismatch, audit failure and zero authority.
- PostgreSQL tests cover locked revalidation and atomic binding/idempotency persistence without
  foreign keys to replaceable current lease rows.
- API tests prove workload-token-only creation and username/password read access to minimized
  metadata.
- Web tests prove exact metadata, empty and error states, no physical transport fields or mutation
  controls and no second-login or MFA text.
- Full backend/frontend suites, Alembic single-head validation and live browser inspection are
  required before merge.
