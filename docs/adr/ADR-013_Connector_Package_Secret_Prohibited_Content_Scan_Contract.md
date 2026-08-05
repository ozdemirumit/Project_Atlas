# ADR-013: Connector Package Secret and Prohibited-Content Scan Contract

- Status: Accepted
- Date: 2026-08-05
- Decision owners: Product Owner, Architecture Owner, Security Owner
- Governing documents: ATLAS-003, ATLAS-020, ATLAS-021, ATLAS-022, ATLAS-025,
  ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-047, ATLAS-050, ATLAS-051,
  ATLAS-053, ATLAS-055, ATLAS-056, ADR-009, ADR-010, ADR-011, ADR-012

## Context

ADR-012 records a complete, deterministic inventory of every file and dependency declaration in
the exact acquired connector package. ATLAS-020 validation pipeline step 4 next requires Atlas to
detect embedded secret material and prohibited files before later schema, behavior, static,
dependency, contract, runner, and laboratory validation.

This stage necessarily reads untrusted package bodies, but its durable evidence must never become
a second secret store or disclose matched content through an API, audit event, log, exception, or
model context. A failed scan must block further promotion without independently changing connector
lifecycle state.

## Decision

Atlas adopts scan profile `atlas.connector-content-policy-scan.python312.v1` and scanner version
`atlas.connector-secret-prohibited-content-scanner.v1` for exact passed reports produced by
`atlas.connector-supply-chain-inventory.python312.v1`.

A dedicated authenticated multi-factor human content-policy operator initiates the stage in the
exact package organization and environment. This operator differs from every Builder actor and all
acquisition, validation, and inventory actors in the lineage. AI, service, wrong-scope,
insufficient-assurance, prior-stage, and unauthorized identities fail closed without package,
inventory, path, finding, or digest discovery.

Before scanning, Atlas verifies the inventory canonical digest, passed outcome, supported profile
and inspector, exact validation/acquisition/package lineage, complete per-file evidence, inventory
and dependency digests, and every no-authority invariant. Atlas independently rereads and verifies
the immutable archive, then requires every archive path, digest, size, and content class to match
the exact passed inventory. Failure at this trust prerequisite creates no scan report.

The deterministic, offline, read-only stage then:

1. Decodes only inventory-classified textual files as strict UTF-8 within existing per-file and
   package bounds. Unsupported or ambiguous content fails closed.
2. Detects bounded high-confidence credential material including private-key headers, known token
   prefixes, authorization literals, credential-bearing URLs, and sensitive assignments containing
   non-placeholder literal values. Opaque `secret.*` references, declared credential-reference
   field names, empty values, and documented synthetic placeholders are not secret values.
3. Rejects prohibited paths, extensions, nested archives, executable or bytecode signatures,
   control characters, and content that conflicts with its passed inventory class. Static source
   behavior, dependency vulnerabilities, licenses, malware classification, and prompt-injection
   analysis remain later independent stages.
4. Emits safe findings containing only a stable detector code, severity, normalized relative path,
   line number where available, remediation, and a salted one-way evidence fingerprint. Matched
   text, surrounding source, decoded bodies, offsets, secret length, and reversible hashes are
   never persisted or returned.
5. Produces deterministic content and finding-set digests bound to the exact package and inventory.

The immutable report records lifecycle `validating`, passed or failed outcome, promotion-blocked
state, complete source lineage, dedicated operator, profile and scanner versions, bounded checks,
safe findings, limitations, and explicit no-authority flags. A failed outcome sets
`promotion_blocked=true`; it does not set `connector_rejected` or mutate a package, registry, or
connector. A passed outcome means only that this bounded detector found no embedded secret or
prohibited-content evidence.

Reports are one-to-one with the exact passed inventory, deterministic, immutable, idempotent,
concurrency-safe, and audit-before-persist. Trust, decode, audit, or persistence failure cannot
fabricate success. The audit event records stable IDs, outcome, and finding count only.

Strict no-store APIs use dedicated create and read permissions, default-deny authorization,
browser CSRF for creation, bounded schemas, correlation, exact tenant scope, safe errors, explicit
untrusted-content acknowledgement, and full-lineage separation of duties. The Connector workspace
shows scan outcome, safe findings, checks, limitations, and promotion state without exposing
matched content or a later-stage action control.

This slice performs no vulnerability, malware, license, provenance, static-code,
permission-behavior, schema-semantic, contract, mock-target, runner, self-test, or lab validation.
It does not resolve dependencies, contact a network, invoke a model, build, import, execute, sign,
attest, reject, register, approve, install, enable, configure, trust, deploy, or mutate a connector
or infrastructure.

## Consequences

- Later stages receive a reproducible policy result bound to exact inventory and package digests.
- Secret-bearing test fixtures are prohibited; scanner tests use synthetic values created only in
  memory and assert that raw values never cross report, audit, API, log, or exception boundaries.
- High-confidence deterministic rules reduce disclosure and false positives but do not claim
  exhaustive secret, malware, or behavioral safety.
- Failed scans block promotion while preserving lifecycle authority for a later designated service.
- Other language profiles and package layouts require separate accepted scan profiles.

## Rejected Alternatives

- Persist matched text for reviewer convenience: rejected because the report would become a secret
  disclosure channel.
- Return a plain pass/fail flag: rejected because enterprise review needs safe, reproducible,
  actionable evidence.
- Combine malware, vulnerability, license, and static analysis here: rejected because each stage has
  different tooling, failure semantics, and trust claims.
- Let the inventory operator scan its own report: rejected because sequential stages require
  independent accountability.
- Automatically reject or delete a failed package: rejected because detection is not lifecycle
  authority and evidence must remain available under retention policy.

## Validation

- Domain invariants, deterministic digests, safe finding shape, and no-authority tests
- Exact inventory, archive, file, digest, class, package, lineage, and tenant binding
- Private key, token, authorization literal, credential URL, sensitive assignment, placeholder,
  secret-reference, binary signature, nested archive, prohibited path, encoding, and control-byte cases
- Raw-secret non-disclosure across domain representation, audit, API, errors, and persisted evidence
- Dedicated permission, MFA, human identity, acknowledgement, scope, and full-lineage separation tests
- Passed and failed immutable reports, idempotency, concurrency, and audit-before-persist
- Memory and PostgreSQL repository equivalence with one Alembic head
- Strict create/read API, CSRF, safe error, no-store, and response-minimization tests
- Web, desktop, 390-pixel mobile, live HTTP, and browser-log validation
