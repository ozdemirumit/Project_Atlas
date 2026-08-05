# ADR-014: Connector Configuration and Capability Schema Semantics Contract

- Status: Accepted
- Date: 2026-08-05
- Decision owners: Product Owner, Architecture Owner, Security Owner
- Governing documents: ATLAS-003, ATLAS-020, ATLAS-021, ATLAS-022, ATLAS-025,
  ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-047, ATLAS-050, ATLAS-051,
  ATLAS-053, ATLAS-055, ATLAS-056, ADR-009 through ADR-013

## Context

ADR-011 verifies the syntax, version, identity, and package binding of generated configuration and
capability schema files. ADR-013 then proves that the exact inventoried package contains no detected
secret or prohibited content. Neither stage proves that the schemas are complete, restrictive, or
safe enough to form a runtime contract. ATLAS-020 validation pipeline step 5 requires this separate
semantic decision before implementation behavior is inspected.

Generated draft schemas may intentionally contain empty input models, open output objects, or
`draft_requires_schema_review` markers. These are valid quarantine artifacts but cannot be treated
as registration-ready contracts.

## Decision

Atlas adopts semantic-validation profile
`atlas.connector-schema-semantics.python312.v1` and validator version
`atlas.connector-configuration-capability-schema-validator.v1`.

A dedicated authenticated multi-factor human schema-validation operator initiates the stage in the
exact package organization and environment. The operator differs from every Builder, acquisition,
manifest-validation, inventory, and content-policy actor. AI, service, prior-stage, wrong-scope,
insufficient-assurance, and unauthorized identities fail closed without package or report discovery.

The stage accepts only an exact passed ADR-013 report with `promotion_blocked=false`. Atlas verifies
the complete validation, acquisition, inventory, package, actor, tenant, digest, completion, and
no-authority lineage before independently rereading the immutable archive. The archive and every
schema path, digest, size, and content class must reconcile exactly with the passed inventory.

The validator uses a bounded, deterministic, offline JSON Schema 2020-12 subset. It does not resolve
remote references, execute custom formats, import connector code, contact a target, or invoke a
model. Unsupported or ambiguous keywords fail closed.

Configuration schemas must:

- have a closed object root and unique, bounded, safely named properties;
- declare each manifest configuration key and secret-reference identifier exactly once;
- use supported scalar or bounded collection types with coherent required/default rules;
- provide applicable enum, length, numeric, pattern, and collection limits without contradictions;
- classify ordinary values as non-sensitive and secret fields only as opaque
  `atlas-secret-reference` values; and
- contain no literal credentials, secret defaults, remote references, composition escape hatches,
  executable annotations, or unknown extension keywords.

Capability input and output schemas must:

- bind one-to-one to each manifest capability identifier and direction;
- use closed object roots, explicit bounded properties, and coherent required fields;
- contain neither unresolved draft-review markers nor empty placeholder contracts;
- reject remote references, recursive or ambiguous composition, unbounded strings or collections,
  and unknown extension keywords;
- preserve secret-reference-only handling where a secret handle is explicitly declared; and
- expose typed, bounded output evidence without permissive `additionalProperties=true` payloads.

This stage validates only declarative schema semantics. It does not claim that implementation code
honors the declarations; permission, network, risk, static analysis, contract, mock-target, runner,
self-test, and lab stages remain separate.

The immutable report records passed or failed outcome, exact upstream lineage, validator identity,
configuration and capability summaries, bounded safe findings, canonical digest, operator, tenant,
time, limitations, `promotion_blocked`, and every no-authority flag. Findings identify only a stable
rule code, severity, schema path, bounded JSON Pointer, summary, and remediation. Raw schema bodies,
defaults, patterns, enum values, examples, and secret-like content never enter reports, audit, logs,
errors, or model context.

Reports are one-to-one, deterministic, immutable, idempotent, concurrency-safe, and
audit-before-persist. A failed semantic report blocks promotion but does not reject, register,
approve, install, enable, configure, trust, execute, deploy, or mutate a connector or infrastructure.

Strict no-store APIs use dedicated create/read permissions, default-deny authorization, browser
CSRF for creation, exact tenant scope, bounded schemas, correlation, safe errors, explicit
acknowledgement, and separation of duties. The Connector workspace presents report evidence and
limitations without later-stage or operational controls.

## Consequences

- Syntactically valid generated drafts can fail safely until humans provide complete contracts.
- Runtime input and output contracts cannot inherit open-ended or unbounded package schemas.
- Later behavior validation receives immutable, attributable semantic evidence.
- Additional JSON Schema features require a versioned profile and ADR rather than silent acceptance.

## Rejected Alternatives

- Treat ADR-011 schema inspection as semantic approval: rejected because it intentionally accepts
  generated review placeholders.
- Use unrestricted third-party reference resolution: rejected because validation must remain offline
  and deterministic.
- Rewrite schemas automatically: rejected because this stage validates evidence and has no package
  mutation authority.
- Include raw schema fragments in findings: rejected because bounded paths and rule codes are
  sufficient and reduce disclosure risk.
- Infer capability schemas from implementation code: rejected because behavior comparison belongs
  to later validation stages.

## Validation

- Exact passed-content-policy and immutable archive/inventory lineage tests
- Configuration type, required/default, bound, secret-reference, and unsupported-keyword tests
- Capability identity, direction, closed-object, bounded-property, and placeholder tests
- Safe findings and non-disclosure tests for defaults, patterns, enums, and package bodies
- Dedicated permission, MFA, human identity, acknowledgement, scope, and separation tests
- Passed and failed immutable reports, idempotency, concurrency, and audit-before-persist
- Memory and PostgreSQL repository equivalence with one Alembic head
- Strict create/read API, CSRF, no-store, safe-error, and response-minimization tests
- Web, desktop, 390-pixel mobile, live HTTP, and browser-log validation
