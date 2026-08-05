# ADR-012: Connector Package Content and Dependency Inventory Contract

- Status: Accepted
- Date: 2026-08-05
- Decision owners: Product Owner, Architecture Owner, Security Owner
- Governing documents: ATLAS-003, ATLAS-020, ATLAS-021, ATLAS-022, ATLAS-025,
  ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-047, ATLAS-050, ATLAS-051,
  ATLAS-053, ATLAS-055, ATLAS-056, ADR-009, ADR-010, ADR-011

## Context

ADR-011 independently verifies the exact acquired archive, Builder handoff envelope, canonical
manifest, and generated JSON Schemas, then records a bounded report in lifecycle `validating`.
ATLAS-020 next requires package-content and dependency inspection before secret, malware, license,
static-code, contract, runner, and laboratory validation.

Package inventory is a trust prerequisite for later scanners. A later finding is not reproducible
unless every scanned file and dependency declaration is bound to an exact package digest. This
stage must therefore normalize supply-chain input without claiming that the content is safe.

## Decision

Atlas adopts inventory profile `atlas.connector-supply-chain-inventory.python312.v1` and inspector
version `atlas.connector-content-dependency-inspector.v1` for passed reports produced by
`atlas.connector-validation-intake.builder-v1`.

A dedicated authenticated multi-factor human supply-chain inventory operator initiates the stage
in the exact package organization and environment. The operator differs from the acquisition and
manifest/schema validation operators and every Builder custodian, domain reviewer, security
reviewer, and lab operator in the lineage. AI, service, wrong-scope, insufficient-assurance,
prior-stage, and unauthorized identities fail closed without package, file, dependency, or finding
discovery.

Before inventory, Atlas verifies the prior validation report canonical digest, passed outcome,
supported profile and validator, exact acquisition and package lineage, no-authority invariants,
and immutable source archive digest and size. It independently reopens the archive and enforces the
same bounded ZIP, fixed metadata, normalized path, duplicate, and regular-file contracts. Failure
at this trust prerequisite creates no inventory report.

The deterministic read-only stage then:

1. Records every archive entry in ordinal path order with relative path, SHA-256 digest, byte size,
   and one bounded content class: provenance, manifest, build metadata, documentation, source,
   configuration schema, capability schema, contract test, or synthetic fixture.
2. Requires the Python 3.12 generated profile inventory to remain inside its exact top-level files
   and roots. Missing, duplicate, empty, unclassified, case-colliding, or profile-extraneous entries
   produce a failed stage report.
3. Parses `pyproject.toml` with the standard TOML parser and an exact bounded key contract. It binds
   project identity, Python range, build backend, build requirements, runtime dependency
   declarations, and test/lint/type configuration to the generated profile.
4. Normalizes direct runtime and build dependency declarations into name, version constraint,
   dependency kind, and source file evidence without resolving a package index, downloading an
   artifact, importing code, or executing a build.
5. Records dependency-lock presence and normalized lock-file digests when present. For the first
   generated profile, an empty runtime dependency set is accepted and reported explicitly; build
   requirement resolution and artifact trust remain incomplete.
6. Computes deterministic inventory and dependency-set digests so every later scanner can prove it
   consumed the exact same normalized input.

The immutable report records lifecycle `validating`, passed or failed inventory outcome, complete
source lineage, operator, profile and inspector versions, bounded file and dependency evidence,
inventory and dependency digests, safe checks, limitations, and explicit no-authority flags. It
never returns file bodies, TOML bodies, source snippets, fixture contents, credentials, or secret
values.

Reports are one-to-one with the exact passed manifest/schema report, deterministic, immutable,
idempotent, concurrency-safe, and audit-before-persist. Prior records and archive bytes are not
mutated. Trust, parse, audit, or persistence failure cannot fabricate success. Inventory defects
produce a persisted failed report with safe findings and do not register or reject the connector.

Strict no-store APIs use dedicated create and read permissions, default-deny authorization,
browser CSRF for creation, bounded schemas, correlation, exact tenant scope, safe errors, explicit
untrusted-content acknowledgement, and separation of duties. The Connector workspace presents the
inventory, dependencies, checks, and limitations without later-stage action controls.

This slice does not perform vulnerability, malware, embedded-secret, prohibited-content, license,
source-provenance, static-code, permission-behavior, contract, mock-target, runner, self-test, or
lab validation. It does not resolve or download dependencies, contact a package index, build,
import, sign, attest, reject, register, approve, install, enable, configure, trust, execute, deploy,
or mutate a connector or infrastructure.

## Consequences

- Later scanners receive a canonical content and dependency input bound to one package digest.
- A passed inventory means completeness and deterministic normalization, not supply-chain safety.
- Unknown files and dependency declarations remain visible as failed bounded evidence rather than
  being silently ignored.
- The first profile can inventory zero runtime dependencies without implying build-dependency trust.
- Other language profiles and non-Builder layouts require separate inventory profiles.

## Rejected Alternatives

- Combine every supply-chain scanner into one stage: rejected because one unavailable detector
  would obscure which trust decision is incomplete.
- Treat the ZIP filename list as sufficient evidence: rejected because later scanners require exact
  per-entry digests, sizes, and classifications.
- Resolve dependencies during inventory: rejected because network resolution and downloaded
  artifacts require separate governed source and trust controls.
- Mark an empty runtime dependency list as vulnerability-safe: rejected because build requirements,
  bundled code, and later artifacts still require independent validation.
- Return file or TOML bodies in the report: rejected because bounded normalized metadata is enough
  for evidence and reduces disclosure.
- Let the manifest/schema validator inventory its own output: rejected because sequential registry
  stages require independent accountability.

## Validation

- Domain invariant, canonical inventory, dependency normalization, and safe finding tests
- Exact prior-report, acquisition, package, archive, path, digest, and tenant binding
- Missing, duplicate, empty, case-colliding, unclassified, extraneous, malformed TOML, extension-key,
  dependency, stale, changed, corrupt, and oversized adversarial fixtures
- Dedicated permission, MFA, human identity, acknowledgement, scope, and full-lineage separation tests
- Passed and failed immutable reports, idempotency, concurrency, and audit-before-persist
- Memory and PostgreSQL repository equivalence with one Alembic head
- Strict create/read API, CSRF, safe error, no-store, and response-minimization tests
- Web, desktop, 390-pixel mobile, live HTTP, and browser-log validation
