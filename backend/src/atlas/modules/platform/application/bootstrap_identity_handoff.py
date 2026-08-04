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
from atlas.modules.platform.application.bootstrap_identity_ports import (
    BootstrapIdentityCatalog,
    BootstrapIdentityError,
    BootstrapIdentityTarget,
)
from atlas.modules.platform.application.bootstrap_service_deployment import (
    BootstrapServicePlanService,
)
from atlas.modules.platform.application.bootstrap_state_ports import BootstrapStateRepository
from atlas.modules.platform.domain.bootstrap_identity_handoff import (
    BootstrapIdentityGroupMapping,
    BootstrapIdentityPlan,
    IdentityHandoffExecution,
    IdentityHandoffState,
    IdentityPlanState,
    IdentityTargetState,
)
from atlas.modules.platform.domain.bootstrap_service_deployment import ServiceDeploymentState
from atlas.modules.platform.domain.bootstrap_state import (
    BootstrapMutationResult,
    BootstrapRunRecord,
)
from atlas.modules.platform.domain.deployment_configuration import DeploymentConfigurationOverlay
from atlas.modules.platform.domain.release_preflight import DeploymentProfile


class BootstrapIdentityPlanService:
    def __init__(
        self,
        *,
        catalog: BootstrapIdentityCatalog,
        target: BootstrapIdentityTarget,
        service_plan_service: BootstrapServicePlanService,
        environment_id: str,
        site_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._catalog = catalog
        self._target = target
        self._service_plan_service = service_plan_service
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
    ) -> BootstrapIdentityPlan:
        if (
            organization_id != actor.organization_id
            or environment_id != self._environment_id
            or site_id != self._site_id
        ):
            raise BootstrapIdentityError("bootstrap_identity_plan_unavailable")
        try:
            service_plan = await self._service_plan_service.prepare(
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
            if service_plan.service_plan_digest != service_plan_digest:
                raise BootstrapIdentityError("bootstrap_service_plan_digest_mismatch")
            (
                target_id,
                target_kind,
                administrator_id,
                verifier_reference_id,
                recovery_identity_id,
                provider_id,
                pilot_subject_id,
                mappings,
            ) = self._catalog.load(profile=profile, environment_id=environment_id)
            self._validate_mappings(mappings)
        except BootstrapIdentityError:
            raise
        except ValueError as error:
            raise BootstrapIdentityError("bootstrap_identity_plan_invalid") from error
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
            target_id=target_id,
            target_kind=target_kind,
            administrator_id=administrator_id,
            verifier_reference_id=verifier_reference_id,
            recovery_identity_id=recovery_identity_id,
            provider_id=provider_id,
            pilot_subject_id=pilot_subject_id,
            mappings=mappings,
        )
        plan = BootstrapIdentityPlan(
            schema_version="atlas.bootstrap-identity-plan.v1",
            release_id=release_id,
            profile=profile,
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
            configuration_digest=configuration_digest,
            trust_plan_digest=trust_plan_digest,
            data_plan_digest=data_plan_digest,
            service_plan_digest=service_plan_digest,
            identity_plan_digest=sha256(self._canonical_json(payload)).hexdigest(),
            target_id=target_id,
            target_kind=target_kind,
            target_state=IdentityTargetState.EMPTY,
            bootstrap_administrator_subject_id=administrator_id,
            credential_verifier_reference_id=verifier_reference_id,
            credential_replacement_required=True,
            recovery_identity_id=recovery_identity_id,
            recovery_seal_required=True,
            provider_id=provider_id,
            provider_protocol="ldaps",
            pilot_subject_id=pilot_subject_id,
            group_mappings=mappings,
            state=IdentityPlanState.PASSED,
            result_code="bootstrap.identity-plan.passed",
            generated_at=self._clock(),
        )
        return replace(plan, target_state=await self._target.inspect(plan=plan))

    @classmethod
    def render(cls, plan: BootstrapIdentityPlan) -> bytes:
        return cls._canonical_json(
            {
                "schema_version": "atlas.synthetic-identity-state.v1",
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
                "target_id": plan.target_id,
                "target_kind": plan.target_kind,
                "bootstrap_administrator_subject_id": plan.bootstrap_administrator_subject_id,
                "credential_verifier_reference_id": plan.credential_verifier_reference_id,
                "credential_replacement_required": True,
                "recovery_identity_id": plan.recovery_identity_id,
                "recovery_identity_verified": True,
                "bootstrap_material_sealed": True,
                "provider_id": plan.provider_id,
                "provider_protocol": plan.provider_protocol,
                "pilot_subject_id": plan.pilot_subject_id,
                "pilot_identity_verified": True,
                "enterprise_authentication_validated": True,
                "group_mappings": [cls._mapping_payload(item) for item in plan.group_mappings],
                "credential_material_present": False,
                "directory_mutation_performed": False,
                "provider_activation_performed": False,
            }
        )

    @staticmethod
    def _validate_mappings(mappings: tuple[BootstrapIdentityGroupMapping, ...]) -> None:
        if not 1 <= len(mappings) <= 8:
            raise ValueError("identity mapping catalog is outside platform bounds")
        if len({item.mapping_id for item in mappings}) != len(mappings) or len(
            {item.directory_group_reference for item in mappings}
        ) != len(mappings):
            raise ValueError("identity mapping catalog contains duplicates")

    @classmethod
    def _plan_payload(cls, **values: object) -> dict[str, object]:
        mappings = cast(tuple[BootstrapIdentityGroupMapping, ...], values.pop("mappings"))
        profile = cast(DeploymentProfile, values["profile"])
        return {
            "schema_version": "atlas.bootstrap-identity-plan.v1",
            **values,
            "profile": profile.value,
            "provider_protocol": "ldaps",
            "credential_replacement_required": True,
            "recovery_seal_required": True,
            "group_mappings": [cls._mapping_payload(item) for item in mappings],
            "credential_material_authorized": False,
            "directory_mutation_authorized": False,
            "provider_activation_authorized": False,
        }

    @staticmethod
    def _mapping_payload(item: BootstrapIdentityGroupMapping) -> dict[str, object]:
        return {
            "mapping_id": item.mapping_id,
            "directory_group_reference": item.directory_group_reference,
            "role_ids": item.role_ids,
        }

    @staticmethod
    def _canonical_json(payload: Mapping[str, object]) -> bytes:
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


class BootstrapIdentityHandoffService:
    def __init__(
        self,
        *,
        repository: BootstrapStateRepository,
        plan_service: BootstrapIdentityPlanService,
        target: BootstrapIdentityTarget,
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
        identity_schema_version: str,
        identity_plan_digest: str,
        target_id: str,
        expected_target_state: IdentityTargetState,
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
            raise BootstrapIdentityError("bootstrap_run_unavailable")
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
                "identity_schema_version": identity_schema_version,
                "identity_plan_digest": identity_plan_digest,
                "target_id": target_id,
                "expected_target_state": expected_target_state.value,
                "justification": justification,
            }
        )
        execution_id = self._execution_id(run_id, lease_holder_id, idempotency_key, fingerprint)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            result_code="bootstrap_identity_execution_authorized",
            run_id=run_id,
            idempotency_key=idempotency_key,
            metadata=(
                ("execution_id", execution_id),
                ("identity_plan_digest", identity_plan_digest),
            ),
        )
        prior = current.identity_handoff
        if prior is not None and prior.execution_id == execution_id:
            if prior.state is not IdentityHandoffState.RUNNING:
                return BootstrapMutationResult(
                    record=current, replayed=True, identity_handoff=prior
                )
            running = prior
            begin = BootstrapMutationResult(record=current, replayed=True, identity_handoff=running)
        else:
            self._validate_run(
                current=current,
                release_id=release_id,
                profile=profile,
                plan_digest=plan_digest,
                resume_key=resume_key,
                configuration_digest=configuration_digest,
                service_plan_digest=service_plan_digest,
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
            )
            if (
                identity_schema_version != plan.schema_version
                or identity_plan_digest != plan.identity_plan_digest
                or target_id != plan.target_id
                or expected_target_state is not plan.target_state
            ):
                raise BootstrapIdentityError("bootstrap_identity_plan_digest_mismatch")
            if prior is not None and prior.state is IdentityHandoffState.FAILED:
                await self._target.cleanup_attempt(prior.execution_id)
            running = IdentityHandoffExecution(
                execution_id=execution_id,
                phase_id="phase.identity",
                release_id=release_id,
                profile=profile,
                configuration_digest=configuration_digest,
                trust_plan_digest=trust_plan_digest,
                data_plan_digest=data_plan_digest,
                service_plan_digest=service_plan_digest,
                identity_schema_version=identity_schema_version,
                identity_plan_digest=identity_plan_digest,
                target_id=target_id,
                state=IdentityHandoffState.RUNNING,
                result_code="bootstrap.identity.running",
                started_at=self._clock(),
                completed_at=None,
                group_mapping_count=0,
                validation_count=0,
                credential_replacement_required=False,
                recovery_identity_verified=False,
                bootstrap_material_sealed=False,
                pilot_identity_verified=False,
                enterprise_authentication_validated=False,
                evidence=(),
            )
            begin = await self._repository.begin_identity_handoff(
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
        )
        try:
            receipt = await self._target.publish(
                execution_id=running.execution_id,
                plan=plan,
                state_document=self._plan_service.render(plan),
            )
            finished = replace(
                running,
                state=IdentityHandoffState.COMPLETED,
                result_code="bootstrap.identity.completed",
                completed_at=self._clock(),
                group_mapping_count=receipt.group_mapping_count,
                validation_count=receipt.validation_count,
                credential_replacement_required=True,
                recovery_identity_verified=True,
                bootstrap_material_sealed=True,
                pilot_identity_verified=True,
                enterprise_authentication_validated=True,
                evidence=receipt.evidence,
            )
        except BootstrapIdentityError as error:
            finished = replace(
                running,
                state=IdentityHandoffState.FAILED,
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
                ("identity_plan_digest", identity_plan_digest),
            ),
        )
        return await self._repository.finish_identity_handoff(
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
        service_plan_digest: str,
    ) -> None:
        if (
            current.identity.release_id != release_id
            or current.identity.profile is not profile
            or current.identity.plan_digest != plan_digest
            or current.identity.resume_key != resume_key
            or current.identity.configuration_digest != configuration_digest
            or current.current_phase_id != "phase.identity"
        ):
            raise BootstrapIdentityError("bootstrap_plan_mismatch")
        services = current.service_deployment
        if (
            services is None
            or services.state is not ServiceDeploymentState.COMPLETED
            or services.service_plan_digest != service_plan_digest
            or services.ready_service_count != services.deployed_service_count
            or services.passed_probe_count != services.ready_service_count * 3
            or "phase.services" not in current.completed_phase_ids
        ):
            raise BootstrapIdentityError("bootstrap_service_evidence_missing")

    @staticmethod
    def _execution_id(
        run_id: str, lease_holder_id: str, idempotency_key: str, fingerprint: str
    ) -> str:
        digest = sha256(
            f"{run_id}:{lease_holder_id}:{idempotency_key}:{fingerprint}".encode()
        ).hexdigest()[:24]
        return f"phase-execution.{digest}"

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
                event_type="atlas.platform.bootstrap-identity.execute",
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
                event_type="atlas.platform.bootstrap-identity.denied",
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
