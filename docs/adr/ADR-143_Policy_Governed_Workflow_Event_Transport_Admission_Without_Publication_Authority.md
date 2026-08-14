# ADR-143: Policy-Governed Workflow Event Transport Admission Without Publication Authority

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-14 |
| Owners | Workflow Platform, Security Architecture, Event Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-136, ADR-137, ADR-138, ADR-139, ADR-140, ADR-141, ADR-142 |

## Context

Atlas now prepares one immutable canonical `WorkflowStepDispatchRequested` envelope for the exact
pending workflow outbox entry while a dedicated publisher holds the current fenced publication
lease. The envelope is not yet proven eligible for any transport boundary. Selecting a broker or
creating wire bytes before policy admission would mix event meaning, security policy and provider
behavior and would make rejected or oversized events ambiguous.

## Decision

Atlas will record one immutable provider-neutral transport-admission decision for each exact
prepared workflow dispatch event envelope. A dedicated service identity authenticated for
`audience.workflow-outbox-publisher` may request admission only while holding the current active
publication lease for the same pending outbox entry. Browser sessions and ordinary API tokens
cannot create admission evidence.

Admission uses an immutable code-owned policy profile. Version 1 admits only the exact
`WorkflowStepDispatchRequested` event type, version `1.0`, internal classification, canonical schema
URI and `canonical-json` representation contract within a bounded maximum canonical byte count.
The policy records a stable identifier, version, digest, allowed event/schema/classification values,
representation name, UTF-8 encoding and maximum byte count. It contains no provider, credential or
network configuration.

The admission record binds the policy, exact event identifier and digest, exact outbox and workflow
lineage, organization/environment/site/target scope, canonical byte count, publisher subject,
source orchestration lease, publication lease and both fencing tokens. Its state is `admitted` and
all publication, delivery, dispatch and execution authority fields remain false. Unsupported,
oversized, stale, changed, competing or tampered evidence fails closed and creates no partial record.

Every admission locks and revalidates the planned plan, exact pending outbox entry, current source
orchestration lease, current publication lease and exact prepared event envelope. The admission and
its immutable idempotency claim are persisted atomically. Production persistence never falls back
to memory.

This boundary records no broker, endpoint, queue, topic, partition, routing key, transport
credential, wire payload, serialized artifact, publication attempt, retry schedule, receipt,
delivery acknowledgement, worker reservation or execution result. It does not send or deliver a
message, mutate workflow state, dispatch a worker, invoke a connector or model, create an approval,
mutate ITSM, execute a runbook or change infrastructure.

Humans may inspect admission evidence through the existing workflow read permission and normal
username/password browser session. The UI exposes no admission, serialization, publication,
delivery, dispatch or execution action and requires no additional login or MFA ceremony.

## Consequences

- Policy eligibility is durable and independently auditable before provider or route selection.
- Canonical size, schema and classification limits are enforced before wire artifacts or network
  calls exist.
- An admitted event means only that the exact canonical envelope satisfies the named policy; it
  does not mean bytes exist or any transport accepted a message.
- Provider profiles, route selection, wire serialization, publication attempts, receipts, retries,
  quarantine, worker dispatch and all external execution remain deferred.

## Validation

- Domain and application tests cover policy digest stability, exact lineage, size calculation,
  idempotent replay, changed-request conflict, unsupported and oversized events, stale fences,
  lease expiry/release, tampered evidence and zero authority.
- PostgreSQL tests cover complete locked revalidation and atomic admission/idempotency persistence.
- API tests prove workload-token-only admission and username/password browser-session read access.
- Web tests prove exact admission/policy evidence, empty and error states, no mutation controls and
  no second-login or MFA text.
- Full backend/frontend suites, Alembic single-head validation and live browser inspection are
  required before merge.
