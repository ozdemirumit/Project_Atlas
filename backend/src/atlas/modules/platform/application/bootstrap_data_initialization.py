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
from atlas.modules.platform.application.bootstrap_data_ports import (
    BootstrapDataCatalog,
    BootstrapDataError,
    BootstrapDataTarget,
)
from atlas.modules.platform.application.bootstrap_state_ports import BootstrapStateRepository
from atlas.modules.platform.application.bootstrap_trust_provisioning import (
    BootstrapTrustPlanService,
)
from atlas.modules.platform.application.deployment_configuration import (
    DeploymentConfigurationService,
)
from atlas.modules.platform.domain.bootstrap_data_initialization import (
    BackupApplicability,
    BootstrapDataPlan,
    BootstrapMigrationSpec,
    DataInitializationExecution,
    DataInitializationState,
    DataPlanState,
    DataTargetState,
)
from atlas.modules.platform.domain.bootstrap_state import (
    BootstrapMutationResult,
    BootstrapRunRecord,
)
from atlas.modules.platform.domain.bootstrap_trust_provisioning import TrustProvisioningState
from atlas.modules.platform.domain.deployment_configuration import (
    ConfigurationState,
    DeploymentConfigurationOverlay,
    DeploymentConfigurationRequest,
)
from atlas.modules.platform.domain.release_preflight import SHA256_PATTERN, DeploymentProfile


class BootstrapDataPlanService:
    def __init__(
        self,
        *,
        catalog: BootstrapDataCatalog,
        target: BootstrapDataTarget,
        configuration_service: DeploymentConfigurationService,
        trust_plan_service: BootstrapTrustPlanService,
        environment_id: str,
        site_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._catalog = catalog
        self._target = target
        self._configuration_service = configuration_service
        self._trust_plan_service = trust_plan_service
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
    ) -> BootstrapDataPlan:
        if (
            organization_id != actor.organization_id
            or environment_id != self._environment_id
            or site_id != self._site_id
        ):
            raise BootstrapDataError("bootstrap_data_plan_unavailable")
        try:
            configuration = self._configuration_service.prepare(
                DeploymentConfigurationRequest(
                    schema_version="atlas.deployment-configuration-request.v1",
                    release_id=release_id,
                    profile=profile,
                    organization_id=organization_id,
                    environment_id=environment_id,
                    site_id=site_id,
                    overlay=overlay,
                )
            )
            if configuration.state is ConfigurationState.FAILED:
                raise BootstrapDataError("bootstrap_configuration_validation_failed")
            if configuration.configuration_digest != configuration_digest:
                raise BootstrapDataError("bootstrap_configuration_digest_mismatch")
            trust_plan = self._trust_plan_service.prepare(
                actor=actor,
                release_id=release_id,
                profile=profile,
                organization_id=organization_id,
                environment_id=environment_id,
                site_id=site_id,
                configuration_digest=configuration_digest,
                overlay=overlay,
            )
            if trust_plan.trust_plan_digest != trust_plan_digest:
                raise BootstrapDataError("bootstrap_trust_plan_digest_mismatch")
            target_id, target_kind, migration_artifact_digest, migrations = self._catalog.load(
                profile=profile, environment_id=environment_id
            )
            if not SHA256_PATTERN.fullmatch(migration_artifact_digest):
                raise ValueError("migration artifact digest is invalid")
            self._validate_catalog(migrations)
        except BootstrapDataError:
            raise
        except ValueError as error:
            raise BootstrapDataError("bootstrap_data_plan_invalid") from error
        payload = self._plan_payload(
            release_id=release_id,
            profile=profile,
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
            configuration_digest=configuration_digest,
            trust_plan_digest=trust_plan_digest,
            migration_artifact_digest=migration_artifact_digest,
            target_id=target_id,
            target_kind=target_kind,
            migrations=migrations,
        )
        digest = sha256(self._canonical_json(payload)).hexdigest()
        plan = BootstrapDataPlan(
            schema_version="atlas.bootstrap-data-plan.v1",
            release_id=release_id,
            profile=profile,
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
            configuration_digest=configuration_digest,
            trust_plan_digest=trust_plan_digest,
            migration_artifact_digest=migration_artifact_digest,
            data_plan_digest=digest,
            target_id=target_id,
            target_kind=target_kind,
            current_revision=migrations[0].from_revision,
            target_revision=migrations[-1].to_revision,
            target_state=DataTargetState.EMPTY,
            state=DataPlanState.PASSED,
            result_code="bootstrap.data-plan.passed",
            migrations=migrations,
            backup_applicability=BackupApplicability.NOT_APPLICABLE_CLEAN_INSTALL,
            generated_at=self._clock(),
        )
        target_state = await self._target.inspect(plan=plan)
        return replace(plan, target_state=target_state)

    @classmethod
    def render(cls, plan: BootstrapDataPlan) -> bytes:
        return cls._canonical_json(
            {
                "schema_version": "atlas.synthetic-schema-state.v1",
                "release_id": plan.release_id,
                "profile": plan.profile.value,
                "organization_id": plan.organization_id,
                "environment_id": plan.environment_id,
                "site_id": plan.site_id,
                "configuration_digest": plan.configuration_digest,
                "trust_plan_digest": plan.trust_plan_digest,
                "migration_artifact_digest": plan.migration_artifact_digest,
                "data_plan_digest": plan.data_plan_digest,
                "target_id": plan.target_id,
                "target_kind": plan.target_kind,
                "schema_revision": plan.target_revision,
                "owner_id": "owner.project-atlas",
                "backup_applicability": plan.backup_applicability.value,
                "migrations": [cls._migration_payload(item) for item in plan.migrations],
                "verified_object_count": sum(
                    item.expected_object_count for item in plan.migrations
                ),
            }
        )

    @staticmethod
    def _validate_catalog(migrations: tuple[BootstrapMigrationSpec, ...]) -> None:
        if not 1 <= len(migrations) <= 64:
            raise ValueError("migration catalog is outside platform bounds")
        expected_sequence = 1
        expected_revision = "schema.none"
        ids: set[str] = set()
        checksums: set[str] = set()
        for migration in migrations:
            if (
                migration.sequence != expected_sequence
                or migration.from_revision != expected_revision
                or migration.migration_id in ids
                or migration.sha256 in checksums
                or migration.destructive
                or not migration.reversible
            ):
                raise ValueError("migration catalog is unsafe")
            ids.add(migration.migration_id)
            checksums.add(migration.sha256)
            expected_sequence += 1
            expected_revision = migration.to_revision

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
        migration_artifact_digest: str,
        target_id: str,
        target_kind: str,
        migrations: tuple[BootstrapMigrationSpec, ...],
    ) -> dict[str, object]:
        return {
            "schema_version": "atlas.bootstrap-data-plan.v1",
            "release_id": release_id,
            "profile": profile.value,
            "organization_id": organization_id,
            "environment_id": environment_id,
            "site_id": site_id,
            "configuration_digest": configuration_digest,
            "trust_plan_digest": trust_plan_digest,
            "migration_artifact_digest": migration_artifact_digest,
            "target_id": target_id,
            "target_kind": target_kind,
            "migrations": [cls._migration_payload(item) for item in migrations],
            "backup_applicability": BackupApplicability.NOT_APPLICABLE_CLEAN_INSTALL.value,
        }

    @staticmethod
    def _migration_payload(item: BootstrapMigrationSpec) -> dict[str, object]:
        return {
            "migration_id": item.migration_id,
            "sequence": item.sequence,
            "sha256": item.sha256,
            "from_revision": item.from_revision,
            "to_revision": item.to_revision,
            "compatibility": item.compatibility.value,
            "reversible": item.reversible,
            "destructive": item.destructive,
            "recovery_code": item.recovery_code,
            "expected_object_count": item.expected_object_count,
        }

    @staticmethod
    def _canonical_json(payload: Mapping[str, object]) -> bytes:
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


class BootstrapDataInitializationService:
    def __init__(
        self,
        *,
        repository: BootstrapStateRepository,
        plan_service: BootstrapDataPlanService,
        target: BootstrapDataTarget,
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
        data_schema_version: str,
        data_plan_digest: str,
        migration_artifact_digest: str,
        target_id: str,
        expected_target_state: DataTargetState,
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
            raise BootstrapDataError("bootstrap_run_unavailable")
        if (
            organization_id != actor.organization_id
            or environment_id != self._environment_id
            or site_id != self._site_id
            or current.identity.organization_id != organization_id
            or current.identity.environment_id != environment_id
            or current.identity.site_id != site_id
        ):
            await self._audit_denial(actor, correlation_id)
            raise BootstrapDataError("bootstrap_run_unavailable")
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
                "data_schema_version": data_schema_version,
                "data_plan_digest": data_plan_digest,
                "migration_artifact_digest": migration_artifact_digest,
                "target_id": target_id,
                "expected_target_state": expected_target_state.value,
                "justification": justification,
            }
        )
        execution_id = self._execution_id(run_id, lease_holder_id, idempotency_key, fingerprint)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            result_code="bootstrap_data_execution_authorized",
            run_id=run_id,
            idempotency_key=idempotency_key,
            metadata=(("execution_id", execution_id), ("data_plan_digest", data_plan_digest)),
        )
        prior = current.data_initialization
        if prior is not None and prior.execution_id == execution_id:
            if prior.state is not DataInitializationState.RUNNING:
                return BootstrapMutationResult(
                    record=current, replayed=True, data_initialization=prior
                )
            running = prior
            begin = BootstrapMutationResult(
                record=current, replayed=True, data_initialization=running
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
            )
            data_plan = await self._plan_service.prepare(
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
            if data_schema_version != data_plan.schema_version:
                raise BootstrapDataError("bootstrap_data_schema_mismatch")
            if (
                data_plan_digest != data_plan.data_plan_digest
                or migration_artifact_digest != data_plan.migration_artifact_digest
                or target_id != data_plan.target_id
                or expected_target_state is not data_plan.target_state
            ):
                raise BootstrapDataError("bootstrap_data_plan_digest_mismatch")
            if prior is not None and prior.state is DataInitializationState.FAILED:
                await self._target.cleanup_attempt(prior.execution_id)
            started_at = self._clock()
            running = DataInitializationExecution(
                execution_id=execution_id,
                phase_id="phase.data",
                release_id=release_id,
                profile=profile,
                configuration_digest=configuration_digest,
                trust_plan_digest=trust_plan_digest,
                data_schema_version=data_schema_version,
                data_plan_digest=data_plan_digest,
                migration_artifact_digest=migration_artifact_digest,
                target_id=target_id,
                from_revision=data_plan.current_revision,
                to_revision=data_plan.target_revision,
                state=DataInitializationState.RUNNING,
                result_code="bootstrap.data.running",
                started_at=started_at,
                completed_at=None,
                migration_count=0,
                verified_object_count=0,
                lock_acquired=True,
                backup_applicability=data_plan.backup_applicability,
                evidence=(),
            )
            begin = await self._repository.begin_data_initialization(
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
            assert begin.data_initialization is not None
            running = begin.data_initialization
            if running.state is not DataInitializationState.RUNNING:
                return begin

        data_plan = await self._plan_service.prepare(
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
        try:
            receipt = await self._target.initialize(
                execution_id=running.execution_id,
                plan=data_plan,
                state_document=self._plan_service.render(data_plan),
            )
            finished = replace(
                running,
                state=DataInitializationState.COMPLETED,
                result_code="bootstrap.data.completed",
                completed_at=self._clock(),
                migration_count=receipt.migration_count,
                verified_object_count=receipt.verified_object_count,
                evidence=receipt.evidence,
            )
        except BootstrapDataError as error:
            finished = replace(
                running,
                state=DataInitializationState.FAILED,
                result_code=error.code,
                completed_at=self._clock(),
                lock_acquired=False,
            )
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            result_code=finished.result_code,
            run_id=run_id,
            idempotency_key=idempotency_key,
            metadata=(
                ("execution_id", finished.execution_id),
                ("migration_count", str(finished.migration_count)),
                ("verified_object_count", str(finished.verified_object_count)),
            ),
        )
        return await self._repository.finish_data_initialization(
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
    ) -> None:
        if (
            current.identity.release_id != release_id
            or current.identity.profile is not profile
            or current.identity.plan_digest != plan_digest
            or current.identity.resume_key != resume_key
            or current.identity.configuration_digest != configuration_digest
        ):
            raise BootstrapDataError("bootstrap_plan_mismatch")
        trust = current.trust_provisioning
        if (
            trust is None
            or trust.state is not TrustProvisioningState.COMPLETED
            or trust.trust_plan_digest != trust_plan_digest
            or "phase.trust" not in current.completed_phase_ids
        ):
            raise BootstrapDataError("bootstrap_trust_evidence_missing")

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
                event_type="atlas.platform.bootstrap-data.execute",
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
                event_type="atlas.platform.bootstrap-data.denied",
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
