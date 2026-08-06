from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from hashlib import sha256
from typing import cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.connectors.application.capability_enablement_ports import (
    ConnectorCapabilityEnablementError,
)
from atlas.modules.connectors.application.runtime_trust_ports import (
    ConnectorRuntimeTrustEnablementSource,
    ConnectorRuntimeTrustError,
    ConnectorRuntimeTrustPolicySource,
    ConnectorRuntimeTrustProfileSource,
    ConnectorRuntimeTrustRepository,
)
from atlas.modules.connectors.domain.capability_enablement import (
    ENABLED_CAPABILITIES_GOVERNED,
    ConnectorCapabilityEnablementRecord,
)
from atlas.modules.connectors.domain.package_registration import (
    ConnectorPackageRegistrationRecord,
)
from atlas.modules.connectors.domain.runtime_trust import (
    ENABLED_RUNTIME_TRUSTED,
    ConnectorRuntimeTrustGrantRecord,
    ConnectorRuntimeTrustPolicySnapshot,
    ConnectorRuntimeTrustProfileSnapshot,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

RUNTIME_TRUST_CREATE_PERMISSION = "connectors.runtime-trust-grants.create"
RUNTIME_TRUST_READ_PERMISSION = "connectors.runtime-trust-grants.read"
RUNTIME_TRUST_GRANT_SCHEMA = "atlas.connector-runtime-trust-grant.v1"


class ConnectorRuntimeTrustService:
    def __init__(
        self,
        *,
        repository: ConnectorRuntimeTrustRepository,
        enablement_source: ConnectorRuntimeTrustEnablementSource,
        profile_source: ConnectorRuntimeTrustProfileSource,
        policy_source: ConnectorRuntimeTrustPolicySource,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._enablement_source = enablement_source
        self._profile_source = profile_source
        self._policy_source = policy_source
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    @property
    def repository(self) -> ConnectorRuntimeTrustRepository:
        return self._repository

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_enablement_id: str,
        source_enablement_digest: str,
        package_digest: str,
        runtime_profile_id: str,
        runtime_profile_digest: str,
        trust_policy_id: str,
        trust_policy_digest: str,
        purpose: str,
        boundary_only_acknowledged: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorRuntimeTrustGrantRecord:
        self._require_enterprise_human(actor)
        if not boundary_only_acknowledged:
            raise ConnectorRuntimeTrustError("runtime_trust_acknowledgement_required")
        purpose = purpose.strip()
        if not 20 <= len(purpose) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise ConnectorRuntimeTrustError("runtime_trust_request_invalid")
        fingerprint = self._digest(
            {
                "source_enablement_id": source_enablement_id,
                "source_enablement_digest": source_enablement_digest,
                "package_digest": package_digest,
                "runtime_profile_id": runtime_profile_id,
                "runtime_profile_digest": runtime_profile_digest,
                "trust_policy_id": trust_policy_id,
                "trust_policy_digest": trust_policy_digest,
                "purpose": purpose,
            }
        )
        existing = await self._repository.get_by_create_key(
            granted_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            return self._reuse(existing, actor, fingerprint)
        try:
            (
                enablement,
                registration,
                source_actors,
            ) = await self._enablement_source.runtime_trust_source(
                enablement_id=source_enablement_id
            )
        except ConnectorCapabilityEnablementError as error:
            raise ConnectorRuntimeTrustError("runtime_trust_source_not_found") from error
        profile = await self._profile_source.get_by_id(profile_id=runtime_profile_id)
        if profile is None:
            raise ConnectorRuntimeTrustError("runtime_trust_profile_not_found")
        policy = await self._policy_source.get_by_id(policy_id=trust_policy_id)
        if policy is None:
            raise ConnectorRuntimeTrustError("runtime_trust_policy_not_found")
        self._verify_snapshot(profile, "profile")
        self._verify_snapshot(policy, "policy")
        self._require_scope(actor, enablement.organization_id, enablement.environment_id)
        now = self._clock()
        self._verify_trust(
            actor=actor,
            enablement=enablement,
            registration=registration,
            profile=profile,
            policy=policy,
            source_enablement_digest=source_enablement_digest,
            package_digest=package_digest,
            runtime_profile_digest=runtime_profile_digest,
            trust_policy_digest=trust_policy_digest,
            now=now,
        )
        if actor.subject_id in source_actors | {profile.signed_by, policy.signed_by}:
            raise ConnectorRuntimeTrustError("runtime_trust_separation_required")

        async with self._mutation_lock:
            prior = await self._repository.get_by_enablement(
                source_enablement_id=enablement.enablement_id
            )
            if prior is not None:
                if (
                    prior.granted_by == actor.subject_id
                    and prior.request_fingerprint == fingerprint
                ):
                    return replace(prior, reused=True)
                raise ConnectorRuntimeTrustError("runtime_trust_enablement_conflict")
            await self._audit(
                actor,
                correlation_id,
                "connector_runtime_trust_requested",
                enablement.instance_id,
                idempotency_key,
                (("runtime_profile_digest", profile.canonical_digest),),
            )
            seed = self._digest(
                [enablement.enablement_id, profile.profile_id, profile.canonical_digest]
            )
            record = ConnectorRuntimeTrustGrantRecord(
                grant_id=f"connector-runtime-trust-grant.{seed[:24]}",
                schema_version=RUNTIME_TRUST_GRANT_SCHEMA,
                version=1,
                source_enablement_id=enablement.enablement_id,
                source_enablement_digest=enablement.canonical_digest,
                organization_id=enablement.organization_id,
                environment_id=enablement.environment_id,
                package_digest=enablement.package_digest,
                connector_id=enablement.connector_id,
                release_version=enablement.release_version,
                manifest_digest=enablement.manifest_digest,
                instance_id=enablement.instance_id,
                instance_key=enablement.instance_key,
                display_name=enablement.display_name,
                owner_id=enablement.owner_id,
                target_profile_id=enablement.target_profile_id,
                target_profile_digest=enablement.target_profile_digest,
                site_id=enablement.site_id,
                target_type=enablement.target_type,
                target_product=enablement.target_product,
                credential_profile_id=enablement.credential_profile_id,
                credential_profile_digest=enablement.credential_profile_digest,
                capability_profile_id=enablement.capability_profile_id,
                capability_profile_digest=enablement.capability_profile_digest,
                capability_count=len(enablement.capabilities),
                runtime_profile_id=profile.profile_id,
                runtime_profile_digest=profile.canonical_digest,
                sdk_profile=profile.sdk_profile,
                runner_runtime_id=profile.runner_runtime_id,
                runner_pool_id=profile.runner_pool_id,
                runner_image_digest=profile.runner_image_digest,
                runner_workload_identity_id=profile.runner_workload_identity_id,
                isolation_profile_id=profile.isolation_profile_id,
                filesystem_policy_id=profile.filesystem_policy_id,
                egress_policy_id=profile.egress_policy_id,
                secret_delivery_policy_id=profile.secret_delivery_policy_id,
                telemetry_policy_id=profile.telemetry_policy_id,
                resource_limit_profile_id=profile.resource_limit_profile_id,
                trust_policy_id=policy.policy_id,
                trust_policy_digest=policy.canonical_digest,
                trust_policy_version=policy.policy_version,
                trust_version=1,
                instance_state=policy.required_effective_state,
                granted_by=actor.subject_id,
                purpose=purpose,
                granted_at=now,
                canonical_digest="0" * 64,
                request_fingerprint=fingerprint,
                idempotency_key=idempotency_key,
            )
            record = replace(record, canonical_digest=self._digest(self._record_payload(record)))
            await self._audit(
                actor,
                correlation_id,
                "connector_runtime_trust_completed",
                record.grant_id,
                idempotency_key,
                (("instance_state", record.instance_state),),
            )
            if not await self._repository.add(record):
                raced = await self._repository.get_by_create_key(
                    granted_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    raise ConnectorRuntimeTrustError("runtime_trust_record_conflict")
                self._verify_record(raced)
                return replace(raced, reused=True)
        return record

    async def get(
        self, *, actor: AuthenticatedSubject, grant_id: str, correlation_id: str
    ) -> ConnectorRuntimeTrustGrantRecord:
        self._require_enterprise_human(actor)
        record = await self._repository.get(grant_id=grant_id)
        if record is None:
            raise ConnectorRuntimeTrustError("runtime_trust_record_not_found")
        self._verify_record(record)
        self._require_scope(actor, record.organization_id, record.environment_id)
        await self._audit(
            actor,
            correlation_id,
            "connector_runtime_trust_read",
            record.grant_id,
            None,
            (),
            permission_id=RUNTIME_TRUST_READ_PERMISSION,
        )
        return record

    async def secret_brokerage_source(
        self, *, grant_id: str
    ) -> tuple[ConnectorRuntimeTrustGrantRecord, frozenset[str]]:
        record = await self._repository.get(grant_id=grant_id)
        if record is None:
            raise ConnectorRuntimeTrustError("runtime_trust_record_not_found")
        self._verify_record(record)
        profile = await self._profile_source.get_by_id(profile_id=record.runtime_profile_id)
        policy = await self._policy_source.get_by_id(policy_id=record.trust_policy_id)
        if profile is None or policy is None:
            raise ConnectorRuntimeTrustError("runtime_trust_source_not_found")
        self._verify_snapshot(profile, "profile")
        self._verify_snapshot(policy, "policy")
        try:
            enablement, _, source_actors = await self._enablement_source.runtime_trust_source(
                enablement_id=record.source_enablement_id
            )
        except ConnectorCapabilityEnablementError as error:
            raise ConnectorRuntimeTrustError("runtime_trust_source_not_found") from error
        if (
            record.source_enablement_digest != enablement.canonical_digest
            or record.package_digest != enablement.package_digest
            or record.manifest_digest != enablement.manifest_digest
            or record.instance_id != enablement.instance_id
            or record.credential_profile_digest != enablement.credential_profile_digest
            or record.capability_profile_digest != enablement.capability_profile_digest
            or record.runtime_profile_digest != profile.canonical_digest
            or record.trust_policy_digest != policy.canonical_digest
        ):
            raise ConnectorRuntimeTrustError("runtime_trust_source_invalid")
        return (
            record,
            frozenset(source_actors | {record.granted_by, profile.signed_by, policy.signed_by}),
        )

    async def close(self) -> None:
        await self._repository.close()

    def _reuse(
        self,
        record: ConnectorRuntimeTrustGrantRecord,
        actor: AuthenticatedSubject,
        fingerprint: str,
    ) -> ConnectorRuntimeTrustGrantRecord:
        if record.granted_by != actor.subject_id or record.request_fingerprint != fingerprint:
            raise ConnectorRuntimeTrustError("runtime_trust_idempotency_conflict")
        self._verify_record(record)
        return replace(record, reused=True)

    @classmethod
    def _verify_snapshot(
        cls,
        snapshot: ConnectorRuntimeTrustProfileSnapshot | ConnectorRuntimeTrustPolicySnapshot,
        kind: str,
    ) -> None:
        payload = cast(dict[str, object], asdict(snapshot))
        payload.pop("canonical_digest")
        if cls._digest(cls._normalize(payload)) != snapshot.canonical_digest:
            raise ConnectorRuntimeTrustError(f"runtime_trust_{kind}_integrity_failed")

    @staticmethod
    def _verify_trust(
        *,
        actor: AuthenticatedSubject,
        enablement: ConnectorCapabilityEnablementRecord,
        registration: ConnectorPackageRegistrationRecord,
        profile: ConnectorRuntimeTrustProfileSnapshot,
        policy: ConnectorRuntimeTrustPolicySnapshot,
        source_enablement_digest: str,
        package_digest: str,
        runtime_profile_digest: str,
        trust_policy_digest: str,
        now: datetime,
    ) -> None:
        if (
            enablement.canonical_digest != source_enablement_digest
            or enablement.package_digest != package_digest
            or profile.canonical_digest != runtime_profile_digest
            or policy.canonical_digest != trust_policy_digest
            or policy.required_enablement_schema != enablement.schema_version
            or policy.required_profile_schema != profile.schema_version
            or policy.trust_grant_schema != RUNTIME_TRUST_GRANT_SCHEMA
            or profile.signed_by != policy.required_profile_signer_id
            or profile.organization_id != enablement.organization_id
            or profile.environment_id != enablement.environment_id
            or policy.organization_id != enablement.organization_id
            or policy.environment_id != enablement.environment_id
            or profile.package_digest != enablement.package_digest
            or profile.connector_id != enablement.connector_id
            or profile.release_version != enablement.release_version
            or profile.manifest_digest != enablement.manifest_digest
            or profile.instance_id != enablement.instance_id
            or profile.source_enablement_digest != enablement.canonical_digest
            or profile.capability_profile_digest != enablement.capability_profile_digest
            or registration.package_digest != enablement.package_digest
            or registration.manifest.manifest_digest != enablement.manifest_digest
            or profile.sdk_profile != registration.manifest.sdk_profile
            or profile.sdk_profile not in policy.allowed_sdk_profiles
            or profile.runner_runtime_id not in policy.allowed_runner_runtime_ids
            or profile.runner_pool_id not in policy.allowed_runner_pool_ids
            or profile.runner_image_digest not in policy.allowed_runner_image_digests
            or profile.runner_workload_identity_id != policy.required_runner_workload_identity_id
            or profile.isolation_profile_id != policy.required_isolation_profile_id
            or profile.filesystem_policy_id != policy.required_filesystem_policy_id
            or profile.egress_policy_id != policy.required_egress_policy_id
            or profile.secret_delivery_policy_id != policy.required_secret_delivery_policy_id
            or profile.telemetry_policy_id != policy.required_telemetry_policy_id
            or profile.resource_limit_profile_id != policy.required_resource_limit_profile_id
            or enablement.instance_state != ENABLED_CAPABILITIES_GOVERNED
            or not enablement.connector_enabled
            or not enablement.eligible_for_runtime_trust
            or enablement.runtime_trust_granted
            or enablement.credentials_resolved
            or not policy.issued_at <= now < policy.expires_at
            or not profile.issued_at <= now < profile.expires_at
            or now - enablement.enabled_at > timedelta(hours=policy.maximum_enablement_age_hours)
            or now - profile.issued_at > timedelta(hours=policy.maximum_profile_age_hours)
            or (
                policy.required_assurance_level is AssuranceLevel.HARDWARE_BACKED
                and actor.assurance_level is not AssuranceLevel.HARDWARE_BACKED
            )
        ):
            raise ConnectorRuntimeTrustError("runtime_trust_invalid")

    @classmethod
    def _verify_record(cls, record: ConnectorRuntimeTrustGrantRecord) -> None:
        if cls._digest(cls._record_payload(record)) != record.canonical_digest:
            raise ConnectorRuntimeTrustError("runtime_trust_record_integrity_failed")

    @classmethod
    def _record_payload(cls, record: ConnectorRuntimeTrustGrantRecord) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(record))
        for field in ("canonical_digest", "request_fingerprint", "idempotency_key", "reused"):
            payload.pop(field)
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _normalize(cls, value: object) -> object:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(key): cls._normalize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._normalize(item) for item in value]
        return value

    @staticmethod
    def _digest(payload: object) -> str:
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
                "ascii"
            )
        ).hexdigest()

    @staticmethod
    def _require_enterprise_human(actor: AuthenticatedSubject) -> None:
        if (
            actor.kind is not SubjectKind.HUMAN
            or actor.authentication_method is AuthenticationMethod.DEVELOPMENT
            or actor.assurance_level
            not in {AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED}
        ):
            raise ConnectorRuntimeTrustError("runtime_trust_enterprise_human_mfa_required")

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise ConnectorRuntimeTrustError("runtime_trust_record_not_found")

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        idempotency_key: str | None,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = RUNTIME_TRUST_CREATE_PERMISSION,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.runtime-trust",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id=permission_id,
                resource_type="resource.connector.runtime-trust-grant",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=metadata,
            )
        )


def _signed_snapshot(
    snapshot: ConnectorRuntimeTrustProfileSnapshot | ConnectorRuntimeTrustPolicySnapshot,
) -> str:
    payload = cast(dict[str, object], asdict(snapshot))
    payload.pop("canonical_digest")
    return ConnectorRuntimeTrustService._digest(ConnectorRuntimeTrustService._normalize(payload))


def build_connector_runtime_trust_profile(
    *,
    enablement: ConnectorCapabilityEnablementRecord,
    registration: ConnectorPackageRegistrationRecord,
    issued_at: datetime,
    expires_at: datetime,
) -> ConnectorRuntimeTrustProfileSnapshot:
    snapshot = ConnectorRuntimeTrustProfileSnapshot(
        profile_id="connector-runtime-trust-profile.development-isolated-read-only",
        schema_version="atlas.connector-runtime-trust-profile.v1",
        version=1,
        organization_id=enablement.organization_id,
        environment_id=enablement.environment_id,
        package_digest=enablement.package_digest,
        connector_id=enablement.connector_id,
        release_version=enablement.release_version,
        manifest_digest=enablement.manifest_digest,
        instance_id=enablement.instance_id,
        source_enablement_digest=enablement.canonical_digest,
        capability_profile_digest=enablement.capability_profile_digest,
        sdk_profile=registration.manifest.sdk_profile,
        runner_runtime_id="runner-runtime.python312",
        runner_pool_id="runner-pool.development-isolated",
        runner_image_digest=sha256(b"atlas-connector-runner-python312-v1").hexdigest(),
        runner_workload_identity_id="workload.connector-runner.read-only",
        isolation_profile_id="isolation-profile.process-restricted",
        filesystem_policy_id="filesystem-policy.package-read-only",
        egress_policy_id="egress-policy.target-bound-disabled-until-invocation",
        secret_delivery_policy_id="secret-delivery-policy.ephemeral-disabled-until-brokered",
        telemetry_policy_id="telemetry-policy.connector-redacted",
        resource_limit_profile_id="resource-limit-profile.connector-read-only",
        signed_by="subject.connector-runtime-security-attestor",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(snapshot, canonical_digest=_signed_snapshot(snapshot))


def build_development_connector_runtime_trust_policy(
    *,
    organization_id: str,
    environment_id: str,
    issued_at: datetime,
    expires_at: datetime,
) -> ConnectorRuntimeTrustPolicySnapshot:
    image_digest = sha256(b"atlas-connector-runner-python312-v1").hexdigest()
    snapshot = ConnectorRuntimeTrustPolicySnapshot(
        policy_id="connector-runtime-trust-policy.development",
        schema_version="atlas.connector-runtime-trust-policy.v1",
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-v1",
        required_enablement_schema="atlas.connector-capability-enablement.v1",
        required_profile_schema="atlas.connector-runtime-trust-profile.v1",
        required_profile_signer_id="subject.connector-runtime-security-attestor",
        allowed_sdk_profiles=("atlas.python312.v1",),
        allowed_runner_runtime_ids=("runner-runtime.python312",),
        allowed_runner_pool_ids=("runner-pool.development-isolated",),
        allowed_runner_image_digests=(image_digest,),
        required_runner_workload_identity_id="workload.connector-runner.read-only",
        required_isolation_profile_id="isolation-profile.process-restricted",
        required_filesystem_policy_id="filesystem-policy.package-read-only",
        required_egress_policy_id="egress-policy.target-bound-disabled-until-invocation",
        required_secret_delivery_policy_id=(
            "secret-delivery-policy.ephemeral-disabled-until-brokered"
        ),
        required_telemetry_policy_id="telemetry-policy.connector-redacted",
        required_resource_limit_profile_id="resource-limit-profile.connector-read-only",
        maximum_enablement_age_hours=720,
        maximum_profile_age_hours=168,
        required_assurance_level=AssuranceLevel.HARDWARE_BACKED,
        required_effective_state=ENABLED_RUNTIME_TRUSTED,
        trust_grant_schema=RUNTIME_TRUST_GRANT_SCHEMA,
        signed_by="subject.connector-runtime-trust-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(snapshot, canonical_digest=_signed_snapshot(snapshot))
