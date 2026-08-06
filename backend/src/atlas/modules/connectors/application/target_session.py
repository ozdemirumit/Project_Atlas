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
)
from atlas.modules.connectors.application.target_session_ports import (
    ConnectorTargetSessionAdapter,
    ConnectorTargetSessionError,
    ConnectorTargetSessionPolicySource,
    ConnectorTargetSessionProfileSource,
    ConnectorTargetSessionRepository,
    ConnectorTargetSessionSource,
)
from atlas.modules.connectors.domain.credential_assignment import ConnectorCredentialProfileSnapshot
from atlas.modules.connectors.domain.runtime_activation import (
    ENABLED_RUNTIME_HEALTHY,
    ConnectorRuntimeActivationRecord,
)
from atlas.modules.connectors.domain.runtime_trust import ConnectorRuntimeTrustGrantRecord
from atlas.modules.connectors.domain.secret_brokerage import (
    ConnectorSecretBrokerageAuthorizationRecord,
)
from atlas.modules.connectors.domain.target_session import (
    ENABLED_TARGET_SESSION_VERIFIED,
    ConnectorTargetSessionInstruction,
    ConnectorTargetSessionPolicySnapshot,
    ConnectorTargetSessionProfileSnapshot,
    ConnectorTargetSessionReceipt,
    ConnectorTargetSessionVerificationRecord,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

TARGET_SESSION_CREATE_PERMISSION = "connectors.target-session-verifications.create"
TARGET_SESSION_READ_PERMISSION = "connectors.target-session-verifications.read"
TARGET_SESSION_SCHEMA = "atlas.connector-target-session-verification.v1"


class ConnectorTargetSessionService:
    def __init__(
        self,
        *,
        repository: ConnectorTargetSessionRepository,
        source: ConnectorTargetSessionSource,
        profile_source: ConnectorTargetSessionProfileSource,
        policy_source: ConnectorTargetSessionPolicySource,
        adapter: ConnectorTargetSessionAdapter,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._source = source
        self._profile_source = profile_source
        self._policy_source = policy_source
        self._adapter = adapter
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    @property
    def repository(self) -> ConnectorTargetSessionRepository:
        return self._repository

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_runtime_activation_id: str,
        source_runtime_activation_digest: str,
        package_digest: str,
        session_profile_id: str,
        session_profile_digest: str,
        session_policy_id: str,
        session_policy_digest: str,
        purpose: str,
        bounded_session_acknowledged: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorTargetSessionVerificationRecord:
        self._require_enterprise_human(actor)
        if not bounded_session_acknowledged:
            raise ConnectorTargetSessionError("target_session_acknowledgement_required")
        purpose = purpose.strip()
        if not 20 <= len(purpose) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise ConnectorTargetSessionError("target_session_request_invalid")
        fingerprint = self._digest(
            {
                "source_runtime_activation_id": source_runtime_activation_id,
                "source_runtime_activation_digest": source_runtime_activation_digest,
                "package_digest": package_digest,
                "session_profile_id": session_profile_id,
                "session_profile_digest": session_profile_digest,
                "session_policy_id": session_policy_id,
                "session_policy_digest": session_policy_digest,
                "purpose": purpose,
            }
        )
        existing = await self._repository.get_by_create_key(
            verified_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            return self._reuse(existing, actor, fingerprint)
        try:
            (
                activation,
                brokerage,
                runtime_trust,
                credential_profile,
                source_actors,
            ) = await self._source.target_session_source(activation_id=source_runtime_activation_id)
        except ConnectorRuntimeActivationError as error:
            raise ConnectorTargetSessionError("target_session_source_not_found") from error
        profile = await self._profile_source.get_by_id(profile_id=session_profile_id)
        policy = await self._policy_source.get_by_id(policy_id=session_policy_id)
        if profile is None or policy is None:
            raise ConnectorTargetSessionError("target_session_evidence_not_found")
        self._verify_snapshot(profile, "profile")
        self._verify_snapshot(policy, "policy")
        self._require_scope(actor, activation.organization_id, activation.environment_id)
        self._verify_session(
            actor=actor,
            activation=activation,
            brokerage=brokerage,
            runtime_trust=runtime_trust,
            credential_profile=credential_profile,
            profile=profile,
            policy=policy,
            source_digest=source_runtime_activation_digest,
            package_digest=package_digest,
            profile_digest=session_profile_digest,
            policy_digest=session_policy_digest,
            now=self._clock(),
        )
        if actor.subject_id in (
            source_actors
            | {profile.signed_by, policy.signed_by, profile.session_adapter_attestor_id}
        ):
            raise ConnectorTargetSessionError("target_session_separation_required")

        seed = self._digest(
            [activation.activation_id, profile.profile_id, profile.canonical_digest]
        )
        verification_id = f"connector-target-session-verification.{seed[:24]}"
        instruction = ConnectorTargetSessionInstruction(
            verification_id=verification_id,
            organization_id=activation.organization_id,
            environment_id=activation.environment_id,
            source_runtime_activation_id=activation.activation_id,
            source_runtime_activation_digest=activation.canonical_digest,
            package_digest=activation.package_digest,
            session_profile_digest=profile.canonical_digest,
            session_policy_digest=policy.canonical_digest,
            session_adapter_id=profile.session_adapter_id,
            expected_target_identity_digest=profile.expected_target_identity_digest,
            protocol_classification=profile.protocol_classification,
            session_timeout_seconds=profile.session_timeout_seconds,
            connectivity_check_ids=profile.connectivity_check_ids,
        )
        async with self._mutation_lock:
            prior = await self._repository.get_by_runtime_activation(
                source_runtime_activation_id=activation.activation_id
            )
            if prior is not None:
                if (
                    prior.verified_by == actor.subject_id
                    and prior.request_fingerprint == fingerprint
                ):
                    return replace(prior, reused=True)
                raise ConnectorTargetSessionError("target_session_source_conflict")
            await self._audit(
                actor,
                correlation_id,
                "connector_target_session_requested",
                activation.instance_id,
                idempotency_key,
                (("session_profile_digest", profile.canonical_digest),),
            )
            try:
                receipt = await self._adapter.verify(instruction)
                self._verify_receipt(receipt, instruction, profile, policy)
                record = self._record(
                    activation=activation,
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
                    "connector_target_session_completed",
                    record.verification_id,
                    idempotency_key,
                    (("instance_state", record.instance_state),),
                )
            except Exception as error:
                await self._adapter.compensate(verification_id=verification_id)
                if isinstance(error, ConnectorTargetSessionError):
                    raise
                raise ConnectorTargetSessionError("target_session_failed") from error
            if not await self._repository.add(record):
                raced = await self._repository.get_by_create_key(
                    verified_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    await self._adapter.compensate(verification_id=verification_id)
                    raise ConnectorTargetSessionError("target_session_record_conflict")
                self._verify_record(raced)
                return replace(raced, reused=True)
        return record

    async def get(
        self, *, actor: AuthenticatedSubject, verification_id: str, correlation_id: str
    ) -> ConnectorTargetSessionVerificationRecord:
        self._require_enterprise_human(actor)
        record = await self._repository.get(verification_id=verification_id)
        if record is None:
            raise ConnectorTargetSessionError("target_session_record_not_found")
        self._verify_record(record)
        self._require_scope(actor, record.organization_id, record.environment_id)
        await self._audit(
            actor,
            correlation_id,
            "connector_target_session_read",
            record.verification_id,
            None,
            (),
            permission_id=TARGET_SESSION_READ_PERMISSION,
        )
        return record

    async def close(self) -> None:
        await self._repository.close()

    def _record(
        self,
        *,
        activation: ConnectorRuntimeActivationRecord,
        runtime_trust: ConnectorRuntimeTrustGrantRecord,
        profile: ConnectorTargetSessionProfileSnapshot,
        policy: ConnectorTargetSessionPolicySnapshot,
        receipt: ConnectorTargetSessionReceipt,
        actor: AuthenticatedSubject,
        purpose: str,
        fingerprint: str,
        idempotency_key: str,
    ) -> ConnectorTargetSessionVerificationRecord:
        record = ConnectorTargetSessionVerificationRecord(
            verification_id=receipt.verification_id,
            schema_version=TARGET_SESSION_SCHEMA,
            version=1,
            source_runtime_activation_id=activation.activation_id,
            source_runtime_activation_digest=activation.canonical_digest,
            organization_id=activation.organization_id,
            environment_id=activation.environment_id,
            package_digest=activation.package_digest,
            connector_id=activation.connector_id,
            release_version=activation.release_version,
            manifest_digest=activation.manifest_digest,
            instance_id=activation.instance_id,
            instance_key=activation.instance_key,
            display_name=activation.display_name,
            target_profile_digest=runtime_trust.target_profile_digest,
            target_identity_digest=receipt.target_identity_digest,
            expected_target_product=profile.expected_target_product,
            protocol_classification=receipt.protocol_classification,
            tls_classification=receipt.tls_classification,
            session_profile_id=profile.profile_id,
            session_profile_digest=profile.canonical_digest,
            session_policy_id=policy.policy_id,
            session_policy_digest=policy.canonical_digest,
            session_policy_version=policy.policy_version,
            session_adapter_id=profile.session_adapter_id,
            connectivity_check_results=receipt.connectivity_check_results,
            instance_state=ENABLED_TARGET_SESSION_VERIFIED,
            verified_by=actor.subject_id,
            purpose=purpose,
            verified_at=receipt.verified_at,
            canonical_digest="0" * 64,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
        )
        return replace(record, canonical_digest=self._digest(self._record_payload(record)))

    @staticmethod
    def _verify_session(
        *,
        actor: AuthenticatedSubject,
        activation: ConnectorRuntimeActivationRecord,
        brokerage: ConnectorSecretBrokerageAuthorizationRecord,
        runtime_trust: ConnectorRuntimeTrustGrantRecord,
        credential_profile: ConnectorCredentialProfileSnapshot,
        profile: ConnectorTargetSessionProfileSnapshot,
        policy: ConnectorTargetSessionPolicySnapshot,
        source_digest: str,
        package_digest: str,
        profile_digest: str,
        policy_digest: str,
        now: datetime,
    ) -> None:
        expected_identity = ConnectorTargetSessionService._digest(
            [runtime_trust.target_profile_digest, runtime_trust.target_product]
        )
        if (
            activation.canonical_digest != source_digest
            or activation.package_digest != package_digest
            or profile.canonical_digest != profile_digest
            or policy.canonical_digest != policy_digest
            or policy.required_activation_schema != activation.schema_version
            or policy.required_profile_schema != profile.schema_version
            or policy.verification_schema != TARGET_SESSION_SCHEMA
            or profile.signed_by != policy.required_profile_signer_id
            or profile.organization_id != activation.organization_id
            or profile.environment_id != activation.environment_id
            or policy.organization_id != activation.organization_id
            or policy.environment_id != activation.environment_id
            or profile.package_digest != activation.package_digest
            or profile.connector_id != activation.connector_id
            or profile.release_version != activation.release_version
            or profile.manifest_digest != activation.manifest_digest
            or profile.instance_id != activation.instance_id
            or profile.source_runtime_activation_digest != activation.canonical_digest
            or profile.target_profile_digest != runtime_trust.target_profile_digest
            or profile.expected_target_product != runtime_trust.target_product
            or profile.expected_target_identity_digest != expected_identity
            or profile.tls_policy_digest
            != ConnectorTargetSessionService._identifier_digest("tls-policy.enterprise-validated")
            or profile.certificate_policy_digest
            != ConnectorTargetSessionService._identifier_digest(
                "certificate-policy.trusted-chain-and-identity"
            )
            or profile.network_path_policy_digest
            != ConnectorTargetSessionService._identifier_digest(runtime_trust.egress_policy_id)
            or profile.workload_identity_digest != activation.workload_identity_digest
            or profile.credential_profile_digest != brokerage.credential_profile_digest
            or profile.delivery_policy_id != brokerage.delivery_policy_id
            or profile.lease_policy_id != brokerage.lease_policy_id
            or profile.session_adapter_id not in policy.allowed_session_adapter_ids
            or profile.session_adapter_attestor_id != policy.required_session_adapter_attestor_id
            or profile.protocol_classification != policy.required_protocol_classification
            or policy.required_source_state != ENABLED_RUNTIME_HEALTHY
            or profile.delivery_policy_id != policy.required_delivery_policy_id
            or profile.lease_policy_id != policy.required_lease_policy_id
            or profile.session_timeout_seconds > policy.maximum_session_timeout_seconds
            or profile.connectivity_check_ids != policy.required_connectivity_check_ids
            or credential_profile.canonical_digest != brokerage.credential_profile_digest
            or credential_profile.rotation_state != brokerage.rotation_state
            or credential_profile.revocation_state != brokerage.revocation_state
            or credential_profile.next_rotation_at != brokerage.next_rotation_at
            or credential_profile.privilege_class != "privilege.read-only"
            or activation.instance_state != ENABLED_RUNTIME_HEALTHY
            or not activation.runtime_health_verified
            or not activation.eligible_for_target_session_authorization
            or activation.target_connected
            or activation.target_connection_authorized
            or activation.capability_invocation_authorized
            or activation.capability_invoked
            or activation.execution_authorized
            or activation.deployment_approved
            or activation.infrastructure_mutation_performed
            or not policy.issued_at <= now < policy.expires_at
            or not profile.issued_at <= now < profile.expires_at
            or now - activation.healthy_at > timedelta(hours=policy.maximum_activation_age_hours)
            or now - profile.issued_at > timedelta(hours=policy.maximum_profile_age_hours)
            or actor.assurance_level is not AssuranceLevel.HARDWARE_BACKED
        ):
            raise ConnectorTargetSessionError("target_session_invalid")

    @classmethod
    def _verify_snapshot(
        cls,
        snapshot: ConnectorTargetSessionProfileSnapshot | ConnectorTargetSessionPolicySnapshot,
        kind: str,
    ) -> None:
        payload = cast(dict[str, object], asdict(snapshot))
        payload.pop("canonical_digest")
        if cls._digest(cls._normalize(payload)) != snapshot.canonical_digest:
            raise ConnectorTargetSessionError(f"target_session_{kind}_integrity_failed")

    @classmethod
    def _verify_receipt(
        cls,
        receipt: ConnectorTargetSessionReceipt,
        instruction: ConnectorTargetSessionInstruction,
        profile: ConnectorTargetSessionProfileSnapshot,
        policy: ConnectorTargetSessionPolicySnapshot,
    ) -> None:
        payload = cast(dict[str, object], asdict(receipt))
        payload.pop("canonical_digest")
        if (
            cls._digest(cls._normalize(payload)) != receipt.canonical_digest
            or receipt.verification_id != instruction.verification_id
            or receipt.organization_id != instruction.organization_id
            or receipt.environment_id != instruction.environment_id
            or receipt.source_runtime_activation_digest
            != instruction.source_runtime_activation_digest
            or receipt.package_digest != instruction.package_digest
            or receipt.session_profile_digest != instruction.session_profile_digest
            or receipt.session_policy_digest != instruction.session_policy_digest
            or receipt.session_adapter_id != instruction.session_adapter_id
            or receipt.target_identity_digest != profile.expected_target_identity_digest
            or receipt.protocol_classification != profile.protocol_classification
            or receipt.tls_classification != policy.required_tls_classification
            or tuple(item.check_id for item in receipt.connectivity_check_results)
            != instruction.connectivity_check_ids
            or receipt.signed_by != profile.session_adapter_attestor_id
        ):
            raise ConnectorTargetSessionError("target_session_receipt_invalid")

    def _reuse(
        self,
        record: ConnectorTargetSessionVerificationRecord,
        actor: AuthenticatedSubject,
        fingerprint: str,
    ) -> ConnectorTargetSessionVerificationRecord:
        if record.verified_by != actor.subject_id or record.request_fingerprint != fingerprint:
            raise ConnectorTargetSessionError("target_session_idempotency_conflict")
        self._verify_record(record)
        return replace(record, reused=True)

    @classmethod
    def _verify_record(cls, record: ConnectorTargetSessionVerificationRecord) -> None:
        if cls._digest(cls._record_payload(record)) != record.canonical_digest:
            raise ConnectorTargetSessionError("target_session_record_integrity_failed")

    @classmethod
    def _record_payload(cls, record: ConnectorTargetSessionVerificationRecord) -> dict[str, object]:
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
            raise ConnectorTargetSessionError(
                "target_session_enterprise_human_hardware_mfa_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise ConnectorTargetSessionError("target_session_record_not_found")

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        idempotency_key: str | None,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = TARGET_SESSION_CREATE_PERMISSION,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.target-session",
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
                resource_type="resource.connector.target-session-verification",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=metadata,
            )
        )


def _signed_snapshot(
    snapshot: ConnectorTargetSessionProfileSnapshot | ConnectorTargetSessionPolicySnapshot,
) -> str:
    payload = cast(dict[str, object], asdict(snapshot))
    payload.pop("canonical_digest")
    return ConnectorTargetSessionService._digest(ConnectorTargetSessionService._normalize(payload))


def build_connector_target_session_profile(
    *,
    activation: ConnectorRuntimeActivationRecord,
    brokerage: ConnectorSecretBrokerageAuthorizationRecord,
    runtime_trust: ConnectorRuntimeTrustGrantRecord,
    issued_at: datetime,
    expires_at: datetime,
) -> ConnectorTargetSessionProfileSnapshot:
    target_identity_digest = ConnectorTargetSessionService._digest(
        [runtime_trust.target_profile_digest, runtime_trust.target_product]
    )
    snapshot = ConnectorTargetSessionProfileSnapshot(
        profile_id="connector-target-session-profile.development-synthetic",
        schema_version="atlas.connector-target-session-profile.v1",
        version=1,
        organization_id=activation.organization_id,
        environment_id=activation.environment_id,
        package_digest=activation.package_digest,
        connector_id=activation.connector_id,
        release_version=activation.release_version,
        manifest_digest=activation.manifest_digest,
        instance_id=activation.instance_id,
        source_runtime_activation_digest=activation.canonical_digest,
        target_profile_digest=runtime_trust.target_profile_digest,
        expected_target_product=runtime_trust.target_product,
        expected_target_identity_digest=target_identity_digest,
        protocol_classification="protocol.https-read-only",
        tls_policy_digest=ConnectorTargetSessionService._identifier_digest(
            "tls-policy.enterprise-validated"
        ),
        certificate_policy_digest=ConnectorTargetSessionService._identifier_digest(
            "certificate-policy.trusted-chain-and-identity"
        ),
        network_path_policy_digest=ConnectorTargetSessionService._identifier_digest(
            runtime_trust.egress_policy_id
        ),
        workload_identity_digest=activation.workload_identity_digest,
        credential_profile_digest=brokerage.credential_profile_digest,
        delivery_policy_id=brokerage.delivery_policy_id,
        lease_policy_id=brokerage.lease_policy_id,
        session_adapter_id="connector-target-session-adapter.synthetic",
        session_adapter_attestor_id="subject.connector-target-session-adapter-attestor",
        session_timeout_seconds=30,
        connectivity_check_ids=(
            "connectivity.authentication",
            "connectivity.read-only-privilege",
            "connectivity.target-identity",
            "connectivity.tls",
        ),
        signed_by="subject.connector-target-session-profile-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(snapshot, canonical_digest=_signed_snapshot(snapshot))


def build_development_connector_target_session_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> ConnectorTargetSessionPolicySnapshot:
    snapshot = ConnectorTargetSessionPolicySnapshot(
        policy_id="connector-target-session-policy.development",
        schema_version="atlas.connector-target-session-policy.v1",
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-v1",
        required_activation_schema="atlas.connector-runtime-activation.v1",
        required_profile_schema="atlas.connector-target-session-profile.v1",
        required_profile_signer_id="subject.connector-target-session-profile-signer",
        allowed_session_adapter_ids=("connector-target-session-adapter.synthetic",),
        required_session_adapter_attestor_id=("subject.connector-target-session-adapter-attestor"),
        required_protocol_classification="protocol.https-read-only",
        required_tls_classification="tls.1-3-verified",
        required_delivery_policy_id="secret-delivery-policy.ephemeral-disabled-until-brokered",
        required_lease_policy_id="secret-lease-policy.single-use-non-renewable",
        maximum_session_timeout_seconds=60,
        required_connectivity_check_ids=(
            "connectivity.authentication",
            "connectivity.read-only-privilege",
            "connectivity.target-identity",
            "connectivity.tls",
        ),
        maximum_activation_age_hours=24,
        maximum_profile_age_hours=24,
        required_assurance_level=AssuranceLevel.HARDWARE_BACKED,
        required_source_state=ENABLED_RUNTIME_HEALTHY,
        verification_schema=TARGET_SESSION_SCHEMA,
        signed_by="subject.connector-target-session-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(snapshot, canonical_digest=_signed_snapshot(snapshot))
