from __future__ import annotations

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
from atlas.modules.connectors.application.bounded_invocation_ports import (
    ConnectorBoundedInvocationAdapter,
    ConnectorBoundedInvocationError,
    ConnectorBoundedInvocationPermissionAuthorizer,
    ConnectorBoundedInvocationPolicySource,
    ConnectorBoundedInvocationRepository,
    ConnectorBoundedInvocationSource,
    ConnectorBoundedInvocationUncertainError,
)
from atlas.modules.connectors.application.invocation_authorization_ports import (
    ConnectorInvocationAuthorizationError,
)
from atlas.modules.connectors.domain.bounded_invocation import (
    ENABLED_BOUNDED_CAPABILITY_INVOCATION_COMPLETED,
    ConnectorBoundedInvocationInstruction,
    ConnectorBoundedInvocationPolicySnapshot,
    ConnectorBoundedInvocationReceipt,
    ConnectorBoundedInvocationRecord,
    ConnectorInvocationConsumptionClaim,
)
from atlas.modules.connectors.domain.invocation_authorization import (
    ENABLED_CAPABILITY_INVOCATION_GOVERNED,
    ConnectorInvocationAuthorizationRecord,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    SubjectKind,
    assurance_satisfies_policy,
)

BOUNDED_INVOCATION_CREATE_PERMISSION = "connectors.bounded-invocations.create"
BOUNDED_INVOCATION_READ_PERMISSION = "connectors.bounded-invocations.read"
BOUNDED_INVOCATION_SCHEMA = "atlas.connector-bounded-invocation.v1"
CONSUMPTION_CLAIM_SCHEMA = "atlas.connector-invocation-consumption-claim.v1"


class ConnectorBoundedInvocationService:
    def __init__(
        self,
        *,
        repository: ConnectorBoundedInvocationRepository,
        source: ConnectorBoundedInvocationSource,
        policy_source: ConnectorBoundedInvocationPolicySource,
        permission_authorizer: ConnectorBoundedInvocationPermissionAuthorizer,
        adapter: ConnectorBoundedInvocationAdapter,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._source = source
        self._policy_source = policy_source
        self._permission_authorizer = permission_authorizer
        self._adapter = adapter
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def repository(self) -> ConnectorBoundedInvocationRepository:
        return self._repository

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_authorization_id: str,
        source_authorization_digest: str,
        package_digest: str,
        invocation_policy_id: str,
        invocation_policy_digest: str,
        purpose: str,
        irreversible_consumption_acknowledged: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorBoundedInvocationRecord:
        self._require_enterprise_human(actor)
        if not irreversible_consumption_acknowledged:
            raise ConnectorBoundedInvocationError("bounded_invocation_acknowledgement_required")
        purpose = purpose.strip()
        if not 20 <= len(purpose) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise ConnectorBoundedInvocationError("bounded_invocation_request_invalid")
        request_binding_digest = self._digest(
            {
                "source_authorization_id": source_authorization_id,
                "source_authorization_digest": source_authorization_digest,
                "package_digest": package_digest,
                "invocation_policy_id": invocation_policy_id,
                "invocation_policy_digest": invocation_policy_digest,
                "purpose": purpose,
            }
        )
        idempotency_digest = self._digest([actor.subject_id, idempotency_key])
        existing_claim = await self._repository.get_claim_by_idempotency(
            claimed_by=actor.subject_id, idempotency_digest=idempotency_digest
        )
        if existing_claim is not None:
            return await self._reuse(
                existing_claim,
                actor,
                request_binding_digest,
                idempotency_digest,
            )
        try:
            source, source_actors = await self._source.bounded_invocation_source(
                authorization_id=source_authorization_id
            )
        except ConnectorInvocationAuthorizationError as error:
            raise ConnectorBoundedInvocationError("bounded_invocation_source_not_found") from error
        policy = await self._policy_source.get_by_id(policy_id=invocation_policy_id)
        if policy is None:
            raise ConnectorBoundedInvocationError("bounded_invocation_policy_not_found")
        self._verify_snapshot(policy)
        now = self._clock()
        self._require_scope(actor, source.organization_id, source.environment_id)
        self._verify_source(
            actor=actor,
            source=source,
            policy=policy,
            source_digest=source_authorization_digest,
            package_digest=package_digest,
            policy_digest=invocation_policy_digest,
            now=now,
        )
        if actor.subject_id in source_actors | {
            policy.signed_by,
            policy.required_adapter_attestor_id,
        }:
            raise ConnectorBoundedInvocationError("bounded_invocation_separation_required")
        await self._permission_authorizer.authorize(
            actor=actor,
            permission_id=source.required_permission,
            capability_id=source.capability_id,
            capability_class=source.capability_class,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            correlation_id=correlation_id,
        )
        seed = self._digest(
            [source.authorization_id, policy.canonical_digest, source.input_envelope_digest]
        )
        invocation_id = f"connector-bounded-invocation.{seed[:24]}"
        await self._audit(
            actor,
            correlation_id,
            "connector_bounded_invocation_requested",
            source.authorization_id,
            (("capability_id", source.capability_id),),
        )
        claim = ConnectorInvocationConsumptionClaim(
            claim_id=f"connector-invocation-consumption-claim.{seed[:24]}",
            schema_version=CONSUMPTION_CLAIM_SCHEMA,
            version=1,
            source_authorization_id=source.authorization_id,
            source_authorization_digest=source.canonical_digest,
            invocation_id=invocation_id,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            claimed_by=actor.subject_id,
            purpose=purpose,
            claimed_at=now,
            request_binding_digest=request_binding_digest,
            idempotency_digest=idempotency_digest,
            canonical_digest="0" * 64,
        )
        claim = replace(claim, canonical_digest=self._digest(self._claim_payload(claim)))
        if not await self._repository.claim(claim):
            prior = await self._repository.get_claim_by_authorization(
                source_authorization_id=source.authorization_id
            )
            if prior is None:
                raise ConnectorBoundedInvocationUncertainError(
                    "bounded_invocation_consumption_uncertain"
                )
            return await self._reuse(
                prior,
                actor,
                request_binding_digest,
                idempotency_digest,
            )
        await self._audit(
            actor,
            correlation_id,
            "connector_bounded_invocation_authorization_consumed",
            claim.claim_id,
            (("invocation_id", invocation_id),),
        )
        instruction = ConnectorBoundedInvocationInstruction(
            invocation_id=invocation_id,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            source_authorization_id=source.authorization_id,
            source_authorization_digest=source.canonical_digest,
            package_digest=source.package_digest,
            connector_id=source.connector_id,
            instance_id=source.instance_id,
            capability_id=source.capability_id,
            capability_class=source.capability_class,
            required_permission=source.required_permission,
            invocation_profile_digest=source.invocation_profile_digest,
            input_envelope_id=source.input_envelope_id,
            input_envelope_digest=source.input_envelope_digest,
            input_schema_digest=source.input_schema_digest,
            output_schema_digest=source.output_schema_digest,
            result_policy_digest=source.result_policy_digest,
            maximum_timeout_seconds=min(
                source.maximum_timeout_seconds,
                policy.maximum_invocation_duration_seconds,
            ),
            maximum_output_bytes=min(
                source.maximum_output_bytes,
                policy.maximum_output_bytes,
            ),
            maximum_observations=policy.maximum_observations,
            invocation_policy_digest=policy.canonical_digest,
        )
        try:
            receipt = await self._adapter.invoke(instruction)
        except ConnectorBoundedInvocationError as error:
            result_code = (
                "connector_bounded_invocation_uncertain"
                if isinstance(error, ConnectorBoundedInvocationUncertainError)
                else "connector_bounded_invocation_failed"
            )
            await self._audit(
                actor,
                correlation_id,
                result_code,
                invocation_id,
                (("authorization_consumed", "true"),),
            )
            raise
        except Exception as error:
            await self._audit(
                actor,
                correlation_id,
                "connector_bounded_invocation_uncertain",
                invocation_id,
                (("authorization_consumed", "true"),),
            )
            raise ConnectorBoundedInvocationUncertainError(
                "bounded_invocation_outcome_uncertain"
            ) from error
        try:
            self._verify_receipt(instruction, receipt, policy)
        except ConnectorBoundedInvocationUncertainError:
            await self._audit(
                actor,
                correlation_id,
                "connector_bounded_invocation_uncertain",
                invocation_id,
                (("authorization_consumed", "true"),),
            )
            raise
        record = ConnectorBoundedInvocationRecord(
            invocation_id=invocation_id,
            schema_version=BOUNDED_INVOCATION_SCHEMA,
            version=1,
            consumption_claim_id=claim.claim_id,
            source_authorization_id=source.authorization_id,
            source_authorization_digest=source.canonical_digest,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            package_digest=source.package_digest,
            connector_id=source.connector_id,
            release_version=source.release_version,
            manifest_digest=source.manifest_digest,
            instance_id=source.instance_id,
            instance_key=source.instance_key,
            display_name=source.display_name,
            capability_id=source.capability_id,
            capability_class=source.capability_class,
            required_permission=source.required_permission,
            invocation_profile_id=source.invocation_profile_id,
            invocation_profile_digest=source.invocation_profile_digest,
            input_envelope_id=source.input_envelope_id,
            input_envelope_digest=source.input_envelope_digest,
            input_schema_digest=source.input_schema_digest,
            output_schema_digest=source.output_schema_digest,
            result_policy_digest=source.result_policy_digest,
            invocation_policy_id=policy.policy_id,
            invocation_policy_digest=policy.canonical_digest,
            invocation_policy_version=policy.policy_version,
            invocation_adapter_id=receipt.adapter_id,
            normalized_redacted_result_digest=(receipt.normalized_redacted_result_digest),
            observation_count=receipt.observation_count,
            output_bytes=receipt.output_bytes,
            instance_state=ENABLED_BOUNDED_CAPABILITY_INVOCATION_COMPLETED,
            invoked_by=actor.subject_id,
            purpose=purpose,
            started_at=receipt.started_at,
            completed_at=receipt.completed_at,
            canonical_digest="0" * 64,
        )
        record = replace(record, canonical_digest=self._digest(self._record_payload(record)))
        await self._audit(
            actor,
            correlation_id,
            "connector_bounded_invocation_completed",
            record.invocation_id,
            (("instance_state", record.instance_state),),
        )
        if not await self._repository.add(record):
            raced = await self._repository.get_by_authorization(
                source_authorization_id=source.authorization_id
            )
            if raced is None or raced.canonical_digest != record.canonical_digest:
                raise ConnectorBoundedInvocationUncertainError(
                    "bounded_invocation_completion_persistence_uncertain"
                )
            return replace(raced, reused=True)
        return record

    async def get(
        self, *, actor: AuthenticatedSubject, invocation_id: str, correlation_id: str
    ) -> ConnectorBoundedInvocationRecord:
        self._require_enterprise_human(actor)
        record = await self._repository.get(invocation_id=invocation_id)
        if record is None:
            raise ConnectorBoundedInvocationError("bounded_invocation_record_not_found")
        self._verify_record(record)
        claim = await self._repository.get_claim_by_authorization(
            source_authorization_id=record.source_authorization_id
        )
        if claim is None:
            raise ConnectorBoundedInvocationError("bounded_invocation_claim_not_found")
        self._verify_claim(claim)
        self._require_scope(actor, record.organization_id, record.environment_id)
        await self._audit(
            actor,
            correlation_id,
            "connector_bounded_invocation_read",
            record.invocation_id,
            (),
            permission_id=BOUNDED_INVOCATION_READ_PERMISSION,
        )
        return record

    async def evidence_ingestion_source(
        self, *, invocation_id: str
    ) -> tuple[ConnectorBoundedInvocationRecord, frozenset[str]]:
        record = await self._repository.get(invocation_id=invocation_id)
        if record is None:
            raise ConnectorBoundedInvocationError("bounded_invocation_record_not_found")
        self._verify_record(record)
        claim = await self._repository.get_claim_by_authorization(
            source_authorization_id=record.source_authorization_id
        )
        if claim is None:
            raise ConnectorBoundedInvocationError("bounded_invocation_claim_not_found")
        self._verify_claim(claim)
        try:
            authorization, source_actors = await self._source.bounded_invocation_source(
                authorization_id=record.source_authorization_id
            )
        except ConnectorInvocationAuthorizationError as error:
            raise ConnectorBoundedInvocationError("bounded_invocation_source_not_found") from error
        policy = await self._policy_source.get_by_id(policy_id=record.invocation_policy_id)
        if policy is None:
            raise ConnectorBoundedInvocationError("bounded_invocation_policy_not_found")
        self._verify_snapshot(policy)
        if (
            authorization.canonical_digest != record.source_authorization_digest
            or authorization.package_digest != record.package_digest
            or authorization.connector_id != record.connector_id
            or authorization.instance_id != record.instance_id
            or authorization.capability_id != record.capability_id
            or authorization.required_permission != record.required_permission
            or authorization.output_schema_digest != record.output_schema_digest
            or authorization.result_policy_digest != record.result_policy_digest
            or policy.canonical_digest != record.invocation_policy_digest
            or claim.claim_id != record.consumption_claim_id
            or claim.source_authorization_id != record.source_authorization_id
            or claim.source_authorization_digest != record.source_authorization_digest
            or claim.invocation_id != record.invocation_id
            or claim.claimed_by != record.invoked_by
            or claim.purpose != record.purpose
            or record.instance_state != ENABLED_BOUNDED_CAPABILITY_INVOCATION_COMPLETED
            or not record.authorization_consumed
            or not record.capability_invoked
            or not record.result_received
            or not record.result_validated
            or not record.result_redacted
            or not record.target_session_closed
            or not record.delivery_channel_closed
            or not record.lease_revocation_confirmed
            or record.target_connected
            or record.reusable_session_available
            or record.scheduled
            or record.evidence_ingested
            or record.execution_authorized
            or record.deployment_approved
            or record.infrastructure_mutation_performed
            or record.observation_count < 1
        ):
            raise ConnectorBoundedInvocationError("bounded_invocation_evidence_source_invalid")
        return record, source_actors | {
            record.invoked_by,
            policy.signed_by,
            policy.required_adapter_attestor_id,
        }

    async def close(self) -> None:
        await self._repository.close()

    async def _reuse(
        self,
        claim: ConnectorInvocationConsumptionClaim,
        actor: AuthenticatedSubject,
        request_binding_digest: str,
        idempotency_digest: str,
    ) -> ConnectorBoundedInvocationRecord:
        self._verify_claim(claim)
        if (
            claim.claimed_by != actor.subject_id
            or claim.request_binding_digest != request_binding_digest
            or claim.idempotency_digest != idempotency_digest
        ):
            raise ConnectorBoundedInvocationError("bounded_invocation_idempotency_conflict")
        self._require_scope(actor, claim.organization_id, claim.environment_id)
        record = await self._repository.get(invocation_id=claim.invocation_id)
        if record is None:
            raise ConnectorBoundedInvocationError("bounded_invocation_authorization_consumed")
        self._verify_record(record)
        return replace(record, reused=True)

    @staticmethod
    def _verify_source(
        *,
        actor: AuthenticatedSubject,
        source: ConnectorInvocationAuthorizationRecord,
        policy: ConnectorBoundedInvocationPolicySnapshot,
        source_digest: str,
        package_digest: str,
        policy_digest: str,
        now: datetime,
    ) -> None:
        if (
            source.canonical_digest != source_digest
            or source.package_digest != package_digest
            or policy.canonical_digest != policy_digest
            or policy.required_source_schema != source.schema_version
            or policy.required_source_state != source.instance_state
            or source.instance_state != ENABLED_CAPABILITY_INVOCATION_GOVERNED
            or source.capability_class not in policy.allowed_capability_classes
            or not source.single_use
            or source.renewable
            or source.consumed
            or not source.capability_invocation_authorized
            or not source.eligible_for_bounded_capability_invocation
            or source.target_connected
            or source.capability_invoked
            or source.scheduled
            or source.result_received
            or source.evidence_ingested
            or source.execution_authorized
            or source.deployment_approved
            or source.infrastructure_mutation_performed
            or not source.authorized_at <= now < source.expires_at
            or now - source.authorized_at
            > timedelta(minutes=policy.maximum_authorization_age_minutes)
            or not policy.issued_at <= now < policy.expires_at
            or not assurance_satisfies_policy(
                actor.assurance_level, policy.required_assurance_level
            )
        ):
            raise ConnectorBoundedInvocationError("bounded_invocation_source_invalid")

    @classmethod
    def _verify_receipt(
        cls,
        instruction: ConnectorBoundedInvocationInstruction,
        receipt: ConnectorBoundedInvocationReceipt,
        policy: ConnectorBoundedInvocationPolicySnapshot,
    ) -> None:
        if (
            cls._receipt_digest(receipt) != receipt.canonical_digest
            or receipt.invocation_id != instruction.invocation_id
            or receipt.schema_version != policy.required_receipt_schema
            or receipt.adapter_id != policy.required_adapter_id
            or receipt.attested_by != policy.required_adapter_attestor_id
            or receipt.source_authorization_digest != instruction.source_authorization_digest
            or receipt.capability_id != instruction.capability_id
            or receipt.invocation_profile_digest != instruction.invocation_profile_digest
            or receipt.input_envelope_digest != instruction.input_envelope_digest
            or receipt.result_schema_digest != instruction.output_schema_digest
            or receipt.result_policy_digest != instruction.result_policy_digest
            or receipt.observation_count > instruction.maximum_observations
            or receipt.output_bytes > instruction.maximum_output_bytes
            or receipt.completed_at - receipt.started_at
            > timedelta(seconds=instruction.maximum_timeout_seconds)
        ):
            raise ConnectorBoundedInvocationUncertainError("bounded_invocation_receipt_invalid")

    @classmethod
    def _verify_snapshot(cls, policy: ConnectorBoundedInvocationPolicySnapshot) -> None:
        payload = cast(dict[str, object], asdict(policy))
        digest = str(payload.pop("canonical_digest"))
        if cls._digest(cls._normalize(payload)) != digest:
            raise ConnectorBoundedInvocationError("bounded_invocation_policy_integrity_failed")

    @classmethod
    def _verify_claim(cls, claim: ConnectorInvocationConsumptionClaim) -> None:
        if cls._digest(cls._claim_payload(claim)) != claim.canonical_digest:
            raise ConnectorBoundedInvocationError("bounded_invocation_claim_integrity_failed")

    @classmethod
    def _verify_record(cls, record: ConnectorBoundedInvocationRecord) -> None:
        if cls._digest(cls._record_payload(record)) != record.canonical_digest:
            raise ConnectorBoundedInvocationError("bounded_invocation_record_integrity_failed")

    @classmethod
    def _claim_payload(cls, claim: ConnectorInvocationConsumptionClaim) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(claim))
        payload.pop("canonical_digest")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _record_payload(cls, record: ConnectorBoundedInvocationRecord) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(record))
        for field in ("canonical_digest", "reused"):
            payload.pop(field)
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _receipt_digest(cls, receipt: ConnectorBoundedInvocationReceipt) -> str:
        payload = cast(dict[str, object], asdict(receipt))
        payload.pop("canonical_digest")
        return cls._digest(cls._normalize(payload))

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
            raise ConnectorBoundedInvocationError("bounded_invocation_human_required")

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise ConnectorBoundedInvocationError("bounded_invocation_record_not_found")

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = BOUNDED_INVOCATION_CREATE_PERMISSION,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.bounded-invocation",
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
                resource_type="resource.connector.bounded-invocation",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=metadata,
            )
        )


def _signed_policy(policy: ConnectorBoundedInvocationPolicySnapshot) -> str:
    payload = cast(dict[str, object], asdict(policy))
    payload.pop("canonical_digest")
    return ConnectorBoundedInvocationService._digest(
        ConnectorBoundedInvocationService._normalize(payload)
    )


def build_development_connector_bounded_invocation_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> ConnectorBoundedInvocationPolicySnapshot:
    policy = ConnectorBoundedInvocationPolicySnapshot(
        policy_id="connector-bounded-invocation-policy.development",
        schema_version="atlas.connector-bounded-invocation-policy.v1",
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-v1",
        required_source_schema="atlas.connector-invocation-authorization.v1",
        required_source_state=ENABLED_CAPABILITY_INVOCATION_GOVERNED,
        allowed_capability_classes=("C0", "C1"),
        maximum_authorization_age_minutes=15,
        maximum_invocation_duration_seconds=60,
        maximum_output_bytes=524_288,
        maximum_observations=100,
        required_adapter_id="connector-bounded-invocation-adapter.synthetic",
        required_adapter_attestor_id=("subject.connector-bounded-invocation-adapter-attestor"),
        required_receipt_schema="atlas.connector-bounded-invocation-receipt.v1",
        required_assurance_level=AssuranceLevel.SINGLE_FACTOR,
        signed_by="subject.connector-bounded-invocation-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(policy, canonical_digest=_signed_policy(policy))
