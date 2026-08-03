# Project Atlas Backend

The backend is a Python modular monolith with explicit domain, application, port, adapter, and transport boundaries.

## Local Setup

```powershell
cd backend
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn atlas.main:app --app-dir src --reload
```

For direct development without PostgreSQL, omit `ATLAS_DATABASE_URL` and keep `ATLAS_DATABASE_REQUIRED=false`. The readiness response will identify the database probe as disabled. PostgreSQL-backed development and all migration verification use the root Compose profile.

## Checks

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
```

## API Foundation

- `GET /health/live`
- `GET /health/ready`
- `GET /api/v1/platform/status`
- `GET /docs` in development only

All responses return a validated `X-Correlation-ID`. Protected product APIs will be added only with the deterministic identity and authorization foundation in ATLAS-IMP-002.
