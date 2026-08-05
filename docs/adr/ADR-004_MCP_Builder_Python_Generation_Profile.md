# ADR-004: MCP Builder Python Generation Profile

| Field | Value |
| --- | --- |
| Status | Accepted |
| Decision Date | 2026-08-05 |
| Decision Owner | Project Atlas Architecture |
| Related Documents | ATLAS-003, ATLAS-020, ATLAS-021, ATLAS-022, ATLAS-047, ATLAS-051, ATLAS-055, ATLAS-056 |
| Supersedes | None |

## Context

ATLAS-021 requires an approved language profile before MCP Builder can generate connector code. The
application stack already standardizes on Python 3.12, while ATLAS-022 requires generation to remain
isolated, reproducible, reviewable, and unable to grant runtime trust.

The first generation profile must create useful connector source and test drafts without assuming that
the future Atlas connector SDK package, runner, package registry, or signing service is already
available. It must also remain usable in restricted networks.

## Decision

The first MCP Builder generation profile is `atlas.python312.v1`:

| Area | Selection |
| --- | --- |
| Language | Python 3.12 |
| Source layout | Standard `src` project layout |
| Generated encoding | UTF-8 with LF line endings |
| Runtime dependencies | None during scaffold generation |
| Development contracts | Python 3.12, Ruff, mypy, and pytest metadata |
| Capability handlers | Typed, non-executable drafts that fail closed until later implementation and validation |
| Target clients | Metadata-only drafts; no socket, HTTP, SDK, CLI, shell, or secret resolution behavior |
| Schemas | Deterministic JSON Schema drafts derived from the confirmed design |
| Provenance | Exact project, source, design-checkpoint, template, and per-file digests |
| Publication | Atomic local publication under an Atlas-owned quarantine root |

Generation is deterministic and template-driven in the first slice. Model-assisted refinement may be
added later only through ATLAS-014 governance and an approved isolated model profile. It cannot replace
the exact source and checkpoint bindings or silently alter capability risk.

The generated scaffold is an untrusted review artifact. It is not a connector package, is not eligible
for registration, and cannot be imported or executed by the Atlas API process. Build, static analysis,
test execution, security validation, domain review, lab validation, packaging, signing, registration,
installation, and enablement remain separate gates.

## Consequences

- The first Builder pilot aligns with the existing Python platform and restricted-network toolchain.
- Useful manifests, schemas, source drafts, tests, documentation, and traceability can be produced
  before the runtime SDK is implemented.
- Generated handlers intentionally contain no target-operation implementation.
- A future language profile or model-assisted generator requires a new ADR and equivalent contract
  coverage.
- Generated projects do not receive a reduced review path because they are deterministic.

## Rejected Alternatives

- Generate directly into the Atlas repository: rejected because generated output must stay quarantined.
- Execute generated code during generation: rejected because validation is a later isolated stage.
- Require a live LLM for the first profile: rejected because deterministic restricted-network operation
  and reproducibility are mandatory.
- Generate network-capable clients immediately: rejected because source analysis does not establish
  runtime trust, credential authority, redirect policy, or lab compatibility.
- Package or register the scaffold automatically: rejected because ATLAS-020 lifecycle gates remain
  authoritative.

## Validation

- Exact source and human-design binding with canonical digests
- Deterministic file inventory and per-file content digests
- Safe path, symlink, collision, interruption, and changed-replay tests
- Secret, source-content, network, model, subprocess, dynamic-execution, and runtime-authority denial
- Python syntax parsing without importing or executing generated modules
- Local and PostgreSQL metadata persistence parity

