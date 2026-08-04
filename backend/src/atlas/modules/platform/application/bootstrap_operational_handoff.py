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
from atlas.modules.platform.application.bootstrap_handoff_ports import (
    BootstrapHandoffError,
    BootstrapHandoffTarget,
)
from atlas.modules.platform.application.bootstrap_state_ports import BootstrapStateRepository
from atlas.modules.platform.domain.bootstrap_artifact_acquisition import ArtifactAcquisitionState
from atlas.modules.platform.domain.bootstrap_configuration_rendering import (
    ConfigurationRenderingState,
)
from atlas.modules.platform.domain.bootstrap_data_initialization import (
    BackupApplicability,
    DataInitializationState,
)
from atlas.modules.platform.domain.bootstrap_end_to_end_verification import (
    VerificationExecutionState,
)
from atlas.modules.platform.domain.bootstrap_identity_handoff import IdentityHandoffState
from atlas.modules.platform.domain.bootstrap_integration_validation import (
    IntegrationValidationState,
)
from atlas.modules.platform.domain.bootstrap_operational_handoff import (
    BootstrapHandoffPlan,
    HandoffCheckState,
    HandoffExecutionState,
    HandoffPlanState,
    HandoffReadinessClaims,
    HandoffReadinessClass,
    HandoffTargetState,
    OperationalHandoffCheck,
    OperationalHandoffExecution,
)
from atlas.modules.platform.domain.bootstrap_service_deployment import ServiceDeploymentState
from atlas.modules.platform.domain.bootstrap_state import (
    BootstrapMutationResult,
    BootstrapRunRecord,
)
from atlas.modules.platform.domain.bootstrap_trust_provisioning import TrustProvisioningState
from atlas.modules.platform.domain.release_preflight import DeploymentProfile


class BootstrapHandoffPlanService:
    def __init__(
        self,
        *,
        repository: BootstrapStateRepository,
        target: BootstrapHandoffTarget,
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
        verification_plan_digest: str,
        verification_report_digest: str,
    ) -> BootstrapHandoffPlan:
        if (
            organization_id != actor.organization_id
            or environment_id != self._environment_id
            or site_id != self._site_id
        ):
            raise BootstrapHandoffError("bootstrap_handoff_plan_unavailable")
        current = await self._repository.get_current(
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
        )
        if current is None or current.run_id != source_run_id:
            raise BootstrapHandoffError("bootstrap_handoff_plan_unavailable")
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
            verification_plan_digest=verification_plan_digest,
            verification_report_digest=verification_report_digest,
        )
        source_evidence_digest = self._source_evidence_digest(current)
        checks = self._checks()
        target_id = "target.bootstrap-handoff-report"
        target_kind = "target-kind.local-handoff-report"
        ingress_contract_id = "ingress.local-api-ui"
        readiness_class = HandoffReadinessClass.DEVELOPER_LINUX_LAB_BOOTSTRAP_COMPLETE
        readiness_claims = HandoffReadinessClaims()
        known_limitation_ids = self._known_limitations()
        pending_action_ids = self._pending_actions()
        owner_role_ids = self._owner_roles()
        missing_production_evidence_ids = self._missing_production_evidence()
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
            verification_plan_digest=verification_plan_digest,
            verification_report_digest=verification_report_digest,
            source_evidence_digest=source_evidence_digest,
            ingress_contract_id=ingress_contract_id,
            target_id=target_id,
            target_kind=target_kind,
            readiness_class=readiness_class,
            readiness_claims=readiness_claims,
            known_limitation_ids=known_limitation_ids,
            pending_action_ids=pending_action_ids,
            owner_role_ids=owner_role_ids,
            missing_production_evidence_ids=missing_production_evidence_ids,
            checks=checks,
        )
        plan = BootstrapHandoffPlan(
            schema_version="atlas.bootstrap-handoff-plan.v1",
            suite_version="atlas.bootstrap-handoff-suite.v1",
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
            verification_plan_digest=verification_plan_digest,
            verification_report_digest=verification_report_digest,
            source_evidence_digest=source_evidence_digest,
            handoff_plan_digest=sha256(self._canonical_json(payload)).hexdigest(),
            ingress_contract_id=ingress_contract_id,
            target_id=target_id,
            target_kind=target_kind,
            target_state=HandoffTargetState.EMPTY,
            readiness_class=readiness_class,
            readiness_claims=readiness_claims,
            known_limitation_ids=known_limitation_ids,
            pending_action_ids=pending_action_ids,
            owner_role_ids=owner_role_ids,
            missing_production_evidence_ids=missing_production_evidence_ids,
            checks=checks,
            state=HandoffPlanState.PASSED,
            result_code="bootstrap.handoff-plan.passed",
            generated_at=self._clock(),
        )
        return replace(plan, target_state=await self._target.inspect(plan=plan))

    @classmethod
    def render(cls, plan: BootstrapHandoffPlan) -> bytes:
        return cls._canonical_json(
            {
                "schema_version": "atlas.synthetic-handoff-report.v1",
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
                "verification_report_digest": plan.verification_report_digest,
                "source_evidence_digest": plan.source_evidence_digest,
                "handoff_plan_digest": plan.handoff_plan_digest,
                "ingress_contract_id": plan.ingress_contract_id,
                "target_id": plan.target_id,
                "completed_phase_ids": [
                    "phase.preflight",
                    "phase.acquire",
                    "phase.configure",
                    "phase.trust",
                    "phase.data",
                    "phase.services",
                    "phase.identity",
                    "phase.integrations",
                    "phase.verify",
                ],
                "support_procedure_reference": "support.bootstrap-troubleshooting",
                "installation_audit_reference": "audit.bootstrap-run",
                "handoff_audit_reference": "audit.bootstrap-handoff",
                "checks": [cls._check_payload(item) for item in plan.checks],
                "readiness": {
                    "classification": plan.readiness_class.value,
                    "claims": cls._claims_payload(plan.readiness_claims),
                    "known_limitation_ids": list(plan.known_limitation_ids),
                    "pending_action_ids": list(plan.pending_action_ids),
                    "owner_role_ids": list(plan.owner_role_ids),
                    "missing_production_evidence_ids": list(plan.missing_production_evidence_ids),
                },
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
                "support_bundle_export_performed": False,
                "ticket_creation_performed": False,
                "notification_performed": False,
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
        verification_plan_digest: str,
        verification_report_digest: str,
    ) -> None:
        allowed_versions = {source_run_version}
        if current.operational_handoff is not None:
            allowed_versions.add(source_run_version + 1)
        if (
            current.version not in allowed_versions
            or current.identity.release_id != release_id
            or current.identity.profile is not profile
            or current.identity.configuration_digest != configuration_digest
            or current.current_phase_id != "phase.handoff"
        ):
            raise BootstrapHandoffError("bootstrap_handoff_source_mismatch")
        artifact = current.artifact_acquisition
        configuration = current.configuration_rendering
        trust = current.trust_provisioning
        data = current.data_initialization
        services = current.service_deployment
        identity = current.identity_handoff
        integrations = current.integration_validation
        verification = current.end_to_end_verification
        required_phases = {
            "phase.acquire",
            "phase.configure",
            "phase.trust",
            "phase.data",
            "phase.services",
            "phase.identity",
            "phase.integrations",
            "phase.verify",
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
            and verification is not None
            and verification.state is VerificationExecutionState.COMPLETED
            and verification.verification_plan_digest == verification_plan_digest
            and len(verification.evidence) == 1
            and verification.evidence[0].sha256 == verification_report_digest
            and verification.passed_count == 12
            and verification.failed_count == 0
            and verification.skipped_count == 0
            and verification.not_applicable_count == 3
            and verification.unresolved_mandatory_count == 0
            and verification.external_operation_count == 0
        )
        if not valid:
            raise BootstrapHandoffError("bootstrap_handoff_evidence_missing")

    @staticmethod
    def _checks() -> tuple[OperationalHandoffCheck, ...]:
        passed = HandoffCheckState.PASSED
        na = HandoffCheckState.NOT_APPLICABLE
        rows = (
            (
                "handoff.release-profile",
                "category.release",
                "release.profile-bound",
                passed,
                "handoff.release-profile.bound",
                True,
            ),
            (
                "handoff.phase-evidence",
                "category.evidence",
                "evidence.bootstrap-phases",
                passed,
                "handoff.phase-evidence.complete",
                True,
            ),
            (
                "handoff.verification-evidence",
                "category.evidence",
                "evidence.verification-report",
                passed,
                "handoff.verification-evidence.bound",
                True,
            ),
            (
                "handoff.integrity-record",
                "category.integrity",
                "integrity.digest-chain",
                passed,
                "handoff.integrity-record.complete",
                True,
            ),
            (
                "handoff.readiness-class",
                "category.readiness",
                "readiness.developer-linux-lab",
                passed,
                "handoff.readiness-class.bounded",
                True,
            ),
            (
                "handoff.production-claims",
                "category.readiness",
                "readiness.production-claims-false",
                passed,
                "handoff.production-claims.denied",
                True,
            ),
            (
                "handoff.known-limitations",
                "category.operations",
                "operations.known-limitations",
                passed,
                "handoff.known-limitations.recorded",
                True,
            ),
            (
                "handoff.pending-actions",
                "category.operations",
                "operations.pending-actions",
                passed,
                "handoff.pending-actions.recorded",
                True,
            ),
            (
                "handoff.owner-roles",
                "category.operations",
                "operations.owner-roles",
                passed,
                "handoff.owner-roles.recorded",
                True,
            ),
            (
                "handoff.support-procedure",
                "category.support",
                "support.procedure-reference",
                passed,
                "handoff.support-procedure.recorded",
                True,
            ),
            (
                "handoff.security-redaction",
                "category.security",
                "security.sanitized-report",
                passed,
                "handoff.security-redaction.passed",
                True,
            ),
            (
                "handoff.zero-operations",
                "category.security",
                "security.zero-external-operations",
                passed,
                "handoff.zero-operations.passed",
                True,
            ),
            (
                "handoff.production-ownership",
                "category.production",
                "production.named-owners",
                na,
                "handoff.production-ownership.not-available",
                False,
            ),
            (
                "handoff.production-recovery",
                "category.production",
                "production.backup-restore-ha-dr",
                na,
                "handoff.production-recovery.not-available",
                False,
            ),
            (
                "handoff.release-approval",
                "category.production",
                "production.release-support-approval",
                na,
                "handoff.release-approval.not-available",
                False,
            ),
        )
        return tuple(OperationalHandoffCheck(*row) for row in rows)

    @classmethod
    def _source_evidence_digest(cls, current: BootstrapRunRecord) -> str:
        executions = (
            current.artifact_acquisition,
            current.configuration_rendering,
            current.trust_provisioning,
            current.data_initialization,
            current.service_deployment,
            current.identity_handoff,
            current.integration_validation,
            current.end_to_end_verification,
        )
        payload = {
            "checkpoints": [
                {
                    "phase_id": item.phase_id,
                    "state": item.state.value,
                    "safe_output_references": list(item.safe_output_references),
                }
                for item in current.checkpoints
                if item.phase_id != "phase.handoff"
            ],
            "executions": [
                {
                    "phase_id": execution.phase_id,
                    "execution_id": execution.execution_id,
                    "result_code": execution.result_code,
                    "execution_digest": sha256(repr(execution).encode()).hexdigest(),
                    "evidence_sha256": [item.sha256 for item in execution.evidence],
                }
                for execution in executions
                if execution is not None
            ],
        }
        return sha256(cls._canonical_json(payload)).hexdigest()

    @staticmethod
    def _known_limitations() -> tuple[str, ...]:
        return (
            "limitation.developer-linux-lab-only",
            "limitation.no-production-ingress",
            "limitation.no-customer-integrations",
            "limitation.no-backup-restore-validation",
            "limitation.no-ha-dr-certification",
            "limitation.no-support-acceptance",
            "limitation.no-release-approval",
        )

    @staticmethod
    def _pending_actions() -> tuple[str, ...]:
        return (
            "action.assign-production-owners",
            "action.validate-production-ingress",
            "action.validate-customer-integrations",
            "action.test-backup-restore",
            "action.exercise-ha-dr",
            "action.complete-support-acceptance",
            "action.complete-release-approval",
        )

    @staticmethod
    def _owner_roles() -> tuple[str, ...]:
        return (
            "owner-role.service",
            "owner-role.platform",
            "owner-role.security",
            "owner-role.data",
            "owner-role.escalation",
        )

    @staticmethod
    def _missing_production_evidence() -> tuple[str, ...]:
        return (
            "evidence.production-environment",
            "evidence.named-production-owners",
            "evidence.customer-integrations",
            "evidence.backup-restore-test",
            "evidence.ha-dr-exercise",
            "evidence.support-acceptance",
            "evidence.release-approval",
        )

    @classmethod
    def _plan_payload(cls, **values: object) -> dict[str, object]:
        checks = cast(tuple[OperationalHandoffCheck, ...], values.pop("checks"))
        profile = cast(DeploymentProfile, values["profile"])
        readiness_class = cast(HandoffReadinessClass, values.pop("readiness_class"))
        readiness_claims = cast(HandoffReadinessClaims, values.pop("readiness_claims"))
        return {
            "schema_version": "atlas.bootstrap-handoff-plan.v1",
            "suite_version": "atlas.bootstrap-handoff-suite.v1",
            **values,
            "profile": profile.value,
            "readiness_class": readiness_class.value,
            "readiness_claims": cls._claims_payload(readiness_claims),
            "checks": [cls._check_payload(item) for item in checks],
            "external_operations_authorized": False,
        }

    @staticmethod
    def _claims_payload(claims: HandoffReadinessClaims) -> dict[str, bool]:
        return {
            "production_ready": claims.production_ready,
            "customer_integrations_validated": claims.customer_integrations_validated,
            "support_accepted": claims.support_accepted,
            "ha_certified": claims.ha_certified,
            "dr_certified": claims.dr_certified,
            "backup_restore_validated": claims.backup_restore_validated,
            "release_approved": claims.release_approved,
        }

    @staticmethod
    def _check_payload(item: OperationalHandoffCheck) -> dict[str, object]:
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


class BootstrapOperationalHandoffService:
    def __init__(
        self,
        *,
        repository: BootstrapStateRepository,
        plan_service: BootstrapHandoffPlanService,
        target: BootstrapHandoffTarget,
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
        verification_plan_digest: str,
        verification_report_digest: str,
        source_evidence_digest: str,
        handoff_schema_version: str,
        suite_version: str,
        handoff_plan_digest: str,
        target_id: str,
        expected_target_state: HandoffTargetState,
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
            raise BootstrapHandoffError("bootstrap_run_unavailable")
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
                "verification_plan_digest": verification_plan_digest,
                "verification_report_digest": verification_report_digest,
                "source_evidence_digest": source_evidence_digest,
                "handoff_schema_version": handoff_schema_version,
                "suite_version": suite_version,
                "handoff_plan_digest": handoff_plan_digest,
                "target_id": target_id,
                "expected_target_state": expected_target_state.value,
                "justification": justification,
            }
        )
        execution_id = self._execution_id(run_id, lease_holder_id, idempotency_key, fingerprint)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            result_code="bootstrap_handoff_execution_authorized",
            run_id=run_id,
            idempotency_key=idempotency_key,
            metadata=(
                ("execution_id", execution_id),
                ("handoff_plan_digest", handoff_plan_digest),
            ),
        )
        prior = current.operational_handoff
        if prior is not None and prior.execution_id == execution_id:
            if prior.state is not HandoffExecutionState.RUNNING:
                return BootstrapMutationResult(
                    record=current, replayed=True, operational_handoff=prior
                )
            running = prior
            begin = BootstrapMutationResult(
                record=current, replayed=True, operational_handoff=running
            )
        else:
            if (
                current.identity.plan_digest != plan_digest
                or current.identity.resume_key != resume_key
                or current.current_phase_id != "phase.handoff"
            ):
                raise BootstrapHandoffError("bootstrap_plan_mismatch")
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
                verification_plan_digest=verification_plan_digest,
                verification_report_digest=verification_report_digest,
            )
            if (
                handoff_schema_version != plan.schema_version
                or suite_version != plan.suite_version
                or handoff_plan_digest != plan.handoff_plan_digest
                or target_id != plan.target_id
                or expected_target_state is not plan.target_state
                or source_evidence_digest != plan.source_evidence_digest
            ):
                raise BootstrapHandoffError("bootstrap_handoff_plan_digest_mismatch")
            if prior is not None and prior.state is HandoffExecutionState.FAILED:
                await self._target.cleanup_attempt(prior.execution_id)
            running = OperationalHandoffExecution(
                execution_id=execution_id,
                phase_id="phase.handoff",
                release_id=release_id,
                profile=profile,
                configuration_digest=configuration_digest,
                trust_plan_digest=trust_plan_digest,
                data_plan_digest=data_plan_digest,
                service_plan_digest=service_plan_digest,
                identity_plan_digest=identity_plan_digest,
                integration_plan_digest=integration_plan_digest,
                verification_plan_digest=verification_plan_digest,
                verification_report_digest=verification_report_digest,
                source_evidence_digest=source_evidence_digest,
                handoff_schema_version=handoff_schema_version,
                suite_version=suite_version,
                handoff_plan_digest=handoff_plan_digest,
                target_id=target_id,
                readiness_class=plan.readiness_class,
                readiness_claims=plan.readiness_claims,
                state=HandoffExecutionState.RUNNING,
                result_code="bootstrap.handoff.running",
                started_at=self._clock(),
                completed_at=None,
                passed_count=0,
                not_applicable_count=0,
                mandatory_pass_count=0,
                known_limitation_count=0,
                pending_action_count=0,
                owner_role_count=0,
                missing_production_evidence_count=0,
                external_operation_count=0,
                checks=(),
                evidence=(),
            )
            begin = await self._repository.begin_operational_handoff(
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
            verification_plan_digest=verification_plan_digest,
            verification_report_digest=verification_report_digest,
        )
        try:
            receipt = await self._target.publish(
                execution_id=running.execution_id,
                plan=plan,
                report=self._plan_service.render(plan),
            )
            finished = replace(
                running,
                state=HandoffExecutionState.COMPLETED,
                result_code="bootstrap.handoff.completed",
                completed_at=self._clock(),
                passed_count=12,
                not_applicable_count=3,
                mandatory_pass_count=12,
                known_limitation_count=7,
                pending_action_count=7,
                owner_role_count=5,
                missing_production_evidence_count=7,
                checks=receipt.checks,
                evidence=receipt.evidence,
            )
        except BootstrapHandoffError as error:
            finished = replace(
                running,
                state=HandoffExecutionState.FAILED,
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
                ("handoff_plan_digest", handoff_plan_digest),
            ),
        )
        return await self._repository.finish_operational_handoff(
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
                event_type="atlas.platform.bootstrap-handoff.execute",
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
                event_type="atlas.platform.bootstrap-handoff.denied",
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
