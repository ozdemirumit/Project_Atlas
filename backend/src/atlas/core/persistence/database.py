from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from atlas.core.config import Settings
from atlas.modules.platform.domain.status import ComponentHealth, ComponentState

logger = logging.getLogger(__name__)


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
