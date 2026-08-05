# ADR-006: MCP Builder Domain Review Contract

| Field | Value |
| --- | --- |
| Status | Accepted |
| Decision Date | 2026-08-05 |
| Decision Owner | Project Atlas Architecture |
| Related Documents | ATLAS-003, ATLAS-020, ATLAS-021, ATLAS-022, ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-046, ATLAS-047, ATLAS-050, ATLAS-055, ATLAS-056, ADR-004, ADR-005 |
| Supersedes | None |

## Context

ADR-005 supplies immutable static evidence for an exact quarantined MCP Builder scaffold. ATLAS-022
requires a qualified domain reviewer to inspect vendor semantics, product applicability,
authentication, permissions, side effects, operational impact, error behavior, evidence quality,
and health guidance before security review or lab validation can begin.

Static checks cannot prove vendor behavior. Domain review must therefore remain an accountable human
decision that cites the analyzed source and records uncertainty without changing generated files or
granting downstream authority.

## Decision

Atlas records domain review under profile `atlas.domain-review.connector.v1` and reviewer contract
version `mcp-builder-domain-review.v1`.

A review is bound to the exact project and source digests, design checkpoint, generation and artifact
digests, static-validation report and validator versions, capability set, organization, environment,
and authenticated multi-factor human reviewer. Creation requires the dedicated domain-review
permission; AI, service, wrong-scope, insufficient-assurance, and unassigned identities fail closed.

Each generation-eligible capability receives one of three decisions:

- `accepted`: the reviewer confirms the bounded vendor semantics for this candidate.
- `needs_evidence`: one or more declared gaps prevent acceptance.
- `rejected`: the candidate is unsuitable or contradicts authoritative domain evidence.

Every capability decision records:

- Candidate identity and confirmed capability class
- Supported product versions
- Vendor permission and authentication assessment
- Side-effect and operational-impact assessment
- Error, timeout, asynchronous, pagination, and rate-behavior assessment
- Evidence citations restricted to the analyzed source lineage
- Stable missing-case codes and bounded human rationale

The overall state is `accepted` only when every generation-eligible capability is accepted and no
blocking evidence gap remains. Any rejected capability makes the review `rejected`; otherwise any
`needs_evidence` capability makes it `needs_evidence`. The record is immutable, deterministic,
idempotent, audit-before-persist, and one-to-one with the exact static validation report. Changed
source, design, generation, artifact, or validation evidence requires a new Builder lifecycle.

An accepted domain review proves only that the accountable reviewer accepted the recorded semantic
assessment. It does not perform or satisfy security review, dependency resolution, runtime self-test,
lab validation, packaging, signing, registration, installation, enablement, target connection,
execution, deployment, or infrastructure mutation.

## Consequences

- Domain accountability and evidence gaps are visible per capability rather than hidden in free-form
  comments.
- Static validation remains a mandatory prerequisite and cannot be bypassed by human assertion.
- Review acceptance can become an input to later security review while granting no runtime trust.
- A `needs_evidence` or `rejected` outcome remains durable evidence and blocks lifecycle advancement.
- Organizations map the dedicated permission to qualified vendor or platform-domain groups through
  enterprise identity governance.

## Rejected Alternatives

- Let the LLM approve vendor semantics: rejected because domain accountability must remain human.
- Treat a passing static report as domain acceptance: rejected because syntax and structure do not
  prove vendor behavior.
- Store only one overall free-form decision: rejected because capability-level gaps, evidence, and
  risk classifications must remain traceable.
- Allow review to edit generated files: rejected because review evidence and artifact mutation are
  separate lifecycle events.
- Advance directly to packaging after domain acceptance: rejected because security and lab gates
  remain mandatory.

## Validation

- Exact project, checkpoint, generation, artifact, static-report, capability, scope, MFA, and reviewer
  permission binding
- Capability-level accepted, needs-evidence, and rejected derivation with bounded evidence citations
- Immutable canonical digest, idempotent replay, concurrency, audit-before-persist, and PostgreSQL
  parity
- Strict no-store API and web review with explicit human acknowledgement and downstream-boundary
  display
- Proof that security, lab, package, registration, installation, runtime trust, execution, and
  infrastructure authority remain false
