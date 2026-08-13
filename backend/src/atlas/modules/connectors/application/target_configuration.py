from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from hashlib import sha256
from typing import cast
from urllib.parse import urlsplit
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.connectors.application.instance_creation_ports import (
    ConnectorInstanceCreationError,
)
from atlas.modules.connectors.application.target_configuration_ports import (
    ConnectorTargetConfigurationError,
    ConnectorTargetConfigurationPolicySource,
    ConnectorTargetConfigurationRepository,
    ConnectorTargetInstanceSource,
    ConnectorTargetProfileSource,
)
from atlas.modules.connectors.domain.instance_creation import (
    DISABLED_UNCONFIGURED,
    ConnectorInstanceRecord,
)
from atlas.modules.connectors.domain.package_registration import (
    ConnectorPackageRegistrationRecord,
)
from atlas.modules.connectors.domain.target_configuration import (
    DISABLED_TARGET_CONFIGURED,
    ConnectorTargetConfigurationBinding,
    ConnectorTargetConfigurationPolicySnapshot,
    ConnectorTargetProfileSnapshot,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    SubjectKind,
    assurance_satisfies_policy,
)

TARGET_BINDING_CREATE_PERMISSION = "connectors.target-configuration-bindings.create"
TARGET_BINDING_READ_PERMISSION = "connectors.target-configuration-bindings.read"
TARGET_BINDING_SCHEMA = "atlas.connector-target-configuration-binding.v1"


class ConnectorTargetConfigurationService:
    def __init__(
        self,
        *,
        repository: ConnectorTargetConfigurationRepository,
        instance_source: ConnectorTargetInstanceSource,
        target_profile_source: ConnectorTargetProfileSource,
        policy_source: ConnectorTargetConfigurationPolicySource,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._instance_source = instance_source
        self._target_profile_source = target_profile_source
        self._policy_source = policy_source
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    @property
    def repository(self) -> ConnectorTargetConfigurationRepository:
        return self._repository

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_instance_record_id: str,
        source_instance_record_digest: str,
        package_digest: str,
        target_profile_id: str,
        target_profile_digest: str,
        configuration_policy_id: str,
        configuration_policy_digest: str,
        purpose: str,
        acknowledged_binding_grants_no_credentials_enablement_or_runtime_authority: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorTargetConfigurationBinding:
        self._require_human(actor)
        if not acknowledged_binding_grants_no_credentials_enablement_or_runtime_authority:
            raise ConnectorTargetConfigurationError("target_configuration_acknowledgement_required")
        purpose = purpose.strip()
        if not 20 <= len(purpose) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise ConnectorTargetConfigurationError("target_configuration_request_invalid")
        fingerprint = self._digest(
            {
                "source_instance_record_id": source_instance_record_id,
                "source_instance_record_digest": source_instance_record_digest,
                "package_digest": package_digest,
                "target_profile_id": target_profile_id,
                "target_profile_digest": target_profile_digest,
                "configuration_policy_id": configuration_policy_id,
                "configuration_policy_digest": configuration_policy_digest,
                "purpose": purpose,
            }
        )
        existing = await self._repository.get_by_create_key(
            bound_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            return self._reuse(existing, actor, fingerprint)
        try:
            (
                instance,
                _instance_policy,
                installation,
                registration,
                source_actors,
            ) = await self._instance_source.target_configuration_source(
                record_id=source_instance_record_id
            )
        except ConnectorInstanceCreationError as error:
            raise ConnectorTargetConfigurationError(
                "target_configuration_source_not_found"
            ) from error
        profile = await self._target_profile_source.get_by_id(profile_id=target_profile_id)
        if profile is None:
            raise ConnectorTargetConfigurationError("target_configuration_profile_not_found")
        policy = await self._policy_source.get_by_id(policy_id=configuration_policy_id)
        if policy is None:
            raise ConnectorTargetConfigurationError("target_configuration_policy_not_found")
        self._verify_profile(profile)
        self._verify_policy(policy)
        self._require_scope(actor, instance.organization_id, instance.environment_id)
        now = self._clock()
        self._verify_binding(
            actor=actor,
            instance=instance,
            profile=profile,
            policy=policy,
            source_instance_record_digest=source_instance_record_digest,
            package_digest=package_digest,
            target_profile_digest=target_profile_digest,
            configuration_policy_digest=configuration_policy_digest,
            registration_target_products=registration.manifest.target_products,
            now=now,
        )
        del installation
        if actor.subject_id in source_actors | {profile.signed_by, policy.signed_by}:
            raise ConnectorTargetConfigurationError("target_configuration_separation_required")

        async with self._mutation_lock:
            prior = await self._repository.get_by_instance(
                source_instance_record_id=instance.record_id
            )
            if prior is not None:
                if prior.bound_by == actor.subject_id and prior.request_fingerprint == fingerprint:
                    return replace(prior, reused=True)
                raise ConnectorTargetConfigurationError("target_configuration_instance_conflict")
            await self._audit(
                actor,
                correlation_id,
                "connector_target_configuration_requested",
                instance.instance_id,
                idempotency_key,
                (("target_profile_digest", profile.canonical_digest),),
            )
            seed = self._digest([instance.record_id, profile.profile_id, profile.canonical_digest])
            binding = ConnectorTargetConfigurationBinding(
                binding_id=f"connector-target-configuration.{seed[:24]}",
                schema_version=TARGET_BINDING_SCHEMA,
                version=1,
                source_instance_record_id=instance.record_id,
                source_instance_record_digest=instance.canonical_digest,
                source_installation_receipt_id=instance.source_installation_receipt_id,
                source_installation_receipt_digest=instance.source_installation_receipt_digest,
                organization_id=instance.organization_id,
                environment_id=instance.environment_id,
                package_digest=instance.package_digest,
                connector_id=instance.connector_id,
                release_version=instance.release_version,
                manifest_digest=instance.manifest_digest,
                instance_id=instance.instance_id,
                instance_key=instance.instance_key,
                display_name=instance.display_name,
                owner_id=instance.owner_id,
                target_profile_id=profile.profile_id,
                target_profile_digest=profile.canonical_digest,
                site_id=profile.site_id,
                target_id=profile.target_id,
                target_type=profile.target_type,
                target_product=profile.target_product,
                target_version=profile.target_version,
                configuration_policy_id=policy.policy_id,
                configuration_policy_digest=policy.canonical_digest,
                configuration_policy_version=policy.policy_version,
                configuration_version=1,
                instance_state=policy.required_effective_state,
                bound_by=actor.subject_id,
                purpose=purpose,
                bound_at=now,
                canonical_digest="0" * 64,
                request_fingerprint=fingerprint,
                idempotency_key=idempotency_key,
            )
            binding = replace(
                binding, canonical_digest=self._digest(self._binding_payload(binding))
            )
            await self._audit(
                actor,
                correlation_id,
                "connector_target_configuration_completed",
                binding.binding_id,
                idempotency_key,
                (("instance_state", binding.instance_state),),
            )
            if not await self._repository.add(binding):
                raced = await self._repository.get_by_create_key(
                    bound_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    raise ConnectorTargetConfigurationError("target_configuration_record_conflict")
                self._verify_record(raced)
                return replace(raced, reused=True)
        return binding

    async def get(
        self, *, actor: AuthenticatedSubject, binding_id: str, correlation_id: str
    ) -> ConnectorTargetConfigurationBinding:
        self._require_human(actor)
        binding = await self._repository.get(binding_id=binding_id)
        if binding is None:
            raise ConnectorTargetConfigurationError("target_configuration_record_not_found")
        self._verify_record(binding)
        self._require_scope(actor, binding.organization_id, binding.environment_id)
        await self._audit(
            actor,
            correlation_id,
            "connector_target_configuration_read",
            binding.binding_id,
            None,
            (),
            permission_id=TARGET_BINDING_READ_PERMISSION,
        )
        return binding

    async def credential_assignment_source(
        self, *, binding_id: str
    ) -> tuple[
        ConnectorTargetConfigurationBinding,
        ConnectorPackageRegistrationRecord,
        frozenset[str],
    ]:
        binding = await self._repository.get(binding_id=binding_id)
        if binding is None:
            raise ConnectorTargetConfigurationError("target_configuration_record_not_found")
        self._verify_record(binding)
        profile = await self._target_profile_source.get_by_id(profile_id=binding.target_profile_id)
        policy = await self._policy_source.get_by_id(policy_id=binding.configuration_policy_id)
        if profile is None or policy is None:
            raise ConnectorTargetConfigurationError("target_configuration_source_not_found")
        self._verify_profile(profile)
        self._verify_policy(policy)
        try:
            (
                instance,
                _instance_policy,
                _installation,
                registration,
                source_actors,
            ) = await self._instance_source.target_configuration_source(
                record_id=binding.source_instance_record_id
            )
        except ConnectorInstanceCreationError as error:
            raise ConnectorTargetConfigurationError(
                "target_configuration_source_not_found"
            ) from error
        if (
            binding.source_instance_record_digest != instance.canonical_digest
            or binding.package_digest != instance.package_digest
            or binding.target_profile_digest != profile.canonical_digest
            or binding.configuration_policy_digest != policy.canonical_digest
            or binding.organization_id != profile.organization_id
            or binding.environment_id != profile.environment_id
            or binding.site_id != profile.site_id
            or binding.target_id != profile.target_id
            or binding.target_type != profile.target_type
            or binding.target_product != profile.target_product
        ):
            raise ConnectorTargetConfigurationError("target_configuration_source_invalid")
        return (
            binding,
            registration,
            frozenset(
                source_actors
                | {
                    binding.bound_by,
                    profile.signed_by,
                    policy.signed_by,
                }
            ),
        )

    async def close(self) -> None:
        await self._repository.close()

    def _reuse(
        self,
        binding: ConnectorTargetConfigurationBinding,
        actor: AuthenticatedSubject,
        fingerprint: str,
    ) -> ConnectorTargetConfigurationBinding:
        if binding.bound_by != actor.subject_id or binding.request_fingerprint != fingerprint:
            raise ConnectorTargetConfigurationError("target_configuration_idempotency_conflict")
        self._verify_record(binding)
        return replace(binding, reused=True)

    @classmethod
    def _verify_profile(cls, profile: ConnectorTargetProfileSnapshot) -> None:
        payload = cast(dict[str, object], asdict(profile))
        payload.pop("canonical_digest")
        if cls._digest(cls._normalize(payload)) != profile.canonical_digest:
            raise ConnectorTargetConfigurationError("target_configuration_profile_integrity_failed")

    @classmethod
    def _verify_policy(cls, policy: ConnectorTargetConfigurationPolicySnapshot) -> None:
        payload = cast(dict[str, object], asdict(policy))
        payload.pop("canonical_digest")
        if cls._digest(cls._normalize(payload)) != policy.canonical_digest:
            raise ConnectorTargetConfigurationError("target_configuration_policy_integrity_failed")

    @staticmethod
    def _verify_binding(
        *,
        actor: AuthenticatedSubject,
        instance: ConnectorInstanceRecord,
        profile: ConnectorTargetProfileSnapshot,
        policy: ConnectorTargetConfigurationPolicySnapshot,
        source_instance_record_digest: str,
        package_digest: str,
        target_profile_digest: str,
        configuration_policy_digest: str,
        registration_target_products: tuple[str, ...],
        now: datetime,
    ) -> None:
        parsed = urlsplit(profile.endpoint_origin)
        host = (parsed.hostname or "").lower()
        if (
            instance.canonical_digest != source_instance_record_digest
            or instance.package_digest != package_digest
            or profile.canonical_digest != target_profile_digest
            or policy.canonical_digest != configuration_policy_digest
            or policy.required_instance_record_schema != instance.schema_version
            or policy.required_target_profile_schema != profile.schema_version
            or policy.binding_record_schema != TARGET_BINDING_SCHEMA
            or profile.signed_by != policy.required_target_profile_signer_id
            or profile.organization_id != instance.organization_id
            or profile.environment_id != instance.environment_id
            or policy.organization_id != instance.organization_id
            or policy.environment_id != instance.environment_id
            or instance.connector_id not in profile.allowed_connector_ids
            or instance.release_version not in profile.allowed_release_versions
            or profile.target_type not in policy.allowed_target_types
            or profile.target_product not in policy.allowed_target_products
            or profile.target_product not in registration_target_products
            or not any(host.endswith(suffix) for suffix in policy.allowed_endpoint_dns_suffixes)
            or parsed.port not in policy.allowed_endpoint_ports
            or profile.trust_profile_id != policy.required_trust_profile_id
            or profile.network_route_profile_id != policy.required_network_route_profile_id
            or profile.proxy_profile_id != policy.required_proxy_profile_id
            or instance.instance_state != DISABLED_UNCONFIGURED
            or not instance.eligible_for_configuration_governance
            or instance.target_configured
            or not policy.issued_at <= now < policy.expires_at
            or not profile.issued_at <= now < profile.expires_at
            or now - instance.created_at > timedelta(hours=policy.maximum_instance_age_hours)
            or now - profile.issued_at > timedelta(hours=policy.maximum_target_profile_age_hours)
            or not assurance_satisfies_policy(
                actor.assurance_level, policy.required_assurance_level
            )
        ):
            raise ConnectorTargetConfigurationError("target_configuration_binding_invalid")

    @classmethod
    def _verify_record(cls, binding: ConnectorTargetConfigurationBinding) -> None:
        if cls._digest(cls._binding_payload(binding)) != binding.canonical_digest:
            raise ConnectorTargetConfigurationError("target_configuration_record_integrity_failed")

    @classmethod
    def _binding_payload(cls, binding: ConnectorTargetConfigurationBinding) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(binding))
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
    def _require_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise ConnectorTargetConfigurationError("target_configuration_human_required")

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise ConnectorTargetConfigurationError("target_configuration_record_not_found")

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        idempotency_key: str | None,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = TARGET_BINDING_CREATE_PERMISSION,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.target-configuration",
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
                resource_type="resource.connector.target-configuration-binding",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=metadata,
            )
        )


def _signed_snapshot(
    snapshot: ConnectorTargetProfileSnapshot | ConnectorTargetConfigurationPolicySnapshot,
) -> str:
    payload = cast(dict[str, object], asdict(snapshot))
    payload.pop("canonical_digest")
    return ConnectorTargetConfigurationService._digest(
        ConnectorTargetConfigurationService._normalize(payload)
    )


def build_development_connector_target_profile(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> ConnectorTargetProfileSnapshot:
    profile = ConnectorTargetProfileSnapshot(
        profile_id="connector-target-profile.development-storage",
        schema_version="atlas.connector-target-profile.v1",
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        site_id="site.local",
        target_id="target.storage.development",
        target_type="target-type.storage-management",
        target_product="Synthetic Storage",
        target_version="version.10.9",
        endpoint_origin="https://storage-api.atlas.internal:443",
        trust_profile_id="trust-profile.enterprise-internal-ca",
        network_route_profile_id="network-route.connector-management",
        proxy_profile_id="proxy-profile.direct",
        allowed_connector_ids=("connector.synthetic-storage",),
        allowed_release_versions=("version.0.1.0-draft",),
        classification="classification.internal",
        signed_by="subject.connector-target-profile-owner",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(profile, canonical_digest=_signed_snapshot(profile))


def build_development_connector_target_configuration_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> ConnectorTargetConfigurationPolicySnapshot:
    policy = ConnectorTargetConfigurationPolicySnapshot(
        policy_id="connector-target-configuration-policy.development",
        schema_version="atlas.connector-target-configuration-policy.v1",
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="version.1.0",
        required_instance_record_schema="atlas.connector-instance-record.v1",
        required_target_profile_schema="atlas.connector-target-profile.v1",
        maximum_instance_age_hours=168,
        maximum_target_profile_age_hours=168,
        required_assurance_level=AssuranceLevel.SINGLE_FACTOR,
        required_target_profile_signer_id="subject.connector-target-profile-owner",
        allowed_target_types=("target-type.storage-management",),
        allowed_target_products=("Synthetic Storage",),
        allowed_endpoint_dns_suffixes=(".atlas.internal",),
        allowed_endpoint_ports=(443,),
        required_trust_profile_id="trust-profile.enterprise-internal-ca",
        required_network_route_profile_id="network-route.connector-management",
        required_proxy_profile_id="proxy-profile.direct",
        required_effective_state=DISABLED_TARGET_CONFIGURED,
        binding_record_schema=TARGET_BINDING_SCHEMA,
        signed_by="subject.connector-target-configuration-policy-owner",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(policy, canonical_digest=_signed_snapshot(policy))
