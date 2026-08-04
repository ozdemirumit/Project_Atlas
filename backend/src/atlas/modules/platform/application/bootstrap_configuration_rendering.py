from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.platform.application.bootstrap_configuration_ports import (
    ConfigurationRenderingError,
    EffectiveConfigurationPublisher,
)
from atlas.modules.platform.application.bootstrap_state_ports import BootstrapStateRepository
from atlas.modules.platform.application.deployment_configuration import (
    DeploymentConfigurationService,
)
from atlas.modules.platform.domain.bootstrap_artifact_acquisition import ArtifactAcquisitionState
from atlas.modules.platform.domain.bootstrap_configuration_rendering import (
    ConfigurationRenderingExecution,
    ConfigurationRenderingState,
)
from atlas.modules.platform.domain.bootstrap_state import (
    BootstrapMutationResult,
    BootstrapRunRecord,
)
from atlas.modules.platform.domain.deployment_configuration import (
    ConfigurationState,
    DeploymentConfigurationOverlay,
    DeploymentConfigurationRequest,
)
from atlas.modules.platform.domain.release_preflight import DeploymentProfile


class BootstrapConfigurationExecutionError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class BootstrapConfigurationRenderingService:
    def __init__(
        self,
        *,
        repository: BootstrapStateRepository,
        configuration_service: DeploymentConfigurationService,
        publisher: EffectiveConfigurationPublisher,
        audit_sink: AuditSink,
        environment_id: str,
        site_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._configuration_service = configuration_service
        self._publisher = publisher
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._site_id = site_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def execute(
        self,
        *,
        actor: AuthenticatedSubject,
        lease_holder_id: str,
        run_id: str,
        organization_id: str,
        environment_id: str,
        site_id: str,
        expected_version: int,
        plan_digest: str,
        resume_key: str,
        release_id: str,
        profile: DeploymentProfile,
        configuration_schema_version: str,
        configuration_digest: str,
        overlay: DeploymentConfigurationOverlay,
        justification: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> BootstrapMutationResult:
        current = await self._repository.get_current(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
        )
        if current is None or current.run_id != run_id:
            await self._audit_denial(actor, correlation_id)
            raise BootstrapConfigurationExecutionError("bootstrap_run_unavailable")
        if (
            organization_id != actor.organization_id
            or environment_id != self._environment_id
            or site_id != self._site_id
            or current.identity.organization_id != organization_id
            or current.identity.environment_id != environment_id
            or current.identity.site_id != site_id
        ):
            await self._audit_denial(actor, correlation_id)
            raise BootstrapConfigurationExecutionError("bootstrap_run_unavailable")
        fingerprint = self._fingerprint(
            {
                "run_id": run_id,
                "organization_id": organization_id,
                "environment_id": environment_id,
                "site_id": site_id,
                "expected_version": expected_version,
                "plan_digest": plan_digest,
                "resume_key": resume_key,
                "release_id": release_id,
                "profile": profile.value,
                "configuration_schema_version": configuration_schema_version,
                "configuration_digest": configuration_digest,
                "overlay": self._overlay_payload(overlay),
                "justification": justification,
            }
        )
        execution_id = self._execution_id(run_id, lease_holder_id, idempotency_key, fingerprint)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            result_code="bootstrap_configuration_execution_authorized",
            run_id=run_id,
            idempotency_key=idempotency_key,
            metadata=(
                ("execution_id", execution_id),
                ("configuration_digest", configuration_digest),
                ("profile", profile.value),
                ("justification_digest", self._fingerprint({"justification": justification})),
            ),
        )
        prior = current.configuration_rendering
        if prior is not None and prior.execution_id == execution_id:
            if prior.state is not ConfigurationRenderingState.RUNNING:
                return BootstrapMutationResult(
                    record=current,
                    replayed=True,
                    configuration_rendering=prior,
                )
            running = prior
            begin = BootstrapMutationResult(
                record=current,
                replayed=True,
                configuration_rendering=running,
            )
        else:
            self._validate_run_identity(
                current=current,
                release_id=release_id,
                profile=profile,
                plan_digest=plan_digest,
                resume_key=resume_key,
                configuration_digest=configuration_digest,
            )
            if configuration_schema_version != "atlas.deployment-configuration.v1":
                raise BootstrapConfigurationExecutionError(
                    "bootstrap_configuration_schema_mismatch"
                )
            request = DeploymentConfigurationRequest(
                schema_version="atlas.deployment-configuration-request.v1",
                release_id=release_id,
                profile=profile,
                organization_id=organization_id,
                environment_id=environment_id,
                site_id=site_id,
                overlay=overlay,
            )
            prepared = self._configuration_service.prepare(request)
            if prepared.state is ConfigurationState.FAILED:
                raise BootstrapConfigurationExecutionError(
                    "bootstrap_configuration_validation_failed"
                )
            if prepared.configuration_digest != configuration_digest:
                raise BootstrapConfigurationExecutionError(
                    "bootstrap_configuration_digest_mismatch"
                )
            if prior is not None and prior.state is ConfigurationRenderingState.FAILED:
                await self._publisher.cleanup_attempt(prior.execution_id)
            started_at = self._clock()
            running = ConfigurationRenderingExecution(
                execution_id=execution_id,
                phase_id="phase.configure",
                release_id=release_id,
                profile=profile,
                configuration_schema_version=configuration_schema_version,
                configuration_digest=configuration_digest,
                state=ConfigurationRenderingState.RUNNING,
                result_code="bootstrap.configuration.running",
                started_at=started_at,
                completed_at=None,
                evidence=(),
                total_bytes=0,
            )
            begin = await self._repository.begin_configuration_rendering(
                run_id=run_id,
                plan_digest=plan_digest,
                resume_key=resume_key,
                execution=running,
                lease_holder_id=lease_holder_id,
                expected_version=expected_version,
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
                now=started_at,
            )
            assert begin.configuration_rendering is not None
            running = begin.configuration_rendering
            if running.state is not ConfigurationRenderingState.RUNNING:
                return begin

        request = DeploymentConfigurationRequest(
            schema_version="atlas.deployment-configuration-request.v1",
            release_id=release_id,
            profile=profile,
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
            overlay=overlay,
        )
        prepared = self._configuration_service.prepare(request)
        try:
            receipt = await self._publisher.publish(
                execution_id=running.execution_id,
                organization_id=organization_id,
                environment_id=environment_id,
                site_id=site_id,
                release_id=release_id,
                configuration_digest=configuration_digest,
                content=prepared.rendered_content,
            )
            finished = replace(
                running,
                state=ConfigurationRenderingState.COMPLETED,
                result_code="bootstrap.configuration.completed",
                completed_at=self._clock(),
                evidence=receipt.evidence,
                total_bytes=receipt.total_bytes,
            )
        except ConfigurationRenderingError as error:
            finished = replace(
                running,
                state=ConfigurationRenderingState.FAILED,
                result_code=error.code,
                completed_at=self._clock(),
            )
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            result_code=finished.result_code,
            run_id=run_id,
            idempotency_key=idempotency_key,
            metadata=(
                ("execution_id", finished.execution_id),
                ("file_count", str(len(finished.evidence))),
                ("total_bytes", str(finished.total_bytes)),
            ),
        )
        return await self._repository.finish_configuration_rendering(
            run_id=run_id,
            execution=finished,
            lease_holder_id=lease_holder_id,
            expected_version=begin.record.version,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            now=finished.completed_at or self._clock(),
        )

    @staticmethod
    def _validate_run_identity(
        *,
        current: BootstrapRunRecord,
        release_id: str,
        profile: DeploymentProfile,
        plan_digest: str,
        resume_key: str,
        configuration_digest: str,
    ) -> None:
        if (
            current.identity.release_id != release_id
            or current.identity.profile is not profile
            or current.identity.plan_digest != plan_digest
            or current.identity.resume_key != resume_key
            or current.identity.configuration_digest != configuration_digest
        ):
            raise BootstrapConfigurationExecutionError("bootstrap_plan_mismatch")
        if (
            current.artifact_acquisition is None
            or current.artifact_acquisition.state is not ArtifactAcquisitionState.COMPLETED
            or "phase.acquire" not in current.completed_phase_ids
        ):
            raise BootstrapConfigurationExecutionError("bootstrap_artifact_evidence_missing")

    @staticmethod
    def _overlay_payload(overlay: DeploymentConfigurationOverlay) -> dict[str, object]:
        return {
            "api_bind": overlay.api_bind,
            "public_url": overlay.public_url,
            "cors_origins": overlay.cors_origins,
            "component_references": (
                None
                if overlay.component_references is None
                else tuple((item.name, item.value) for item in overlay.component_references)
            ),
            "feature_flags": (
                None
                if overlay.feature_flags is None
                else tuple((item.name, item.value) for item in overlay.feature_flags)
            ),
            "integration_endpoints": (
                None
                if overlay.integration_endpoints is None
                else tuple((item.name, item.value) for item in overlay.integration_endpoints)
            ),
            "resource_names": overlay.resource_names,
            "secret_references": (
                None
                if overlay.secret_references is None
                else tuple((item.name, item.value) for item in overlay.secret_references)
            ),
        }

    @staticmethod
    def _fingerprint(payload: dict[str, object]) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return sha256(encoded).hexdigest()

    @staticmethod
    def _execution_id(
        run_id: str, lease_holder_id: str, idempotency_key: str, fingerprint: str
    ) -> str:
        digest = sha256(
            f"{run_id}:{lease_holder_id}:{idempotency_key}:{fingerprint}".encode()
        ).hexdigest()[:24]
        return f"phase-execution.{digest}"

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        run_id: str,
        idempotency_key: str,
        metadata: tuple[tuple[str, str], ...],
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.platform.bootstrap-configuration.execute",
                schema_version="1.0",
                producer="atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id="platform.bootstrap-state.manage",
                resource_type="resource.platform.bootstrap-state",
                scope_reference=(
                    f"{actor.organization_id}/{self._environment_id}/{self._site_id}/"
                    "domain.platform/resource.platform.bootstrap-state/C2"
                ),
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=(("run_id", run_id), *metadata),
            )
        )

    async def _audit_denial(self, actor: AuthenticatedSubject, correlation_id: str) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.platform.bootstrap-configuration.denied",
                schema_version="1.0",
                producer="atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id="platform.bootstrap-state.manage",
                resource_type="resource.platform.bootstrap-state",
                scope_reference="scope.redacted",
                decision_id=None,
                outcome="denied",
                result_code="bootstrap_run_unavailable",
                target_metadata=(),
            )
        )
