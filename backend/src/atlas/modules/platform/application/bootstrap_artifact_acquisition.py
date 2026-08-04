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
from atlas.modules.platform.application.bootstrap_artifact_ports import (
    ArtifactAcquisitionError,
    ReleaseArtifactPublisher,
)
from atlas.modules.platform.application.bootstrap_state_ports import BootstrapStateRepository
from atlas.modules.platform.application.release_preflight import (
    ReleasePreflightService,
    canonical_manifest_payload,
)
from atlas.modules.platform.domain.bootstrap_artifact_acquisition import (
    ArtifactAcquisitionExecution,
    ArtifactAcquisitionState,
)
from atlas.modules.platform.domain.bootstrap_state import BootstrapMutationResult
from atlas.modules.platform.domain.release_preflight import (
    AcquisitionMode,
    DeploymentProfile,
    PreflightState,
)


class BootstrapArtifactExecutionError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class BootstrapArtifactAcquisitionService:
    def __init__(
        self,
        *,
        repository: BootstrapStateRepository,
        preflight_service: ReleasePreflightService,
        publisher: ReleaseArtifactPublisher,
        audit_sink: AuditSink,
        environment_id: str,
        site_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._preflight_service = preflight_service
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
        manifest_digest: str,
        mode: AcquisitionMode,
        profile: DeploymentProfile,
        preflight_report_id: str,
        preflight_state: PreflightState,
        warning_accepted: bool,
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
            raise BootstrapArtifactExecutionError("bootstrap_run_unavailable")
        if (
            organization_id != actor.organization_id
            or environment_id != self._environment_id
            or site_id != self._site_id
            or current.identity.organization_id != organization_id
            or current.identity.environment_id != environment_id
            or current.identity.site_id != site_id
        ):
            await self._audit_denial(actor, correlation_id)
            raise BootstrapArtifactExecutionError("bootstrap_run_unavailable")
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
                "manifest_digest": manifest_digest,
                "mode": mode.value,
                "profile": profile.value,
                "preflight_report_id": preflight_report_id,
                "preflight_state": preflight_state.value,
                "warning_accepted": warning_accepted,
                "justification": justification,
            }
        )
        execution_id = self._execution_id(run_id, lease_holder_id, idempotency_key, fingerprint)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            result_code="bootstrap_artifact_execution_authorized",
            run_id=run_id,
            idempotency_key=idempotency_key,
            metadata=(
                ("execution_id", execution_id),
                ("manifest_digest", manifest_digest),
                ("mode", mode.value),
                ("justification_digest", self._fingerprint({"justification": justification})),
            ),
        )
        prior = current.artifact_acquisition
        if prior is not None and prior.execution_id == execution_id:
            if prior.state is not ArtifactAcquisitionState.RUNNING:
                return BootstrapMutationResult(
                    record=current,
                    replayed=True,
                    artifact_acquisition=prior,
                )
            running = prior
            begin = BootstrapMutationResult(
                record=current,
                replayed=True,
                artifact_acquisition=running,
            )
        else:
            self._validate_run_identity(
                current=current,
                release_id=release_id,
                profile=profile,
                plan_digest=plan_digest,
                resume_key=resume_key,
            )
            manifest = self._preflight_service.manifest
            authoritative_digest = sha256(canonical_manifest_payload(manifest)).hexdigest()
            if release_id != manifest.release_id or manifest_digest != authoritative_digest:
                raise BootstrapArtifactExecutionError("bootstrap_artifact_manifest_mismatch")
            report = await self._preflight_service.run(
                actor=actor,
                mode=mode,
                profile=profile,
                correlation_id=correlation_id,
            )
            if report.manifest_digest != manifest_digest or report.state is not preflight_state:
                raise BootstrapArtifactExecutionError("bootstrap_preflight_stale")
            if report.state is PreflightState.FAILED:
                raise BootstrapArtifactExecutionError("bootstrap_preflight_failed")
            if report.state is PreflightState.WARNING and not warning_accepted:
                raise BootstrapArtifactExecutionError("bootstrap_preflight_warning_unaccepted")
            if prior is not None and prior.state is ArtifactAcquisitionState.FAILED:
                await self._publisher.cleanup_attempt(prior.execution_id)
            started_at = self._clock()
            running = ArtifactAcquisitionExecution(
                execution_id=execution_id,
                phase_id="phase.acquire",
                release_id=release_id,
                manifest_digest=manifest_digest,
                mode=mode,
                preflight_report_id=preflight_report_id,
                state=ArtifactAcquisitionState.RUNNING,
                result_code="bootstrap.artifact.running",
                started_at=started_at,
                completed_at=None,
                evidence=(),
                total_bytes=0,
            )
            begin = await self._repository.begin_artifact_acquisition(
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
            assert begin.artifact_acquisition is not None
            running = begin.artifact_acquisition
            if running.state is not ArtifactAcquisitionState.RUNNING:
                return begin

        try:
            receipt = await self._publisher.acquire(
                manifest=self._preflight_service.manifest,
                manifest_digest=manifest_digest,
                mode=mode,
                execution_id=running.execution_id,
            )
            finished = replace(
                running,
                state=ArtifactAcquisitionState.COMPLETED,
                result_code="bootstrap.artifact.completed",
                completed_at=self._clock(),
                evidence=receipt.evidence,
                total_bytes=receipt.total_bytes,
            )
        except ArtifactAcquisitionError as error:
            finished = replace(
                running,
                state=ArtifactAcquisitionState.FAILED,
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
                ("artifact_count", str(len(finished.evidence))),
                ("total_bytes", str(finished.total_bytes)),
            ),
        )
        return await self._repository.finish_artifact_acquisition(
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
        current: object,
        release_id: str,
        profile: DeploymentProfile,
        plan_digest: str,
        resume_key: str,
    ) -> None:
        from atlas.modules.platform.domain.bootstrap_state import BootstrapRunRecord

        if not isinstance(current, BootstrapRunRecord):
            raise BootstrapArtifactExecutionError("bootstrap_run_unavailable")
        if (
            current.identity.release_id != release_id
            or current.identity.profile is not profile
            or current.identity.plan_digest != plan_digest
            or current.identity.resume_key != resume_key
        ):
            raise BootstrapArtifactExecutionError("bootstrap_plan_mismatch")

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
                event_type="atlas.platform.bootstrap-artifact.execute",
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
                event_type="atlas.platform.bootstrap-artifact.denied",
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
