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
    ConnectorBoundedInvocationError,
)
from atlas.modules.connectors.application.invocation_evidence_ports import (
    ConnectorInvocationEvidenceAdapter,
    ConnectorInvocationEvidenceError,
    ConnectorInvocationEvidencePermissionAuthorizer,
    ConnectorInvocationEvidencePolicySource,
    ConnectorInvocationEvidenceRepository,
    ConnectorInvocationEvidenceSource,
    ConnectorInvocationEvidenceUncertainError,
)
from atlas.modules.connectors.domain.bounded_invocation import (
    ENABLED_BOUNDED_CAPABILITY_INVOCATION_COMPLETED,
    ConnectorBoundedInvocationRecord,
)
from atlas.modules.connectors.domain.invocation_evidence import (
    ENABLED_INVOCATION_EVIDENCE_INGESTED,
    ConnectorInvocationEvidenceClaim,
    ConnectorInvocationEvidenceInstruction,
    ConnectorInvocationEvidencePolicySnapshot,
    ConnectorInvocationEvidenceReceipt,
    ConnectorInvocationEvidenceRecord,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

INVOCATION_EVIDENCE_CREATE_PERMISSION = "connectors.invocation-evidence.create"
INVOCATION_EVIDENCE_READ_PERMISSION = "connectors.invocation-evidence.read"
INVOCATION_EVIDENCE_SCHEMA = "atlas.connector-invocation-evidence-ingestion.v1"
INVOCATION_EVIDENCE_CLAIM_SCHEMA = "atlas.connector-invocation-evidence-claim.v1"


class ConnectorInvocationEvidenceService:
    def __init__(
        self,
        *,
        repository: ConnectorInvocationEvidenceRepository,
        source: ConnectorInvocationEvidenceSource,
        policy_source: ConnectorInvocationEvidencePolicySource,
        permission_authorizer: ConnectorInvocationEvidencePermissionAuthorizer,
        adapter: ConnectorInvocationEvidenceAdapter,
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
    def repository(self) -> ConnectorInvocationEvidenceRepository:
        return self._repository

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_invocation_id: str,
        source_invocation_digest: str,
        ingestion_policy_id: str,
        ingestion_policy_digest: str,
        purpose: str,
        one_way_ingestion_acknowledged: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorInvocationEvidenceRecord:
        self._require_enterprise_human(actor)
        if not one_way_ingestion_acknowledged:
            raise ConnectorInvocationEvidenceError("invocation_evidence_acknowledgement_required")
        purpose = purpose.strip()
        if not 20 <= len(purpose) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise ConnectorInvocationEvidenceError("invocation_evidence_request_invalid")
        request_binding_digest = self._digest(
            {
                "source_invocation_id": source_invocation_id,
                "source_invocation_digest": source_invocation_digest,
                "ingestion_policy_id": ingestion_policy_id,
                "ingestion_policy_digest": ingestion_policy_digest,
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
            source, source_actors = await self._source.evidence_ingestion_source(
                invocation_id=source_invocation_id
            )
        except ConnectorBoundedInvocationError as error:
            raise ConnectorInvocationEvidenceError(
                "invocation_evidence_source_not_found"
            ) from error
        policy = await self._policy_source.get_by_id(policy_id=ingestion_policy_id)
        if policy is None:
            raise ConnectorInvocationEvidenceError("invocation_evidence_policy_not_found")
        self._verify_snapshot(policy)
        now = self._clock()
        self._require_scope(actor, source.organization_id, source.environment_id)
        self._verify_source(
            source=source,
            policy=policy,
            source_digest=source_invocation_digest,
            policy_digest=ingestion_policy_digest,
            now=now,
        )
        if actor.subject_id in source_actors | {
            policy.signed_by,
            policy.required_adapter_attestor_id,
        }:
            raise ConnectorInvocationEvidenceError("invocation_evidence_separation_required")
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
            [
                source.invocation_id,
                policy.canonical_digest,
                source.normalized_redacted_result_digest,
            ]
        )
        ingestion_id = f"connector-invocation-evidence-ingestion.{seed[:24]}"
        await self._audit(
            actor,
            correlation_id,
            "connector_invocation_evidence_requested",
            source.invocation_id,
            (("capability_id", source.capability_id),),
        )
        claim = ConnectorInvocationEvidenceClaim(
            claim_id=f"connector-invocation-evidence-claim.{seed[:24]}",
            schema_version=INVOCATION_EVIDENCE_CLAIM_SCHEMA,
            version=1,
            source_invocation_id=source.invocation_id,
            source_invocation_digest=source.canonical_digest,
            ingestion_id=ingestion_id,
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
            prior = await self._repository.get_claim_by_invocation(
                source_invocation_id=source.invocation_id
            )
            if prior is None:
                raise ConnectorInvocationEvidenceUncertainError(
                    "invocation_evidence_claim_uncertain"
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
            "connector_invocation_evidence_claimed",
            claim.claim_id,
            (("ingestion_id", ingestion_id),),
        )
        instruction = ConnectorInvocationEvidenceInstruction(
            ingestion_id=ingestion_id,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            source_invocation_id=source.invocation_id,
            source_invocation_digest=source.canonical_digest,
            connector_id=source.connector_id,
            instance_id=source.instance_id,
            capability_id=source.capability_id,
            output_schema_digest=source.output_schema_digest,
            result_policy_digest=source.result_policy_digest,
            normalized_redacted_result_digest=source.normalized_redacted_result_digest,
            source_observation_count=source.observation_count,
            source_output_bytes=source.output_bytes,
            source_started_at=source.started_at,
            source_completed_at=source.completed_at,
            classification=policy.required_classification,
            access_policy_id=policy.access_policy_id,
            access_policy_digest=policy.access_policy_digest,
            retention_policy_id=policy.retention_policy_id,
            retention_policy_digest=policy.retention_policy_digest,
            encryption_profile_id=policy.encryption_profile_id,
            encryption_profile_digest=policy.encryption_profile_digest,
            maximum_evidence_items=policy.maximum_evidence_items,
            maximum_evidence_bytes=policy.maximum_evidence_bytes,
            ingestion_policy_digest=policy.canonical_digest,
        )
        try:
            receipt = await self._adapter.ingest(instruction)
        except ConnectorInvocationEvidenceError as error:
            result_code = (
                "connector_invocation_evidence_uncertain"
                if isinstance(error, ConnectorInvocationEvidenceUncertainError)
                else "connector_invocation_evidence_failed"
            )
            await self._audit(
                actor,
                correlation_id,
                result_code,
                ingestion_id,
                (("claim_persisted", "true"),),
            )
            raise
        except Exception as error:
            await self._audit(
                actor,
                correlation_id,
                "connector_invocation_evidence_uncertain",
                ingestion_id,
                (("claim_persisted", "true"),),
            )
            raise ConnectorInvocationEvidenceUncertainError(
                "invocation_evidence_outcome_uncertain"
            ) from error
        try:
            self._verify_receipt(instruction, receipt, policy)
        except ConnectorInvocationEvidenceUncertainError:
            await self._audit(
                actor,
                correlation_id,
                "connector_invocation_evidence_uncertain",
                ingestion_id,
                (("claim_persisted", "true"),),
            )
            raise
        record = ConnectorInvocationEvidenceRecord(
            ingestion_id=ingestion_id,
            schema_version=INVOCATION_EVIDENCE_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            source_invocation_id=source.invocation_id,
            source_invocation_digest=source.canonical_digest,
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
            output_schema_digest=source.output_schema_digest,
            result_policy_digest=source.result_policy_digest,
            normalized_redacted_result_digest=source.normalized_redacted_result_digest,
            evidence_package_id=receipt.evidence_package_id,
            evidence_schema_version=receipt.evidence_schema_version,
            evidence_content_digest=receipt.evidence_content_digest,
            evidence_metadata_digest=receipt.evidence_metadata_digest,
            classification=receipt.classification,
            access_policy_id=receipt.access_policy_id,
            access_policy_digest=receipt.access_policy_digest,
            retention_policy_id=receipt.retention_policy_id,
            retention_policy_digest=receipt.retention_policy_digest,
            encryption_profile_id=receipt.encryption_profile_id,
            encryption_profile_digest=receipt.encryption_profile_digest,
            ingestion_policy_id=policy.policy_id,
            ingestion_policy_digest=policy.canonical_digest,
            ingestion_policy_version=policy.policy_version,
            ingestion_adapter_id=receipt.adapter_id,
            evidence_item_count=receipt.evidence_item_count,
            evidence_bytes=receipt.evidence_bytes,
            observed_from=receipt.observed_from,
            observed_to=receipt.observed_to,
            ingested_at=receipt.ingested_at,
            instance_state=ENABLED_INVOCATION_EVIDENCE_INGESTED,
            ingested_by=actor.subject_id,
            purpose=purpose,
            canonical_digest="0" * 64,
        )
        record = replace(record, canonical_digest=self._digest(self._record_payload(record)))
        await self._audit(
            actor,
            correlation_id,
            "connector_invocation_evidence_ingested",
            record.ingestion_id,
            (("instance_state", record.instance_state),),
        )
        if not await self._repository.add(record):
            raced = await self._repository.get_by_invocation(
                source_invocation_id=source.invocation_id
            )
            if raced is None or raced.canonical_digest != record.canonical_digest:
                raise ConnectorInvocationEvidenceUncertainError(
                    "invocation_evidence_persistence_uncertain"
                )
            return replace(raced, reused=True)
        return record

    async def get(
        self, *, actor: AuthenticatedSubject, ingestion_id: str, correlation_id: str
    ) -> ConnectorInvocationEvidenceRecord:
        self._require_enterprise_human(actor)
        record = await self._repository.get(ingestion_id=ingestion_id)
        if record is None:
            raise ConnectorInvocationEvidenceError("invocation_evidence_record_not_found")
        self._verify_record(record)
        self._require_scope(actor, record.organization_id, record.environment_id)
        await self._audit(
            actor,
            correlation_id,
            "connector_invocation_evidence_read",
            record.ingestion_id,
            (),
            permission_id=INVOCATION_EVIDENCE_READ_PERMISSION,
        )
        return record

    async def knowledge_draft_source(
        self, *, ingestion_id: str
    ) -> tuple[ConnectorInvocationEvidenceRecord, frozenset[str]]:
        record = await self._repository.get(ingestion_id=ingestion_id)
        if record is None:
            raise ConnectorInvocationEvidenceError("invocation_evidence_record_not_found")
        self._verify_record(record)
        claim = await self._repository.get_claim_by_invocation(
            source_invocation_id=record.source_invocation_id
        )
        if claim is None:
            raise ConnectorInvocationEvidenceError("invocation_evidence_claim_not_found")
        self._verify_claim(claim)
        try:
            source, source_actors = await self._source.evidence_ingestion_source(
                invocation_id=record.source_invocation_id
            )
        except ConnectorInvocationEvidenceError:
            raise
        except Exception as error:
            raise ConnectorInvocationEvidenceError(
                "invocation_evidence_source_not_found"
            ) from error
        policy = await self._policy_source.get_by_id(policy_id=record.ingestion_policy_id)
        if policy is None:
            raise ConnectorInvocationEvidenceError("invocation_evidence_policy_not_found")
        self._verify_snapshot(policy)
        if (
            source.canonical_digest != record.source_invocation_digest
            or source.package_digest != record.package_digest
            or source.connector_id != record.connector_id
            or source.instance_id != record.instance_id
            or source.capability_id != record.capability_id
            or source.normalized_redacted_result_digest != record.normalized_redacted_result_digest
            or claim.claim_id != record.claim_id
            or claim.source_invocation_id != record.source_invocation_id
            or claim.source_invocation_digest != record.source_invocation_digest
            or claim.ingestion_id != record.ingestion_id
            or claim.claimed_by != record.ingested_by
            or claim.purpose != record.purpose
            or policy.canonical_digest != record.ingestion_policy_digest
            or record.instance_state != ENABLED_INVOCATION_EVIDENCE_INGESTED
            or not record.evidence_ingested
            or not record.immutable_storage_confirmed
            or not record.encrypted_at_rest
            or not record.transient_buffers_erased
            or not record.artifact_channel_closed
            or record.knowledge_item_created
            or record.retrieval_published
            or record.model_context_available
            or record.graph_updated
            or record.scheduled
            or record.workflow_continued
            or record.execution_authorized
            or record.deployment_approved
            or record.infrastructure_mutation_performed
        ):
            raise ConnectorInvocationEvidenceError(
                "invocation_evidence_knowledge_draft_source_invalid"
            )
        return record, source_actors | {
            record.ingested_by,
            policy.signed_by,
            policy.required_adapter_attestor_id,
        }

    async def close(self) -> None:
        await self._repository.close()

    async def _reuse(
        self,
        claim: ConnectorInvocationEvidenceClaim,
        actor: AuthenticatedSubject,
        request_binding_digest: str,
        idempotency_digest: str,
    ) -> ConnectorInvocationEvidenceRecord:
        self._verify_claim(claim)
        if (
            claim.claimed_by != actor.subject_id
            or claim.request_binding_digest != request_binding_digest
            or claim.idempotency_digest != idempotency_digest
        ):
            raise ConnectorInvocationEvidenceError("invocation_evidence_idempotency_conflict")
        self._require_scope(actor, claim.organization_id, claim.environment_id)
        record = await self._repository.get(ingestion_id=claim.ingestion_id)
        if record is None:
            raise ConnectorInvocationEvidenceError("invocation_evidence_already_claimed")
        self._verify_record(record)
        return replace(record, reused=True)

    @staticmethod
    def _verify_source(
        *,
        source: ConnectorBoundedInvocationRecord,
        policy: ConnectorInvocationEvidencePolicySnapshot,
        source_digest: str,
        policy_digest: str,
        now: datetime,
    ) -> None:
        if (
            source.canonical_digest != source_digest
            or policy.canonical_digest != policy_digest
            or policy.organization_id != source.organization_id
            or policy.environment_id != source.environment_id
            or policy.required_source_schema != source.schema_version
            or policy.required_source_state != source.instance_state
            or source.instance_state != ENABLED_BOUNDED_CAPABILITY_INVOCATION_COMPLETED
            or source.capability_class not in {"C0", "C1"}
            or not source.capability_invoked
            or not source.result_received
            or not source.result_validated
            or not source.result_redacted
            or not source.target_session_closed
            or not source.delivery_channel_closed
            or not source.lease_revocation_confirmed
            or source.target_connected
            or source.reusable_session_available
            or source.scheduled
            or source.evidence_ingested
            or source.execution_authorized
            or source.deployment_approved
            or source.infrastructure_mutation_performed
            or not 1 <= source.observation_count <= policy.maximum_evidence_items
            or not 0 <= source.output_bytes <= policy.maximum_evidence_bytes
            or now - source.completed_at > timedelta(minutes=policy.maximum_source_age_minutes)
            or not policy.issued_at <= now < policy.expires_at
        ):
            raise ConnectorInvocationEvidenceError("invocation_evidence_source_invalid")

    @classmethod
    def _verify_receipt(
        cls,
        instruction: ConnectorInvocationEvidenceInstruction,
        receipt: ConnectorInvocationEvidenceReceipt,
        policy: ConnectorInvocationEvidencePolicySnapshot,
    ) -> None:
        if (
            cls._receipt_digest(receipt) != receipt.canonical_digest
            or receipt.ingestion_id != instruction.ingestion_id
            or receipt.schema_version != policy.required_receipt_schema
            or receipt.adapter_id != policy.required_adapter_id
            or receipt.attested_by != policy.required_adapter_attestor_id
            or receipt.source_invocation_digest != instruction.source_invocation_digest
            or receipt.normalized_redacted_result_digest
            != instruction.normalized_redacted_result_digest
            or receipt.classification != policy.required_classification
            or receipt.access_policy_id != policy.access_policy_id
            or receipt.access_policy_digest != policy.access_policy_digest
            or receipt.retention_policy_id != policy.retention_policy_id
            or receipt.retention_policy_digest != policy.retention_policy_digest
            or receipt.encryption_profile_id != policy.encryption_profile_id
            or receipt.encryption_profile_digest != policy.encryption_profile_digest
            or receipt.evidence_item_count != instruction.source_observation_count
            or receipt.evidence_bytes != instruction.source_output_bytes
            or receipt.observed_from != instruction.source_started_at
            or receipt.observed_to != instruction.source_completed_at
            or receipt.evidence_item_count > instruction.maximum_evidence_items
            or receipt.evidence_bytes > instruction.maximum_evidence_bytes
        ):
            raise ConnectorInvocationEvidenceUncertainError("invocation_evidence_receipt_invalid")

    @classmethod
    def _verify_snapshot(cls, policy: ConnectorInvocationEvidencePolicySnapshot) -> None:
        payload = cast(dict[str, object], asdict(policy))
        digest = str(payload.pop("canonical_digest"))
        if cls._digest(cls._normalize(payload)) != digest:
            raise ConnectorInvocationEvidenceError("invocation_evidence_policy_integrity_failed")

    @classmethod
    def _verify_claim(cls, claim: ConnectorInvocationEvidenceClaim) -> None:
        if cls._digest(cls._claim_payload(claim)) != claim.canonical_digest:
            raise ConnectorInvocationEvidenceError("invocation_evidence_claim_integrity_failed")

    @classmethod
    def _verify_record(cls, record: ConnectorInvocationEvidenceRecord) -> None:
        if cls._digest(cls._record_payload(record)) != record.canonical_digest:
            raise ConnectorInvocationEvidenceError("invocation_evidence_record_integrity_failed")

    @classmethod
    def _claim_payload(cls, claim: ConnectorInvocationEvidenceClaim) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(claim))
        payload.pop("canonical_digest")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _record_payload(cls, record: ConnectorInvocationEvidenceRecord) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(record))
        for field in ("canonical_digest", "reused"):
            payload.pop(field)
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _receipt_digest(cls, receipt: ConnectorInvocationEvidenceReceipt) -> str:
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
        if (
            actor.kind is not SubjectKind.HUMAN
            or actor.authentication_method is AuthenticationMethod.DEVELOPMENT
            or actor.assurance_level is not AssuranceLevel.HARDWARE_BACKED
        ):
            raise ConnectorInvocationEvidenceError(
                "invocation_evidence_enterprise_human_hardware_mfa_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise ConnectorInvocationEvidenceError("invocation_evidence_record_not_found")

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = INVOCATION_EVIDENCE_CREATE_PERMISSION,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.invocation-evidence",
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
                resource_type="resource.connector.invocation-evidence",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=metadata,
            )
        )


def _signed_policy(policy: ConnectorInvocationEvidencePolicySnapshot) -> str:
    payload = cast(dict[str, object], asdict(policy))
    payload.pop("canonical_digest")
    return ConnectorInvocationEvidenceService._digest(
        ConnectorInvocationEvidenceService._normalize(payload)
    )


def build_development_connector_invocation_evidence_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> ConnectorInvocationEvidencePolicySnapshot:
    policy = ConnectorInvocationEvidencePolicySnapshot(
        policy_id="connector-invocation-evidence-policy.development",
        schema_version="atlas.connector-invocation-evidence-policy.v1",
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-v1",
        required_source_schema="atlas.connector-bounded-invocation.v1",
        required_source_state=ENABLED_BOUNDED_CAPABILITY_INVOCATION_COMPLETED,
        required_adapter_id="connector-invocation-evidence-adapter.synthetic",
        required_adapter_attestor_id=("subject.connector-invocation-evidence-adapter-attestor"),
        required_receipt_schema="atlas.connector-invocation-evidence-receipt.v1",
        required_classification="classification.internal",
        access_policy_id="connector-evidence-access.development-tenant",
        access_policy_digest=ConnectorInvocationEvidenceService._digest(
            [organization_id, environment_id, "connector-evidence-access-v1"]
        ),
        retention_policy_id="connector-evidence-retention.development-30-days",
        retention_policy_digest=ConnectorInvocationEvidenceService._digest(
            ["connector-evidence-retention", "30-days", "policy-v1"]
        ),
        encryption_profile_id="connector-evidence-encryption.development",
        encryption_profile_digest=ConnectorInvocationEvidenceService._digest(
            ["connector-evidence-encryption", "synthetic-at-rest", "profile-v1"]
        ),
        maximum_source_age_minutes=60,
        maximum_evidence_items=100,
        maximum_evidence_bytes=524_288,
        required_assurance_level=AssuranceLevel.HARDWARE_BACKED,
        signed_by="subject.connector-invocation-evidence-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(policy, canonical_digest=_signed_policy(policy))
