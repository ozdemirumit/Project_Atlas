from __future__ import annotations

import json
import ssl
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.platform.application.bootstrap_state_ports import BootstrapStateRepository
from atlas.modules.platform.application.bootstrap_trust_ports import (
    BootstrapTrustError,
    BootstrapTrustPublisher,
    BootstrapTrustSource,
)
from atlas.modules.platform.application.deployment_configuration import (
    DeploymentConfigurationService,
)
from atlas.modules.platform.domain.bootstrap_configuration_rendering import (
    ConfigurationRenderingState,
)
from atlas.modules.platform.domain.bootstrap_state import (
    BootstrapMutationResult,
    BootstrapRunRecord,
)
from atlas.modules.platform.domain.bootstrap_trust_provisioning import (
    BootstrapTrustPlan,
    BootstrapWorkloadIdentitySpec,
    TrustAnchorSpec,
    TrustPlanState,
    TrustProvisioningExecution,
    TrustProvisioningState,
)
from atlas.modules.platform.domain.deployment_configuration import (
    ConfigurationState,
    DeploymentConfigurationOverlay,
    DeploymentConfigurationRequest,
)
from atlas.modules.platform.domain.release_preflight import DeploymentProfile


class BootstrapTrustPlanService:
    def __init__(
        self,
        *,
        source: BootstrapTrustSource,
        configuration_service: DeploymentConfigurationService,
        environment_id: str,
        site_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._source = source
        self._configuration_service = configuration_service
        self._environment_id = environment_id
        self._site_id = site_id
        self._clock = clock or (lambda: datetime.now(UTC))

    def prepare(
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
    ) -> BootstrapTrustPlan:
        now = self._clock()
        if (
            organization_id != actor.organization_id
            or environment_id != self._environment_id
            or site_id != self._site_id
        ):
            raise BootstrapTrustError("bootstrap_trust_plan_unavailable")
        try:
            prepared_configuration = self._configuration_service.prepare(
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
            if prepared_configuration.state is ConfigurationState.FAILED:
                raise BootstrapTrustError("bootstrap_configuration_validation_failed")
            if prepared_configuration.configuration_digest != configuration_digest:
                raise BootstrapTrustError("bootstrap_configuration_digest_mismatch")
            anchors, identities = self._source.load(
                profile=profile,
                environment_id=environment_id,
            )
            ordered_anchors = tuple(sorted(anchors, key=lambda item: item.anchor_id))
            ordered_identities = tuple(sorted(identities, key=lambda item: item.identity_id))
            self._validate_material(
                ordered_anchors, ordered_identities, profile, environment_id, now
            )
        except BootstrapTrustError:
            raise
        except (ValueError, ssl.SSLError) as error:
            raise BootstrapTrustError("bootstrap_trust_plan_invalid") from error
        payload = self._plan_payload(
            release_id=release_id,
            profile=profile,
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
            configuration_digest=configuration_digest,
            anchors=ordered_anchors,
            identities=ordered_identities,
        )
        digest = sha256(self._canonical_json(payload)).hexdigest()
        return BootstrapTrustPlan(
            schema_version="atlas.bootstrap-trust-plan.v1",
            release_id=release_id,
            profile=profile,
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
            configuration_digest=configuration_digest,
            trust_plan_digest=digest,
            state=TrustPlanState.PASSED,
            result_code="bootstrap.trust-plan.passed",
            anchors=ordered_anchors,
            workload_identities=ordered_identities,
            generated_at=now,
        )

    @classmethod
    def render(cls, plan: BootstrapTrustPlan) -> tuple[bytes, bytes]:
        trust_bundle = "".join(item.certificate_pem for item in plan.anchors).encode("ascii")
        catalog: dict[str, object] = {
            "schema_version": "atlas.bootstrap-workload-identity-catalog.v1",
            "release_id": plan.release_id,
            "profile": plan.profile.value,
            "organization_id": plan.organization_id,
            "environment_id": plan.environment_id,
            "site_id": plan.site_id,
            "configuration_digest": plan.configuration_digest,
            "trust_plan_digest": plan.trust_plan_digest,
            "trust_anchors": [
                {
                    "anchor_id": item.anchor_id,
                    "source_id": item.source_id,
                    "purpose": item.purpose.value,
                    "sha256": item.sha256,
                    "not_before": item.not_before.isoformat(),
                    "not_after": item.not_after.isoformat(),
                    "non_production_only": item.non_production_only,
                }
                for item in plan.anchors
            ],
            "workload_identities": [
                cls._identity_payload(item) for item in plan.workload_identities
            ],
        }
        return trust_bundle, cls._canonical_json(catalog)

    @staticmethod
    def _validate_material(
        anchors: tuple[TrustAnchorSpec, ...],
        identities: tuple[BootstrapWorkloadIdentitySpec, ...],
        profile: DeploymentProfile,
        environment_id: str,
        now: datetime,
    ) -> None:
        anchor_ids: set[str] = set()
        fingerprints: set[str] = set()
        for anchor in anchors:
            if anchor.anchor_id in anchor_ids or anchor.sha256 in fingerprints:
                raise ValueError("duplicate trust anchor")
            if not anchor.not_before <= now < anchor.not_after:
                raise ValueError("trust anchor is outside its validity period")
            if anchor.non_production_only and profile not in {
                DeploymentProfile.DEVELOPER,
                DeploymentProfile.LINUX_LAB,
            }:
                raise ValueError("non-production trust is not allowed for this profile")
            der = ssl.PEM_cert_to_DER_cert(anchor.certificate_pem)
            if sha256(der).hexdigest() != anchor.sha256:
                raise ValueError("trust anchor fingerprint mismatch")
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.load_verify_locations(cadata=anchor.certificate_pem)
            anchor_ids.add(anchor.anchor_id)
            fingerprints.add(anchor.sha256)
        identity_ids: set[str] = set()
        service_instances: set[tuple[str, str]] = set()
        for identity in identities:
            key = (identity.service_id, identity.instance_id)
            if identity.identity_id in identity_ids or key in service_instances:
                raise ValueError("duplicate workload identity")
            if identity.environment_id != environment_id:
                raise ValueError("workload identity environment mismatch")
            if (
                identity.identity_id.startswith("human.")
                or "autonomous" in identity.purpose.casefold()
            ):
                raise ValueError("workload identity authority is unsafe")
            identity_ids.add(identity.identity_id)
            service_instances.add(key)

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
        anchors: tuple[TrustAnchorSpec, ...],
        identities: tuple[BootstrapWorkloadIdentitySpec, ...],
    ) -> dict[str, object]:
        return {
            "schema_version": "atlas.bootstrap-trust-plan.v1",
            "release_id": release_id,
            "profile": profile.value,
            "organization_id": organization_id,
            "environment_id": environment_id,
            "site_id": site_id,
            "configuration_digest": configuration_digest,
            "anchors": [
                {
                    "anchor_id": item.anchor_id,
                    "source_id": item.source_id,
                    "purpose": item.purpose.value,
                    "subject_summary": item.subject_summary,
                    "sha256": item.sha256,
                    "not_before": item.not_before.isoformat(),
                    "not_after": item.not_after.isoformat(),
                    "non_production_only": item.non_production_only,
                }
                for item in anchors
            ],
            "workload_identities": [cls._identity_payload(item) for item in identities],
        }

    @staticmethod
    def _identity_payload(item: BootstrapWorkloadIdentitySpec) -> dict[str, object]:
        return {
            "identity_id": item.identity_id,
            "service_id": item.service_id,
            "instance_id": item.instance_id,
            "owner_subject_id": item.owner_subject_id,
            "purpose": item.purpose,
            "environment_id": item.environment_id,
            "audiences": item.audiences,
            "secret_reference_ids": item.secret_reference_ids,
        }

    @staticmethod
    def _canonical_json(payload: Mapping[str, object]) -> bytes:
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


class BootstrapTrustProvisioningService:
    def __init__(
        self,
        *,
        repository: BootstrapStateRepository,
        plan_service: BootstrapTrustPlanService,
        publisher: BootstrapTrustPublisher,
        audit_sink: AuditSink,
        environment_id: str,
        site_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._plan_service = plan_service
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
        configuration_digest: str,
        overlay: DeploymentConfigurationOverlay,
        trust_schema_version: str,
        trust_plan_digest: str,
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
            raise BootstrapTrustError("bootstrap_run_unavailable")
        if (
            organization_id != actor.organization_id
            or environment_id != self._environment_id
            or site_id != self._site_id
            or current.identity.organization_id != organization_id
            or current.identity.environment_id != environment_id
            or current.identity.site_id != site_id
        ):
            await self._audit_denial(actor, correlation_id)
            raise BootstrapTrustError("bootstrap_run_unavailable")
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
                "trust_schema_version": trust_schema_version,
                "trust_plan_digest": trust_plan_digest,
                "justification": justification,
            }
        )
        execution_id = self._execution_id(run_id, lease_holder_id, idempotency_key, fingerprint)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            result_code="bootstrap_trust_execution_authorized",
            run_id=run_id,
            idempotency_key=idempotency_key,
            metadata=(
                ("execution_id", execution_id),
                ("trust_plan_digest", trust_plan_digest),
                ("justification_digest", self._fingerprint({"justification": justification})),
            ),
        )
        prior = current.trust_provisioning
        if prior is not None and prior.execution_id == execution_id:
            if prior.state is not TrustProvisioningState.RUNNING:
                return BootstrapMutationResult(
                    record=current, replayed=True, trust_provisioning=prior
                )
            running = prior
            begin = BootstrapMutationResult(
                record=current, replayed=True, trust_provisioning=running
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
            trust_plan = self._plan_service.prepare(
                actor=actor,
                release_id=release_id,
                profile=profile,
                organization_id=organization_id,
                environment_id=environment_id,
                site_id=site_id,
                configuration_digest=configuration_digest,
                overlay=overlay,
            )
            if trust_schema_version != trust_plan.schema_version:
                raise BootstrapTrustError("bootstrap_trust_schema_mismatch")
            if trust_plan_digest != trust_plan.trust_plan_digest:
                raise BootstrapTrustError("bootstrap_trust_plan_digest_mismatch")
            if prior is not None and prior.state is TrustProvisioningState.FAILED:
                await self._publisher.cleanup_attempt(prior.execution_id)
            started_at = self._clock()
            running = TrustProvisioningExecution(
                execution_id=execution_id,
                phase_id="phase.trust",
                release_id=release_id,
                profile=profile,
                configuration_digest=configuration_digest,
                trust_schema_version=trust_schema_version,
                trust_plan_digest=trust_plan_digest,
                state=TrustProvisioningState.RUNNING,
                result_code="bootstrap.trust.running",
                started_at=started_at,
                completed_at=None,
                anchor_count=0,
                workload_identity_count=0,
                evidence=(),
                total_bytes=0,
            )
            begin = await self._repository.begin_trust_provisioning(
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
            assert begin.trust_provisioning is not None
            running = begin.trust_provisioning
            if running.state is not TrustProvisioningState.RUNNING:
                return begin

        trust_plan = self._plan_service.prepare(
            actor=actor,
            release_id=release_id,
            profile=profile,
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
            configuration_digest=configuration_digest,
            overlay=overlay,
        )
        trust_bundle, identity_catalog = self._plan_service.render(trust_plan)
        try:
            receipt = await self._publisher.publish(
                execution_id=running.execution_id,
                plan=trust_plan,
                trust_bundle=trust_bundle,
                identity_catalog=identity_catalog,
            )
            finished = replace(
                running,
                state=TrustProvisioningState.COMPLETED,
                result_code="bootstrap.trust.completed",
                completed_at=self._clock(),
                anchor_count=receipt.anchor_count,
                workload_identity_count=receipt.workload_identity_count,
                evidence=receipt.evidence,
                total_bytes=receipt.total_bytes,
            )
        except BootstrapTrustError as error:
            finished = replace(
                running,
                state=TrustProvisioningState.FAILED,
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
                ("anchor_count", str(finished.anchor_count)),
                ("workload_identity_count", str(finished.workload_identity_count)),
                ("file_count", str(len(finished.evidence))),
                ("total_bytes", str(finished.total_bytes)),
            ),
        )
        return await self._repository.finish_trust_provisioning(
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
            raise BootstrapTrustError("bootstrap_plan_mismatch")
        if (
            current.configuration_rendering is None
            or current.configuration_rendering.state is not ConfigurationRenderingState.COMPLETED
            or "phase.configure" not in current.completed_phase_ids
        ):
            raise BootstrapTrustError("bootstrap_configuration_evidence_missing")

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
                event_type="atlas.platform.bootstrap-trust.execute",
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
                event_type="atlas.platform.bootstrap-trust.denied",
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
