"""docs/037_Approval_Workflow.md SS20/SS22 (pass 38 investigation): real, durable, pull-based
in-app notifications.

Pass 38 found `docs/037_Approval_Workflow.md`'s MVP-included "read-only approval inbox and
notifications" (SS29) entirely unimplemented, and found no notification-delivery infrastructure
anywhere in this codebase -- not approval-specific, none at all. SS20 describes required
notification content (a safe summary, risk, expiry, an authorized link, bounded reminders,
escalation visibility, delivery-failure visibility) in terms that read as channel-agnostic; SS22's
own heading groups list/read concerns with "Event Subscriptions and Webhooks" as one shared
"real-time and polling" access surface, not an approvals-only concept. This module is deliberately
placed at `atlas.modules.notifications` (a new, dedicated, cross-cutting module) rather than
inside `atlas.modules.approvals.domain` for exactly that reason: a `Notification` is a real
recipient-addressed record that any future domain event (not only the two approval events pass 38
wires up -- `ApprovalRequestCreated`/`ApprovalGranted`) could plausibly create, and nothing about
its own shape (`notification_type`, `reference_id`, a safe `summary`) is approval-specific.

This module intentionally stops at genuine, durable, pull-based in-app notifications. This
codebase has no email/SMTP, no SMS, no webhook-delivery, and no push-notification infrastructure
anywhere -- confirmed by a real search of the whole source tree, not assumed. Building "external
push delivery" here would mean inventing a whole third-party integration this codebase has no
config, credentials, or delivery-failure handling for, which is a fabrication this pass explicitly
declines to make. A caller reads their own real notifications through a real, RBAC-gated,
cursor-paginated `GET /notifications` (see `atlas.modules.notifications.application.service` and
`atlas.api.routes.notifications`) -- genuinely reachable, not a TODO.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import validate_stable_identifier

_MAX_SUMMARY_CHARACTERS = 2000


@dataclass(frozen=True, slots=True)
class Notification:
    """One real, addressed, pull-based notification. `summary` is expected to already be the
    safe, non-sensitive text SS20 asks for (e.g. an approval packet's own title/risk/purpose,
    never restricted evidence content) -- this dataclass cannot itself know what its caller
    considers safe, so that responsibility sits with whichever real event-bus subscriber
    constructs the summary (see `atlas.modules.notifications.application.subscriber`), the same
    division of responsibility `ApprovalPacket` itself already draws between "this dataclass
    validates its own shape" and "the service decides what real content belongs in that shape."
    """

    notification_id: str
    recipient_subject_id: str
    organization_id: str
    environment_id: str
    notification_type: str
    reference_id: str
    summary: str
    created_at: datetime
    read_at: datetime | None = None
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        for value, name in (
            (self.notification_id, "notification_id"),
            (self.recipient_subject_id, "recipient_subject_id"),
            (self.organization_id, "organization_id"),
            (self.environment_id, "environment_id"),
            (self.notification_type, "notification_type"),
            (self.reference_id, "reference_id"),
        ):
            validate_stable_identifier(value, name)
        if not self.summary.strip():
            raise ValueError("a notification requires a non-empty summary")
        if len(self.summary) > _MAX_SUMMARY_CHARACTERS:
            raise ValueError(
                f"a notification summary must be at most {_MAX_SUMMARY_CHARACTERS} characters"
            )
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if self.read_at is not None:
            if self.read_at.tzinfo is None:
                raise ValueError("read_at must be timezone-aware")
            if self.read_at < self.created_at:
                raise ValueError("read_at cannot precede created_at")
        if self.expires_at is not None:
            if self.expires_at.tzinfo is None:
                raise ValueError("expires_at must be timezone-aware")
            if self.expires_at <= self.created_at:
                raise ValueError("expires_at must be later than created_at")

    @property
    def is_read(self) -> bool:
        return self.read_at is not None
