from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine

from atlas.core.persistence.models import (
    BundledConnectionConfigurationModel,
    BundledConnectorRuntimeStateModel,
    ConnectorConnectionTestResultModel,
)
from atlas.modules.connectors.adapters.bundled_operator_state_postgres import (
    PostgreSQLBundledConnectionConfigurationRepository,
    PostgreSQLBundledConnectorRuntimeStateRepository,
    PostgreSQLConnectorConnectionTestResultRepository,
)
from atlas.modules.connectors.domain.bundled_connection_configuration import (
    BundledConnectionConfiguration,
)
from atlas.modules.connectors.domain.bundled_runtime_state import (
    DISABLED,
    ENABLED_READ_ONLY,
    BundledConnectorRuntimeState,
)
from atlas.modules.connectors.domain.connection_test import ConnectorConnectionTestResult
from atlas.modules.connectors.vendors.hitachi_ops_center.manifest import PACKAGE_ID


@pytest.mark.asyncio
async def test_live_postgres_restores_bundled_operator_state_and_rejects_stale_version() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")

    suffix = uuid4().hex
    organization_id = f"organization.persistence.{suffix}"
    environment_id = "environment.development"
    instance_id = f"connector-instance.{suffix}"
    configuration_id = f"connection-configuration.{suffix}"
    test_id = f"connection-test.{suffix}"
    now = datetime.now(UTC)
    engine = create_async_engine(database_url, pool_pre_ping=True)
    configuration_repository = PostgreSQLBundledConnectionConfigurationRepository(engine)
    result_repository = PostgreSQLConnectorConnectionTestResultRepository(engine)
    runtime_repository = PostgreSQLBundledConnectorRuntimeStateRepository(engine)
    try:
        configuration = BundledConnectionConfiguration(
            configuration_id=configuration_id,
            organization_id=organization_id,
            environment_id=environment_id,
            connector_id=PACKAGE_ID,
            instance_id=instance_id,
            hostname="opscenter.persistence.example",
            port=23451,
            trust_profile_id="trust.system-ca",
            secret_reference_id="secret.hitachi.persistence",
            configured_by="subject.persistence.operator",
            configured_at=now,
        )
        result = ConnectorConnectionTestResult(
            test_id=test_id,
            connector_id=PACKAGE_ID,
            instance_id=instance_id,
            outcome="passed",
            result_code="connection_test_passed",
            retryable=False,
            checked_at=now,
            duration_ms=42,
            read_only_request_performed=True,
            managed_infrastructure_contacted=True,
        )
        enabled = BundledConnectorRuntimeState(
            organization_id=organization_id,
            environment_id=environment_id,
            connector_id=PACKAGE_ID,
            instance_id=instance_id,
            state=ENABLED_READ_ONLY,
            version=1,
            changed_at=now,
            changed_by="subject.persistence.operator",
            reason="Enable bounded read-only health polling for the persisted MCP.",
            configuration_id=configuration_id,
            connection_test_id=test_id,
        )

        await configuration_repository.put(configuration)
        await result_repository.put(
            organization_id=organization_id,
            environment_id=environment_id,
            result=result,
        )
        assert await runtime_repository.put(enabled, expected_version=0) is True

        restored_configuration = await PostgreSQLBundledConnectionConfigurationRepository(
            engine
        ).get(
            organization_id=organization_id,
            environment_id=environment_id,
            instance_id=instance_id,
        )
        restored_result = await PostgreSQLConnectorConnectionTestResultRepository(
            engine
        ).get_latest(
            organization_id=organization_id,
            environment_id=environment_id,
            instance_id=instance_id,
        )
        restored_runtime = await PostgreSQLBundledConnectorRuntimeStateRepository(engine).get(
            organization_id=organization_id,
            environment_id=environment_id,
            instance_id=instance_id,
        )

        assert restored_configuration == configuration
        assert restored_result == result
        assert restored_runtime == enabled

        disabled = BundledConnectorRuntimeState(
            organization_id=organization_id,
            environment_id=environment_id,
            connector_id=PACKAGE_ID,
            instance_id=instance_id,
            state=DISABLED,
            version=2,
            changed_at=now,
            changed_by="subject.persistence.operator",
            reason="Disable persisted MCP runtime after the bounded verification run.",
            configuration_id=configuration_id,
            connection_test_id=test_id,
        )
        assert await runtime_repository.put(disabled, expected_version=0) is False
        assert await runtime_repository.put(disabled, expected_version=1) is True
        assert (
            await runtime_repository.get(
                organization_id=organization_id,
                environment_id=environment_id,
                instance_id=instance_id,
            )
            == disabled
        )
    finally:
        async with engine.begin() as connection:
            for model in (
                BundledConnectorRuntimeStateModel,
                ConnectorConnectionTestResultModel,
                BundledConnectionConfigurationModel,
            ):
                await connection.execute(
                    delete(model).where(model.organization_id == organization_id)
                )
        await engine.dispose()
