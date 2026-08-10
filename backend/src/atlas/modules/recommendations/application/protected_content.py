from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from hashlib import sha256
from typing import cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.authorization.application.bootstrap import (
    RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_CREATE,
    RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.recommendations.application.protected_content_ports import (
    RecommendationProtectedContentError,
    RecommendationProtectedContentPermissionAuthorizer,
    RecommendationProtectedContentPolicySource,
    RecommendationProtectedContentPresenter,
    RecommendationProtectedContentRepository,
    RecommendationProtectedContentSource,
    RecommendationProtectedContentUncertainError,
)
from atlas.modules.recommendations.domain.promotion import PromotedRecommendationArtifact
from atlas.modules.recommendations.domain.protected_content import (
    RECOMMENDATION_PROTECTED_CONTENT_PRESENTED,
    RecommendationProtectedContentClaim,
    RecommendationProtectedContentGrant,
    RecommendationProtectedContentInstruction,
    RecommendationProtectedContentPolicySnapshot,
    RecommendationProtectedContentReceipt,
    RecommendationProtectedContentRecord,
)
from atlas.modules.recommendations.domain.protected_inspection import (
    RECOMMENDATION_PROTECTED_INSPECTION_LEASED,
    RecommendationProtectedInspectionPolicySnapshot,
    RecommendationProtectedInspectionRecord,
)
from atlas.modules.recommendations.domain.readiness import RecommendationReadinessAssessment
from atlas.modules.recommendations.domain.review_request import RecommendationReviewRequestRecord
from atlas.modules.recommendations.domain.reviewer_assignment import (
    RecommendationReviewerAssignmentRecord,
)

CONTENT_POLICY_SCHEMA = "atlas.recommendation-protected-content-policy.v1"
CONTENT_CLAIM_SCHEMA = "atlas.recommendation-protected-content-claim.v1"
CONTENT_RECORD_SCHEMA = "atlas.recommendation-protected-content-presentation.v1"


class RecommendationProtectedContentService:
    def __init__(
        self,
        *,
        repository: RecommendationProtectedContentRepository,
        source: RecommendationProtectedContentSource,
        policy_source: RecommendationProtectedContentPolicySource,
        permission_authorizer: RecommendationProtectedContentPermissionAuthorizer,
        presenter: RecommendationProtectedContentPresenter,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._source = source
        self._policy_source = policy_source
        self._permission_authorizer = permission_authorizer
        self._presenter = presenter
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        recommendation_id: str,
        source_lease_id: str,
        source_lease_digest: str,
        presentation_policy_id: str,
        presentation_policy_digest: str,
        purpose: str,
        sensitive_read_only_acknowledged: bool,
        browser_session_id: str,
        lease_secrets: Mapping[str, str],
        idempotency_key: str,
        correlation_id: str,
    ) -> RecommendationProtectedContentGrant:
        purpose = purpose.strip()
        if (
            not sensitive_read_only_acknowledged
            or not 20 <= len(purpose) <= 1000
            or not 16 <= len(browser_session_id) <= 256
            or not 8 <= len(idempotency_key) <= 128
        ):
            raise RecommendationProtectedContentError(
                "recommendation_protected_content_request_invalid"
            )
        (
            source,
            inspection_policy,
            _assignment,
            _request,
            _assessment,
            artifact,
            policy,
        ) = await self._authorize(
            actor=actor,
            recommendation_id=recommendation_id,
            source_lease_id=source_lease_id,
            source_lease_digest=source_lease_digest,
            presentation_policy_id=presentation_policy_id,
            presentation_policy_digest=presentation_policy_digest,
            browser_session_id=browser_session_id,
            lease_secrets=lease_secrets,
            correlation_id=correlation_id,
        )
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        browser_digest = self._digest(
            [inspection_policy.browser_binding_key_digest, browser_session_id]
        )
        request_digest = self._digest(
            {
                "source_lease_id": source.lease_id,
                "source_lease_digest": source.canonical_digest,
                "presentation_policy_id": policy.policy_id,
                "presentation_policy_digest": policy.canonical_digest,
                "purpose": purpose,
                "browser_session_binding_digest": browser_digest,
            }
        )
        idempotency_digest = self._digest([subject_digest, browser_digest, idempotency_key])
        existing = await self._repository.get_claim_by_idempotency(
            claimed_by_subject_digest=subject_digest,
            idempotency_digest=idempotency_digest,
        )
        if existing is not None:
            return await self._reuse(
                existing,
                actor=actor,
                source=source,
                artifact=artifact,
                policy=policy,
                subject_digest=subject_digest,
                browser_digest=browser_digest,
                request_digest=request_digest,
                idempotency_digest=idempotency_digest,
                correlation_id=correlation_id,
            )
        seed = self._digest([source.lease_id, source.canonical_digest, policy.canonical_digest])
        presentation_id = f"recommendation-protected-content-presentation.{seed[:24]}"
        await self._audit(
            actor,
            correlation_id,
            "recommendation_protected_content_requested",
            source.lease_id,
            (("track_code", source.track_code),),
        )
        claim = RecommendationProtectedContentClaim(
            claim_id=f"recommendation-protected-content-claim.{seed[:24]}",
            schema_version=CONTENT_CLAIM_SCHEMA,
            version=1,
            source_lease_id=source.lease_id,
            source_lease_digest=source.canonical_digest,
            presentation_id=presentation_id,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            claimed_by_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            purpose=purpose,
            claimed_at=self._clock(),
            request_binding_digest=request_digest,
            idempotency_digest=idempotency_digest,
            canonical_digest="0" * 64,
        )
        claim = replace(claim, canonical_digest=self._digest(self._claim_payload(claim)))
        if not await self._repository.claim(claim):
            prior = await self._repository.get_claim_by_source_lease(
                source_lease_id=source.lease_id
            )
            if prior is None:
                raise RecommendationProtectedContentUncertainError(
                    "recommendation_protected_content_claim_uncertain"
                )
            return await self._reuse(
                prior,
                actor=actor,
                source=source,
                artifact=artifact,
                policy=policy,
                subject_digest=subject_digest,
                browser_digest=browser_digest,
                request_digest=request_digest,
                idempotency_digest=idempotency_digest,
                correlation_id=correlation_id,
            )
        await self._audit(
            actor,
            correlation_id,
            "recommendation_protected_content_claimed",
            claim.claim_id,
            (("presentation_id", presentation_id),),
        )
        instruction = self._instruction(presentation_id, source, artifact, policy)
        try:
            grant = await self._presenter.present(instruction)
            self._verify_grant(instruction, grant.receipt, grant.content, policy)
        except RecommendationProtectedContentError:
            await self._audit(
                actor,
                correlation_id,
                "recommendation_protected_content_failed",
                presentation_id,
                (("claim_persisted", "true"),),
            )
            raise
        except Exception as error:
            await self._audit(
                actor,
                correlation_id,
                "recommendation_protected_content_uncertain",
                presentation_id,
                (("claim_persisted", "true"),),
            )
            raise RecommendationProtectedContentUncertainError(
                "recommendation_protected_content_outcome_uncertain"
            ) from error
        record = self._record(claim, source, artifact, policy, grant.receipt)
        await self._audit(
            actor,
            correlation_id,
            "recommendation_protected_content_presented",
            presentation_id,
            (("content_bytes", str(record.protected_content_bytes_returned)),),
        )
        if not await self._repository.add(record):
            raced = await self._repository.get_by_source_lease(source_lease_id=source.lease_id)
            if raced is None or raced.canonical_digest != record.canonical_digest:
                raise RecommendationProtectedContentUncertainError(
                    "recommendation_protected_content_persistence_uncertain"
                )
            record = replace(raced, reused=True)
        return RecommendationProtectedContentGrant(record=record, content=grant.content)

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        recommendation_id: str,
        source_lease_id: str,
        presentation_id: str,
        browser_session_id: str,
        lease_secrets: Mapping[str, str],
        correlation_id: str,
    ) -> RecommendationProtectedContentGrant:
        record = await self._repository.get(presentation_id=presentation_id)
        if record is None or record.source_lease_id != source_lease_id:
            raise RecommendationProtectedContentError(
                "recommendation_protected_content_record_not_found"
            )
        self._verify_record(record)
        (
            source,
            _inspection,
            _assignment,
            _request,
            _assessment,
            artifact,
            policy,
        ) = await self._authorize(
            actor=actor,
            recommendation_id=recommendation_id,
            source_lease_id=source_lease_id,
            source_lease_digest=record.source_lease_digest,
            presentation_policy_id=record.presentation_policy_id,
            presentation_policy_digest=record.presentation_policy_digest,
            browser_session_id=browser_session_id,
            lease_secrets=lease_secrets,
            correlation_id=correlation_id,
        )
        instruction = self._instruction(record.presentation_id, source, artifact, policy)
        try:
            grant = await self._presenter.present(instruction)
            self._verify_grant(instruction, grant.receipt, grant.content, policy)
        except Exception as error:
            raise RecommendationProtectedContentUncertainError(
                "recommendation_protected_content_replay_uncertain"
            ) from error
        if (
            grant.receipt.presented_content_digest != record.presented_content_digest
            or grant.receipt.content_bytes != record.protected_content_bytes_returned
        ):
            raise RecommendationProtectedContentUncertainError(
                "recommendation_protected_content_replay_drift"
            )
        await self._audit(
            actor,
            correlation_id,
            "recommendation_protected_content_read",
            presentation_id,
            (("content_bytes", str(record.protected_content_bytes_returned)),),
            permission_id=RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_READ,
        )
        return RecommendationProtectedContentGrant(
            record=replace(record, reused=True), content=grant.content
        )

    async def close(self) -> None:
        await self._repository.close()

    async def human_review_finding_source(
        self, *, presentation_id: str
    ) -> tuple[
        RecommendationProtectedContentRecord,
        RecommendationProtectedInspectionRecord,
        RecommendationProtectedInspectionPolicySnapshot,
        RecommendationReviewerAssignmentRecord,
        RecommendationReviewRequestRecord,
        RecommendationReadinessAssessment,
        PromotedRecommendationArtifact,
        RecommendationProtectedContentPolicySnapshot,
    ]:
        record = await self._repository.get(presentation_id=presentation_id)
        if record is None:
            raise RecommendationProtectedContentError(
                "recommendation_protected_content_record_not_found"
            )
        self._verify_record(record)
        try:
            (
                lease,
                inspection_policy,
                assignment,
                _assignment_policy,
                request,
                assessment,
                artifact,
            ) = await self._source.protected_content_source(lease_id=record.source_lease_id)
        except Exception as error:
            raise RecommendationProtectedContentError(
                "recommendation_protected_content_lineage_invalid"
            ) from error
        policy = await self._policy_source.get_by_id(policy_id=record.presentation_policy_id)
        if policy is None:
            raise RecommendationProtectedContentError(
                "recommendation_protected_content_lineage_invalid"
            )
        self._verify_policy(policy)
        if (
            record.source_lease_digest != lease.canonical_digest
            or record.source_assignment_set_id != assignment.assignment_set_id
            or record.recommendation_id != artifact.recommendation_id
            or record.review_request_id != request.review_request_id
            or record.readiness_assessment_id != assessment.assessment_id
            or record.promotion_id != artifact.promotion_id
            or record.recommendation_artifact_digest != artifact.canonical_digest
            or record.presentation_policy_digest != policy.canonical_digest
            or record.track_code != lease.track_code
            or record.organization_id != artifact.organization_id
            or record.environment_id != artifact.environment_id
        ):
            raise RecommendationProtectedContentError(
                "recommendation_protected_content_lineage_invalid"
            )
        return (
            record,
            lease,
            inspection_policy,
            assignment,
            request,
            assessment,
            artifact,
            policy,
        )

    async def _authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        recommendation_id: str,
        source_lease_id: str,
        source_lease_digest: str,
        presentation_policy_id: str,
        presentation_policy_digest: str,
        browser_session_id: str,
        lease_secrets: Mapping[str, str],
        correlation_id: str,
    ) -> tuple[
        RecommendationProtectedInspectionRecord,
        RecommendationProtectedInspectionPolicySnapshot,
        RecommendationReviewerAssignmentRecord,
        RecommendationReviewRequestRecord,
        RecommendationReadinessAssessment,
        PromotedRecommendationArtifact,
        RecommendationProtectedContentPolicySnapshot,
    ]:
        self._require_enterprise_human(actor)
        try:
            (
                source,
                inspection_policy,
                assignment,
                assignment_policy,
                review_request,
                assessment,
                artifact,
            ) = await self._source.protected_content_source(lease_id=source_lease_id)
        except Exception as error:
            raise RecommendationProtectedContentError(
                "recommendation_protected_content_source_not_found"
            ) from error
        policy = await self._policy_source.get_by_id(policy_id=presentation_policy_id)
        if policy is None:
            raise RecommendationProtectedContentError(
                "recommendation_protected_content_policy_not_found"
            )
        self._verify_policy(policy)
        now = self._clock()
        if (
            source.canonical_digest != source_lease_digest
            or source.recommendation_id != recommendation_id
            or source.state != RECOMMENDATION_PROTECTED_INSPECTION_LEASED
            or source.content_disclosed
            or source.protected_content_bytes_returned != 0
            or now < source.issued_at
            or now >= source.expires_at
            or policy.canonical_digest != presentation_policy_digest
            or policy.organization_id != source.organization_id
            or policy.environment_id != source.environment_id
            or policy.required_source_schema != source.schema_version
            or policy.required_source_state != source.state
            or policy.subject_digest_salt_digest != inspection_policy.subject_digest_salt_digest
            or assignment_policy.subject_digest_salt_digest
            != inspection_policy.subject_digest_salt_digest
            or assignment.assignment_set_id != source.source_assignment_set_id
            or assignment.canonical_digest != source.source_assignment_set_digest
            or review_request.review_request_id != source.review_request_id
            or assessment.assessment_id != source.readiness_assessment_id
            or artifact.recommendation_id != source.recommendation_id
            or artifact.promotion_id != source.promotion_id
            or artifact.canonical_digest != assessment.source_artifact_digest
            or review_request.source_recommendation_digest != artifact.canonical_digest
            or artifact.outcome != source.source_outcome
            or len(artifact.options) != source.option_count
            or sum(option.role == "preferred" for option in artifact.options)
            != source.preferred_count
            or not policy.issued_at <= now < policy.expires_at
            or actor.authenticated_at > now
            or now - actor.authenticated_at
            > timedelta(minutes=policy.maximum_authentication_age_minutes)
            or any(
                (
                    source.human_review_completed,
                    source.recommendation_approved,
                    source.workflow_created,
                    source.itsm_record_created,
                    source.execution_authorized,
                    source.deployment_authorized,
                    source.infrastructure_mutated,
                )
            )
        ):
            raise RecommendationProtectedContentError(
                "recommendation_protected_content_source_invalid"
            )
        self._require_scope(actor, source.organization_id, source.environment_id)
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        expected_assignee = next(
            (
                reviewer
                for track, _queue, opaque_id, reviewer, status in assignment.track_assignments
                if track == source.track_code
                and opaque_id == source.opaque_assignment_id
                and status == "assigned"
            ),
            None,
        )
        browser_digest = self._digest(
            [inspection_policy.browser_binding_key_digest, browser_session_id]
        )
        secret = lease_secrets.get(source.track_code)
        secret_digest = (
            self._digest([source.inspection_policy_digest, "lease-secret", secret])
            if secret
            else None
        )
        if (
            expected_assignee is None
            or subject_digest != source.lease_holder_subject_digest
            or subject_digest != expected_assignee
            or browser_digest != source.browser_session_binding_digest
            or secret_digest != source.lease_secret_digest
        ):
            raise RecommendationProtectedContentError(
                "recommendation_protected_content_source_not_found"
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            correlation_id=correlation_id,
        )
        return source, inspection_policy, assignment, review_request, assessment, artifact, policy

    async def _reuse(
        self,
        claim: RecommendationProtectedContentClaim,
        *,
        actor: AuthenticatedSubject,
        source: RecommendationProtectedInspectionRecord,
        artifact: PromotedRecommendationArtifact,
        policy: RecommendationProtectedContentPolicySnapshot,
        subject_digest: str,
        browser_digest: str,
        request_digest: str,
        idempotency_digest: str,
        correlation_id: str,
    ) -> RecommendationProtectedContentGrant:
        self._verify_claim(claim)
        if (
            claim.claimed_by_subject_digest != subject_digest
            or claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_digest
            or claim.idempotency_digest != idempotency_digest
        ):
            raise RecommendationProtectedContentError(
                "recommendation_protected_content_idempotency_conflict"
            )
        record = await self._repository.get(presentation_id=claim.presentation_id)
        if record is None:
            raise RecommendationProtectedContentError(
                "recommendation_protected_content_already_claimed"
            )
        self._verify_record(record)
        instruction = self._instruction(record.presentation_id, source, artifact, policy)
        grant = await self._presenter.present(instruction)
        self._verify_grant(instruction, grant.receipt, grant.content, policy)
        if (
            grant.receipt.presented_content_digest != record.presented_content_digest
            or grant.receipt.content_bytes != record.protected_content_bytes_returned
        ):
            raise RecommendationProtectedContentUncertainError(
                "recommendation_protected_content_replay_drift"
            )
        await self._audit(
            actor,
            correlation_id,
            "recommendation_protected_content_read",
            record.presentation_id,
            (("content_bytes", str(record.protected_content_bytes_returned)),),
            permission_id=RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_READ,
        )
        return RecommendationProtectedContentGrant(
            record=replace(record, reused=True), content=grant.content
        )

    @staticmethod
    def _instruction(
        presentation_id: str,
        source: RecommendationProtectedInspectionRecord,
        artifact: PromotedRecommendationArtifact,
        policy: RecommendationProtectedContentPolicySnapshot,
    ) -> RecommendationProtectedContentInstruction:
        return RecommendationProtectedContentInstruction(
            presentation_id=presentation_id,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            lease_id=source.lease_id,
            lease_digest=source.canonical_digest,
            assignment_set_id=source.source_assignment_set_id,
            track_code=source.track_code,
            opaque_assignment_id=source.opaque_assignment_id,
            lease_holder_subject_digest=source.lease_holder_subject_digest,
            browser_session_binding_digest=source.browser_session_binding_digest,
            recommendation_id=artifact.recommendation_id,
            promotion_id=artifact.promotion_id,
            recommendation_artifact_digest=artifact.canonical_digest,
            source_binding_digest=artifact.source_binding_digest,
            classification=artifact.classification,
            outcome=artifact.outcome,
            headline=artifact.headline,
            safety_notice=artifact.safety_notice,
            options=artifact.options,
            evidence_needs=artifact.evidence_needs,
            output_media_type=policy.output_media_type,
            language=policy.language,
            redaction_profile_id=policy.redaction_profile_id,
            maximum_content_bytes=policy.maximum_content_bytes,
            presentation_policy_digest=policy.canonical_digest,
            expires_at=source.expires_at,
        )

    @classmethod
    def _verify_grant(
        cls,
        instruction: RecommendationProtectedContentInstruction,
        receipt: RecommendationProtectedContentReceipt,
        content: str,
        policy: RecommendationProtectedContentPolicySnapshot,
    ) -> None:
        encoded = content.encode("utf-8")
        if (
            cls._receipt_digest(receipt) != receipt.canonical_digest
            or receipt.schema_version != policy.required_receipt_schema
            or receipt.presenter_id != policy.required_presenter_id
            or receipt.attested_by != policy.required_presenter_attestor_id
            or receipt.presentation_id != instruction.presentation_id
            or receipt.lease_id != instruction.lease_id
            or receipt.lease_digest != instruction.lease_digest
            or receipt.recommendation_id != instruction.recommendation_id
            or receipt.promotion_id != instruction.promotion_id
            or receipt.recommendation_artifact_digest != instruction.recommendation_artifact_digest
            or receipt.track_code != instruction.track_code
            or receipt.lease_holder_subject_digest != instruction.lease_holder_subject_digest
            or receipt.browser_session_binding_digest != instruction.browser_session_binding_digest
            or receipt.output_media_type != policy.output_media_type
            or receipt.language != instruction.language
            or receipt.presented_content_digest != sha256(encoded).hexdigest()
            or receipt.content_bytes != len(encoded)
            or not 1 <= receipt.content_bytes <= policy.maximum_content_bytes
            or receipt.source_binding_digest != instruction.source_binding_digest
            or receipt.expires_at != instruction.expires_at
        ):
            raise RecommendationProtectedContentUncertainError(
                "recommendation_protected_content_receipt_invalid"
            )

    @staticmethod
    def _record(
        claim: RecommendationProtectedContentClaim,
        source: RecommendationProtectedInspectionRecord,
        artifact: PromotedRecommendationArtifact,
        policy: RecommendationProtectedContentPolicySnapshot,
        receipt: RecommendationProtectedContentReceipt,
    ) -> RecommendationProtectedContentRecord:
        record = RecommendationProtectedContentRecord(
            presentation_id=receipt.presentation_id,
            schema_version=CONTENT_RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            source_lease_id=source.lease_id,
            source_lease_digest=source.canonical_digest,
            source_assignment_set_id=source.source_assignment_set_id,
            recommendation_id=source.recommendation_id,
            review_request_id=source.review_request_id,
            readiness_assessment_id=source.readiness_assessment_id,
            promotion_id=source.promotion_id,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            classification=source.classification,
            source_outcome=source.source_outcome,
            option_count=source.option_count,
            preferred_count=source.preferred_count,
            track_code=source.track_code,
            opaque_assignment_id=source.opaque_assignment_id,
            lease_holder_subject_digest=source.lease_holder_subject_digest,
            browser_session_binding_digest=source.browser_session_binding_digest,
            recommendation_artifact_digest=artifact.canonical_digest,
            source_binding_digest=receipt.source_binding_digest,
            output_media_type=receipt.output_media_type,
            language=receipt.language,
            presented_content_digest=receipt.presented_content_digest,
            protected_content_bytes_returned=receipt.content_bytes,
            redaction_digest=receipt.redaction_digest,
            truncation_digest=receipt.truncation_digest,
            cleanup_digest=receipt.cleanup_digest,
            presentation_policy_id=policy.policy_id,
            presentation_policy_digest=policy.canonical_digest,
            presentation_policy_version=policy.policy_version,
            presenter_id=receipt.presenter_id,
            presented_at=receipt.presented_at,
            expires_at=receipt.expires_at,
            state=RECOMMENDATION_PROTECTED_CONTENT_PRESENTED,
            purpose=claim.purpose,
            truncated=receipt.truncated,
            canonical_digest="0" * 64,
        )
        return replace(
            record,
            canonical_digest=RecommendationProtectedContentService._digest(
                RecommendationProtectedContentService._record_payload(record)
            ),
        )

    @classmethod
    def _verify_policy(cls, policy: RecommendationProtectedContentPolicySnapshot) -> None:
        if cls._digest(cls._policy_payload(policy)) != policy.canonical_digest:
            raise RecommendationProtectedContentError(
                "recommendation_protected_content_policy_integrity_failed"
            )

    @classmethod
    def _verify_claim(cls, claim: RecommendationProtectedContentClaim) -> None:
        if cls._digest(cls._claim_payload(claim)) != claim.canonical_digest:
            raise RecommendationProtectedContentError(
                "recommendation_protected_content_claim_integrity_failed"
            )

    @classmethod
    def _verify_record(cls, record: RecommendationProtectedContentRecord) -> None:
        if cls._digest(cls._record_payload(record)) != record.canonical_digest:
            raise RecommendationProtectedContentError(
                "recommendation_protected_content_record_integrity_failed"
            )

    @classmethod
    def _policy_payload(
        cls, policy: RecommendationProtectedContentPolicySnapshot
    ) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(policy))
        payload.pop("canonical_digest")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _claim_payload(cls, claim: RecommendationProtectedContentClaim) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(claim))
        payload.pop("canonical_digest")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _record_payload(cls, record: RecommendationProtectedContentRecord) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(record))
        for field in ("canonical_digest", "reused"):
            payload.pop(field)
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _receipt_digest(cls, receipt: RecommendationProtectedContentReceipt) -> str:
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
            raise RecommendationProtectedContentError(
                "recommendation_protected_content_enterprise_human_hardware_mfa_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise RecommendationProtectedContentError(
                "recommendation_protected_content_source_not_found"
            )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.recommendations.protected-content",
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
                resource_type="resource.recommendations.protected-content",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=metadata,
            )
        )


def build_development_recommendation_protected_content_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> RecommendationProtectedContentPolicySnapshot:
    digest = RecommendationProtectedContentService._digest
    policy = RecommendationProtectedContentPolicySnapshot(
        policy_id="recommendation-protected-content-policy.development",
        schema_version=CONTENT_POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-v1",
        required_source_schema="atlas.recommendation-protected-inspection-lease.v1",
        required_source_state=RECOMMENDATION_PROTECTED_INSPECTION_LEASED,
        required_presenter_id="recommendation-protected-content-presenter.synthetic",
        required_presenter_attestor_id=(
            "subject.recommendation-protected-content-presenter-attestor"
        ),
        required_receipt_schema="atlas.recommendation-protected-content-receipt.v1",
        subject_digest_salt_digest=digest(["recommendation-reviewer-subject-salt.v1"]),
        output_media_type="media-type.text-plain",
        language="language.en",
        redaction_profile_id="redaction-profile.recommendation-review-v1",
        maximum_authentication_age_minutes=15,
        maximum_content_bytes=32_768,
        require_exact_replay=True,
        require_plain_text=True,
        required_assurance_level=AssuranceLevel.HARDWARE_BACKED,
        signed_by="subject.recommendation-protected-content-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy,
        canonical_digest=digest(RecommendationProtectedContentService._policy_payload(policy)),
    )
