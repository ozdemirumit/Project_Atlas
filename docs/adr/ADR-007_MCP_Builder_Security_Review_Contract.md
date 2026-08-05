# ADR-007: MCP Builder Security Review Contract

| Field | Value |
| --- | --- |
| Status | Accepted |
| Decision Date | 2026-08-05 |
| Decision Owner | Project Atlas Architecture |
| Related Documents | ATLAS-003, ATLAS-020, ATLAS-021, ATLAS-022, ATLAS-025, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-046, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-053, ATLAS-055, ATLAS-056, ADR-004, ADR-005, ADR-006 |
| Supersedes | None |

## Context

ADR-006 supplies immutable human domain evidence for the exact generated scaffold and vendor
semantics. ATLAS-022 next requires an independent security reviewer to assess provenance,
dependencies, credentials, network behavior, validation boundaries, logging, privileges, and
capability governance before any lab or package lifecycle can begin.

The first Python generation profile has no runtime dependencies and remains quarantined. Security
review can therefore assess the declared scaffold and its immutable evidence without resolving
packages, importing generated code, contacting a target, or claiming that a future candidate package
has been scanned or approved.

## Decision

Atlas records security review under profile `atlas.security-review.connector.v1` and reviewer
contract version `mcp-builder-security-review.v1`.

A review requires an accepted `atlas.domain-review.connector.v1` record and binds the exact project,
source, design checkpoint, generation, artifact, static-validation report, domain-review record,
organization, environment, and authenticated multi-factor human security reviewer. Creation requires
the dedicated security-review permission. The security reviewer must be different from the domain
reviewer. AI, service, wrong-scope, insufficient-assurance, self-review, and unassigned identities
fail closed.

Exactly one structured assessment is required for each control:

- `provenance`: source, generation, artifact, and review lineage
- `supply_chain`: declared dependencies, lock state, licenses, and build hooks
- `credentials`: secret references, credential handling, and secret-exposure boundaries
- `network`: declared destinations, redirects, TLS, proxy, and egress boundaries
- `input_output`: schema, size, encoding, untrusted response, and output bounds
- `injection_execution`: command, path, query, template, deserialization, and dynamic-code risks
- `logging_redaction`: telemetry, error, audit, and sensitive-value redaction
- `runner_privileges`: filesystem, process, resource, identity, and least-privilege boundaries
- `capability_governance`: capability classes, target permissions, side effects, and later approvals

Each assessment records an `accepted`, `needs_remediation`, or `rejected` decision, bounded human
analysis, exact evidence references restricted to upstream source citations or artifact inventory,
stable finding codes, and required controls. Accepted assessments cannot retain findings. A
non-accepted assessment must identify at least one finding and required control.

The overall state is `accepted` only when all nine controls are accepted. Any rejected control makes
the review `rejected`; otherwise any needs-remediation control makes it `needs_remediation`. The
review is immutable, deterministic, idempotent, audit-before-persist, and one-to-one with the exact
accepted domain review. Changed upstream evidence requires a new Builder lifecycle.

An accepted security review proves only that the independent reviewer accepted the recorded security
posture of this exact quarantined scaffold. It does not perform dependency resolution, malware or
dynamic scanning, runtime self-test, lab validation, package creation or signing, registration,
installation, enablement, target connection, execution, deployment, or infrastructure mutation.

## Consequences

- Security posture and unresolved findings are explicit per control rather than hidden in prose.
- Domain acceptance is mandatory but cannot substitute for independent security judgment.
- The empty dependency set of the first profile is reviewed as declared evidence; any future
  dependency requires a new compatible validation and security-review profile.
- An accepted review can become an input to isolated lab validation while granting no runtime trust.
- Needs-remediation and rejected outcomes remain durable evidence and block lifecycle advancement.

## Rejected Alternatives

- Let the Builder agent approve its own output: rejected because generated artifacts cannot validate
  or approve themselves.
- Reuse the domain reviewer as security reviewer: rejected because independent security judgment and
  separation of duties are required.
- Treat static validation as security approval: rejected because structure and bounded static checks
  do not establish the complete security posture.
- Resolve dependencies or contact targets during review: rejected because review is an evidence gate,
  not an execution or lab environment.
- Allow partial acceptance to advance: rejected because unknown and unresolved controls are not
  success.

## Validation

- Exact upstream digest, accepted-domain-review, tenant, MFA, permission, and separation-of-duties
  binding
- Complete nine-control accepted, needs-remediation, and rejected derivation with evidence-lineage
  enforcement
- Immutable canonical digest, idempotent replay, concurrency, audit-before-persist, and PostgreSQL
  parity
- Strict no-store API and web review with explicit human acknowledgement and no persuasive defaults
- Proof that lab, package, registration, installation, target, runtime, execution, and infrastructure
  authority remain false
