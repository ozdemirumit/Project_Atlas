# ADR-020: Connector Contract Validation Contract

- Status: Accepted
- Date: 2026-08-05
- Decision owners: Product Owner, Architecture Owner, Security Owner
- Governing documents: ATLAS-003, ATLAS-020, ATLAS-021, ATLAS-022, ATLAS-025,
  ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-047, ATLAS-050, ATLAS-051,
  ATLAS-053, ATLAS-055, ATLAS-056, ADR-009 through ADR-019

## Context

ADR-019 establishes that the exact connector package satisfies one approved internal-use license
policy snapshot. It does not establish that the package's manifest, schemas, generated handlers,
contract-test declaration, and synthetic fixtures describe one internally consistent connector
contract. That consistency must be proven before any untrusted package code enters an isolated
runner.

Generated tests are untrusted package content. Executing them during this stage would grant process
and filesystem behavior before runner isolation has been validated. Contract validation therefore
uses bounded standard parsers and Python AST inspection only. Runner execution, runtime self-test,
simulator behavior, and vendor compatibility remain later independent gates.

## Decision

Atlas adopts profile `atlas.connector-contract.python312.v1` and validator version
`atlas.connector-contract-validator.v1`.

A dedicated authenticated multi-factor human contract-validation operator initiates the stage in
the exact package organization and environment. The operator differs from every Builder,
acquisition, manifest-validation, inventory, content-policy, schema-semantics,
authority-behavior, static-dependency, vulnerability-analysis, malware-analysis, and
license-analysis actor. AI, service, prior-stage, wrong-scope, insufficient-assurance, and
unauthorized identities fail closed without package or report discovery.

The stage accepts only the exact passed ADR-019 report with `promotion_blocked=false` and all
through-license completion flags. Atlas verifies the complete upstream canonical lineage, every
no-authority flag, immutable archive bytes, and exact package and inventory digests before
validation. The caller cannot upload tests or fixtures, choose a profile, declare expected values,
exclude files, suppress findings, or select assertions.

The validator reads only the exact verified archive and accepted inventory. It uses bounded JSON,
TOML, UTF-8, and Python AST parsing. It never imports, compiles, installs, builds, resolves,
downloads, or executes package content and has no network, model, secret, target, shell, or child
process access.

The initial generated-draft profile verifies these contract families:

- Manifest identity, SDK profile, quarantine status, capability class, permission, and denied
  runtime/execution authority
- Configuration schema identity, required keys, closed properties, and secret-reference semantics
- Per-capability input/output schema identity and exact manifest-to-module-to-schema binding
- Per-capability handler constants, async signature, bounded literal result or fail-closed return,
  and absence of import-time behavior
- Contract-test AST restricted to per-capability manifest, schema, handler-binding, and synthetic
  expected-result declarations, including exact denied-authority assertions for fail-closed handlers
- Synthetic fixture schema, synthetic classification, disconnected target, absent secret values,
  bounded empty responses, and absence of real-system markers
- Exact coverage so every declared capability has one module, one input schema, and one output
  schema, with no orphan or duplicate contract artifact

This profile proves only static consistency of the generated quarantined draft. It does not prove
that a vendor API behaves as documented, that a handler succeeds, that mocks are realistic, that
the package is safe to execute, or that a connector is compatible with a target. A pass cannot be
used as runner, self-test, lab, registration, approval, installation, or enablement evidence.

Any missing, changed, duplicate, orphaned, ambiguous, malformed, oversized, unsupported, unexpectedly permissive,
inconsistent, executable, non-synthetic, secret-bearing, target-connected, or unbound contract
artifact fails the report and blocks promotion. Parser, audit, integrity, or persistence failure
cannot fabricate a report or a passing result.

Reports never persist or expose package source, test bodies, assertions, fixture payloads, schema
properties, configuration names, secret-reference names, capability identifiers, paths, endpoint
details, citations, permissions, target products, or parse diagnostics. A safe finding contains only
a public rule identity, category, severity, artifact scope, one-way subject fingerprint, generic
summary, and remediation. APIs, audit metadata, logs, errors, and model context use only these
minimized fields and aggregate counts.

The immutable report records outcome, exact upstream lineage, profile and validator identities,
contract-family and coverage counts, safe findings, limitations, canonical digest, operator,
tenant, time, `promotion_blocked`, and all no-authority flags. Reports are one-to-one,
deterministic, immutable, idempotent, concurrency-safe, and audit-before-persist.

A failed report blocks promotion but does not reject, rewrite, delete, repair, regenerate, approve,
sign, register, install, enable, configure, trust, execute, deploy, or change a connector or
infrastructure. Completion marks only `contract_validation_completed=true` while preserving all
through-license completion flags. Runner, self-test, lab, final validation, approval, registration,
installation, and enablement remain separate later stages.

Strict no-store APIs use dedicated create/read permissions, default-deny authorization, browser
CSRF for creation, exact tenant scope, bounded schemas, correlation, safe errors, explicit
acknowledgement, and full-lineage separation of duties. The Connector workspace presents safe
profile, coverage, finding, limitation, lineage, and promotion summaries without package internals
or later-stage action controls.

## Consequences

- Untrusted generated tests cannot gain execution merely because they are named contract tests.
- Exact package contracts become reproducible and reviewable before isolated runner work begins.
- The initial profile validates only quarantined generated-draft contracts whose handlers either
  fail closed or return bounded literal results that exactly match synthetic contract evidence.
- Executable behavioral tests, simulator scenarios, and vendor compatibility require later stages.
- A package requiring richer contracts must be regenerated through the Builder and repeat every
  prior immutable promotion gate.

## Rejected Alternatives

- Run `pytest` directly during contract validation: rejected because package tests are untrusted
  executable content and runner isolation is not yet established.
- Accept the earlier Builder static-validation result: rejected because downstream admission must
  independently verify the exact acquired package and complete promotion lineage.
- Let the caller upload fixtures or choose assertions: rejected because the caller could manufacture
  a passing contract.
- Treat a generated mock pass as vendor compatibility: rejected because self-consistency does not
  prove real target behavior.
- Rewrite missing tests or schemas during validation: rejected because validation is read-only and
  any remediation must produce a new package that repeats all prior gates.
- Expose contract contents in findings: rejected because safe rule identity and fingerprints are
  sufficient for this boundary and avoid unnecessary package disclosure.

## Validation

- Exact passed-license-report, archive, inventory, and full-lineage tests
- Manifest, configuration, input, output, handler, test-AST, fixture, and coverage-family tests
- Missing, duplicate, orphaned, malformed, oversized, changed, unsupported, and ambiguous artifacts
- Runtime-authority, import-time behavior, unsafe AST, unbounded result, target-connected, secret-bearing, and
  non-synthetic fixture failures
- No import, compilation, build, installation, execution, child-process, network, model, secret, or
  target access tests
- Safe-finding and non-disclosure tests for paths, source, assertions, fixtures, schemas,
  configuration, capabilities, permissions, endpoints, citations, and parser diagnostics
- Dedicated permission, MFA, human identity, acknowledgement, scope, and separation tests
- Passed and failed immutable reports, idempotency, concurrency, and audit-before-persist
- Memory and PostgreSQL repository equivalence with one Alembic head
- Strict create/read API, CSRF, no-store, safe-error, and response-minimization tests
- Web, desktop, 390-pixel mobile, live HTTP, browser-log, and GitHub CI validation
