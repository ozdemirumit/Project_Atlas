# ADR-045: Governed Operational Knowledge Protected Inspection Lease Contract

- Status: Accepted
- Date: 2026-08-06
- Owners: Product Owner, Solution Architecture, Security Architecture, Knowledge Management,
  Identity Governance, Data Governance
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-013, ATLAS-014, ATLAS-015,
  ATLAS-016, ATLAS-020, ATLAS-021, ATLAS-023, ATLAS-025, ATLAS-027, ATLAS-030, ATLAS-031,
  ATLAS-032, ATLAS-033, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-053, ATLAS-054, ATLAS-055,
  ATLAS-056, ADR-009 through ADR-044

## Context

ADR-044 assigns distinct domain and security reviewers to one immutable operational knowledge
review request. Assignment exposes only opaque assignment IDs and salted subject digests. It does
not open content, create a reusable session, or grant review-decision authority.

An assigned reviewer needs a narrowly bounded way to begin protected inspection. Atlas must prove
that the current hardware-MFA human is the exact assignee for the selected track without exposing
raw reviewer identity, draft content, storage coordinates, or bearer material in API responses.

## Decision

Atlas will implement a dedicated protected-inspection lease service. It atomically claims one
assignment and one assigned track for the exact current reviewer, instructs a trusted lease broker
to create a short-lived browser-bound inspection channel, validates a signed minimized receipt,
and records immutable lease metadata without returning content or a reusable bearer token.

### Caller Contract

The caller may provide only:

- exact reviewer-assignment set ID and canonical digest;
- one exact assigned track code, `review-track.domain` or `review-track.security`;
- exact signed inspection-lease policy ID and digest;
- a bounded inspection purpose;
- acknowledgement that lease issuance returns no content and records no decision;
- idempotency and correlation identifiers.

The caller cannot provide or override reviewer identity, subject digest, assignment ID, queue,
directory query, draft/evidence content, excerpt, content range, storage location, decryption key,
lease secret, cookie attributes, duration, finding, decision, correction, approval, publication,
parser, chunker, embedding model, index, retrieval, model context, target, credential, secret,
session, command, schedule, workflow, execution, deployment, or mutation fields.

### Authorization And Lineage

Before claim creation the service revalidates:

- complete immutable connector, evidence, draft, review-request, and reviewer-assignment lineage;
- exact assignment-set ID, digest, schema, state, tenant, manifest, routing, governance, artifact,
  track, queue, opaque assignment IDs, salted reviewer digests, expiry, policy, immutable-write,
  and cleanup bindings;
- exact signed inspection policy, signer, schema, scope, identity-digest salt, lease broker,
  receipt schema, authentication freshness, TTL, browser-binding, and concurrency limits;
- a current enterprise human identity with hardware-backed MFA, exact tenant scope, dedicated C2
  protected-inspection-lease permission, assignment-read permission, and recent authentication;
- the salted current subject digest exactly matches the selected track's assigned reviewer digest;
- the assignment and selected track are current, no prior active or claimed lease exists for that
  track and assignment, and no later decision, correction, approval, publication, retrieval,
  workflow, execution, deployment, or mutation authority exists.

The domain reviewer cannot request the security track and the security reviewer cannot request the
domain track. The assignment requester, curator, policy signer, adapter attestor, approver, or
publisher cannot gain access unless independently assigned to the exact selected track.

### Atomic One-Way Lease Claim

After required intent audit succeeds and before lease creation, the repository creates an immutable
claim with a unique constraint on assignment-set ID plus track code. Claim creation is the point of
no return.

An existing claim returns the same completed lease only when subject digest, idempotency key,
request binding, browser-session binding, and completion evidence match. Otherwise it fails as
already claimed. A claim is not released after cancellation, timeout, broker failure, audit
failure, partial write, or uncertain outcome. Atlas does not retry automatically.

### Trusted Lease Broker Boundary

The application sends only trusted lineage IDs and digests, selected track and opaque assignment
ID, salted current-subject digest, browser-session binding digest, signed policy references, limits,
and lease ID. It never sends content, raw subject identity, credentials, keys, or target details.

The broker must:

1. verify the instruction and exact ADR-044 assignment and review-manifest binding;
2. verify the selected opaque assignment ID and salted current subject digest match;
3. verify assignment expiry, authentication freshness, tenant, track, and concurrency limits;
4. create one random, non-derivable, track-specific lease secret with a maximum ten-minute TTL;
5. store only a keyed secret digest and encrypted browser-session binding;
6. bind the channel to the exact draft version, manifest, actor digest, track, and browser session;
7. prohibit transfer, delegation, refresh, extension, cross-track use, and concurrent reuse;
8. compute lease, binding, assignment, policy, and cleanup digests;
9. close broker channels and erase plaintext lease-secret buffers in every outcome;
10. return a signed receipt plus the one-time secret only to the API cookie boundary.

Production fails closed when no trusted lease broker is configured. Development may use a
deterministic metadata broker but must still generate a random per-attempt secret and cannot read
draft content, contact a directory, model, vector store, workflow, deployment system, target, or
infrastructure endpoint.

### Browser Secret Boundary

The API writes the one-time lease secret only to a dedicated `HttpOnly`, `SameSite=Strict`,
path-scoped cookie with policy TTL and `Secure` outside local development. The cookie value never
appears in JSON, HTML, JavaScript state, URL, log, audit, exception, trace, or persistent record.

Mutation CSRF remains required for lease issuance. Later protected content reads require the normal
browser session, exact subject and tenant, the lease cookie, current lease state, exact track, and
separate read audit. Logout, session revocation, subject disablement, assignment expiry, lease
expiry, or explicit lease revocation makes the cookie unusable.

### Lease Record

A successful immutable record uses state `operational_knowledge_protected_inspection_leased` and
contains:

- assignment, review request, draft, knowledge item/version, evidence, invocation, connector,
  instance, capability, manifest, and governance lineage IDs and digests;
- lease ID, selected track, selected opaque assignment ID, salted lease-holder subject digest,
  browser binding digest, lease-secret digest, lease/binding/assignment/policy/cleanup digests,
  issued timestamp, expiry, policy ID/digest/version, and opaque broker identity;
- inherited classification, access, retention, and encryption labels;
- request purpose, cleanup proof, canonical digest, and safe lifecycle flags.

It records `review_requested=true`, `reviewer_assigned=true`, and
`content_inspection_opened=true`, meaning a bounded channel exists. It also records
`content_disclosed=false` and `content_bytes_read=0`. Domain/security decisions, correction,
approval, publication, chunks, embeddings, retrieval, model context, graph update, scheduling,
workflow, execution, deployment, and infrastructure mutation remain false.

The JSON API may expose safe lineage, selected track, opaque assignment and lease IDs, salted
holder digest, lifecycle state, expiry, policy references, safe digests, and zero-disclosure flags.
It never exposes content, raw identity, names, usernames, email, groups, directory data, cookie or
secret values, secret digests usable as credentials, browser identifiers, storage coordinates,
keys, request fingerprints, or idempotency material.

### Lease Is Not Content Or Decision

Lease issuance establishes only a short-lived authorization boundary. It does not return draft
content, mark either review complete, create a finding, accept or reject knowledge, authorize
correction, publish to retrieval, call a model, continue a workflow, or authorize an operational
action. Protected content presentation and each review decision require separate contracts.

### Failure And Audit

Failures before claim creation perform no broker write and set no cookie. Failures after claim
creation remain claimed, set no usable cookie unless a fully validated committed lease is proven,
and emit safe failed or uncertain outcomes. No completion record is created unless receipt
identity, lineage, assignment, subject, track, policy, expiry, session binding, immutable-write, and
cleanup evidence validate.

Required intent audit precedes the claim. Claim audit follows successful atomic claim creation.
Completion audit succeeds before completion persistence and cookie delivery. Enterprise audit
identifies the accountable authenticated subject, while public records expose only salted subject
digests. Audit never contains content or lease secrets.

### Persistence And API

Claims and lease records are immutable, deterministic, concurrency-safe, and equivalent in memory
and PostgreSQL. The API uses browser session, mutation CSRF, strict schemas, no-store, dedicated
default-deny RBAC, C2 classification, hardware MFA, authentication freshness, exact tenant scope,
safe errors, minimized responses, and narrowly scoped cookie handling.

## Consequences

### Positive

- Only the exact assigned reviewer can open the selected track's inspection boundary.
- Raw reviewer identity and lease secrets stay out of normal application and browser data models.
- A stolen JSON response cannot be reused as an inspection credential.
- Uncertain broker outcomes cannot create duplicate or cross-track access.

### Costs

- Production requires a trusted lease broker, session binding, and revocation integration.
- A lease must expire instead of being silently refreshed or delegated.
- Content presentation needs a separate audited endpoint and lifecycle contract.

## Rejected Alternatives

### Return A Bearer Token In JSON

Rejected because browser JavaScript, logs, traces, extensions, and copied responses could expose it.

### Let Any Operator Inspect Assigned Work

Rejected because queue visibility is not reviewer assignment or need-to-know authorization.

### Use One Lease For Both Tracks

Rejected because domain and security inspection have separate accountable boundaries.

### Return Content With Lease Creation

Rejected because authorization establishment and protected content disclosure need independent
audit and failure boundaries.

## Follow-Up

Later independent lifecycle contracts cover protected content presentation and redaction,
track-specific findings and decisions, correction and resubmission, approval or rejection,
chunking and embedding, retrieval-index validation and publication, suspension, supersession,
retention, and deletion execution.
