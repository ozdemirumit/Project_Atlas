# ADR-015: Connector Declared Authority and Implementation Behavior Contract

- Status: Accepted
- Date: 2026-08-05
- Decision owners: Product Owner, Architecture Owner, Security Owner
- Governing documents: ATLAS-003, ATLAS-020, ATLAS-021, ATLAS-022, ATLAS-025,
  ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-033, ATLAS-047, ATLAS-050, ATLAS-051,
  ATLAS-053, ATLAS-055, ATLAS-056, ADR-009 through ADR-014

## Context

ADR-014 proves that configuration and capability schemas are complete, restrictive, and bound to
the exact package. It does not prove that connector source code honors the manifest's declared
capability classes, target permissions, or network boundary. ATLAS-020 validation pipeline step 6
requires a separate comparison of those declarations to implementation behavior where behavior is
statically testable.

Static inspection is useful evidence but not runtime proof. Dynamic dispatch, native extensions,
dependencies, reflection, generated code, and target-specific behavior can hide side effects. This
stage therefore fails closed on ambiguity and never upgrades static evidence into execution trust.

## Decision

Atlas adopts comparison profile `atlas.connector-authority-behavior.python312.v1` and analyzer
version `atlas.connector-declared-authority-ast-analyzer.v1`.

A dedicated authenticated multi-factor human behavior-validation operator initiates the stage in
the exact package organization and environment. The operator differs from every Builder,
acquisition, manifest-validation, inventory, content-policy, and schema-semantics actor. AI,
service, prior-stage, wrong-scope, insufficient-assurance, and unauthorized identities fail closed
without package or report discovery.

The stage accepts only the exact passed ADR-014 report with `promotion_blocked=false`. Atlas
verifies the complete upstream canonical lineage and no-authority flags, independently rereads the
immutable archive, and reconciles manifest authority declarations, Python source paths, digests,
sizes, and content classes to the passed inventory.

The analyzer parses Python 3.12 source with the standard AST without importing, compiling, or
executing connector code. It uses bounded files, source sizes, AST depth, node counts, findings,
and processing time. Syntax failure, unsupported source layout, excessive complexity, dynamic
import, reflection, generated execution, unresolved indirection, or incomplete capability binding
fails closed.

For every manifest capability, Atlas compares:

- the declared capability class to statically observed read, mutation, process, filesystem,
  dynamic-execution, and network behavior categories;
- the declared required permission to the matching capability module constant;
- the declared capability identifier and class to the matching module constants and one handler;
- the declared network destinations and quarantine authority flags to bounded client construction,
  socket, and request call evidence where behavior can be resolved safely; and
- quarantine, runtime-trust, execution-authority, redirect, broad-administrator, and fail-closed
  declarations to implementation evidence.

C0 and C1 capabilities cannot contain observable mutation, process, filesystem-write, or dynamic
execution behavior. Network behavior is allowed only when explicitly enabled and bound to declared
destinations. Wildcards, credentials in destinations, non-literal destinations, undeclared hosts,
redirect expansion, shell/process launch, filesystem writes, dynamic evaluation, and unbounded or
unresolved calls produce blocking findings. Higher-risk classes still require exact declarations;
this stage records observations but grants no permission or execution authority.

The immutable report records passed or failed outcome, exact upstream lineage, analyzer identity,
per-capability declaration and observation summaries, bounded safe findings, canonical digest,
operator, tenant, time, limitations, `promotion_blocked`, and every no-authority flag. Findings
contain only stable rule code, behavior category, severity, relative path, bounded line number,
evidence fingerprint, summary, and remediation. Source snippets, string literals, destination
values, credentials, arguments, request bodies, and imported content never enter reports, audit,
logs, errors, or model context.

Reports are one-to-one, deterministic, immutable, idempotent, concurrency-safe, and
audit-before-persist. A failed report blocks promotion but does not reject, register, approve,
install, enable, configure, trust, execute, deploy, or mutate a connector or infrastructure.

Strict no-store APIs use dedicated create/read permissions, default-deny authorization, browser
CSRF for creation, exact tenant scope, bounded schemas, correlation, safe errors, explicit
acknowledgement, and separation of duties. The Connector workspace presents declarations,
observations, safe findings, checks, limitations, lineage, and promotion state without source code
or later-stage action controls.

## Consequences

- Manifest authority drift becomes visible before generic static analysis or runtime testing.
- Ambiguous implementation behavior blocks promotion instead of being inferred as safe.
- Passing this stage means only that bounded static evidence matches declared authority.
- Dependency, vulnerability, malware, license, general static-code, contract, runner, self-test,
  and lab validation remain separate later stages.

## Rejected Alternatives

- Execute connector code to observe behavior: rejected because execution belongs to isolated later
  stages and this stage has no runtime trust.
- Treat absence of detected calls as proof of no side effects: rejected because static analysis is
  incomplete by nature.
- Reuse the generic static-analysis stage: rejected because declaration drift is a distinct package
  contract with separate evidence and ownership.
- Return source snippets or destination literals: rejected because rule, path, line, and fingerprint
  evidence is sufficient and reduces disclosure risk.
- Automatically change risk classes or permissions: rejected because validation reports evidence
  and cannot rewrite reviewed authority declarations.

## Validation

- Exact passed-schema-semantics and immutable archive/inventory lineage tests
- Manifest authority declaration, module, and handler one-to-one binding tests
- Python AST tests for network, process, filesystem, mutation, dynamic execution, and ambiguity
- Capability-class, required-permission, network-enablement, and destination comparison tests
- Safe finding and non-disclosure tests for source, literals, URLs, credentials, and arguments
- Dedicated permission, MFA, human identity, acknowledgement, scope, and separation tests
- Passed and failed immutable reports, idempotency, concurrency, and audit-before-persist
- Memory and PostgreSQL repository equivalence with one Alembic head
- Strict create/read API, CSRF, no-store, safe-error, and response-minimization tests
- Web, desktop, 390-pixel mobile, live HTTP, and browser-log validation
