from __future__ import annotations

from typing import NoReturn

from atlas.modules.conversations.application.ports import (
    ConversationIdempotencyRecord,
    ConversationMutationResult,
    ConversationOperationsError,
)
from atlas.modules.conversations.domain.models import ConversationScope, OperationalConversation


class UnavailableConversationRepository:
    """Fail-closed production adapter used when durable storage is not configured."""

    @property
    def durable(self) -> bool:
        return False

    @staticmethod
    def _raise() -> NoReturn:
        raise ConversationOperationsError(
            "conversation_repository_unavailable",
            "Durable conversation storage is not configured.",
        )

    async def get_by_id(self, *, conversation_id: str) -> OperationalConversation | None:
        self._raise()

    async def list_owned(
        self,
        *,
        scope: ConversationScope,
        owner_subject_id: str,
        authorized_target_ids: frozenset[str],
        limit: int,
    ) -> tuple[OperationalConversation, ...]:
        self._raise()

    async def get_create_request(
        self, *, owner_subject_id: str, idempotency_key: str
    ) -> ConversationIdempotencyRecord | None:
        self._raise()

    async def get_append_request(
        self, *, conversation_id: str, idempotency_key: str
    ) -> ConversationIdempotencyRecord | None:
        self._raise()

    async def create(
        self,
        record: OperationalConversation,
        *,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> ConversationMutationResult:
        self._raise()

    async def append(
        self,
        record: OperationalConversation,
        *,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> ConversationMutationResult:
        self._raise()

    async def close(self) -> None:
        return None
