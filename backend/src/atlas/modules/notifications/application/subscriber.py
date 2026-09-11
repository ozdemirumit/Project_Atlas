"""`ApprovalNotificationSubscriber`: the real event-bus subscriber that turns
`ApprovalRequestCreated`/`ApprovalGranted` domain events -- already published by
`ApprovalService` onto the already-wired `InMemoryDomainEventBus` -- into real, durable
`Notification` records.

Recipient derivation is deliberately never fabricated. In both cases the recipients are exactly
"whoever could genuinely act on this request right now" (or, for a grant, "who asked for it"),
derived from the same real, persisted `RoleAssignment` directory the HTTP authorization path
itself already consults:

* `ApprovalRequestCreated`: for a staged request, every subject holding one of
  `reachable_stage_roles()`'s currently-required roles (the exact stage(s)
  `evaluate_plan_state()` is still waiting on), resolved via
  `AuthorizationService.subjects_with_role()`. For a request with no stage plan (the
  single-stage/legacy path -- ATLAS-037's stage machinery is additive, not universal, see
  `atlas.modules.approvals.domain.stages`), every subject holding the same
  `APPROVAL_REQUEST_DECIDE` permission the real `authorize_approval_decide` HTTP dependency
  itself gates a decision on, at the identical `approval_scope(...,
  CapabilityClass.C2_DIAGNOSTIC)` shape, resolved via the parallel
  `AuthorizationService.subjects_with_permission()`. Either branch answers the same question --
  "who could actually decide this" -- the two real RBAC models this codebase happens to use
  (discrete role membership for a stage, flat permission grant otherwise) just require two
  different real lookups to answer it.
* `ApprovalGranted`: the request's own real requester, `ApprovalRecord.packet.requested_by`.

Both handlers fetch the full record through `ApprovalService.get_record_unchecked()` -- a narrow,
explicitly-internal accessor documented on that service as reachable only by a trusted in-process
subscriber, never over HTTP -- because the event envelope alone (`request_id`, org/env ids) does
not carry the stage plan or the requester.

Scope decision (documented, not silently dropped): pass 38 wires exactly these two events.
`cancel()`/`revoke()`/`decide()`'s other outcomes (rejected/needs-evidence/deferred) do not yet
publish a domain event at all -- `ApprovalService` today only calls `_publish_domain_event` from
`create()` and from `decide()`'s full-approval branch (see
`atlas.modules.approvals.application.service`). Notifying on those transitions too is real,
plausible future work SS20's "bounded reminders, escalation visibility" language gestures at, but
it needs new publish sites inside `ApprovalService` itself first (a service-layer change this pass
did not make, to keep `create()`/`decide()`'s existing, already-tested behavior for callers with
no subscriber registered exactly unchanged) -- not something this subscriber can honestly
backfill by guessing at events that are never actually published.
"""

from __future__ import annotations

from atlas.core.capabilities import CapabilityClass
from atlas.core.events import EventEnvelope
from atlas.modules.approvals.application.service import ApprovalService
from atlas.modules.approvals.domain.models import ApprovalRecord
from atlas.modules.approvals.domain.stages import reachable_stage_roles
from atlas.modules.authorization.application.bootstrap import (
    APPROVAL_REQUEST_DECIDE,
    approval_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.notifications.application.service import NotificationService

APPROVAL_REQUEST_CREATED_NOTIFICATION = "notification.approval-request-created"
APPROVAL_GRANTED_NOTIFICATION = "notification.approval-granted"

_SUMMARY_MAX = 480


class ApprovalNotificationSubscriber:
    def __init__(
        self,
        *,
        approval_service: ApprovalService,
        authorization_service: AuthorizationService,
        notification_service: NotificationService,
        environment: str,
    ) -> None:
        self._approvals = approval_service
        self._authorization = authorization_service
        self._notifications = notification_service
        self._environment = environment

    async def handle_request_created(self, envelope: EventEnvelope) -> None:
        record = await self._approvals.get_record_unchecked(envelope.subject_id)
        if record is None:
            return
        recipients = await self._eligible_decision_makers(record)
        summary = self._summary_for_creation(record)
        for recipient in recipients:
            await self._notifications.create(
                recipient_subject_id=recipient,
                organization_id=record.packet.organization_id,
                environment_id=record.packet.environment_id,
                notification_type=APPROVAL_REQUEST_CREATED_NOTIFICATION,
                reference_id=record.request_id,
                summary=summary,
                correlation_id=envelope.correlation_id,
                expires_at=record.packet.expires_at,
            )

    async def handle_granted(self, envelope: EventEnvelope) -> None:
        record = await self._approvals.get_record_unchecked(envelope.subject_id)
        if record is None:
            return
        await self._notifications.create(
            recipient_subject_id=record.packet.requested_by,
            organization_id=record.packet.organization_id,
            environment_id=record.packet.environment_id,
            notification_type=APPROVAL_GRANTED_NOTIFICATION,
            reference_id=record.request_id,
            summary=self._summary_for_grant(record),
            correlation_id=envelope.correlation_id,
        )

    async def _eligible_decision_makers(self, record: ApprovalRecord) -> tuple[str, ...]:
        scope = approval_scope(
            record.packet.organization_id, self._environment, CapabilityClass.C2_DIAGNOSTIC
        )
        if record.stage_plan is None:
            return await self._authorization.subjects_with_permission(
                permission_id=APPROVAL_REQUEST_DECIDE, scope=scope
            )
        reachable_roles = reachable_stage_roles(record.stage_plan, record.stage_decisions)
        recipients: set[str] = set()
        for role_id in reachable_roles:
            recipients.update(
                await self._authorization.subjects_with_role(role_id=role_id, scope=scope)
            )
        return tuple(sorted(recipients))

    @staticmethod
    def _summary_for_creation(record: ApprovalRecord) -> str:
        text = (
            f"Approval requested: {record.packet.option_title} "
            f"({record.packet.overall_risk} risk) -- {record.packet.purpose}"
        )
        return text[:_SUMMARY_MAX]

    @staticmethod
    def _summary_for_grant(record: ApprovalRecord) -> str:
        text = f"Your approval request for {record.packet.option_title!r} was granted."
        return text[:_SUMMARY_MAX]
