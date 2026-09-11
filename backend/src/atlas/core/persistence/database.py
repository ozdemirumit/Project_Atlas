from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from atlas.core.config import Settings
from atlas.modules.platform.domain.status import ComponentHealth, ComponentState

logger = logging.getLogger(__name__)

# backend/src/atlas/core/persistence/database.py -> parents[4] is the repo root (backend/),
# matching the same `alembic.ini` / `migrations/` layout the alembic-head tests in
# backend/tests/test_workflow_*_persistence.py resolve independently.
_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
_ALEMBIC_INI_PATH = _REPOSITORY_ROOT / "alembic.ini"
_MIGRATIONS_SCRIPT_LOCATION = _REPOSITORY_ROOT / "migrations"


def _compute_expected_schema_head() -> str:
    """Return the single Alembic migration head the running application code expects.

    Mirrors the `Config`/`ScriptDirectory.from_config` invocation the alembic-head
    assertions in backend/tests/test_workflow_*_persistence.py already use.
    """
    config = Config(str(_ALEMBIC_INI_PATH))
    config.set_main_option("script_location", str(_MIGRATIONS_SCRIPT_LOCATION))
    script = ScriptDirectory.from_config(config)
    heads = [str(head) for head in script.get_heads()]
    if len(heads) != 1:
        raise RuntimeError(
            f"alembic migration graph does not have exactly one head, found: {heads!r}"
        )
    return heads[0]


def _classify_schema_compatibility(
    *, expected_revision: str, applied_revision: str | None
) -> tuple[ComponentState, str]:
    """Pure comparison of an expected vs. applied Alembic revision -> (state, code).

    Factored out of `SchemaCompatibilityProbe.check` so the comparison itself -- the part
    of this probe with real branching logic -- can be exercised directly in tests without
    a live database, by passing in a stubbed `applied_revision`.
    """
    if applied_revision is None:
        return ComponentState.UNAVAILABLE, "schema_not_migrated"
    if applied_revision != expected_revision:
        return ComponentState.UNAVAILABLE, "schema_incompatible"
    return ComponentState.HEALTHY, "schema_compatible"


class DatabaseHealthProbe:
    name = "database"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._engine: AsyncEngine | None = None

    @property
    def required(self) -> bool:
        return self._settings.database_required

    def _get_engine(self) -> AsyncEngine | None:
        if not self._settings.database_url:
            return None
        if self._engine is None:
            self._engine = create_async_engine(
                self._settings.database_url,
                pool_pre_ping=True,
                pool_recycle=300,
            )
        return self._engine

    async def check(self) -> ComponentHealth:
        engine = self._get_engine()
        if engine is None:
            state = ComponentState.UNAVAILABLE if self.required else ComponentState.DISABLED
            code = "database_url_missing" if self.required else "database_not_configured"
            return ComponentHealth(name=self.name, status=state, required=self.required, code=code)

        try:
            async with asyncio.timeout(self._settings.database_probe_timeout_seconds):
                async with engine.connect() as connection:
                    await connection.execute(text("SELECT 1"))
        except Exception as exc:
            logger.warning("database_health_check_failed", extra={"error_type": type(exc).__name__})
            return ComponentHealth(
                name=self.name,
                status=ComponentState.UNAVAILABLE,
                required=self.required,
                code="database_unavailable",
            )

        return ComponentHealth(
            name=self.name,
            status=ComponentState.HEALTHY,
            required=self.required,
            code="database_healthy",
        )

    async def close(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()


class SchemaCompatibilityProbe:
    """Compares the connected database's applied Alembic revision against the revision
    the running application code expects.

    Mirrors `DatabaseHealthProbe`'s conventions exactly: a no-op `DISABLED`/`UNAVAILABLE`
    result (driven by `required`) when no real database is configured, so this probe never
    breaks a test or environment that already runs with `settings.database_url` unset.
    """

    name = "database_schema"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._engine: AsyncEngine | None = None
        self._expected_head: str | None = None
        self.last_expected_revision: str | None = None
        self.last_applied_revision: str | None = None

    @property
    def required(self) -> bool:
        return self._settings.database_required

    def _get_engine(self) -> AsyncEngine | None:
        if not self._settings.database_url:
            return None
        if self._engine is None:
            self._engine = create_async_engine(
                self._settings.database_url,
                pool_pre_ping=True,
                pool_recycle=300,
            )
        return self._engine

    def _get_expected_head(self) -> str:
        if self._expected_head is None:
            self._expected_head = _compute_expected_schema_head()
        return self._expected_head

    @staticmethod
    def _read_applied_revision(connection: Connection) -> str | None:
        # `alembic_version` (single column `version_num`) is the standard table Alembic
        # itself creates and maintains to record the currently-applied revision -- see
        # https://alembic.sqlalchemy.org (the "Version Table Configuration" reference).
        # `Inspector.has_table` is portable across backends, unlike the postgres-only
        # `to_regclass`, and never leaves a failed statement/aborted transaction behind
        # the way probing via a caught `ProgrammingError` would.
        if not inspect(connection).has_table("alembic_version"):
            return None
        raw = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one_or_none()
        return None if raw is None else str(raw)

    async def check(self) -> ComponentHealth:
        engine = self._get_engine()
        if engine is None:
            state = ComponentState.UNAVAILABLE if self.required else ComponentState.DISABLED
            code = "database_url_missing" if self.required else "database_not_configured"
            return ComponentHealth(name=self.name, status=state, required=self.required, code=code)

        expected = self._get_expected_head()
        self.last_expected_revision = expected

        try:
            async with asyncio.timeout(self._settings.database_probe_timeout_seconds):
                async with engine.connect() as connection:
                    applied = await connection.run_sync(self._read_applied_revision)
        except Exception as exc:
            logger.warning(
                "schema_compatibility_check_failed", extra={"error_type": type(exc).__name__}
            )
            self.last_applied_revision = None
            return ComponentHealth(
                name=self.name,
                status=ComponentState.UNAVAILABLE,
                required=self.required,
                code="database_unavailable",
            )

        self.last_applied_revision = applied

        state, code = _classify_schema_compatibility(
            expected_revision=expected, applied_revision=applied
        )
        if code == "schema_not_migrated":
            logger.warning("schema_not_migrated", extra={"expected_revision": expected})
        elif code == "schema_incompatible":
            logger.error(
                "schema_incompatible",
                extra={"expected_revision": expected, "applied_revision": applied},
            )
        return ComponentHealth(name=self.name, status=state, required=self.required, code=code)

    async def close(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
