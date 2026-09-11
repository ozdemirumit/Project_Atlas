from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.config import Settings
from atlas.core.persistence.database import (
    DatabaseHealthProbe,
    SchemaCompatibilityProbe,
    _classify_schema_compatibility,
    _compute_expected_schema_head,
)
from atlas.modules.platform.domain.status import ComponentHealth, ComponentState

ROOT = Path(__file__).resolve().parents[1]

# A loopback address nothing listens on: real TCP connect attempts to it fail fast
# (connection refused) without needing a live Postgres instance or any network access
# beyond localhost, exercising the probe's genuine connection-failure path for real.
_UNREACHABLE_DATABASE_URL = (
    "postgresql+psycopg://atlas:wrong@127.0.0.1:59999/atlas_schema_probe_test"
)


# --- DatabaseHealthProbe (pre-existing probe; no dedicated unit test file existed yet) ---


@pytest.mark.asyncio
async def test_database_health_probe_is_disabled_without_database_when_not_required() -> None:
    probe = DatabaseHealthProbe(Settings(environment="test"))
    try:
        health = await probe.check()
    finally:
        await probe.close()

    assert health == ComponentHealth(
        name="database",
        status=ComponentState.DISABLED,
        required=False,
        code="database_not_configured",
    )


# --- SchemaCompatibilityProbe: no-database-configured behavior, mirroring DatabaseHealthProbe ---


@pytest.mark.asyncio
async def test_schema_compatibility_probe_is_disabled_without_database_when_not_required() -> None:
    probe = SchemaCompatibilityProbe(Settings(environment="test"))
    try:
        health = await probe.check()
    finally:
        await probe.close()

    assert health == ComponentHealth(
        name="database_schema",
        status=ComponentState.DISABLED,
        required=False,
        code="database_not_configured",
    )
    assert probe.last_expected_revision is None
    assert probe.last_applied_revision is None


@pytest.mark.asyncio
async def test_schema_compatibility_probe_is_unavailable_without_database_when_required() -> None:
    probe = SchemaCompatibilityProbe(Settings(environment="test", database_required=True))
    try:
        health = await probe.check()
    finally:
        await probe.close()

    assert health == ComponentHealth(
        name="database_schema",
        status=ComponentState.UNAVAILABLE,
        required=True,
        code="database_url_missing",
    )


@pytest.mark.asyncio
async def test_schema_compatibility_probe_reports_unavailable_on_real_connection_failure() -> None:
    """No live Postgres is required for this: it makes a genuine TCP connection attempt
    against an address nothing listens on and observes the real failure, rather than
    mocking the engine or the query result."""
    settings = Settings(
        environment="test",
        database_url=_UNREACHABLE_DATABASE_URL,
        database_required=True,
    )
    probe = SchemaCompatibilityProbe(settings)
    try:
        health = await probe.check()
    finally:
        await probe.close()

    assert health.status is ComponentState.UNAVAILABLE
    assert health.code == "database_unavailable"
    assert health.required is True
    # the expected head is still computed from the real migration graph even though the
    # connection itself failed
    assert probe.last_expected_revision is not None
    assert probe.last_applied_revision is None


# --- _compute_expected_schema_head: real (non-mocked) check against the actual migration graph ---


def test_compute_expected_schema_head_matches_the_real_migration_graph() -> None:
    # Deliberately recomputed independently here (rather than asserting a hardcoded revision
    # literal) so this test never goes stale as new migrations are added -- see the
    # stale-alembic-head-assertion class of bug this project has hit in prior passes.
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()

    assert len(heads) == 1
    assert _compute_expected_schema_head() == heads[0]


# --- _classify_schema_compatibility: pure comparison logic, stubbed applied revision ---
# No live-Postgres test infrastructure (ATLAS_TEST_POSTGRES_DSN) is configured in this
# environment, so the HEALTHY / schema_not_migrated / schema_incompatible branches of the
# comparison are proven here directly against stubbed inputs instead of a live database.


def test_classify_schema_compatibility_is_healthy_when_applied_matches_expected() -> None:
    state, code = _classify_schema_compatibility(
        expected_revision="20260911_0173", applied_revision="20260911_0173"
    )
    assert state is ComponentState.HEALTHY
    assert code == "schema_compatible"


def test_classify_schema_compatibility_is_schema_not_migrated_when_applied_is_none() -> None:
    state, code = _classify_schema_compatibility(
        expected_revision="20260911_0173", applied_revision=None
    )
    assert state is ComponentState.UNAVAILABLE
    assert code == "schema_not_migrated"


def test_classify_schema_compatibility_is_schema_incompatible_when_applied_differs() -> None:
    state, code = _classify_schema_compatibility(
        expected_revision="20260911_0173", applied_revision="20260101_0001"
    )
    assert state is ComponentState.UNAVAILABLE
    assert code == "schema_incompatible"


# --- lifespan fail-closed startup enforcement ---


def test_create_app_starts_up_fine_with_no_database_configured() -> None:
    """The single most universally-used code path in the backend: `create_app()` with
    `Settings(environment="test")` and no database configured must keep starting cleanly."""
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get("/health/live")
    assert response.status_code == 200


def test_lifespan_fails_closed_when_required_schema_check_is_not_healthy() -> None:
    """A real (non-mocked) end-to-end proof that an incompatible/unreachable schema blocks
    application startup: a required database is configured pointing at an address nothing
    listens on, so the real startup schema check genuinely fails, and `lifespan()` must
    raise instead of ever yielding control to serve requests."""
    settings = Settings(
        environment="test",
        database_url=_UNREACHABLE_DATABASE_URL,
        database_required=True,
    )
    app = create_app(settings)

    with pytest.raises(Exception, match="database schema is not compatible"), TestClient(app):
        pass


def test_lifespan_skips_schema_check_when_database_not_required() -> None:
    """A real database URL that would fail the schema check must NOT block startup when
    the database isn't required -- mirroring `DatabaseHealthProbe`'s own required-aware
    no-op convention exactly."""
    settings = Settings(
        environment="test",
        database_url=_UNREACHABLE_DATABASE_URL,
        database_required=False,
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
