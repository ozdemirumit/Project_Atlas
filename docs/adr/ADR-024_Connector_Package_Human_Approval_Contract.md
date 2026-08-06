# ADR-024: Connector Package Human Approval Contract

## Status

Accepted

## Context

ADR-023 produces a deterministic final-validation report for one exact connector package and marks
it either blocked or eligible for human approval. Eligibility is evidence, not a decision. Atlas
therefore needs a separate approval boundary where an accountable human can review that immutable
packet and record approve, reject, needs-evidence, or defer without changing the packet or gaining
execution authority.

This approval concerns only whether the exact validated package may proceed to later publisher,
signing, and registry governance. It does not approve an infrastructure operation, target,
credential, connector instance, installation, enablement, capability invocation, or deployment.

## Decision

Atlas will implement connector package approval as two immutable records:

1. an approval request that binds one eligible ADR-023 result to one signed approval-policy snapshot
   and one bounded review purpose; and
2. at most one terminal decision for the first profile, bound to the exact request version and
   canonical packet digest.

The request remains immutable after submission. State is a deterministic projection of the request,
decision, policy, and current time. Historical evidence is never rewritten.

## First Approval Profile

The first profile is a single-stage, quorum-one, package-governance review. It supports:

- `approve`: the exact package is approved only for the next separately governed lifecycle stage;
- `reject`: the exact package is rejected and cannot be promoted;
- `needs_evidence`: the packet is not approved and must return to evidence preparation; and
- `defer`: no decision is made and promotion remains blocked.

No outcome authorizes package signing, publisher attestation, registry publication, installation,
configuration, enablement, target access, credential resolution, capability execution, deployment,
or infrastructure mutation.

## Request Contract

The create request accepts only:

- exact eligible final-validation ID and canonical digest;
- exact package digest;
- immutable connector-approval policy ID and canonical digest;
- a bounded human review purpose;
- explicit acknowledgement that request creation is not approval or execution authority; and
- platform idempotency and correlation identifiers.

The caller cannot select upstream evidence, alter findings or risks, accept a limitation, lower a
severity, set expiry, choose an approver, set quorum, supply a decision, define a lifecycle state,
or provide target, secret, credential, command, payload, signing, registry, installation,
enablement, or execution values.

## Immutable Approval Packet

The platform packet binds at least:

- request schema/version, requester, tenant, environment, creation, and expiry;
- exact final-validation ID, digest, policy ID/digest/version, actor-set digest, and evidence digest;
- exact package, handoff, project, inventory, product, and observed-version identity;
- eligibility, coverage, finding, limitation, and blocking-risk counts;
- stable risk, check, limitation, and source-stage summary digests;
- approval-policy ID, digest, version, stage, quorum, assurance, and expiry requirements;
- review purpose and explicit no-authority declarations; and
- deterministic canonicalization version and packet digest.

Raw package content, target coordinates, filesystem paths, trust or secret references, credential
handles, traffic, request/response payloads, stdout, stderr, exceptions, model context, and other
sensitive evidence are excluded.

Any mismatch, material source change, policy change, expiry, or digest substitution invalidates the
request for decision. A new review requires a new immutable request.

## Approval Policy Snapshot

Platform policy selects one immutable, signed, verified, unexpired, tenant-scoped snapshot. The
first snapshot defines:

- accepted final-validation schema and eligible outcome;
- maximum final-evidence age and request lifetime;
- required human authentication assurance;
- one stable approval stage and quorum of one distinct eligible human;
- permitted outcomes and mandatory rationale bounds;
- requester/approver/upstream/policy-author separation;
- required no-authority flags and disclosure text; and
- deterministic request and decision schema versions.

Customer policy may strengthen but cannot weaken non-overridable separation, integrity, audit,
human identity, no-authority, and fail-closed requirements.

## Requester And Approver Separation

Only an exact-tenant, multi-factor human with dedicated request permission may submit the eligible
final-validation report. The final validator may submit it because submission creates no decision.

Only a separate exact-tenant, multi-factor human with dedicated decision permission may decide.
The approver must be distinct from:

- the request creator and final validator;
- every acquisition, review, validation, analysis, runner, lab, plan-approval, and credential-
  custody actor in the exact lineage; and
- the approval-policy signer or publisher.

AI, workload, service, anonymous, shared, wrong-scope, disabled, delegated-without-policy, and
insufficient-assurance identities fail closed without request discovery.

## Decision Contract

The decision request accepts only:

- exact request ID, expected request version, and canonical packet digest;
- one policy-permitted outcome;
- bounded, non-empty human rationale;
- explicit acknowledgement of the outcome's package-only scope; and
- idempotency and correlation identifiers.

Approvers cannot edit the packet, evidence, risk, limitation, policy, expiry, stage, quorum,
requester, package, or downstream lifecycle flags. Optimistic concurrency preserves the first valid
decision. Conflicting replay, stale version, expired packet, changed source, tampered digest, or
ineligible identity is rejected.

## State And Lifecycle Effect

The projected states are `pending`, `approved`, `rejected`, `needs_evidence`, `deferred`, and
`expired`.

- Pending, needs-evidence, deferred, and expired remain promotion-blocked and set neither approval
  nor rejection authority.
- Rejected sets only `connector_rejected=true` for the exact package and remains promotion-blocked.
- Approved sets only `connector_approved=true` and `eligible_for_publisher_governance=true` for the
  exact packet while preserving every upstream completion flag.

Every state keeps `package_signed`, `publisher_attested`, `connector_registered`,
`connector_installed`, `connector_enabled`, `target_configured`, `credentials_resolved`,
`runtime_trust_granted`, `execution_authorized`, `deployment_approved`, and
`infrastructure_mutation_performed` false.

Approval expiry does not erase the historical decision. It makes the approval invalid for a later
handoff, which must independently revalidate current evidence, policy, roles, and context.

## Persistence, Audit, And Concurrency

Requests and decisions are immutable, idempotent, deterministic for stable evidence, and
concurrency-safe. A final-validation report has at most one active request in the first profile and
a request has at most one decision. Memory and PostgreSQL adapters are behaviorally equivalent.

Required audit succeeds before each persistence event and records safe request, packet, policy,
actor, outcome, rationale classification, version, and no-authority metadata. Audit, integrity,
source, policy, clock, or persistence failure cannot fabricate approval.

## API And Web Contract

Strict create/read/decide APIs require dedicated default-deny RBAC, browser sessions, CSRF for
mutations, exact tenant scope, MFA human identity, correlation, acknowledgements, bounded schemas,
safe errors, optimistic concurrency, and `no-store` responses.

The web view presents exact package/evidence/policy identity, requester, expiry, stage, eligibility,
risks, limitations, and what each outcome does and does not permit before neutral decision controls.
Approve, reject, needs-evidence, and defer are equally available; no outcome is preselected and no
urgency or persuasive language is used. No signing, registry, install, enable, target, secret,
execution, or deployment control is present.

## Consequences

- Package approval becomes an attributable human decision rather than an inferred validation state.
- Exact digest binding prevents approval replay or package substitution.
- Request creation, evidence validation, policy authority, and decision remain separate roles.
- Publisher attestation, signing, registration, installation, instance configuration, enablement,
  and runtime trust require later ADRs and independent controls.

## Rejected Alternatives

- Mark final validation as approval: rejected because evidence producers cannot accept risk.
- Use chat acknowledgement or generic ticket state: rejected because neither is an exact signed
  human decision packet.
- Let the requester approve: rejected because it collapses accountable separation of duties.
- Allow the approver to edit risk or policy: rejected because approval must bind immutable evidence.
- Issue an execution token on approval: rejected because Project Atlas remains decision support and
  this package-level decision has no target or operation contract.

## Validation

- Exact final-report, package, policy, packet-digest, tenant, environment, and source-change tests
- Requester/approver/upstream/policy-signer separation, MFA, scope, and no-discovery tests
- Approve, reject, needs-evidence, defer, expiry, stale-version, conflict, and replay tests
- Immutable request/decision, idempotency, concurrency, audit-before-persist, memory/PostgreSQL
  equivalence, and one Alembic-head tests
- Proof that no state signs, attests, registers, installs, enables, accesses a target or secret,
  executes, deploys, or mutates infrastructure
- Strict API, CSRF, `no-store`, safe-error, response-minimization, web neutrality, desktop,
  390-pixel mobile, browser-log, live HTTP, and GitHub CI validation
