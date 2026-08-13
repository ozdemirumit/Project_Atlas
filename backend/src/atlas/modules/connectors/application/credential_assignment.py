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
from atlas.modules.connectors.application.credential_assignment_ports import (
    ConnectorCredentialAssignmentError,
    ConnectorCredentialAssignmentPolicySource,
    ConnectorCredentialAssignmentRepository,
    ConnectorCredentialProfileSource,
    ConnectorCredentialTargetSource,
)
from atlas.modules.connectors.application.target_configuration_ports import (
    ConnectorTargetConfigurationError,
)
from atlas.modules.connectors.domain.credential_assignment import (
    DISABLED_CREDENTIALS_ASSIGNED,
    ConnectorCredentialAssignmentPolicySnapshot,
    ConnectorCredentialAssignmentRecord,
    ConnectorCredentialProfileSnapshot,
)
from atlas.modules.connectors.domain.package_registration import (
    ConnectorPackageRegistrationRecord,
)
from atlas.modules.connectors.domain.target_configuration import (
    DISABLED_TARGET_CONFIGURED,
    ConnectorTargetConfigurationBinding,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    SubjectKind,
    assurance_satisfies_policy,
)

CREDENTIAL_ASSIGNMENT_CREATE_PERMISSION = "connectors.credential-assignments.create"
CREDENTIAL_ASSIGNMENT_READ_PERMISSION = "connectors.credential-assignments.read"
CREDENTIAL_ASSIGNMENT_SCHEMA = "atlas.connector-credential-assignment.v1"


class ConnectorCredentialAssignmentService:
    def __init__(
        self,
        *,
        repository: ConnectorCredentialAssignmentRepository,
        target_source: ConnectorCredentialTargetSource,
        credential_profile_source: ConnectorCredentialProfileSource,
        policy_source: ConnectorCredentialAssignmentPolicySource,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._target_source = target_source
        self._credential_profile_source = credential_profile_source
        self._policy_source = policy_source
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    @property
    def repository(self) -> ConnectorCredentialAssignmentRepository:
        return self._repository

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_target_binding_id: str,
        source_target_binding_digest: str,
        package_digest: str,
        credential_profile_id: str,
        credential_profile_digest: str,
        credential_policy_id: str,
        credential_policy_digest: str,
        purpose: str,
        acknowledged_assignment_grants_no_secret_access_enablement_or_runtime_authority: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorCredentialAssignmentRecord:
        self._require_human(actor)
        if not acknowledged_assignment_grants_no_secret_access_enablement_or_runtime_authority:
            raise ConnectorCredentialAssignmentError(
                "credential_assignment_acknowledgement_required"
            )
        purpose = purpose.strip()
        if not 20 <= len(purpose) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise ConnectorCredentialAssignmentError("credential_assignment_request_invalid")
        fingerprint = self._digest(
            {
                "source_target_binding_id": source_target_binding_id,
                "source_target_binding_digest": source_target_binding_digest,
                "package_digest": package_digest,
                "credential_profile_id": credential_profile_id,
                "credential_profile_digest": credential_profile_digest,
                "credential_policy_id": credential_policy_id,
                "credential_policy_digest": credential_policy_digest,
                "purpose": purpose,
            }
        )
        existing = await self._repository.get_by_create_key(
            assigned_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            return self._reuse(existing, actor, fingerprint)
        try:
            (
                binding,
                _registration,
                source_actors,
            ) = await self._target_source.credential_assignment_source(
                binding_id=source_target_binding_id
            )
        except ConnectorTargetConfigurationError as error:
            raise ConnectorCredentialAssignmentError(
                "credential_assignment_source_not_found"
            ) from error
        profile = await self._credential_profile_source.get_by_id(profile_id=credential_profile_id)
        if profile is None:
            raise ConnectorCredentialAssignmentError("credential_assignment_profile_not_found")
        policy = await self._policy_source.get_by_id(policy_id=credential_policy_id)
        if policy is None:
            raise ConnectorCredentialAssignmentError("credential_assignment_policy_not_found")
        self._verify_profile(profile)
        self._verify_policy(policy)
        self._require_scope(actor, binding.organization_id, binding.environment_id)
        now = self._clock()
        self._verify_assignment(
            actor=actor,
            binding=binding,
            profile=profile,
            policy=policy,
            source_target_binding_digest=source_target_binding_digest,
            package_digest=package_digest,
            credential_profile_digest=credential_profile_digest,
            credential_policy_digest=credential_policy_digest,
            now=now,
        )
        if actor.subject_id in source_actors | {profile.signed_by, policy.signed_by}:
            raise ConnectorCredentialAssignmentError("credential_assignment_separation_required")

        async with self._mutation_lock:
            prior = await self._repository.get_by_target_binding(
                source_target_binding_id=binding.binding_id
            )
            if prior is not None:
                if (
                    prior.assigned_by == actor.subject_id
                    and prior.request_fingerprint == fingerprint
                ):
                    return replace(prior, reused=True)
                raise ConnectorCredentialAssignmentError("credential_assignment_target_conflict")
            await self._audit(
                actor,
                correlation_id,
                "connector_credential_assignment_requested",
                binding.instance_id,
                idempotency_key,
                (("credential_profile_digest", profile.canonical_digest),),
            )
            seed = self._digest([binding.binding_id, profile.profile_id, profile.canonical_digest])
            record = ConnectorCredentialAssignmentRecord(
                assignment_id=f"connector-credential-assignment.{seed[:24]}",
                schema_version=CREDENTIAL_ASSIGNMENT_SCHEMA,
                version=1,
                source_target_binding_id=binding.binding_id,
                source_target_binding_digest=binding.canonical_digest,
                organization_id=binding.organization_id,
                environment_id=binding.environment_id,
                package_digest=binding.package_digest,
                connector_id=binding.connector_id,
                release_version=binding.release_version,
                manifest_digest=binding.manifest_digest,
                instance_id=binding.instance_id,
                instance_key=binding.instance_key,
                display_name=binding.display_name,
                owner_id=binding.owner_id,
                target_profile_id=binding.target_profile_id,
                target_profile_digest=binding.target_profile_digest,
                site_id=binding.site_id,
                target_type=binding.target_type,
                target_product=binding.target_product,
                credential_profile_id=profile.profile_id,
                credential_profile_digest=profile.canonical_digest,
                credential_class=profile.credential_class,
                authentication_method=profile.authentication_method,
                vendor_role=profile.vendor_role,
                privilege_class=profile.privilege_class,
                rotation_state=profile.rotation_state,
                revocation_state=profile.revocation_state,
                next_rotation_at=profile.next_rotation_at,
                credential_policy_id=policy.policy_id,
                credential_policy_digest=policy.canonical_digest,
                credential_policy_version=policy.policy_version,
                assignment_version=1,
                instance_state=policy.required_effective_state,
                assigned_by=actor.subject_id,
                purpose=purpose,
                assigned_at=now,
                canonical_digest="0" * 64,
                request_fingerprint=fingerprint,
                idempotency_key=idempotency_key,
            )
            record = replace(record, canonical_digest=self._digest(self._record_payload(record)))
            await self._audit(
                actor,
                correlation_id,
                "connector_credential_assignment_completed",
                record.assignment_id,
                idempotency_key,
                (("instance_state", record.instance_state),),
            )
            if not await self._repository.add(record):
                raced = await self._repository.get_by_create_key(
                    assigned_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    raise ConnectorCredentialAssignmentError(
                        "credential_assignment_record_conflict"
                    )
                self._verify_record(raced)
                return replace(raced, reused=True)
        return record

    async def get(
        self, *, actor: AuthenticatedSubject, assignment_id: str, correlation_id: str
    ) -> ConnectorCredentialAssignmentRecord:
        self._require_human(actor)
        record = await self._repository.get(assignment_id=assignment_id)
        if record is None:
            raise ConnectorCredentialAssignmentError("credential_assignment_record_not_found")
        self._verify_record(record)
        self._require_scope(actor, record.organization_id, record.environment_id)
        await self._audit(
            actor,
            correlation_id,
            "connector_credential_assignment_read",
            record.assignment_id,
            None,
            (),
            permission_id=CREDENTIAL_ASSIGNMENT_READ_PERMISSION,
        )
        return record

    async def configuration_validation_source(
        self, *, assignment_id: str
    ) -> tuple[
        ConnectorCredentialAssignmentRecord,
        ConnectorPackageRegistrationRecord,
        frozenset[str],
    ]:
        record = await self._repository.get(assignment_id=assignment_id)
        if record is None:
            raise ConnectorCredentialAssignmentError("credential_assignment_record_not_found")
        self._verify_record(record)
        profile = await self._credential_profile_source.get_by_id(
            profile_id=record.credential_profile_id
        )
        policy = await self._policy_source.get_by_id(policy_id=record.credential_policy_id)
        if profile is None or policy is None:
            raise ConnectorCredentialAssignmentError("credential_assignment_source_not_found")
        self._verify_profile(profile)
        self._verify_policy(policy)
        try:
            (
                binding,
                registration,
                source_actors,
            ) = await self._target_source.credential_assignment_source(
                binding_id=record.source_target_binding_id
            )
        except ConnectorTargetConfigurationError as error:
            raise ConnectorCredentialAssignmentError(
                "credential_assignment_source_not_found"
            ) from error
        if (
            record.source_target_binding_digest != binding.canonical_digest
            or record.package_digest != binding.package_digest
            or record.credential_profile_digest != profile.canonical_digest
            or record.credential_policy_digest != policy.canonical_digest
            or record.organization_id != profile.organization_id
            or record.environment_id != profile.environment_id
            or record.target_profile_id != profile.target_profile_id
            or record.site_id != profile.site_id
            or record.target_type != profile.target_type
            or record.target_product != profile.target_product
        ):
            raise ConnectorCredentialAssignmentError("credential_assignment_source_invalid")
        return (
            record,
            registration,
            frozenset(source_actors | {record.assigned_by, profile.signed_by, policy.signed_by}),
        )

    async def secret_brokerage_source(
        self, *, credential_profile_id: str, instance_id: str
    ) -> tuple[
        ConnectorCredentialAssignmentRecord,
        ConnectorCredentialProfileSnapshot,
        frozenset[str],
    ]:
        candidate = await self._repository.get_by_profile_and_instance(
            credential_profile_id=credential_profile_id,
            instance_id=instance_id,
        )
        if candidate is None:
            raise ConnectorCredentialAssignmentError("credential_assignment_record_not_found")
        record, _, source_actors = await self.configuration_validation_source(
            assignment_id=candidate.assignment_id
        )
        profile = await self._credential_profile_source.get_by_id(
            profile_id=record.credential_profile_id
        )
        if profile is None:
            raise ConnectorCredentialAssignmentError("credential_assignment_source_not_found")
        self._verify_profile(profile)
        if (
            profile.profile_id != credential_profile_id
            or profile.canonical_digest != record.credential_profile_digest
            or profile.target_profile_id != record.target_profile_id
            or profile.site_id != record.site_id
            or profile.organization_id != record.organization_id
            or profile.environment_id != record.environment_id
        ):
            raise ConnectorCredentialAssignmentError("credential_assignment_source_invalid")
        return record, profile, source_actors

    async def close(self) -> None:
        await self._repository.close()

    def _reuse(
        self,
        record: ConnectorCredentialAssignmentRecord,
        actor: AuthenticatedSubject,
        fingerprint: str,
    ) -> ConnectorCredentialAssignmentRecord:
        if record.assigned_by != actor.subject_id or record.request_fingerprint != fingerprint:
            raise ConnectorCredentialAssignmentError("credential_assignment_idempotency_conflict")
        self._verify_record(record)
        return replace(record, reused=True)

    @classmethod
    def _verify_profile(cls, profile: ConnectorCredentialProfileSnapshot) -> None:
        payload = cast(dict[str, object], asdict(profile))
        payload.pop("canonical_digest")
        if cls._digest(cls._normalize(payload)) != profile.canonical_digest:
            raise ConnectorCredentialAssignmentError(
                "credential_assignment_profile_integrity_failed"
            )

    @classmethod
    def _verify_policy(cls, policy: ConnectorCredentialAssignmentPolicySnapshot) -> None:
        payload = cast(dict[str, object], asdict(policy))
        payload.pop("canonical_digest")
        if cls._digest(cls._normalize(payload)) != policy.canonical_digest:
            raise ConnectorCredentialAssignmentError(
                "credential_assignment_policy_integrity_failed"
            )

    @staticmethod
    def _verify_assignment(
        *,
        actor: AuthenticatedSubject,
        binding: ConnectorTargetConfigurationBinding,
        profile: ConnectorCredentialProfileSnapshot,
        policy: ConnectorCredentialAssignmentPolicySnapshot,
        source_target_binding_digest: str,
        package_digest: str,
        credential_profile_digest: str,
        credential_policy_digest: str,
        now: datetime,
    ) -> None:
        if (
            binding.canonical_digest != source_target_binding_digest
            or binding.package_digest != package_digest
            or profile.canonical_digest != credential_profile_digest
            or policy.canonical_digest != credential_policy_digest
            or policy.required_target_binding_schema != binding.schema_version
            or policy.required_credential_profile_schema != profile.schema_version
            or policy.assignment_record_schema != CREDENTIAL_ASSIGNMENT_SCHEMA
            or profile.signed_by != policy.required_credential_profile_signer_id
            or profile.organization_id != binding.organization_id
            or profile.environment_id != binding.environment_id
            or policy.organization_id != binding.organization_id
            or policy.environment_id != binding.environment_id
            or profile.site_id != binding.site_id
            or profile.target_profile_id != binding.target_profile_id
            or profile.target_id != binding.target_id
            or profile.target_type != binding.target_type
            or profile.target_product != binding.target_product
            or binding.connector_id not in profile.allowed_connector_ids
            or binding.release_version not in profile.allowed_release_versions
            or profile.secret_store_profile_id not in policy.allowed_secret_store_profile_ids
            or profile.credential_class not in policy.allowed_credential_classes
            or profile.authentication_method not in policy.allowed_authentication_methods
            or profile.privilege_class not in policy.allowed_privilege_classes
            or profile.rotation_state != policy.required_rotation_state
            or profile.revocation_state != policy.required_revocation_state
            or binding.instance_state != DISABLED_TARGET_CONFIGURED
            or not binding.eligible_for_credential_governance
            or binding.credentials_resolved
            or not policy.issued_at <= now < policy.expires_at
            or not profile.issued_at <= now < profile.expires_at
            or now - binding.bound_at > timedelta(hours=policy.maximum_target_binding_age_hours)
            or now - profile.issued_at
            > timedelta(hours=policy.maximum_credential_profile_age_hours)
            or profile.next_rotation_at - now
            < timedelta(hours=policy.minimum_rotation_window_hours)
            or not assurance_satisfies_policy(
                actor.assurance_level, policy.required_assurance_level
            )
        ):
            raise ConnectorCredentialAssignmentError("credential_assignment_invalid")

    @classmethod
    def _verify_record(cls, record: ConnectorCredentialAssignmentRecord) -> None:
        if cls._digest(cls._record_payload(record)) != record.canonical_digest:
            raise ConnectorCredentialAssignmentError(
                "credential_assignment_record_integrity_failed"
            )

    @classmethod
    def _record_payload(cls, record: ConnectorCredentialAssignmentRecord) -> dict[str, object]:
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
    def _require_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise ConnectorCredentialAssignmentError("credential_assignment_human_required")

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise ConnectorCredentialAssignmentError("credential_assignment_record_not_found")

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        idempotency_key: str | None,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = CREDENTIAL_ASSIGNMENT_CREATE_PERMISSION,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.credential-assignment",
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
                resource_type="resource.connector.credential-assignment",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=metadata,
            )
        )


def _signed_snapshot(
    snapshot: ConnectorCredentialProfileSnapshot | ConnectorCredentialAssignmentPolicySnapshot,
) -> str:
    payload = cast(dict[str, object], asdict(snapshot))
    payload.pop("canonical_digest")
    return ConnectorCredentialAssignmentService._digest(
        ConnectorCredentialAssignmentService._normalize(payload)
    )


def build_development_connector_credential_profile(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> ConnectorCredentialProfileSnapshot:
    profile = ConnectorCredentialProfileSnapshot(
        profile_id="connector-credential-profile.development-storage-reader",
        schema_version="atlas.connector-credential-profile.v1",
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        site_id="site.local",
        target_profile_id="connector-target-profile.development-storage",
        target_id="target.storage.development",
        target_type="target-type.storage-management",
        target_product="Synthetic Storage",
        secret_reference_id="secret-reference.connector.storage-reader",
        secret_store_profile_id="secret-store-profile.enterprise",
        credential_class="credential.vendor-api",
        authentication_method="authentication.api-token",
        vendor_role="vendor-role.storage-reader",
        privilege_class="privilege.read-only",
        allowed_connector_ids=("connector.synthetic-storage",),
        allowed_release_versions=("version.0.1.0-draft",),
        rotation_state="rotation.current",
        revocation_state="revocation.active",
        next_rotation_at=issued_at + timedelta(hours=96),
        signed_by="subject.connector-credential-profile-owner",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(profile, canonical_digest=_signed_snapshot(profile))


def build_development_connector_credential_assignment_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> ConnectorCredentialAssignmentPolicySnapshot:
    policy = ConnectorCredentialAssignmentPolicySnapshot(
        policy_id="connector-credential-assignment-policy.development",
        schema_version="atlas.connector-credential-assignment-policy.v1",
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="version.1.0",
        required_target_binding_schema="atlas.connector-target-configuration-binding.v1",
        required_credential_profile_schema="atlas.connector-credential-profile.v1",
        maximum_target_binding_age_hours=168,
        maximum_credential_profile_age_hours=168,
        required_assurance_level=AssuranceLevel.SINGLE_FACTOR,
        required_credential_profile_signer_id="subject.connector-credential-profile-owner",
        allowed_secret_store_profile_ids=("secret-store-profile.enterprise",),
        allowed_credential_classes=("credential.vendor-api",),
        allowed_authentication_methods=("authentication.api-token",),
        allowed_privilege_classes=("privilege.read-only",),
        required_rotation_state="rotation.current",
        required_revocation_state="revocation.active",
        minimum_rotation_window_hours=24,
        required_effective_state=DISABLED_CREDENTIALS_ASSIGNED,
        assignment_record_schema=CREDENTIAL_ASSIGNMENT_SCHEMA,
        signed_by="subject.connector-credential-assignment-policy-owner",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(policy, canonical_digest=_signed_snapshot(policy))
