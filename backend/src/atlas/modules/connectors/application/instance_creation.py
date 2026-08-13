from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from hashlib import sha256
from typing import cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.connectors.application.instance_creation_ports import (
    ConnectorInstanceCreationError,
    ConnectorInstanceCreationPolicySource,
    ConnectorInstanceInstallationSource,
    ConnectorInstanceRepository,
)
from atlas.modules.connectors.application.package_installation_ports import PackageInstallationError
from atlas.modules.connectors.domain.instance_creation import (
    DISABLED_UNCONFIGURED,
    ConnectorInstanceCreationPolicySnapshot,
    ConnectorInstanceRecord,
)
from atlas.modules.connectors.domain.package_installation import (
    ConnectorPackageInstallationPolicySnapshot,
    ConnectorPackageInstallationReceipt,
)
from atlas.modules.connectors.domain.package_registration import ConnectorPackageRegistrationRecord
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    SubjectKind,
)

INSTANCE_CREATE_PERMISSION = "connectors.instances.create"
INSTANCE_READ_PERMISSION = "connectors.instances.read"
INSTANCE_RECORD_SCHEMA = "atlas.connector-instance-record.v1"
_INSTANCE_KEY = re.compile(r"^[a-z][a-z0-9_.:-]{2,127}$")


class ConnectorInstanceCreationService:
    def __init__(
        self,
        *,
        repository: ConnectorInstanceRepository,
        installation_source: ConnectorInstanceInstallationSource,
        policy_source: ConnectorInstanceCreationPolicySource,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._installation_source = installation_source
        self._policy_source = policy_source
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    @property
    def repository(self) -> ConnectorInstanceRepository:
        return self._repository

    @property
    def environment_id(self) -> str:
        return self._environment_id

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_installation_receipt_id: str,
        source_installation_receipt_digest: str,
        package_digest: str,
        instance_key: str,
        display_name: str,
        instance_policy_id: str,
        instance_policy_digest: str,
        purpose: str,
        acknowledged_instance_is_disabled_and_grants_no_target_or_runtime_authority: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorInstanceRecord:
        self._require_enterprise_human(actor)
        if not acknowledged_instance_is_disabled_and_grants_no_target_or_runtime_authority:
            raise ConnectorInstanceCreationError("connector_instance_acknowledgement_required")
        instance_key = instance_key.strip().lower()
        display_name = display_name.strip()
        purpose = purpose.strip()
        if (
            _INSTANCE_KEY.fullmatch(instance_key) is None
            or not 3 <= len(display_name) <= 200
            or not 20 <= len(purpose) <= 1000
            or not 8 <= len(idempotency_key) <= 128
        ):
            raise ConnectorInstanceCreationError("connector_instance_request_invalid")
        fingerprint = self._digest(
            {
                "source_installation_receipt_id": source_installation_receipt_id,
                "source_installation_receipt_digest": source_installation_receipt_digest,
                "package_digest": package_digest,
                "instance_key": instance_key,
                "display_name": display_name,
                "instance_policy_id": instance_policy_id,
                "instance_policy_digest": instance_policy_digest,
                "purpose": purpose,
            }
        )
        existing = await self._repository.get_by_create_key(
            created_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            return self._reuse(existing, actor, fingerprint)

        try:
            (
                installation,
                installation_policy,
                registration,
                source_actors,
            ) = await self._installation_source.connector_instance_creation_source(
                receipt_id=source_installation_receipt_id
            )
        except PackageInstallationError as error:
            raise ConnectorInstanceCreationError("connector_instance_source_not_found") from error
        policy = await self._policy_source.get_by_id(policy_id=instance_policy_id)
        if policy is None:
            raise ConnectorInstanceCreationError("connector_instance_policy_not_found")
        self._verify_policy(policy)
        self._require_scope(actor, installation.organization_id, installation.environment_id)
        now = self._clock()
        self._verify_source(
            actor=actor,
            installation=installation,
            installation_policy=installation_policy,
            registration=registration,
            policy=policy,
            source_installation_receipt_digest=source_installation_receipt_digest,
            package_digest=package_digest,
            instance_policy_digest=instance_policy_digest,
            instance_key=instance_key,
            display_name=display_name,
            now=now,
        )
        if actor.subject_id in source_actors | {policy.signed_by}:
            raise ConnectorInstanceCreationError("connector_instance_separation_required")

        async with self._mutation_lock:
            prior = await self._repository.get_by_scope_key(
                organization_id=installation.organization_id,
                environment_id=installation.environment_id,
                instance_key=instance_key,
            )
            if prior is not None:
                if (
                    prior.created_by == actor.subject_id
                    and prior.request_fingerprint == fingerprint
                ):
                    return replace(prior, reused=True)
                raise ConnectorInstanceCreationError("connector_instance_key_conflict")
            await self._audit(
                actor,
                correlation_id,
                "connector_instance_creation_requested",
                installation.receipt_id,
                idempotency_key,
                (("package_digest", package_digest), ("instance_key", instance_key)),
            )
            seed = self._digest(
                [
                    installation.organization_id,
                    installation.environment_id,
                    installation.connector_id,
                    installation.release_version,
                    installation.receipt_id,
                    instance_key,
                ]
            )
            record = ConnectorInstanceRecord(
                record_id=f"connector-instance-record.{seed[:24]}",
                schema_version=INSTANCE_RECORD_SCHEMA,
                version=1,
                source_installation_receipt_id=installation.receipt_id,
                source_installation_receipt_digest=installation.canonical_digest,
                source_registration_record_id=installation.source_registration_record_id,
                source_registration_record_digest=installation.source_registration_record_digest,
                source_publication_receipt_id=installation.source_publication_receipt_id,
                source_publication_receipt_digest=installation.source_publication_receipt_digest,
                source_signing_receipt_id=installation.source_signing_receipt_id,
                source_signing_receipt_digest=installation.source_signing_receipt_digest,
                source_approval_request_id=installation.source_approval_request_id,
                source_approval_request_digest=installation.source_approval_request_digest,
                source_final_validation_id=installation.source_final_validation_id,
                source_final_validation_digest=installation.source_final_validation_digest,
                source_acquisition_id=installation.source_acquisition_id,
                source_acquisition_digest=installation.source_acquisition_digest,
                organization_id=installation.organization_id,
                environment_id=installation.environment_id,
                package_digest=installation.package_digest,
                package_size_bytes=installation.package_size_bytes,
                publisher_id=installation.publisher_id,
                connector_id=installation.connector_id,
                release_version=installation.release_version,
                provenance_digest=installation.provenance_digest,
                manifest_digest=installation.manifest_digest,
                sdk_profile=installation.sdk_profile,
                registry_profile_id=installation.registry_profile_id,
                installation_policy_id=installation.installation_policy_id,
                installation_policy_digest=installation.installation_policy_digest,
                installation_store_profile_id=(
                    installation.installation.installation_store_profile_id
                ),
                installation_artifact_reference_schema=(
                    installation.installation.artifact_reference_schema
                ),
                instance_policy_id=policy.policy_id,
                instance_policy_digest=policy.canonical_digest,
                instance_policy_version=policy.policy_version,
                instance_id=f"connector-instance.{seed[:24]}",
                instance_key=instance_key,
                display_name=display_name,
                instance_state=policy.required_initial_state,
                owner_id=actor.subject_id,
                support_group_id=policy.support_group_id,
                created_by=actor.subject_id,
                purpose=purpose,
                created_at=now,
                canonical_digest="0" * 64,
                request_fingerprint=fingerprint,
                idempotency_key=idempotency_key,
            )
            record = replace(record, canonical_digest=self._digest(self._record_payload(record)))
            await self._audit(
                actor,
                correlation_id,
                "connector_instance_creation_completed",
                record.instance_id,
                idempotency_key,
                (("instance_state", record.instance_state),),
            )
            if not await self._repository.add(record):
                raced = await self._repository.get_by_create_key(
                    created_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    raise ConnectorInstanceCreationError("connector_instance_record_conflict")
                self._verify_record(raced)
                return replace(raced, reused=True)
        return record

    async def get(
        self, *, actor: AuthenticatedSubject, record_id: str, correlation_id: str
    ) -> ConnectorInstanceRecord:
        self._require_enterprise_human(actor)
        record = await self._repository.get(record_id=record_id)
        if record is None:
            raise ConnectorInstanceCreationError("connector_instance_record_not_found")
        self._verify_record(record)
        self._require_scope(actor, record.organization_id, record.environment_id)
        await self._audit(
            actor,
            correlation_id,
            "connector_instance_record_read",
            record.instance_id,
            None,
            (),
            permission_id=INSTANCE_READ_PERMISSION,
        )
        return record

    async def list_policies(
        self, *, actor: AuthenticatedSubject, correlation_id: str
    ) -> tuple[ConnectorInstanceCreationPolicySnapshot, ...]:
        self._require_enterprise_human(actor)
        policies = await self._policy_source.list_scope(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
        )
        now = self._clock()
        current: list[ConnectorInstanceCreationPolicySnapshot] = []
        for policy in policies:
            self._verify_policy(policy)
            if (
                policy.organization_id != actor.organization_id
                or policy.environment_id != self._environment_id
                or not policy.issued_at <= now < policy.expires_at
            ):
                continue
            current.append(policy)
        await self._audit(
            actor,
            correlation_id,
            "connector_instance_policies_listed",
            self._environment_id,
            None,
            (("count", str(len(current))),),
            permission_id=INSTANCE_READ_PERMISSION,
        )
        return tuple(current)

    async def target_configuration_source(
        self, *, record_id: str
    ) -> tuple[
        ConnectorInstanceRecord,
        ConnectorInstanceCreationPolicySnapshot,
        ConnectorPackageInstallationReceipt,
        ConnectorPackageRegistrationRecord,
        frozenset[str],
    ]:
        record = await self._repository.get(record_id=record_id)
        if record is None:
            raise ConnectorInstanceCreationError("connector_instance_record_not_found")
        self._verify_record(record)
        try:
            (
                installation,
                _installation_policy,
                registration,
                source_actors,
            ) = await self._installation_source.connector_instance_creation_source(
                receipt_id=record.source_installation_receipt_id
            )
        except PackageInstallationError as error:
            raise ConnectorInstanceCreationError("connector_instance_source_not_found") from error
        policy = await self._policy_source.get_by_id(policy_id=record.instance_policy_id)
        if policy is None:
            raise ConnectorInstanceCreationError("connector_instance_policy_not_found")
        self._verify_policy(policy)
        if (
            record.source_installation_receipt_digest != installation.canonical_digest
            or record.source_registration_record_id != installation.source_registration_record_id
            or record.source_registration_record_digest
            != installation.source_registration_record_digest
            or record.source_publication_receipt_id != installation.source_publication_receipt_id
            or record.source_publication_receipt_digest
            != installation.source_publication_receipt_digest
            or record.source_signing_receipt_id != installation.source_signing_receipt_id
            or record.source_signing_receipt_digest != installation.source_signing_receipt_digest
            or record.source_approval_request_id != installation.source_approval_request_id
            or record.source_approval_request_digest != installation.source_approval_request_digest
            or record.source_final_validation_id != installation.source_final_validation_id
            or record.source_final_validation_digest != installation.source_final_validation_digest
            or record.source_acquisition_id != installation.source_acquisition_id
            or record.source_acquisition_digest != installation.source_acquisition_digest
            or record.organization_id != installation.organization_id
            or record.environment_id != installation.environment_id
            or record.package_digest != installation.package_digest
            or record.package_size_bytes != installation.package_size_bytes
            or record.publisher_id != installation.publisher_id
            or record.connector_id != installation.connector_id
            or record.release_version != installation.release_version
            or record.provenance_digest != installation.provenance_digest
            or record.manifest_digest != installation.manifest_digest
            or record.sdk_profile != installation.sdk_profile
            or record.registry_profile_id != installation.registry_profile_id
            or record.installation_policy_id != installation.installation_policy_id
            or record.installation_policy_digest != installation.installation_policy_digest
            or record.installation_store_profile_id
            != installation.installation.installation_store_profile_id
            or record.installation_artifact_reference_schema
            != installation.installation.artifact_reference_schema
            or record.instance_policy_digest != policy.canonical_digest
            or record.instance_policy_version != policy.policy_version
            or not record.instance_created
            or not record.eligible_for_configuration_governance
            or record.instance_state != DISABLED_UNCONFIGURED
            or record.target_configured
            or record.promotion_blocked
            or any(
                (
                    record.credentials_resolved,
                    record.connector_enabled,
                    record.runtime_trust_granted,
                    record.execution_authorized,
                    record.deployment_approved,
                    record.infrastructure_mutation_performed,
                )
            )
        ):
            raise ConnectorInstanceCreationError("connector_instance_source_binding_invalid")
        actors = source_actors | {
            record.created_by,
            record.owner_id,
            policy.signed_by,
        }
        return record, policy, installation, registration, frozenset(actors)

    async def close(self) -> None:
        await self._repository.close()

    def _reuse(
        self, record: ConnectorInstanceRecord, actor: AuthenticatedSubject, fingerprint: str
    ) -> ConnectorInstanceRecord:
        if record.created_by != actor.subject_id or record.request_fingerprint != fingerprint:
            raise ConnectorInstanceCreationError("connector_instance_idempotency_conflict")
        self._verify_record(record)
        return replace(record, reused=True)

    @classmethod
    def _verify_policy(cls, policy: ConnectorInstanceCreationPolicySnapshot) -> None:
        payload = cast(dict[str, object], asdict(policy))
        payload.pop("canonical_digest")
        if cls._digest(cls._normalize(payload)) != policy.canonical_digest:
            raise ConnectorInstanceCreationError("connector_instance_policy_integrity_failed")

    @staticmethod
    def _verify_source(
        *,
        actor: AuthenticatedSubject,
        installation: ConnectorPackageInstallationReceipt,
        installation_policy: ConnectorPackageInstallationPolicySnapshot,
        registration: ConnectorPackageRegistrationRecord,
        policy: ConnectorInstanceCreationPolicySnapshot,
        source_installation_receipt_digest: str,
        package_digest: str,
        instance_policy_digest: str,
        instance_key: str,
        display_name: str,
        now: datetime,
    ) -> None:
        classes = {item.capability_class for item in registration.manifest.capabilities}
        if (
            installation.canonical_digest != source_installation_receipt_digest
            or installation.package_digest != package_digest
            or policy.canonical_digest != instance_policy_digest
            or policy.required_installation_receipt_schema != installation.schema_version
            or policy.record_schema != INSTANCE_RECORD_SCHEMA
            or policy.required_installation_store_profile_id
            != installation.installation.installation_store_profile_id
            or policy.required_installation_artifact_reference_schema
            != installation.installation.artifact_reference_schema
            or installation.installation_policy_id != installation_policy.policy_id
            or installation.installation_policy_digest != installation_policy.canonical_digest
            or installation.sdk_profile not in policy.allowed_sdk_profiles
            or not classes.issubset(set(policy.allowed_capability_classes))
            or policy.organization_id != installation.organization_id
            or policy.environment_id != installation.environment_id
            or not policy.issued_at <= now < policy.expires_at
            or installation.installed_at > now
            or now - installation.installed_at
            > timedelta(hours=policy.maximum_installation_age_hours)
            or len(instance_key) > policy.maximum_instance_key_length
            or len(display_name) > policy.maximum_display_name_length
            or not installation.package_installed
            or not installation.eligible_for_instance_governance
            or installation.instance_created
            or installation.promotion_blocked
            or not ConnectorInstanceCreationService._assurance_satisfies(
                actor.assurance_level, policy.required_assurance_level
            )
        ):
            raise ConnectorInstanceCreationError("connector_instance_binding_invalid")

    @classmethod
    def _verify_record(cls, record: ConnectorInstanceRecord) -> None:
        if cls._digest(cls._record_payload(record)) != record.canonical_digest:
            raise ConnectorInstanceCreationError("connector_instance_record_integrity_failed")

    @classmethod
    def _record_payload(cls, record: ConnectorInstanceRecord) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(record))
        for field in (
            "canonical_digest",
            "request_fingerprint",
            "idempotency_key",
            "retirement_request_fingerprint",
            "retirement_idempotency_key",
            "reused",
        ):
            payload.pop(field)
        if record.retired_by is None:
            for field in ("retired_by", "retired_at", "retirement_reason"):
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
        if actor.kind is not SubjectKind.HUMAN:
            raise ConnectorInstanceCreationError("connector_instance_human_required")

    @staticmethod
    def _assurance_satisfies(actual: AssuranceLevel, required: AssuranceLevel) -> bool:
        if required is AssuranceLevel.SINGLE_FACTOR:
            return actual in {
                AssuranceLevel.DEVELOPMENT,
                AssuranceLevel.SINGLE_FACTOR,
                AssuranceLevel.MULTI_FACTOR,
                AssuranceLevel.HARDWARE_BACKED,
            }
        order = {
            AssuranceLevel.DEVELOPMENT: 0,
            AssuranceLevel.SINGLE_FACTOR: 1,
            AssuranceLevel.MULTI_FACTOR: 2,
            AssuranceLevel.HARDWARE_BACKED: 3,
        }
        return order[actual] >= order[required]

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise ConnectorInstanceCreationError("connector_instance_record_not_found")

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        idempotency_key: str | None,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = INSTANCE_CREATE_PERMISSION,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.instance",
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
                resource_type="resource.connector.instance",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=metadata,
            )
        )


def build_development_connector_instance_creation_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> ConnectorInstanceCreationPolicySnapshot:
    policy = ConnectorInstanceCreationPolicySnapshot(
        policy_id="connector-instance-creation-policy.development",
        schema_version="atlas.connector-instance-creation-policy.v1",
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="version.1.0",
        required_installation_receipt_schema="atlas.connector-package-installation-receipt.v1",
        maximum_installation_age_hours=168,
        required_assurance_level=AssuranceLevel.SINGLE_FACTOR,
        required_installation_store_profile_id="installation-store.nonproduction-immutable",
        required_installation_artifact_reference_schema=(
            "atlas.connector-installation-artifact-reference.v1"
        ),
        allowed_sdk_profiles=("atlas.python312.v1",),
        allowed_capability_classes=("C0", "C1"),
        required_initial_state=DISABLED_UNCONFIGURED,
        support_group_id="group.connector-platform-support",
        maximum_instance_key_length=64,
        maximum_display_name_length=120,
        record_schema=INSTANCE_RECORD_SCHEMA,
        signed_by="subject.connector-instance-policy-owner",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    payload = cast(dict[str, object], asdict(policy))
    payload.pop("canonical_digest")
    return replace(
        policy,
        canonical_digest=ConnectorInstanceCreationService._digest(
            ConnectorInstanceCreationService._normalize(payload)
        ),
    )
