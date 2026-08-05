# ADR-019: Connector Package License Analysis Contract

- Status: Accepted
- Date: 2026-08-05
- Decision owners: Product Owner, Architecture Owner, Security Owner
- Governing documents: ATLAS-003, ATLAS-020, ATLAS-021, ATLAS-022, ATLAS-025,
  ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-047, ATLAS-050, ATLAS-051,
  ATLAS-053, ATLAS-055, ATLAS-056, ADR-009 through ADR-018

## Context

ADR-018 establishes that the exact connector archive and files contain no indicator known to one
trusted malware-definition snapshot. It does not establish that Atlas may use, modify, package, or
redistribute the generated connector, its source documentation, or its dependencies. Licensing
evidence has different ownership, legal-review, policy, disclosure, refresh, and failure semantics,
so it remains an independent promotion gate before connector-contract, runner, and lab validation.

The Builder project records a source-license identifier and whether organizational redistribution
is permitted, but the original package profile did not bind those facts into generated package
metadata. Downstream analysis must not rely on an unbound UI statement or ask an LLM to interpret
raw legal text. The generated package therefore needs deterministic, integrity-protected license
metadata, and the later gate needs a separately governed organizational policy snapshot.

## Decision

Atlas adopts analysis profile `atlas.connector-license-policy.python312.v1`, analyzer version
`atlas.connector-license-policy-analyzer.v1`, policy schema
`atlas.connector-license-policy-snapshot.v1`, and generated-package expression
`LicenseRef-Atlas-Internal-Generated`.

The deterministic Builder generator writes the package expression, source-license identifier, and
source redistribution flag into bounded `pyproject.toml` metadata. Builder static validation checks
that these values exactly match the immutable project record. They are bound transitively through
generation, review, handoff, acquisition, archive, inventory, and all later canonical digests.

A dedicated authenticated multi-factor human license-analysis operator initiates the stage in the
exact package organization and environment. The operator differs from every Builder, acquisition,
manifest-validation, inventory, content-policy, schema-semantics, authority-behavior,
static-dependency, vulnerability-analysis, and malware-analysis actor. AI, service, prior-stage,
wrong-scope, insufficient-assurance, and unauthorized identities fail closed without package,
policy, or report discovery.

The stage accepts only the exact passed ADR-018 report with `promotion_blocked=false`,
`vulnerability_scan_completed=true`, and `malware_scan_completed=true`. Atlas verifies its complete
upstream canonical lineage, every no-authority flag, immutable archive bytes, and exact inventory,
package, and dependency-set digests before analysis.

The caller cannot upload legal text, choose a policy snapshot, classify a license, suppress an
obligation, lower a disposition, or mark an item reviewed. A trusted provider supplies one
registered immutable policy snapshot for the organization and environment. The snapshot records
stable identity/version, issuance/expiry, supported profile/analyzer, canonical digest, signing-key
identity, verified signature, coverage declarations, and bounded normalized policy records.
Policy-record admission, legal approval, refresh, key rotation, exception governance, and retention
remain separate administrative capabilities.

Atlas creates no report for a malformed, unsigned, signature-invalid, digest-invalid,
future-issued, duplicate, conflicting, oversized, wrong-scope, unsupported, or analyzer-incompatible
snapshot. A structurally trusted but expired or coverage-incomplete snapshot creates an immutable
failed report so the evidence gap is visible and promotion remains blocked.

The analyzer reads only the exact verified archive and previously accepted inventory. Standard TOML
parsing extracts the package expression and bounded Atlas source-license metadata. Dependency
subjects come from the exact inventory and static-analysis lineage; package content is never
imported, built, installed, resolved, downloaded, or executed. Missing, ambiguous, conflicting,
unsupported, changed, unbound, or unparsable metadata fails closed.

The initial policy model distinguishes generated-package, source-document, runtime-dependency,
transitive-dependency, build-tool, and dataset subjects. Each trusted record maps a deterministic
subject fingerprint to one disposition: `permitted`, `review_required`, or `prohibited`, plus
bounded obligation codes such as attribution, notice, source-offer, reciprocal-source,
network-source, patent-notice, or internal-use-only. A passing report requires every represented
subject to be covered and permitted and every required obligation to be satisfiable under the exact
package distribution mode. `review_required` and `prohibited` both block promotion; the former does
not fabricate legal approval.

No analysis result is legal advice or a legal conclusion. Passing means only that the represented
metadata matched the exact approved organizational policy snapshot for the recorded internal
distribution mode. Unknown licenses, custom terms, conflicting expressions, missing dependency
evidence, public redistribution, or unsatisfied obligations require an independently recorded legal
or policy decision in a later governed exception process; the scanner cannot create that decision.

Reports never persist or expose raw legal text, license files, notice bodies, file paths, dependency
names/versions/constraints, private source-license identifiers, policy-record bodies, reviewer
notes, or exception rationale. A safe finding contains only public policy-rule identity, category,
severity, subject scope, one-way subject fingerprint, disposition, obligation codes, generic
summary, and remediation. APIs, audit metadata, logs, errors, and model context use only these
minimized fields and aggregate counts.

The immutable report records passed or failed outcome, exact upstream lineage, policy snapshot
identity/version/digest and freshness, analyzer identity, subject/disposition/obligation counts,
safe findings, canonical digest, operator, tenant, time, limitations, `promotion_blocked`, and every
no-authority flag. Reports are one-to-one, deterministic, immutable, idempotent,
concurrency-safe, and audit-before-persist.

A failed report blocks promotion but does not reject, rewrite, delete, repair, relicense, add a
notice, sign, register, approve, install, enable, configure, trust, execute, deploy, or change a
connector or infrastructure. Completion marks only `license_scan_completed=true` while preserving
vulnerability and malware completion; contract, runner, self-test, lab, final validation, approval,
registration, installation, and enablement remain separate later stages.

Strict no-store APIs use dedicated create/read permissions, default-deny authorization, browser
CSRF for creation, exact tenant scope, bounded schemas, correlation, safe errors, explicit
acknowledgement, and full-lineage separation of duties. The Connector workspace presents safe
policy, freshness, coverage, disposition, obligation, limitation, lineage, and promotion summaries
without raw terms, private identifiers, dependency identities, or later-stage action controls.

## Consequences

- Generated packages preserve source-license and redistribution provenance in exact package bytes.
- License-policy conclusions become reproducible and attributable to one approved snapshot.
- Missing, custom, ambiguous, or incompatible terms fail closed instead of being interpreted by an
  LLM or silently accepted.
- Passing remains policy-bound, distribution-mode-bound, metadata-bound, and explicitly not legal
  advice or a substitute for counsel.
- Policy ingestion, legal-review workflows, governed exceptions, obligation artifact generation,
  and public-distribution approval require separate implementation work.

## Rejected Alternatives

- Ask an LLM to read and approve license text: rejected because legal conclusions must be
  deterministic, attributable, policy-governed, and human-accountable.
- Trust only the license value entered in the initial UI: rejected because downstream evidence must
  be bound to exact generated package bytes and reviewed lineage.
- Let the caller select a policy or suppress an obligation: rejected because a caller could
  manufacture a permissive result.
- Treat `review_required` as passing: rejected because absence of prohibition is not approval.
- Rewrite package metadata or generate notices during analysis: rejected because analysis is
  read-only; remediation creates a new package and repeats all prior gates.
- Expose raw terms and dependency identities in normal reports: rejected because minimized policy
  evidence is sufficient at this API boundary and reduces legal and supply-chain disclosure.
- Combine vulnerability, malware, and license results: rejected because their evidence, owners,
  refresh models, reviewers, and failure semantics differ.

## Validation

- Deterministic generated metadata and exact Builder-project binding tests
- Exact passed-malware-report, archive, inventory, dependency-set, and full-lineage tests
- Trusted, invalid, future-issued, expired, incomplete, duplicate, conflicting, oversized,
  wrong-scope, unsupported-profile, and analyzer-incompatible policy snapshot tests
- Permitted, review-required, prohibited, unknown, conflicting, missing, and unsatisfied-obligation
  fixtures across package, source, runtime, transitive, build, and dataset subjects
- Standard TOML parsing, exact metadata, distribution-mode, and no-package-execution tests
- Safe-finding and non-disclosure tests for raw terms, private identifiers, paths, dependency values,
  policy bodies, reviewer notes, and exception rationale
- Dedicated permission, MFA, human identity, acknowledgement, scope, and separation tests
- Passed and failed immutable reports, idempotency, concurrency, and audit-before-persist
- Memory and PostgreSQL repository equivalence with one Alembic head
- Strict create/read API, CSRF, no-store, safe-error, and response-minimization tests
- Web, desktop, 390-pixel mobile, live HTTP, browser-log, and GitHub CI validation
