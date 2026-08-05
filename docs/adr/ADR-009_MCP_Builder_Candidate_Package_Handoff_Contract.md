# ADR-009: MCP Builder Candidate Package Handoff Contract

- Status: Accepted
- Date: 2026-08-05
- Decision owners: Product Owner, Architecture Owner, Security Owner
- Governing documents: ATLAS-003, ATLAS-020, ATLAS-021, ATLAS-022, ATLAS-025,
  ATLAS-032, ATLAS-033, ATLAS-047, ATLAS-050, ATLAS-051, ATLAS-053, ATLAS-056,
  ADR-004, ADR-005, ADR-006, ADR-007, ADR-008

## Context

ADR-008 produces immutable evidence that the exact deterministic connector scaffold passed its
bounded synthetic lab profile. It does not create a transportable artifact, package digest, custody
record, review packet, signature, registry entry, installation, or runtime authority.

ATLAS-022 requires an exact candidate package handoff before ATLAS-020 acquisition and registration
can begin. That handoff must preserve the complete Builder lineage and remain visibly quarantined.
It cannot silently convert successful Builder evidence into a trusted or executable connector.

## Decision

Atlas records the first candidate handoff under profile `atlas.candidate-handoff.python312.v1` and
archive contract `mcp-builder-candidate-zip.v1`.

A handoff requires a passed `atlas.lab-validation.python312.v1` result and binds the exact project,
source, design checkpoint, generation, generated artifact, static validation, domain review,
security review, lab validation, organization, environment, and authenticated multi-factor human
package custodian. Creation, read, and artifact download use dedicated permissions. The custodian
must differ from the domain reviewer, security reviewer, and lab operator. AI, service, wrong-scope,
insufficient-assurance, self-custody, and unassigned identities fail closed.

Before packaging, Atlas rereads every generated file through the quarantine publisher and confirms
its immutable path, media type, byte size, SHA-256 digest, deterministic regeneration, language
profile, template, and complete inventory. It also verifies every upstream canonical digest and
accepted or passed state. Missing, changed, extra, stale, unsupported, failed, or unreadable evidence
blocks handoff creation.

The package is a deterministic ZIP archive. Entries use normalized relative POSIX paths, fixed
timestamps and permissions, stable ordering, no symbolic links, no path traversal, no duplicate
names, no compression-dependent variability, and bounded entry and archive sizes. It contains only
the exact verified generated scaffold plus `ATLAS-CANDIDATE-HANDOFF.json`. That envelope records the
schema and contract versions, complete upstream IDs and digests, capability/risk/permission/network
summaries, generated-versus-manual change counts, limitations, unsupported behavior, custodian,
tenant, and explicit no-authority flags. It contains no source document bodies, credentials, target
addresses, raw child output, session material, or secret values.

The archive SHA-256 digest and size are calculated from the final bytes. Publication is
content-addressed, immutable, idempotent, concurrency-safe, and path confined. Every download
rereads and verifies the recorded digest and size before returning a bounded attachment with
`application/zip`, `nosniff`, and `no-store` headers. Audit is required for create, read, and download.
Audit or persistence failure cannot fabricate a successful handoff or disclose an artifact.

The handoff state is `candidate_quarantined`. Signature state is explicitly `unsigned`; Builder does
not own a signing key and does not claim publisher identity. The result sets candidate-package
creation true only for this exact quarantined archive. Connector registration, package validation
under ATLAS-020, signing, installation, enablement, target configuration, credential resolution,
runtime trust, execution approval, deployment approval, and infrastructure mutation remain false.

## Consequences

- A passed Builder chain can produce a reproducible, integrity-verifiable artifact for controlled
  transfer to the separate ATLAS-020 acquisition and validation lifecycle.
- Package consumers can inspect complete evidence and limitations without trusting mutable Builder
  database state or receiving sensitive inputs.
- The first profile preserves generated files exactly and records zero manual changes. A later manual
  change profile requires a new ADR, diff contract, renewed validation, and renewed human reviews.
- The archive is intentionally unsigned. Signing and publisher attestation belong to a later
  controlled release or internal registry boundary.
- Deleting or corrupting the content-addressed archive causes download failure; it never falls back to
  regeneration under an existing handoff identity.

## Rejected Alternatives

- Register directly after lab success: rejected because Builder evidence is not ATLAS-020 package
  validation or environment approval.
- Mark the generated folder itself as the package: rejected because transfer needs deterministic bytes,
  an exact digest, and an immutable custody envelope.
- Sign with an application-local or development key: rejected because that would misrepresent
  publisher identity and production trust.
- Include raw source documents or lab output: rejected because the handoff needs references and
  digests, not potentially sensitive or unbounded content.
- Permit manual edits during packaging: rejected because prior static, domain, security, and lab
  evidence binds the exact deterministic generated scaffold.

## Validation

- Domain invariants and canonical digest tests
- Exact upstream lineage, state, profile, contract, capability, tenant, and custodian binding tests
- Deterministic archive byte and digest tests across repeated construction
- Entry ordering, timestamp, mode, path, duplicate, symlink, count, and size-bound tests
- Artifact tamper, stale evidence, failed lab, unsupported profile, and missing archive tests
- Idempotency, concurrent replay, audit-before-persist, memory/PostgreSQL equivalence, and migration tests
- Content-addressed filesystem publication, integrity reread, confinement, and cleanup tests
- Strict create/read/download API, CSRF, RBAC, MFA, tenant, acknowledgement, and separation tests
- Desktop, 390-pixel mobile, browser-log, live API, and downloaded archive inspection
