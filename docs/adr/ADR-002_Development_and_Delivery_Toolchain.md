# ADR-002: Development and Delivery Toolchain

| Field | Value |
| --- | --- |
| Status | Accepted |
| Decision Date | 2026-08-03 |
| Decision Owner | Umit Ozdemir, acting Architecture Owner |
| Related Documents | ATLAS-038, ATLAS-055, ATLAS-056, ATLAS-057, ATLAS-058, ATLAS-059 |
| Supersedes | None |

## Context

Project Atlas needs deterministic local and CI workflows for Python, TypeScript, PostgreSQL, and container assets. The tools must support Windows development, Linux CI, dependency locking, and future mirrored or offline installation.

## Decision

| Area | Selection |
| --- | --- |
| Python dependency and environment management | uv 0.12.1 with committed `uv.lock` |
| Python formatting and linting | Ruff 0.16.1 |
| Python type checking | mypy 2.3.0 in strict mode |
| Python testing | pytest 9.1.1, pytest-asyncio 1.4.0, and HTTPX 0.28.1 |
| JavaScript package manager | pnpm 11.7.0 with committed lockfile |
| Frontend linting | ESLint 9.39.4 with typescript-eslint 8.65.0 |
| Frontend testing | Vitest 4.1.10, Testing Library, and jsdom 30.0.1 |
| Local service composition | Docker Compose specification |
| Continuous integration | GitHub Actions with separate backend and frontend jobs |

PowerShell scripts provide the first supported Windows bootstrap and development path. Portable package-manager commands remain visible so Linux CI does not depend on PowerShell.

## Consequences

- Lockfiles are reviewed artifacts and must change with dependency declarations.
- CI installs from lockfiles and fails when they are stale.
- Docker Compose is a supported local profile but not a production deployment design.
- Absence of Docker on one workstation does not justify replacing PostgreSQL tests with SQLite.
- CI and a Docker-capable environment must perform migration and Compose runtime validation before ATLAS-IMP-001 is considered fully portable.

## Supply Chain Controls

- Dependencies are pinned, scanned, and reviewed for license and transitive impact before release.
- Install scripts do not receive production credentials.
- No package may require an undisclosed external runtime service.
- Future restricted-network bundles must use approved mirrors and integrity verification.

## Validation

- `uv sync --frozen` and all backend checks
- `pnpm install --frozen-lockfile` and all frontend checks
- Docker Compose configuration validation and runtime health in a capable environment
- GitHub Actions execution on pull requests
