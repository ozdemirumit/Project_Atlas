from __future__ import annotations

import asyncio

from atlas.modules.conversations.application.ports import (
    ConversationIdempotencyRecord,
    ConversationMutationResult,
    ConversationMutationStatus,
)
from atlas.modules.conversations.domain.models import ConversationScope, OperationalConversation


class InMemoryConversationRepository:
    def __init__(self) -> None:
        self._records: dict[str, OperationalConversation] = {}
        self._create_requests: dict[tuple[str, str], ConversationIdempotencyRecord] = {}
        self._append_requests: dict[tuple[str, str], ConversationIdempotencyRecord] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get_by_id(self, *, conversation_id: str) -> OperationalConversation | None:
        return self._records.get(conversation_id)

    async def list_owned(
        self,
        *,
        scope: ConversationScope,
        owner_subject_id: str,
        authorized_target_ids: frozenset[str],
        limit: int,
    ) -> tuple[OperationalConversation, ...]:
        records = sorted(
            (
                record
                for record in self._records.values()
                if record.scope == scope
                and record.owner_subject_id == owner_subject_id
                and record.target_id in authorized_target_ids
            ),
            key=lambda record: (record.updated_at, record.conversation_id),
            reverse=True,
        )
        return tuple(records[:limit])

    async def get_create_request(
        self, *, owner_subject_id: str, idempotency_key: str
    ) -> ConversationIdempotencyRecord | None:
        return self._create_requests.get((owner_subject_id, idempotency_key))

    async def get_append_request(
        self, *, conversation_id: str, idempotency_key: str
    ) -> ConversationIdempotencyRecord | None:
        return self._append_requests.get((conversation_id, idempotency_key))

    async def create(
        self,
        record: OperationalConversation,
        *,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> ConversationMutationResult:
        async with self._lock:
            key = (record.owner_subject_id, idempotency_key)
            prior = self._create_requests.get(key)
            if prior is not None:
                status = (
                    ConversationMutationStatus.REPLAY
                    if prior.request_fingerprint == request_fingerprint
                    else ConversationMutationStatus.IDEMPOTENCY_CONFLICT
                )
                return ConversationMutationResult(status, prior.conversation)
            if record.conversation_id in self._records:
                return ConversationMutationResult(
                    ConversationMutationStatus.IDEMPOTENCY_CONFLICT, None
                )
            self._records[record.conversation_id] = record
            self._create_requests[key] = ConversationIdempotencyRecord(
                request_fingerprint=request_fingerprint,
                conversation=record,
            )
            return ConversationMutationResult(ConversationMutationStatus.CREATED, record)

    async def append(
        self,
        record: OperationalConversation,
        *,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> ConversationMutationResult:
        async with self._lock:
            key = (record.conversation_id, idempotency_key)
            prior = self._append_requests.get(key)
            if prior is not None:
                status = (
                    ConversationMutationStatus.REPLAY
                    if prior.request_fingerprint == request_fingerprint
                    else ConversationMutationStatus.IDEMPOTENCY_CONFLICT
                )
                return ConversationMutationResult(status, prior.conversation)
            current = self._records.get(record.conversation_id)
            if current is None:
                return ConversationMutationResult(ConversationMutationStatus.NOT_FOUND, None)
            if current.version != expected_version:
                return ConversationMutationResult(
                    ConversationMutationStatus.VERSION_CONFLICT, current
                )
            self._records[record.conversation_id] = record
            self._append_requests[key] = ConversationIdempotencyRecord(
                request_fingerprint=request_fingerprint,
                conversation=record,
            )
            return ConversationMutationResult(ConversationMutationStatus.CREATED, record)

    async def close(self) -> None:
        return None
