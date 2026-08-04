from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from typing import cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.platform.application.bootstrap_identity_handoff import (
    BootstrapIdentityPlanService,
)
from atlas.modules.platform.application.bootstrap_integration_ports import (
    BootstrapIntegrationCatalog,
    BootstrapIntegrationError,
    BootstrapIntegrationTarget,
)
from atlas.modules.platform.application.bootstrap_state_ports import BootstrapStateRepository
from atlas.modules.platform.domain.bootstrap_identity_handoff import IdentityHandoffState
from atlas.modules.platform.domain.bootstrap_integration_validation import (
    BootstrapIntegrationPlan,
    CoreIntegrationRegistration,
    IntegrationCheckState,
    IntegrationPlanState,
    IntegrationTargetState,
    IntegrationValidationCheck,
    IntegrationValidationExecution,
    IntegrationValidationState,
    ModelEndpointRegistration,
)
from atlas.modules.platform.domain.bootstrap_state import (
    BootstrapMutationResult,
    BootstrapRunRecord,
)
from atlas.modules.platform.domain.deployment_configuration import DeploymentConfigurationOverlay
from atlas.modules.platform.domain.release_preflight import DeploymentProfile


class BootstrapIntegrationPlanService:
    def __init__(
        self,
        *,
        catalog: BootstrapIntegrationCatalog,
        target: BootstrapIntegrationTarget,
        identity_plan_service: BootstrapIdentityPlanService,
        environment_id: str,
        site_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._catalog = catalog
        self._target = target
        self._identity_plan_service = identity_plan_service
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
        service_plan_digest: str,
        identity_plan_digest: str,
    ) -> BootstrapIntegrationPlan:
        if (
            organization_id != actor.organization_id
            or environment_id != self._environment_id
            or site_id != self._site_id
        ):
            raise BootstrapIntegrationError("bootstrap_integration_plan_unavailable")
        try:
            identity_plan = await self._identity_plan_service.prepare(
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
                service_plan_digest=service_plan_digest,
            )
            if identity_plan.identity_plan_digest != identity_plan_digest:
                raise BootstrapIntegrationError("bootstrap_identity_plan_digest_mismatch")
            target_id, target_kind, model, integrations, checks = self._catalog.load(
                profile=profile, environment_id=environment_id
            )
            self._validate_catalog(model, integrations, checks)
        except BootstrapIntegrationError:
            raise
        except ValueError as error:
            raise BootstrapIntegrationError("bootstrap_integration_plan_invalid") from error
        payload = self._plan_payload(
            release_id=release_id,
            profile=profile,
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
            configuration_digest=configuration_digest,
            trust_plan_digest=trust_plan_digest,
            data_plan_digest=data_plan_digest,
            service_plan_digest=service_plan_digest,
            identity_plan_digest=identity_plan_digest,
            target_id=target_id,
            target_kind=target_kind,
            model=model,
            integrations=integrations,
            checks=checks,
        )
        plan = BootstrapIntegrationPlan(
            schema_version="atlas.bootstrap-integration-plan.v1",
            release_id=release_id,
            profile=profile,
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
            configuration_digest=configuration_digest,
            trust_plan_digest=trust_plan_digest,
            data_plan_digest=data_plan_digest,
            service_plan_digest=service_plan_digest,
            identity_plan_digest=identity_plan_digest,
            integration_plan_digest=sha256(self._canonical_json(payload)).hexdigest(),
            target_id=target_id,
            target_kind=target_kind,
            target_state=IntegrationTargetState.EMPTY,
            model_endpoint=model,
            integrations=integrations,
            checks=checks,
            state=IntegrationPlanState.PASSED,
            result_code="bootstrap.integration-plan.passed",
            generated_at=self._clock(),
        )
        return replace(plan, target_state=await self._target.inspect(plan=plan))

    @classmethod
    def render(cls, plan: BootstrapIntegrationPlan) -> bytes:
        return cls._canonical_json(
            {
                "schema_version": "atlas.synthetic-integration-state.v1",
                "owner_id": "owner.project-atlas",
                "release_id": plan.release_id,
                "profile": plan.profile.value,
                "organization_id": plan.organization_id,
                "environment_id": plan.environment_id,
                "site_id": plan.site_id,
                "configuration_digest": plan.configuration_digest,
                "trust_plan_digest": plan.trust_plan_digest,
                "data_plan_digest": plan.data_plan_digest,
                "service_plan_digest": plan.service_plan_digest,
                "identity_plan_digest": plan.identity_plan_digest,
                "integration_plan_digest": plan.integration_plan_digest,
                "target_id": plan.target_id,
                "target_kind": plan.target_kind,
                "model_endpoint": cls._model_payload(plan.model_endpoint),
                "integrations": [cls._integration_payload(item) for item in plan.integrations],
                "checks": [cls._check_payload(item) for item in plan.checks],
                "synthetic_inference_fixture_validated": True,
                "actual_model_request_performed": False,
                "network_request_performed": False,
                "secret_resolution_performed": False,
                "integration_activation_performed": False,
                "connector_invocation_performed": False,
                "knowledge_ingestion_performed": False,
                "infrastructure_mutation_performed": False,
                "ai_advice_generated": False,
            }
        )

    @staticmethod
    def _validate_catalog(
        model: ModelEndpointRegistration,
        integrations: tuple[CoreIntegrationRegistration, ...],
        checks: tuple[IntegrationValidationCheck, ...],
    ) -> None:
        if len(integrations) != 4 or len(checks) != 12:
            raise ValueError("integration catalog is outside platform bounds")
        if len({item.integration_id for item in integrations}) != len(integrations):
            raise ValueError("integration catalog contains duplicate integrations")
        if len({item.check_id for item in checks}) != len(checks):
            raise ValueError("integration catalog contains duplicate checks")
        valid_subjects = {model.endpoint_id, *(item.integration_id for item in integrations)}
        if any(
            item.subject_id not in valid_subjects
            or not item.mandatory
            or item.state is not IntegrationCheckState.PASSED
            for item in checks
        ):
            raise ValueError("integration catalog check evidence is invalid")

    @classmethod
    def _plan_payload(cls, **values: object) -> dict[str, object]:
        model = cast(ModelEndpointRegistration, values.pop("model"))
        integrations = cast(tuple[CoreIntegrationRegistration, ...], values.pop("integrations"))
        checks = cast(tuple[IntegrationValidationCheck, ...], values.pop("checks"))
        profile = cast(DeploymentProfile, values["profile"])
        return {
            "schema_version": "atlas.bootstrap-integration-plan.v1",
            **values,
            "profile": profile.value,
            "model_endpoint": cls._model_payload(model),
            "integrations": [cls._integration_payload(item) for item in integrations],
            "checks": [cls._check_payload(item) for item in checks],
            "network_request_authorized": False,
            "secret_resolution_authorized": False,
            "integration_activation_authorized": False,
            "connector_invocation_authorized": False,
            "knowledge_ingestion_authorized": False,
            "infrastructure_mutation_authorized": False,
            "ai_operation_authorized": False,
        }

    @staticmethod
    def _model_payload(item: ModelEndpointRegistration) -> dict[str, object]:
        return {
            "endpoint_id": item.endpoint_id,
            "owner_id": item.owner_id,
            "provider_type": item.provider_type,
            "service_reference_id": item.service_reference_id,
            "credential_reference_id": item.credential_reference_id,
            "model_id": item.model_id,
            "context_limit": item.context_limit,
            "output_limit": item.output_limit,
            "data_classification_ceiling": item.data_classification_ceiling,
            "residency_boundary_id": item.residency_boundary_id,
            "timeout_seconds": item.timeout_seconds,
            "max_retries": item.max_retries,
            "rate_limit_per_minute": item.rate_limit_per_minute,
            "concurrency_limit": item.concurrency_limit,
            "telemetry_classification": item.telemetry_classification,
            "approved_task_class_ids": item.approved_task_class_ids,
        }

    @staticmethod
    def _integration_payload(item: CoreIntegrationRegistration) -> dict[str, object]:
        return {
            "integration_id": item.integration_id,
            "integration_type": item.integration_type,
            "owner_id": item.owner_id,
            "purpose_id": item.purpose_id,
            "classification": item.classification,
            "endpoint_reference_id": item.endpoint_reference_id,
            "trust_reference_id": item.trust_reference_id,
            "credential_reference_id": item.credential_reference_id,
            "scope_id": item.scope_id,
            "rate_limit_per_minute": item.rate_limit_per_minute,
            "validation_operation_id": item.validation_operation_id,
            "mapping_preview_id": item.mapping_preview_id,
            "data_flow_id": item.data_flow_id,
            "activation_state": item.activation_state.value,
        }

    @staticmethod
    def _check_payload(item: IntegrationValidationCheck) -> dict[str, object]:
        return {
            "check_id": item.check_id,
            "subject_id": item.subject_id,
            "state": item.state.value,
            "result_code": item.result_code,
            "mandatory": item.mandatory,
        }

    @staticmethod
    def _canonical_json(payload: Mapping[str, object]) -> bytes:
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


class BootstrapIntegrationValidationService:
    def __init__(
        self,
        *,
        repository: BootstrapStateRepository,
        plan_service: BootstrapIntegrationPlanService,
        target: BootstrapIntegrationTarget,
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
        service_plan_digest: str,
        identity_plan_digest: str,
        integration_schema_version: str,
        integration_plan_digest: str,
        target_id: str,
        expected_target_state: IntegrationTargetState,
        justification: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> BootstrapMutationResult:
        current = await self._repository.get_current(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
        )
        if (
            current is None
            or current.run_id != run_id
            or organization_id != actor.organization_id
            or environment_id != self._environment_id
            or site_id != self._site_id
        ):
            await self._audit_denial(actor, correlation_id)
            raise BootstrapIntegrationError("bootstrap_run_unavailable")
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
                "configuration_digest": configuration_digest,
                "overlay": self._overlay_payload(overlay),
                "trust_plan_digest": trust_plan_digest,
                "data_plan_digest": data_plan_digest,
                "migration_artifact_digest": migration_artifact_digest,
                "service_plan_digest": service_plan_digest,
                "identity_plan_digest": identity_plan_digest,
                "integration_schema_version": integration_schema_version,
                "integration_plan_digest": integration_plan_digest,
                "target_id": target_id,
                "expected_target_state": expected_target_state.value,
                "justification": justification,
            }
        )
        execution_id = self._execution_id(run_id, lease_holder_id, idempotency_key, fingerprint)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            result_code="bootstrap_integration_execution_authorized",
            run_id=run_id,
            idempotency_key=idempotency_key,
            metadata=(
                ("execution_id", execution_id),
                ("integration_plan_digest", integration_plan_digest),
            ),
        )
        prior = current.integration_validation
        if prior is not None and prior.execution_id == execution_id:
            if prior.state is not IntegrationValidationState.RUNNING:
                return BootstrapMutationResult(
                    record=current, replayed=True, integration_validation=prior
                )
            running = prior
            begin = BootstrapMutationResult(
                record=current, replayed=True, integration_validation=running
            )
        else:
            self._validate_run(
                current=current,
                release_id=release_id,
                profile=profile,
                plan_digest=plan_digest,
                resume_key=resume_key,
                configuration_digest=configuration_digest,
                identity_plan_digest=identity_plan_digest,
            )
            plan = await self._plan_service.prepare(
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
                service_plan_digest=service_plan_digest,
                identity_plan_digest=identity_plan_digest,
            )
            if (
                integration_schema_version != plan.schema_version
                or integration_plan_digest != plan.integration_plan_digest
                or target_id != plan.target_id
                or expected_target_state is not plan.target_state
            ):
                raise BootstrapIntegrationError("bootstrap_integration_plan_digest_mismatch")
            if prior is not None and prior.state is IntegrationValidationState.FAILED:
                await self._target.cleanup_attempt(prior.execution_id)
            running = IntegrationValidationExecution(
                execution_id=execution_id,
                phase_id="phase.integrations",
                release_id=release_id,
                profile=profile,
                configuration_digest=configuration_digest,
                trust_plan_digest=trust_plan_digest,
                data_plan_digest=data_plan_digest,
                service_plan_digest=service_plan_digest,
                identity_plan_digest=identity_plan_digest,
                integration_schema_version=integration_schema_version,
                integration_plan_digest=integration_plan_digest,
                target_id=target_id,
                state=IntegrationValidationState.RUNNING,
                result_code="bootstrap.integrations.running",
                started_at=self._clock(),
                completed_at=None,
                model_check_count=0,
                integration_check_count=0,
                mandatory_pass_count=0,
                activation_count=0,
                network_request_count=0,
                secret_resolution_count=0,
                checks=(),
                evidence=(),
            )
            begin = await self._repository.begin_integration_validation(
                run_id=run_id,
                plan_digest=plan_digest,
                resume_key=resume_key,
                execution=running,
                lease_holder_id=lease_holder_id,
                expected_version=expected_version,
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
                now=running.started_at,
            )
        plan = await self._plan_service.prepare(
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
            service_plan_digest=service_plan_digest,
            identity_plan_digest=identity_plan_digest,
        )
        try:
            receipt = await self._target.publish(
                execution_id=running.execution_id,
                plan=plan,
                state_document=self._plan_service.render(plan),
            )
            finished = replace(
                running,
                state=IntegrationValidationState.COMPLETED,
                result_code="bootstrap.integrations.completed",
                completed_at=self._clock(),
                model_check_count=8,
                integration_check_count=4,
                mandatory_pass_count=12,
                checks=receipt.checks,
                evidence=receipt.evidence,
            )
        except BootstrapIntegrationError as error:
            finished = replace(
                running,
                state=IntegrationValidationState.FAILED,
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
                ("execution_id", execution_id),
                ("integration_plan_digest", integration_plan_digest),
            ),
        )
        return await self._repository.finish_integration_validation(
            run_id=run_id,
            execution=finished,
            lease_holder_id=lease_holder_id,
            expected_version=begin.record.version,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            now=finished.completed_at or self._clock(),
        )

    @staticmethod
    def _validate_run(
        *,
        current: BootstrapRunRecord,
        release_id: str,
        profile: DeploymentProfile,
        plan_digest: str,
        resume_key: str,
        configuration_digest: str,
        identity_plan_digest: str,
    ) -> None:
        if (
            current.identity.release_id != release_id
            or current.identity.profile is not profile
            or current.identity.plan_digest != plan_digest
            or current.identity.resume_key != resume_key
            or current.identity.configuration_digest != configuration_digest
            or current.current_phase_id != "phase.integrations"
        ):
            raise BootstrapIntegrationError("bootstrap_plan_mismatch")
        identity = current.identity_handoff
        if (
            identity is None
            or identity.state is not IdentityHandoffState.COMPLETED
            or identity.identity_plan_digest != identity_plan_digest
            or identity.group_mapping_count < 1
            or identity.validation_count != 5
            or not identity.credential_replacement_required
            or not identity.recovery_identity_verified
            or not identity.bootstrap_material_sealed
            or not identity.pilot_identity_verified
            or not identity.enterprise_authentication_validated
            or len(identity.evidence) != 1
            or "phase.identity" not in current.completed_phase_ids
        ):
            raise BootstrapIntegrationError("bootstrap_identity_evidence_missing")

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
                event_type="atlas.platform.bootstrap-integrations.execute",
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
                event_type="atlas.platform.bootstrap-integrations.denied",
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
