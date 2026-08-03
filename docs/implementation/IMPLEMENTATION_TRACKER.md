# Project Atlas Implementation Tracker

## Current Focus

| Field | Value |
| --- | --- |
| Task ID | ATLAS-IMP-002 |
| Title | Identity and authorization foundation |
| Status | Review |
| Branch | `agent/identity-authorization-foundation` |
| Pull Request | [#13](https://github.com/ozdemirumit/Project_Atlas/pull/13) |
| Governing Documents | ATLAS-003, ATLAS-030, ATLAS-031, ATLAS-032, ATLAS-050, ATLAS-051 |
| Last Updated | 2026-08-03 |
| Next Action | Review and merge the identity and authorization foundation pull request |

### ATLAS-IMP-002 Acceptance Criteria

- A stable normalized subject contract distinguishes authentication from authorization.
- Development identity is deterministic, server-configured, disabled by default, and impossible to enable in production.
- A versioned permission registry, role definition, exact resource scope, and time-bound assignment contract exists.
- Protected API requests return safe `401` and `403` problem details without resource disclosure.
- Authorization decisions are deterministic, correlated, and submitted to the audit boundary.
- Client-supplied identity, role, or scope headers cannot elevate access.
- Current-identity API and frontend identity display work in the supported development profile.
- Backend and frontend quality gates and runtime smoke tests pass.

### ATLAS-IMP-002 Validation Evidence

- Backend Ruff formatting and lint checks passed.
- Backend strict mypy analysis passed for 43 source files.
- Backend pytest suite passed: 17 tests, including default deny, exact scope, expired
  assignment, header spoofing, unverified bearer token, production configuration, and audit
  failure behavior.
- Frontend ESLint, TypeScript, Vitest, and production build checks passed.
- Direct API and frontend-proxy smoke tests returned the same authorized current-identity
  contract and preserved correlation IDs.
- Unverified bearer input returned safe `401` problem details and did not enter audit records.
- Desktop UI displayed the server-derived `Local Operator` identity with no console errors or
  horizontal overflow.
- Developer web and Compose host ports bind to loopback only, preserving the local development
  identity boundary.
- Production configuration rejects interactive API documentation; backend validation now passes
  19 tests.
- CI checkout uses the current Node 24-based action runtime.

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

| Task ID | Title | Status | Depends On | Governing Documents | Expected Outcome |
| --- | --- | --- | --- | --- | --- |
| ATLAS-IMP-003 | Connector registry and simulator framework | Planned | ATLAS-IMP-001, ATLAS-IMP-002 | ATLAS-020, ATLAS-021, ATLAS-025, ATLAS-032 | Registered packages, instances, C0/C1 capabilities, isolation, and simulator harness |
| ATLAS-IMP-004 | Hitachi Ops Center read-only connector candidate | Planned | ATLAS-IMP-003 | ATLAS-020 through ATLAS-022, ATLAS-047 | Quarantined C1 inventory and health connector using synthetic and approved lab data |
| ATLAS-IMP-005 | Storage inventory and health vertical slice | Planned | ATLAS-IMP-004 | ATLAS-026, ATLAS-042 through ATLAS-046, ATLAS-052 | Evidence-linked storage inventory, health findings, investigation, and report workflow |
| ATLAS-IMP-006 | Local LLM and governed RAG foundation | Planned | ATLAS-IMP-002, ATLAS-IMP-005 | ATLAS-014, ATLAS-015, ATLAS-027, ATLAS-040, ATLAS-047, ATLAS-054 | Model gateway, retrieval, citations, ACL filtering, and evaluation harness |

## Blocked Tasks

No task is currently blocked.

Environment limitation for ATLAS-IMP-001: Docker is not installed on the current workstation. Compose assets will be generated and statically inspected, but runtime Compose validation requires a Docker-capable environment.

## Completed Tasks

| Task ID | Title | Completion Evidence |
| --- | --- | --- |
| ATLAS-IMP-001 | Runnable development foundation | Merged through [PR #12](https://github.com/ozdemirumit/Project_Atlas/pull/12); local and GitHub quality gates passed |

## Status Rules

- `Planned`: accepted scope exists but work has not started.
- `In Progress`: one active branch owns the task.
- `Blocked`: progress requires a missing decision, dependency, permission, or environment.
- `Review`: implementation and available validation are complete; a pull request is open.
- `Done`: required review is resolved and the implementation pull request is merged.

Git history, code, tests, and pull requests are authoritative when this tracker is stale. Every implementation session must reconcile the tracker against repository evidence before editing and update it before completion.
