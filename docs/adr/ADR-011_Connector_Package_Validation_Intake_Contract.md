# ADR-011: Connector Package Validation Intake Contract

- Status: Accepted
- Date: 2026-08-05
- Decision owners: Product Owner, Architecture Owner, Security Owner
- Governing documents: ATLAS-003, ATLAS-020, ATLAS-021, ATLAS-022, ATLAS-025,
  ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-047, ATLAS-050, ATLAS-051,
  ATLAS-053, ATLAS-055, ATLAS-056, ADR-009, ADR-010

## Context

ADR-010 transfers exact MCP Builder package bytes into connector quarantine and records an
immutable acquisition receipt. It deliberately performs no registry validation. ATLAS-020 next
requires integrity and allowed-source acceptance before a package enters `validating`, followed by
manifest and schema inspection before later supply-chain, static, contract, runner, and lab stages.

The first validation slice must independently consume acquired bytes, preserve separation of
duties, and produce attributable deterministic evidence without treating a partial stage as
registration approval or runtime trust.

## Decision

Atlas adopts validation profile `atlas.connector-validation-intake.builder-v1` and validator
version `atlas.connector-manifest-schema-validator.v1` for exact acquisitions produced by
`atlas.connector-acquisition.builder-handoff.v1`.

A dedicated authenticated multi-factor human package validation operator initiates the stage in
the exact acquisition organization and environment. The operator differs from the acquisition
operator and every Builder custodian, domain reviewer, security reviewer, and lab operator bound to
the acquisition. AI, service, wrong-scope, insufficient-assurance, prior-stage, and unauthorized
identities fail closed without acquisition, archive, manifest, schema, or finding discovery.

Before creating a validation report, Atlas verifies the acquisition canonical digest, supported
source and profile, quarantined unsigned and unattested state, every no-authority invariant, and
the exact content-addressed archive digest and size. It independently enforces the ZIP contract,
safe paths, fixed metadata, bounded regular-file entries, unique ordinal inventory, and handoff
envelope binding. Failure at this trust prerequisite creates no validation report.

After source acceptance, Atlas performs deterministic read-only checks against the exact bytes:

1. Require one bounded `atlas-connector.yaml` manifest and parse its canonical JSON form with
   duplicate-key rejection, exact allowed keys, bounded types, and no hidden extension fields.
2. Require the generated-draft schema version, SDK profile, semantic draft version, quarantined
   status, and explicit false runtime-trust and execution-authority flags.
3. Bind manifest capabilities, classes, permissions, products, and network destinations to the
   acquisition receipt and immutable handoff envelope without allowing scope expansion.
4. Require one bounded configuration schema and exact per-capability input/output schemas using
   JSON Schema draft 2020-12, duplicate-key rejection, safe identifiers, object roots, bounded
   properties, and the generated draft-review markers.
5. Bind configuration and secret-reference property names, required fields, and safety markers to
   the manifest. Secret values are neither requested nor resolved.

The immutable stage report records `validating` lifecycle state, passed or failed outcome, exact
acquisition and package lineage, validator profile and version, manifest and schema digests, safe
check results, bounded evidence paths, remediation text, actor, time, tenant, limitations, and
explicit no-authority flags. It never returns raw package files or raw manifest/schema bodies.
Manifest or schema failures produce a persisted failed report with safe findings; they do not
silently reject or register the package.

Reports are one-to-one with the exact acquisition, deterministic, immutable, idempotent,
concurrency-safe, and audit-before-persist. Acquisition and archive records are not mutated. Audit,
source, parse, or persistence failure cannot fabricate success.

Strict no-store APIs use dedicated create and read permissions, default-deny authorization,
browser CSRF for creation, bounded schemas, correlation, exact tenant scope, safe errors, explicit
untrusted-package acknowledgement, and separation of duties. The Connector workspace presents
stage evidence and limitations without signing, attestation, registration, approval, installation,
enablement, configuration, credential, trust, execution, deployment, or mutation controls.

This slice does not claim completion of dependency, vulnerability, malware, secret-content,
license, static-code, permission-behavior, contract, mock-target, runner, self-test, or lab
validation. It does not sign, attest, register, approve, install, enable, configure, trust, execute,
deploy, or mutate a connector or infrastructure.

## Consequences

- The lifecycle can enter `validating` only from an exact accepted acquisition.
- Manifest and schema defects become immutable attributable findings bound to one package digest.
- A failed stage report cannot be interpreted as rejection completion, registration, or approval.
- Later validation stages can consume normalized digests and checks without rereading mutable input.
- Non-Builder packages and alternate manifest formats require separate validation profiles.

## Rejected Alternatives

- Reuse the Builder static validation result: rejected because registry validation must
  independently verify the acquired bytes.
- Validate mutable unpacked files: rejected because all evidence must bind the exact archive digest.
- Register immediately after manifest parsing: rejected because supply-chain, behavior, runner, and
  approval stages remain incomplete.
- Let the acquisition operator validate the same package: rejected because custody and validation
  require independent accountability.
- Resolve secret references during schema inspection: rejected because this stage needs names and
  safety markers only.
- Store raw manifest and schema bodies in the report: rejected because evidence can be represented
  by bounded normalized fields, paths, and digests.

## Validation

- Domain invariant, canonical digest, and safe finding tests
- Exact acquisition, archive, envelope, manifest, capability, product, network, and schema binding
- Missing, duplicate, malformed, oversized, stale, changed, corrupt, unsupported, and extension-key
  adversarial fixtures
- Dedicated permission, MFA, human identity, acknowledgement, scope, and separation tests
- Passed and failed immutable reports, idempotency, concurrency, and audit-before-persist
- Memory and PostgreSQL repository equivalence with one Alembic head
- Strict create/read API, CSRF, safe error, no-store, and response-minimization tests
- Web, desktop, 390-pixel mobile, live HTTP, and browser-log validation
