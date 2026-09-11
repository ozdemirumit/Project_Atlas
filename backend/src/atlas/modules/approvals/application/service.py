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
from atlas.core.classification import DataClassification
from atlas.core.event_catalog import ApprovalGranted, ApprovalRequestCreated
from atlas.core.events import EventEnvelope, InMemoryDomainEventBus
from atlas.core.pagination import CursorCodec, CursorDecodeError
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
from atlas.modules.approvals.domain.stages import (
    ApprovalStagePlan,
    ApprovalStageRequirement,
    StageDecisionRecord,
    evaluate_plan_state,
    reachable_stage_roles,
)
from atlas.modules.itsm.domain.approval_sync import ItsmExternalApprovalBinding
from atlas.modules.recommendations.domain.models import OptionState, RecommendationArtifact

EVENT_PRODUCER = "approvals"

APPROVAL_RESOURCE_ID = "resource.approval.storage.synthetic"
CANONICALIZATION_VERSION = "atlas-approval-packet.v1"
ELIGIBLE_ASSURANCE = frozenset({"development", "single_factor", "multi_factor", "hardware_backed"})

# Mirrors HumanReviewService.MAX_INBOX_SCAN -- a real, defensive upper bound on how many
# in-memory records list() will scan before paginating in-process.
MAX_APPROVAL_LIST_SCAN = 1000


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
    role_ids: tuple[str, ...] = ()


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
        event_bus: InMemoryDomainEventBus | None = None,
    ) -> None:
        self._recommendation_provider = recommendation_provider
        self._audit_sink = audit_sink
        self._event_bus = event_bus if event_bus is not None else InMemoryDomainEventBus()
        self._records: dict[str, ApprovalRecord] = {}
        self._idempotency: dict[tuple[str, str], tuple[str, ApprovalRecord]] = {}
        self._lock = asyncio.Lock()
        self._cursor_codec = CursorCodec()

    async def create(
        self,
        request: ApprovalCreateRequest,
        *,
        context: ApprovalAccessContext,
        stage_requirements: tuple[ApprovalStageRequirement, ...] | None = None,
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
        stage_plan: ApprovalStagePlan | None = None
        if stage_requirements:
            try:
                stage_plan = ApprovalStagePlan(request_id=request_id, stages=stage_requirements)
            except ValueError as exc:
                raise ApprovalOperationsError(
                    "approval_stage_plan_invalid",
                    "The requested approval stage plan is invalid.",
                ) from exc
        record = ApprovalRecord(
            request_id=request_id,
            version=1,
            state=ApprovalState.PENDING,
            packet=packet,
            created_at=context.requested_at,
            updated_at=context.requested_at,
            decisions=(),
            execution_authorized=False,
            stage_plan=stage_plan,
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
        await self._publish_domain_event(
            context,
            event_type="ApprovalRequestCreated",
            subject_id=request_id,
            payload=ApprovalRequestCreated(
                request_id=request_id,
                packet_version=packet.packet_version,
                requested_by=context.subject_id,
                created_at=context.requested_at,
            ),
        )
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

    async def list(
        self,
        *,
        context: ApprovalAccessContext,
        state: ApprovalState | None = None,
        role_id: str | None = None,
        scope_reference: str | None = None,
        owner_subject_id: str | None = None,
        expiring_before: datetime | None = None,
        cursor: str | None = None,
        limit: int = 20,
        correlation_id: str,
    ) -> tuple[tuple[ApprovalRecord, ...], str | None]:
        """docs/037_Approval_Workflow.md SS22: "List requests by state, role, scope, owner, and
        expiry." A caller sees only requests they own (`packet.requested_by`) or are currently
        eligible to decide -- for a staged request, holding one of `reachable_stage_roles()`'s
        currently-required roles; for a single-stage/legacy request, the same real, non-owner,
        sufficiently-assured human posture `_validate_reviewer()` itself requires before a
        decision can be recorded. There is no elevated cross-scope override today (unlike
        `OperationResourceService.get()`'s `cross_subject_access_allowed` fallback) because no
        such permission exists yet in this codebase's authorization catalog for approvals --
        adding one is real future work, not silently assumed here. For the same reason,
        `owner_subject_id` (if given) must equal the caller's own subject id, and `role_id` (if
        given) must be one of the caller's own `context.role_ids`.

        `role_id`/`scope_reference` further narrow an already-visible result to records actually
        matching that filter -- they can only narrow, never grant visibility a caller otherwise
        lacks. `scope_reference` matches `ApprovalStageRequirement.required_scope_reference`
        directly (the exact string a stage plan already carries); a non-staged record has no
        comparable field and never matches a `scope_reference` filter.

        Cursor pagination is "position in one deterministically ordered, freshly computed result
        list" via `atlas.core.pagination.CursorCodec` -- the same opaque, signed, integrity-
        protected primitive `security_export` already implements privately for its own event
        export, reused here directly since `ApprovalService` (like this whole approvals module)
        has no repository/database layer able to hand back a stable native row sequence.
        """
        self._validate_context(context)
        if not 1 <= limit <= 100:
            raise ApprovalOperationsError(
                "approval_list_limit_invalid", "The requested page size is invalid."
            )
        if owner_subject_id is not None and owner_subject_id != context.subject_id:
            raise ApprovalOperationsError(
                "approval_list_owner_forbidden",
                "A subject may only list their own requests as owner.",
            )
        if role_id is not None and role_id not in context.role_ids:
            raise ApprovalOperationsError(
                "approval_list_role_forbidden",
                "A role filter must be one of the caller's own roles.",
            )
        async with self._lock:
            candidates = list(self._records.values())
        if len(candidates) > MAX_APPROVAL_LIST_SCAN:
            # Mirrors HumanReviewService.inbox()'s own capacity guard: a bounded scan that
            # silently truncated would hide real records from a caller without any signal that
            # happened -- a real, audited error is the honest behavior instead.
            raise ApprovalOperationsError(
                "approval_list_capacity_exceeded",
                "Too many approval requests exist to list in one bounded scan.",
            )
        results: list[ApprovalRecord] = []
        for record in candidates:
            if not self._visible(record, context):
                continue
            effective_state = self._effective_state(record, context.requested_at)
            if state is not None and effective_state is not state:
                continue
            if owner_subject_id is not None and record.packet.requested_by != owner_subject_id:
                continue
            if expiring_before is not None and record.packet.expires_at >= expiring_before:
                continue
            if scope_reference is not None and not self._matches_scope_reference(
                record, scope_reference
            ):
                continue
            is_owner = record.packet.requested_by == context.subject_id
            eligible_roles = (
                reachable_stage_roles(record.stage_plan, record.stage_decisions)
                if record.stage_plan is not None
                else frozenset()
            )
            if record.stage_plan is not None:
                is_eligible_approver = bool(eligible_roles & set(context.role_ids))
            else:
                is_eligible_approver = (
                    context.actor_type == "human"
                    and context.assurance_level in ELIGIBLE_ASSURANCE
                    and not is_owner
                )
            if role_id is not None:
                if record.stage_plan is None or role_id not in eligible_roles:
                    continue
            elif not (is_owner or is_eligible_approver):
                continue
            results.append(record)
        results.sort(key=lambda item: (item.created_at, item.request_id))
        start = 0
        if cursor is not None:
            try:
                start = self._cursor_codec.decode(cursor)
            except CursorDecodeError as exc:
                raise ApprovalOperationsError(
                    "approval_list_cursor_invalid", "The pagination cursor is invalid."
                ) from exc
        page = tuple(results[start : start + limit])
        has_more = start + limit < len(results)
        next_cursor = self._cursor_codec.encode(start + len(page)) if has_more and page else None
        await self._audit(
            context,
            event_type="atlas.approval.request.listed",
            outcome="succeeded",
            result_code="approval_list_read",
            request_id="list",
            permission_id="approval.request.read",
        )
        return page, next_cursor

    async def get_record_unchecked(self, request_id: str) -> ApprovalRecord | None:
        """Internal-only accessor for trusted in-process subscribers reacting to this service's
        own already-published domain events (e.g.
        `atlas.modules.notifications.application.subscriber`) -- never exposed over HTTP, and
        performs no RBAC/audit of its own since there is no external caller to authorize or hold
        accountable. The authority is the already-committed state transition the subscriber is
        reacting to, the same posture `atlas.core.audit` records are written under (no per-write
        permission check of their own)."""
        async with self._lock:
            return self._records.get(request_id)

    async def decide(
        self,
        request_id: str,
        *,
        outcome: ApprovalOutcome,
        rationale: str,
        expected_version: int,
        idempotency_key: str,
        context: ApprovalAccessContext,
        stage_id: str | None = None,
    ) -> ApprovalRecord:
        self._validate_context(context)
        if outcome is ApprovalOutcome.CANCEL:
            raise ApprovalOperationsError(
                "approval_wrong_operation",
                "Use cancel() to withdraw a request; decide() records an approver's decision.",
            )
        if outcome is ApprovalOutcome.REVOKE:
            raise ApprovalOperationsError(
                "approval_wrong_operation",
                "Use revoke() to withdraw an approved request; decide() records the initial"
                " decision.",
            )
        fingerprint = self._decision_fingerprint(
            outcome=outcome,
            rationale=rationale,
            expected_version=expected_version,
            reviewer_id=context.subject_id,
            stage_id=stage_id,
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
            stage: ApprovalStageRequirement | None = None
            if record.stage_plan is None:
                if stage_id is not None:
                    await self._deny(context, "approval_wrong_operation", request_id=request_id)
                    raise ApprovalOperationsError(
                        "approval_wrong_operation",
                        "This request has no stage plan; stage_id must not be supplied.",
                    )
            else:
                if outcome not in (ApprovalOutcome.APPROVE, ApprovalOutcome.REJECT):
                    await self._deny(context, "approval_wrong_operation", request_id=request_id)
                    raise ApprovalOperationsError(
                        "approval_wrong_operation",
                        "Staged approval requests only support approve or reject decisions"
                        " at a stage.",
                    )
                if stage_id is None:
                    await self._deny(context, "approval_stage_required", request_id=request_id)
                    raise ApprovalOperationsError(
                        "approval_stage_required",
                        "A stage_id is required to decide a staged approval request.",
                    )
                stage = next(
                    (item for item in record.stage_plan.stages if item.stage_id == stage_id),
                    None,
                )
                if stage is None:
                    await self._deny(context, "approval_stage_unknown", request_id=request_id)
                    raise ApprovalOperationsError(
                        "approval_stage_unknown",
                        "The specified stage does not exist in this request's stage plan.",
                    )
                if stage.required_role not in context.role_ids:
                    await self._deny(context, "approval_stage_role_mismatch", request_id=request_id)
                    raise ApprovalOperationsError(
                        "approval_stage_role_mismatch",
                        "The current identity does not hold the role required for this"
                        " approval stage.",
                    )
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
            valid_states = (
                {ApprovalState.PENDING}
                if record.stage_plan is None
                else {ApprovalState.PENDING, ApprovalState.PARTIALLY_APPROVED}
            )
            if record.state not in valid_states or record.version != expected_version:
                await self._deny(context, "approval_state_conflict", request_id=request_id)
                raise ApprovalOperationsError(
                    "approval_state_conflict",
                    "The approval request changed before this decision.",
                )
            decision = ApprovalDecision(
                decision_id=f"approval_decision_{uuid4().hex}",
                request_version=record.version,
                outcome=outcome,
                reviewer_id=context.subject_id,
                decided_at=context.requested_at,
                rationale=rationale,
            )
            if record.stage_plan is None or stage is None:
                next_state = {
                    ApprovalOutcome.APPROVE: ApprovalState.APPROVED,
                    ApprovalOutcome.REJECT: ApprovalState.REJECTED,
                    ApprovalOutcome.NEEDS_EVIDENCE: ApprovalState.NEEDS_EVIDENCE,
                    ApprovalOutcome.DEFER: ApprovalState.DEFERRED,
                }[outcome]
                updated = replace(
                    record,
                    version=record.version + 1,
                    state=next_state,
                    updated_at=context.requested_at,
                    decisions=(*record.decisions, decision),
                )
            else:
                stage_decision = StageDecisionRecord(
                    stage_id=stage.stage_id,
                    reviewer_role=stage.required_role,
                    decision=decision,
                )
                updated_stage_decisions = (*record.stage_decisions, stage_decision)
                next_state = evaluate_plan_state(record.stage_plan, updated_stage_decisions)
                updated = replace(
                    record,
                    version=record.version + 1,
                    state=next_state,
                    updated_at=context.requested_at,
                    decisions=(*record.decisions, decision),
                    stage_decisions=updated_stage_decisions,
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
        if updated.state is ApprovalState.APPROVED:
            await self._publish_domain_event(
                context,
                event_type="ApprovalGranted",
                subject_id=request_id,
                payload=ApprovalGranted(
                    request_id=request_id,
                    decision_id=decision.decision_id,
                    reviewer_id=context.subject_id,
                    granted_at=context.requested_at,
                ),
            )
        return updated

    async def cancel(
        self,
        request_id: str,
        *,
        rationale: str,
        expected_version: int,
        idempotency_key: str,
        context: ApprovalAccessContext,
    ) -> ApprovalRecord:
        """SS9: "Cancel: the requester or authorized workflow withdraws the request." SS8's
        state diagram permits this from Pending, NeedsEvidence, or Deferred (this
        implementation has no separate Draft step -- `create()` already submits)."""
        self._validate_context(context)
        if not rationale.strip():
            raise ApprovalOperationsError(
                "approval_rationale_required", "Cancellation requires a rationale."
            )
        async with self._lock:
            record = self._records.get(request_id)
            if not self._visible(record, context):
                await self._deny(context, "approval_not_found", request_id=request_id)
                raise ApprovalOperationsError(
                    "approval_not_found", "The requested approval is unavailable."
                )
            assert record is not None
            record = await self._expire_if_needed(record, context)
            if context.subject_id != record.packet.requested_by:
                await self._deny(context, "approval_cancel_not_requester", request_id=request_id)
                raise ApprovalOperationsError(
                    "approval_cancel_not_requester",
                    "Only the original requester may cancel this request.",
                )
            replay = self._idempotency.get((request_id, idempotency_key))
            if replay is not None:
                if replay[1].state is not ApprovalState.CANCELLED:
                    await self._deny(
                        context, "approval_idempotency_conflict", request_id=request_id
                    )
                    raise ApprovalOperationsError(
                        "approval_idempotency_conflict",
                        "The cancellation conflicts with an earlier request.",
                    )
                return replay[1]
            if (
                record.state
                not in {
                    ApprovalState.PENDING,
                    ApprovalState.NEEDS_EVIDENCE,
                    ApprovalState.DEFERRED,
                }
                or record.version != expected_version
            ):
                await self._deny(context, "approval_state_conflict", request_id=request_id)
                raise ApprovalOperationsError(
                    "approval_state_conflict",
                    "The approval request changed before this cancellation.",
                )
            decision = ApprovalDecision(
                decision_id=f"approval_decision_{uuid4().hex}",
                request_version=record.version,
                outcome=ApprovalOutcome.CANCEL,
                reviewer_id=context.subject_id,
                decided_at=context.requested_at,
                rationale=rationale,
            )
            updated = replace(
                record,
                version=record.version + 1,
                state=ApprovalState.CANCELLED,
                updated_at=context.requested_at,
                decisions=(*record.decisions, decision),
            )
            await self._audit(
                context,
                event_type="atlas.approval.request.cancelled",
                outcome="succeeded",
                result_code="approval_cancelled",
                request_id=request_id,
                permission_id="approval.request.cancel",
            )
            self._records[request_id] = updated
            fingerprint = self._digest_values(
                {
                    "operation": "cancel",
                    "rationale": rationale,
                    "expected_version": expected_version,
                }
            )
            self._idempotency[(request_id, idempotency_key)] = (fingerprint, updated)
            return updated

    async def revoke(
        self,
        request_id: str,
        *,
        rationale: str,
        expected_version: int,
        idempotency_key: str,
        context: ApprovalAccessContext,
    ) -> ApprovalRecord:
        """SS9: "Revoke: a previously valid approval is withdrawn before handoff or
        completion." Unlike cancel (the requester withdrawing their own request), revoke acts
        on an already-Approved record and requires a governance identity distinct from the
        requester -- SS15 lists "an authorized approver or governance role revokes it" as the
        first revocation trigger."""
        self._validate_context(context)
        if not rationale.strip():
            raise ApprovalOperationsError(
                "approval_rationale_required", "Revocation requires a rationale."
            )
        async with self._lock:
            record = self._records.get(request_id)
            if not self._visible(record, context):
                await self._deny(context, "approval_not_found", request_id=request_id)
                raise ApprovalOperationsError(
                    "approval_not_found", "The requested approval is unavailable."
                )
            assert record is not None
            record = await self._expire_if_needed(record, context)
            if context.actor_type != "human":
                await self._deny(context, "approval_human_reviewer_required", request_id=request_id)
                raise ApprovalOperationsError(
                    "approval_human_reviewer_required",
                    "Only a human governance identity may revoke an approval.",
                )
            if context.subject_id == record.packet.requested_by:
                await self._deny(context, "approval_separation_required", request_id=request_id)
                raise ApprovalOperationsError(
                    "approval_separation_required",
                    "The original requester cannot revoke their own approved request.",
                )
            replay = self._idempotency.get((request_id, idempotency_key))
            if replay is not None:
                if replay[1].state is not ApprovalState.REVOKED:
                    await self._deny(
                        context, "approval_idempotency_conflict", request_id=request_id
                    )
                    raise ApprovalOperationsError(
                        "approval_idempotency_conflict",
                        "The revocation conflicts with an earlier request.",
                    )
                return replay[1]
            if record.state is not ApprovalState.APPROVED or record.version != expected_version:
                await self._deny(context, "approval_state_conflict", request_id=request_id)
                raise ApprovalOperationsError(
                    "approval_state_conflict",
                    "The approval request changed before this revocation.",
                )
            decision = ApprovalDecision(
                decision_id=f"approval_decision_{uuid4().hex}",
                request_version=record.version,
                outcome=ApprovalOutcome.REVOKE,
                reviewer_id=context.subject_id,
                decided_at=context.requested_at,
                rationale=rationale,
            )
            updated = replace(
                record,
                version=record.version + 1,
                state=ApprovalState.REVOKED,
                updated_at=context.requested_at,
                decisions=(*record.decisions, decision),
            )
            await self._audit(
                context,
                event_type="atlas.approval.request.revoked",
                outcome="succeeded",
                result_code="approval_revoked",
                request_id=request_id,
                permission_id="approval.request.revoke",
            )
            self._records[request_id] = updated
            fingerprint = self._digest_values(
                {
                    "operation": "revoke",
                    "rationale": rationale,
                    "expected_version": expected_version,
                }
            )
            self._idempotency[(request_id, idempotency_key)] = (fingerprint, updated)
            return updated

    async def attach_itsm_binding(
        self,
        request_id: str,
        binding: ItsmExternalApprovalBinding,
        *,
        idempotency_key: str,
        context: ApprovalAccessContext,
    ) -> ApprovalRecord:
        """ATLAS-036 SS12: admits one validated external ITSM approval as an input to this
        request's own approval contract -- never a substitute for it. Only attachable while the
        request is still `PENDING`, since an ITSM binding informs a not-yet-made decision."""
        self._validate_context(context)
        if binding.exact_plan_reference != request_id or binding.atlas_approval_reference not in (
            None,
            request_id,
        ):
            await self._deny(context, "approval_itsm_binding_mismatch", request_id=request_id)
            raise ApprovalOperationsError(
                "approval_itsm_binding_mismatch",
                "The ITSM approval binding does not match this approval request.",
            )
        fingerprint = self._digest_values(
            {
                "operation": "attach_itsm_binding",
                "binding_id": binding.binding_id,
                "external_approval_record_id": binding.external_approval_record_id,
                "external_record_version": binding.external_record_version,
            }
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
            replay = self._idempotency.get((request_id, idempotency_key))
            if replay is not None:
                if replay[0] != fingerprint:
                    await self._deny(
                        context, "approval_idempotency_conflict", request_id=request_id
                    )
                    raise ApprovalOperationsError(
                        "approval_idempotency_conflict",
                        "The ITSM binding attachment conflicts with an earlier request.",
                    )
                return replay[1]
            if record.state is not ApprovalState.PENDING:
                await self._deny(context, "approval_state_conflict", request_id=request_id)
                raise ApprovalOperationsError(
                    "approval_state_conflict",
                    "The approval request changed before this ITSM binding could attach.",
                )
            updated = replace(record, itsm_binding=binding)
            await self._audit(
                context,
                event_type="atlas.approval.itsm_binding.attached",
                outcome="succeeded",
                result_code="approval_itsm_binding_attached",
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

    @staticmethod
    def _effective_state(record: ApprovalRecord, at: datetime) -> ApprovalState:
        """A side-effect-free view of what `record.state` would become if `_expire_if_needed`
        ran right now -- used by `list()` so a bulk read never has to mutate every stored record
        it scans just to answer a `state` filter accurately."""
        if (
            record.state in {ApprovalState.PENDING, ApprovalState.APPROVED, ApprovalState.DEFERRED}
            and at >= record.packet.expires_at
        ):
            return ApprovalState.EXPIRED
        return record.state

    @staticmethod
    def _matches_scope_reference(record: ApprovalRecord, scope_reference: str) -> bool:
        if record.stage_plan is None:
            return False
        return any(
            stage.required_scope_reference == scope_reference for stage in record.stage_plan.stages
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
        stage_id: str | None = None,
    ) -> str:
        return cls._digest_values(
            {
                "outcome": outcome.value,
                "rationale": rationale,
                "expected_version": expected_version,
                "reviewer_id": reviewer_id,
                "stage_id": stage_id,
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

    async def _publish_domain_event(
        self,
        context: ApprovalAccessContext,
        *,
        event_type: str,
        subject_id: str,
        payload: object,
    ) -> None:
        """ATLAS-016: publishes one of the Initial Event Catalog's approval events
        (`ApprovalRequestCreated`/`ApprovalGranted`) after the owned state transition has
        already committed (SS4.3), through the shared in-process bus rather than a bespoke
        approvals-only mechanism."""
        await self._event_bus.publish(
            EventEnvelope(
                event_id=f"evt_{uuid4().hex}",
                event_type=event_type,
                event_version="1.0",
                occurred_at=context.requested_at,
                recorded_at=context.requested_at,
                producer=EVENT_PRODUCER,
                subject_type="approval_request",
                subject_id=subject_id,
                correlation_id=context.correlation_id,
                classification=DataClassification.INTERNAL,
                payload=payload,
                organization_id=context.organization_id,
                environment_id=context.environment_id,
            )
        )
