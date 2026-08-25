from __future__ import annotations

import asyncio
import inspect
import os
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from test_workflow_protected_runtime_process_creation_authorizations_postgres import (
    _authorize_process_creation,
    _cleanup_fixture_fences,
    _cleanup_process_creation,
    _FixtureProcessCreationRepository,
    _process_service,
    _seed_fixture_fences,
    _seed_ready_result,
)
from test_workflow_protected_runtime_readiness_authorizations_postgres import (
    _AcceptAllReceiptVerifier,
)
from test_workflow_protected_runtime_readiness_consumptions_postgres import (
    _cleanup as _cleanup_readiness,
)

from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.adapters.protected_runtime_process_creators import (
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationInstructionSignatureVerifier,
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationInstructionSigner,
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier,
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreator,
)
from atlas.modules.workflows.application.protected_runtime_process_creation_consumption_ports import (  # noqa: E501
    WorkflowProtectedRuntimeProcessCreationConsumptionError,
)
from atlas.modules.workflows.application.protected_runtime_process_creation_consumptions import (
    WorkflowProtectedRuntimeProcessCreationConsumptionService,
)
from atlas.modules.workflows.domain.protected_runtime_process_creation_consumption_domain import (
    WorkflowProtectedRuntimeProcessCreationConsumptionResultState,
    code_owned_workflow_protected_runtime_process_creation_consumption_policy,
)


class _ConsumptionFixtureProcessCreationRepository(_FixtureProcessCreationRepository):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._fixture_time: datetime | None = None

    def bind_fixture_time(self, value: datetime) -> None:
        self._fixture_time = value

    def fixture_time(self) -> datetime:
        assert self._fixture_time is not None
        return self._fixture_time

    async def get_authoritative_time(self) -> datetime:
        if self._fixture_time is not None:
            return self._fixture_time
        return await super().get_authoritative_time()

    async def _lock_protected_runtime_process_creation_authorization_rows(
        self,
        session: Any,
        *,
        readiness_result_id: str,
        scope: Any,
        consumer_subject_id: str,
        consumer_audience: str,
        idempotency_key: str | None,
        for_update: bool = True,
    ) -> Any:
        locked = await super()._lock_protected_runtime_process_creation_authorization_rows(
            session,
            readiness_result_id=readiness_result_id,
            scope=scope,
            consumer_subject_id=consumer_subject_id,
            consumer_audience=consumer_audience,
            idempotency_key=idempotency_key,
            for_update=for_update,
        )
        if self._fixture_time is None:
            return locked
        return replace(
            locked,
            first_observed_at=self._fixture_time,
            observed_at=self._fixture_time,
        )

    async def _lock_protected_runtime_process_creation_rows(
        self, session: Any, *, request: Any
    ) -> Any:
        locked = await super()._lock_protected_runtime_process_creation_rows(
            session, request=request
        )
        if self._fixture_time is None:
            return locked
        return replace(
            locked,
            authorization=replace(
                locked.authorization,
                first_observed_at=self._fixture_time,
                observed_at=self._fixture_time,
            ),
            observed_at=self._fixture_time,
        )

    async def _lock_protected_runtime_process_creation_result_rows(
        self, session: Any, *, request: Any
    ) -> Any:
        locked = await super()._lock_protected_runtime_process_creation_result_rows(
            session, request=request
        )
        if self._fixture_time is None:
            return locked
        return replace(locked, observed_at=self._fixture_time)


async def _cleanup_consumption(engine: AsyncEngine, *, authorization_lease_id: str) -> None:
    async with engine.begin() as connection:
        await connection.execute(text("SET LOCAL session_replication_role = replica"))
        for table in (
            "workflow_event_runtime_process_creation_results",
            "workflow_event_runtime_process_creation_attempts",
            "workflow_event_runtime_process_creation_consumption_claims",
        ):
            await connection.execute(
                text(f"DELETE FROM {table} WHERE authorization_lease_id = :lease_id"),
                {"lease_id": authorization_lease_id},
            )
        await connection.execute(text("SET LOCAL session_replication_role = origin"))


def test_postgres_claim_commit_ambiguity_is_terminal_and_non_retrying() -> None:
    source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.claim_protected_runtime_process_creation
    )

    assert "except SQLAlchemyError:" in source
    assert "statuses.REPLAY_UNCERTAIN" in source


def test_postgres_result_write_reverifies_creator_receipt_signature() -> None:
    source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._protected_runtime_process_creation_result_is_valid
    )

    assert "_protected_runtime_process_creation_receipt_signature_verifier" in source
    assert ".verify_receipt(" in source
    assert "is True" in source


@pytest.mark.asyncio
async def test_live_postgres_atomic_consumption_and_exact_replay_call_creator_once() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")

    engine = create_async_engine(database_url)
    repository = _ConsumptionFixtureProcessCreationRepository(engine=engine)
    repository.bind_protected_runtime_start_receipt_signature_verifier(
        cast(Any, _AcceptAllReceiptVerifier())
    )
    receipt_verifier = (
        DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier(
            development_enabled=True
        )
    )
    repository.bind_protected_runtime_process_creation_receipt_signature_verifier(receipt_verifier)
    creator = DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreator(
        development_enabled=True,
        clock=repository.fixture_time,
    )
    service = WorkflowProtectedRuntimeProcessCreationConsumptionService(
        repository=cast(Any, repository),
        instruction_signer=(
            DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationInstructionSigner(
                development_enabled=True
            )
        ),
        instruction_signature_verifier=(
            DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationInstructionSignatureVerifier(
                development_enabled=True
            )
        ),
        receipt_signature_verifier=receipt_verifier,
        creator=creator,
    )
    seeded: list[Any] = []
    readiness_result: Any | None = None
    authorization_lease_id: str | None = None
    try:
        start_request, readiness_result = await _seed_ready_result(
            engine,
            repository,
            suffix=f"imp228-consumption-{uuid4().hex[:12]}",
        )
        seeded.append(start_request)
        await _seed_fixture_fences(engine, repository, readiness_result)
        repository.bind_fixture_time(await repository.get_authoritative_time())
        authorization = await _authorize_process_creation(
            _process_service(repository),
            readiness_result,
            idempotency_key=f"imp-228-authorization-{uuid4().hex}",
        )
        authorization_lease_id = authorization.authorization_lease_id
        repository.bind_fixture_time(authorization.issued_at + timedelta(milliseconds=200))
        policy = code_owned_workflow_protected_runtime_process_creation_consumption_policy()
        request = {
            "authorization_lease_id": authorization_lease_id,
            "scope": readiness_result.scope,
            "consumer_subject_id": policy.consumer_subject_id,
            "consumer_audience": policy.consumer_audience,
            "consumer_contract_id": policy.consumer_contract_id,
            "consumer_contract_version": policy.consumer_contract_version,
            "irreversible_consumption_acknowledged": True,
            "uncertainty_no_retry_acknowledged": True,
            "idempotency_key": f"imp-228-consumption-{uuid4().hex}",
        }

        concurrent = await asyncio.gather(
            service.consume(**cast(Any, request)),
            service.consume(**cast(Any, request)),
            return_exceptions=True,
        )
        successes = [item for item in concurrent if not isinstance(item, BaseException)]
        failures = [item for item in concurrent if isinstance(item, BaseException)]
        failure_codes = [getattr(item, "code", type(item).__name__) for item in failures]
        assert len(successes) == 1, failure_codes
        assert len(failures) == 1, failure_codes
        assert isinstance(failures[0], WorkflowProtectedRuntimeProcessCreationConsumptionError)
        assert failures[0].code.endswith("attempt_committed_no_retry")
        first = successes[0]
        replay = await service.consume(**cast(Any, request))

        assert first == replay
        assert first.result is not None
        result_states = WorkflowProtectedRuntimeProcessCreationConsumptionResultState
        assert (
            first.result.result_state
            is result_states.PROCESS_CREATED_SUSPENDED_IN_PROTECTED_BOUNDARY
        )
        assert len(creator.calls) == 1
        assert first.result.process_created is True
        assert first.result.process_sealed is True
        assert first.result.process_suspended is True
        assert first.result.process_scheduled is False
        assert first.result.process_executed is False
    finally:
        if authorization_lease_id is not None:
            await _cleanup_consumption(engine, authorization_lease_id=authorization_lease_id)
        if readiness_result is not None:
            await _cleanup_process_creation(engine, readiness_result_id=readiness_result.result_id)
            await _cleanup_fixture_fences(
                engine,
                repository,
                readiness_result_id=readiness_result.result_id,
            )
        if seeded:
            await _cleanup_readiness(engine, tuple(seeded))
        await engine.dispose()
