# ADR-005: MCP Builder Static Validation Profile

| Field | Value |
| --- | --- |
| Status | Accepted |
| Decision Date | 2026-08-05 |
| Decision Owner | Project Atlas Architecture |
| Related Documents | ATLAS-003, ATLAS-020, ATLAS-021, ATLAS-022, ATLAS-025, ATLAS-032, ATLAS-047, ATLAS-050, ATLAS-055, ATLAS-056, ADR-004 |
| Supersedes | None |

## Context

ADR-004 produces deterministic Python 3.12 connector review scaffolds inside Atlas-owned quarantine.
ATLAS-021 and ATLAS-022 require generated artifacts to pass validation before domain review, security
review, lab execution, or candidate packaging. The first validator must provide useful evidence in a
restricted-network environment without importing or executing untrusted generated code.

Validation success must not be confused with vendor compatibility, production approval, package
eligibility, registration, installation, runtime trust, or execution authority.

## Decision

The first MCP Builder validation profile is `atlas.static-validation.python312.v1`, implemented by
validator version `mcp-builder-static-validator.v1`.

The validator reads every generated file through the quarantine artifact boundary and produces an
immutable report bound to the exact project, design checkpoint, generation, artifact, language
profile, and template digests. It performs deterministic checks for:

- Artifact inventory, byte-size, digest, and deterministic-regeneration equality
- Connector manifest structure and quarantine authority flags
- Python 3.12 syntax and prohibited import, call, and dynamic-execution constructs using AST only
- Python project metadata, bounded build backend, and empty runtime dependency set
- JSON Schema and synthetic-fixture structure
- Capability, class, permission, network, configuration, secret-reference, entity-mapping, and source
  traceability completeness against the approved design checkpoint
- Required fail-closed contract tests and generated documentation
- Bounded secret, credential, private-key, unsafe URL, and prohibited-file scans

The report records every check as passed, failed, or skipped with stable code, severity, summary,
evidence paths, and remediation. A failed artifact-integrity gate records the remaining checks as
skipped rather than reading or trusting unverified content.

The validator does not import, compile, execute, test, package, sign, register, install, enable, or
invoke generated code. It performs no network request, model inference, subprocess or shell
invocation, secret resolution, target connection, or infrastructure mutation. Runtime self-test,
dependency vulnerability resolution, domain review, security review, lab validation, and packaging
remain later isolated gates.

## Consequences

- Reviewers receive machine-readable and human-readable evidence before any generated-code execution.
- Validation is reproducible in restricted networks and independent of a package registry or model.
- A passing report proves only the bounded static profile against the exact artifact digest.
- Any generated or manually changed artifact requires a new validation record and report digest.
- Later executable sandbox profiles require a separate ADR and stronger host, network, resource, and
  evidence controls.

## Rejected Alternatives

- Run generated pytest or import modules in the API process: rejected because generated content is
  untrusted and no isolated execution runner exists yet.
- Treat deterministic generation as validation: rejected because generation and validation must be
  independent lifecycle gates.
- Resolve dependencies or vulnerability feeds online: rejected because the first profile must work in
  restricted networks and must not grant network access.
- Advance a passing artifact directly to packaging: rejected because domain, security, lab, and
  environment approvals remain mandatory.

## Validation

- Exact source, design, generation, artifact, profile, and validator binding
- Deterministic passed, failed, and skipped check reports with canonical report digests
- Artifact tamper, unsafe Python, manifest authority, permission, traceability, secret, and prohibited
  file tests
- Audit-before-persist, idempotency, concurrency, scope, MFA, and PostgreSQL parity tests
- Explicit proof that model, network, subprocess, dynamic execution, package, registration, runtime
  trust, and infrastructure authority remain false
