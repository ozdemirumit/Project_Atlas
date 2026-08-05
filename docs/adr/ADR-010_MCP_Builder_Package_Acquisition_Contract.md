# ADR-010: MCP Builder Package Acquisition Contract

- Status: Accepted
- Date: 2026-08-05
- Decision owners: Product Owner, Architecture Owner, Security Owner
- Governing documents: ATLAS-003, ATLAS-020, ATLAS-021, ATLAS-022, ATLAS-025,
  ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-047, ATLAS-050, ATLAS-051,
  ATLAS-053, ATLAS-055, ATLAS-056, ADR-009

## Context

ADR-009 creates an immutable, unsigned, quarantined MCP Builder candidate archive. It does not
transfer package custody into the ATLAS-020 connector lifecycle. ATLAS-020 requires package
acquisition to record the allowed source, actor, time, digest, publisher identity, and environment
before registration validation can begin.

The first acquisition boundary must preserve the exact Builder handoff without treating Builder
evidence as registry validation, publisher attestation, package approval, or runtime trust.

## Decision

Atlas accepts the first acquisition profile `atlas.connector-acquisition.builder-handoff.v1` only
from an exact `atlas.candidate-handoff.python312.v1` record and its immutable
`mcp-builder-candidate-zip.v1` archive.

Acquisition is initiated by a dedicated, authenticated, multi-factor human registry intake
operator with create and read permissions in the exact handoff organization and environment. The
intake operator must differ from the Builder package custodian, domain reviewer, security reviewer,
and lab operator. AI, service, wrong-scope, insufficient-assurance, self-transfer, and unauthorized
identities fail closed without disclosing source or archive details.

Before recording acquisition, Atlas rereads the source archive through the Builder archive port,
verifies its recorded size and SHA-256 digest, inspects the bounded handoff envelope, and binds the
complete handoff identity, archive contract, package digest, capability summary, tenant, source
custodian, and intake operator. The archive is copied unchanged into a separate, content-addressed,
path-confined acquisition store. The copied bytes must retain the source digest and size. Atlas
never rebuilds or modifies the package during acquisition.

The immutable acquisition receipt records source type, actor, time, organization, environment,
package filename, exact digest and size, source publisher claim, signature state, publisher
attestation state, quarantine state, and explicit no-authority flags. Builder output has publisher
identity `unattested.generated` until a later controlled attestation boundary. Acquisition remains
idempotent and one-to-one with the exact handoff. Audit succeeds before persistence; archive,
audit, or persistence failure cannot fabricate success.

The acquired package state is `quarantined`. Signature remains `unsigned` and publisher
attestation remains `unattested`. Acquisition does not run dependency, malware, secret, license,
schema, static, contract, mock-target, runner, or lab validation. It does not register, approve,
install, enable, configure, trust, execute, deploy, or mutate a connector or infrastructure.

Strict no-store APIs use dedicated create and read permissions, default-deny authorization,
browser CSRF for creation, bounded schemas, correlation, exact tenant scope, safe errors, explicit
quarantine acknowledgement, and separation of duties. The web workspace exposes custody,
integrity, source, signature, attestation, and no-authority state without presenting signing,
registration, installation, enablement, or execution controls.

## Consequences

- MCP Builder custody and ATLAS-020 registry intake become distinct, attributable stages.
- Validation can consume immutable acquired bytes without trusting mutable Builder state.
- A digest mismatch, missing archive, unsupported profile, changed lineage, or custody conflict
  blocks acquisition and never creates a partial receipt.
- Signing format, publisher attestation mechanism, and registry validation remain later decisions.
- The first profile accepts only MCP Builder output; other acquisition sources require separate
  profiles and threat analysis.

## Rejected Alternatives

- Register directly from the Builder handoff: rejected because acquisition is not validation or
  registration.
- Reuse the Builder custodian as registry intake operator: rejected because custody transfer must
  be attributable and independently controlled.
- Rebuild or normalize the ZIP during acquisition: rejected because all evidence binds exact bytes.
- Apply a development signature: rejected because it would misrepresent publisher identity and
  trust.
- Run the complete validation pipeline in the acquisition request: rejected because validation has
  separate evidence, failure, review, and lifecycle semantics.

## Validation

- Domain invariant and canonical digest tests
- Exact handoff, archive profile, contract, digest, size, capability, and tenant binding tests
- Missing, stale, changed, corrupt, unsupported, and cross-scope source tests
- Dedicated permission, MFA, human identity, acknowledgement, and separation tests
- Immutable content-addressed copy, confinement, idempotency, and concurrency tests
- Audit-before-persist and memory/PostgreSQL equivalence tests
- Strict create/read API, CSRF, safe error, and no-store tests
- Web, desktop, 390-pixel mobile, live HTTP, browser-log, and acquired-byte verification

