# ADR-022: Connector Isolated Lab Self-Test Contract

- Status: Accepted
- Date: 2026-08-05
- Decision owners: Product Owner, Architecture Owner, Security Owner
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-020, ATLAS-021,
  ATLAS-022, ATLAS-023, ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033,
  ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-053, ATLAS-055, ATLAS-056, ADR-009
  through ADR-021

## Context

ADR-021 proves that the exact quarantined package imports and preserves reviewed bounded or
fail-closed behavior in a disconnected synthetic subprocess. It does not prove TLS, authentication,
product identity, version compatibility, target-side authorization, real response parsing, or
read-only behavior against an approved laboratory target.

The next gate needs target-connected evidence without turning a validation request into arbitrary
network access or an infrastructure operation. Lab access must remain production-excluded,
pre-approved, least privilege, observable, revocable, and separate from registration, installation,
enablement, or production execution authority.

## Decision

Atlas adopts profile `atlas.connector-lab-self-test.readonly.v1`, plan schema
`atlas.connector-lab-plan.v1`, runner adapter contract `atlas.connector-lab-runner.v1`, and report
schema `atlas.connector-lab-self-test-report.v1`.

A dedicated authenticated multi-factor human lab operator initiates the stage in the exact package
organization and environment. The operator differs from every prior Builder, review, acquisition,
analysis, contract, and runner-validation actor and from the lab-plan approver and credential
custodian. AI, service, prior-stage, plan-approver, credential-custodian, wrong-scope,
insufficient-assurance, and unauthorized identities fail closed without target, secret, package,
or report discovery.

The stage accepts only the exact passed ADR-021 report with `promotion_blocked=false`, every
through-runner completion flag, and all no-authority flags intact. Atlas independently verifies the
complete canonical lineage, report digest, package bytes, inventory, and prior evidence before
requesting lab access.

The caller supplies only an immutable approved lab-plan identifier and digest. The plan is created
and approved outside this stage and binds one non-production target identity, environment, site,
vendor, product family, supported version range, TLS trust reference, secret references, permitted
destinations, read-only capability set, request budget, deadline, maintenance window, data-handling
classification, and expiry. The request cannot provide or override an endpoint, route, proxy,
certificate, credential, secret value, command, argument, method, payload, capability, expected
result, timeout, runner, or environment variable.

Only capability classes `C0` and `C1` are eligible. Every selected operation must be declared
read-only by the exact accepted contract and explicitly allowlisted by the lab plan. Mutation,
configuration change, lifecycle action, delete, create, update, restart, failover, write-like method,
unbounded query, or undeclared request fails before target access. A package with unresolved
required capability coverage cannot pass by silently excluding capabilities.

The lab runner receives a one-time execution grant from a policy decision point. A secret broker
resolves only plan-bound references into short-lived least-privilege credentials inside the runner;
raw values never enter the API, database, audit event, application log, report, browser, model
context, command line, or inherited environment. Grants and credentials expire or are revoked when
the run ends, times out, loses its lease, or fails cleanup.

The runner uses a fresh isolated workspace and denies all egress except the exact approved target
destinations and required platform control channels. It enforces TLS verification and the plan's
trust binding, request count and byte budgets, redirects disabled, DNS rebinding protection where
applicable, hard deadline, bounded output, no nested process or shell, and no persistent filesystem
effects. The lab adapter contract is replaceable by container, VM, or dedicated-pool
implementations without changing application evidence semantics.

The platform-owned harness performs only these checks:

- exact source, plan validity, approval separation, lease, and package integrity
- isolated runner, bounded egress, secret-broker delivery, and post-run revocation
- TLS trust, authentication, expected lab target identity, product family, and version range
- package import, quarantine declarations, and exact plan-bound read-only capability coverage
- connector self-test and each approved C0/C1 capability with bounded, sanitized lab inputs
- response schema, error mapping, pagination or bounded-result behavior where declared
- observation that no mutation, undeclared destination, secret disclosure, or persistent effect occurred
- bounded evidence output, target-session closure, lease release, and workspace cleanup

All required checks must pass for overall `passed`. Expired or changed plan evidence, target
identity or version mismatch, TLS or authentication failure, redirect, undeclared egress, secret
broker failure, credential disclosure, denied-policy event, timeout, malformed or excessive output,
incomplete capability coverage, write attempt, target-side mutation observation, cleanup failure,
or revocation failure cannot produce a pass.

The immutable report is one-to-one with the exact passed runner-validation report and approved lab
plan. It is deterministic for stable evidence, idempotent, concurrency-safe, and
audit-before-persist. It records only safe lineage, plan and policy fingerprints, target identity
alias, product/version evidence, profile and adapter identities, aggregate capability/request
counts, stable check outcomes, duration, bounded evidence digests, lease/revocation/cleanup states,
limitations, canonical digest, operator, tenant, and time. Endpoints, addresses, routes,
certificates, secret references or values, headers, requests, responses, package internals,
workspace paths, stdout/stderr, and exception details never enter user-visible or model-visible
evidence.

A failed report blocks promotion but does not reject, rewrite, delete, repair, approve, sign,
register, install, enable, configure, trust, deploy, or operate a connector. Either outcome marks
only `lab_validation_completed=true` while preserving all through-runner completion flags. A pass
proves bounded read-only compatibility only for the exact package, approved lab plan, target
identity, observed product version, and test time. It does not prove production compatibility,
performance, availability, broad vendor support, production sandbox strength, signing eligibility,
runtime trust, deployment approval, or infrastructure safety.

Strict no-store APIs use dedicated create/read permissions, default-deny authorization, browser
CSRF for creation, exact tenant scope, bounded schemas, correlation, safe errors, explicit
acknowledgement, full-lineage separation of duties, and non-disclosing not-found behavior. The
Connector workspace presents only safe plan status, target alias, product/version, aggregate
coverage, checks, limitations, lease/revocation/cleanup, lineage, and promotion summaries without
secrets, target coordinates, raw traffic, package internals, or later-stage action controls.

## Consequences

- Target-connected validation occurs only after all static, supply-chain, contract, and disconnected
  runtime gates pass.
- Lab access is a policy-issued, time-bounded evidence grant rather than connector runtime authority.
- The first profile supports read-only C0/C1 behavior only; mutation validation needs a separate ADR,
  risk analysis, approved rollback, and explicit human change process.
- A deterministic local mock-target adapter can validate orchestration and fail-closed controls, but
  only evidence from an approved external lab adapter can claim vendor/product compatibility.
- Successful evidence can advance to a separate final validation and approval gate while granting no
  registration, installation, enablement, or production authority.

## Rejected Alternatives

- Let the operator type a URL or credential: rejected because it bypasses approved plan, scope, and
  secret governance.
- Reuse the disconnected synthetic runner result: rejected because it provides no TLS,
  authentication, target identity, or real response evidence.
- Permit write capabilities in the first profile: rejected because lab self-test is evidence
  collection, not a change workflow.
- Store raw traffic for debugging: rejected because it can disclose secrets, target topology, and
  customer data.
- Treat a lab pass as production approval: rejected because lab identity, scale, state, routing, and
  policy differ from production.

## Validation

- Exact passed-runner-report, package, inventory, digest, plan, approval, lease, and lineage tests
- Dedicated permission, MFA, human identity, acknowledgement, scope, and complete separation tests
- Plan expiry/drift, product/version mismatch, target identity, TLS, redirect, DNS/egress, deadline,
  request/output budget, malformed evidence, and cleanup/revocation failure tests
- Secret-reference-only API and persistence tests plus proof that raw values never enter audit,
  logs, reports, errors, command line, environment, browser, or model context
- Read-only C0/C1 allowlist, exact capability coverage, method classification, schema, pagination,
  self-test, and mutation-observation tests
- Passed and failed immutable reports, idempotency, concurrency, audit-before-persist, and
  memory/PostgreSQL equivalence with one Alembic head
- Strict create/read API, CSRF, no-store, safe-error, response-minimization, desktop, 390-pixel
  mobile, live HTTP, browser-log, mock-target, approved-adapter, and GitHub CI validation
