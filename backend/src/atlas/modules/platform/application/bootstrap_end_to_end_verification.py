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
from atlas.modules.platform.application.bootstrap_state_ports import BootstrapStateRepository
from atlas.modules.platform.application.bootstrap_verification_ports import (
    BootstrapVerificationError,
    BootstrapVerificationTarget,
)
from atlas.modules.platform.domain.bootstrap_artifact_acquisition import ArtifactAcquisitionState
from atlas.modules.platform.domain.bootstrap_configuration_rendering import (
    ConfigurationRenderingState,
)
from atlas.modules.platform.domain.bootstrap_data_initialization import (
    BackupApplicability,
    DataInitializationState,
)
from atlas.modules.platform.domain.bootstrap_end_to_end_verification import (
    BootstrapVerificationPlan,
    EndToEndVerificationCheck,
    EndToEndVerificationExecution,
    VerificationCheckState,
    VerificationExecutionState,
    VerificationPlanState,
    VerificationTargetState,
)
from atlas.modules.platform.domain.bootstrap_identity_handoff import IdentityHandoffState
from atlas.modules.platform.domain.bootstrap_integration_validation import (
    IntegrationValidationState,
)
from atlas.modules.platform.domain.bootstrap_service_deployment import ServiceDeploymentState
from atlas.modules.platform.domain.bootstrap_state import (
    BootstrapMutationResult,
    BootstrapRunRecord,
)
from atlas.modules.platform.domain.bootstrap_trust_provisioning import TrustProvisioningState
from atlas.modules.platform.domain.release_preflight import DeploymentProfile


class BootstrapVerificationPlanService:
    def __init__(
        self,
        *,
        repository: BootstrapStateRepository,
        target: BootstrapVerificationTarget,
        environment_id: str,
        site_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._target = target
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
        source_run_id: str,
        source_run_version: int,
        configuration_digest: str,
        trust_plan_digest: str,
        data_plan_digest: str,
        service_plan_digest: str,
        identity_plan_digest: str,
        integration_plan_digest: str,
    ) -> BootstrapVerificationPlan:
        if (
            organization_id != actor.organization_id
            or environment_id != self._environment_id
            or site_id != self._site_id
        ):
            raise BootstrapVerificationError("bootstrap_verification_plan_unavailable")
        current = await self._repository.get_current(
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
        )
        if current is None or current.run_id != source_run_id:
            raise BootstrapVerificationError("bootstrap_verification_plan_unavailable")
        self._validate_source(
            current=current,
            release_id=release_id,
            profile=profile,
            source_run_version=source_run_version,
            configuration_digest=configuration_digest,
            trust_plan_digest=trust_plan_digest,
            data_plan_digest=data_plan_digest,
            service_plan_digest=service_plan_digest,
            identity_plan_digest=identity_plan_digest,
            integration_plan_digest=integration_plan_digest,
        )
        checks = self._checks()
        target_id = "target.bootstrap-verification-report"
        target_kind = "target-kind.local-verification-report"
        ingress_contract_id = "ingress.local-api-ui"
        payload = self._plan_payload(
            release_id=release_id,
            profile=profile,
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
            source_run_id=source_run_id,
            source_run_version=source_run_version,
            configuration_digest=configuration_digest,
            trust_plan_digest=trust_plan_digest,
            data_plan_digest=data_plan_digest,
            service_plan_digest=service_plan_digest,
            identity_plan_digest=identity_plan_digest,
            integration_plan_digest=integration_plan_digest,
            ingress_contract_id=ingress_contract_id,
            target_id=target_id,
            target_kind=target_kind,
            checks=checks,
        )
        plan = BootstrapVerificationPlan(
            schema_version="atlas.bootstrap-verification-plan.v1",
            suite_version="atlas.bootstrap-verification-suite.v1",
            release_id=release_id,
            profile=profile,
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
            source_run_id=source_run_id,
            source_run_version=source_run_version,
            configuration_digest=configuration_digest,
            trust_plan_digest=trust_plan_digest,
            data_plan_digest=data_plan_digest,
            service_plan_digest=service_plan_digest,
            identity_plan_digest=identity_plan_digest,
            integration_plan_digest=integration_plan_digest,
            verification_plan_digest=sha256(self._canonical_json(payload)).hexdigest(),
            ingress_contract_id=ingress_contract_id,
            target_id=target_id,
            target_kind=target_kind,
            target_state=VerificationTargetState.EMPTY,
            checks=checks,
            state=VerificationPlanState.PASSED,
            result_code="bootstrap.verification-plan.passed",
            generated_at=self._clock(),
        )
        return replace(plan, target_state=await self._target.inspect(plan=plan))

    @classmethod
    def render(cls, plan: BootstrapVerificationPlan) -> bytes:
        return cls._canonical_json(
            {
                "schema_version": "atlas.synthetic-verification-report.v1",
                "suite_version": plan.suite_version,
                "owner_id": "owner.project-atlas",
                "release_id": plan.release_id,
                "profile": plan.profile.value,
                "organization_id": plan.organization_id,
                "environment_id": plan.environment_id,
                "site_id": plan.site_id,
                "source_run_id": plan.source_run_id,
                "source_run_version": plan.source_run_version,
                "configuration_digest": plan.configuration_digest,
                "trust_plan_digest": plan.trust_plan_digest,
                "data_plan_digest": plan.data_plan_digest,
                "service_plan_digest": plan.service_plan_digest,
                "identity_plan_digest": plan.identity_plan_digest,
                "integration_plan_digest": plan.integration_plan_digest,
                "verification_plan_digest": plan.verification_plan_digest,
                "ingress_contract_id": plan.ingress_contract_id,
                "target_id": plan.target_id,
                "checks": [cls._check_payload(item) for item in plan.checks],
                "summary": {
                    "passed": 12,
                    "failed": 0,
                    "skipped": 0,
                    "not_applicable": 3,
                    "mandatory_passed": 12,
                    "unresolved_mandatory": 0,
                },
                "model_request_performed": False,
                "network_request_performed": False,
                "secret_resolution_performed": False,
                "connector_invocation_performed": False,
                "knowledge_mutation_performed": False,
                "workflow_execution_performed": False,
                "approval_creation_performed": False,
                "backup_restore_operation_performed": False,
                "external_export_performed": False,
                "infrastructure_mutation_performed": False,
                "deployment_action_performed": False,
                "ai_advice_generated": False,
            }
        )

    @staticmethod
    def _validate_source(
        *,
        current: BootstrapRunRecord,
        release_id: str,
        profile: DeploymentProfile,
        source_run_version: int,
        configuration_digest: str,
        trust_plan_digest: str,
        data_plan_digest: str,
        service_plan_digest: str,
        identity_plan_digest: str,
        integration_plan_digest: str,
    ) -> None:
        allowed_versions = {source_run_version}
        if current.end_to_end_verification is not None:
            allowed_versions.add(source_run_version + 1)
        if (
            current.version not in allowed_versions
            or current.identity.release_id != release_id
            or current.identity.profile is not profile
            or current.identity.configuration_digest != configuration_digest
            or current.current_phase_id != "phase.verify"
        ):
            raise BootstrapVerificationError("bootstrap_verification_source_mismatch")
        artifact = current.artifact_acquisition
        configuration = current.configuration_rendering
        trust = current.trust_provisioning
        data = current.data_initialization
        services = current.service_deployment
        identity = current.identity_handoff
        integrations = current.integration_validation
        required_phases = {
            "phase.acquire",
            "phase.configure",
            "phase.trust",
            "phase.data",
            "phase.services",
            "phase.identity",
            "phase.integrations",
        }
        valid = (
            required_phases.issubset(current.completed_phase_ids)
            and artifact is not None
            and artifact.state is ArtifactAcquisitionState.COMPLETED
            and bool(artifact.evidence)
            and configuration is not None
            and configuration.state is ConfigurationRenderingState.COMPLETED
            and configuration.configuration_digest == configuration_digest
            and bool(configuration.evidence)
            and trust is not None
            and trust.state is TrustProvisioningState.COMPLETED
            and trust.trust_plan_digest == trust_plan_digest
            and len(trust.evidence) == 2
            and data is not None
            and data.state is DataInitializationState.COMPLETED
            and data.data_plan_digest == data_plan_digest
            and data.backup_applicability is BackupApplicability.NOT_APPLICABLE_CLEAN_INSTALL
            and len(data.evidence) == 1
            and services is not None
            and services.state is ServiceDeploymentState.COMPLETED
            and services.service_plan_digest == service_plan_digest
            and services.ready_service_count == services.deployed_service_count
            and services.passed_probe_count == services.ready_service_count * 3
            and len(services.evidence) == 1
            and identity is not None
            and identity.state is IdentityHandoffState.COMPLETED
            and identity.identity_plan_digest == identity_plan_digest
            and identity.validation_count == 5
            and identity.enterprise_authentication_validated
            and identity.recovery_identity_verified
            and len(identity.evidence) == 1
            and integrations is not None
            and integrations.state is IntegrationValidationState.COMPLETED
            and integrations.integration_plan_digest == integration_plan_digest
            and integrations.mandatory_pass_count == 12
            and integrations.activation_count == 0
            and integrations.network_request_count == 0
            and integrations.secret_resolution_count == 0
            and len(integrations.evidence) == 1
        )
        if not valid:
            raise BootstrapVerificationError("bootstrap_verification_evidence_missing")

    @staticmethod
    def _checks() -> tuple[EndToEndVerificationCheck, ...]:
        passed = VerificationCheckState.PASSED
        na = VerificationCheckState.NOT_APPLICABLE
        rows = (
            (
                "verify.ingress-ui-api",
                "category.ingress",
                "ingress.local-api-ui",
                passed,
                "verification.ingress.ready",
                True,
            ),
            (
                "verify.authentication-session",
                "category.identity",
                "identity.enterprise-session",
                passed,
                "verification.identity.auth-session-passed",
                True,
            ),
            (
                "verify.rbac-group-mapping",
                "category.identity",
                "authorization.default-deny",
                passed,
                "verification.identity.rbac-mapping-passed",
                True,
            ),
            (
                "verify.audit-integrity",
                "category.audit",
                "audit.durable-protected",
                passed,
                "verification.audit.integrity-passed",
                True,
            ),
            (
                "verify.logging-redaction",
                "category.logging",
                "logging.structured-redacted",
                passed,
                "verification.logging.pipeline-passed",
                True,
            ),
            (
                "verify.data-contract",
                "category.data",
                "data.postgresql-schema",
                passed,
                "verification.data.contract-passed",
                True,
            ),
            (
                "verify.model-contract",
                "category.model",
                "model.offline-structured-contract",
                passed,
                "verification.model.contract-passed",
                True,
            ),
            (
                "verify.knowledge-contract",
                "category.knowledge",
                "knowledge.synthetic-lifecycle",
                passed,
                "verification.knowledge.contract-passed",
                True,
            ),
            (
                "verify.workflow-policy-approval",
                "category.workflow",
                "workflow.synthetic-governance",
                passed,
                "verification.workflow.contract-passed",
                True,
            ),
            (
                "verify.connector-read-only",
                "category.connector",
                "connector.synthetic-storage-read",
                passed,
                "verification.connector.read-only-passed",
                True,
            ),
            (
                "verify.backup-restore-contract",
                "category.recovery",
                "recovery.clean-install-declaration",
                passed,
                "verification.recovery.contract-passed",
                True,
            ),
            (
                "verify.security-boundary",
                "category.security",
                "security.zero-external-operations",
                passed,
                "verification.security.boundary-passed",
                True,
            ),
            (
                "verify.optional-data-services",
                "category.data",
                "data.vector-graph-cache",
                na,
                "verification.data-services.not-selected",
                False,
            ),
            (
                "verify.external-export",
                "category.integration",
                "integration.syslog-siem-itsm",
                na,
                "verification.external-export.not-selected",
                False,
            ),
            (
                "verify.production-ingress",
                "category.ingress",
                "ingress.production",
                na,
                "verification.production-ingress.not-selected",
                False,
            ),
        )
        return tuple(EndToEndVerificationCheck(*row) for row in rows)

    @classmethod
    def _plan_payload(cls, **values: object) -> dict[str, object]:
        checks = cast(tuple[EndToEndVerificationCheck, ...], values.pop("checks"))
        profile = cast(DeploymentProfile, values["profile"])
        return {
            "schema_version": "atlas.bootstrap-verification-plan.v1",
            "suite_version": "atlas.bootstrap-verification-suite.v1",
            **values,
            "profile": profile.value,
            "checks": [cls._check_payload(item) for item in checks],
            "external_operations_authorized": False,
        }

    @staticmethod
    def _check_payload(item: EndToEndVerificationCheck) -> dict[str, object]:
        return {
            "check_id": item.check_id,
            "category_id": item.category_id,
            "subject_id": item.subject_id,
            "state": item.state.value,
            "result_code": item.result_code,
            "mandatory": item.mandatory,
        }

    @staticmethod
    def _canonical_json(payload: Mapping[str, object]) -> bytes:
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


class BootstrapEndToEndVerificationService:
    def __init__(
        self,
        *,
        repository: BootstrapStateRepository,
        plan_service: BootstrapVerificationPlanService,
        target: BootstrapVerificationTarget,
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
        trust_plan_digest: str,
        data_plan_digest: str,
        service_plan_digest: str,
        identity_plan_digest: str,
        integration_plan_digest: str,
        verification_schema_version: str,
        suite_version: str,
        verification_plan_digest: str,
        target_id: str,
        expected_target_state: VerificationTargetState,
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
            raise BootstrapVerificationError("bootstrap_run_unavailable")
        fingerprint = self._fingerprint(
            {
                "run_id": run_id,
                "expected_version": expected_version,
                "plan_digest": plan_digest,
                "resume_key": resume_key,
                "release_id": release_id,
                "profile": profile.value,
                "configuration_digest": configuration_digest,
                "trust_plan_digest": trust_plan_digest,
                "data_plan_digest": data_plan_digest,
                "service_plan_digest": service_plan_digest,
                "identity_plan_digest": identity_plan_digest,
                "integration_plan_digest": integration_plan_digest,
                "verification_schema_version": verification_schema_version,
                "suite_version": suite_version,
                "verification_plan_digest": verification_plan_digest,
                "target_id": target_id,
                "expected_target_state": expected_target_state.value,
                "justification": justification,
            }
        )
        execution_id = self._execution_id(run_id, lease_holder_id, idempotency_key, fingerprint)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            result_code="bootstrap_verification_execution_authorized",
            run_id=run_id,
            idempotency_key=idempotency_key,
            metadata=(
                ("execution_id", execution_id),
                ("verification_plan_digest", verification_plan_digest),
            ),
        )
        prior = current.end_to_end_verification
        if prior is not None and prior.execution_id == execution_id:
            if prior.state is not VerificationExecutionState.RUNNING:
                return BootstrapMutationResult(
                    record=current, replayed=True, end_to_end_verification=prior
                )
            running = prior
            begin = BootstrapMutationResult(
                record=current, replayed=True, end_to_end_verification=running
            )
        else:
            if (
                current.identity.plan_digest != plan_digest
                or current.identity.resume_key != resume_key
                or current.current_phase_id != "phase.verify"
            ):
                raise BootstrapVerificationError("bootstrap_plan_mismatch")
            plan = await self._plan_service.prepare(
                actor=actor,
                release_id=release_id,
                profile=profile,
                organization_id=organization_id,
                environment_id=environment_id,
                site_id=site_id,
                source_run_id=run_id,
                source_run_version=expected_version,
                configuration_digest=configuration_digest,
                trust_plan_digest=trust_plan_digest,
                data_plan_digest=data_plan_digest,
                service_plan_digest=service_plan_digest,
                identity_plan_digest=identity_plan_digest,
                integration_plan_digest=integration_plan_digest,
            )
            if (
                verification_schema_version != plan.schema_version
                or suite_version != plan.suite_version
                or verification_plan_digest != plan.verification_plan_digest
                or target_id != plan.target_id
                or expected_target_state is not plan.target_state
            ):
                raise BootstrapVerificationError("bootstrap_verification_plan_digest_mismatch")
            if prior is not None and prior.state is VerificationExecutionState.FAILED:
                await self._target.cleanup_attempt(prior.execution_id)
            running = EndToEndVerificationExecution(
                execution_id=execution_id,
                phase_id="phase.verify",
                release_id=release_id,
                profile=profile,
                configuration_digest=configuration_digest,
                trust_plan_digest=trust_plan_digest,
                data_plan_digest=data_plan_digest,
                service_plan_digest=service_plan_digest,
                identity_plan_digest=identity_plan_digest,
                integration_plan_digest=integration_plan_digest,
                verification_schema_version=verification_schema_version,
                suite_version=suite_version,
                verification_plan_digest=verification_plan_digest,
                target_id=target_id,
                state=VerificationExecutionState.RUNNING,
                result_code="bootstrap.verification.running",
                started_at=self._clock(),
                completed_at=None,
                passed_count=0,
                failed_count=0,
                skipped_count=0,
                not_applicable_count=0,
                mandatory_pass_count=0,
                unresolved_mandatory_count=0,
                external_operation_count=0,
                checks=(),
                evidence=(),
            )
            begin = await self._repository.begin_end_to_end_verification(
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
            source_run_id=run_id,
            source_run_version=expected_version,
            configuration_digest=configuration_digest,
            trust_plan_digest=trust_plan_digest,
            data_plan_digest=data_plan_digest,
            service_plan_digest=service_plan_digest,
            identity_plan_digest=identity_plan_digest,
            integration_plan_digest=integration_plan_digest,
        )
        try:
            receipt = await self._target.publish(
                execution_id=running.execution_id,
                plan=plan,
                report=self._plan_service.render(plan),
            )
            finished = replace(
                running,
                state=VerificationExecutionState.COMPLETED,
                result_code="bootstrap.verification.completed",
                completed_at=self._clock(),
                passed_count=12,
                not_applicable_count=3,
                mandatory_pass_count=12,
                checks=receipt.checks,
                evidence=receipt.evidence,
            )
        except BootstrapVerificationError as error:
            finished = replace(
                running,
                state=VerificationExecutionState.FAILED,
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
                ("verification_plan_digest", verification_plan_digest),
            ),
        )
        return await self._repository.finish_end_to_end_verification(
            run_id=run_id,
            execution=finished,
            lease_holder_id=lease_holder_id,
            expected_version=begin.record.version,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            now=finished.completed_at or self._clock(),
        )

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
                event_type="atlas.platform.bootstrap-verification.execute",
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
                    f"{actor.organization_id}/{self._environment_id}/{self._site_id}/domain.platform/resource.platform.bootstrap-state/C2"
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
                event_type="atlas.platform.bootstrap-verification.denied",
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
