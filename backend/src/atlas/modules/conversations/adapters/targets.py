from __future__ import annotations

from atlas.modules.conversations.application.ports import ConversationTargetAccessRequest
from atlas.modules.conversations.domain.models import (
    AuthorizedConversationTarget,
    ConversationScope,
)


class EmptyConversationTargetAccessSource:
    async def authorized_storage_targets(
        self, request: ConversationTargetAccessRequest
    ) -> tuple[AuthorizedConversationTarget, ...]:
        return ()


class DevelopmentConversationTargetAccessSource:
    def __init__(
        self,
        *,
        subject_id: str,
        required_principal_ids: frozenset[str],
        scope: ConversationScope,
        targets: tuple[AuthorizedConversationTarget, ...],
    ) -> None:
        self._subject_id = subject_id
        self._required_principal_ids = required_principal_ids
        self._scope = scope
        self._targets = targets

    async def authorized_storage_targets(
        self, request: ConversationTargetAccessRequest
    ) -> tuple[AuthorizedConversationTarget, ...]:
        if (
            request.subject_id != self._subject_id
            or request.scope != self._scope
            or not self._required_principal_ids.intersection(request.principal_ids)
        ):
            return ()
        return self._targets
