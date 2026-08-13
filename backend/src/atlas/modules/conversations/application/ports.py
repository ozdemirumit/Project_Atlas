from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from atlas.modules.conversations.domain.models import (
    AuthorizedConversationTarget,
    ConversationGenerationRequest,
    ConversationGenerationResult,
    ConversationScope,
    OperationalConversation,
)


@dataclass(frozen=True, slots=True)
class ConversationTargetAccessRequest:
    subject_id: str
    principal_ids: frozenset[str]
    scope: ConversationScope


class ConversationTargetAccessSource(Protocol):
    async def authorized_storage_targets(
        self, request: ConversationTargetAccessRequest
    ) -> tuple[AuthorizedConversationTarget, ...]: ...


class ConversationOperationsError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class ConversationGenerationUnavailable(Exception):
    def __init__(self, code: str = "conversation_generation_unavailable") -> None:
        super().__init__(code)
        self.code = code


class ConversationMutationStatus(StrEnum):
    CREATED = "created"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    VERSION_CONFLICT = "version_conflict"
    NOT_FOUND = "not_found"


@dataclass(frozen=True, slots=True)
class ConversationMutationResult:
    status: ConversationMutationStatus
    conversation: OperationalConversation | None


@dataclass(frozen=True, slots=True)
class ConversationIdempotencyRecord:
    request_fingerprint: str
    conversation: OperationalConversation


class ConversationRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_by_id(self, *, conversation_id: str) -> OperationalConversation | None: ...

    async def list_owned(
        self,
        *,
        scope: ConversationScope,
        owner_subject_id: str,
        authorized_target_ids: frozenset[str],
        limit: int,
    ) -> tuple[OperationalConversation, ...]: ...

    async def get_create_request(
        self, *, owner_subject_id: str, idempotency_key: str
    ) -> ConversationIdempotencyRecord | None: ...

    async def get_append_request(
        self, *, conversation_id: str, idempotency_key: str
    ) -> ConversationIdempotencyRecord | None: ...

    async def create(
        self,
        record: OperationalConversation,
        *,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> ConversationMutationResult: ...

    async def append(
        self,
        record: OperationalConversation,
        *,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> ConversationMutationResult: ...

    async def close(self) -> None: ...


class ConversationGenerator(Protocol):
    async def generate(
        self, request: ConversationGenerationRequest
    ) -> ConversationGenerationResult: ...
