# ADR-016: Connector Static Code and Dependency Hygiene Contract

- Status: Accepted
- Date: 2026-08-05
- Decision owners: Product Owner, Architecture Owner, Security Owner
- Governing documents: ATLAS-003, ATLAS-020, ATLAS-021, ATLAS-022, ATLAS-025,
  ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-047, ATLAS-050, ATLAS-051,
  ATLAS-053, ATLAS-055, ATLAS-056, ADR-009 through ADR-015

## Context

ADR-015 proves that bounded implementation evidence matches declared authority. It does not prove
that the complete connector source tree is structurally sound, that imports reconcile to package
metadata, or that dependency declarations are reproducible and suitable for later isolated builds.
ATLAS-020 validation pipeline step 7 therefore requires independent static and dependency checks.

Static inspection and dependency hygiene are not vulnerability, malware, or license conclusions.
Those conclusions require separately governed advisory, signature, and policy datasets with their
own freshness, availability, failure, and approval semantics.

## Decision

Atlas adopts profile `atlas.connector-static-dependency.python312.v1` and analyzer version
`atlas.connector-static-dependency-analyzer.v1`.

A dedicated authenticated multi-factor human static-analysis operator initiates the stage in the
exact package organization and environment. The operator differs from every Builder, acquisition,
manifest-validation, inventory, content-policy, schema-semantics, and authority-behavior actor.
AI, service, prior-stage, wrong-scope, insufficient-assurance, and unauthorized identities fail
closed without package or report discovery.

The stage accepts only the exact passed ADR-015 report with `promotion_blocked=false`. Atlas
verifies complete upstream canonical lineage and no-authority flags, independently rereads the
immutable archive, and reconciles Python and project-metadata paths, digests, sizes, content
classes, and normalized dependencies to the passed inventory.

The analyzer operates offline and read-only. It parses Python 3.12 source with the standard AST,
tokenizes source only for bounded structural checks, and parses `pyproject.toml` through the
standard structured parser. It never imports, compiles, executes, builds, installs, resolves, or
downloads connector code or dependencies and never contacts a target, network, model, package
index, advisory database, or license service.

The static-code profile checks:

- package/module path uniqueness and a bounded, internally resolvable import graph;
- no wildcard, dynamic, ambiguous, or path-escaping imports;
- external imports bind exactly to normalized runtime dependency declarations;
- no executable top-level statements outside imports, declarations, constants, and definitions;
- no bare exception handlers, silent exception suppression, mutable global state, `global` or
  `nonlocal` mutation, or unsupported metaprogramming;
- bounded file, AST node, nesting, branch, function, import, and finding counts; and
- annotations on public and capability functions without claiming full type soundness.

The dependency-hygiene profile checks:

- project metadata and normalized inventory remain identical;
- runtime dependencies use exact versions; a non-empty runtime set requires a deterministic lock
  artifact with hashes and exact direct-dependency coverage;
- build dependencies use bounded lower and upper constraints and the declared build backend remains
  consistent with its build requirements;
- duplicate, conflicting, unbounded, prerelease-only, path, URL, VCS, marker, wildcard, editable,
  alternate-index, and undeclared dependency forms fail closed; and
- imported third-party roots reconcile one-to-one to declared runtime dependencies under a
  versioned package-to-import mapping profile.

An empty runtime dependency set may pass without a lock artifact. Passing dependency hygiene means
only that declarations are deterministic and internally consistent; it does not establish that a
version is secure, available, compatible, licensed, authentic, or installable.

The immutable report records passed or failed outcome, exact upstream lineage, analyzer identity,
bounded source and dependency summaries, safe findings, canonical digest, operator, tenant, time,
limitations, `promotion_blocked`, and every no-authority flag. Findings contain only stable rule
code, category, severity, normalized relative path, bounded line number, evidence fingerprint,
generic summary, and remediation. Source snippets, tokens, string literals, import targets,
dependency constraints, URLs, indexes, credentials, and archive bodies never enter report, audit,
logs, errors, or model context.

Reports are one-to-one, deterministic, immutable, idempotent, concurrency-safe, and
audit-before-persist. Failed analysis blocks promotion but does not reject, rewrite, sign,
register, approve, install, enable, configure, trust, execute, deploy, or mutate a connector or
infrastructure.

Strict no-store APIs use dedicated create/read permissions, default-deny authorization, browser
CSRF for creation, exact tenant scope, bounded schemas, correlation, safe errors, explicit
acknowledgement, and full-lineage separation of duties. The Connector workspace presents safe
summaries, findings, checks, limitations, lineage, and promotion state without source code,
dependency values, or later-stage action controls.

## Consequences

- Source structure, import consistency, and dependency reproducibility become explicit evidence
  before contract or runner tests.
- Ambiguous source, imports, metadata, or dependency state blocks promotion rather than being
  interpreted as safe.
- Passing this stage sets only `static_code_validation_completed=true` for this exact report.
- Vulnerability, malware, license, contract, mock-target, runner, self-test, lab, final validation,
  approval, registration, installation, and enablement remain separate later stages.

## Rejected Alternatives

- Run package linters, type checkers, builds, or installers in this stage: rejected because those
  tools load package configuration or code and belong in a later isolated runner.
- Resolve or download dependencies during analysis: rejected because this stage is deterministic,
  offline, and has no package-index authority.
- Combine vulnerability, malware, and license results into this report: rejected because each
  requires independently versioned evidence and has different failure semantics.
- Treat dependency names or import targets as harmless response data: rejected because safe counts,
  paths, rule identifiers, and one-way fingerprints are sufficient at this boundary.
- Automatically rewrite imports or pin dependencies: rejected because validation cannot mutate the
  reviewed package.

## Validation

- Exact passed-authority-report and immutable archive/inventory lineage tests
- Python syntax, import graph, top-level execution, exception, global-state, annotation, complexity,
  ambiguity, and resource-bound tests
- Empty, exact-pinned, unbounded, conflicting, undeclared, unmapped, and lock-required dependency tests
- Safe-finding and non-disclosure tests for source, import targets, constraints, URLs, and indexes
- Dedicated permission, MFA, human identity, acknowledgement, scope, and separation tests
- Passed and failed immutable reports, idempotency, concurrency, and audit-before-persist
- Memory and PostgreSQL repository equivalence with one Alembic head
- Strict create/read API, CSRF, no-store, safe-error, and response-minimization tests
- Web, desktop, 390-pixel mobile, live HTTP, browser-log, and GitHub CI validation
