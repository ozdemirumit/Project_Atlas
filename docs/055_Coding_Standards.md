# Project Atlas

## Coding Standards

| Field | Value |
| --- | --- |
| Document ID | ATLAS-055 |
| Version | 1.0.0 |
| Status | Approved |
| Document Owner | Engineering Enablement Owner |
| Reviewers | Architecture Owner, Backend Engineering, Frontend Engineering, Security Architecture, Platform Engineering, Quality Engineering, AI Architecture, Documentation Owner |
| Approver | Umit Ozdemir (acting Architecture Owner) |
| Approval Date | 2026-08-03 |
| Last Updated | 2026-08-03 |
| Related Documents | [ATLAS-003](003_Project_Principles.md), [ATLAS-011](011_Component_Architecture.md), [ATLAS-020](020_MCP_Framework.md), [ATLAS-032](032_Audit.md), [ATLAS-033](033_Logging.md), [ATLAS-040](040_AI_Agents.md), [ATLAS-047](047_Guardrails.md), [ATLAS-050](050_API.md), [ATLAS-051](051_Backend.md), [ATLAS-052](052_Frontend.md), [ATLAS-053](053_Database.md), [ATLAS-056](056_Testing.md), [ATLAS-058](058_CI_CD.md) |
| Supersedes | ATLAS-055 version 0.1.0 |

## 1. Purpose

This document defines coding and change-quality standards for future Project Atlas implementation.

These standards apply equally to human-authored and AI-generated code. Generated code is untrusted until reviewed, tested, and accepted through the same repository controls.

## 2. Scope

### In Scope

- General code design, readability, types, errors, concurrency, configuration, security, and observability
- Python and TypeScript baselines
- API, database, event, connector, AI, frontend, test, documentation, dependency, and review practices
- Tooling and enforcement expectations

### Out of Scope

- Final formatter, linter, or compiler selection before language ADRs
- Product architecture decisions owned by other documents
- Customer-specific scripts outside the Atlas repository
- Style preferences with no readability, correctness, or consistency benefit

## 3. Objectives

- Produce understandable, secure, testable, and maintainable code
- Preserve domain and trust boundaries
- Make failure and operational state explicit
- Keep changes focused and reviewable
- Prevent secrets, environment assumptions, and vendor details from entering core logic
- Ensure implementation and governed documentation remain synchronized
- Automate objective checks while preserving meaningful human review

## 4. Normative Language

- `must` and `must not` are required for merge.
- `should` and `should not` are strong defaults requiring documented reason when violated.
- `may` identifies an optional compatible choice.
- Tool-generated exceptions do not override these standards.
- Approved ADRs can refine a rule but cannot weaken ATLAS-003 or ATLAS-047 invariants.

## 5. General Principles

- Prefer clear code over clever code.
- Keep changes limited to the requested behavior and affected ownership boundary.
- Model domain concepts explicitly.
- Validate all trust-boundary input.
- Make invalid states difficult or impossible to represent.
- Separate pure domain behavior from I/O and frameworks.
- Return structured outcomes for expected failure.
- Bound time, retries, memory, concurrency, and output.
- Preserve correlation and evidence for operational behavior.
- Delete dead code rather than retaining commented alternatives.
- Add abstractions only when they remove demonstrated complexity or match an established pattern.

## 6. Repository Structure

- Source directories reflect domain modules and runtime components.
- Every module has an owner and public boundary.
- Tests mirror owned behavior without duplicating implementation structure mechanically.
- Generated files live in declared directories and are reproducible.
- Configuration, migrations, schemas, deployment assets, and documentation are versioned.
- Temporary, local, secret, build, and cache files are ignored.
- Large binaries and model assets are not committed without an approved artifact strategy.
- Directory names use consistent lowercase conventions selected by language tooling.

## 7. Naming

- Names communicate domain meaning and avoid unexplained abbreviations.
- Boolean names describe a true condition such as `is_active` or `can_cancel`.
- Commands use verbs; events describe completed facts in past tense.
- Stable API, event, permission, policy, capability, and error identifiers follow their governed naming conventions.
- Avoid generic names such as `data`, `item`, `manager`, `helper`, or `utils` when a domain term exists.
- Vendor-specific names remain inside adapters unless preserving source evidence.
- Secrets and sensitive fields use names that enable scanners and redaction.

## 8. Functions and Methods

- One function has one coherent responsibility.
- Inputs and outputs are explicit and typed.
- Hidden global state and implicit environment access are prohibited in domain logic.
- Side effects occur through named ports or adapters.
- Functions remain small enough to understand and test, without arbitrary line limits.
- Boolean mode parameters are replaced with named options or separate functions when they create different behavior.
- Public functions document non-obvious invariants, failure, and side effects.
- A function must not report success before required verification completes.

## 9. Types and Schemas

- Use strict static typing in supported languages.
- Avoid unbounded `Any`, `unknown` casts, or dynamic dictionaries at domain boundaries.
- Parse untrusted data into validated boundary schemas.
- Convert boundary schemas into domain types explicitly.
- Model state and outcome with enums, tagged unions, result types, or equivalent constructs.
- Distinguish absent, unknown, redacted, stale, partial, and failed.
- Units and timestamps use dedicated types or explicit names.
- API, event, artifact, and configuration schemas are versioned and machine validated.

## 10. Domain Boundaries

- Domain modules expose application contracts, not internal tables or framework objects.
- Direct table access across module ownership is prohibited.
- Vendor clients, LLM SDKs, HTTP requests, ORM sessions, and UI framework state do not enter domain models.
- Shared primitives remain small, stable, and owned.
- Circular dependencies are prohibited and checked.
- Cross-module asynchronous facts use ATLAS-016 events.
- Module boundaries are tested as architecture constraints.

## 11. Error Handling

- Expected errors use stable typed codes and safe messages.
- Validation, denial, conflict, stale, timeout, dependency, partial, unknown, and internal failure remain distinct.
- Exceptions are caught at appropriate boundaries, not suppressed broadly.
- Catch-all handlers preserve correlation and emit sanitized diagnostics.
- Stack traces are logged only in protected operational channels.
- Retryability is explicit and paired with idempotency.
- A timeout or partial external result is never converted to success.
- Error messages do not expose secrets, hidden resources, queries, file paths, or control internals.

## 12. Asynchronous and Concurrent Code

- Async functions do not perform blocking I/O on event loops.
- Every external call has a timeout within the overall deadline.
- Retries are bounded, classified, and use backoff with jitter where appropriate.
- Mutations use idempotency or documented reconciliation.
- Shared state uses explicit concurrency control.
- Cancellation propagates and preserves partial state.
- Background work has owner, correlation, expiry, resource limits, and durable state when required.
- Tests cover races, duplicate delivery, reordering, cancellation, shutdown, and lease expiry.

## 13. State and Transactions

- State transitions occur through domain behavior, not arbitrary field mutation.
- Database transactions are short and exclude external network calls.
- Optimistic concurrency protects governed resources.
- Outbox patterns preserve state and event consistency.
- Append-only records create new versions instead of updates.
- Rollback is not assumed after an irreversible external effect.
- Workflow state is durable and not inferred from logs.
- Unknown external state requires reconciliation.

## 14. Input Validation

- Validate type, shape, enum, length, range, encoding, format, and cross-field rules.
- Reject unexpected fields for consequential command payloads.
- Normalize time, units, identifiers, and targets before authorization.
- Bound graph, query, file, archive, model-context, and batch complexity.
- Validate generated input as untrusted input.
- Validate again at the component that owns the invariant.
- Client-side validation improves usability but never replaces backend validation.

## 15. Configuration

- Configuration uses typed versioned schemas.
- Defaults are secure and explicit.
- Unknown or incompatible keys fail validation.
- Customer, target, vendor, and environment details are not hard-coded.
- Environment variables contain bounded overrides or secret references, not uncontrolled configuration blobs.
- Dynamic reload behavior is explicit and safe.
- Effective configuration is inspectable with redaction.
- Non-overridable security and guardrail rules cannot be disabled by configuration.

## 16. Secrets

- Never commit, embed, print, log, serialize, or test with real secrets.
- Use approved secret-manager references.
- Do not pass secrets through command-line arguments or URLs.
- Secret values do not enter model context, exceptions, traces, reports, support bundles, or snapshots.
- Use synthetic recognizable markers in secret-leakage tests.
- Credentials have narrow purpose, target, capability, and rotation.
- Secret scanning runs locally where available and in CI.
- If exposure is suspected, rotate and investigate; deleting a commit alone is insufficient.

## 17. Security

- Use maintained libraries for authentication, cryptography, parsing, and security-sensitive protocols.
- Custom cryptography is prohibited.
- Parameterize database queries.
- Prevent command, template, path, header, query-language, and deserialization injection.
- Resolve outbound destinations through allowlists and governed clients.
- Treat files, archives, documents, HTML, Markdown, logs, tool output, and model output as untrusted.
- Apply least privilege to process, file, database, network, and cloud permissions.
- Add threat models and negative tests for privileged or externally reachable features.

## 18. Authentication and Authorization

- Authentication is performed through shared approved middleware or services.
- Authorization is checked in the backend at the owning use-case boundary.
- Do not derive access from UI state, role display name, email domain, or prompt instruction.
- Queries apply organization and scope before aggregation or pagination.
- Service delegation preserves human and service identities.
- Approval cannot supply a missing permission.
- Security-sensitive deny behavior is consistent and does not reveal hidden resources.

## 19. Logging and Audit

- Use structured logging with stable event names and fields.
- Propagate correlation, request, trace, workflow, decision, approval, and operation IDs.
- Choose levels according to ATLAS-033.
- Redact before logging and avoid raw bodies by default.
- Audit events use ATLAS-032 contracts and are not ordinary log messages.
- Do not sample mandatory audit events.
- Include enough safe context to diagnose state and failure.
- Never log `success` while result is partial or unknown.

## 20. Metrics and Traces

- Instrument user and operationally meaningful boundaries.
- Metrics use bounded label cardinality.
- Traces propagate across API, worker, model, connector, and integration calls.
- Sensitive parameters and content are excluded.
- Record duration, state, result code, retry, and dependency without raw identities where possible.
- Instrumentation failure does not alter business behavior, except mandatory audit behavior.
- Performance work begins with measurement.

## 21. API Code

- OpenAPI contract and generated types follow ATLAS-050.
- Transport handlers remain thin.
- API schemas are separate from ORM and domain models.
- Stable error codes and HTTP semantics are centralized.
- Pagination, idempotency, ETag, operation resources, and SSE follow shared implementations.
- All protected endpoints declare permission and scope.
- Avoid endpoint-specific authentication, audit, or redaction reinvention.
- Breaking changes require compatibility review.

## 22. Database Code

- Repositories belong to one domain module.
- Queries select required fields and avoid unbounded relationship loading.
- Database constraints back critical invariants.
- Migrations are immutable after release and tested from supported versions.
- ORM lazy loading is controlled to avoid hidden I/O and authorization gaps.
- Raw SQL requires reason, parameterization, ownership, tests, and query-plan review where material.
- Direct production data fixes are not shipped as undocumented manual queries.
- Retention and deletion are explicit governed jobs.

## 23. Event and Worker Code

- Events and commands have versioned schemas and stable IDs.
- Consumers are idempotent and tolerate duplicate delivery.
- Ordering assumptions are explicit and bounded.
- Poison messages enter governed intervention state with safe diagnostics.
- Retry and dead-letter behavior is configured per failure class.
- Worker tasks checkpoint durable progress where needed.
- Human wait states do not use busy polling.
- Shutdown and lease recovery are tested.

## 24. Connector Code

- Implement ATLAS-020 manifests, capabilities, schemas, normalization, and error contracts.
- No arbitrary command or unrestricted HTTP surface.
- Validate target, parameter, timeout, output size, and capability class.
- Resolve credentials only in the connector runtime.
- Use vendor-supported APIs or CLI mechanisms with version checks.
- Preserve safe vendor evidence and request IDs.
- Simulators and contract fixtures are required.
- Unknown, timeout, partial, and side-effect states remain explicit.

## 25. AI and RAG Code

- Prompts, agents, model profiles, retrieval, and output schemas are versioned.
- Model output is parsed and validated, never trusted through string convention alone.
- Tool calls use the governed gateway.
- Retrieval enforces access before and after candidate selection.
- Citations are validated against exact source versions.
- Do not request or store private chain-of-thought.
- Guardrail, DLP, prompt-injection, budget, timeout, and fallback behavior are deterministic where required.
- Model upgrades require evaluation, not only compilation or unit tests.

## 26. Frontend Code

- TypeScript strict mode is required.
- Components separate server state, view state, and durable backend state.
- Use semantic HTML and accessible component primitives.
- Avoid custom reimplementation of standard controls without need.
- Render untrusted content safely and never execute model-provided markup.
- Authorization-sensitive state is refreshed on scope and session change.
- Loading, empty, stale, partial, denied, failed, and unknown states are explicit.
- Responsive layouts and text must not overlap at supported widths.

## 27. Python Baseline

Subject to the language ADR:

- Use a supported Python version and lock exact dependency resolution.
- Format and lint through one repository configuration.
- Type-check production code under a strict agreed baseline.
- Prefer dataclasses or validated models for structured data.
- Use timezone-aware UTC timestamps.
- Use context managers for resource lifecycle.
- Avoid mutable default arguments, implicit broad exception handling, and import-time side effects.
- Async and sync interfaces are not mixed invisibly.
- Public modules and complex behavior have concise docstrings.

## 28. TypeScript Baseline

Subject to the language ADR:

- Enable strict compiler settings and checked indexed access where practical.
- Avoid `any`; narrow `unknown` through validation.
- Generate or derive API types from governed schemas.
- Use discriminated unions for operation and result states.
- Keep server responses out of UI state until validated.
- Avoid non-null assertions except after locally provable checks.
- Components have stable typed props and accessible semantics.
- Effects declare dependencies and clean up subscriptions.
- Browser storage use is explicit and security-reviewed.

## 29. Dependencies

- Add a dependency only for a clear maintained capability.
- Review license, maintenance, security history, transitive size, runtime privilege, and offline availability.
- Pin direct and resolved versions through lock files.
- Do not duplicate frameworks solving the same problem without ADR.
- Remove unused dependencies.
- Automated updates must still pass review and tests.
- Critical libraries have an upgrade and replacement strategy.
- Vendored artifacts preserve source, license, checksum, and update process.

## 30. Comments and Documentation

- Comments explain why, constraints, invariants, or non-obvious failure behavior.
- Do not narrate obvious assignments or stale implementation detail.
- Public contracts, operations, migrations, and security decisions are documented.
- Behavior changes update the appropriate governed document and API or schema contract.
- Significant choices use ADRs.
- Examples are synthetic, minimal, executable where practical, and secret-free.
- Deprecated behavior identifies replacement and removal path.

## 31. Testing Standards

- New behavior includes tests proportional to risk and blast radius.
- Bug fixes include a regression test where feasible.
- Tests assert outcomes and contracts, not private implementation details.
- Time, randomness, network, model, and external systems are controlled through ports or fixtures.
- Security controls include negative and bypass tests.
- AI behavior uses evaluation suites in addition to unit tests.
- Flaky tests are repaired or quarantined with owner and deadline, not retried indefinitely.
- Test code follows the same readability and secret rules as production code.

## 32. AI-Generated Code

- The task prompt references relevant governed documents.
- Generated changes stay within requested scope.
- Authors inspect every diff and understand behavior before acceptance.
- Generated dependencies, commands, queries, schemas, migrations, and security code receive heightened review.
- Generated code cannot approve, sign, publish, or deploy itself.
- Tests and static checks do not prove architecture or security correctness alone.
- Attribution and tool-use recording follow repository policy.
- Repeated generated duplication is refactored only when a clear local pattern emerges.

## 33. Code Review

Reviewers prioritize:

- Correctness and unintended behavior
- Security, privacy, organization isolation, and secrets
- Authorization, policy, approval, audit, and guardrails
- Failure, retry, idempotency, partial, unknown, cancellation, and recovery
- Domain and module boundaries
- API, event, schema, migration, and compatibility changes
- Test adequacy and observability
- Documentation and ADR updates
- Dependency and operational impact

Authors respond with code or rationale; unresolved material findings block merge.

## 34. Change and Commit Hygiene

- One change has a clear purpose and excludes unrelated cleanup.
- Generated and formatting churn is isolated when large.
- Commits are coherent and use conventional descriptive messages.
- Do not rewrite or discard unrelated user changes.
- Do not commit temporary files, local output, credentials, or environment-specific state.
- Branches remain mergeable and CI-clean.
- Pull requests explain behavior, risk, tests, migration, deployment, and rollback.

## 35. Tooling and Enforcement

CI should enforce:

- Formatting and linting
- Static typing
- Unit, integration, contract, and architecture tests
- Secret and sensitive-data scanning
- Dependency, license, vulnerability, and provenance checks
- OpenAPI, JSON Schema, event, and migration validation
- Documentation links, metadata, and Markdown checks
- Generated-file reproducibility
- Coverage and evaluation gates where risk-appropriate

Local hooks can provide fast feedback but server-side CI remains authoritative.

## 36. Exceptions

A standard exception records:

- Rule and affected code
- Justification and alternatives
- Risk and compensating control
- Owner and reviewers
- Expiry or removal condition
- Test and monitoring evidence

Exceptions cannot weaken ATLAS-003 principles or ATLAS-047 invariants.

## 37. Definition of Done

A code change is done when:

- Behavior and scope match approved requirements
- Contracts and documentation are updated
- Security and control boundaries are preserved
- Tests and static checks pass
- Errors, logs, metrics, audit, and recovery are appropriate
- Migrations, compatibility, deployment, and rollback are addressed
- No secrets or unrelated churn are included
- Required reviewers approve

## 38. MVP Scope

### Included

- General standards and module boundaries
- Strict Python and TypeScript baselines after ADR selection
- Shared API, error, configuration, logging, audit, and telemetry patterns
- Secure dependency and secret handling
- Connector, AI, RAG, frontend, database, event, and worker rules
- Automated formatting, linting, typing, test, schema, secret, dependency, and documentation checks
- Human review for every AI-generated change

### Excluded

- Language or framework proliferation
- Self-approving generated code
- Style rules that are not automatable or meaningfully reviewable
- Production hotfixes without follow-up governance and tests
- Hidden exceptions to security invariants

## 39. Dependencies and Traceability

- ATLAS-003 defines implementation principles.
- ATLAS-011 and ATLAS-051 define module and backend boundaries.
- ATLAS-020 defines connector contracts.
- ATLAS-032 and ATLAS-033 define audit and logging.
- ATLAS-040 and ATLAS-047 define AI and generated-code constraints.
- ATLAS-050, ATLAS-052, and ATLAS-053 define API, frontend, and persistence contracts.
- ATLAS-056 defines testing strategy.
- ATLAS-058 enforces checks and supply-chain controls.

## 40. Assumptions

- MVP uses Python for backend and TypeScript for frontend if ADRs confirm the direction.
- Repository automation can enforce objective quality checks.
- Contributors include humans using multiple coding agents.
- Security and domain reviewers are available for consequential changes.

## 41. Open Questions and ADR Backlog

- Which exact Python and TypeScript versions and strictness settings are selected?
- Which formatter, linter, type checker, test framework, and dependency managers are mandatory?
- Which repository architecture-boundary tool is used?
- What coverage and mutation thresholds apply by risk class?
- Which commit, branch-protection, and reviewer rules are enforced in GitHub?
- How is AI-tool attribution recorded without storing sensitive prompts?

## 42. Acceptance Criteria

This document is ready to enter Review when:

- General, language, API, database, event, connector, AI, and frontend standards are agreed.
- Error, async, transaction, configuration, secret, security, logging, and audit behavior are testable.
- Generated code is subject to the same controls and cannot approve or deploy itself.
- Documentation, tests, migration, deployment, and rollback are part of done.
- Objective rules have an enforcement plan and exceptions are governed.
- Architecture, engineering, security, platform, testing, AI, and documentation reviewers accept the standard.

## 43. Change History

| Version | Date | Author | Summary |
| --- | --- | --- | --- |
| 0.1.0 | 2026-07-21 | Project Atlas Team | Initial general, security, and documentation standards |
| 0.2.0 | 2026-08-03 | Engineering Enablement Owner | Added domain, type, error, async, state, security, API, database, event, connector, AI, frontend, Python, TypeScript, dependency, testing, review, enforcement, and definition-of-done standards |
| 1.0.0 | 2026-08-03 | Umit Ozdemir | Approved as the first binding documentation baseline under the designated approver authority |
