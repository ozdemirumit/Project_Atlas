# ADR-001: Initial Application Stack

| Field | Value |
| --- | --- |
| Status | Accepted |
| Decision Date | 2026-08-03 |
| Decision Owner | Umit Ozdemir, acting Architecture Owner |
| Related Documents | ATLAS-010, ATLAS-011, ATLAS-012, ATLAS-050, ATLAS-051, ATLAS-052, ATLAS-053 |
| Supersedes | None |

## Context

Project Atlas needs a conservative, self-hosted implementation foundation that preserves modular-monolith boundaries, supports restricted networks, and does not add early distributed-system complexity. The approved documents identify technology candidates but require an ADR for final selection.

## Decision

The initial application stack is:

| Area | Selection |
| --- | --- |
| Backend language | Python 3.12 |
| HTTP API | FastAPI-compatible ASGI using FastAPI 0.141.1 and Uvicorn 0.52.1 |
| Validation and settings | Pydantic 2.13.4 and pydantic-settings 2.14.2 |
| Persistence | SQLAlchemy 2.0.51 and Alembic 1.18.5 |
| Transactional database | PostgreSQL 18 development image, with production version governed by release support policy |
| PostgreSQL driver | Psycopg 3.3.4 |
| Frontend language | TypeScript 6.0.3 in strict mode |
| Frontend | React 19.2.8 and Vite 8.2.0 |
| Routing and server state | React Router 7.18.2 and TanStack Query 5.101.4 |
| Icons | Lucide React 1.28.0 |

The backend starts as one modular-monolith API process. Workers and connector runtimes remain explicit future process boundaries and are not simulated inside the API process.

The frontend is a client-rendered enterprise application shell served as static assets in deployment profiles. It has no mandatory public SaaS runtime dependency.

TypeScript 7 is not selected because the accepted TypeScript ESLint release supports TypeScript versions below 6.1. The compatibility constraint is preferred over using the newest compiler without supported lint analysis.

## Consequences

- The selected stack matches the approved candidate direction and local runtime availability.
- Domain code must remain independent from FastAPI, SQLAlchemy, and frontend transport types.
- PostgreSQL-specific behavior must be tested against PostgreSQL rather than inferred from SQLite.
- Package versions are pinned and updated through reviewed dependency changes.
- A future service, graph, vector, workflow, or model technology requires its own ADR.

## Rejected Alternatives

- Immediate microservices: rejected because ownership and scaling evidence do not yet justify distributed operation.
- Cloud-managed mandatory services: rejected because restricted-network deployment is a baseline requirement.
- SQLite as a compatibility target: rejected because it does not prove PostgreSQL transaction, type, migration, or concurrency behavior.
- TypeScript 7 for the initial baseline: deferred until the selected lint and build toolchain supports it.

## Validation

- Backend dependency resolution, formatting, linting, strict type checking, tests, and API startup
- Frontend dependency resolution, linting, strict type checking, component tests, and production build
- PostgreSQL migration generation and execution in a Docker-capable CI or development environment
- Restricted-network artifact mirroring and license review before a production release
