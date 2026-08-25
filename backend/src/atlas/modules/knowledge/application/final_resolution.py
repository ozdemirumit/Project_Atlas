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
from atlas.modules.authorization.application.bootstrap import (
    KNOWLEDGE_FINAL_RESOLUTION_CREATE,
    KNOWLEDGE_FINAL_RESOLUTION_READ,
)
from atlas.modules.identity.domain.models import (
    AuthenticatedSubject,
    SubjectKind,
)
from atlas.modules.knowledge.application.final_resolution_ports import (
    OperationalKnowledgeFinalResolutionAttestor,
    OperationalKnowledgeFinalResolutionError,
    OperationalKnowledgeFinalResolutionPermissionAuthorizer,
    OperationalKnowledgeFinalResolutionPolicySource,
    OperationalKnowledgeFinalResolutionRepository,
    OperationalKnowledgeFinalResolutionSource,
    OperationalKnowledgeFinalResolutionUncertainError,
)
from atlas.modules.knowledge.domain.draft_review_request import (
    OPERATIONAL_KNOWLEDGE_REVIEW_REQUESTED,
    OperationalKnowledgeReviewRequestRecord,
)
from atlas.modules.knowledge.domain.evidence_draft import (
    DRAFT_OPERATIONAL_KNOWLEDGE_CREATED,
    OperationalEvidenceKnowledgeDraftRecord,
)
from atlas.modules.knowledge.domain.final_resolution import (
    FINAL_APPROVED,
    FINAL_APPROVED_STATE,
    FINAL_DISPOSITIONS,
    FINAL_REJECTED_STATE,
    OperationalKnowledgeFinalResolutionClaim,
    OperationalKnowledgeFinalResolutionInstruction,
    OperationalKnowledgeFinalResolutionPolicySnapshot,
    OperationalKnowledgeFinalResolutionReceipt,
    OperationalKnowledgeFinalResolutionRecord,
)
from atlas.modules.knowledge.domain.review_decision import (
    OPERATIONAL_KNOWLEDGE_TRACK_REVIEW_DECIDED,
    TRACKS,
    OperationalKnowledgeTrackReviewDecisionRecord,
)

FINAL_RESOLUTION_POLICY_SCHEMA = "atlas.operational-knowledge-final-resolution-policy.v1"
FINAL_RESOLUTION_CLAIM_SCHEMA = "atlas.operational-knowledge-final-resolution-claim.v1"
FINAL_RESOLUTION_RECORD_SCHEMA = "atlas.operational-knowledge-final-resolution.v1"


class OperationalKnowledgeFinalResolutionService:
    def __init__(
        self,
        *,
        repository: OperationalKnowledgeFinalResolutionRepository,
        source: OperationalKnowledgeFinalResolutionSource,
        policy_source: OperationalKnowledgeFinalResolutionPolicySource,
        permission_authorizer: OperationalKnowledgeFinalResolutionPermissionAuthorizer,
        attestor: OperationalKnowledgeFinalResolutionAttestor,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._source = source
        self._policy_source = policy_source
        self._permission_authorizer = permission_authorizer
        self._attestor = attestor
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        review_request_id: str,
        review_request_digest: str,
        decision_ids: tuple[str, str],
        decision_digests: tuple[str, str],
        disposition_code: str,
        basis_codes: tuple[str, ...],
        resolution_policy_id: str,
        resolution_policy_digest: str,
        purpose: str,
        immutable_generation_acknowledged: bool,
        publication_readiness_only_acknowledged: bool,
        no_operational_authority_acknowledged: bool,
        browser_session_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> OperationalKnowledgeFinalResolutionRecord:
        self._require_human(actor)
        purpose = purpose.strip()
        basis_codes = tuple(sorted(set(basis_codes)))
        if (
            disposition_code not in FINAL_DISPOSITIONS
            or not basis_codes
            or len(set(decision_ids)) != 2
            or len(set(decision_digests)) != 2
            or not 20 <= len(purpose) <= 1000
            or not 16 <= len(browser_session_id) <= 256
            or not 8 <= len(idempotency_key) <= 128
            or not all(
                (
                    immutable_generation_acknowledged,
                    publication_readiness_only_acknowledged,
                    no_operational_authority_acknowledged,
                )
            )
        ):
            raise OperationalKnowledgeFinalResolutionError(
                "operational_knowledge_final_resolution_request_invalid"
            )
        try:
            decisions, request, draft = await self._source.final_resolution_source(
                review_request_id=review_request_id,
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
            )
        except Exception as error:
            raise OperationalKnowledgeFinalResolutionError(
                "operational_knowledge_final_resolution_source_not_found"
            ) from error
        policy = await self._policy_source.get_by_id(policy_id=resolution_policy_id)
        if policy is None:
            raise OperationalKnowledgeFinalResolutionError(
                "operational_knowledge_final_resolution_policy_not_found"
            )
        self._verify_policy(policy)
        now = self._clock()
        ordered = tuple(sorted(decisions, key=lambda item: item.track_code))
        supplied = set(zip(decision_ids, decision_digests, strict=True))
        actual = {(item.decision_id, item.canonical_digest) for item in ordered}
        later_authority = any(
            any(
                (
                    item.correction_created,
                    item.knowledge_approved,
                    item.knowledge_published,
                    item.retrieval_published,
                    item.workflow_continued,
                    item.execution_authorized,
                    item.deployment_approved,
                    item.infrastructure_mutation_performed,
                )
            )
            for item in ordered
        )
        if (
            len(ordered) != 2
            or {item.track_code for item in ordered} != TRACKS
            or supplied != actual
            or request.review_request_id != review_request_id
            or request.canonical_digest != review_request_digest
            or request.instance_state != OPERATIONAL_KNOWLEDGE_REVIEW_REQUESTED
            or draft.instance_state != DRAFT_OPERATIONAL_KNOWLEDGE_CREATED
            or request.source_draft_id != draft.draft_id
            or request.source_draft_digest != draft.canonical_digest
            or request.knowledge_item_id != draft.knowledge_item_id
            or any(item.review_request_id != review_request_id for item in ordered)
            or any(item.source_draft_id != draft.draft_id for item in ordered)
            or any(item.source_draft_digest != draft.canonical_digest for item in ordered)
            or any(item.disposition_code != "review-disposition.passed" for item in ordered)
            or any(item.correction_required for item in ordered)
            or later_authority
            or policy.canonical_digest != resolution_policy_digest
            or policy.organization_id != request.organization_id
            or policy.environment_id != request.environment_id
            or policy.required_decision_schema != ordered[0].schema_version
            or any(item.schema_version != policy.required_decision_schema for item in ordered)
            or any(item.instance_state != policy.required_decision_state for item in ordered)
            or request.schema_version != policy.required_request_schema
            or request.instance_state != policy.required_request_state
            or draft.schema_version != policy.required_draft_schema
            or draft.instance_state != policy.required_draft_state
            or not policy.issued_at <= now < policy.expires_at
            or now - actor.authenticated_at
            > timedelta(minutes=policy.maximum_authentication_age_minutes)
            or not set(basis_codes) <= set(policy.allowed_basis_codes)
        ):
            raise OperationalKnowledgeFinalResolutionError(
                "operational_knowledge_final_resolution_source_invalid"
            )
        self._require_scope(actor, request.organization_id, request.environment_id)
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        if (
            actor.subject_id == draft.curated_by
            or subject_digest in {item.decided_by_subject_digest for item in ordered}
            or actor.subject_id in {policy.signed_by, policy.required_attestor_id}
        ):
            raise OperationalKnowledgeFinalResolutionError(
                "operational_knowledge_final_resolution_actor_separation_required"
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=request.organization_id,
            environment_id=request.environment_id,
            correlation_id=correlation_id,
        )
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        decision_aggregate_digest = self._digest(
            [
                [item.track_code, item.decision_id, item.canonical_digest, item.disposition_code]
                for item in ordered
            ]
        )
        basis_digest = self._digest(list(basis_codes))
        request_binding_digest = self._digest(
            [
                review_request_id,
                review_request_digest,
                decision_aggregate_digest,
                disposition_code,
                basis_digest,
                resolution_policy_digest,
                purpose,
                subject_digest,
                browser_digest,
            ]
        )
        idempotency_digest = self._digest([subject_digest, review_request_id, idempotency_key])
        existing = await self._repository.get_claim_by_review_request(
            review_request_id=review_request_id
        )
        if existing is not None:
            return await self._reuse(
                existing,
                subject_digest=subject_digest,
                browser_digest=browser_digest,
                request_binding_digest=request_binding_digest,
                idempotency_digest=idempotency_digest,
                actor=actor,
                correlation_id=correlation_id,
            )
        seed = self._digest([review_request_id, request_binding_digest])
        resolution_id = f"operational-knowledge-final-resolution.{seed[:24]}"
        claim = OperationalKnowledgeFinalResolutionClaim(
            claim_id=f"operational-knowledge-final-resolution-claim.{seed[:24]}",
            schema_version=FINAL_RESOLUTION_CLAIM_SCHEMA,
            version=1,
            review_request_id=review_request_id,
            resolution_id=resolution_id,
            claimed_by_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            request_binding_digest=request_binding_digest,
            idempotency_digest=idempotency_digest,
            organization_id=request.organization_id,
            environment_id=request.environment_id,
            claimed_at=now,
            canonical_digest="0" * 64,
        )
        claim = replace(claim, canonical_digest=self._digest(self._payload(claim)))
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_final_resolution_requested",
            review_request_id,
            (("disposition_code", disposition_code),),
        )
        if not await self._repository.claim(claim):
            concurrent = await self._repository.get_claim_by_review_request(
                review_request_id=review_request_id
            )
            if concurrent is None:
                raise OperationalKnowledgeFinalResolutionUncertainError(
                    "operational_knowledge_final_resolution_claim_uncertain"
                )
            return await self._reuse(
                concurrent,
                subject_digest=subject_digest,
                browser_digest=browser_digest,
                request_binding_digest=request_binding_digest,
                idempotency_digest=idempotency_digest,
                actor=actor,
                correlation_id=correlation_id,
            )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_final_resolution_claimed",
            resolution_id,
            (("disposition_code", disposition_code),),
        )
        instruction = OperationalKnowledgeFinalResolutionInstruction(
            resolution_id=resolution_id,
            organization_id=request.organization_id,
            environment_id=request.environment_id,
            review_request_id=review_request_id,
            review_request_digest=review_request_digest,
            source_draft_id=draft.draft_id,
            source_draft_digest=draft.canonical_digest,
            assignment_set_id=ordered[0].source_assignment_set_id,
            decision_aggregate_digest=decision_aggregate_digest,
            knowledge_item_id=draft.knowledge_item_id,
            draft_version_id=draft.draft_version_id,
            approver_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            disposition_code=disposition_code,
            basis_codes=basis_codes,
            basis_digest=basis_digest,
            policy_id=policy.policy_id,
            policy_digest=policy.canonical_digest,
            purpose=purpose,
            requested_at=now,
        )
        try:
            receipt = await self._attestor.attest(instruction)
            self._verify_receipt(receipt, instruction, policy)
        except OperationalKnowledgeFinalResolutionError:
            raise
        except Exception as error:
            raise OperationalKnowledgeFinalResolutionUncertainError(
                "operational_knowledge_final_resolution_outcome_uncertain"
            ) from error
        record = OperationalKnowledgeFinalResolutionRecord(
            resolution_id=resolution_id,
            schema_version=FINAL_RESOLUTION_RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            review_request_id=review_request_id,
            review_request_digest=review_request_digest,
            source_draft_id=draft.draft_id,
            source_draft_digest=draft.canonical_digest,
            source_assignment_set_id=ordered[0].source_assignment_set_id,
            decision_ids=(ordered[0].decision_id, ordered[1].decision_id),
            decision_digests=(ordered[0].canonical_digest, ordered[1].canonical_digest),
            decision_aggregate_digest=decision_aggregate_digest,
            organization_id=request.organization_id,
            environment_id=request.environment_id,
            knowledge_item_id=draft.knowledge_item_id,
            draft_version_id=draft.draft_version_id,
            title=draft.title,
            classification=draft.classification,
            access_policy_id=draft.access_policy_id,
            retention_policy_id=draft.retention_policy_id,
            disposition_code=disposition_code,
            basis_codes=basis_codes,
            basis_digest=basis_digest,
            approved_by_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            resolution_policy_id=policy.policy_id,
            resolution_policy_digest=policy.canonical_digest,
            resolution_policy_version=policy.policy_version,
            attestor_id=receipt.attestor_id,
            attestation_digest=receipt.canonical_digest,
            resolved_at=receipt.attested_at,
            instance_state=(
                FINAL_APPROVED_STATE if disposition_code == FINAL_APPROVED else FINAL_REJECTED_STATE
            ),
            purpose=purpose,
            canonical_digest="0" * 64,
            knowledge_approved=disposition_code == FINAL_APPROVED,
            publication_ready=disposition_code == FINAL_APPROVED,
        )
        record = replace(record, canonical_digest=self._digest(self._payload(record)))
        if not await self._repository.add(record):
            raise OperationalKnowledgeFinalResolutionUncertainError(
                "operational_knowledge_final_resolution_persistence_uncertain"
            )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_final_resolution_recorded",
            resolution_id,
            (("disposition_code", disposition_code),),
        )
        return record

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        resolution_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> OperationalKnowledgeFinalResolutionRecord:
        self._require_human(actor)
        record = await self._repository.get(resolution_id=resolution_id)
        if record is None:
            raise OperationalKnowledgeFinalResolutionError(
                "operational_knowledge_final_resolution_not_found"
            )
        policy = await self._policy_source.get_by_id(policy_id=record.resolution_policy_id)
        if policy is None or not policy.issued_at <= self._clock() < policy.expires_at:
            raise OperationalKnowledgeFinalResolutionError(
                "operational_knowledge_final_resolution_not_found"
            )
        self._require_scope(actor, record.organization_id, record.environment_id)
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        if (
            subject_digest != record.approved_by_subject_digest
            or browser_digest != record.browser_session_binding_digest
        ):
            raise OperationalKnowledgeFinalResolutionError(
                "operational_knowledge_final_resolution_not_found"
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            correlation_id=correlation_id,
        )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_final_resolution_read",
            resolution_id,
            (("disposition_code", record.disposition_code),),
            permission_id=KNOWLEDGE_FINAL_RESOLUTION_READ,
        )
        return replace(record, reused=True)

    async def publication_preparation_source(
        self, *, resolution_id: str
    ) -> tuple[
        OperationalKnowledgeFinalResolutionRecord,
        tuple[OperationalKnowledgeTrackReviewDecisionRecord, ...],
        OperationalKnowledgeReviewRequestRecord,
        OperationalEvidenceKnowledgeDraftRecord,
    ]:
        record = await self._repository.get(resolution_id=resolution_id)
        if record is None:
            raise OperationalKnowledgeFinalResolutionError(
                "operational_knowledge_final_resolution_not_found"
            )
        decisions, request, draft = await self._source.final_resolution_source(
            review_request_id=record.review_request_id,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
        )
        return record, decisions, request, draft

    async def close(self) -> None:
        await self._repository.close()

    async def _reuse(
        self,
        claim: OperationalKnowledgeFinalResolutionClaim,
        *,
        subject_digest: str,
        browser_digest: str,
        request_binding_digest: str,
        idempotency_digest: str,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> OperationalKnowledgeFinalResolutionRecord:
        if (
            claim.claimed_by_subject_digest != subject_digest
            or claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_binding_digest
            or claim.idempotency_digest != idempotency_digest
        ):
            raise OperationalKnowledgeFinalResolutionError(
                "operational_knowledge_final_resolution_idempotency_conflict"
            )
        record = await self._repository.get(resolution_id=claim.resolution_id)
        if record is None:
            raise OperationalKnowledgeFinalResolutionError(
                "operational_knowledge_final_resolution_already_claimed"
            )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_final_resolution_read",
            record.resolution_id,
            (("disposition_code", record.disposition_code),),
            permission_id=KNOWLEDGE_FINAL_RESOLUTION_READ,
        )
        return replace(record, reused=True)

    @classmethod
    def _verify_receipt(
        cls,
        receipt: OperationalKnowledgeFinalResolutionReceipt,
        instruction: OperationalKnowledgeFinalResolutionInstruction,
        policy: OperationalKnowledgeFinalResolutionPolicySnapshot,
    ) -> None:
        if (
            receipt.resolution_id != instruction.resolution_id
            or receipt.disposition_code != instruction.disposition_code
            or receipt.attestor_id != policy.required_attestor_id
            or receipt.instruction_digest != cls._digest(asdict(instruction))
            or not receipt.signature_verified
        ):
            raise OperationalKnowledgeFinalResolutionError(
                "operational_knowledge_final_resolution_attestation_invalid"
            )

    @classmethod
    def _verify_policy(cls, policy: OperationalKnowledgeFinalResolutionPolicySnapshot) -> None:
        if policy.canonical_digest != cls._digest(cls._payload(policy)):
            raise OperationalKnowledgeFinalResolutionError(
                "operational_knowledge_final_resolution_policy_invalid"
            )

    @staticmethod
    def _payload(
        value: OperationalKnowledgeFinalResolutionPolicySnapshot
        | OperationalKnowledgeFinalResolutionClaim
        | OperationalKnowledgeFinalResolutionRecord,
    ) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(value))
        payload.pop("canonical_digest", None)
        payload.pop("reused", None)
        return payload

    @classmethod
    def _normalize(cls, value: object) -> object:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {key: cls._normalize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._normalize(item) for item in value]
        return value

    @classmethod
    def _digest(cls, payload: object) -> str:
        return sha256(
            json.dumps(
                cls._normalize(payload),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("ascii")
        ).hexdigest()

    @staticmethod
    def _require_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise OperationalKnowledgeFinalResolutionError(
                "operational_knowledge_final_resolution_human_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise OperationalKnowledgeFinalResolutionError(
                "operational_knowledge_final_resolution_source_not_found"
            )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = KNOWLEDGE_FINAL_RESOLUTION_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.knowledge.operational-final-resolution",
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
                resource_type="resource.knowledge.operational-final-resolutions",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=metadata,
            )
        )


def build_development_operational_knowledge_final_resolution_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> OperationalKnowledgeFinalResolutionPolicySnapshot:
    digest = OperationalKnowledgeFinalResolutionService._digest
    policy = OperationalKnowledgeFinalResolutionPolicySnapshot(
        policy_id="operational-knowledge-final-resolution-policy.development",
        schema_version=FINAL_RESOLUTION_POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-version.operational-knowledge-final-resolution-development-v1",
        required_decision_schema="atlas.operational-knowledge-track-review-decision.v1",
        required_decision_state=OPERATIONAL_KNOWLEDGE_TRACK_REVIEW_DECIDED,
        required_request_schema="atlas.operational-knowledge-review-request.v1",
        required_request_state=OPERATIONAL_KNOWLEDGE_REVIEW_REQUESTED,
        required_draft_schema="atlas.operational-evidence-knowledge-draft.v1",
        required_draft_state=DRAFT_OPERATIONAL_KNOWLEDGE_CREATED,
        allowed_dispositions=tuple(sorted(FINAL_DISPOSITIONS)),
        allowed_basis_codes=(
            "final-basis.domain-and-security-passed",
            "final-basis.governance-scope-accepted",
            "final-basis.governance-scope-rejected",
        ),
        maximum_authentication_age_minutes=15,
        subject_digest_salt_digest=digest([organization_id, environment_id, "review-salt-v1"]),
        browser_binding_key_digest=digest(["operational-knowledge-final-browser-key"]),
        required_attestor_id="operational-knowledge-final-resolution-attestor.synthetic",
        signed_by="subject.operational-knowledge-final-resolution-policy-signer",
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy, canonical_digest=digest(OperationalKnowledgeFinalResolutionService._payload(policy))
    )
