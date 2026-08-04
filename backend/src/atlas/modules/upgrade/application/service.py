from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.platform.application.bootstrap_state_ports import BootstrapStateRepository
from atlas.modules.platform.domain.bootstrap_state import BootstrapRunRecord, BootstrapRunState
from atlas.modules.recovery.application.ports import RecoveryRepository
from atlas.modules.recovery.domain.backup import BackupState, RestoreValidationState
from atlas.modules.upgrade.application.ports import UpgradeError, UpgradeSimulationRepository
from atlas.modules.upgrade.domain.upgrade import (
    MigrationStep,
    SimulationStep,
    SimulationStepState,
    UpgradePlanState,
    UpgradeReadinessCheck,
    UpgradeReadinessPlan,
    UpgradeSimulation,
    UpgradeSimulationState,
)

SCHEMA_VERSION = "atlas.upgrade-readiness-plan.v1"
CATALOG_VERSION = "atlas.synthetic-upgrade-catalog.v1"
SIMULATION_SCHEMA = "atlas.upgrade-rollback-simulation.v1"
SOURCE_RELEASE_ID = "release.atlas.lab-0.1.0"
SOURCE_RELEASE_VERSION = "0.1.0"
TARGET_RELEASE_ID = "release.atlas.lab-0.2.0"
TARGET_RELEASE_VERSION = "0.2.0"
SOURCE_SCHEMA = "schema.platform.v1"
TARGET_SCHEMA = "schema.platform.v2"
MIGRATIONS = (
    MigrationStep("migration.application.compatibility", 1, "application", True, False, 2),
    MigrationStep("migration.schema.expand-v2", 2, "schema_expand", True, True, 4),
    MigrationStep("migration.projection.rebuild-v2", 3, "projection_rebuild", True, False, 3),
)
SERVICE_DEPENDENCIES = ("service.atlas-api", "service.atlas-web")
ABORT_CRITERIA = (
    "abort.readiness-check-failed",
    "abort.schema-expand-failed",
    "abort.target-readiness-failed",
    "abort.verification-regressed",
)
ROLLBACK_STEPS = (
    "rollback.stop-target-routing",
    "rollback.restore-source-application",
    "rollback.reconcile-expand-schema",
    "rollback.verify-source-release",
)
POST_VERIFY = (
    "verify.api-readiness",
    "verify.web-readiness",
    "verify.authentication",
    "verify.authorization",
    "verify.audit-write",
    "verify.logical-data-consistency",
)
READINESS_CHECKS = (
    ("upgrade.check.source-complete", "category.source", "upgrade.source.completed"),
    ("upgrade.check.target-known", "category.target", "upgrade.target.known"),
    ("upgrade.check.target-signed", "category.target", "upgrade.target.signature-valid"),
    ("upgrade.check.profile-compatible", "category.compatibility", "upgrade.profile.compatible"),
    ("upgrade.check.configuration-bound", "category.configuration", "upgrade.configuration.bound"),
    ("upgrade.check.schema-compatible", "category.migration", "upgrade.schema.expand-compatible"),
    ("upgrade.check.backup-current", "category.recovery", "upgrade.backup.current"),
    ("upgrade.check.restore-validated", "category.recovery", "upgrade.restore.validated"),
    ("upgrade.check.rollback-artifacts", "category.rollback", "upgrade.rollback.artifacts-ready"),
    ("upgrade.check.rollback-window", "category.rollback", "upgrade.rollback.window-declared"),
    ("upgrade.check.abort-criteria", "category.safety", "upgrade.abort.criteria-declared"),
    ("upgrade.check.post-verification", "category.verification", "upgrade.verification.declared"),
)


class UpgradeService:
    def __init__(
        self,
        *,
        bootstrap_repository: BootstrapStateRepository,
        recovery_repository: RecoveryRepository,
        simulation_repository: UpgradeSimulationRepository,
        audit_sink: AuditSink,
        environment_id: str,
        site_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._bootstrap_repository = bootstrap_repository
        self._recovery_repository = recovery_repository
        self._simulation_repository = simulation_repository
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._site_id = site_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def close(self) -> None:
        await self._simulation_repository.close()

    async def preview(
        self,
        *,
        actor: AuthenticatedSubject,
        source_run_id: str,
        backup_id: str,
        restore_validation_id: str,
        target_release_id: str,
    ) -> UpgradeReadinessPlan:
        if target_release_id != TARGET_RELEASE_ID:
            raise UpgradeError("upgrade_target_unsupported")
        run = await self._source_run(actor, source_run_id)
        if run.identity.release_id != SOURCE_RELEASE_ID:
            raise UpgradeError("upgrade_source_unsupported")
        backup = await self._recovery_repository.get_backup_by_id(
            actor_id=actor.subject_id, backup_id=backup_id
        )
        validation = await self._recovery_repository.get_validation_by_id(
            actor_id=actor.subject_id, validation_id=restore_validation_id
        )
        now = self._clock()
        if (
            backup is None
            or backup.state is not BackupState.COMPLETED
            or backup.source_run_id != run.run_id
            or backup.source_run_version != run.version
            or backup.expires_at <= now
        ):
            raise UpgradeError("upgrade_backup_evidence_invalid")
        if (
            validation is None
            or validation.state is not RestoreValidationState.PASSED
            or validation.backup_id != backup.backup_id
            or validation.archive_sha256 != backup.archive_sha256
            or validation.validated_at < now - timedelta(hours=24)
            or validation.validated_at > now
        ):
            raise UpgradeError("upgrade_restore_evidence_invalid")
        target_manifest_digest = self._digest(
            {
                "release_id": TARGET_RELEASE_ID,
                "release_version": TARGET_RELEASE_VERSION,
                "configuration_schema": "schema.configuration.v2",
                "platform_schema": TARGET_SCHEMA,
                "supported_sources": (SOURCE_RELEASE_VERSION,),
                "migration_ids": tuple(item.step_id for item in MIGRATIONS),
                "signature_verified": True,
            }
        )
        source_evidence_digest = self._source_digest(
            run, backup.archive_sha256, validation.validation_digest
        )
        checks = tuple(
            UpgradeReadinessCheck(check_id, category_id, result_code, True, True)
            for check_id, category_id, result_code in READINESS_CHECKS
        )
        digest_payload = {
            "schema_version": SCHEMA_VERSION,
            "catalog_version": CATALOG_VERSION,
            "organization_id": actor.organization_id,
            "environment_id": self._environment_id,
            "site_id": self._site_id,
            "source_run_id": run.run_id,
            "source_run_version": run.version,
            "source_release_id": SOURCE_RELEASE_ID,
            "target_release_id": TARGET_RELEASE_ID,
            "source_configuration_digest": run.identity.configuration_digest,
            "source_schema_version": SOURCE_SCHEMA,
            "target_schema_version": TARGET_SCHEMA,
            "target_manifest_digest": target_manifest_digest,
            "backup_id": backup.backup_id,
            "backup_archive_sha256": backup.archive_sha256,
            "restore_validation_id": validation.validation_id,
            "restore_validation_digest": validation.validation_digest,
            "source_evidence_digest": source_evidence_digest,
            "migrations": tuple(
                (
                    item.step_id,
                    item.sequence,
                    item.migration_kind,
                    item.reversible,
                    item.requires_quiescence,
                    item.estimated_minutes,
                )
                for item in MIGRATIONS
            ),
            "service_dependencies": SERVICE_DEPENDENCIES,
            "abort_criteria": ABORT_CRITERIA,
            "rollback_steps": ROLLBACK_STEPS,
            "post_verification": POST_VERIFY,
            "readiness_checks": tuple(item.check_id for item in checks),
            "downtime": (6, 12),
            "rollback_window_minutes": 60,
        }
        plan_digest = self._digest(digest_payload)
        return UpgradeReadinessPlan(
            plan_id=f"upgrade-plan.{plan_digest[:24]}",
            schema_version=SCHEMA_VERSION,
            catalog_version=CATALOG_VERSION,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
            source_run_id=run.run_id,
            source_run_version=run.version,
            source_release_id=SOURCE_RELEASE_ID,
            source_release_version=SOURCE_RELEASE_VERSION,
            target_release_id=TARGET_RELEASE_ID,
            target_release_version=TARGET_RELEASE_VERSION,
            profile=run.identity.profile.value,
            source_configuration_digest=run.identity.configuration_digest,
            source_schema_version=SOURCE_SCHEMA,
            target_schema_version=TARGET_SCHEMA,
            target_manifest_digest=target_manifest_digest,
            backup_id=backup.backup_id,
            backup_archive_sha256=backup.archive_sha256,
            restore_validation_id=validation.validation_id,
            restore_validation_digest=validation.validation_digest,
            source_evidence_digest=source_evidence_digest,
            migration_steps=MIGRATIONS,
            service_dependency_ids=SERVICE_DEPENDENCIES,
            abort_criterion_ids=ABORT_CRITERIA,
            rollback_step_ids=ROLLBACK_STEPS,
            post_verification_check_ids=POST_VERIFY,
            readiness_checks=checks,
            estimated_downtime_min_minutes=6,
            estimated_downtime_max_minutes=12,
            rollback_window_minutes=60,
            rollback_supported=True,
            forward_recovery_required_after_step_id=None,
            state=UpgradePlanState.READY,
            plan_digest=plan_digest,
            generated_at=now,
            expires_at=now + timedelta(hours=1),
        )

    async def simulate(
        self,
        *,
        actor: AuthenticatedSubject,
        source_run_id: str,
        source_run_version: int,
        backup_id: str,
        restore_validation_id: str,
        target_release_id: str,
        plan_id: str,
        plan_digest: str,
        source_evidence_digest: str,
        justification: str,
        confirmed_isolated: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> UpgradeSimulation:
        if not confirmed_isolated or not 12 <= len(justification.strip()) <= 500:
            raise UpgradeError("upgrade_simulation_confirmation_required")
        fingerprint = self._digest(
            {
                "source_run_id": source_run_id,
                "source_run_version": source_run_version,
                "backup_id": backup_id,
                "restore_validation_id": restore_validation_id,
                "target_release_id": target_release_id,
                "plan_id": plan_id,
                "plan_digest": plan_digest,
                "source_evidence_digest": source_evidence_digest,
                "justification": justification.strip(),
                "confirmed_isolated": confirmed_isolated,
            }
        )
        prior = await self._simulation_repository.get(
            actor_id=actor.subject_id, idempotency_key=idempotency_key
        )
        if prior is not None:
            if prior.request_fingerprint != fingerprint:
                raise UpgradeError("upgrade_simulation_idempotency_conflict")
            return replace(prior, reused=True)
        plan = await self.preview(
            actor=actor,
            source_run_id=source_run_id,
            backup_id=backup_id,
            restore_validation_id=restore_validation_id,
            target_release_id=target_release_id,
        )
        if (
            plan.source_run_version != source_run_version
            or plan.plan_id != plan_id
            or plan.plan_digest != plan_digest
            or plan.source_evidence_digest != source_evidence_digest
        ):
            raise UpgradeError("upgrade_readiness_plan_stale")
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            result_code="upgrade_rollback_simulation_authorized",
            metadata=(("plan_digest", plan_digest),),
        )
        step_specs = (
            ("simulation.preflight", "simulation.preflight.passed", True, 0),
            ("simulation.quiesce-services", "simulation.quiescence.modeled", True, 2),
            ("simulation.schema-expand", "simulation.schema-expand.modeled", True, 4),
            ("simulation.deploy-target", "simulation.abort.injected", True, 1),
            ("simulation.stop-target-routing", "simulation.target-routing.stopped", True, 0),
            ("simulation.restore-source-application", "simulation.source-restored", True, 2),
            ("simulation.reconcile-schema", "simulation.schema-reconciled", True, 1),
            ("simulation.verify-source", "simulation.source-verification.passed", False, 1),
        )
        steps = tuple(
            SimulationStep(
                step_id,
                index,
                SimulationStepState.SIMULATED,
                result_code,
                rollback_applicable,
                minutes,
            )
            for index, (step_id, result_code, rollback_applicable, minutes) in enumerate(
                step_specs, start=1
            )
        )
        simulation_digest = self._digest(
            {
                "plan_digest": plan.plan_digest,
                "source_evidence_digest": plan.source_evidence_digest,
                "steps": tuple(
                    (item.step_id, item.result_code, item.simulated_minutes) for item in steps
                ),
                "impacted_services": SERVICE_DEPENDENCIES,
                "post_verification": POST_VERIFY,
                "abort_injected_at": "simulation.deploy-target",
                "rollback_decision": "rollback.decision.applicable",
                "estimated_downtime_minutes": 10,
                "isolated_target": True,
            }
        )
        simulation_key = f"{actor.subject_id}:{idempotency_key}:{fingerprint}"
        record = UpgradeSimulation(
            simulation_id=f"upgrade-simulation.{sha256(simulation_key.encode()).hexdigest()[:24]}",
            schema_version=SIMULATION_SCHEMA,
            state=UpgradeSimulationState.PASSED,
            actor_id=actor.subject_id,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
            source_run_id=source_run_id,
            source_run_version=source_run_version,
            plan_id=plan_id,
            plan_digest=plan_digest,
            backup_id=backup_id,
            restore_validation_id=restore_validation_id,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            steps=steps,
            impacted_service_ids=SERVICE_DEPENDENCIES,
            post_verification_check_ids=POST_VERIFY,
            abort_injected_at_step_id="simulation.deploy-target",
            rollback_decision="rollback.decision.applicable",
            estimated_downtime_minutes=10,
            simulation_digest=simulation_digest,
            created_at=self._clock(),
        )
        if not await self._simulation_repository.add(record):
            raced = await self._simulation_repository.get(
                actor_id=actor.subject_id, idempotency_key=idempotency_key
            )
            if raced is None or raced.request_fingerprint != fingerprint:
                raise UpgradeError("upgrade_simulation_idempotency_conflict")
            return replace(raced, reused=True)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            result_code="upgrade_rollback_simulation_completed",
            metadata=(
                ("simulation_id", record.simulation_id),
                ("simulation_digest", simulation_digest),
            ),
        )
        return record

    async def _source_run(
        self, actor: AuthenticatedSubject, source_run_id: str
    ) -> BootstrapRunRecord:
        run = await self._bootstrap_repository.get_current(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
        )
        if (
            run is None
            or run.run_id != source_run_id
            or run.state is not BootstrapRunState.COMPLETED
            or run.operational_handoff is None
            or run.end_to_end_verification is None
        ):
            raise UpgradeError("upgrade_source_unavailable")
        return run

    @staticmethod
    def _source_digest(run: BootstrapRunRecord, backup_digest: str, validation_digest: str) -> str:
        handoff = run.operational_handoff
        assert handoff is not None
        return UpgradeService._digest(
            {
                "run_id": run.run_id,
                "version": run.version,
                "release_id": run.identity.release_id,
                "configuration_digest": run.identity.configuration_digest,
                "handoff_report_digest": handoff.evidence[0].sha256,
                "backup_archive_sha256": backup_digest,
                "restore_validation_digest": validation_digest,
            }
        )

    @staticmethod
    def _digest(payload: object) -> str:
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        idempotency_key: str,
        result_code: str,
        metadata: tuple[tuple[str, str], ...],
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.upgrade.simulation",
                schema_version="1.0",
                producer="atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id="platform.upgrade.simulate",
                resource_type="resource.platform.upgrade-simulation",
                scope_reference=(
                    f"{actor.organization_id}/{self._environment_id}/{self._site_id}/"
                    "domain.platform/resource.platform.upgrade-simulation/C2"
                ),
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=metadata,
            )
        )
