# ADR-159: Bounded Single-Use Workflow Protected Transport Target-Context Access Authorization Lease Without Artifact Opening or Runtime Authority

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-15 |
| Owners | Workflow Architecture, Deployment Architecture, Security Architecture, Identity Architecture |
| Related | ATLAS-003, ATLAS-016, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-032, ADR-150, ADR-152, ADR-155, ADR-157, ADR-158 |

## Context

ADR-158 immutably proves that one successful protected endpoint materialization result and one
successful protected credential materialization result belong to the same exact workflow physical
route and credential-assignment lineage. That binding is historical evidence only: it opens neither
artifact, makes no current protected-store claim and grants no access or runtime authority.

Atlas now needs the next smallest authorization boundary. One exact platform workload must be able
to receive a short-lived authorization to access the already bound protected artifacts in a later,
separate consumption step. Issuance must prove that the target context remains live, current and
internally consistent without exposing either artifact or performing any runtime operation.

A lease based only on the historical binding would be unsafe. The route may have been superseded,
the credential assignment may have rotated or been revoked, the workflow outbox entry may have
been cancelled, or either protected artifact may have expired, been revoked or been destroyed.
Conversely, coupling access authorization to an active orchestration or publication lease would
mix independent ownership and transport concerns into a capability that grants no orchestration or
publication authority.

## Decision

Atlas will issue one immutable
`WorkflowProtectedTransportTargetContextAccessAuthorizationLease` for one exact target-context
binding and one exact dedicated accessor workload. The lease authorizes only a future protected-
artifact access attempt. It does not open an artifact and is not a bearer credential, runtime
instruction or operational capability.

Only the exact service subject
`service.workflow-protected-transport-context-accessor` authenticated for the exact audience
`audience.workflow-protected-transport-context-accessor` may request issuance for itself. Human
sessions, personal access tokens and every other workload fail closed.

The request contains only:

- target-context binding ID and canonical digest;
- the code-owned access-authorization policy ID and version; and
- idempotency metadata.

The caller cannot supply a policy digest, TTL, accessor subject, artifact ID or digest, protected-
store coordinate, endpoint, credential, route, assignment, provider, network, readiness,
publication, delivery, runtime, dispatch, execution or mutation field. Atlas derives the policy
digest, exact subject, bounded time and all authoritative evidence from trusted server-side state.

### Trusted Status Attestations

Before opening a database transaction, Atlas obtains one fresh, independently signed, metadata-
only status attestation from each trusted protected store: one for the endpoint artifact and one
for the credential artifact. No external protected-store or network call may occur while a database
transaction is open.

Each attestation is bound to a server-created nonce and canonically commits to the trusted
attestor, exact materialization result ID and digest, exact target-context binding commitment,
artifact kind, observed time, validity deadline, and usable, non-revoked and non-destroyed status.
It contains no artifact contents, bearer token, secret, endpoint coordinate, protected-store
locator or provider payload. An unavailable, unsigned, expired, malformed, mismatched or negative
attestation fails closed.

The attestations are untrusted input until verified. Inside the durable transaction Atlas performs
only offline signature, canonical-integrity, nonce, identity, lineage, state and deadline
validation against the already captured attestation bytes and trusted key material. A later
consumer must obtain and validate new attestations; issuance does not eliminate the time-of-check
to time-of-use boundary.

### Atomic Currentness And Liveness Proof

One durable PostgreSQL transaction uses a fixed lock and fencing order and revalidates:

1. the exact immutable target-context binding and both successful materialization results;
2. the pending workflow outbox entry and cancellation/liveness state bound to that lineage;
3. the authoritative current route-selection head and route fence for the exact physical route;
4. the authoritative current credential-assignment head and assignment-scoped advisory fence;
5. the two pre-fetched protected-store attestations through offline canonical and cryptographic
   validation;
6. any prior access-authorization lease for the binding; and
7. any existing idempotency claim for the exact scoped request.

The binding, materialization receipts, outbox, route head, credential-assignment head,
attestations, scope, subject and policy must agree exactly. Route supersession, credential
rotation, deactivation, expiry or revocation, cancellation, fence drift, ambiguous heads,
materialization uncertainty, artifact expiry, revocation or destruction, or any canonical-
integrity mismatch fails closed.

An active orchestration lease and an active publication lease are not dependencies of this
authorization. They grant and fence different responsibilities. Their ownership, expiry and
fencing values are neither accepted from the caller nor copied into this lease. Publication-
specific or orchestration-specific consumers must independently enforce their own current lease
and fence when their separate boundary is reached.

Required intent and commit-authorization audit precede persistence. After those audit records are
durable, PostgreSQL reads `clock_timestamp()` again and repeats all database-resident currentness,
liveness, canonical-integrity and deadline checks before atomically inserting the lease and its
idempotency claim. The pre-fetched attestations must still be valid for the complete lease window
at this second database time.

### Lifetime, Single Use And Replay

The code-owned lease lifetime is exactly five seconds. Atlas issues a lease only when the complete
five-second interval fits within all applicable authoritative bounds, including the target-context
`joint_usable_until`, both materialization-result usable deadlines, both status-attestation
deadlines and credential-assignment expiry. Atlas never shortens the lease to fit a smaller
remaining window.

Each target-context binding may produce at most one lease. The lease is append-only, single-use,
non-renewable and non-transferable, and begins only in `authorized_unconsumed` state. Expiry does
not permit renewal or replacement from the same binding. A new authorization requires new
materialization evidence and a new target-context binding.

Exact replay under the same scope, accessor, request, policy and idempotency key returns the same
lease only while the lease and all current evidence remain valid. Replay reacquires fresh store
attestations before the transaction and repeats the complete validation. A changed request,
competing accessor, different idempotency key for the same binding, expired lease, route drift,
credential drift, cancelled outbox or stale attestation fails closed and cannot create a second
lease.

Completion audit follows commit. If completion audit fails, the committed lease remains
authoritative and cannot be duplicated. The result is outcome-uncertain until an exact valid
replay recovers the minimized record.

### Authority Contract

The lease contains exactly 17 explicit authority declarations. Only
`protected_artifact_access_authorized` is true. The following 16 declarations are exactly false:

- `endpoint_resolution_authorized`;
- `route_selection_authorized`;
- `route_binding_authorized`;
- `credential_selection_authorized`;
- `credential_assignment_binding_authorized`;
- `credential_access_authorized`;
- `credential_brokerage_authorized`;
- `credential_resolution_authorized`;
- `credential_delivery_authorized`;
- `network_access_authorized`;
- `readiness_probe_authorized`;
- `publication_authorized`;
- `delivery_authorized`;
- `dispatch_authorized`;
- `execution_authorized`; and
- `infrastructure_mutation_authorized`.

The one true value means only that the exact accessor may later request a separate, atomic,
irreversible consumption claim for the already bound protected artifacts. It does not authorize
artifact opening within this boundary and cannot be interpreted as credential delivery, endpoint
reveal, network use or runtime authority.

### Human Presentation

Authorized humans may inspect a minimized read-only inventory through the existing
username/password browser session. No MFA, second login or authorized-browser prompt is required.
Human API and UI responses expose only non-sensitive lease identity, scope, accessor identity,
state, issue and expiry times, single-use/non-renewable properties, minimized policy reference,
the 17-field authority declaration and a non-sensitive integrity reference.

They omit target-context commitments or digests, materialization and artifact IDs or digests,
protected-store attestations and locators, endpoint coordinates, credential metadata, provider or
broker fields, internal fences, request fingerprints, idempotency values and source or policy
digests. The UI provides no create, consume, access, reveal, copy, download, deliver, connect,
probe, publish, retry, dispatch, execute or mutate control.

## Consequences

- One exact workload can receive a narrowly bounded access authorization without ordinary
  application code opening either protected artifact.
- Route, credential-assignment, outbox and protected-store drift are checked at issuance rather
  than inferred from historical materialization success.
- External protected-store latency does not hold database locks or an open transaction.
- Five-second full-window issuance and one-lease-per-binding rules prevent silent renewal or
  weakened short leases.
- Orchestration and publication ownership remain independent and cannot accidentally enlarge the
  access lease's authority.
- A separate irreversible consumer remains necessary before any artifact can be opened.

## Deferred Scope

- Access-lease consumption and protected artifact opening or decryption
- Credential delivery, injection, reveal, copy, download or runtime handoff
- Endpoint reveal, DNS, TLS, socket, proxy or network establishment
- Readiness or health probes and transport-provider negotiation
- Provider SDK calls, publication attempts, acknowledgement, retry, quarantine or delivery
  receipts
- Worker dispatch, workflow state transition, workflow execution and infrastructure mutation
- Human- or AI-initiated lease issuance or artifact access

## Validation

- Domain and application tests cover the exact workload subject/audience, code-owned policy,
  five-second full window, single source use, exact replay, changed replay, competing accessor,
  all currentness and liveness conflicts, canonical integrity, expiry and the exact 17-field
  authority contract.
- Adapter tests prove that both status attestations are metadata-only, independently signed,
  nonce-bound and fetched before the transaction, with no protected-store call while database
  locks are held.
- PostgreSQL tests cover fixed lock/fence order, route and assignment current-head drift, outbox
  cancellation, atomic lease/idempotency insertion, concurrent callers, append-only enforcement,
  database-time expiry, precommit-audit rollback and no production memory fallback.
- API and UI tests prove exact workload-only issuance, default-deny minimized human reads,
  non-oracle errors, no sensitive fields or operational controls, and normal username/password
  access without MFA, second login or authorized-browser prompts.
- Full backend/frontend suites, Alembic single-head validation, real PostgreSQL CI, live browser
  inspection, exact-head PR CI, SHA-locked merge and independent main CI are required.
