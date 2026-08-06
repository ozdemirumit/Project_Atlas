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
    ConnectorCapabilityEnablementPolicySource,
    ConnectorCapabilityEnablementRepository,
    ConnectorCapabilityProfileSource,
    ConnectorCapabilityValidationSource,
)
from atlas.modules.connectors.application.configuration_validation_ports import (
    ConnectorConfigurationValidationError,
)
from atlas.modules.connectors.domain.capability_enablement import (
    ENABLED_CAPABILITIES_GOVERNED,
    ConnectorCapabilityEnablementPolicySnapshot,
    ConnectorCapabilityEnablementRecord,
    ConnectorCapabilityProfileSnapshot,
    ConnectorGovernedCapability,
)
from atlas.modules.connectors.domain.configuration_validation import (
    DISABLED_CONFIGURATION_VALIDATED,
    ConnectorConfigurationValidationRecord,
)
from atlas.modules.connectors.domain.package_registration import (
    ConnectorPackageRegistrationRecord,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

CAPABILITY_ENABLEMENT_CREATE_PERMISSION = "connectors.capability-enablements.create"
CAPABILITY_ENABLEMENT_READ_PERMISSION = "connectors.capability-enablements.read"
CAPABILITY_ENABLEMENT_SCHEMA = "atlas.connector-capability-enablement.v1"


class ConnectorCapabilityEnablementService:
    def __init__(
        self,
        *,
        repository: ConnectorCapabilityEnablementRepository,
        validation_source: ConnectorCapabilityValidationSource,
        profile_source: ConnectorCapabilityProfileSource,
        policy_source: ConnectorCapabilityEnablementPolicySource,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._validation_source = validation_source
        self._profile_source = profile_source
        self._policy_source = policy_source
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    @property
    def repository(self) -> ConnectorCapabilityEnablementRepository:
        return self._repository

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_validation_id: str,
        source_validation_digest: str,
        package_digest: str,
        capability_profile_id: str,
        capability_profile_digest: str,
        enablement_policy_id: str,
        enablement_policy_digest: str,
        purpose: str,
        acknowledged_enablement_grants_no_secret_runtime_execution_or_deployment_authority: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorCapabilityEnablementRecord:
        self._require_enterprise_human(actor)
        if not acknowledged_enablement_grants_no_secret_runtime_execution_or_deployment_authority:
            raise ConnectorCapabilityEnablementError(
                "capability_enablement_acknowledgement_required"
            )
        purpose = purpose.strip()
        if not 20 <= len(purpose) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise ConnectorCapabilityEnablementError("capability_enablement_request_invalid")
        fingerprint = self._digest(
            {
                "source_validation_id": source_validation_id,
                "source_validation_digest": source_validation_digest,
                "package_digest": package_digest,
                "capability_profile_id": capability_profile_id,
                "capability_profile_digest": capability_profile_digest,
                "enablement_policy_id": enablement_policy_id,
                "enablement_policy_digest": enablement_policy_digest,
                "purpose": purpose,
            }
        )
        existing = await self._repository.get_by_create_key(
            enabled_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            return self._reuse(existing, actor, fingerprint)
        try:
            (
                validation,
                registration,
                source_actors,
            ) = await self._validation_source.capability_enablement_source(
                validation_id=source_validation_id
            )
        except ConnectorConfigurationValidationError as error:
            raise ConnectorCapabilityEnablementError(
                "capability_enablement_source_not_found"
            ) from error
        profile = await self._profile_source.get_by_id(profile_id=capability_profile_id)
        if profile is None:
            raise ConnectorCapabilityEnablementError("capability_enablement_profile_not_found")
        policy = await self._policy_source.get_by_id(policy_id=enablement_policy_id)
        if policy is None:
            raise ConnectorCapabilityEnablementError("capability_enablement_policy_not_found")
        self._verify_snapshot(profile, "profile")
        self._verify_snapshot(policy, "policy")
        self._require_scope(actor, validation.organization_id, validation.environment_id)
        now = self._clock()
        self._verify_enablement(
            actor=actor,
            validation=validation,
            registration=registration,
            profile=profile,
            policy=policy,
            source_validation_digest=source_validation_digest,
            package_digest=package_digest,
            capability_profile_digest=capability_profile_digest,
            enablement_policy_digest=enablement_policy_digest,
            now=now,
        )
        if actor.subject_id in source_actors | {profile.signed_by, policy.signed_by}:
            raise ConnectorCapabilityEnablementError("capability_enablement_separation_required")

        async with self._mutation_lock:
            prior = await self._repository.get_by_validation(
                source_validation_id=validation.validation_id
            )
            if prior is not None:
                if (
                    prior.enabled_by == actor.subject_id
                    and prior.request_fingerprint == fingerprint
                ):
                    return replace(prior, reused=True)
                raise ConnectorCapabilityEnablementError(
                    "capability_enablement_validation_conflict"
                )
            await self._audit(
                actor,
                correlation_id,
                "connector_capability_enablement_requested",
                validation.instance_id,
                idempotency_key,
                (("capability_profile_digest", profile.canonical_digest),),
            )
            seed = self._digest(
                [validation.validation_id, profile.profile_id, profile.canonical_digest]
            )
            record = ConnectorCapabilityEnablementRecord(
                enablement_id=f"connector-capability-enablement.{seed[:24]}",
                schema_version=CAPABILITY_ENABLEMENT_SCHEMA,
                version=1,
                source_validation_id=validation.validation_id,
                source_validation_digest=validation.canonical_digest,
                organization_id=validation.organization_id,
                environment_id=validation.environment_id,
                package_digest=validation.package_digest,
                connector_id=validation.connector_id,
                release_version=validation.release_version,
                manifest_digest=validation.manifest_digest,
                instance_id=validation.instance_id,
                instance_key=validation.instance_key,
                display_name=validation.display_name,
                owner_id=validation.owner_id,
                target_profile_id=validation.target_profile_id,
                target_profile_digest=validation.target_profile_digest,
                site_id=validation.site_id,
                target_type=validation.target_type,
                target_product=validation.target_product,
                credential_profile_id=validation.credential_profile_id,
                credential_profile_digest=validation.credential_profile_digest,
                capability_profile_id=profile.profile_id,
                capability_profile_digest=profile.canonical_digest,
                capabilities=profile.capabilities,
                enablement_policy_id=policy.policy_id,
                enablement_policy_digest=policy.canonical_digest,
                enablement_policy_version=policy.policy_version,
                enablement_version=1,
                instance_state=policy.required_effective_state,
                enabled_by=actor.subject_id,
                purpose=purpose,
                enabled_at=now,
                canonical_digest="0" * 64,
                request_fingerprint=fingerprint,
                idempotency_key=idempotency_key,
            )
            record = replace(record, canonical_digest=self._digest(self._record_payload(record)))
            await self._audit(
                actor,
                correlation_id,
                "connector_capability_enablement_completed",
                record.enablement_id,
                idempotency_key,
                (("instance_state", record.instance_state),),
            )
            if not await self._repository.add(record):
                raced = await self._repository.get_by_create_key(
                    enabled_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    raise ConnectorCapabilityEnablementError(
                        "capability_enablement_record_conflict"
                    )
                self._verify_record(raced)
                return replace(raced, reused=True)
        return record

    async def get(
        self, *, actor: AuthenticatedSubject, enablement_id: str, correlation_id: str
    ) -> ConnectorCapabilityEnablementRecord:
        self._require_enterprise_human(actor)
        record = await self._repository.get(enablement_id=enablement_id)
        if record is None:
            raise ConnectorCapabilityEnablementError("capability_enablement_record_not_found")
        self._verify_record(record)
        self._require_scope(actor, record.organization_id, record.environment_id)
        await self._audit(
            actor,
            correlation_id,
            "connector_capability_enablement_read",
            record.enablement_id,
            None,
            (),
            permission_id=CAPABILITY_ENABLEMENT_READ_PERMISSION,
        )
        return record

    async def close(self) -> None:
        await self._repository.close()

    def _reuse(
        self,
        record: ConnectorCapabilityEnablementRecord,
        actor: AuthenticatedSubject,
        fingerprint: str,
    ) -> ConnectorCapabilityEnablementRecord:
        if record.enabled_by != actor.subject_id or record.request_fingerprint != fingerprint:
            raise ConnectorCapabilityEnablementError("capability_enablement_idempotency_conflict")
        self._verify_record(record)
        return replace(record, reused=True)

    @classmethod
    def _verify_snapshot(
        cls,
        snapshot: ConnectorCapabilityProfileSnapshot | ConnectorCapabilityEnablementPolicySnapshot,
        kind: str,
    ) -> None:
        payload = cast(dict[str, object], asdict(snapshot))
        payload.pop("canonical_digest")
        if cls._digest(cls._normalize(payload)) != snapshot.canonical_digest:
            raise ConnectorCapabilityEnablementError(
                f"capability_enablement_{kind}_integrity_failed"
            )

    @staticmethod
    def _verify_enablement(
        *,
        actor: AuthenticatedSubject,
        validation: ConnectorConfigurationValidationRecord,
        registration: ConnectorPackageRegistrationRecord,
        profile: ConnectorCapabilityProfileSnapshot,
        policy: ConnectorCapabilityEnablementPolicySnapshot,
        source_validation_digest: str,
        package_digest: str,
        capability_profile_digest: str,
        enablement_policy_digest: str,
        now: datetime,
    ) -> None:
        registered = tuple(
            sorted(
                (
                    item.capability_id,
                    item.capability_class,
                    item.required_permission,
                )
                for item in registration.manifest.capabilities
            )
        )
        selected = tuple(
            sorted(
                (
                    item.capability_id,
                    item.capability_class,
                    item.required_permission,
                )
                for item in profile.capabilities
            )
        )
        if (
            validation.canonical_digest != source_validation_digest
            or validation.package_digest != package_digest
            or profile.canonical_digest != capability_profile_digest
            or policy.canonical_digest != enablement_policy_digest
            or policy.required_validation_schema != validation.schema_version
            or policy.required_profile_schema != profile.schema_version
            or policy.enablement_record_schema != CAPABILITY_ENABLEMENT_SCHEMA
            or profile.signed_by != policy.required_profile_signer_id
            or profile.organization_id != validation.organization_id
            or profile.environment_id != validation.environment_id
            or policy.organization_id != validation.organization_id
            or policy.environment_id != validation.environment_id
            or profile.package_digest != validation.package_digest
            or profile.connector_id != validation.connector_id
            or profile.release_version != validation.release_version
            or profile.manifest_digest != validation.manifest_digest
            or profile.instance_id != validation.instance_id
            or profile.target_type != validation.target_type
            or registration.manifest.manifest_digest != validation.manifest_digest
            or selected != registered
            or len(selected) > policy.maximum_capabilities
            or any(item[1] not in policy.allowed_capability_classes for item in selected)
            or validation.target_product not in registration.manifest.target_products
            or validation.instance_state != DISABLED_CONFIGURATION_VALIDATED
            or not validation.eligible_for_capability_governance
            or validation.connector_enabled
            or validation.credentials_resolved
            or not policy.issued_at <= now < policy.expires_at
            or not profile.issued_at <= now < profile.expires_at
            or now - validation.validated_at > timedelta(hours=policy.maximum_validation_age_hours)
            or now - profile.issued_at > timedelta(hours=policy.maximum_profile_age_hours)
            or (
                policy.required_assurance_level is AssuranceLevel.HARDWARE_BACKED
                and actor.assurance_level is not AssuranceLevel.HARDWARE_BACKED
            )
        ):
            raise ConnectorCapabilityEnablementError("capability_enablement_invalid")

    @classmethod
    def _verify_record(cls, record: ConnectorCapabilityEnablementRecord) -> None:
        if cls._digest(cls._record_payload(record)) != record.canonical_digest:
            raise ConnectorCapabilityEnablementError(
                "capability_enablement_record_integrity_failed"
            )

    @classmethod
    def _record_payload(cls, record: ConnectorCapabilityEnablementRecord) -> dict[str, object]:
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
            raise ConnectorCapabilityEnablementError(
                "capability_enablement_enterprise_human_mfa_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise ConnectorCapabilityEnablementError("capability_enablement_record_not_found")

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        idempotency_key: str | None,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = CAPABILITY_ENABLEMENT_CREATE_PERMISSION,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.capability-enablement",
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
                resource_type="resource.connector.capability-enablement",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=metadata,
            )
        )


def _signed_snapshot(
    snapshot: ConnectorCapabilityProfileSnapshot | ConnectorCapabilityEnablementPolicySnapshot,
) -> str:
    payload = cast(dict[str, object], asdict(snapshot))
    payload.pop("canonical_digest")
    return ConnectorCapabilityEnablementService._digest(
        ConnectorCapabilityEnablementService._normalize(payload)
    )


def build_connector_capability_profile(
    *,
    validation: ConnectorConfigurationValidationRecord,
    registration: ConnectorPackageRegistrationRecord,
    issued_at: datetime,
    expires_at: datetime,
) -> ConnectorCapabilityProfileSnapshot:
    capabilities = tuple(
        ConnectorGovernedCapability(
            capability_id=item.capability_id,
            capability_class=item.capability_class,
            required_permission=item.required_permission,
        )
        for item in sorted(registration.manifest.capabilities, key=lambda item: item.capability_id)
    )
    snapshot = ConnectorCapabilityProfileSnapshot(
        profile_id="connector-capability-profile.development-read-only",
        schema_version="atlas.connector-capability-profile.v1",
        version=1,
        organization_id=validation.organization_id,
        environment_id=validation.environment_id,
        package_digest=validation.package_digest,
        connector_id=validation.connector_id,
        release_version=validation.release_version,
        manifest_digest=validation.manifest_digest,
        instance_id=validation.instance_id,
        target_type=validation.target_type,
        capabilities=capabilities,
        signed_by="human.connector-capability-profile-owner",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(snapshot, canonical_digest=_signed_snapshot(snapshot))


def build_development_connector_capability_enablement_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> ConnectorCapabilityEnablementPolicySnapshot:
    snapshot = ConnectorCapabilityEnablementPolicySnapshot(
        policy_id="connector-capability-enablement-policy.development",
        schema_version="atlas.connector-capability-enablement-policy.v1",
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-v1",
        required_validation_schema="atlas.connector-configuration-validation.v1",
        required_profile_schema="atlas.connector-capability-profile.v1",
        required_profile_signer_id="human.connector-capability-profile-owner",
        allowed_capability_classes=("C0", "C1"),
        maximum_capabilities=100,
        maximum_validation_age_hours=8760,
        maximum_profile_age_hours=8760,
        required_assurance_level=AssuranceLevel.MULTI_FACTOR,
        required_effective_state=ENABLED_CAPABILITIES_GOVERNED,
        enablement_record_schema=CAPABILITY_ENABLEMENT_SCHEMA,
        signed_by="human.connector-capability-enablement-policy-owner",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(snapshot, canonical_digest=_signed_snapshot(snapshot))
