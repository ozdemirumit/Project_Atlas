# Project Atlas Backend

The backend is a Python modular monolith with explicit domain, application, port, adapter, and transport boundaries.

## Local Setup

```bat
cd backend
uv sync --frozen
set ATLAS_DEVELOPMENT_IDENTITY_ENABLED=true
uv run uvicorn atlas.main:app --app-dir src --reload
```

For direct development without PostgreSQL, omit `ATLAS_DATABASE_URL` and keep
`ATLAS_DATABASE_REQUIRED=false`. The readiness response will identify the database probe as
disabled. PostgreSQL-backed development and all migration execution use the root Compose profile.

## Checks

```bat
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
```

## API Foundation

- `GET /health/live`
- `GET /health/ready`
- `GET /api/v1/platform/status`
- `GET /api/v1/identity/me` (authenticated and authorized)
- `GET /api/v1/storage/overview` (authenticated, exact-scope C1 read)
- `POST /api/v1/ai/grounded-query` (authenticated, evidence-grounded C0 analysis)
- `GET /docs` in development only

All responses return a validated `X-Correlation-ID`. Development identity is disabled by
default, cannot be enabled in production, and never accepts client-provided identity or role
headers. It grants only the exact C0 scope required to read its own normalized identity.

## Connector Foundation

The connector application boundary provides immutable package registration, C0/C1 manifest
validation, disabled-by-default scoped instances, trusted self-test enablement, audited capability
discovery, and a deterministic isolated simulator. Vendor network integrations and operational
capabilities above C1 are intentionally outside the current foundation boundary.

## Local OpenAI-Compatible Model

The grounded-query API uses a clearly labeled synthetic model and synthetic knowledge profile by
default. Enable a configured local OpenAI-compatible endpoint only when all required values are
available:

```bat
set ATLAS_LOCAL_MODEL_ENABLED=true
set ATLAS_LOCAL_MODEL_BASE_URL=http://127.0.0.1:11434/v1
set ATLAS_LOCAL_MODEL_ID=approved-local-model-id
set ATLAS_LOCAL_MODEL_READER_TOKEN=reader-token-value
set ATLAS_LOCAL_MODEL_SECRET_REFERENCE_ID=secret.model.local-reader
```

The Reader Token is owned by the provider transport, is excluded from model prompts and audit
records, and is never accepted from an API caller. Non-loopback endpoints must use HTTPS. Model
responses are accepted only when their structured citations resolve to the authorized retrieval
package.
