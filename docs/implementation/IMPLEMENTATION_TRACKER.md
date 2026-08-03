# Project Atlas Implementation Tracker

## Current Focus

| Field | Value |
| --- | --- |
| Task ID | ATLAS-IMP-009 |
| Title | Evidence-grounded investigation and reasoning vertical slice |
| Status | Review |
| Branch | `agent/investigation-reasoning` |
| Pull Request | Pending |
| Governing Documents | ATLAS-002, ATLAS-014, ATLAS-015, ATLAS-026, ATLAS-027, ATLAS-031, ATLAS-032, ATLAS-041, ATLAS-046, ATLAS-047, ATLAS-050, ATLAS-052 |
| Last Updated | 2026-08-03 |
| Next Action | Open the implementation pull request and verify GitHub quality gates |

### ATLAS-IMP-009 Acceptance Criteria

- Investigation requests are limited to an exact authorized organization, environment, site,
  resource, target, question, time window, and bounded evidence budget.
- Artifacts are immutable and versioned and retain the prior version reference, requester,
  intended decision, component versions, stop reason, and safety boundary.
- Material statements remain typed as observations, retrieved facts, calculated findings,
  correlations, inferences, hypotheses, assumptions, unknowns, or recommendations.
- Material claims reference current authorized evidence or explicitly declare why evidence is
  unavailable; unresolved, stale, and contradicting evidence remains visible.
- Timeline entries preserve occurrence, observation, and ingestion time without claiming temporal
  order proves causality.
- Multiple hypotheses retain supporting and contradicting evidence, categorical confidence,
  limiting factors, and safe discriminating checks.
- Graph reachability, recent change, correlation, and historical similarity are never labeled root
  cause or confirmed outage in this slice.
- Schema, citation, scope, evidence-budget, capability, and audit failures fail closed without
  exposing hidden targets or partial unauthorized artifacts.
- The web workspace communicates what is known, inferred, assumed, conflicting, and unknown,
  explains confidence, and shows the safest next evidence without private chain-of-thought.
- Atlas remains decision support and does not authorize or execute infrastructure changes.

### ATLAS-IMP-009 Validation Evidence

- Backend Ruff formatting and lint checks passed.
- Backend strict mypy analysis passed for 130 source and test files.
- Backend pytest suite passed: 103 tests, including ten investigation tests for exact
  authorization, immutable version links, typed claims, evidence references, normalized time,
  hidden-target non-disclosure, evidence budgets, fail-closed audit, allowlisted checks, and exact
  resource scope.
- Frontend ESLint, TypeScript, Vitest, and production bundle checks passed.
- Live API validation returned all eight implemented epistemic claim types, two alternative
  hypotheses, explicit stopping behavior, and false root-cause and outage confirmation flags.
- The live web flow created a versioned artifact from the selected storage target and displayed
  known, inferred, and unknown statements, confidence rationale, typed claims, alternatives,
  bounded C1 checks, normalized UTC timeline, stop reason, and safety boundary.
- Desktop and 390-pixel mobile views were inspected with no incoherent overlap or page-level
  horizontal overflow; inventory tables remain bounded and internally scrollable.
- Browser console validation reported no errors or warnings during the investigation flow.

### ATLAS-IMP-008 Acceptance Criteria

### ATLAS-IMP-008 Acceptance Criteria

- Health-check definitions are immutable and versioned, and retain owner, target scope, connector
  capability, schedule, thresholds, timeout, step, and evidence limits.
- Definitions can be enabled or disabled without changing historical runs.
- Schedule evaluation is deterministic and reports the last and next due times without relying on
  an LLM or an in-process timer as authoritative state.
- On-demand execution is limited to an allowlisted C1 read-only connector capability and exact
  authorized target scope.
- Runs retain definition and connector versions, actor, trigger, timestamps, state, observations,
  findings, evidence, freshness, partial-result reasons, and safety notice.
- Completed, partial, timed-out, failed, and cancelled states are distinct; unknown outcomes are
  never represented as healthy.
- Step, evidence, duration, and target limits fail closed before connector dispatch or truncate to
  an explicit partial result where the contract permits.
- Required authorization and audit failures block protected health-check responses.
- The web workspace shows enabled checks, schedule state, latest run, findings, freshness,
  evidence, partial context, and an explicit read-only decision-support boundary.

### ATLAS-IMP-008 Validation Evidence

- Backend Ruff formatting and lint checks passed.
- Backend strict mypy analysis passed for 119 source and test files.
- Backend pytest suite passed: 93 tests, including eleven health-check tests for exact
  authorization, deterministic schedules, versioned definitions, partial results, safe timeout,
  disabled dispatch, generic target errors, result budgets, and fail-closed pre-dispatch audit.
- Frontend ESLint, TypeScript, Vitest, and production bundle checks passed.
- Live API validation returned two versioned C1 definitions with deterministic 15- and 60-minute
  schedules and evidence-linked partial and completed latest runs.
- A live manual controller check completed as `partial`, retained the authenticated requester,
  and did not represent missing event-log evidence as healthy or as a confirmed outage.
- Desktop and 390-pixel mobile views were inspected with no incoherent overlap or page-level
  horizontal overflow; health-check tabs and tables remain bounded and internally scrollable.
- Browser console validation reported no errors or warnings during overview and manual-run flows.
- GitHub backend and frontend CI jobs passed before merge.

### ATLAS-IMP-007 Acceptance Criteria

- Canonical entities, relationships, observations, and snapshots retain source, time, freshness,
  confidence basis, classification, and access metadata.
- The first modeled path covers storage, volume, datastore, virtual machine, technical service,
  and business service entities.
- Authorization filters entities and relationships before traversal and again before output.
- Hidden nodes cannot leak through counts, labels, path shapes, errors, or completeness metadata.
- Blast-radius traversal is bounded by direction, relationship type, depth, and node limits.
- Every affected entity includes an exact relationship and evidence path from the starting entity.
- Results distinguish directly affected, possibly affected, and unknown scope.
- Graph reachability is never presented as a confirmed outage or a production digital twin.
- Missing redundancy, stale branches, and incomplete service mappings remain explicit.
- Required graph-read audit failure blocks the protected response.
- The web workspace displays the dependency path, impact scope, freshness, and graph gaps.

### ATLAS-IMP-007 Validation Evidence

- Backend Ruff formatting and lint checks passed.
- Backend strict mypy analysis passed for 108 source and test files.
- Backend pytest suite passed: 82 tests, including eight graph impact tests for exact scope,
  bounded traversal, pre-traversal authorization, hidden-node non-disclosure, evidence paths,
  safe target errors, and fail-closed audit behavior.
- Frontend ESLint, TypeScript, Vitest, and production bundle checks passed.
- Live desktop and 390-pixel mobile views were inspected with no incoherent overlap; the
  dependency path remains horizontally scrollable within its bounded workspace.
- Live selection tests confirmed B28 maps through ERP dependencies and G400 maps through the
  Analytics service without inventing a business-service dependency.
- The UI labels the result as D0-D1 dependency analysis, exposes stale/partial graph context,
  and does not present graph reachability as an outage.
- GitHub backend and frontend CI jobs passed before merge.

### ATLAS-IMP-006 Completion Criteria

- The Model Gateway is the only application path to a model transport.
- Endpoint routing is deterministic by task class, classification, lifecycle, and evaluation state.
- Model transports receive bounded provider-neutral invocations and no infrastructure credentials.
- Knowledge chunks carry organization, environment, classification, ACL, lifecycle, version, and
  exact citation metadata before becoming retrievable.
- Unauthorized chunks are excluded before relevance scoring and revalidated after ranking.
- Empty authorized retrieval is a valid result and is never presented as success or evidence.
- Model output citations must resolve to the exact authorized retrieval package.
- Grounded answers distinguish evidence-backed summary text and explicit unknowns.
- Required retrieval and model audit failures block the protected response.
- Evaluation covers citation recall, resolution, empty results, and zero ACL leakage.

### ATLAS-IMP-006 Validation Evidence

- Backend Ruff formatting and lint checks passed.
- Backend strict mypy analysis passed for 97 source and test files.
- Backend pytest suite passed: 74 tests, including pre-score ACL filtering, classification denial,
  exact citation validation, empty authorized retrieval, audit failure, bounded input, and safe API
  denial behavior.
- The retrieval evaluation harness passed fixed citation-recall and zero-leakage cases.
- The OpenAI-compatible adapter passed Reader Token isolation, structured request, and malformed
  provider-response tests.
- Frontend ESLint, TypeScript, Vitest, and production bundle checks passed without regressions.
- Live HTTP smoke tests returned one exact authorized citation for a grounded query and did not
  invoke the model when no authorized relevant evidence was available.
- GitHub backend and frontend CI jobs passed before merge.

### ATLAS-IMP-001 Validation Evidence

- Backend Ruff formatting and lint checks passed.
- Backend strict mypy analysis passed for 25 source files.
- Backend pytest suite passed: 7 tests.
- Frontend ESLint and TypeScript checks passed.
- Frontend Vitest suite passed and the production bundle built successfully.
- API liveness, correlation ID, platform status, and frontend proxy smoke tests passed.
- Desktop and 390-pixel mobile layouts were visually inspected with no horizontal overflow or console errors.
- Windows Command Prompt bootstrap and quality-check entry points passed without PowerShell execution-policy changes.
- Compose YAML parsed successfully with database, backend, and frontend services.
- Docker runtime validation remains unavailable on this workstation and is delegated to CI or a Docker-capable reviewer.

## Planned Tasks

The next implementation task will be added after its vertical slice is selected from the approved
roadmap and its dependencies and acceptance criteria are recorded.

## Blocked Tasks

No task is currently blocked.

Environment limitation for ATLAS-IMP-001: Docker is not installed on the current workstation. Compose assets will be generated and statically inspected, but runtime Compose validation requires a Docker-capable environment.

## Completed Tasks

| Task ID | Title | Completion Evidence |
| --- | --- | --- |
| ATLAS-IMP-001 | Runnable development foundation | Merged through [PR #12](https://github.com/ozdemirumit/Project_Atlas/pull/12); local and GitHub quality gates passed |
| ATLAS-IMP-002 | Identity and authorization foundation | Merged through [PR #13](https://github.com/ozdemirumit/Project_Atlas/pull/13); local and GitHub quality gates passed |
| ATLAS-IMP-003 | Connector registry and simulator framework | Merged through [PR #14](https://github.com/ozdemirumit/Project_Atlas/pull/14); 41 backend tests and all GitHub quality gates passed |
| ATLAS-IMP-004 | Hitachi Ops Center read-only connector candidate | Merged through [PR #15](https://github.com/ozdemirumit/Project_Atlas/pull/15); 55 backend tests and all GitHub quality gates passed |
| ATLAS-IMP-005 | Storage inventory and health vertical slice | Merged through [PR #16](https://github.com/ozdemirumit/Project_Atlas/pull/16); 60 backend tests, live UI validation, and all GitHub quality gates passed |
| ATLAS-IMP-006 | Local LLM and governed RAG foundation | Merged through [PR #17](https://github.com/ozdemirumit/Project_Atlas/pull/17); 74 backend tests, retrieval evaluation, live API smoke tests, and all GitHub quality gates passed |
| ATLAS-IMP-007 | Infrastructure Graph and storage impact vertical slice | Completed through [PR #19](https://github.com/ozdemirumit/Project_Atlas/pull/19); 82 backend tests, live desktop/mobile UI validation, and all GitHub quality gates passed |
| ATLAS-IMP-008 | Scheduled storage health checks vertical slice | Completed through [PR #20](https://github.com/ozdemirumit/Project_Atlas/pull/20); 93 backend tests, live desktop/mobile UI and manual-run validation, and all GitHub quality gates passed |

## Status Rules

- `Planned`: accepted scope exists but work has not started.
- `In Progress`: one active branch owns the task.
- `Blocked`: progress requires a missing decision, dependency, permission, or environment.
- `Review`: implementation and available validation are complete; a pull request is open.
- `Done`: required review is resolved and the implementation pull request is merged.

Git history, code, tests, and pull requests are authoritative when this tracker is stale. Every implementation session must reconcile the tracker against repository evidence before editing and update it before completion.
