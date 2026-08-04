from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.platform.application.bootstrap_data_initialization import (
    BootstrapDataPlanService,
)
from atlas.modules.platform.application.bootstrap_service_ports import (
    BootstrapServiceCatalog,
    BootstrapServiceError,
    BootstrapServiceTarget,
)
from atlas.modules.platform.application.bootstrap_state_ports import BootstrapStateRepository
from atlas.modules.platform.domain.bootstrap_artifact_acquisition import ArtifactAcquisitionState
from atlas.modules.platform.domain.bootstrap_data_initialization import DataInitializationState
from atlas.modules.platform.domain.bootstrap_service_deployment import (
    BootstrapServicePlan,
    BootstrapServiceSpec,
    ServiceDeploymentExecution,
    ServiceDeploymentState,
    ServicePlanState,
    ServiceTargetState,
)
from atlas.modules.platform.domain.bootstrap_state import (
    BootstrapMutationResult,
    BootstrapRunRecord,
)
from atlas.modules.platform.domain.deployment_configuration import DeploymentConfigurationOverlay
from atlas.modules.platform.domain.release_preflight import DeploymentProfile


class BootstrapServicePlanService:
    def __init__(
        self,
        *,
        catalog: BootstrapServiceCatalog,
        target: BootstrapServiceTarget,
        data_plan_service: BootstrapDataPlanService,
        environment_id: str,
        site_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._catalog = catalog
        self._target = target
        self._data_plan_service = data_plan_service
        self._environment_id = environment_id
        self._site_id = site_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def prepare(
        self,
        *,
        actor: AuthenticatedSubject,
        release_id: str,
        profile: DeploymentProfile,
        organization_id: str,
        environment_id: str,
        site_id: str,
        configuration_digest: str,
        overlay: DeploymentConfigurationOverlay,
        trust_plan_digest: str,
        data_plan_digest: str,
        migration_artifact_digest: str,
    ) -> BootstrapServicePlan:
        if (
            organization_id != actor.organization_id
            or environment_id != self._environment_id
            or site_id != self._site_id
        ):
            raise BootstrapServiceError("bootstrap_service_plan_unavailable")
        try:
            data_plan = await self._data_plan_service.prepare(
                actor=actor,
                release_id=release_id,
                profile=profile,
                organization_id=organization_id,
                environment_id=environment_id,
                site_id=site_id,
                configuration_digest=configuration_digest,
                overlay=overlay,
                trust_plan_digest=trust_plan_digest,
            )
            if (
                data_plan.data_plan_digest != data_plan_digest
                or data_plan.migration_artifact_digest != migration_artifact_digest
            ):
                raise BootstrapServiceError("bootstrap_data_plan_digest_mismatch")
            target_id, target_kind, services = self._catalog.load(
                profile=profile, environment_id=environment_id
            )
            self._validate_catalog(services)
        except BootstrapServiceError:
            raise
        except ValueError as error:
            raise BootstrapServiceError("bootstrap_service_plan_invalid") from error
        payload = self._plan_payload(
            release_id=release_id,
            profile=profile,
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
            configuration_digest=configuration_digest,
            trust_plan_digest=trust_plan_digest,
            data_plan_digest=data_plan_digest,
            migration_artifact_digest=migration_artifact_digest,
            target_id=target_id,
            target_kind=target_kind,
            services=services,
        )
        plan = BootstrapServicePlan(
            schema_version="atlas.bootstrap-service-plan.v1",
            release_id=release_id,
            profile=profile,
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
            configuration_digest=configuration_digest,
            trust_plan_digest=trust_plan_digest,
            data_plan_digest=data_plan_digest,
            migration_artifact_digest=migration_artifact_digest,
            service_plan_digest=sha256(self._canonical_json(payload)).hexdigest(),
            target_id=target_id,
            target_kind=target_kind,
            target_state=ServiceTargetState.EMPTY,
            state=ServicePlanState.PASSED,
            result_code="bootstrap.service-plan.passed",
            services=services,
            generated_at=self._clock(),
        )
        return replace(plan, target_state=await self._target.inspect(plan=plan))

    @classmethod
    def render(cls, plan: BootstrapServicePlan) -> bytes:
        return cls._canonical_json(
            {
                "schema_version": "atlas.synthetic-service-state.v1",
                "owner_id": "owner.project-atlas",
                "release_id": plan.release_id,
                "profile": plan.profile.value,
                "organization_id": plan.organization_id,
                "environment_id": plan.environment_id,
                "site_id": plan.site_id,
                "configuration_digest": plan.configuration_digest,
                "trust_plan_digest": plan.trust_plan_digest,
                "data_plan_digest": plan.data_plan_digest,
                "migration_artifact_digest": plan.migration_artifact_digest,
                "service_plan_digest": plan.service_plan_digest,
                "target_id": plan.target_id,
                "target_kind": plan.target_kind,
                "services": [
                    {
                        **cls._service_payload(item),
                        "runtime_state": "ready",
                        "startup_passed": True,
                        "readiness_passed": True,
                        "liveness_passed": True,
                    }
                    for item in plan.services
                ],
                "real_runtime_mutation_performed": False,
            }
        )

    @staticmethod
    def _validate_catalog(services: tuple[BootstrapServiceSpec, ...]) -> None:
        if not 1 <= len(services) <= 32:
            raise ValueError("service catalog is outside platform bounds")
        seen: set[str] = set()
        artifact_ids: set[str] = set()
        for sequence, service in enumerate(services, start=1):
            if (
                service.sequence != sequence
                or service.service_id in seen
                or service.artifact_id in artifact_ids
                or any(dependency not in seen for dependency in service.dependencies)
            ):
                raise ValueError("service catalog order or identity is unsafe")
            seen.add(service.service_id)
            artifact_ids.add(service.artifact_id)

    @classmethod
    def _plan_payload(
        cls,
        *,
        release_id: str,
        profile: DeploymentProfile,
        organization_id: str,
        environment_id: str,
        site_id: str,
        configuration_digest: str,
        trust_plan_digest: str,
        data_plan_digest: str,
        migration_artifact_digest: str,
        target_id: str,
        target_kind: str,
        services: tuple[BootstrapServiceSpec, ...],
    ) -> dict[str, object]:
        return {
            "schema_version": "atlas.bootstrap-service-plan.v1",
            "release_id": release_id,
            "profile": profile.value,
            "organization_id": organization_id,
            "environment_id": environment_id,
            "site_id": site_id,
            "configuration_digest": configuration_digest,
            "trust_plan_digest": trust_plan_digest,
            "data_plan_digest": data_plan_digest,
            "migration_artifact_digest": migration_artifact_digest,
            "target_id": target_id,
            "target_kind": target_kind,
            "services": [cls._service_payload(item) for item in services],
            "real_runtime_mutation_authorized": False,
        }

    @staticmethod
    def _service_payload(item: BootstrapServiceSpec) -> dict[str, object]:
        return {
            "service_id": item.service_id,
            "sequence": item.sequence,
            "artifact_id": item.artifact_id,
            "artifact_sha256": item.artifact_sha256,
            "dependencies": item.dependencies,
            "workload_identity_id": item.workload_identity_id,
            "endpoint_class": item.endpoint_class.value,
            "cpu_limit_millicores": item.cpu_limit_millicores,
            "memory_limit_mb": item.memory_limit_mb,
            "startup_probe_id": item.startup_probe_id,
            "readiness_probe_id": item.readiness_probe_id,
            "liveness_probe_id": item.liveness_probe_id,
            "run_as_root": item.run_as_root,
            "privileged": item.privileged,
            "arbitrary_public_egress": item.arbitrary_public_egress,
        }

    @staticmethod
    def _canonical_json(payload: Mapping[str, object]) -> bytes:
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


class BootstrapServiceDeploymentService:
    def __init__(
        self,
        *,
        repository: BootstrapStateRepository,
        plan_service: BootstrapServicePlanService,
        target: BootstrapServiceTarget,
        audit_sink: AuditSink,
        environment_id: str,
        site_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._plan_service = plan_service
        self._target = target
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
        configuration_digest: str,
        overlay: DeploymentConfigurationOverlay,
        trust_plan_digest: str,
        data_plan_digest: str,
        migration_artifact_digest: str,
        service_schema_version: str,
        service_plan_digest: str,
        target_id: str,
        expected_target_state: ServiceTargetState,
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
            raise BootstrapServiceError("bootstrap_run_unavailable")
        if (
            organization_id != actor.organization_id
            or environment_id != self._environment_id
            or site_id != self._site_id
            or current.identity.organization_id != organization_id
            or current.identity.environment_id != environment_id
            or current.identity.site_id != site_id
        ):
            await self._audit_denial(actor, correlation_id)
            raise BootstrapServiceError("bootstrap_run_unavailable")
        fingerprint = self._fingerprint(
            {
                "run_id": run_id,
                "expected_version": expected_version,
                "plan_digest": plan_digest,
                "resume_key": resume_key,
                "release_id": release_id,
                "profile": profile.value,
                "configuration_digest": configuration_digest,
                "overlay": self._overlay_payload(overlay),
                "trust_plan_digest": trust_plan_digest,
                "data_plan_digest": data_plan_digest,
                "migration_artifact_digest": migration_artifact_digest,
                "service_schema_version": service_schema_version,
                "service_plan_digest": service_plan_digest,
                "target_id": target_id,
                "expected_target_state": expected_target_state.value,
                "justification": justification,
            }
        )
        execution_id = self._execution_id(run_id, lease_holder_id, idempotency_key, fingerprint)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            result_code="bootstrap_service_execution_authorized",
            run_id=run_id,
            idempotency_key=idempotency_key,
            metadata=(("execution_id", execution_id), ("service_plan_digest", service_plan_digest)),
        )
        prior = current.service_deployment
        if prior is not None and prior.execution_id == execution_id:
            if prior.state is not ServiceDeploymentState.RUNNING:
                return BootstrapMutationResult(
                    record=current, replayed=True, service_deployment=prior
                )
            running = prior
            begin = BootstrapMutationResult(
                record=current, replayed=True, service_deployment=running
            )
        else:
            self._validate_run_identity(
                current=current,
                release_id=release_id,
                profile=profile,
                plan_digest=plan_digest,
                resume_key=resume_key,
                configuration_digest=configuration_digest,
                trust_plan_digest=trust_plan_digest,
                data_plan_digest=data_plan_digest,
                migration_artifact_digest=migration_artifact_digest,
            )
            service_plan = await self._plan_service.prepare(
                actor=actor,
                release_id=release_id,
                profile=profile,
                organization_id=organization_id,
                environment_id=environment_id,
                site_id=site_id,
                configuration_digest=configuration_digest,
                overlay=overlay,
                trust_plan_digest=trust_plan_digest,
                data_plan_digest=data_plan_digest,
                migration_artifact_digest=migration_artifact_digest,
            )
            self._validate_artifacts(current, service_plan)
            if service_schema_version != service_plan.schema_version:
                raise BootstrapServiceError("bootstrap_service_schema_mismatch")
            if (
                service_plan_digest != service_plan.service_plan_digest
                or target_id != service_plan.target_id
                or expected_target_state is not service_plan.target_state
            ):
                raise BootstrapServiceError("bootstrap_service_plan_digest_mismatch")
            if prior is not None and prior.state is ServiceDeploymentState.FAILED:
                await self._target.cleanup_attempt(prior.execution_id)
            started_at = self._clock()
            running = ServiceDeploymentExecution(
                execution_id=execution_id,
                phase_id="phase.services",
                release_id=release_id,
                profile=profile,
                configuration_digest=configuration_digest,
                trust_plan_digest=trust_plan_digest,
                data_plan_digest=data_plan_digest,
                migration_artifact_digest=migration_artifact_digest,
                service_schema_version=service_schema_version,
                service_plan_digest=service_plan_digest,
                target_id=target_id,
                state=ServiceDeploymentState.RUNNING,
                result_code="bootstrap.services.running",
                started_at=started_at,
                completed_at=None,
                deployed_service_count=0,
                ready_service_count=0,
                passed_probe_count=0,
                service_statuses=(),
                evidence=(),
            )
            begin = await self._repository.begin_service_deployment(
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
            assert begin.service_deployment is not None
            running = begin.service_deployment
            if running.state is not ServiceDeploymentState.RUNNING:
                return begin

        service_plan = await self._plan_service.prepare(
            actor=actor,
            release_id=release_id,
            profile=profile,
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
            configuration_digest=configuration_digest,
            overlay=overlay,
            trust_plan_digest=trust_plan_digest,
            data_plan_digest=data_plan_digest,
            migration_artifact_digest=migration_artifact_digest,
        )
        try:
            receipt = await self._target.deploy(
                execution_id=running.execution_id,
                plan=service_plan,
                state_document=self._plan_service.render(service_plan),
            )
            service_count = len(receipt.service_statuses)
            finished = replace(
                running,
                state=ServiceDeploymentState.COMPLETED,
                result_code="bootstrap.services.completed",
                completed_at=self._clock(),
                deployed_service_count=service_count,
                ready_service_count=service_count,
                passed_probe_count=service_count * 3,
                service_statuses=receipt.service_statuses,
                evidence=receipt.evidence,
            )
        except BootstrapServiceError as error:
            finished = replace(
                running,
                state=ServiceDeploymentState.FAILED,
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
                ("ready_service_count", str(finished.ready_service_count)),
                ("passed_probe_count", str(finished.passed_probe_count)),
            ),
        )
        return await self._repository.finish_service_deployment(
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
        trust_plan_digest: str,
        data_plan_digest: str,
        migration_artifact_digest: str,
    ) -> None:
        if (
            current.identity.release_id != release_id
            or current.identity.profile is not profile
            or current.identity.plan_digest != plan_digest
            or current.identity.resume_key != resume_key
            or current.identity.configuration_digest != configuration_digest
        ):
            raise BootstrapServiceError("bootstrap_plan_mismatch")
        data = current.data_initialization
        if (
            data is None
            or data.state is not DataInitializationState.COMPLETED
            or data.trust_plan_digest != trust_plan_digest
            or data.data_plan_digest != data_plan_digest
            or data.migration_artifact_digest != migration_artifact_digest
            or "phase.data" not in current.completed_phase_ids
        ):
            raise BootstrapServiceError("bootstrap_data_evidence_missing")

    @staticmethod
    def _validate_artifacts(current: BootstrapRunRecord, plan: BootstrapServicePlan) -> None:
        acquisition = current.artifact_acquisition
        if acquisition is None or acquisition.state is not ArtifactAcquisitionState.COMPLETED:
            raise BootstrapServiceError("bootstrap_artifact_evidence_missing")
        evidence = {item.artifact_id: item.sha256 for item in acquisition.evidence}
        if any(evidence.get(item.artifact_id) != item.artifact_sha256 for item in plan.services):
            raise BootstrapServiceError("bootstrap_service_artifact_mismatch")

    @staticmethod
    def _overlay_payload(overlay: DeploymentConfigurationOverlay) -> dict[str, object]:
        return {
            "api_bind": overlay.api_bind,
            "public_url": overlay.public_url,
            "cors_origins": overlay.cors_origins,
            "component_references": None
            if overlay.component_references is None
            else tuple((item.name, item.value) for item in overlay.component_references),
            "feature_flags": None
            if overlay.feature_flags is None
            else tuple((item.name, item.value) for item in overlay.feature_flags),
            "integration_endpoints": None
            if overlay.integration_endpoints is None
            else tuple((item.name, item.value) for item in overlay.integration_endpoints),
            "resource_names": overlay.resource_names,
            "secret_references": None
            if overlay.secret_references is None
            else tuple((item.name, item.value) for item in overlay.secret_references),
        }

    @staticmethod
    def _fingerprint(payload: dict[str, object]) -> str:
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

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
                event_type="atlas.platform.bootstrap-services.execute",
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
                event_type="atlas.platform.bootstrap-services.denied",
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
