from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta
from hashlib import sha256

from atlas.modules.platform.application.bootstrap_state_ports import BootstrapRepositoryError
from atlas.modules.platform.domain.bootstrap_artifact_acquisition import (
    ArtifactAcquisitionExecution,
    ArtifactAcquisitionState,
)
from atlas.modules.platform.domain.bootstrap_configuration_rendering import (
    ConfigurationRenderingExecution,
    ConfigurationRenderingState,
)
from atlas.modules.platform.domain.bootstrap_data_initialization import (
    DataInitializationExecution,
    DataInitializationState,
)
from atlas.modules.platform.domain.bootstrap_end_to_end_verification import (
    EndToEndVerificationExecution,
    VerificationExecutionState,
)
from atlas.modules.platform.domain.bootstrap_identity_handoff import (
    IdentityHandoffExecution,
    IdentityHandoffState,
)
from atlas.modules.platform.domain.bootstrap_integration_validation import (
    IntegrationValidationExecution,
    IntegrationValidationState,
)
from atlas.modules.platform.domain.bootstrap_invalidation import compare_bootstrap_run
from atlas.modules.platform.domain.bootstrap_operational_handoff import (
    HandoffExecutionState,
    OperationalHandoffExecution,
)
from atlas.modules.platform.domain.bootstrap_service_deployment import (
    ServiceDeploymentExecution,
    ServiceDeploymentState,
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
    TrustProvisioningExecution,
    TrustProvisioningState,
)


class InMemoryBootstrapStateRepository:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str], BootstrapRunRecord] = {}
        self._idempotency: dict[tuple[str, str], tuple[str, BootstrapMutationResult]] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def close(self) -> None:
        return None

    async def get_current(
        self, *, organization_id: str, environment_id: str, site_id: str
    ) -> BootstrapRunRecord | None:
        async with self._lock:
            return self._records.get((organization_id, environment_id, site_id))

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
        async with self._lock:
            replay = self._replay(lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            key = (identity.organization_id, identity.environment_id, identity.site_id)
            current = self._records.get(key)
            reclaimed = False
            if current is None:
                run_digest = sha256(
                    "/".join((*key, identity.resume_key)).encode("utf-8")
                ).hexdigest()[:24]
                updated = BootstrapRunRecord(
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
            else:
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
                if (
                    reclaimed
                    and current.end_to_end_verification is not None
                    and current.end_to_end_verification.state is VerificationExecutionState.RUNNING
                ):
                    interrupted_verification = replace(
                        current.end_to_end_verification,
                        state=VerificationExecutionState.FAILED,
                        result_code="bootstrap.verification.interrupted",
                        completed_at=now,
                    )
                    failed_verification_checkpoint = BootstrapPhaseCheckpoint(
                        phase_id="phase.verify",
                        state=BootstrapCheckpointState.FAILED,
                        safe_output_references=(
                            "result.end-to-end-verification."
                            f"{sha256(interrupted_verification.execution_id.encode()).hexdigest()[:24]}",
                        ),
                        recorded_at=now,
                    )
                    current = replace(
                        current,
                        checkpoints=(
                            *(
                                item
                                for item in current.checkpoints
                                if item.phase_id != "phase.verify"
                            ),
                            failed_verification_checkpoint,
                        ),
                        end_to_end_verification=interrupted_verification,
                    )
                if (
                    reclaimed
                    and current.operational_handoff is not None
                    and current.operational_handoff.state is HandoffExecutionState.RUNNING
                ):
                    interrupted_handoff = replace(
                        current.operational_handoff,
                        state=HandoffExecutionState.FAILED,
                        result_code="bootstrap.handoff.interrupted",
                        completed_at=now,
                    )
                    failed_handoff_checkpoint = BootstrapPhaseCheckpoint(
                        phase_id="phase.handoff",
                        state=BootstrapCheckpointState.FAILED,
                        safe_output_references=(
                            "result.operational-handoff."
                            f"{sha256(interrupted_handoff.execution_id.encode()).hexdigest()[:24]}",
                        ),
                        recorded_at=now,
                    )
                    current = replace(
                        current,
                        checkpoints=(
                            *(
                                item
                                for item in current.checkpoints
                                if item.phase_id != "phase.handoff"
                            ),
                            failed_handoff_checkpoint,
                        ),
                        operational_handoff=interrupted_handoff,
                    )
                updated = replace(
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
            result = BootstrapMutationResult(
                record=updated, replayed=False, reclaimed_expired_lease=reclaimed
            )
            self._records[key] = updated
            self._remember(lease_holder_id, idempotency_key, request_fingerprint, result)
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
        async with self._lock:
            replay = self._replay(lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            key, current = self._find(run_id)
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
            updated = replace(
                current,
                version=current.version + 1,
                state=run_state,
                checkpoints=checkpoints,
                updated_at=now,
            )
            result = BootstrapMutationResult(record=updated, replayed=False)
            self._records[key] = updated
            self._remember(lease_holder_id, idempotency_key, request_fingerprint, result)
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
        async with self._lock:
            replay = self._replay(lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            key, current = self._find(run_id)
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
            updated = replace(
                current,
                version=current.version + 1,
                state=BootstrapRunState.ACTIVE,
                checkpoints=tuple(
                    item for item in current.checkpoints if item.phase_id != "phase.acquire"
                ),
                artifact_acquisition=execution,
                updated_at=now,
            )
            result = BootstrapMutationResult(
                record=updated,
                replayed=False,
                artifact_acquisition=execution,
            )
            self._records[key] = updated
            self._remember(lease_holder_id, idempotency_key, request_fingerprint, result)
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
        async with self._lock:
            replay = self._replay(lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            key, current = self._find(run_id)
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
            updated = replace(
                current,
                version=current.version + 1,
                state=BootstrapRunState.ACTIVE,
                checkpoints=tuple(
                    item for item in current.checkpoints if item.phase_id != "phase.configure"
                ),
                configuration_rendering=execution,
                updated_at=now,
            )
            result = BootstrapMutationResult(
                record=updated,
                replayed=False,
                configuration_rendering=execution,
            )
            self._records[key] = updated
            self._remember(lease_holder_id, idempotency_key, request_fingerprint, result)
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
        async with self._lock:
            replay = self._replay(lease_holder_id, idempotency_key, request_fingerprint)
            if (
                replay is not None
                and replay.configuration_rendering is not None
                and replay.configuration_rendering.state is not ConfigurationRenderingState.RUNNING
            ):
                return replay
            key, current = self._find(run_id)
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
            updated = replace(
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
            result = BootstrapMutationResult(
                record=updated,
                replayed=False,
                configuration_rendering=execution,
            )
            self._records[key] = updated
            self._remember(lease_holder_id, idempotency_key, request_fingerprint, result)
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
        async with self._lock:
            replay = self._replay(lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            key, current = self._find(run_id)
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
            updated = replace(
                current,
                version=current.version + 1,
                state=BootstrapRunState.ACTIVE,
                checkpoints=tuple(
                    item for item in current.checkpoints if item.phase_id != "phase.trust"
                ),
                trust_provisioning=execution,
                updated_at=now,
            )
            result = BootstrapMutationResult(
                record=updated,
                replayed=False,
                trust_provisioning=execution,
            )
            self._records[key] = updated
            self._remember(lease_holder_id, idempotency_key, request_fingerprint, result)
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
        async with self._lock:
            replay = self._replay(lease_holder_id, idempotency_key, request_fingerprint)
            if (
                replay is not None
                and replay.trust_provisioning is not None
                and replay.trust_provisioning.state is not TrustProvisioningState.RUNNING
            ):
                return replay
            key, current = self._find(run_id)
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
            updated = replace(
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
            result = BootstrapMutationResult(
                record=updated,
                replayed=False,
                trust_provisioning=execution,
            )
            self._records[key] = updated
            self._remember(lease_holder_id, idempotency_key, request_fingerprint, result)
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
        async with self._lock:
            replay = self._replay(lease_holder_id, idempotency_key, request_fingerprint)
            if (
                replay is not None
                and replay.artifact_acquisition is not None
                and replay.artifact_acquisition.state is not ArtifactAcquisitionState.RUNNING
            ):
                return replay
            key, current = self._find(run_id)
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
            updated = replace(
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
            result = BootstrapMutationResult(
                record=updated,
                replayed=False,
                artifact_acquisition=execution,
            )
            self._records[key] = updated
            self._remember(lease_holder_id, idempotency_key, request_fingerprint, result)
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
        async with self._lock:
            replay = self._replay(lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            key, current = self._find(run_id)
            self._require_no_running_phase(current)
            self._require_lease(current, lease_holder_id, now)
            if current.version != expected_version:
                raise BootstrapRepositoryError("bootstrap_stale_revision")
            updated = replace(
                current,
                version=current.version + 1,
                lease_holder_id=None,
                lease_acquired_at=None,
                lease_expires_at=None,
                updated_at=now,
            )
            result = BootstrapMutationResult(record=updated, replayed=False)
            self._records[key] = updated
            self._remember(lease_holder_id, idempotency_key, request_fingerprint, result)
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
        async with self._lock:
            replay = self._replay(lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            key, current = self._find(run_id)
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
            updated = replace(
                current,
                version=current.version + 1,
                state=BootstrapRunState.ACTIVE,
                checkpoints=tuple(
                    item for item in current.checkpoints if item.phase_id != "phase.data"
                ),
                data_initialization=execution,
                updated_at=now,
            )
            result = BootstrapMutationResult(
                record=updated, replayed=False, data_initialization=execution
            )
            self._records[key] = updated
            self._remember(lease_holder_id, idempotency_key, request_fingerprint, result)
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
        async with self._lock:
            replay = self._replay(lease_holder_id, idempotency_key, request_fingerprint)
            if (
                replay is not None
                and replay.data_initialization is not None
                and replay.data_initialization.state is not DataInitializationState.RUNNING
            ):
                return replay
            key, current = self._find(run_id)
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
            updated = replace(
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
            result = BootstrapMutationResult(
                record=updated, replayed=False, data_initialization=execution
            )
            self._records[key] = updated
            self._remember(lease_holder_id, idempotency_key, request_fingerprint, result)
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
        async with self._lock:
            replay = self._replay(lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            key, current = self._find(run_id)
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
            updated = replace(
                current,
                version=current.version + 1,
                state=BootstrapRunState.ACTIVE,
                checkpoints=tuple(
                    item for item in current.checkpoints if item.phase_id != "phase.services"
                ),
                service_deployment=execution,
                updated_at=now,
            )
            result = BootstrapMutationResult(
                record=updated, replayed=False, service_deployment=execution
            )
            self._records[key] = updated
            self._remember(lease_holder_id, idempotency_key, request_fingerprint, result)
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
        async with self._lock:
            replay = self._replay(lease_holder_id, idempotency_key, request_fingerprint)
            if (
                replay is not None
                and replay.service_deployment is not None
                and replay.service_deployment.state is not ServiceDeploymentState.RUNNING
            ):
                return replay
            key, current = self._find(run_id)
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
            updated = replace(
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
            result = BootstrapMutationResult(
                record=updated, replayed=False, service_deployment=execution
            )
            self._records[key] = updated
            self._remember(lease_holder_id, idempotency_key, request_fingerprint, result)
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
        async with self._lock:
            replay = self._replay(lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            key, current = self._find(run_id)
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
            updated = replace(
                current,
                version=current.version + 1,
                state=BootstrapRunState.ACTIVE,
                checkpoints=tuple(
                    item for item in current.checkpoints if item.phase_id != "phase.identity"
                ),
                identity_handoff=execution,
                updated_at=now,
            )
            result = BootstrapMutationResult(
                record=updated, replayed=False, identity_handoff=execution
            )
            self._records[key] = updated
            self._remember(lease_holder_id, idempotency_key, request_fingerprint, result)
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
        async with self._lock:
            replay = self._replay(lease_holder_id, idempotency_key, request_fingerprint)
            if (
                replay is not None
                and replay.identity_handoff is not None
                and replay.identity_handoff.state is not IdentityHandoffState.RUNNING
            ):
                return replay
            key, current = self._find(run_id)
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
            updated = replace(
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
            result = BootstrapMutationResult(
                record=updated, replayed=False, identity_handoff=execution
            )
            self._records[key] = updated
            self._remember(lease_holder_id, idempotency_key, request_fingerprint, result)
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
        async with self._lock:
            replay = self._replay(lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            key, current = self._find(run_id)
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
            updated = replace(
                current,
                version=current.version + 1,
                state=BootstrapRunState.ACTIVE,
                checkpoints=tuple(
                    item for item in current.checkpoints if item.phase_id != "phase.integrations"
                ),
                integration_validation=execution,
                updated_at=now,
            )
            result = BootstrapMutationResult(
                record=updated,
                replayed=False,
                integration_validation=execution,
            )
            self._records[key] = updated
            self._remember(lease_holder_id, idempotency_key, request_fingerprint, result)
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
        async with self._lock:
            replay = self._replay(lease_holder_id, idempotency_key, request_fingerprint)
            if (
                replay is not None
                and replay.integration_validation is not None
                and replay.integration_validation.state is not IntegrationValidationState.RUNNING
            ):
                return replay
            key, current = self._find(run_id)
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
            updated = replace(
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
            result = BootstrapMutationResult(
                record=updated,
                replayed=False,
                integration_validation=execution,
            )
            self._records[key] = updated
            self._remember(lease_holder_id, idempotency_key, request_fingerprint, result)
            return result

    async def begin_end_to_end_verification(
        self,
        *,
        run_id: str,
        plan_digest: str,
        resume_key: str,
        execution: EndToEndVerificationExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult:
        async with self._lock:
            replay = self._replay(lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            key, current = self._find(run_id)
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
            if current.current_phase_id != "phase.verify" or execution.phase_id != "phase.verify":
                raise BootstrapRepositoryError("bootstrap_phase_out_of_order")
            updated = replace(
                current,
                version=current.version + 1,
                state=BootstrapRunState.ACTIVE,
                checkpoints=tuple(
                    item for item in current.checkpoints if item.phase_id != "phase.verify"
                ),
                end_to_end_verification=execution,
                updated_at=now,
            )
            result = BootstrapMutationResult(
                record=updated, replayed=False, end_to_end_verification=execution
            )
            self._records[key] = updated
            self._remember(lease_holder_id, idempotency_key, request_fingerprint, result)
            return result

    async def finish_end_to_end_verification(
        self,
        *,
        run_id: str,
        execution: EndToEndVerificationExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult:
        async with self._lock:
            replay = self._replay(lease_holder_id, idempotency_key, request_fingerprint)
            if (
                replay is not None
                and replay.end_to_end_verification is not None
                and replay.end_to_end_verification.state is not VerificationExecutionState.RUNNING
            ):
                return replay
            key, current = self._find(run_id)
            self._require_lease(current, lease_holder_id, now)
            if current.version != expected_version:
                raise BootstrapRepositoryError("bootstrap_stale_revision")
            active = current.end_to_end_verification
            if (
                active is None
                or active.state is not VerificationExecutionState.RUNNING
                or active.execution_id != execution.execution_id
            ):
                raise BootstrapRepositoryError("bootstrap_phase_execution_unavailable")
            if (
                execution.state is VerificationExecutionState.RUNNING
                or execution.release_id != active.release_id
                or execution.profile is not active.profile
                or execution.configuration_digest != active.configuration_digest
                or execution.trust_plan_digest != active.trust_plan_digest
                or execution.data_plan_digest != active.data_plan_digest
                or execution.service_plan_digest != active.service_plan_digest
                or execution.identity_plan_digest != active.identity_plan_digest
                or execution.integration_plan_digest != active.integration_plan_digest
                or execution.verification_schema_version != active.verification_schema_version
                or execution.suite_version != active.suite_version
                or execution.verification_plan_digest != active.verification_plan_digest
                or execution.target_id != active.target_id
                or execution.started_at != active.started_at
            ):
                raise BootstrapRepositoryError("bootstrap_phase_execution_conflict")
            if execution.state is VerificationExecutionState.COMPLETED:
                reference = f"result.verification.{execution.verification_plan_digest[:32]}"
                checkpoint_state = BootstrapCheckpointState.COMPLETED
                run_state = (
                    BootstrapRunState.COMPLETED
                    if len(current.completed_phase_ids) + 1 == len(current.identity.phase_ids)
                    else BootstrapRunState.ACTIVE
                )
            else:
                reference = (
                    "result.end-to-end-verification."
                    f"{sha256(execution.result_code.encode()).hexdigest()[:24]}"
                )
                checkpoint_state = BootstrapCheckpointState.FAILED
                run_state = BootstrapRunState.FAILED
            checkpoint = BootstrapPhaseCheckpoint(
                phase_id="phase.verify",
                state=checkpoint_state,
                safe_output_references=(reference,),
                recorded_at=now,
            )
            updated = replace(
                current,
                version=current.version + 1,
                state=run_state,
                checkpoints=(
                    *(item for item in current.checkpoints if item.phase_id != "phase.verify"),
                    checkpoint,
                ),
                end_to_end_verification=execution,
                updated_at=now,
            )
            result = BootstrapMutationResult(
                record=updated, replayed=False, end_to_end_verification=execution
            )
            self._records[key] = updated
            self._remember(lease_holder_id, idempotency_key, request_fingerprint, result)
            return result

    async def begin_operational_handoff(
        self,
        *,
        run_id: str,
        plan_digest: str,
        resume_key: str,
        execution: OperationalHandoffExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult:
        async with self._lock:
            replay = self._replay(lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            key, current = self._find(run_id)
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
            if current.current_phase_id != "phase.handoff" or execution.phase_id != "phase.handoff":
                raise BootstrapRepositoryError("bootstrap_phase_out_of_order")
            updated = replace(
                current,
                version=current.version + 1,
                state=BootstrapRunState.ACTIVE,
                checkpoints=tuple(
                    item for item in current.checkpoints if item.phase_id != "phase.handoff"
                ),
                operational_handoff=execution,
                updated_at=now,
            )
            result = BootstrapMutationResult(
                record=updated, replayed=False, operational_handoff=execution
            )
            self._records[key] = updated
            self._remember(lease_holder_id, idempotency_key, request_fingerprint, result)
            return result

    async def finish_operational_handoff(
        self,
        *,
        run_id: str,
        execution: OperationalHandoffExecution,
        lease_holder_id: str,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BootstrapMutationResult:
        async with self._lock:
            replay = self._replay(lease_holder_id, idempotency_key, request_fingerprint)
            if (
                replay is not None
                and replay.operational_handoff is not None
                and replay.operational_handoff.state is not HandoffExecutionState.RUNNING
            ):
                return replay
            key, current = self._find(run_id)
            self._require_lease(current, lease_holder_id, now)
            if current.version != expected_version:
                raise BootstrapRepositoryError("bootstrap_stale_revision")
            active = current.operational_handoff
            if (
                active is None
                or active.state is not HandoffExecutionState.RUNNING
                or active.execution_id != execution.execution_id
            ):
                raise BootstrapRepositoryError("bootstrap_phase_execution_unavailable")
            if (
                execution.state is HandoffExecutionState.RUNNING
                or execution.release_id != active.release_id
                or execution.profile is not active.profile
                or execution.configuration_digest != active.configuration_digest
                or execution.trust_plan_digest != active.trust_plan_digest
                or execution.data_plan_digest != active.data_plan_digest
                or execution.service_plan_digest != active.service_plan_digest
                or execution.identity_plan_digest != active.identity_plan_digest
                or execution.integration_plan_digest != active.integration_plan_digest
                or execution.verification_plan_digest != active.verification_plan_digest
                or execution.verification_report_digest != active.verification_report_digest
                or execution.source_evidence_digest != active.source_evidence_digest
                or execution.handoff_schema_version != active.handoff_schema_version
                or execution.suite_version != active.suite_version
                or execution.handoff_plan_digest != active.handoff_plan_digest
                or execution.target_id != active.target_id
                or execution.readiness_class is not active.readiness_class
                or execution.readiness_claims != active.readiness_claims
                or execution.started_at != active.started_at
            ):
                raise BootstrapRepositoryError("bootstrap_phase_execution_conflict")
            if execution.state is HandoffExecutionState.COMPLETED:
                reference = f"result.handoff.{execution.handoff_plan_digest[:32]}"
                checkpoint_state = BootstrapCheckpointState.COMPLETED
                run_state = (
                    BootstrapRunState.COMPLETED
                    if len(current.completed_phase_ids) + 1 == len(current.identity.phase_ids)
                    else BootstrapRunState.ACTIVE
                )
            else:
                reference = (
                    "result.operational-handoff."
                    f"{sha256(execution.result_code.encode()).hexdigest()[:24]}"
                )
                checkpoint_state = BootstrapCheckpointState.FAILED
                run_state = BootstrapRunState.FAILED
            checkpoint = BootstrapPhaseCheckpoint(
                phase_id="phase.handoff",
                state=checkpoint_state,
                safe_output_references=(reference,),
                recorded_at=now,
            )
            updated = replace(
                current,
                version=current.version + 1,
                state=run_state,
                checkpoints=(
                    *(item for item in current.checkpoints if item.phase_id != "phase.handoff"),
                    checkpoint,
                ),
                operational_handoff=execution,
                updated_at=now,
            )
            result = BootstrapMutationResult(
                record=updated, replayed=False, operational_handoff=execution
            )
            self._records[key] = updated
            self._remember(lease_holder_id, idempotency_key, request_fingerprint, result)
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
        async with self._lock:
            replay = self._replay(lease_holder_id, idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            key, current = self._find(run_id)
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
            updated = replace(
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
                end_to_end_verification=(
                    current.end_to_end_verification if "phase.verify" in reusable else None
                ),
                operational_handoff=(
                    current.operational_handoff if "phase.handoff" in reusable else None
                ),
                updated_at=now,
            )
            result = BootstrapMutationResult(
                record=updated,
                replayed=False,
                preserved_checkpoint_phase_ids=impact.reusable_checkpoint_phase_ids,
                invalidated_checkpoint_phase_ids=impact.invalidated_checkpoint_phase_ids,
                invalidation_reason_codes=tuple(item.reason_code for item in impact.changes),
                earliest_affected_phase_id=impact.earliest_affected_phase_id,
            )
            self._records[key] = updated
            self._remember(lease_holder_id, idempotency_key, request_fingerprint, result)
            return result

    def _find(self, run_id: str) -> tuple[tuple[str, str, str], BootstrapRunRecord]:
        found = next(
            ((key, record) for key, record in self._records.items() if record.run_id == run_id),
            None,
        )
        if found is None:
            raise BootstrapRepositoryError("bootstrap_run_unavailable")
        return found

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
            or (
                record.end_to_end_verification is not None
                and record.end_to_end_verification.state is VerificationExecutionState.RUNNING
            )
            or (
                record.operational_handoff is not None
                and record.operational_handoff.state is HandoffExecutionState.RUNNING
            )
        ):
            raise BootstrapRepositoryError("bootstrap_phase_in_progress")

    def _replay(
        self, lease_holder_id: str, idempotency_key: str, request_fingerprint: str
    ) -> BootstrapMutationResult | None:
        prior = self._idempotency.get((lease_holder_id, idempotency_key))
        if prior is None:
            return None
        fingerprint, result = prior
        if fingerprint != request_fingerprint:
            raise BootstrapRepositoryError("bootstrap_idempotency_conflict")
        return replace(result, replayed=True)

    def _remember(
        self,
        lease_holder_id: str,
        idempotency_key: str,
        request_fingerprint: str,
        result: BootstrapMutationResult,
    ) -> None:
        self._idempotency[(lease_holder_id, idempotency_key)] = (
            request_fingerprint,
            result,
        )
