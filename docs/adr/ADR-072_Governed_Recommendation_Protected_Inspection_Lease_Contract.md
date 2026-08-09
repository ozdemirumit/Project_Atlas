# ADR-072: Governed Recommendation Protected Inspection Lease Contract

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-10 |
| Owners | Product Owner, Architecture Owner, Security Architecture, Identity Governance, Governance and Workflow Owner |
| Decision Scope | Assignee-bound, short-lived browser access to one recommendation review track |
| Related Documents | ATLAS-003, ATLAS-014, ATLAS-023, ATLAS-024, ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-037, ATLAS-043, ATLAS-044, ATLAS-046, ATLAS-047, ATLAS-050, ATLAS-052, ATLAS-053, ATLAS-056, ADR-045, ADR-063 through ADR-071 |

## Context

ADR-071 assigns distinct accountable humans to the technical and service-impact tracks of one
exact recommendation review request. Assignment does not open protected content and does not
create a reusable access credential.

An assigned reviewer needs a narrow way to begin inspecting only their own track. Atlas must
prove the current enterprise identity matches the salted assignment subject, preserve browser and
source lineage, and avoid returning a bearer secret through JSON, logs or ordinary persistence.

## Decision

Atlas will add one governed recommendation protected-inspection lease service. It atomically
claims one exact assignment and track for the exact assigned reviewer, obtains an opaque secret
from a trusted lease broker, stores only its digest, and delivers the secret in a path-scoped
`HttpOnly`, `SameSite=Strict` cookie. The lease is browser-bound, non-transferable,
non-refreshable and valid for no more than ten minutes.

Success records only that protected inspection was opened. It returns no protected content and
records no finding, judgement, correction, approval, workflow, ITSM state, execution authority,
deployment authority or infrastructure mutation.

### Caller Contract

The caller may provide only exact assignment-set, assignment, track and policy bindings; the
unchanged review purpose; three no-authority acknowledgements; and browser-bound session,
idempotency and correlation identifiers.

The caller cannot provide or override reviewer identity, subject digest, username, role, group,
queue, eligibility, lease duration, cookie value, protected content, evidence, finding, decision,
rationale, correction, approval, workflow, ITSM, target, capability, command or mutation fields.

### Authorization And Assignee Binding

Creation requires a current enterprise human with hardware-backed MFA, recent authentication, the
exact tenant, environment and browser binding, and a dedicated default-deny C2 permission. Reading
minimized lease state requires a dedicated C1 permission.

The trusted identity boundary derives the current actor digest with the exact subject-digest
profile bound to the assignment policy. It must equal the selected track's assigned reviewer
digest. The technical assignee cannot claim the service-impact track and vice versa. Requesters,
upstream actors, administrators and other reviewers receive no override.

Production has no synthetic identity, assignment, policy or lease fallback. Any unavailable,
stale or ambiguous identity evidence fails closed.

### Source And Policy Contract

The source must be one exact, unexpired and integrity-valid ADR-071 record with
`state=reviewers_assigned`, two distinct assigned tracks, unchanged opaque assignment IDs, queues
and subject digests, complete protected lineage, and all inspection or later lifecycle flags false.

The signed inspection policy defines the accepted source/output schemas, eligible tracks, maximum
TTL, recent-authentication window, browser and cookie bindings, subject-digest profile, trusted
identity and broker IDs, retention and cleanup proofs. The effective TTL is never greater than ten
minutes and cannot be supplied by the caller.

### Atomic One-Way Claim And Replay

After authorization, source verification, assignee proof and intent audit, Atlas creates one
immutable claim uniquely constrained by assignment set and track. Claim persistence is the point
of no return.

Exact idempotent replay reauthorizes the actor, verifies the current source, policy, browser,
assignee and stored secret digest, and reissues no secret. Changed input conflicts. An expired,
revoked or uncertain lease cannot be refreshed; a later contract must govern any new inspection
session.

### Trusted Lease Boundary

The broker receives only immutable identifiers, digests, selected track, browser binding, policy
limits and timestamps. It never receives recommendation content, evidence, credentials, prompts,
model output or infrastructure coordinates.

The broker creates a high-entropy opaque secret, returns it once with signed minimized proof, and
erases transient plaintext buffers. The application stores only a keyed digest. Development may
use a deterministic no-network broker; it must not use a model, open content or perform an
operation.

The HTTP boundary places the secret only in a cookie scoped to the exact protected-inspection
route. The cookie is `HttpOnly`, `SameSite=Strict`, has the lease maximum age and is `Secure`
outside local development. JSON, logs, audit events, traces, URLs and frontend state never contain
the secret.

### Lease Record And Response

The immutable minimized record contains lease, assignment-set, assignment and recommendation
identifiers; selected track; signed policy and opaque broker identifiers; subject, browser,
source, authorization, secret, receipt and cleanup digests; tenant, environment, classification,
purpose, issue/expiry timestamps; and safe lifecycle flags.

Success sets `content_inspection_opened=true`, `content_disclosed=false` and
`protected_content_bytes_returned=0`. Human-review completion, decision, correction, approval,
workflow, ITSM, execution, deployment and infrastructure mutation remain false.

### Failure And Audit

Authorization denial occurs before source rehydration or broker access. Intent audit precedes the
claim; claim audit follows claim persistence; completion audit precedes lease persistence; every
replay emits a separate read audit.

Policy, source, identity, assignee, browser, recent-authentication, broker, cookie, audit,
persistence, cleanup, integrity or replay uncertainty fails closed. Failure returns no secret,
partial lease or protected content.

## Consequences

- Each reviewer can open only the exact track assigned to that identity.
- Browser scripts and JSON clients cannot read the lease secret.
- Replay and expiry cannot silently mint or refresh access.
- Production requires trusted identity-digest and lease-broker integrations.
- Actual content retrieval and reviewer findings remain separate future contracts.

## Rejected Alternatives

- Caller-selected identity or track: rejected because it bypasses assignment separation.
- Bearer token in JSON or browser storage: rejected because scripts, logs and clients can leak it.
- One shared lease for both tracks: rejected because it merges independent accountabilities.
- Opening content while creating the lease: rejected because disclosure needs its own controls.
- Renewable leases: rejected because stale authorization would silently extend access.

## Follow-Up

Later independent contracts cover reviewer inbox discovery, protected content retrieval, immutable
track findings, review decisions and correction, recommendation approval, workflow or ITSM
handoff, and any human-approved automation.
