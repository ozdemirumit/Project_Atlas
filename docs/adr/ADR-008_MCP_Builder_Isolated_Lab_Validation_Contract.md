# ADR-008: MCP Builder Isolated Lab Validation Contract

- Status: Accepted
- Date: 2026-08-05
- Decision owners: Product Owner, Architecture Owner, Security Owner
- Governing documents: ATLAS-003, ATLAS-020, ATLAS-021, ATLAS-022, ATLAS-025,
  ATLAS-032, ATLAS-033, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-053, ATLAS-056,
  ADR-004, ADR-005, ADR-006, ADR-007

## Context

ADR-007 produces an immutable independent security judgment for the exact quarantined connector
scaffold. It does not prove that the generated Python package imports, preserves its fail-closed
contract when invoked, remains bounded in a child process, or can be exercised without secrets,
network access, target access, or persistent runtime authority.

ATLAS-022 requires isolated laboratory evidence before a candidate package handoff. The first
profile must create meaningful runtime evidence without treating this workstation, a Python
subprocess, or a synthetic fixture as a production-grade connector runner or a real vendor lab.

## Decision

Atlas records the first laboratory result under profile `atlas.lab-validation.python312.v1` and
runner contract version `mcp-builder-isolated-runner.v1`.

A run requires an accepted `atlas.security-review.connector.v1` record and binds the exact project,
source, design checkpoint, generation, artifact, static-validation report, domain review, security
review, organization, environment, and authenticated multi-factor human lab operator. Creation and
read use dedicated permissions. The lab operator must differ from both the domain reviewer and the
security reviewer. AI, service, wrong-scope, insufficient-assurance, self-review, and unassigned
identities fail closed.

The profile accepts only the deterministic `atlas.python312.v1` scaffold produced by
`mcp-builder-python.v1`. Before launch, Atlas reads every file through the quarantine publisher,
reverifies path, media type, size, and SHA-256 inventory, and confirms exact deterministic
regeneration. Any missing, changed, extra, unsupported, or unreadable artifact fails before child
execution.

The runner copies verified files into a new ephemeral workspace and launches the configured Python
runtime in isolated mode with a minimal allowlisted environment, no secret values, no inherited
Python path, no vendor credential, no target address, no model access, bounded output, and a hard
timeout. The child installs a deny-first audit policy for socket creation or connection, nested
process creation, shell invocation, and native-library loading. The current generated profile is
also statically restricted to the exact known template, so the child never receives arbitrary
human-modified source.

The child performs only these synthetic checks:

- package import and declared quarantine constants
- manifest quarantine, runtime-trust, and execution-authority contract
- synthetic fixture classification with no target and no secret values
- capability module import and exact fail-closed handler behavior for every reviewed capability
- network-denial probe and observation that no target request occurred
- bounded structured result production

Atlas records eight stable checks: artifact integrity, runner isolation, secret-free environment,
network denial, package import, quarantine contract, capability fail-closed behavior, and bounded
output. All checks must pass for overall `passed`; any failed or skipped required check yields
`failed`. Runner timeout, abnormal exit, malformed output, excessive output, unsupported runtime, or
isolation-policy failure is failed evidence, never unknown success.

The result is immutable, one-to-one with the exact accepted security review, idempotent,
audit-before-persist, and safe under concurrent replay. It records runtime identity, exit status,
bounded duration, observed checks, artifact and output digests, limitations, and explicit authority
flags. The child process is terminated before a successful result can be persisted, and its
ephemeral workspace is removed on every outcome.

A passing result proves only the bounded synthetic behavior of this exact quarantined scaffold under
this runner contract. It does not prove vendor semantics, real target compatibility, production
sandbox strength, dependency or vulnerability state, malware safety, performance, package
reproducibility, signing eligibility, registration, installation, enablement, target access, runtime
trust, execution approval, deployment approval, or infrastructure safety.

## Consequences

- Generated code receives its first controlled runtime exercise only after domain and independent
  security acceptance.
- The first profile verifies fail-closed C1 draft behavior and cannot test a successful vendor request.
- Platform deployments can replace the local subprocess adapter with a stronger isolated runner while
  preserving the same application and evidence contract.
- A passed result can become input to candidate package construction and approval, but grants no
  package or runtime authority itself.
- Failed results remain durable evidence and block lifecycle advancement.

## Rejected Alternatives

- Treat static validation as laboratory evidence: rejected because it never imports or invokes the
  generated scaffold.
- Execute before independent security acceptance: rejected because generated artifacts are untrusted.
- Use real vendor credentials or targets in the first profile: rejected because target access needs a
  separate approved test plan and environment evidence.
- Run tests in the API process: rejected because untrusted execution must cross an explicit runner
  boundary.
- Mark subprocess success as production approval: rejected because the local adapter is bounded
  evidence, not a production sandbox or deployment authority.

## Validation

- Domain invariants and canonical digest tests
- Exact upstream evidence, profile, template, capability, tenant, and actor binding tests
- Artifact tamper, unreadable file, unsupported runtime, timeout, abnormal exit, malformed output,
  excessive output, and isolation-policy failure tests
- Package import, manifest, fixture, every-capability fail-closed invocation, network denial, no-secret,
  bounded-output, and workspace-cleanup tests
- Idempotency, concurrent replay, audit-before-persist, memory/PostgreSQL equivalence, and migration tests
- Strict create/read API, CSRF, RBAC, MFA, tenant, acknowledgement, and separation-of-duties tests
- Desktop, 390-pixel mobile, browser-log, and live authorized/denied API validation

