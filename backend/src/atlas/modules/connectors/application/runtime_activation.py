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
from atlas.modules.connectors.application.runtime_activation_ports import (
    ConnectorRuntimeActivationError,
    ConnectorRuntimeActivationPolicySource,
    ConnectorRuntimeActivationProfileSource,
    ConnectorRuntimeActivationRepository,
    ConnectorRuntimeActivationSource,
    ConnectorRuntimeActivator,
)
from atlas.modules.connectors.application.secret_brokerage_ports import (
    ConnectorSecretBrokerageError,
)
from atlas.modules.connectors.domain.credential_assignment import ConnectorCredentialProfileSnapshot
from atlas.modules.connectors.domain.runtime_activation import (
    ENABLED_RUNTIME_HEALTHY,
    ConnectorRuntimeActivationInstruction,
    ConnectorRuntimeActivationPolicySnapshot,
    ConnectorRuntimeActivationProfileSnapshot,
    ConnectorRuntimeActivationReceipt,
    ConnectorRuntimeActivationRecord,
)
from atlas.modules.connectors.domain.runtime_trust import ConnectorRuntimeTrustGrantRecord
from atlas.modules.connectors.domain.secret_brokerage import (
    ENABLED_SECRET_BROKERAGE_GOVERNED,
    ConnectorSecretBrokerageAuthorizationRecord,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

RUNTIME_ACTIVATION_CREATE_PERMISSION = "connectors.runtime-activations.create"
RUNTIME_ACTIVATION_READ_PERMISSION = "connectors.runtime-activations.read"
RUNTIME_ACTIVATION_SCHEMA = "atlas.connector-runtime-activation.v1"


class ConnectorRuntimeActivationService:
    def __init__(
        self,
        *,
        repository: ConnectorRuntimeActivationRepository,
        source: ConnectorRuntimeActivationSource,
        profile_source: ConnectorRuntimeActivationProfileSource,
        policy_source: ConnectorRuntimeActivationPolicySource,
        activator: ConnectorRuntimeActivator,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._source = source
        self._profile_source = profile_source
        self._policy_source = policy_source
        self._activator = activator
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    @property
    def repository(self) -> ConnectorRuntimeActivationRepository:
        return self._repository

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_brokerage_authorization_id: str,
        source_brokerage_authorization_digest: str,
        package_digest: str,
        activation_profile_id: str,
        activation_profile_digest: str,
        activation_policy_id: str,
        activation_policy_digest: str,
        purpose: str,
        activation_boundary_acknowledged: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorRuntimeActivationRecord:
        self._require_enterprise_human(actor)
        if not activation_boundary_acknowledged:
            raise ConnectorRuntimeActivationError("runtime_activation_acknowledgement_required")
        purpose = purpose.strip()
        if not 20 <= len(purpose) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise ConnectorRuntimeActivationError("runtime_activation_request_invalid")
        fingerprint = self._digest(
            {
                "source_brokerage_authorization_id": source_brokerage_authorization_id,
                "source_brokerage_authorization_digest": source_brokerage_authorization_digest,
                "package_digest": package_digest,
                "activation_profile_id": activation_profile_id,
                "activation_profile_digest": activation_profile_digest,
                "activation_policy_id": activation_policy_id,
                "activation_policy_digest": activation_policy_digest,
                "purpose": purpose,
            }
        )
        existing = await self._repository.get_by_create_key(
            activated_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            return self._reuse(existing, actor, fingerprint)
        try:
            (
                source,
                runtime_trust,
                credential_profile,
                source_actors,
            ) = await self._source.runtime_activation_source(
                authorization_id=source_brokerage_authorization_id
            )
        except ConnectorSecretBrokerageError as error:
            raise ConnectorRuntimeActivationError("runtime_activation_source_not_found") from error
        profile = await self._profile_source.get_by_id(profile_id=activation_profile_id)
        policy = await self._policy_source.get_by_id(policy_id=activation_policy_id)
        if profile is None or policy is None:
            raise ConnectorRuntimeActivationError("runtime_activation_evidence_not_found")
        self._verify_snapshot(profile, "profile")
        self._verify_snapshot(policy, "policy")
        self._require_scope(actor, source.organization_id, source.environment_id)
        now = self._clock()
        self._verify_activation(
            actor=actor,
            source=source,
            runtime_trust=runtime_trust,
            credential_profile=credential_profile,
            profile=profile,
            policy=policy,
            source_digest=source_brokerage_authorization_digest,
            package_digest=package_digest,
            profile_digest=activation_profile_digest,
            policy_digest=activation_policy_digest,
            now=now,
        )
        separated = source_actors | {
            profile.signed_by,
            policy.signed_by,
            profile.activation_adapter_attestor_id,
        }
        if actor.subject_id in separated:
            raise ConnectorRuntimeActivationError("runtime_activation_separation_required")

        seed = self._digest([source.authorization_id, profile.profile_id, profile.canonical_digest])
        activation_id = f"connector-runtime-activation.{seed[:24]}"
        instruction = ConnectorRuntimeActivationInstruction(
            activation_id=activation_id,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            source_brokerage_authorization_id=source.authorization_id,
            source_brokerage_authorization_digest=source.canonical_digest,
            package_digest=source.package_digest,
            activation_profile_digest=profile.canonical_digest,
            activation_policy_digest=policy.canonical_digest,
            activation_adapter_id=profile.activation_adapter_id,
            runner_identity_digest=profile.runner_identity_digest,
            image_digest=profile.image_digest,
            workload_identity_digest=profile.workload_identity_digest,
            startup_timeout_seconds=profile.startup_timeout_seconds,
            health_probe_ids=profile.health_probe_ids,
        )

        async with self._mutation_lock:
            prior = await self._repository.get_by_brokerage_authorization(
                source_brokerage_authorization_id=source.authorization_id
            )
            if prior is not None:
                if (
                    prior.activated_by == actor.subject_id
                    and prior.request_fingerprint == fingerprint
                ):
                    return replace(prior, reused=True)
                raise ConnectorRuntimeActivationError("runtime_activation_source_conflict")
            await self._audit(
                actor,
                correlation_id,
                "connector_runtime_activation_requested",
                source.instance_id,
                idempotency_key,
                (("activation_profile_digest", profile.canonical_digest),),
            )
            try:
                receipt = await self._activator.activate(instruction)
                self._verify_receipt(receipt, instruction, profile)
                record = self._record(
                    source=source,
                    runtime_trust=runtime_trust,
                    profile=profile,
                    policy=policy,
                    receipt=receipt,
                    actor=actor,
                    purpose=purpose,
                    fingerprint=fingerprint,
                    idempotency_key=idempotency_key,
                )
                await self._audit(
                    actor,
                    correlation_id,
                    "connector_runtime_activation_completed",
                    record.activation_id,
                    idempotency_key,
                    (("instance_state", record.instance_state),),
                )
            except Exception as error:
                await self._activator.compensate(activation_id=activation_id)
                if isinstance(error, ConnectorRuntimeActivationError):
                    raise
                raise ConnectorRuntimeActivationError("runtime_activation_failed") from error
            if not await self._repository.add(record):
                raced = await self._repository.get_by_create_key(
                    activated_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    await self._activator.compensate(activation_id=activation_id)
                    raise ConnectorRuntimeActivationError("runtime_activation_record_conflict")
                self._verify_record(raced)
                return replace(raced, reused=True)
        return record

    async def get(
        self, *, actor: AuthenticatedSubject, activation_id: str, correlation_id: str
    ) -> ConnectorRuntimeActivationRecord:
        self._require_enterprise_human(actor)
        record = await self._repository.get(activation_id=activation_id)
        if record is None:
            raise ConnectorRuntimeActivationError("runtime_activation_record_not_found")
        self._verify_record(record)
        self._require_scope(actor, record.organization_id, record.environment_id)
        await self._audit(
            actor,
            correlation_id,
            "connector_runtime_activation_read",
            record.activation_id,
            None,
            (),
            permission_id=RUNTIME_ACTIVATION_READ_PERMISSION,
        )
        return record

    async def target_session_source(
        self, *, activation_id: str
    ) -> tuple[
        ConnectorRuntimeActivationRecord,
        ConnectorSecretBrokerageAuthorizationRecord,
        ConnectorRuntimeTrustGrantRecord,
        ConnectorCredentialProfileSnapshot,
        frozenset[str],
    ]:
        record = await self._repository.get(activation_id=activation_id)
        if record is None:
            raise ConnectorRuntimeActivationError("runtime_activation_record_not_found")
        self._verify_record(record)
        (
            source,
            runtime_trust,
            credential_profile,
            source_actors,
        ) = await self._source.runtime_activation_source(
            authorization_id=record.source_brokerage_authorization_id
        )
        if (
            record.source_brokerage_authorization_digest != source.canonical_digest
            or record.package_digest != source.package_digest
            or record.instance_id != source.instance_id
            or record.runtime_profile_digest != runtime_trust.runtime_profile_digest
            or record.instance_state != ENABLED_RUNTIME_HEALTHY
            or not record.runtime_health_verified
            or not record.eligible_for_target_session_authorization
            or record.target_connected
            or record.target_connection_authorized
            or record.capability_invocation_authorized
            or record.capability_invoked
            or record.execution_authorized
            or record.deployment_approved
            or record.infrastructure_mutation_performed
        ):
            raise ConnectorRuntimeActivationError("runtime_activation_target_session_invalid")
        return (
            record,
            source,
            runtime_trust,
            credential_profile,
            source_actors | {record.activated_by},
        )

    async def close(self) -> None:
        await self._repository.close()

    def _record(
        self,
        *,
        source: ConnectorSecretBrokerageAuthorizationRecord,
        runtime_trust: ConnectorRuntimeTrustGrantRecord,
        profile: ConnectorRuntimeActivationProfileSnapshot,
        policy: ConnectorRuntimeActivationPolicySnapshot,
        receipt: ConnectorRuntimeActivationReceipt,
        actor: AuthenticatedSubject,
        purpose: str,
        fingerprint: str,
        idempotency_key: str,
    ) -> ConnectorRuntimeActivationRecord:
        record = ConnectorRuntimeActivationRecord(
            activation_id=receipt.activation_id,
            schema_version=RUNTIME_ACTIVATION_SCHEMA,
            version=1,
            source_brokerage_authorization_id=source.authorization_id,
            source_brokerage_authorization_digest=source.canonical_digest,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            package_digest=source.package_digest,
            connector_id=source.connector_id,
            release_version=source.release_version,
            manifest_digest=source.manifest_digest,
            instance_id=source.instance_id,
            instance_key=source.instance_key,
            display_name=source.display_name,
            runtime_profile_digest=source.runtime_profile_digest,
            runner_identity_digest=profile.runner_identity_digest,
            image_digest=profile.image_digest,
            workload_identity_digest=profile.workload_identity_digest,
            activation_profile_id=profile.profile_id,
            activation_profile_digest=profile.canonical_digest,
            activation_policy_id=policy.policy_id,
            activation_policy_digest=policy.canonical_digest,
            activation_policy_version=policy.policy_version,
            activation_adapter_id=profile.activation_adapter_id,
            health_probe_results=receipt.health_probe_results,
            instance_state=ENABLED_RUNTIME_HEALTHY,
            activated_by=actor.subject_id,
            purpose=purpose,
            activated_at=receipt.started_at,
            healthy_at=receipt.healthy_at,
            canonical_digest="0" * 64,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
        )
        return replace(record, canonical_digest=self._digest(self._record_payload(record)))

    @staticmethod
    def _verify_activation(
        *,
        actor: AuthenticatedSubject,
        source: ConnectorSecretBrokerageAuthorizationRecord,
        runtime_trust: ConnectorRuntimeTrustGrantRecord,
        credential_profile: ConnectorCredentialProfileSnapshot,
        profile: ConnectorRuntimeActivationProfileSnapshot,
        policy: ConnectorRuntimeActivationPolicySnapshot,
        source_digest: str,
        package_digest: str,
        profile_digest: str,
        policy_digest: str,
        now: datetime,
    ) -> None:
        if (
            source.canonical_digest != source_digest
            or source.package_digest != package_digest
            or profile.canonical_digest != profile_digest
            or policy.canonical_digest != policy_digest
            or policy.required_brokerage_schema != source.schema_version
            or policy.required_profile_schema != profile.schema_version
            or policy.activation_schema != RUNTIME_ACTIVATION_SCHEMA
            or profile.signed_by != policy.required_profile_signer_id
            or profile.organization_id != source.organization_id
            or profile.environment_id != source.environment_id
            or policy.organization_id != source.organization_id
            or policy.environment_id != source.environment_id
            or profile.package_digest != source.package_digest
            or profile.connector_id != source.connector_id
            or profile.release_version != source.release_version
            or profile.manifest_digest != source.manifest_digest
            or profile.instance_id != source.instance_id
            or profile.source_brokerage_authorization_digest != source.canonical_digest
            or profile.runtime_profile_digest != source.runtime_profile_digest
            or profile.runner_identity_digest
            != ConnectorRuntimeActivationService._identifier_digest(runtime_trust.runner_runtime_id)
            or profile.image_digest != runtime_trust.runner_image_digest
            or profile.workload_identity_digest
            != ConnectorRuntimeActivationService._identifier_digest(
                runtime_trust.runner_workload_identity_id
            )
            or profile.isolation_profile_digest
            != ConnectorRuntimeActivationService._identifier_digest(
                runtime_trust.isolation_profile_id
            )
            or profile.filesystem_policy_digest
            != ConnectorRuntimeActivationService._identifier_digest(
                runtime_trust.filesystem_policy_id
            )
            or profile.egress_policy_digest
            != ConnectorRuntimeActivationService._identifier_digest(runtime_trust.egress_policy_id)
            or profile.delivery_policy_id != source.delivery_policy_id
            or profile.lease_policy_id != source.lease_policy_id
            or profile.activation_adapter_id not in policy.allowed_activation_adapter_ids
            or profile.activation_adapter_attestor_id
            != policy.required_activation_adapter_attestor_id
            or profile.delivery_policy_id != policy.required_delivery_policy_id
            or profile.lease_policy_id != policy.required_lease_policy_id
            or profile.startup_timeout_seconds > policy.maximum_startup_timeout_seconds
            or profile.health_probe_ids != policy.required_health_probe_ids
            or credential_profile.canonical_digest != source.credential_profile_digest
            or credential_profile.rotation_state != source.rotation_state
            or credential_profile.revocation_state != source.revocation_state
            or credential_profile.next_rotation_at != source.next_rotation_at
            or source.instance_state != ENABLED_SECRET_BROKERAGE_GOVERNED
            or not source.credential_resolution_authorized
            or not source.eligible_for_runtime_activation
            or source.secret_lease_issued
            or source.credentials_resolved
            or source.runner_started
            or source.package_loaded
            or source.target_connection_authorized
            or source.capability_invocation_authorized
            or source.execution_authorized
            or source.deployment_approved
            or source.infrastructure_mutation_performed
            or not policy.issued_at <= now < policy.expires_at
            or not profile.issued_at <= now < profile.expires_at
            or now - source.authorized_at > timedelta(hours=policy.maximum_brokerage_age_hours)
            or now - profile.issued_at > timedelta(hours=policy.maximum_profile_age_hours)
            or actor.assurance_level is not AssuranceLevel.HARDWARE_BACKED
        ):
            raise ConnectorRuntimeActivationError("runtime_activation_invalid")

    @classmethod
    def _verify_snapshot(
        cls,
        snapshot: ConnectorRuntimeActivationProfileSnapshot
        | ConnectorRuntimeActivationPolicySnapshot,
        kind: str,
    ) -> None:
        payload = cast(dict[str, object], asdict(snapshot))
        payload.pop("canonical_digest")
        if cls._digest(cls._normalize(payload)) != snapshot.canonical_digest:
            raise ConnectorRuntimeActivationError(f"runtime_activation_{kind}_integrity_failed")

    @classmethod
    def _verify_receipt(
        cls,
        receipt: ConnectorRuntimeActivationReceipt,
        instruction: ConnectorRuntimeActivationInstruction,
        profile: ConnectorRuntimeActivationProfileSnapshot,
    ) -> None:
        payload = cast(dict[str, object], asdict(receipt))
        payload.pop("canonical_digest")
        if (
            cls._digest(cls._normalize(payload)) != receipt.canonical_digest
            or receipt.activation_id != instruction.activation_id
            or receipt.organization_id != instruction.organization_id
            or receipt.environment_id != instruction.environment_id
            or receipt.source_brokerage_authorization_digest
            != instruction.source_brokerage_authorization_digest
            or receipt.package_digest != instruction.package_digest
            or receipt.activation_profile_digest != instruction.activation_profile_digest
            or receipt.activation_policy_digest != instruction.activation_policy_digest
            or receipt.activation_adapter_id != instruction.activation_adapter_id
            or receipt.runner_identity_digest != profile.runner_identity_digest
            or receipt.image_digest != profile.image_digest
            or receipt.workload_identity_digest != profile.workload_identity_digest
            or tuple(item.probe_id for item in receipt.health_probe_results)
            != instruction.health_probe_ids
            or receipt.signed_by != profile.activation_adapter_attestor_id
        ):
            raise ConnectorRuntimeActivationError("runtime_activation_receipt_invalid")

    def _reuse(
        self,
        record: ConnectorRuntimeActivationRecord,
        actor: AuthenticatedSubject,
        fingerprint: str,
    ) -> ConnectorRuntimeActivationRecord:
        if record.activated_by != actor.subject_id or record.request_fingerprint != fingerprint:
            raise ConnectorRuntimeActivationError("runtime_activation_idempotency_conflict")
        self._verify_record(record)
        return replace(record, reused=True)

    @classmethod
    def _verify_record(cls, record: ConnectorRuntimeActivationRecord) -> None:
        if cls._digest(cls._record_payload(record)) != record.canonical_digest:
            raise ConnectorRuntimeActivationError("runtime_activation_record_integrity_failed")

    @classmethod
    def _record_payload(cls, record: ConnectorRuntimeActivationRecord) -> dict[str, object]:
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
    def _identifier_digest(value: str) -> str:
        return sha256(value.encode("ascii")).hexdigest()

    @staticmethod
    def _require_enterprise_human(actor: AuthenticatedSubject) -> None:
        if (
            actor.kind is not SubjectKind.HUMAN
            or actor.authentication_method is AuthenticationMethod.DEVELOPMENT
            or actor.assurance_level is not AssuranceLevel.HARDWARE_BACKED
        ):
            raise ConnectorRuntimeActivationError(
                "runtime_activation_enterprise_human_hardware_mfa_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise ConnectorRuntimeActivationError("runtime_activation_record_not_found")

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        idempotency_key: str | None,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = RUNTIME_ACTIVATION_CREATE_PERMISSION,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.runtime-activation",
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
                resource_type="resource.connector.runtime-activation",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=metadata,
            )
        )


def _signed_snapshot(
    snapshot: ConnectorRuntimeActivationProfileSnapshot | ConnectorRuntimeActivationPolicySnapshot,
) -> str:
    payload = cast(dict[str, object], asdict(snapshot))
    payload.pop("canonical_digest")
    return ConnectorRuntimeActivationService._digest(
        ConnectorRuntimeActivationService._normalize(payload)
    )


def build_connector_runtime_activation_profile(
    *,
    source: ConnectorSecretBrokerageAuthorizationRecord,
    runtime_trust: ConnectorRuntimeTrustGrantRecord,
    issued_at: datetime,
    expires_at: datetime,
) -> ConnectorRuntimeActivationProfileSnapshot:
    snapshot = ConnectorRuntimeActivationProfileSnapshot(
        profile_id="connector-runtime-activation-profile.development-synthetic",
        schema_version="atlas.connector-runtime-activation-profile.v1",
        version=1,
        organization_id=source.organization_id,
        environment_id=source.environment_id,
        package_digest=source.package_digest,
        connector_id=source.connector_id,
        release_version=source.release_version,
        manifest_digest=source.manifest_digest,
        instance_id=source.instance_id,
        source_brokerage_authorization_digest=source.canonical_digest,
        runtime_profile_digest=source.runtime_profile_digest,
        runner_identity_digest=ConnectorRuntimeActivationService._identifier_digest(
            runtime_trust.runner_runtime_id
        ),
        image_digest=runtime_trust.runner_image_digest,
        workload_identity_digest=ConnectorRuntimeActivationService._identifier_digest(
            runtime_trust.runner_workload_identity_id
        ),
        isolation_profile_digest=ConnectorRuntimeActivationService._identifier_digest(
            runtime_trust.isolation_profile_id
        ),
        filesystem_policy_digest=ConnectorRuntimeActivationService._identifier_digest(
            runtime_trust.filesystem_policy_id
        ),
        egress_policy_digest=ConnectorRuntimeActivationService._identifier_digest(
            runtime_trust.egress_policy_id
        ),
        delivery_policy_id=source.delivery_policy_id,
        lease_policy_id=source.lease_policy_id,
        activation_adapter_id="connector-runtime-activator.synthetic",
        activation_adapter_attestor_id=("subject.connector-runtime-activation-adapter-attestor"),
        startup_timeout_seconds=30,
        health_probe_ids=("health.package-loaded", "health.runtime-responsive"),
        telemetry_policy_digest=ConnectorRuntimeActivationService._identifier_digest(
            runtime_trust.telemetry_policy_id
        ),
        resource_policy_digest=ConnectorRuntimeActivationService._identifier_digest(
            runtime_trust.resource_limit_profile_id
        ),
        signed_by="subject.connector-runtime-activation-profile-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(snapshot, canonical_digest=_signed_snapshot(snapshot))


def build_development_connector_runtime_activation_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> ConnectorRuntimeActivationPolicySnapshot:
    snapshot = ConnectorRuntimeActivationPolicySnapshot(
        policy_id="connector-runtime-activation-policy.development",
        schema_version="atlas.connector-runtime-activation-policy.v1",
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-v1",
        required_brokerage_schema="atlas.connector-secret-brokerage-authorization.v1",
        required_profile_schema="atlas.connector-runtime-activation-profile.v1",
        required_profile_signer_id="subject.connector-runtime-activation-profile-signer",
        allowed_activation_adapter_ids=("connector-runtime-activator.synthetic",),
        required_activation_adapter_attestor_id=(
            "subject.connector-runtime-activation-adapter-attestor"
        ),
        required_delivery_policy_id="secret-delivery-policy.ephemeral-disabled-until-brokered",
        required_lease_policy_id="secret-lease-policy.single-use-non-renewable",
        maximum_startup_timeout_seconds=60,
        required_health_probe_ids=("health.package-loaded", "health.runtime-responsive"),
        maximum_brokerage_age_hours=24,
        maximum_profile_age_hours=24,
        required_assurance_level=AssuranceLevel.HARDWARE_BACKED,
        required_source_state=ENABLED_SECRET_BROKERAGE_GOVERNED,
        activation_schema=RUNTIME_ACTIVATION_SCHEMA,
        signed_by="subject.connector-runtime-activation-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(snapshot, canonical_digest=_signed_snapshot(snapshot))
