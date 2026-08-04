from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, is_dataclass, replace
from datetime import datetime, timedelta
from enum import Enum
from hashlib import sha256
from typing import Any
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.approvals.application.ports import RecommendationProvider
from atlas.modules.approvals.domain.models import (
    ApprovalCreateRequest,
    ApprovalDecision,
    ApprovalOutcome,
    ApprovalPacket,
    ApprovalPlanStep,
    ApprovalRecord,
    ApprovalState,
)
from atlas.modules.recommendations.domain.models import OptionState, RecommendationArtifact

APPROVAL_RESOURCE_ID = "resource.approval.storage.synthetic"
CANONICALIZATION_VERSION = "atlas-approval-packet.v1"
ELIGIBLE_ASSURANCE = frozenset({"single_factor", "multi_factor", "hardware_backed"})


@dataclass(frozen=True, slots=True)
class ApprovalAccessContext:
    subject_id: str
    actor_type: str
    authentication_method: str
    assurance_level: str
    organization_id: str
    environment_id: str
    site_id: str
    resource_id: str
    correlation_id: str
    decision_id: str
    requested_at: datetime


class ApprovalOperationsError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class ApprovalService:
    def __init__(
        self,
        *,
        recommendation_provider: RecommendationProvider,
        audit_sink: AuditSink,
    ) -> None:
        self._recommendation_provider = recommendation_provider
        self._audit_sink = audit_sink
        self._records: dict[str, ApprovalRecord] = {}
        self._idempotency: dict[tuple[str, str], tuple[str, ApprovalRecord]] = {}
        self._lock = asyncio.Lock()

    async def create(
        self,
        request: ApprovalCreateRequest,
        *,
        context: ApprovalAccessContext,
    ) -> ApprovalRecord:
        self._validate_context(context)
        recommendation = await self._load_recommendation(request)
        option = next(
            (item for item in recommendation.options if item.option_id == request.option_id),
            None,
        )
        if option is None or option.state is not OptionState.VIABLE:
            raise ApprovalOperationsError(
                "approval_source_unavailable",
                "The requested approval source is unavailable.",
            )
        self._validate_recommendation(recommendation, request, context)
        request_id = f"approval_{uuid4().hex}"
        expires_at = min(
            context.requested_at + timedelta(minutes=request.expires_in_minutes),
            recommendation.expires_at,
        )
        if expires_at <= context.requested_at:
            raise ApprovalOperationsError(
                "approval_source_expired",
                "The requested approval source is no longer current.",
            )
        values = self._packet_values(
            request_id=request_id,
            request=request,
            recommendation=recommendation,
            option=option,
            context=context,
            expires_at=expires_at,
        )
        digest = self._digest_values(values)
        packet = ApprovalPacket(canonical_digest=digest, **values)
        record = ApprovalRecord(
            request_id=request_id,
            version=1,
            state=ApprovalState.PENDING,
            packet=packet,
            created_at=context.requested_at,
            updated_at=context.requested_at,
            decisions=(),
            execution_authorized=False,
        )
        await self._audit(
            context,
            event_type="atlas.approval.request.created",
            outcome="succeeded",
            result_code="approval_packet_created",
            request_id=request_id,
            permission_id="approval.request.create",
        )
        async with self._lock:
            self._records[request_id] = record
        return record

    async def get(
        self,
        request_id: str,
        *,
        context: ApprovalAccessContext,
    ) -> ApprovalRecord:
        self._validate_context(context)
        async with self._lock:
            record = self._records.get(request_id)
            if not self._visible(record, context):
                await self._deny(context, "approval_not_found", request_id=request_id)
                raise ApprovalOperationsError(
                    "approval_not_found",
                    "The requested approval is unavailable.",
                )
            assert record is not None
            record = await self._expire_if_needed(record, context)
            await self._revalidate(record, context)
            await self._audit(
                context,
                event_type="atlas.approval.request.read",
                outcome="succeeded",
                result_code="approval_packet_returned",
                request_id=request_id,
                permission_id="approval.request.read",
            )
            return record

    async def decide(
        self,
        request_id: str,
        *,
        outcome: ApprovalOutcome,
        rationale: str,
        expected_version: int,
        idempotency_key: str,
        context: ApprovalAccessContext,
    ) -> ApprovalRecord:
        self._validate_context(context)
        fingerprint = self._decision_fingerprint(
            outcome=outcome,
            rationale=rationale,
            expected_version=expected_version,
            reviewer_id=context.subject_id,
        )
        async with self._lock:
            record = self._records.get(request_id)
            if not self._visible(record, context):
                await self._deny(context, "approval_not_found", request_id=request_id)
                raise ApprovalOperationsError(
                    "approval_not_found",
                    "The requested approval is unavailable.",
                )
            assert record is not None
            record = await self._expire_if_needed(record, context)
            await self._revalidate(record, context)
            await self._validate_reviewer(record, context)
            replay = self._idempotency.get((request_id, idempotency_key))
            if replay is not None:
                if replay[0] != fingerprint:
                    await self._deny(
                        context, "approval_idempotency_conflict", request_id=request_id
                    )
                    raise ApprovalOperationsError(
                        "approval_idempotency_conflict",
                        "The approval decision conflicts with an earlier request.",
                    )
                await self._audit(
                    context,
                    event_type="atlas.approval.decision.replayed",
                    outcome="succeeded",
                    result_code="approval_decision_replayed",
                    request_id=request_id,
                    permission_id="approval.request.decide",
                )
                return record
            if record.state is not ApprovalState.PENDING or record.version != expected_version:
                await self._deny(context, "approval_state_conflict", request_id=request_id)
                raise ApprovalOperationsError(
                    "approval_state_conflict",
                    "The approval request changed before this decision.",
                )
            next_state = {
                ApprovalOutcome.APPROVE: ApprovalState.APPROVED,
                ApprovalOutcome.REJECT: ApprovalState.REJECTED,
                ApprovalOutcome.NEEDS_EVIDENCE: ApprovalState.NEEDS_EVIDENCE,
                ApprovalOutcome.DEFER: ApprovalState.DEFERRED,
            }[outcome]
            decision = ApprovalDecision(
                decision_id=f"approval_decision_{uuid4().hex}",
                request_version=record.version,
                outcome=outcome,
                reviewer_id=context.subject_id,
                decided_at=context.requested_at,
                rationale=rationale,
            )
            updated = replace(
                record,
                version=record.version + 1,
                state=next_state,
                updated_at=context.requested_at,
                decisions=(*record.decisions, decision),
            )
            await self._audit(
                context,
                event_type="atlas.approval.decision.recorded",
                outcome="succeeded",
                result_code=f"approval_{outcome.value}",
                request_id=request_id,
                permission_id="approval.request.decide",
            )
            self._records[request_id] = updated
            self._idempotency[(request_id, idempotency_key)] = (fingerprint, updated)
            return updated

    async def _load_recommendation(self, request: ApprovalCreateRequest) -> RecommendationArtifact:
        try:
            return await self._recommendation_provider.get_recommendation(
                request.recommendation_id,
                request.recommendation_version,
                request.target_id,
            )
        except KeyError as exc:
            raise ApprovalOperationsError(
                "approval_source_unavailable",
                "The requested approval source is unavailable.",
            ) from exc

    @staticmethod
    def _validate_context(context: ApprovalAccessContext) -> None:
        if context.resource_id != APPROVAL_RESOURCE_ID:
            raise ApprovalOperationsError(
                "approval_scope_mismatch",
                "The approval request is outside the authorized scope.",
            )

    @staticmethod
    def _validate_recommendation(
        recommendation: RecommendationArtifact,
        request: ApprovalCreateRequest,
        context: ApprovalAccessContext,
    ) -> None:
        if (
            recommendation.recommendation_id != request.recommendation_id
            or recommendation.version != request.recommendation_version
            or recommendation.target_id != request.target_id
            or recommendation.organization_id != context.organization_id
            or recommendation.environment_id != context.environment_id
            or recommendation.site_id != context.site_id
            or recommendation.expires_at <= context.requested_at
            or recommendation.execution_authorized
        ):
            raise ApprovalOperationsError(
                "approval_source_unavailable",
                "The requested approval source is unavailable.",
            )

    @classmethod
    def _packet_values(
        cls,
        *,
        request_id: str,
        request: ApprovalCreateRequest,
        recommendation: RecommendationArtifact,
        option: Any,
        context: ApprovalAccessContext,
        expires_at: datetime,
    ) -> dict[str, Any]:
        evidence_ids = set(option.supporting_evidence + option.contradicting_evidence)
        evidence = tuple(
            item for item in recommendation.source_evidence if item.evidence_id in evidence_ids
        )
        alternatives = tuple(
            item.title
            for item in recommendation.options
            if item.option_id != option.option_id and item.state is OptionState.VIABLE
        )
        return {
            "request_id": request_id,
            "packet_version": 1,
            "canonicalization_version": CANONICALIZATION_VERSION,
            "requested_by": context.subject_id,
            "purpose": request.purpose,
            "created_at": context.requested_at,
            "expires_at": expires_at,
            "organization_id": context.organization_id,
            "environment_id": context.environment_id,
            "site_id": context.site_id,
            "target_id": request.target_id,
            "recommendation_id": recommendation.recommendation_id,
            "recommendation_version": recommendation.version,
            "source_case_id": recommendation.source_case_id,
            "source_case_version": recommendation.source_case_version,
            "option_id": option.option_id,
            "option_version": option.version,
            "option_title": option.title,
            "option_category": option.category.value,
            "option_confidence": option.confidence,
            "confidence_rationale": option.confidence_rationale,
            "overall_risk": option.overall_risk.value,
            "risk_rationales": tuple(item.rationale for item in option.risk_dimensions),
            "evidence_references": tuple(item.evidence_id for item in evidence),
            "evidence_summaries": tuple(item.summary for item in evidence),
            "alternatives": alternatives,
            "assumptions": option.assumptions,
            "unknowns": option.unknowns,
            "affected_components": option.impact.affected_components,
            "possibly_affected_services": option.impact.possibly_affected_services,
            "blast_radius": option.impact.blast_radius,
            "impact_confirmed": option.impact.impact_confirmed,
            "graph_maturity": option.impact.graph_maturity,
            "impact_gaps": option.impact.gaps,
            "duration_minimum_minutes": option.duration.minimum_minutes,
            "duration_maximum_minutes": option.duration.maximum_minutes,
            "duration_basis": option.duration.basis,
            "interruption_expected_mode": option.interruption.expected_mode,
            "interruption_worst_credible_mode": option.interruption.worst_credible_mode,
            "interruption_expected_minutes": option.interruption.expected_minutes,
            "interruption_worst_credible_minutes": option.interruption.worst_credible_minutes,
            "interruption_unknowns": option.interruption.unknowns,
            "plan_steps": tuple(
                ApprovalPlanStep(
                    order=item.order,
                    step_id=item.step_id,
                    conceptual_action=item.conceptual_action,
                    capability_id=item.capability_id,
                    capability_class=item.capability_class,
                    expected_output=item.expected_output,
                    stop_condition=item.stop_condition,
                )
                for item in option.plan_steps
            ),
            "preconditions": option.preconditions,
            "success_criteria": option.success_criteria,
            "verification_criteria": option.verification_criteria,
            "stop_conditions": option.stop_conditions,
            "recovery_strategy": option.recovery.strategy,
            "rollback_feasible": option.recovery.rollback_feasible,
            "recovery_duration_minimum_minutes": (
                option.recovery.estimated_duration.minimum_minutes
            ),
            "recovery_duration_maximum_minutes": (
                option.recovery.estimated_duration.maximum_minutes
            ),
            "recovery_gaps": option.recovery.gaps,
            "policy_constraints": recommendation.policy_constraints,
            "execution_authorized": False,
        }

    async def _revalidate(self, record: ApprovalRecord, context: ApprovalAccessContext) -> None:
        values = asdict(record.packet)
        digest = values.pop("canonical_digest")
        if digest != self._digest_values(values):
            await self._deny(context, "approval_digest_mismatch", request_id=record.request_id)
            raise ApprovalOperationsError(
                "approval_digest_mismatch",
                "The approval packet failed integrity validation.",
            )
        try:
            recommendation = await self._recommendation_provider.get_recommendation(
                record.packet.recommendation_id,
                record.packet.recommendation_version,
                record.packet.target_id,
            )
        except KeyError as exc:
            await self._deny(context, "approval_source_changed", request_id=record.request_id)
            raise ApprovalOperationsError(
                "approval_source_changed",
                "The approval source failed current validation.",
            ) from exc
        if (
            recommendation.organization_id != record.packet.organization_id
            or recommendation.environment_id != record.packet.environment_id
            or recommendation.site_id != record.packet.site_id
            or recommendation.requested_by != record.packet.requested_by
            or recommendation.execution_authorized
        ):
            await self._deny(context, "approval_source_changed", request_id=record.request_id)
            raise ApprovalOperationsError(
                "approval_source_changed",
                "The approval source failed current validation.",
            )
        option = next(
            (
                item
                for item in recommendation.options
                if item.option_id == record.packet.option_id and item.state is OptionState.VIABLE
            ),
            None,
        )
        if option is None:
            await self._deny(context, "approval_source_changed", request_id=record.request_id)
            raise ApprovalOperationsError(
                "approval_source_changed",
                "The approval source failed current validation.",
            )
        source_context = replace(
            context,
            subject_id=record.packet.requested_by,
            organization_id=record.packet.organization_id,
            environment_id=record.packet.environment_id,
            site_id=record.packet.site_id,
            requested_at=record.packet.created_at,
        )
        source_request = ApprovalCreateRequest(
            recommendation_id=record.packet.recommendation_id,
            recommendation_version=record.packet.recommendation_version,
            target_id=record.packet.target_id,
            option_id=record.packet.option_id,
            purpose=record.packet.purpose,
            expires_in_minutes=5,
        )
        source_values = self._packet_values(
            request_id=record.request_id,
            request=source_request,
            recommendation=recommendation,
            option=option,
            context=source_context,
            expires_at=record.packet.expires_at,
        )
        if self._digest_values(source_values) != digest:
            await self._deny(context, "approval_source_changed", request_id=record.request_id)
            raise ApprovalOperationsError(
                "approval_source_changed",
                "The approval source failed current validation.",
            )

    @classmethod
    def _digest_values(cls, values: dict[str, Any]) -> str:
        canonical = json.dumps(
            cls._canonical_value(values),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return sha256(canonical.encode()).hexdigest()

    @classmethod
    def _canonical_value(cls, value: Any) -> Any:
        if is_dataclass(value) and not isinstance(value, type):
            return cls._canonical_value(asdict(value))
        if isinstance(value, datetime):
            return value.isoformat(timespec="microseconds")
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {key: cls._canonical_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._canonical_value(item) for item in value]
        return value

    @staticmethod
    def _visible(record: ApprovalRecord | None, context: ApprovalAccessContext) -> bool:
        return bool(
            record
            and record.packet.organization_id == context.organization_id
            and record.packet.environment_id == context.environment_id
            and record.packet.site_id == context.site_id
        )

    async def _expire_if_needed(
        self, record: ApprovalRecord, context: ApprovalAccessContext
    ) -> ApprovalRecord:
        if (
            record.state
            in {
                ApprovalState.PENDING,
                ApprovalState.APPROVED,
                ApprovalState.DEFERRED,
            }
            and context.requested_at >= record.packet.expires_at
        ):
            expired = replace(
                record,
                version=record.version + 1,
                state=ApprovalState.EXPIRED,
                updated_at=context.requested_at,
            )
            await self._audit(
                context,
                event_type="atlas.approval.request.expired",
                outcome="succeeded",
                result_code="approval_request_expired",
                request_id=record.request_id,
                permission_id="approval.request.read",
            )
            self._records[record.request_id] = expired
            return expired
        return record

    async def _validate_reviewer(
        self, record: ApprovalRecord, context: ApprovalAccessContext
    ) -> None:
        reason = None
        if context.actor_type != "human":
            reason = "approval_human_reviewer_required"
        elif context.assurance_level not in ELIGIBLE_ASSURANCE:
            reason = "approval_assurance_insufficient"
        elif context.subject_id == record.packet.requested_by:
            reason = "approval_separation_required"
        if reason is not None:
            await self._deny(context, reason, request_id=record.request_id)
            raise ApprovalOperationsError(
                reason, "The current identity cannot decide this request."
            )

    @classmethod
    def _decision_fingerprint(
        cls,
        *,
        outcome: ApprovalOutcome,
        rationale: str,
        expected_version: int,
        reviewer_id: str,
    ) -> str:
        return cls._digest_values(
            {
                "outcome": outcome.value,
                "rationale": rationale,
                "expected_version": expected_version,
                "reviewer_id": reviewer_id,
            }
        )

    async def _deny(
        self,
        context: ApprovalAccessContext,
        result_code: str,
        *,
        request_id: str,
    ) -> None:
        await self._audit(
            context,
            event_type="atlas.approval.denied",
            outcome="denied",
            result_code=result_code,
            request_id=request_id,
            permission_id="approval.request.decide",
        )

    async def _audit(
        self,
        context: ApprovalAccessContext,
        *,
        event_type: str,
        outcome: str,
        result_code: str,
        request_id: str,
        permission_id: str,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=event_type,
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level=context.assurance_level,
                permission_id=permission_id,
                resource_type="resource.approval",
                scope_reference="/".join(
                    (
                        context.organization_id,
                        context.environment_id,
                        context.site_id,
                        request_id,
                    )
                ),
                decision_id=context.decision_id,
                outcome=outcome,
                result_code=result_code,
            )
        )
