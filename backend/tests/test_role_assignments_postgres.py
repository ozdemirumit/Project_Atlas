"""Durable RBAC role assignments (docs/031_RBAC.md Sec.11/26): live-Postgres round-trip for
`PostgreSQLRoleAssignmentRepository`, the dynamic counterpart to the static, code-level
assignment list `AuthorizationService` is otherwise built from entirely at startup.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine

from atlas.core.persistence.models import RoleAssignmentModel
from atlas.modules.authorization.adapters.role_assignment_postgres import (
    PostgreSQLRoleAssignmentRepository,
)
from atlas.modules.authorization.domain.models import CapabilityClass, ResourceScope, RoleAssignment


@pytest.mark.asyncio
async def test_live_postgres_role_assignment_round_trip_and_expiry() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")

    suffix = uuid4().hex
    subject_id = f"subject.role-assignment-persistence.{suffix}"
    now = datetime.now(UTC)
    scope = ResourceScope(
        organization_id="organization.persistence",
        environment_id="environment.test",
        site_id="site.local",
        domain_id="domain.authorization",
        resource_id="resource.authorization.role-assignments",
        capability_class=CapabilityClass.C1_READ_ONLY,
    )
    engine = create_async_engine(database_url, pool_pre_ping=True)
    repository = PostgreSQLRoleAssignmentRepository(engine)
    try:
        active = RoleAssignment(
            assignment_id=f"assignment.{suffix}.active",
            version=1,
            subject_id=subject_id,
            role_id="role.local-monitor",
            scope=scope,
            valid_from=now - timedelta(minutes=1),
        )
        expired = RoleAssignment(
            assignment_id=f"assignment.{suffix}.expired",
            version=1,
            subject_id=subject_id,
            role_id="role.local-monitor",
            scope=scope,
            valid_from=now - timedelta(hours=2),
            expires_at=now - timedelta(hours=1),
        )
        assert await repository.create(active) is True
        assert await repository.create(active) is False
        assert await repository.create(expired) is True

        live = await repository.list_active_for_subject(subject_id=subject_id, at=now)
        assert live == (active,)

        other_subject = await repository.list_active_for_subject(
            subject_id=f"subject.unrelated.{suffix}", at=now
        )
        assert other_subject == ()
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                delete(RoleAssignmentModel).where(RoleAssignmentModel.subject_id == subject_id)
            )
        await engine.dispose()
