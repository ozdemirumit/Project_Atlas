from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import BootstrapRunModel
from atlas.modules.platform.application.bootstrap_state_ports import BootstrapRepositoryError
from atlas.modules.platform.domain.bootstrap_artifact_acquisition import (
    ArtifactAcquisitionExecution,
    ArtifactAcquisitionState,
    ArtifactDisposition,
    VerifiedArtifactEvidence,
)
from atlas.modules.platform.domain.bootstrap_configuration_rendering import (
    ConfigurationFileDisposition,
    ConfigurationRenderingExecution,
    ConfigurationRenderingState,
    RenderedConfigurationEvidence,
)
from atlas.modules.platform.domain.bootstrap_data_initialization import (
    BackupApplicability,
    DataInitializationExecution,
    DataInitializationState,
    DataStateDisposition,
    DataStateEvidence,
)
from atlas.modules.platform.domain.bootstrap_identity_handoff import (
    IdentityHandoffExecution,
    IdentityHandoffState,
    IdentityStateDisposition,
    IdentityStateEvidence,
)
from atlas.modules.platform.domain.bootstrap_integration_validation import (
    IntegrationCheckState,
    IntegrationStateDisposition,
    IntegrationStateEvidence,
    IntegrationValidationCheck,
    IntegrationValidationExecution,
    IntegrationValidationState,
)
from atlas.modules.platform.domain.bootstrap_invalidation import compare_bootstrap_run
from atlas.modules.platform.domain.bootstrap_service_deployment import (
    ServiceDeploymentExecution,
    ServiceDeploymentState,
    ServiceRuntimeState,
    ServiceStateDisposition,
    ServiceStateEvidence,
    ServiceStatusEvidence,
)
from atlas.modules.platform.domain.bootstrap_state import (
    BootstrapCheckpointState,
    BootstrapMutationResult,
    BootstrapPhaseCheckpoint,
    BootstrapRunIdentity,
    BootstrapRunRecord,
    BootstrapRunState,
)
from atlas.modules.platform.domain.bootstrap_trust_provisioning import (
    TrustFileDisposition,
    TrustFileEvidence,
    TrustProvisioningExecution,
    TrustProvisioningState,
)
from atlas.modules.platform.domain.release_preflight import AcquisitionMode, DeploymentProfile


class PostgreSQLBootstrapStateRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLBootstrapStateRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    async def get_current(
        self, *, organization_id: str, environment_id: str, site_id: str
    ) -> BootstrapRunRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(BootstrapRunModel).where(
                    BootstrapRunModel.organization_id == organization_id,
                    BootstrapRunModel.environment_id == environment_id,
                    BootstrapRunModel.site_id == site_id,
                )
            )
            return self._to_domain(row) if row is not None else None

    async def claim(
        self,
        *,
        identity: BootstrapRunIdentity,
        lease_holder_id: str,
        lease_duration: timedelta,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult:
        scope = self._scope(identity.organization_id, identity.environment_id, identity.site_id)
        async with self._sessions.begin() as session:
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
                {"scope": scope},
            )
            row = await session.scalar(
                select(BootstrapRunModel)
                .where(
                    BootstrapRunModel.organization_id == identity.organization_id,
                    BootstrapRunModel.environment_id == identity.environment_id,
                    BootstrapRunModel.site_id == identity.site_id,
                )
                .with_for_update()
            )
            replay = self._replay(row, lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            reclaimed = False
            if row is None:
                run_digest = sha256(f"{scope}/{identity.resume_key}".encode()).hexdigest()[:24]
                record = BootstrapRunRecord(
                    run_id=f"bootstrap-run.{run_digest}",
                    version=1,
                    identity=identity,
                    state=BootstrapRunState.ACTIVE,
                    checkpoints=(),
                    lease_holder_id=lease_holder_id,
                    lease_acquired_at=now,
                    lease_expires_at=now + lease_duration,
                    created_at=now,
                    updated_at=now,
                )
                row = self._new_model(record)
                session.add(row)
            else:
                current = self._to_domain(row)
                if current.identity != identity:
                    raise BootstrapRepositoryError("bootstrap_plan_mismatch")
                if current.state is BootstrapRunState.COMPLETED:
                    raise BootstrapRepositoryError("bootstrap_run_completed")
                if current.lease_is_active(now):
                    raise BootstrapRepositoryError("bootstrap_lease_unavailable")
                reclaimed = current.lease_expires_at is not None
                if (
                    reclaimed
                    and current.artifact_acquisition is not None
                    and current.artifact_acquisition.state is ArtifactAcquisitionState.RUNNING
                ):
                    interrupted = replace(
                        current.artifact_acquisition,
                        state=ArtifactAcquisitionState.FAILED,
                        result_code="bootstrap.artifact.interrupted",
                        completed_at=now,
                    )
                    failed_checkpoint = BootstrapPhaseCheckpoint(
                        phase_id="phase.acquire",
                        state=BootstrapCheckpointState.FAILED,
                        safe_output_references=(
                            "result.artifact-acquisition."
                            f"{sha256(interrupted.execution_id.encode()).hexdigest()[:24]}",
                        ),
                        recorded_at=now,
                    )
                    current = replace(
                        current,
                        checkpoints=(
                            *(
                                item
                                for item in current.checkpoints
                                if item.phase_id != "phase.acquire"
                            ),
                            failed_checkpoint,
                        ),
                        artifact_acquisition=interrupted,
                    )
                if (
                    reclaimed
                    and current.configuration_rendering is not None
                    and current.configuration_rendering.state is ConfigurationRenderingState.RUNNING
                ):
                    interrupted_configuration = replace(
                        current.configuration_rendering,
                        state=ConfigurationRenderingState.FAILED,
                        result_code="bootstrap.configuration.interrupted",
                        completed_at=now,
                    )
                    failed_configuration_checkpoint = BootstrapPhaseCheckpoint(
                        phase_id="phase.configure",
                        state=BootstrapCheckpointState.FAILED,
                        safe_output_references=(
                            "result.configuration-rendering."
                            f"{sha256(interrupted_configuration.execution_id.encode()).hexdigest()[:24]}",
                        ),
                        recorded_at=now,
                    )
                    current = replace(
                        current,
                        checkpoints=(
                            *(
                                item
                                for item in current.checkpoints
                                if item.phase_id != "phase.configure"
                            ),
                            failed_configuration_checkpoint,
                        ),
                        configuration_rendering=interrupted_configuration,
                    )
                if (
                    reclaimed
                    and current.trust_provisioning is not None
                    and current.trust_provisioning.state is TrustProvisioningState.RUNNING
                ):
                    interrupted_trust = replace(
                        current.trust_provisioning,
                        state=TrustProvisioningState.FAILED,
                        result_code="bootstrap.trust.interrupted",
                        completed_at=now,
                    )
                    failed_trust_checkpoint = BootstrapPhaseCheckpoint(
                        phase_id="phase.trust",
                        state=BootstrapCheckpointState.FAILED,
                        safe_output_references=(
                            "result.trust-provisioning."
                            f"{sha256(interrupted_trust.execution_id.encode()).hexdigest()[:24]}",
                        ),
                        recorded_at=now,
                    )
                    current = replace(
                        current,
                        checkpoints=(
                            *(
                                item
                                for item in current.checkpoints
                                if item.phase_id != "phase.trust"
                            ),
                            failed_trust_checkpoint,
                        ),
                        trust_provisioning=interrupted_trust,
                    )
                if (
                    reclaimed
                    and current.data_initialization is not None
                    and current.data_initialization.state is DataInitializationState.RUNNING
                ):
                    interrupted_data = replace(
                        current.data_initialization,
                        state=DataInitializationState.FAILED,
                        result_code="bootstrap.data.interrupted",
                        completed_at=now,
                        lock_acquired=False,
                    )
                    failed_data_checkpoint = BootstrapPhaseCheckpoint(
                        phase_id="phase.data",
                        state=BootstrapCheckpointState.FAILED,
                        safe_output_references=(
                            "result.data-initialization."
                            f"{sha256(interrupted_data.execution_id.encode()).hexdigest()[:24]}",
                        ),
                        recorded_at=now,
                    )
                    current = replace(
                        current,
                        checkpoints=(
                            *(
                                item
                                for item in current.checkpoints
                                if item.phase_id != "phase.data"
                            ),
                            failed_data_checkpoint,
                        ),
                        data_initialization=interrupted_data,
                    )
                if (
                    reclaimed
                    and current.service_deployment is not None
                    and current.service_deployment.state is ServiceDeploymentState.RUNNING
                ):
                    interrupted_services = replace(
                        current.service_deployment,
                        state=ServiceDeploymentState.FAILED,
                        result_code="bootstrap.services.interrupted",
                        completed_at=now,
                    )
                    failed_service_checkpoint = BootstrapPhaseCheckpoint(
                        phase_id="phase.services",
                        state=BootstrapCheckpointState.FAILED,
                        safe_output_references=(
                            "result.service-deployment."
                            f"{sha256(interrupted_services.execution_id.encode()).hexdigest()[:24]}",
                        ),
                        recorded_at=now,
                    )
                    current = replace(
                        current,
                        checkpoints=(
                            *(
                                item
                                for item in current.checkpoints
                                if item.phase_id != "phase.services"
                            ),
                            failed_service_checkpoint,
                        ),
                        service_deployment=interrupted_services,
                    )
                if (
                    reclaimed
                    and current.identity_handoff is not None
                    and current.identity_handoff.state is IdentityHandoffState.RUNNING
                ):
                    interrupted_identity = replace(
                        current.identity_handoff,
                        state=IdentityHandoffState.FAILED,
                        result_code="bootstrap.identity.interrupted",
                        completed_at=now,
                    )
                    failed_identity_checkpoint = BootstrapPhaseCheckpoint(
                        phase_id="phase.identity",
                        state=BootstrapCheckpointState.FAILED,
                        safe_output_references=(
                            "result.identity-handoff."
                            f"{sha256(interrupted_identity.execution_id.encode()).hexdigest()[:24]}",
                        ),
                        recorded_at=now,
                    )
                    current = replace(
                        current,
                        checkpoints=(
                            *(
                                item
                                for item in current.checkpoints
                                if item.phase_id != "phase.identity"
                            ),
                            failed_identity_checkpoint,
                        ),
                        identity_handoff=interrupted_identity,
                    )
                if (
                    reclaimed
                    and current.integration_validation is not None
                    and current.integration_validation.state is IntegrationValidationState.RUNNING
                ):
                    interrupted_integrations = replace(
                        current.integration_validation,
                        state=IntegrationValidationState.FAILED,
                        result_code="bootstrap.integrations.interrupted",
                        completed_at=now,
                    )
                    failed_integration_checkpoint = BootstrapPhaseCheckpoint(
                        phase_id="phase.integrations",
                        state=BootstrapCheckpointState.FAILED,
                        safe_output_references=(
                            "result.integration-validation."
                            f"{sha256(interrupted_integrations.execution_id.encode()).hexdigest()[:24]}",
                        ),
                        recorded_at=now,
                    )
                    current = replace(
                        current,
                        checkpoints=(
                            *(
                                item
                                for item in current.checkpoints
                                if item.phase_id != "phase.integrations"
                            ),
                            failed_integration_checkpoint,
                        ),
                        integration_validation=interrupted_integrations,
                    )
                record = replace(
                    current,
                    version=current.version + 1,
                    state=(
                        BootstrapRunState.FAILED
                        if current.failed_phase_id is not None
                        else BootstrapRunState.ACTIVE
                    ),
                    lease_holder_id=lease_holder_id,
                    lease_acquired_at=now,
                    lease_expires_at=now + lease_duration,
                    updated_at=now,
                )
                self._apply(row, record)
            result = BootstrapMutationResult(
                record=record, replayed=False, reclaimed_expired_lease=reclaimed
            )
            self._remember(row, lease_holder_id, idempotency_key, request_fingerprint, result)
            return result

    async def checkpoint(
        self,
        *,
        run_id: str,
        plan_digest: str,
        resume_key: str,
        phase_id: str,
        state: BootstrapCheckpointState,
        safe_output_references: tuple[str, ...],
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult:
        async with self._sessions.begin() as session:
            row = await session.scalar(
                select(BootstrapRunModel)
                .where(BootstrapRunModel.run_id == run_id)
                .with_for_update()
            )
            if row is None:
                raise BootstrapRepositoryError("bootstrap_run_unavailable")
            replay = self._replay(row, lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            current = self._to_domain(row)
            self._require_no_running_phase(current)
            if (
                current.identity.plan_digest != plan_digest
                or current.identity.resume_key != resume_key
            ):
                raise BootstrapRepositoryError("bootstrap_plan_mismatch")
            self._require_lease(current, lease_holder_id, now)
            if current.version != expected_version:
                raise BootstrapRepositoryError("bootstrap_stale_revision")
            if current.state is BootstrapRunState.COMPLETED:
                raise BootstrapRepositoryError("bootstrap_run_completed")
            if phase_id not in current.identity.phase_ids:
                raise BootstrapRepositoryError("bootstrap_phase_unavailable")
            phase_index = current.identity.phase_ids.index(phase_id)
            completed = set(current.completed_phase_ids)
            if any(item not in completed for item in current.identity.phase_ids[:phase_index]):
                raise BootstrapRepositoryError("bootstrap_dependency_unsatisfied")
            if current.current_phase_id != phase_id:
                raise BootstrapRepositoryError("bootstrap_phase_out_of_order")
            checkpoint = BootstrapPhaseCheckpoint(
                phase_id=phase_id,
                state=state,
                safe_output_references=safe_output_references,
                recorded_at=now,
            )
            checkpoints = (
                *(item for item in current.checkpoints if item.phase_id != phase_id),
                checkpoint,
            )
            completed_after = {
                item.phase_id
                for item in checkpoints
                if item.state is BootstrapCheckpointState.COMPLETED
            }
            if state is BootstrapCheckpointState.FAILED:
                run_state = BootstrapRunState.FAILED
            elif len(completed_after) == len(current.identity.phase_ids):
                run_state = BootstrapRunState.COMPLETED
            else:
                run_state = BootstrapRunState.ACTIVE
            record = replace(
                current,
                version=current.version + 1,
                state=run_state,
                checkpoints=checkpoints,
                updated_at=now,
            )
            self._apply(row, record)
            result = BootstrapMutationResult(record=record, replayed=False)
            self._remember(row, lease_holder_id, idempotency_key, request_fingerprint, result)
            return result

    async def begin_artifact_acquisition(
        self,
        *,
        run_id: str,
        plan_digest: str,
        resume_key: str,
        execution: ArtifactAcquisitionExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult:
        async with self._sessions.begin() as session:
            row = await session.scalar(
                select(BootstrapRunModel)
                .where(BootstrapRunModel.run_id == run_id)
                .with_for_update()
            )
            if row is None:
                raise BootstrapRepositoryError("bootstrap_run_unavailable")
            replay = self._replay(row, lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            current = self._to_domain(row)
            self._require_no_running_phase(current)
            if (
                current.identity.plan_digest != plan_digest
                or current.identity.resume_key != resume_key
            ):
                raise BootstrapRepositoryError("bootstrap_plan_mismatch")
            self._require_lease(current, lease_holder_id, now)
            if current.version != expected_version:
                raise BootstrapRepositoryError("bootstrap_stale_revision")
            if current.state is BootstrapRunState.COMPLETED:
                raise BootstrapRepositoryError("bootstrap_run_completed")
            if current.current_phase_id != "phase.acquire" or execution.phase_id != "phase.acquire":
                raise BootstrapRepositoryError("bootstrap_phase_out_of_order")
            record = replace(
                current,
                version=current.version + 1,
                state=BootstrapRunState.ACTIVE,
                checkpoints=tuple(
                    item for item in current.checkpoints if item.phase_id != "phase.acquire"
                ),
                artifact_acquisition=execution,
                updated_at=now,
            )
            self._apply(row, record)
            result = BootstrapMutationResult(
                record=record,
                replayed=False,
                artifact_acquisition=execution,
            )
            self._remember(row, lease_holder_id, idempotency_key, request_fingerprint, result)
            return result

    async def begin_configuration_rendering(
        self,
        *,
        run_id: str,
        plan_digest: str,
        resume_key: str,
        execution: ConfigurationRenderingExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult:
        async with self._sessions.begin() as session:
            row = await session.scalar(
                select(BootstrapRunModel)
                .where(BootstrapRunModel.run_id == run_id)
                .with_for_update()
            )
            if row is None:
                raise BootstrapRepositoryError("bootstrap_run_unavailable")
            replay = self._replay(row, lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            current = self._to_domain(row)
            self._require_no_running_phase(current)
            if (
                current.identity.plan_digest != plan_digest
                or current.identity.resume_key != resume_key
            ):
                raise BootstrapRepositoryError("bootstrap_plan_mismatch")
            self._require_lease(current, lease_holder_id, now)
            if current.version != expected_version:
                raise BootstrapRepositoryError("bootstrap_stale_revision")
            if current.state is BootstrapRunState.COMPLETED:
                raise BootstrapRepositoryError("bootstrap_run_completed")
            if (
                current.current_phase_id != "phase.configure"
                or execution.phase_id != "phase.configure"
            ):
                raise BootstrapRepositoryError("bootstrap_phase_out_of_order")
            record = replace(
                current,
                version=current.version + 1,
                state=BootstrapRunState.ACTIVE,
                checkpoints=tuple(
                    item for item in current.checkpoints if item.phase_id != "phase.configure"
                ),
                configuration_rendering=execution,
                updated_at=now,
            )
            self._apply(row, record)
            result = BootstrapMutationResult(
                record=record,
                replayed=False,
                configuration_rendering=execution,
            )
            self._remember(row, lease_holder_id, idempotency_key, request_fingerprint, result)
            return result

    async def finish_configuration_rendering(
        self,
        *,
        run_id: str,
        execution: ConfigurationRenderingExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult:
        async with self._sessions.begin() as session:
            row = await session.scalar(
                select(BootstrapRunModel)
                .where(BootstrapRunModel.run_id == run_id)
                .with_for_update()
            )
            if row is None:
                raise BootstrapRepositoryError("bootstrap_run_unavailable")
            replay = self._replay(row, lease_holder_id, idempotency_key, request_fingerprint)
            if (
                replay is not None
                and replay.configuration_rendering is not None
                and replay.configuration_rendering.state is not ConfigurationRenderingState.RUNNING
            ):
                return replay
            current = self._to_domain(row)
            self._require_lease(current, lease_holder_id, now)
            if current.version != expected_version:
                raise BootstrapRepositoryError("bootstrap_stale_revision")
            active = current.configuration_rendering
            if (
                active is None
                or active.state is not ConfigurationRenderingState.RUNNING
                or active.execution_id != execution.execution_id
            ):
                raise BootstrapRepositoryError("bootstrap_phase_execution_unavailable")
            if (
                execution.state is ConfigurationRenderingState.RUNNING
                or execution.release_id != active.release_id
                or execution.profile is not active.profile
                or execution.configuration_schema_version != active.configuration_schema_version
                or execution.configuration_digest != active.configuration_digest
                or execution.started_at != active.started_at
            ):
                raise BootstrapRepositoryError("bootstrap_phase_execution_conflict")
            if execution.state is ConfigurationRenderingState.COMPLETED:
                reference = f"result.configuration.{execution.configuration_digest[:32]}"
                checkpoint_state = BootstrapCheckpointState.COMPLETED
                completed_after = len(current.completed_phase_ids) + 1
                run_state = (
                    BootstrapRunState.COMPLETED
                    if completed_after == len(current.identity.phase_ids)
                    else BootstrapRunState.ACTIVE
                )
            else:
                reference = (
                    "result.configuration-rendering."
                    f"{sha256(execution.result_code.encode()).hexdigest()[:24]}"
                )
                checkpoint_state = BootstrapCheckpointState.FAILED
                run_state = BootstrapRunState.FAILED
            checkpoint = BootstrapPhaseCheckpoint(
                phase_id="phase.configure",
                state=checkpoint_state,
                safe_output_references=(reference,),
                recorded_at=now,
            )
            record = replace(
                current,
                version=current.version + 1,
                state=run_state,
                checkpoints=(
                    *(item for item in current.checkpoints if item.phase_id != "phase.configure"),
                    checkpoint,
                ),
                configuration_rendering=execution,
                updated_at=now,
            )
            self._apply(row, record)
            result = BootstrapMutationResult(
                record=record,
                replayed=False,
                configuration_rendering=execution,
            )
            self._remember(row, lease_holder_id, idempotency_key, request_fingerprint, result)
            return result

    async def begin_trust_provisioning(
        self,
        *,
        run_id: str,
        plan_digest: str,
        resume_key: str,
        execution: TrustProvisioningExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult:
        async with self._sessions.begin() as session:
            row = await session.scalar(
                select(BootstrapRunModel)
                .where(BootstrapRunModel.run_id == run_id)
                .with_for_update()
            )
            if row is None:
                raise BootstrapRepositoryError("bootstrap_run_unavailable")
            replay = self._replay(row, lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            current = self._to_domain(row)
            self._require_no_running_phase(current)
            if (
                current.identity.plan_digest != plan_digest
                or current.identity.resume_key != resume_key
            ):
                raise BootstrapRepositoryError("bootstrap_plan_mismatch")
            self._require_lease(current, lease_holder_id, now)
            if current.version != expected_version:
                raise BootstrapRepositoryError("bootstrap_stale_revision")
            if current.state is BootstrapRunState.COMPLETED:
                raise BootstrapRepositoryError("bootstrap_run_completed")
            if current.current_phase_id != "phase.trust" or execution.phase_id != "phase.trust":
                raise BootstrapRepositoryError("bootstrap_phase_out_of_order")
            record = replace(
                current,
                version=current.version + 1,
                state=BootstrapRunState.ACTIVE,
                checkpoints=tuple(
                    item for item in current.checkpoints if item.phase_id != "phase.trust"
                ),
                trust_provisioning=execution,
                updated_at=now,
            )
            self._apply(row, record)
            result = BootstrapMutationResult(
                record=record,
                replayed=False,
                trust_provisioning=execution,
            )
            self._remember(row, lease_holder_id, idempotency_key, request_fingerprint, result)
            return result

    async def finish_trust_provisioning(
        self,
        *,
        run_id: str,
        execution: TrustProvisioningExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult:
        async with self._sessions.begin() as session:
            row = await session.scalar(
                select(BootstrapRunModel)
                .where(BootstrapRunModel.run_id == run_id)
                .with_for_update()
            )
            if row is None:
                raise BootstrapRepositoryError("bootstrap_run_unavailable")
            replay = self._replay(row, lease_holder_id, idempotency_key, request_fingerprint)
            if (
                replay is not None
                and replay.trust_provisioning is not None
                and replay.trust_provisioning.state is not TrustProvisioningState.RUNNING
            ):
                return replay
            current = self._to_domain(row)
            self._require_lease(current, lease_holder_id, now)
            if current.version != expected_version:
                raise BootstrapRepositoryError("bootstrap_stale_revision")
            active = current.trust_provisioning
            if (
                active is None
                or active.state is not TrustProvisioningState.RUNNING
                or active.execution_id != execution.execution_id
            ):
                raise BootstrapRepositoryError("bootstrap_phase_execution_unavailable")
            if (
                execution.state is TrustProvisioningState.RUNNING
                or execution.release_id != active.release_id
                or execution.profile is not active.profile
                or execution.configuration_digest != active.configuration_digest
                or execution.trust_schema_version != active.trust_schema_version
                or execution.trust_plan_digest != active.trust_plan_digest
                or execution.started_at != active.started_at
            ):
                raise BootstrapRepositoryError("bootstrap_phase_execution_conflict")
            if execution.state is TrustProvisioningState.COMPLETED:
                reference = f"result.trust.{execution.trust_plan_digest[:32]}"
                checkpoint_state = BootstrapCheckpointState.COMPLETED
                completed_after = len(current.completed_phase_ids) + 1
                run_state = (
                    BootstrapRunState.COMPLETED
                    if completed_after == len(current.identity.phase_ids)
                    else BootstrapRunState.ACTIVE
                )
            else:
                reference = (
                    "result.trust-provisioning."
                    f"{sha256(execution.result_code.encode()).hexdigest()[:24]}"
                )
                checkpoint_state = BootstrapCheckpointState.FAILED
                run_state = BootstrapRunState.FAILED
            checkpoint = BootstrapPhaseCheckpoint(
                phase_id="phase.trust",
                state=checkpoint_state,
                safe_output_references=(reference,),
                recorded_at=now,
            )
            record = replace(
                current,
                version=current.version + 1,
                state=run_state,
                checkpoints=(
                    *(item for item in current.checkpoints if item.phase_id != "phase.trust"),
                    checkpoint,
                ),
                trust_provisioning=execution,
                updated_at=now,
            )
            self._apply(row, record)
            result = BootstrapMutationResult(
                record=record,
                replayed=False,
                trust_provisioning=execution,
            )
            self._remember(row, lease_holder_id, idempotency_key, request_fingerprint, result)
            return result

    async def finish_artifact_acquisition(
        self,
        *,
        run_id: str,
        execution: ArtifactAcquisitionExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult:
        async with self._sessions.begin() as session:
            row = await session.scalar(
                select(BootstrapRunModel)
                .where(BootstrapRunModel.run_id == run_id)
                .with_for_update()
            )
            if row is None:
                raise BootstrapRepositoryError("bootstrap_run_unavailable")
            replay = self._replay(row, lease_holder_id, idempotency_key, request_fingerprint)
            if (
                replay is not None
                and replay.artifact_acquisition is not None
                and replay.artifact_acquisition.state is not ArtifactAcquisitionState.RUNNING
            ):
                return replay
            current = self._to_domain(row)
            self._require_lease(current, lease_holder_id, now)
            if current.version != expected_version:
                raise BootstrapRepositoryError("bootstrap_stale_revision")
            active = current.artifact_acquisition
            if (
                active is None
                or active.state is not ArtifactAcquisitionState.RUNNING
                or active.execution_id != execution.execution_id
            ):
                raise BootstrapRepositoryError("bootstrap_phase_execution_unavailable")
            if (
                execution.state is ArtifactAcquisitionState.RUNNING
                or execution.release_id != active.release_id
                or execution.manifest_digest != active.manifest_digest
                or execution.mode is not active.mode
                or execution.preflight_report_id != active.preflight_report_id
                or execution.started_at != active.started_at
            ):
                raise BootstrapRepositoryError("bootstrap_phase_execution_conflict")
            if execution.state is ArtifactAcquisitionState.COMPLETED:
                reference = f"artifact.receipt.{execution.manifest_digest[:32]}"
                checkpoint_state = BootstrapCheckpointState.COMPLETED
                run_state = (
                    BootstrapRunState.COMPLETED
                    if len(current.identity.phase_ids) == 1
                    else BootstrapRunState.ACTIVE
                )
            else:
                reference = (
                    "result.artifact-acquisition."
                    f"{sha256(execution.result_code.encode()).hexdigest()[:24]}"
                )
                checkpoint_state = BootstrapCheckpointState.FAILED
                run_state = BootstrapRunState.FAILED
            checkpoint = BootstrapPhaseCheckpoint(
                phase_id="phase.acquire",
                state=checkpoint_state,
                safe_output_references=(reference,),
                recorded_at=now,
            )
            record = replace(
                current,
                version=current.version + 1,
                state=run_state,
                checkpoints=(
                    *(item for item in current.checkpoints if item.phase_id != "phase.acquire"),
                    checkpoint,
                ),
                artifact_acquisition=execution,
                updated_at=now,
            )
            self._apply(row, record)
            result = BootstrapMutationResult(
                record=record,
                replayed=False,
                artifact_acquisition=execution,
            )
            self._remember(row, lease_holder_id, idempotency_key, request_fingerprint, result)
            return result

    async def release(
        self,
        *,
        run_id: str,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult:
        async with self._sessions.begin() as session:
            row = await session.scalar(
                select(BootstrapRunModel)
                .where(BootstrapRunModel.run_id == run_id)
                .with_for_update()
            )
            if row is None:
                raise BootstrapRepositoryError("bootstrap_run_unavailable")
            replay = self._replay(row, lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            current = self._to_domain(row)
            self._require_no_running_phase(current)
            self._require_lease(current, lease_holder_id, now)
            if current.version != expected_version:
                raise BootstrapRepositoryError("bootstrap_stale_revision")
            record = replace(
                current,
                version=current.version + 1,
                lease_holder_id=None,
                lease_acquired_at=None,
                lease_expires_at=None,
                updated_at=now,
            )
            self._apply(row, record)
            result = BootstrapMutationResult(record=record, replayed=False)
            self._remember(row, lease_holder_id, idempotency_key, request_fingerprint, result)
            return result

    async def begin_data_initialization(
        self,
        *,
        run_id: str,
        plan_digest: str,
        resume_key: str,
        execution: DataInitializationExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult:
        async with self._sessions.begin() as session:
            row = await session.scalar(
                select(BootstrapRunModel)
                .where(BootstrapRunModel.run_id == run_id)
                .with_for_update()
            )
            if row is None:
                raise BootstrapRepositoryError("bootstrap_run_unavailable")
            replay = self._replay(row, lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            current = self._to_domain(row)
            self._require_no_running_phase(current)
            if (
                current.identity.plan_digest != plan_digest
                or current.identity.resume_key != resume_key
            ):
                raise BootstrapRepositoryError("bootstrap_plan_mismatch")
            self._require_lease(current, lease_holder_id, now)
            if current.version != expected_version:
                raise BootstrapRepositoryError("bootstrap_stale_revision")
            if current.state is BootstrapRunState.COMPLETED:
                raise BootstrapRepositoryError("bootstrap_run_completed")
            if current.current_phase_id != "phase.data" or execution.phase_id != "phase.data":
                raise BootstrapRepositoryError("bootstrap_phase_out_of_order")
            record = replace(
                current,
                version=current.version + 1,
                state=BootstrapRunState.ACTIVE,
                checkpoints=tuple(
                    item for item in current.checkpoints if item.phase_id != "phase.data"
                ),
                data_initialization=execution,
                updated_at=now,
            )
            self._apply(row, record)
            result = BootstrapMutationResult(
                record=record, replayed=False, data_initialization=execution
            )
            self._remember(row, lease_holder_id, idempotency_key, request_fingerprint, result)
            return result

    async def finish_data_initialization(
        self,
        *,
        run_id: str,
        execution: DataInitializationExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult:
        async with self._sessions.begin() as session:
            row = await session.scalar(
                select(BootstrapRunModel)
                .where(BootstrapRunModel.run_id == run_id)
                .with_for_update()
            )
            if row is None:
                raise BootstrapRepositoryError("bootstrap_run_unavailable")
            replay = self._replay(row, lease_holder_id, idempotency_key, request_fingerprint)
            if (
                replay is not None
                and replay.data_initialization is not None
                and replay.data_initialization.state is not DataInitializationState.RUNNING
            ):
                return replay
            current = self._to_domain(row)
            self._require_lease(current, lease_holder_id, now)
            if current.version != expected_version:
                raise BootstrapRepositoryError("bootstrap_stale_revision")
            active = current.data_initialization
            if (
                active is None
                or active.state is not DataInitializationState.RUNNING
                or active.execution_id != execution.execution_id
            ):
                raise BootstrapRepositoryError("bootstrap_phase_execution_unavailable")
            if (
                execution.state is DataInitializationState.RUNNING
                or execution.release_id != active.release_id
                or execution.profile is not active.profile
                or execution.configuration_digest != active.configuration_digest
                or execution.trust_plan_digest != active.trust_plan_digest
                or execution.data_schema_version != active.data_schema_version
                or execution.data_plan_digest != active.data_plan_digest
                or execution.migration_artifact_digest != active.migration_artifact_digest
                or execution.target_id != active.target_id
                or execution.started_at != active.started_at
            ):
                raise BootstrapRepositoryError("bootstrap_phase_execution_conflict")
            if execution.state is DataInitializationState.COMPLETED:
                reference = f"result.data.{execution.data_plan_digest[:32]}"
                checkpoint_state = BootstrapCheckpointState.COMPLETED
                run_state = (
                    BootstrapRunState.COMPLETED
                    if len(current.completed_phase_ids) + 1 == len(current.identity.phase_ids)
                    else BootstrapRunState.ACTIVE
                )
            else:
                reference = (
                    "result.data-initialization."
                    f"{sha256(execution.result_code.encode()).hexdigest()[:24]}"
                )
                checkpoint_state = BootstrapCheckpointState.FAILED
                run_state = BootstrapRunState.FAILED
            checkpoint = BootstrapPhaseCheckpoint(
                phase_id="phase.data",
                state=checkpoint_state,
                safe_output_references=(reference,),
                recorded_at=now,
            )
            record = replace(
                current,
                version=current.version + 1,
                state=run_state,
                checkpoints=(
                    *(item for item in current.checkpoints if item.phase_id != "phase.data"),
                    checkpoint,
                ),
                data_initialization=execution,
                updated_at=now,
            )
            self._apply(row, record)
            result = BootstrapMutationResult(
                record=record, replayed=False, data_initialization=execution
            )
            self._remember(row, lease_holder_id, idempotency_key, request_fingerprint, result)
            return result

    async def begin_service_deployment(
        self,
        *,
        run_id: str,
        plan_digest: str,
        resume_key: str,
        execution: ServiceDeploymentExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult:
        async with self._sessions.begin() as session:
            row = await session.scalar(
                select(BootstrapRunModel)
                .where(BootstrapRunModel.run_id == run_id)
                .with_for_update()
            )
            if row is None:
                raise BootstrapRepositoryError("bootstrap_run_unavailable")
            replay = self._replay(row, lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            current = self._to_domain(row)
            self._require_no_running_phase(current)
            if (
                current.identity.plan_digest != plan_digest
                or current.identity.resume_key != resume_key
            ):
                raise BootstrapRepositoryError("bootstrap_plan_mismatch")
            self._require_lease(current, lease_holder_id, now)
            if current.version != expected_version:
                raise BootstrapRepositoryError("bootstrap_stale_revision")
            if current.state is BootstrapRunState.COMPLETED:
                raise BootstrapRepositoryError("bootstrap_run_completed")
            if (
                current.current_phase_id != "phase.services"
                or execution.phase_id != "phase.services"
            ):
                raise BootstrapRepositoryError("bootstrap_phase_out_of_order")
            record = replace(
                current,
                version=current.version + 1,
                state=BootstrapRunState.ACTIVE,
                checkpoints=tuple(
                    item for item in current.checkpoints if item.phase_id != "phase.services"
                ),
                service_deployment=execution,
                updated_at=now,
            )
            self._apply(row, record)
            result = BootstrapMutationResult(
                record=record, replayed=False, service_deployment=execution
            )
            self._remember(row, lease_holder_id, idempotency_key, request_fingerprint, result)
            return result

    async def finish_service_deployment(
        self,
        *,
        run_id: str,
        execution: ServiceDeploymentExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult:
        async with self._sessions.begin() as session:
            row = await session.scalar(
                select(BootstrapRunModel)
                .where(BootstrapRunModel.run_id == run_id)
                .with_for_update()
            )
            if row is None:
                raise BootstrapRepositoryError("bootstrap_run_unavailable")
            replay = self._replay(row, lease_holder_id, idempotency_key, request_fingerprint)
            if (
                replay is not None
                and replay.service_deployment is not None
                and replay.service_deployment.state is not ServiceDeploymentState.RUNNING
            ):
                return replay
            current = self._to_domain(row)
            self._require_lease(current, lease_holder_id, now)
            if current.version != expected_version:
                raise BootstrapRepositoryError("bootstrap_stale_revision")
            active = current.service_deployment
            if (
                active is None
                or active.state is not ServiceDeploymentState.RUNNING
                or active.execution_id != execution.execution_id
            ):
                raise BootstrapRepositoryError("bootstrap_phase_execution_unavailable")
            if (
                execution.state is ServiceDeploymentState.RUNNING
                or execution.release_id != active.release_id
                or execution.profile is not active.profile
                or execution.configuration_digest != active.configuration_digest
                or execution.trust_plan_digest != active.trust_plan_digest
                or execution.data_plan_digest != active.data_plan_digest
                or execution.migration_artifact_digest != active.migration_artifact_digest
                or execution.service_schema_version != active.service_schema_version
                or execution.service_plan_digest != active.service_plan_digest
                or execution.target_id != active.target_id
                or execution.started_at != active.started_at
            ):
                raise BootstrapRepositoryError("bootstrap_phase_execution_conflict")
            if execution.state is ServiceDeploymentState.COMPLETED:
                reference = f"result.services.{execution.service_plan_digest[:32]}"
                checkpoint_state = BootstrapCheckpointState.COMPLETED
                run_state = (
                    BootstrapRunState.COMPLETED
                    if len(current.completed_phase_ids) + 1 == len(current.identity.phase_ids)
                    else BootstrapRunState.ACTIVE
                )
            else:
                reference = (
                    "result.service-deployment."
                    f"{sha256(execution.result_code.encode()).hexdigest()[:24]}"
                )
                checkpoint_state = BootstrapCheckpointState.FAILED
                run_state = BootstrapRunState.FAILED
            checkpoint = BootstrapPhaseCheckpoint(
                phase_id="phase.services",
                state=checkpoint_state,
                safe_output_references=(reference,),
                recorded_at=now,
            )
            record = replace(
                current,
                version=current.version + 1,
                state=run_state,
                checkpoints=(
                    *(item for item in current.checkpoints if item.phase_id != "phase.services"),
                    checkpoint,
                ),
                service_deployment=execution,
                updated_at=now,
            )
            self._apply(row, record)
            result = BootstrapMutationResult(
                record=record, replayed=False, service_deployment=execution
            )
            self._remember(row, lease_holder_id, idempotency_key, request_fingerprint, result)
            return result

    async def begin_identity_handoff(
        self,
        *,
        run_id: str,
        plan_digest: str,
        resume_key: str,
        execution: IdentityHandoffExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult:
        async with self._sessions.begin() as session:
            row = await session.scalar(
                select(BootstrapRunModel)
                .where(BootstrapRunModel.run_id == run_id)
                .with_for_update()
            )
            if row is None:
                raise BootstrapRepositoryError("bootstrap_run_unavailable")
            replay = self._replay(row, lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            current = self._to_domain(row)
            self._require_no_running_phase(current)
            if (
                current.identity.plan_digest != plan_digest
                or current.identity.resume_key != resume_key
            ):
                raise BootstrapRepositoryError("bootstrap_plan_mismatch")
            self._require_lease(current, lease_holder_id, now)
            if current.version != expected_version:
                raise BootstrapRepositoryError("bootstrap_stale_revision")
            if current.state is BootstrapRunState.COMPLETED:
                raise BootstrapRepositoryError("bootstrap_run_completed")
            if (
                current.current_phase_id != "phase.identity"
                or execution.phase_id != "phase.identity"
            ):
                raise BootstrapRepositoryError("bootstrap_phase_out_of_order")
            record = replace(
                current,
                version=current.version + 1,
                state=BootstrapRunState.ACTIVE,
                checkpoints=tuple(
                    item for item in current.checkpoints if item.phase_id != "phase.identity"
                ),
                identity_handoff=execution,
                updated_at=now,
            )
            self._apply(row, record)
            result = BootstrapMutationResult(
                record=record, replayed=False, identity_handoff=execution
            )
            self._remember(row, lease_holder_id, idempotency_key, request_fingerprint, result)
            return result

    async def finish_identity_handoff(
        self,
        *,
        run_id: str,
        execution: IdentityHandoffExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult:
        async with self._sessions.begin() as session:
            row = await session.scalar(
                select(BootstrapRunModel)
                .where(BootstrapRunModel.run_id == run_id)
                .with_for_update()
            )
            if row is None:
                raise BootstrapRepositoryError("bootstrap_run_unavailable")
            replay = self._replay(row, lease_holder_id, idempotency_key, request_fingerprint)
            if (
                replay is not None
                and replay.identity_handoff is not None
                and replay.identity_handoff.state is not IdentityHandoffState.RUNNING
            ):
                return replay
            current = self._to_domain(row)
            self._require_lease(current, lease_holder_id, now)
            if current.version != expected_version:
                raise BootstrapRepositoryError("bootstrap_stale_revision")
            active = current.identity_handoff
            if (
                active is None
                or active.state is not IdentityHandoffState.RUNNING
                or active.execution_id != execution.execution_id
            ):
                raise BootstrapRepositoryError("bootstrap_phase_execution_unavailable")
            if (
                execution.state is IdentityHandoffState.RUNNING
                or execution.release_id != active.release_id
                or execution.profile is not active.profile
                or execution.configuration_digest != active.configuration_digest
                or execution.trust_plan_digest != active.trust_plan_digest
                or execution.data_plan_digest != active.data_plan_digest
                or execution.service_plan_digest != active.service_plan_digest
                or execution.identity_schema_version != active.identity_schema_version
                or execution.identity_plan_digest != active.identity_plan_digest
                or execution.target_id != active.target_id
                or execution.started_at != active.started_at
            ):
                raise BootstrapRepositoryError("bootstrap_phase_execution_conflict")
            if execution.state is IdentityHandoffState.COMPLETED:
                reference = f"result.identity.{execution.identity_plan_digest[:32]}"
                checkpoint_state = BootstrapCheckpointState.COMPLETED
                run_state = (
                    BootstrapRunState.COMPLETED
                    if len(current.completed_phase_ids) + 1 == len(current.identity.phase_ids)
                    else BootstrapRunState.ACTIVE
                )
            else:
                reference = (
                    "result.identity-handoff."
                    f"{sha256(execution.result_code.encode()).hexdigest()[:24]}"
                )
                checkpoint_state = BootstrapCheckpointState.FAILED
                run_state = BootstrapRunState.FAILED
            checkpoint = BootstrapPhaseCheckpoint(
                phase_id="phase.identity",
                state=checkpoint_state,
                safe_output_references=(reference,),
                recorded_at=now,
            )
            record = replace(
                current,
                version=current.version + 1,
                state=run_state,
                checkpoints=(
                    *(item for item in current.checkpoints if item.phase_id != "phase.identity"),
                    checkpoint,
                ),
                identity_handoff=execution,
                updated_at=now,
            )
            self._apply(row, record)
            result = BootstrapMutationResult(
                record=record, replayed=False, identity_handoff=execution
            )
            self._remember(row, lease_holder_id, idempotency_key, request_fingerprint, result)
            return result

    async def begin_integration_validation(
        self,
        *,
        run_id: str,
        plan_digest: str,
        resume_key: str,
        execution: IntegrationValidationExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult:
        async with self._sessions.begin() as session:
            row = await session.scalar(
                select(BootstrapRunModel)
                .where(BootstrapRunModel.run_id == run_id)
                .with_for_update()
            )
            if row is None:
                raise BootstrapRepositoryError("bootstrap_run_unavailable")
            replay = self._replay(row, lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            current = self._to_domain(row)
            self._require_no_running_phase(current)
            if (
                current.identity.plan_digest != plan_digest
                or current.identity.resume_key != resume_key
            ):
                raise BootstrapRepositoryError("bootstrap_plan_mismatch")
            self._require_lease(current, lease_holder_id, now)
            if current.version != expected_version:
                raise BootstrapRepositoryError("bootstrap_stale_revision")
            if current.state is BootstrapRunState.COMPLETED:
                raise BootstrapRepositoryError("bootstrap_run_completed")
            if (
                current.current_phase_id != "phase.integrations"
                or execution.phase_id != "phase.integrations"
            ):
                raise BootstrapRepositoryError("bootstrap_phase_out_of_order")
            record = replace(
                current,
                version=current.version + 1,
                state=BootstrapRunState.ACTIVE,
                checkpoints=tuple(
                    item for item in current.checkpoints if item.phase_id != "phase.integrations"
                ),
                integration_validation=execution,
                updated_at=now,
            )
            self._apply(row, record)
            result = BootstrapMutationResult(
                record=record,
                replayed=False,
                integration_validation=execution,
            )
            self._remember(row, lease_holder_id, idempotency_key, request_fingerprint, result)
            return result

    async def finish_integration_validation(
        self,
        *,
        run_id: str,
        execution: IntegrationValidationExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult:
        async with self._sessions.begin() as session:
            row = await session.scalar(
                select(BootstrapRunModel)
                .where(BootstrapRunModel.run_id == run_id)
                .with_for_update()
            )
            if row is None:
                raise BootstrapRepositoryError("bootstrap_run_unavailable")
            replay = self._replay(row, lease_holder_id, idempotency_key, request_fingerprint)
            if (
                replay is not None
                and replay.integration_validation is not None
                and replay.integration_validation.state is not IntegrationValidationState.RUNNING
            ):
                return replay
            current = self._to_domain(row)
            self._require_lease(current, lease_holder_id, now)
            if current.version != expected_version:
                raise BootstrapRepositoryError("bootstrap_stale_revision")
            active = current.integration_validation
            if (
                active is None
                or active.state is not IntegrationValidationState.RUNNING
                or active.execution_id != execution.execution_id
            ):
                raise BootstrapRepositoryError("bootstrap_phase_execution_unavailable")
            if (
                execution.state is IntegrationValidationState.RUNNING
                or execution.release_id != active.release_id
                or execution.profile is not active.profile
                or execution.configuration_digest != active.configuration_digest
                or execution.trust_plan_digest != active.trust_plan_digest
                or execution.data_plan_digest != active.data_plan_digest
                or execution.service_plan_digest != active.service_plan_digest
                or execution.identity_plan_digest != active.identity_plan_digest
                or execution.integration_schema_version != active.integration_schema_version
                or execution.integration_plan_digest != active.integration_plan_digest
                or execution.target_id != active.target_id
                or execution.started_at != active.started_at
            ):
                raise BootstrapRepositoryError("bootstrap_phase_execution_conflict")
            if execution.state is IntegrationValidationState.COMPLETED:
                reference = f"result.integrations.{execution.integration_plan_digest[:32]}"
                checkpoint_state = BootstrapCheckpointState.COMPLETED
                run_state = (
                    BootstrapRunState.COMPLETED
                    if len(current.completed_phase_ids) + 1 == len(current.identity.phase_ids)
                    else BootstrapRunState.ACTIVE
                )
            else:
                reference = (
                    "result.integration-validation."
                    f"{sha256(execution.result_code.encode()).hexdigest()[:24]}"
                )
                checkpoint_state = BootstrapCheckpointState.FAILED
                run_state = BootstrapRunState.FAILED
            checkpoint = BootstrapPhaseCheckpoint(
                phase_id="phase.integrations",
                state=checkpoint_state,
                safe_output_references=(reference,),
                recorded_at=now,
            )
            record = replace(
                current,
                version=current.version + 1,
                state=run_state,
                checkpoints=(
                    *(
                        item
                        for item in current.checkpoints
                        if item.phase_id != "phase.integrations"
                    ),
                    checkpoint,
                ),
                integration_validation=execution,
                updated_at=now,
            )
            self._apply(row, record)
            result = BootstrapMutationResult(
                record=record,
                replayed=False,
                integration_validation=execution,
            )
            self._remember(row, lease_holder_id, idempotency_key, request_fingerprint, result)
            return result

    async def rebase(
        self,
        *,
        run_id: str,
        candidate: BootstrapRunIdentity,
        lease_holder_id: str,
        expected_version: int,
        preview_source_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult:
        async with self._sessions.begin() as session:
            row = await session.scalar(
                select(BootstrapRunModel)
                .where(BootstrapRunModel.run_id == run_id)
                .with_for_update()
            )
            if row is None:
                raise BootstrapRepositoryError("bootstrap_run_unavailable")
            replay = self._replay(row, lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            current = self._to_domain(row)
            self._require_no_running_phase(current)
            if (
                candidate.organization_id != current.identity.organization_id
                or candidate.environment_id != current.identity.environment_id
                or candidate.site_id != current.identity.site_id
            ):
                raise BootstrapRepositoryError("bootstrap_run_unavailable")
            self._require_lease(current, lease_holder_id, now)
            if current.version != expected_version or current.version != preview_source_version:
                raise BootstrapRepositoryError("bootstrap_stale_revision")
            if current.state is BootstrapRunState.COMPLETED:
                raise BootstrapRepositoryError("bootstrap_run_completed")
            impact = compare_bootstrap_run(current.identity, candidate, current)
            if impact.earliest_affected_phase_id is None:
                raise BootstrapRepositoryError("bootstrap_plan_unchanged")
            reusable = set(impact.reusable_checkpoint_phase_ids)
            checkpoints = tuple(
                item
                for item in current.checkpoints
                if item.state is BootstrapCheckpointState.COMPLETED and item.phase_id in reusable
            )
            record = replace(
                current,
                version=current.version + 1,
                identity=candidate,
                state=BootstrapRunState.ACTIVE,
                checkpoints=checkpoints,
                artifact_acquisition=(
                    current.artifact_acquisition if "phase.acquire" in reusable else None
                ),
                configuration_rendering=(
                    current.configuration_rendering if "phase.configure" in reusable else None
                ),
                trust_provisioning=(
                    current.trust_provisioning if "phase.trust" in reusable else None
                ),
                data_initialization=(
                    current.data_initialization if "phase.data" in reusable else None
                ),
                service_deployment=(
                    current.service_deployment if "phase.services" in reusable else None
                ),
                identity_handoff=(
                    current.identity_handoff if "phase.identity" in reusable else None
                ),
                integration_validation=(
                    current.integration_validation if "phase.integrations" in reusable else None
                ),
                updated_at=now,
            )
            self._apply(row, record)
            result = BootstrapMutationResult(
                record=record,
                replayed=False,
                preserved_checkpoint_phase_ids=impact.reusable_checkpoint_phase_ids,
                invalidated_checkpoint_phase_ids=impact.invalidated_checkpoint_phase_ids,
                invalidation_reason_codes=tuple(item.reason_code for item in impact.changes),
                earliest_affected_phase_id=impact.earliest_affected_phase_id,
            )
            self._remember(row, lease_holder_id, idempotency_key, request_fingerprint, result)
            return result

    @staticmethod
    def _scope(organization_id: str, environment_id: str, site_id: str) -> str:
        return f"{organization_id}/{environment_id}/{site_id}"

    @staticmethod
    def _require_lease(record: BootstrapRunRecord, lease_holder_id: str, now: datetime) -> None:
        if not record.lease_is_active(now) or record.lease_holder_id != lease_holder_id:
            raise BootstrapRepositoryError("bootstrap_lease_unavailable")

    @staticmethod
    def _require_no_running_phase(record: BootstrapRunRecord) -> None:
        if (
            (
                record.artifact_acquisition is not None
                and record.artifact_acquisition.state is ArtifactAcquisitionState.RUNNING
            )
            or (
                record.configuration_rendering is not None
                and record.configuration_rendering.state is ConfigurationRenderingState.RUNNING
            )
            or (
                record.trust_provisioning is not None
                and record.trust_provisioning.state is TrustProvisioningState.RUNNING
            )
            or (
                record.data_initialization is not None
                and record.data_initialization.state is DataInitializationState.RUNNING
            )
            or (
                record.service_deployment is not None
                and record.service_deployment.state is ServiceDeploymentState.RUNNING
            )
            or (
                record.identity_handoff is not None
                and record.identity_handoff.state is IdentityHandoffState.RUNNING
            )
            or (
                record.integration_validation is not None
                and record.integration_validation.state is IntegrationValidationState.RUNNING
            )
        ):
            raise BootstrapRepositoryError("bootstrap_phase_in_progress")

    @classmethod
    def _new_model(cls, record: BootstrapRunRecord) -> BootstrapRunModel:
        model = BootstrapRunModel()
        model.idempotency_records = {}
        cls._apply(model, record)
        return model

    @classmethod
    def _apply(cls, model: BootstrapRunModel, record: BootstrapRunRecord) -> None:
        model.run_id = record.run_id
        model.version = record.version
        model.organization_id = record.identity.organization_id
        model.environment_id = record.identity.environment_id
        model.site_id = record.identity.site_id
        model.release_id = record.identity.release_id
        model.profile = record.identity.profile.value
        model.plan_digest = record.identity.plan_digest
        model.resume_key = record.identity.resume_key
        model.configuration_digest = record.identity.configuration_digest
        model.phase_ids = list(record.identity.phase_ids)
        model.state = record.state.value
        model.checkpoints = [
            {
                "phase_id": item.phase_id,
                "state": item.state.value,
                "safe_output_references": list(item.safe_output_references),
                "recorded_at": item.recorded_at.isoformat(),
            }
            for item in record.checkpoints
        ]
        model.artifact_acquisition = cls._execution_to_json(record.artifact_acquisition)
        model.configuration_rendering = cls._configuration_execution_to_json(
            record.configuration_rendering
        )
        model.trust_provisioning = cls._trust_execution_to_json(record.trust_provisioning)
        model.data_initialization = cls._data_execution_to_json(record.data_initialization)
        model.service_deployment = cls._service_execution_to_json(record.service_deployment)
        model.identity_handoff = cls._identity_execution_to_json(record.identity_handoff)
        model.integration_validation = cls._integration_execution_to_json(
            record.integration_validation
        )
        model.lease_holder_id = record.lease_holder_id
        model.lease_acquired_at = record.lease_acquired_at
        model.lease_expires_at = record.lease_expires_at
        model.created_at = record.created_at
        model.updated_at = record.updated_at

    @classmethod
    def _to_domain(cls, model: BootstrapRunModel) -> BootstrapRunRecord:
        return BootstrapRunRecord(
            run_id=model.run_id,
            version=model.version,
            identity=BootstrapRunIdentity(
                release_id=model.release_id,
                profile=DeploymentProfile(model.profile),
                organization_id=model.organization_id,
                environment_id=model.environment_id,
                site_id=model.site_id,
                plan_digest=model.plan_digest,
                resume_key=model.resume_key,
                configuration_digest=model.configuration_digest,
                phase_ids=tuple(model.phase_ids),
            ),
            state=BootstrapRunState(model.state),
            checkpoints=tuple(
                BootstrapPhaseCheckpoint(
                    phase_id=item["phase_id"],
                    state=BootstrapCheckpointState(item["state"]),
                    safe_output_references=tuple(item["safe_output_references"]),
                    recorded_at=datetime.fromisoformat(item["recorded_at"]),
                )
                for item in model.checkpoints
            ),
            lease_holder_id=model.lease_holder_id,
            lease_acquired_at=model.lease_acquired_at,
            lease_expires_at=model.lease_expires_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
            artifact_acquisition=cls._execution_from_json(model.artifact_acquisition),
            configuration_rendering=cls._configuration_execution_from_json(
                model.configuration_rendering
            ),
            trust_provisioning=cls._trust_execution_from_json(model.trust_provisioning),
            data_initialization=cls._data_execution_from_json(model.data_initialization),
            service_deployment=cls._service_execution_from_json(model.service_deployment),
            identity_handoff=cls._identity_execution_from_json(model.identity_handoff),
            integration_validation=cls._integration_execution_from_json(
                model.integration_validation
            ),
        )

    @classmethod
    def _replay(
        cls,
        model: BootstrapRunModel | None,
        lease_holder_id: str,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> BootstrapMutationResult | None:
        if model is None:
            return None
        storage_key = cls._idempotency_storage_key(lease_holder_id, idempotency_key)
        prior = model.idempotency_records.get(storage_key)
        if prior is None:
            return None
        if prior["fingerprint"] != request_fingerprint:
            raise BootstrapRepositoryError("bootstrap_idempotency_conflict")
        return BootstrapMutationResult(
            record=cls._record_from_json(prior["record"]),
            replayed=True,
            reclaimed_expired_lease=bool(prior["reclaimed_expired_lease"]),
            preserved_checkpoint_phase_ids=tuple(prior.get("preserved_checkpoint_phase_ids", ())),
            invalidated_checkpoint_phase_ids=tuple(
                prior.get("invalidated_checkpoint_phase_ids", ())
            ),
            invalidation_reason_codes=tuple(prior.get("invalidation_reason_codes", ())),
            earliest_affected_phase_id=prior.get("earliest_affected_phase_id"),
            artifact_acquisition=cls._execution_from_json(prior.get("artifact_acquisition")),
            configuration_rendering=cls._configuration_execution_from_json(
                prior.get("configuration_rendering")
            ),
            trust_provisioning=cls._trust_execution_from_json(prior.get("trust_provisioning")),
            data_initialization=cls._data_execution_from_json(prior.get("data_initialization")),
            service_deployment=cls._service_execution_from_json(prior.get("service_deployment")),
            identity_handoff=cls._identity_execution_from_json(prior.get("identity_handoff")),
            integration_validation=cls._integration_execution_from_json(
                prior.get("integration_validation")
            ),
        )

    @classmethod
    def _remember(
        cls,
        model: BootstrapRunModel,
        lease_holder_id: str,
        idempotency_key: str,
        request_fingerprint: str,
        result: BootstrapMutationResult,
    ) -> None:
        records = dict(model.idempotency_records)
        records[cls._idempotency_storage_key(lease_holder_id, idempotency_key)] = {
            "fingerprint": request_fingerprint,
            "record": cls._record_to_json(result.record),
            "reclaimed_expired_lease": result.reclaimed_expired_lease,
            "preserved_checkpoint_phase_ids": list(result.preserved_checkpoint_phase_ids),
            "invalidated_checkpoint_phase_ids": list(result.invalidated_checkpoint_phase_ids),
            "invalidation_reason_codes": list(result.invalidation_reason_codes),
            "earliest_affected_phase_id": result.earliest_affected_phase_id,
            "artifact_acquisition": cls._execution_to_json(result.artifact_acquisition),
            "configuration_rendering": cls._configuration_execution_to_json(
                result.configuration_rendering
            ),
            "trust_provisioning": cls._trust_execution_to_json(result.trust_provisioning),
            "data_initialization": cls._data_execution_to_json(result.data_initialization),
            "service_deployment": cls._service_execution_to_json(result.service_deployment),
            "identity_handoff": cls._identity_execution_to_json(result.identity_handoff),
            "integration_validation": cls._integration_execution_to_json(
                result.integration_validation
            ),
        }
        while len(records) > 100:
            del records[next(iter(records))]
        model.idempotency_records = records

    @staticmethod
    def _idempotency_storage_key(lease_holder_id: str, idempotency_key: str) -> str:
        return sha256(f"{lease_holder_id}:{idempotency_key}".encode()).hexdigest()

    @classmethod
    def _record_to_json(cls, record: BootstrapRunRecord) -> dict[str, Any]:
        return {
            "run_id": record.run_id,
            "version": record.version,
            "release_id": record.identity.release_id,
            "profile": record.identity.profile.value,
            "organization_id": record.identity.organization_id,
            "environment_id": record.identity.environment_id,
            "site_id": record.identity.site_id,
            "plan_digest": record.identity.plan_digest,
            "resume_key": record.identity.resume_key,
            "configuration_digest": record.identity.configuration_digest,
            "phase_ids": list(record.identity.phase_ids),
            "state": record.state.value,
            "checkpoints": [
                {
                    "phase_id": item.phase_id,
                    "state": item.state.value,
                    "safe_output_references": list(item.safe_output_references),
                    "recorded_at": item.recorded_at.isoformat(),
                }
                for item in record.checkpoints
            ],
            "lease_holder_id": record.lease_holder_id,
            "lease_acquired_at": (
                record.lease_acquired_at.isoformat()
                if record.lease_acquired_at is not None
                else None
            ),
            "lease_expires_at": (
                record.lease_expires_at.isoformat() if record.lease_expires_at is not None else None
            ),
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
            "artifact_acquisition": cls._execution_to_json(record.artifact_acquisition),
            "configuration_rendering": cls._configuration_execution_to_json(
                record.configuration_rendering
            ),
            "trust_provisioning": cls._trust_execution_to_json(record.trust_provisioning),
            "data_initialization": cls._data_execution_to_json(record.data_initialization),
            "service_deployment": cls._service_execution_to_json(record.service_deployment),
            "identity_handoff": cls._identity_execution_to_json(record.identity_handoff),
            "integration_validation": cls._integration_execution_to_json(
                record.integration_validation
            ),
        }

    @classmethod
    def _record_from_json(cls, data: dict[str, Any]) -> BootstrapRunRecord:
        return BootstrapRunRecord(
            run_id=data["run_id"],
            version=data["version"],
            identity=BootstrapRunIdentity(
                release_id=data["release_id"],
                profile=DeploymentProfile(data["profile"]),
                organization_id=data["organization_id"],
                environment_id=data["environment_id"],
                site_id=data["site_id"],
                plan_digest=data["plan_digest"],
                resume_key=data["resume_key"],
                configuration_digest=data["configuration_digest"],
                phase_ids=tuple(data["phase_ids"]),
            ),
            state=BootstrapRunState(data["state"]),
            checkpoints=tuple(
                BootstrapPhaseCheckpoint(
                    phase_id=item["phase_id"],
                    state=BootstrapCheckpointState(item["state"]),
                    safe_output_references=tuple(item["safe_output_references"]),
                    recorded_at=datetime.fromisoformat(item["recorded_at"]),
                )
                for item in data["checkpoints"]
            ),
            lease_holder_id=data["lease_holder_id"],
            lease_acquired_at=(
                datetime.fromisoformat(data["lease_acquired_at"])
                if data["lease_acquired_at"] is not None
                else None
            ),
            lease_expires_at=(
                datetime.fromisoformat(data["lease_expires_at"])
                if data["lease_expires_at"] is not None
                else None
            ),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            artifact_acquisition=cls._execution_from_json(data.get("artifact_acquisition")),
            configuration_rendering=cls._configuration_execution_from_json(
                data.get("configuration_rendering")
            ),
            trust_provisioning=cls._trust_execution_from_json(data.get("trust_provisioning")),
            data_initialization=cls._data_execution_from_json(data.get("data_initialization")),
            service_deployment=cls._service_execution_from_json(data.get("service_deployment")),
            identity_handoff=cls._identity_execution_from_json(data.get("identity_handoff")),
            integration_validation=cls._integration_execution_from_json(
                data.get("integration_validation")
            ),
        )

    @staticmethod
    def _execution_to_json(
        execution: ArtifactAcquisitionExecution | None,
    ) -> dict[str, Any] | None:
        if execution is None:
            return None
        return {
            "execution_id": execution.execution_id,
            "phase_id": execution.phase_id,
            "release_id": execution.release_id,
            "manifest_digest": execution.manifest_digest,
            "mode": execution.mode.value,
            "preflight_report_id": execution.preflight_report_id,
            "state": execution.state.value,
            "result_code": execution.result_code,
            "started_at": execution.started_at.isoformat(),
            "completed_at": (
                execution.completed_at.isoformat() if execution.completed_at is not None else None
            ),
            "evidence": [
                {
                    "artifact_id": item.artifact_id,
                    "sha256": item.sha256,
                    "size_bytes": item.size_bytes,
                    "disposition": item.disposition.value,
                }
                for item in execution.evidence
            ],
            "total_bytes": execution.total_bytes,
        }

    @staticmethod
    def _execution_from_json(data: dict[str, Any] | None) -> ArtifactAcquisitionExecution | None:
        if data is None:
            return None
        return ArtifactAcquisitionExecution(
            execution_id=data["execution_id"],
            phase_id=data["phase_id"],
            release_id=data["release_id"],
            manifest_digest=data["manifest_digest"],
            mode=AcquisitionMode(data["mode"]),
            preflight_report_id=data["preflight_report_id"],
            state=ArtifactAcquisitionState(data["state"]),
            result_code=data["result_code"],
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data["completed_at"] is not None
                else None
            ),
            evidence=tuple(
                VerifiedArtifactEvidence(
                    artifact_id=item["artifact_id"],
                    sha256=item["sha256"],
                    size_bytes=item["size_bytes"],
                    disposition=ArtifactDisposition(item["disposition"]),
                )
                for item in data["evidence"]
            ),
            total_bytes=data["total_bytes"],
        )

    @staticmethod
    def _configuration_execution_to_json(
        execution: ConfigurationRenderingExecution | None,
    ) -> dict[str, Any] | None:
        if execution is None:
            return None
        return {
            "execution_id": execution.execution_id,
            "phase_id": execution.phase_id,
            "release_id": execution.release_id,
            "profile": execution.profile.value,
            "configuration_schema_version": execution.configuration_schema_version,
            "configuration_digest": execution.configuration_digest,
            "state": execution.state.value,
            "result_code": execution.result_code,
            "started_at": execution.started_at.isoformat(),
            "completed_at": (
                execution.completed_at.isoformat() if execution.completed_at is not None else None
            ),
            "evidence": [
                {
                    "file_id": item.file_id,
                    "sha256": item.sha256,
                    "size_bytes": item.size_bytes,
                    "disposition": item.disposition.value,
                }
                for item in execution.evidence
            ],
            "total_bytes": execution.total_bytes,
        }

    @staticmethod
    def _configuration_execution_from_json(
        data: dict[str, Any] | None,
    ) -> ConfigurationRenderingExecution | None:
        if data is None:
            return None
        return ConfigurationRenderingExecution(
            execution_id=data["execution_id"],
            phase_id=data["phase_id"],
            release_id=data["release_id"],
            profile=DeploymentProfile(data["profile"]),
            configuration_schema_version=data["configuration_schema_version"],
            configuration_digest=data["configuration_digest"],
            state=ConfigurationRenderingState(data["state"]),
            result_code=data["result_code"],
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data["completed_at"] is not None
                else None
            ),
            evidence=tuple(
                RenderedConfigurationEvidence(
                    file_id=item["file_id"],
                    sha256=item["sha256"],
                    size_bytes=item["size_bytes"],
                    disposition=ConfigurationFileDisposition(item["disposition"]),
                )
                for item in data["evidence"]
            ),
            total_bytes=data["total_bytes"],
        )

    @staticmethod
    def _trust_execution_to_json(
        execution: TrustProvisioningExecution | None,
    ) -> dict[str, Any] | None:
        if execution is None:
            return None
        return {
            "execution_id": execution.execution_id,
            "phase_id": execution.phase_id,
            "release_id": execution.release_id,
            "profile": execution.profile.value,
            "configuration_digest": execution.configuration_digest,
            "trust_schema_version": execution.trust_schema_version,
            "trust_plan_digest": execution.trust_plan_digest,
            "state": execution.state.value,
            "result_code": execution.result_code,
            "started_at": execution.started_at.isoformat(),
            "completed_at": (
                execution.completed_at.isoformat() if execution.completed_at is not None else None
            ),
            "anchor_count": execution.anchor_count,
            "workload_identity_count": execution.workload_identity_count,
            "evidence": [
                {
                    "file_id": item.file_id,
                    "sha256": item.sha256,
                    "size_bytes": item.size_bytes,
                    "disposition": item.disposition.value,
                }
                for item in execution.evidence
            ],
            "total_bytes": execution.total_bytes,
        }

    @staticmethod
    def _trust_execution_from_json(
        data: dict[str, Any] | None,
    ) -> TrustProvisioningExecution | None:
        if data is None:
            return None
        return TrustProvisioningExecution(
            execution_id=data["execution_id"],
            phase_id=data["phase_id"],
            release_id=data["release_id"],
            profile=DeploymentProfile(data["profile"]),
            configuration_digest=data["configuration_digest"],
            trust_schema_version=data["trust_schema_version"],
            trust_plan_digest=data["trust_plan_digest"],
            state=TrustProvisioningState(data["state"]),
            result_code=data["result_code"],
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data["completed_at"] is not None
                else None
            ),
            anchor_count=data["anchor_count"],
            workload_identity_count=data["workload_identity_count"],
            evidence=tuple(
                TrustFileEvidence(
                    file_id=item["file_id"],
                    sha256=item["sha256"],
                    size_bytes=item["size_bytes"],
                    disposition=TrustFileDisposition(item["disposition"]),
                )
                for item in data["evidence"]
            ),
            total_bytes=data["total_bytes"],
        )

    @staticmethod
    def _data_execution_to_json(
        execution: DataInitializationExecution | None,
    ) -> dict[str, Any] | None:
        if execution is None:
            return None
        return {
            "execution_id": execution.execution_id,
            "phase_id": execution.phase_id,
            "release_id": execution.release_id,
            "profile": execution.profile.value,
            "configuration_digest": execution.configuration_digest,
            "trust_plan_digest": execution.trust_plan_digest,
            "data_schema_version": execution.data_schema_version,
            "data_plan_digest": execution.data_plan_digest,
            "migration_artifact_digest": execution.migration_artifact_digest,
            "target_id": execution.target_id,
            "from_revision": execution.from_revision,
            "to_revision": execution.to_revision,
            "state": execution.state.value,
            "result_code": execution.result_code,
            "started_at": execution.started_at.isoformat(),
            "completed_at": (
                execution.completed_at.isoformat() if execution.completed_at is not None else None
            ),
            "migration_count": execution.migration_count,
            "verified_object_count": execution.verified_object_count,
            "lock_acquired": execution.lock_acquired,
            "backup_applicability": execution.backup_applicability.value,
            "evidence": [
                {
                    "evidence_id": item.evidence_id,
                    "sha256": item.sha256,
                    "size_bytes": item.size_bytes,
                    "disposition": item.disposition.value,
                }
                for item in execution.evidence
            ],
        }

    @staticmethod
    def _data_execution_from_json(
        data: dict[str, Any] | None,
    ) -> DataInitializationExecution | None:
        if data is None:
            return None
        return DataInitializationExecution(
            execution_id=data["execution_id"],
            phase_id=data["phase_id"],
            release_id=data["release_id"],
            profile=DeploymentProfile(data["profile"]),
            configuration_digest=data["configuration_digest"],
            trust_plan_digest=data["trust_plan_digest"],
            data_schema_version=data["data_schema_version"],
            data_plan_digest=data["data_plan_digest"],
            migration_artifact_digest=data["migration_artifact_digest"],
            target_id=data["target_id"],
            from_revision=data["from_revision"],
            to_revision=data["to_revision"],
            state=DataInitializationState(data["state"]),
            result_code=data["result_code"],
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data["completed_at"] is not None
                else None
            ),
            migration_count=data["migration_count"],
            verified_object_count=data["verified_object_count"],
            lock_acquired=data["lock_acquired"],
            backup_applicability=BackupApplicability(data["backup_applicability"]),
            evidence=tuple(
                DataStateEvidence(
                    evidence_id=item["evidence_id"],
                    sha256=item["sha256"],
                    size_bytes=item["size_bytes"],
                    disposition=DataStateDisposition(item["disposition"]),
                )
                for item in data["evidence"]
            ),
        )

    @staticmethod
    def _service_execution_to_json(
        execution: ServiceDeploymentExecution | None,
    ) -> dict[str, Any] | None:
        if execution is None:
            return None
        return {
            "execution_id": execution.execution_id,
            "phase_id": execution.phase_id,
            "release_id": execution.release_id,
            "profile": execution.profile.value,
            "configuration_digest": execution.configuration_digest,
            "trust_plan_digest": execution.trust_plan_digest,
            "data_plan_digest": execution.data_plan_digest,
            "migration_artifact_digest": execution.migration_artifact_digest,
            "service_schema_version": execution.service_schema_version,
            "service_plan_digest": execution.service_plan_digest,
            "target_id": execution.target_id,
            "state": execution.state.value,
            "result_code": execution.result_code,
            "started_at": execution.started_at.isoformat(),
            "completed_at": (
                execution.completed_at.isoformat() if execution.completed_at is not None else None
            ),
            "deployed_service_count": execution.deployed_service_count,
            "ready_service_count": execution.ready_service_count,
            "passed_probe_count": execution.passed_probe_count,
            "service_statuses": [
                {
                    "service_id": item.service_id,
                    "state": item.state.value,
                    "startup_passed": item.startup_passed,
                    "readiness_passed": item.readiness_passed,
                    "liveness_passed": item.liveness_passed,
                }
                for item in execution.service_statuses
            ],
            "evidence": [
                {
                    "evidence_id": item.evidence_id,
                    "sha256": item.sha256,
                    "size_bytes": item.size_bytes,
                    "disposition": item.disposition.value,
                }
                for item in execution.evidence
            ],
        }

    @staticmethod
    def _service_execution_from_json(
        data: dict[str, Any] | None,
    ) -> ServiceDeploymentExecution | None:
        if data is None:
            return None
        return ServiceDeploymentExecution(
            execution_id=data["execution_id"],
            phase_id=data["phase_id"],
            release_id=data["release_id"],
            profile=DeploymentProfile(data["profile"]),
            configuration_digest=data["configuration_digest"],
            trust_plan_digest=data["trust_plan_digest"],
            data_plan_digest=data["data_plan_digest"],
            migration_artifact_digest=data["migration_artifact_digest"],
            service_schema_version=data["service_schema_version"],
            service_plan_digest=data["service_plan_digest"],
            target_id=data["target_id"],
            state=ServiceDeploymentState(data["state"]),
            result_code=data["result_code"],
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data["completed_at"] is not None
                else None
            ),
            deployed_service_count=data["deployed_service_count"],
            ready_service_count=data["ready_service_count"],
            passed_probe_count=data["passed_probe_count"],
            service_statuses=tuple(
                ServiceStatusEvidence(
                    service_id=item["service_id"],
                    state=ServiceRuntimeState(item["state"]),
                    startup_passed=item["startup_passed"],
                    readiness_passed=item["readiness_passed"],
                    liveness_passed=item["liveness_passed"],
                )
                for item in data["service_statuses"]
            ),
            evidence=tuple(
                ServiceStateEvidence(
                    evidence_id=item["evidence_id"],
                    sha256=item["sha256"],
                    size_bytes=item["size_bytes"],
                    disposition=ServiceStateDisposition(item["disposition"]),
                )
                for item in data["evidence"]
            ),
        )

    @staticmethod
    def _identity_execution_to_json(
        execution: IdentityHandoffExecution | None,
    ) -> dict[str, Any] | None:
        if execution is None:
            return None
        return {
            "execution_id": execution.execution_id,
            "phase_id": execution.phase_id,
            "release_id": execution.release_id,
            "profile": execution.profile.value,
            "configuration_digest": execution.configuration_digest,
            "trust_plan_digest": execution.trust_plan_digest,
            "data_plan_digest": execution.data_plan_digest,
            "service_plan_digest": execution.service_plan_digest,
            "identity_schema_version": execution.identity_schema_version,
            "identity_plan_digest": execution.identity_plan_digest,
            "target_id": execution.target_id,
            "state": execution.state.value,
            "result_code": execution.result_code,
            "started_at": execution.started_at.isoformat(),
            "completed_at": (
                execution.completed_at.isoformat() if execution.completed_at is not None else None
            ),
            "group_mapping_count": execution.group_mapping_count,
            "validation_count": execution.validation_count,
            "credential_replacement_required": execution.credential_replacement_required,
            "recovery_identity_verified": execution.recovery_identity_verified,
            "bootstrap_material_sealed": execution.bootstrap_material_sealed,
            "pilot_identity_verified": execution.pilot_identity_verified,
            "enterprise_authentication_validated": execution.enterprise_authentication_validated,
            "evidence": [
                {
                    "evidence_id": item.evidence_id,
                    "sha256": item.sha256,
                    "size_bytes": item.size_bytes,
                    "disposition": item.disposition.value,
                }
                for item in execution.evidence
            ],
        }

    @staticmethod
    def _identity_execution_from_json(
        data: dict[str, Any] | None,
    ) -> IdentityHandoffExecution | None:
        if data is None:
            return None
        return IdentityHandoffExecution(
            execution_id=data["execution_id"],
            phase_id=data["phase_id"],
            release_id=data["release_id"],
            profile=DeploymentProfile(data["profile"]),
            configuration_digest=data["configuration_digest"],
            trust_plan_digest=data["trust_plan_digest"],
            data_plan_digest=data["data_plan_digest"],
            service_plan_digest=data["service_plan_digest"],
            identity_schema_version=data["identity_schema_version"],
            identity_plan_digest=data["identity_plan_digest"],
            target_id=data["target_id"],
            state=IdentityHandoffState(data["state"]),
            result_code=data["result_code"],
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data["completed_at"] is not None
                else None
            ),
            group_mapping_count=data["group_mapping_count"],
            validation_count=data["validation_count"],
            credential_replacement_required=data["credential_replacement_required"],
            recovery_identity_verified=data["recovery_identity_verified"],
            bootstrap_material_sealed=data["bootstrap_material_sealed"],
            pilot_identity_verified=data["pilot_identity_verified"],
            enterprise_authentication_validated=data["enterprise_authentication_validated"],
            evidence=tuple(
                IdentityStateEvidence(
                    evidence_id=item["evidence_id"],
                    sha256=item["sha256"],
                    size_bytes=item["size_bytes"],
                    disposition=IdentityStateDisposition(item["disposition"]),
                )
                for item in data["evidence"]
            ),
        )

    @staticmethod
    def _integration_execution_to_json(
        execution: IntegrationValidationExecution | None,
    ) -> dict[str, Any] | None:
        if execution is None:
            return None
        return {
            "execution_id": execution.execution_id,
            "phase_id": execution.phase_id,
            "release_id": execution.release_id,
            "profile": execution.profile.value,
            "configuration_digest": execution.configuration_digest,
            "trust_plan_digest": execution.trust_plan_digest,
            "data_plan_digest": execution.data_plan_digest,
            "service_plan_digest": execution.service_plan_digest,
            "identity_plan_digest": execution.identity_plan_digest,
            "integration_schema_version": execution.integration_schema_version,
            "integration_plan_digest": execution.integration_plan_digest,
            "target_id": execution.target_id,
            "state": execution.state.value,
            "result_code": execution.result_code,
            "started_at": execution.started_at.isoformat(),
            "completed_at": (
                execution.completed_at.isoformat() if execution.completed_at is not None else None
            ),
            "model_check_count": execution.model_check_count,
            "integration_check_count": execution.integration_check_count,
            "mandatory_pass_count": execution.mandatory_pass_count,
            "activation_count": execution.activation_count,
            "network_request_count": execution.network_request_count,
            "secret_resolution_count": execution.secret_resolution_count,
            "checks": [
                {
                    "check_id": item.check_id,
                    "subject_id": item.subject_id,
                    "state": item.state.value,
                    "result_code": item.result_code,
                    "mandatory": item.mandatory,
                }
                for item in execution.checks
            ],
            "evidence": [
                {
                    "evidence_id": item.evidence_id,
                    "sha256": item.sha256,
                    "size_bytes": item.size_bytes,
                    "disposition": item.disposition.value,
                }
                for item in execution.evidence
            ],
        }

    @staticmethod
    def _integration_execution_from_json(
        data: dict[str, Any] | None,
    ) -> IntegrationValidationExecution | None:
        if data is None:
            return None
        return IntegrationValidationExecution(
            execution_id=data["execution_id"],
            phase_id=data["phase_id"],
            release_id=data["release_id"],
            profile=DeploymentProfile(data["profile"]),
            configuration_digest=data["configuration_digest"],
            trust_plan_digest=data["trust_plan_digest"],
            data_plan_digest=data["data_plan_digest"],
            service_plan_digest=data["service_plan_digest"],
            identity_plan_digest=data["identity_plan_digest"],
            integration_schema_version=data["integration_schema_version"],
            integration_plan_digest=data["integration_plan_digest"],
            target_id=data["target_id"],
            state=IntegrationValidationState(data["state"]),
            result_code=data["result_code"],
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data["completed_at"] is not None
                else None
            ),
            model_check_count=data["model_check_count"],
            integration_check_count=data["integration_check_count"],
            mandatory_pass_count=data["mandatory_pass_count"],
            activation_count=data["activation_count"],
            network_request_count=data["network_request_count"],
            secret_resolution_count=data["secret_resolution_count"],
            checks=tuple(
                IntegrationValidationCheck(
                    check_id=item["check_id"],
                    subject_id=item["subject_id"],
                    state=IntegrationCheckState(item["state"]),
                    result_code=item["result_code"],
                    mandatory=item["mandatory"],
                )
                for item in data["checks"]
            ),
            evidence=tuple(
                IntegrationStateEvidence(
                    evidence_id=item["evidence_id"],
                    sha256=item["sha256"],
                    size_bytes=item["size_bytes"],
                    disposition=IntegrationStateDisposition(item["disposition"]),
                )
                for item in data["evidence"]
            ),
        )
