# ADR-021: Connector Isolated Runner Validation Contract

- Status: Accepted
- Date: 2026-08-05
- Decision owners: Product Owner, Architecture Owner, Security Owner
- Governing documents: ATLAS-003, ATLAS-010, ATLAS-011, ATLAS-020, ATLAS-021,
  ATLAS-022, ATLAS-023, ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033,
  ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-053, ATLAS-055, ATLAS-056, ADR-009
  through ADR-020

## Context

ADR-020 proves that the exact quarantined package has one internally consistent static contract. It
does not prove that the package imports, that a declared handler can be invoked, that synthetic
input produces the declared synthetic result or fail-closed exception, or that execution remains
bounded when the package crosses a process boundary.

Package code and package tests remain untrusted. Runner validation must create runtime evidence
without granting credentials, target access, network access, installation eligibility, runtime
trust, or operational authority. A local child process is a portable evidence adapter, not a
production sandbox or a substitute for later lab and compatibility validation.

## Decision

Atlas adopts profile `atlas.connector-runner.python312.v1`, harness version
`atlas.connector-runner-harness.v1`, and baseline adapter contract
`atlas.connector-isolated-subprocess.v1`.

A dedicated authenticated multi-factor human runner-validation operator initiates the stage in the
exact package organization and environment. The operator differs from every Builder, acquisition,
manifest-validation, inventory, content-policy, schema-semantics, authority-behavior,
static-dependency, vulnerability-analysis, malware-analysis, license-analysis, and
contract-validation actor. AI, service, prior-stage, wrong-scope, insufficient-assurance, and
unauthorized identities fail closed without package, process, or report discovery.

The stage accepts only the exact passed ADR-020 report with `promotion_blocked=false`, all
through-contract completion flags, and every no-authority flag intact. Atlas independently verifies
the complete canonical lineage, archive bytes, inventory, package digest, and contract evidence
before creating a workspace. The caller cannot provide a harness, command, argument, environment,
interpreter, timeout, fixture, expected result, capability selection, network rule, secret, target,
or profile override.

Atlas copies only the exact verified inventory into a fresh ephemeral workspace. The platform-owned
harness launches a fixed Python 3.12 runtime in isolated mode with a minimal allowlisted
environment, no inherited Python path, no package installation, no dependency resolution, no
credential or secret value, no model access, no target address, bounded output, and a hard timeout.
The child installs a deny-first audit policy for socket activity, nested processes, shell
invocation, native-library loading, and filesystem mutation outside its ephemeral workspace.

The harness, not package-supplied tests, performs these checks:

- isolated interpreter, fixed harness/adapter identity, minimal secret-free environment, and
  active deny policies
- package import and exact manifest quarantine, runtime-trust, and execution-authority declarations
- one invocation for every statically accepted capability using its exact disconnected synthetic
  fixture
- exact bounded literal output matching for reviewed handlers, or the exact approved
  `GeneratedDraftNotExecutable` result for fail-closed handlers
- absence of target connection, network request, nested process, shell, native-library, and
  persistent filesystem effects
- bounded structured harness output, deterministic capability counts, and complete workspace
  removal

Atlas records stable checks for accepted source, archive integrity, process isolation, secret-free
environment, network/process denial, package import, quarantine contract, synthetic capability
behavior, bounded output, and workspace cleanup. All checks must pass for overall `passed`. A
timeout, abnormal exit, signal, malformed or excessive output, unsupported runtime, denied-policy
event caused by package behavior, incomplete capability coverage, output mismatch, unexpected
exception, or cleanup failure cannot produce a passing result.

The immutable report is one-to-one with the exact passed contract-validation report. It is
deterministic for stable evidence, idempotent, concurrency-safe, and audit-before-persist. It
records only safe lineage, profile and adapter identities, runtime identity, aggregate capability
counts, check outcomes, bounded duration, exit status, output digest and size, cleanup state,
limitations, canonical digest, operator, tenant, and time. Raw stdout/stderr, source, fixtures,
expected values, capability identifiers, paths, environment values, exception text, import details,
and parser or harness diagnostics never enter API, audit, logs, errors, or model context.

A failed report blocks promotion but does not reject, rewrite, delete, repair, regenerate, approve,
sign, register, install, enable, configure, trust, deploy, or operate a connector. Either report
marks only `runner_validation_completed=true` while preserving all through-contract completion
flags. A pass proves bounded synthetic behavior only under this exact baseline adapter. It does not
prove production sandbox strength, vendor behavior, real target compatibility, performance,
availability, lab acceptance, signing eligibility, runtime trust, or execution authorization.

Strict no-store APIs use dedicated create/read permissions, default-deny authorization, browser
CSRF for creation, exact tenant scope, bounded schemas, correlation, safe errors, explicit
acknowledgement, and full-lineage separation of duties. The Connector workspace presents only safe
profile, runtime, aggregate behavior, check, limitation, lineage, cleanup, and promotion summaries
without package internals or later-stage action controls.

## Consequences

- Exact package code receives its first downstream runtime exercise only after every static,
  security, supply-chain, license, and contract gate passes.
- Package-supplied tests cannot become executable merely because contract validation accepted their
  declarations.
- The portable subprocess adapter provides bounded evidence but is explicitly not a hardened
  production sandbox; stronger container, VM, or dedicated-pool adapters can preserve this report
  contract.
- Successful synthetic behavior can advance to a separate lab gate but grants no connector or
  infrastructure authority.
- Failed results remain immutable evidence and require a newly governed package to retry after
  remediation.

## Rejected Alternatives

- Execute package-supplied tests: rejected because they remain untrusted executable content.
- Run the package in the API process: rejected because untrusted execution must cross an explicit
  process and workspace boundary.
- Let callers select commands, fixtures, environment, timeout, or capabilities: rejected because
  configurable execution would bypass the approved contract.
- Resolve dependencies or install the package before launch: rejected because exact dependency and
  build execution require separate governed stages.
- Use real credentials or targets: rejected because this stage is disconnected synthetic evidence.
- Treat a subprocess pass as production sandbox or vendor compatibility proof: rejected because the
  baseline adapter cannot establish either claim.

## Validation

- Exact passed-contract-report, archive, inventory, digest, and full-lineage tests
- Python version, isolated flags, minimal environment, denied network/process/shell/native-library,
  timeout, exit, malformed output, output budget, and workspace cleanup tests
- Import, quarantine, fail-closed handler, bounded-literal handler, synthetic input/output, and exact
  capability coverage tests
- Proof that package tests are never imported or executed and no dependency installation occurs
- Safe report and non-disclosure tests for source, fixture, expected output, capability, path,
  environment, stdout/stderr, exception, and harness diagnostics
- Dedicated permission, MFA, human identity, acknowledgement, scope, and separation tests
- Passed and failed immutable reports, idempotency, concurrency, and audit-before-persist
- Memory and PostgreSQL repository equivalence with one Alembic head
- Strict create/read API, CSRF, no-store, safe-error, and response-minimization tests
- Web, desktop, 390-pixel mobile, live HTTP, browser-log, and GitHub CI validation
