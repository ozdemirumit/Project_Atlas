# ADR-023: Connector Final Validation Contract

## Status

Accepted

## Context

ADR-022 defines a plan-bound, read-only laboratory self-test for one exact connector candidate.
Passing that gate proves only the bounded behavior observed under the approved lab plan. It does not
prove that every acquisition, supply-chain, semantic, security, contract, disconnected-runner, and
target-connected result still belongs to the same immutable package, tenant, policy set, and actor
lineage at the moment the package enters human approval.

Atlas therefore needs a final validation gate that replays the complete evidence chain, evaluates
all unresolved risks and limitations against one immutable organizational policy, and emits one
deterministic approval-eligibility report. This gate is evidence aggregation only. It cannot approve,
attest, sign, register, install, enable, trust, execute, deploy, or mutate a connector or target.

## Decision

Atlas will implement final validation as a separate, default-deny, human-operated gate after the
exact package has a completed lab self-test. The gate consumes no package bytes directly and runs no
connector code. It independently reloads and verifies the complete immutable evidence lineage,
evaluates a platform-selected final-validation policy snapshot, and produces either:

- `eligible_for_human_approval`: every required gate passes, every required policy snapshot is
  valid and fresh, and every limitation is explicitly classified by policy; or
- `blocked`: lineage, integrity, scope, policy, freshness, coverage, separation, limitation, or
  no-authority evidence is missing, inconsistent, expired, unsupported, or failed.

Absence of a finding is never treated as proof. Unknown, malformed, stale, or unavailable evidence
fails closed.

## Complete Evidence Lineage

Final validation binds one exact candidate package to all required connector-pipeline evidence:

1. candidate-package handoff and acquisition receipt;
2. validation intake;
3. content and dependency inventory;
4. secret and prohibited-content scan;
5. configuration and capability schema-semantics validation;
6. declared-authority implementation-behavior validation;
7. static code and dependency-hygiene analysis;
8. dependency-vulnerability analysis;
9. malware analysis;
10. license analysis;
11. connector-contract validation;
12. isolated disconnected runner validation; and
13. approved-plan isolated lab self-test.

Each source must be immutable, integrity-valid, promotion-unblocked, tenant-bound, and linked to the
same package digest, inventory digest, organization, environment, candidate handoff, and complete
actor-set digest. Every stage-specific policy, definition, advisory, malware, license, profile,
adapter, runner, and lab-plan identifier and digest must match its persisted source evidence.

## Request Contract

The create request accepts only:

- exact passed lab-self-test ID and canonical digest;
- exact package digest;
- final-validation policy snapshot ID and canonical digest;
- explicit acknowledgement that this operation creates evidence only;
- idempotency and correlation identifiers supplied through existing platform contracts.

The caller cannot provide or override package contents, upstream report selections, findings,
severity, disposition, limitation classification, policy rules, freshness, waiver, exception,
target, endpoint, route, trust, secret, credential, capability, command, payload, runner, model,
environment, approval, signing, registration, installation, enablement, or execution values.

## Final-Validation Policy Snapshot

Platform policy selects one immutable, versioned, signed, verified, unexpired, and tenant-scoped
snapshot. The snapshot defines:

- required evidence stages and accepted schema/profile versions;
- maximum source and policy ages;
- required policy-signature and definition-set properties;
- required capability, package, file, dependency, and lab coverage;
- blocking outcomes, severities, uncertainty classes, and promotion states;
- permitted limitation categories and mandatory disclosure language;
- product/version support rules and lab-plan compatibility requirements; and
- exact report schema and deterministic check order.

The snapshot cannot grant an exception or approval. A waiver or risk acceptance belongs to a later
explicit human governance workflow and cannot convert blocked final validation into eligible
evidence.

## Validation Checks

The first profile performs a fixed, ordered set of checks covering:

- source availability, schema, canonical digest, and one-to-one lineage;
- package, inventory, handoff, organization, environment, and actor-set consistency;
- all required completion, outcome, promotion, and no-authority flags;
- source-policy identity, signature verification, freshness, and compatibility;
- package/file/dependency/capability/contract/runner/lab coverage reconciliation;
- product identity, supported version, lab plan, profile, adapter, and runner compatibility;
- unresolved finding aggregation without double counting or severity reduction;
- limitation completeness, stable classification, and required disclosure;
- absence of signing, approval, registration, installation, enablement, runtime trust, execution,
  deployment, production access, and infrastructure mutation; and
- deterministic report and evidence-digest reconstruction.

No check performs network access, dependency resolution, import, compilation, package execution,
target access, secret resolution, model inference, or mutation.

## Unresolved Risk And Limitation Report

The result includes only normalized, bounded, non-sensitive summaries:

- stable finding and limitation codes;
- source stage and immutable evidence reference;
- policy classification, severity, and blocking state;
- affected product/version or capability count where safe;
- missing, stale, unsupported, uncertain, or failed evidence counts;
- required next governance step; and
- explicit statements of what the evidence does not prove.

Raw source, package internals, filesystem paths, target coordinates, trust or secret references,
credential handles, traffic, request/response payloads, stdout, stderr, exceptions, vendor-sensitive
details, and model context are excluded from API responses, persistence payloads, audit, logs, and
browser state.

## Separation Of Duties

Only a dedicated multi-factor human final-validation operator may create or read a report in the
exact organization and environment. The operator must be distinct from every upstream acquisition,
validation, analysis, review, runner, lab, plan-approval, and credential-custody actor represented
in the complete lineage. AI, workload, service, anonymous, wrong-scope, disabled, and insufficient-
assurance identities fail closed without report discovery.

The final-validation operator cannot supply a waiver, approve risk, approve the package, or invoke a
later lifecycle action through this surface.

## Persistence, Audit, And Concurrency

Reports are one-to-one with the exact lab-self-test evidence and final policy snapshot, immutable,
idempotent, deterministic for stable evidence, and concurrency-safe. Memory and PostgreSQL adapters
must be behaviorally equivalent. Audit succeeds before persistence and records only safe lineage,
policy, check counts, outcome, and no-authority state.

Integrity, source, policy, audit, or persistence failure cannot fabricate eligibility. Safe stable
error codes replace internal exception details. Reads and creation responses use `no-store`.

## Lifecycle Effect

A blocked result preserves all verified upstream completion flags, sets
`final_validation_completed=true`, and sets `promotion_blocked=true`.

An eligible result preserves the same lineage, sets `final_validation_completed=true`, and sets
`eligible_for_human_approval=true`. It grants no approval, publisher identity, attestation,
signature, registration, installation, enablement, configuration, credential, runtime trust,
execution, deployment, production access, or infrastructure mutation authority.

## API And Web Contract

Strict create/read APIs require dedicated default-deny RBAC, browser session authentication, CSRF
for creation, exact tenant scope, correlation, acknowledgement, bounded schemas, safe errors, and
complete separation of duties. The Connector workspace presents only safe lineage, policy status,
aggregate gate/coverage/risk/limitation checks, eligibility, blocking reasons, and limitations. It
contains no approval, signing, registration, installation, enablement, or execution controls.

## Consequences

- Human approvers receive one reproducible evidence summary without trusting caller-selected gates.
- Every unresolved risk remains visible and cannot be silently downgraded or waived by validation.
- A final pass means only that the exact evidence is eligible to enter a separate human approval
  workflow.
- Signing, attestation, registry, installation, and runtime trust require later ADRs and independent
  identities.

## Rejected Alternatives

- Let an approver inspect independent reports manually: rejected because lineage drift, stale policy,
  missing gates, and inconsistent limitations can be overlooked.
- Treat a lab pass as final validation: rejected because lab evidence does not replay supply-chain,
  policy, and complete actor lineage.
- Permit operator-selected waivers: rejected because validation cannot accept organizational risk.
- Re-run package code during final validation: rejected because dynamic behavior already belongs to
  isolated runner and approved lab gates.
- Mark the package approved or signed on success: rejected because evidence creation, risk decision,
  publisher identity, and privileged signing must remain separate authorities.

## Validation

- Exact 13-stage lineage, digest, package, inventory, tenant, environment, actor-set, and policy tests
- Missing, duplicated, reordered, stale, tampered, unsupported, failed, and cross-tenant evidence tests
- Full separation-of-duties, MFA human identity, scope, CSRF, acknowledgement, and no-discovery tests
- Deterministic finding/limitation aggregation, blocking policy, disclosure, and no-waiver tests
- One-to-one idempotency, concurrency, audit-before-persist, memory/PostgreSQL equivalence, and one
  Alembic-head tests
- Proof that validation performs no network, package execution, target, secret, model, signing,
  approval, registration, installation, enablement, deployment, or infrastructure operation
- Strict create/read API, `no-store`, safe-error, response-minimization, desktop, 390-pixel mobile,
  browser-log, live HTTP, and GitHub CI validation
