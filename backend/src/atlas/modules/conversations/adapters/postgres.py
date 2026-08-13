from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from hashlib import sha256
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from atlas.core.persistence.models import (
    OperationalConversationIdempotencyModel,
    OperationalConversationModel,
    OperationalConversationTurnModel,
)
from atlas.modules.conversations.application.ports import (
    ConversationIdempotencyRecord,
    ConversationMutationResult,
    ConversationMutationStatus,
)
from atlas.modules.conversations.domain.models import (
    ConversationArtifactReference,
    ConversationAuthority,
    ConversationEvidenceReference,
    ConversationLifecycle,
    ConversationScope,
    ConversationTurn,
    ConversationTurnRole,
    ConversationTurnStatus,
    OperationalConversation,
    canonical_digest,
)


class PostgreSQLConversationRepository:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self._engine = engine
        self._sessions = session_factory or async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLConversationRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get_by_id(self, *, conversation_id: str) -> OperationalConversation | None:
        async with self._sessions() as session:
            return await self._load_conversation(session, conversation_id=conversation_id)

    async def list_owned(
        self,
        *,
        scope: ConversationScope,
        owner_subject_id: str,
        authorized_target_ids: frozenset[str],
        limit: int,
    ) -> tuple[OperationalConversation, ...]:
        statement = (
            select(OperationalConversationModel)
            .where(
                OperationalConversationModel.organization_id == scope.organization_id,
                OperationalConversationModel.environment_id == scope.environment_id,
                OperationalConversationModel.site_id == scope.site_id,
                OperationalConversationModel.owner_subject_id == owner_subject_id,
                OperationalConversationModel.target_id.in_(authorized_target_ids),
            )
            .order_by(
                OperationalConversationModel.updated_at.desc(),
                OperationalConversationModel.conversation_id.desc(),
            )
            .limit(limit)
        )
        async with self._sessions() as session:
            rows = (await session.scalars(statement)).all()
            turns_by_conversation = await self._load_turns(
                session, tuple(row.conversation_id for row in rows)
            )
            return tuple(
                self._to_domain(row.payload, turns_by_conversation.get(row.conversation_id, ()))
                for row in rows
            )

    async def get_create_request(
        self, *, owner_subject_id: str, idempotency_key: str
    ) -> ConversationIdempotencyRecord | None:
        return await self._get_idempotency_record(
            operation="create",
            scope_id=owner_subject_id,
            idempotency_key=idempotency_key,
        )

    async def get_append_request(
        self, *, conversation_id: str, idempotency_key: str
    ) -> ConversationIdempotencyRecord | None:
        return await self._get_idempotency_record(
            operation="append",
            scope_id=conversation_id,
            idempotency_key=idempotency_key,
        )

    async def create(
        self,
        record: OperationalConversation,
        *,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> ConversationMutationResult:
        operation = "create"
        scope_id = record.owner_subject_id
        async with self._sessions() as session:
            prior = await self._replay_result(
                session,
                operation=operation,
                scope_id=scope_id,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
            )
            if prior is not None:
                return prior
            if record.version != 1 or record.turns:
                return ConversationMutationResult(
                    ConversationMutationStatus.IDEMPOTENCY_CONFLICT, None
                )
            try:
                session.add(self._conversation_model(record))
                session.add(
                    self._idempotency_model(
                        operation=operation,
                        scope_id=scope_id,
                        idempotency_key=idempotency_key,
                        request_fingerprint=request_fingerprint,
                        record=record,
                        appended_turns=(),
                    )
                )
                await session.commit()
                return ConversationMutationResult(ConversationMutationStatus.CREATED, record)
            except IntegrityError:
                await session.rollback()

        return await self._result_after_integrity_conflict(
            operation=operation,
            scope_id=scope_id,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            conversation_id=record.conversation_id,
        )

    async def append(
        self,
        record: OperationalConversation,
        *,
        expected_version: int,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> ConversationMutationResult:
        operation = "append"
        scope_id = record.conversation_id
        async with self._sessions() as session:
            prior = await self._replay_result(
                session,
                operation=operation,
                scope_id=scope_id,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
            )
            if prior is not None:
                return prior

            row = await session.scalar(
                select(OperationalConversationModel)
                .where(OperationalConversationModel.conversation_id == record.conversation_id)
                .with_for_update()
            )
            if row is None:
                await session.rollback()
                return ConversationMutationResult(ConversationMutationStatus.NOT_FOUND, None)

            # The lock may have waited for a concurrent identical append. Re-check its claim
            # under the fresh READ COMMITTED snapshot before considering the version.
            prior = await self._replay_result(
                session,
                operation=operation,
                scope_id=scope_id,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
            )
            if prior is not None:
                await session.rollback()
                return prior

            current_turns = await self._load_turns(session, (record.conversation_id,))
            current = self._to_domain(row.payload, current_turns.get(record.conversation_id, ()))
            if current.version != expected_version:
                await session.rollback()
                return ConversationMutationResult(
                    ConversationMutationStatus.VERSION_CONFLICT, current
                )

            appended_turns = self._validate_append_transition(
                current=current,
                candidate=record,
                expected_version=expected_version,
            )
            if appended_turns is None:
                await session.rollback()
                return ConversationMutationResult(
                    ConversationMutationStatus.VERSION_CONFLICT, current
                )

            values = self._conversation_columns(record)
            try:
                result = cast(
                    CursorResult[Any],
                    await session.execute(
                        update(OperationalConversationModel)
                        .where(
                            OperationalConversationModel.conversation_id == record.conversation_id,
                            OperationalConversationModel.version == expected_version,
                        )
                        .values(**values)
                    ),
                )
                if result.rowcount != 1:
                    await session.rollback()
                    latest = await self.get_by_id(conversation_id=record.conversation_id)
                    return ConversationMutationResult(
                        ConversationMutationStatus.VERSION_CONFLICT, latest
                    )
                session.add_all(
                    self._turn_model(record.conversation_id, turn) for turn in appended_turns
                )
                session.add(
                    self._idempotency_model(
                        operation=operation,
                        scope_id=scope_id,
                        idempotency_key=idempotency_key,
                        request_fingerprint=request_fingerprint,
                        record=record,
                        appended_turns=appended_turns,
                    )
                )
                await session.commit()
                return ConversationMutationResult(ConversationMutationStatus.CREATED, record)
            except IntegrityError:
                await session.rollback()

        return await self._result_after_integrity_conflict(
            operation=operation,
            scope_id=scope_id,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            conversation_id=record.conversation_id,
        )

    async def close(self) -> None:
        await self._engine.dispose()

    async def _result_after_integrity_conflict(
        self,
        *,
        operation: str,
        scope_id: str,
        idempotency_key: str,
        request_fingerprint: str,
        conversation_id: str,
    ) -> ConversationMutationResult:
        async with self._sessions() as session:
            replay = await self._replay_result(
                session,
                operation=operation,
                scope_id=scope_id,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
            )
            if replay is not None:
                return replay
            current = await self._load_conversation(session, conversation_id=conversation_id)
            status = (
                ConversationMutationStatus.VERSION_CONFLICT
                if operation == "append" and current is not None
                else ConversationMutationStatus.IDEMPOTENCY_CONFLICT
            )
            return ConversationMutationResult(status, current)

    async def _replay_result(
        self,
        session: AsyncSession,
        *,
        operation: str,
        scope_id: str,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> ConversationMutationResult | None:
        claim = await self._load_idempotency_claim(
            session,
            operation=operation,
            scope_id=scope_id,
            idempotency_key=idempotency_key,
        )
        if claim is None:
            return None
        conversation = self._conversation_from_claim(claim)
        if claim.request_fingerprint != request_fingerprint:
            return ConversationMutationResult(
                ConversationMutationStatus.IDEMPOTENCY_CONFLICT, conversation
            )
        if conversation is None:
            return ConversationMutationResult(ConversationMutationStatus.IDEMPOTENCY_CONFLICT, None)
        return ConversationMutationResult(ConversationMutationStatus.REPLAY, conversation)

    async def _get_idempotency_record(
        self,
        *,
        operation: str,
        scope_id: str,
        idempotency_key: str,
    ) -> ConversationIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_idempotency_claim(
                session,
                operation=operation,
                scope_id=scope_id,
                idempotency_key=idempotency_key,
            )
            if claim is None:
                return None
            conversation = self._conversation_from_claim(claim)
            if conversation is None:
                return None
            return ConversationIdempotencyRecord(
                request_fingerprint=claim.request_fingerprint,
                conversation=conversation,
            )

    @staticmethod
    async def _load_idempotency_claim(
        session: AsyncSession,
        *,
        operation: str,
        scope_id: str,
        idempotency_key: str,
    ) -> OperationalConversationIdempotencyModel | None:
        return cast(
            OperationalConversationIdempotencyModel | None,
            await session.scalar(
                select(OperationalConversationIdempotencyModel).where(
                    OperationalConversationIdempotencyModel.operation == operation,
                    OperationalConversationIdempotencyModel.idempotency_scope_id == scope_id,
                    OperationalConversationIdempotencyModel.idempotency_key == idempotency_key,
                )
            ),
        )

    async def _load_conversation(
        self,
        session: AsyncSession,
        *,
        conversation_id: str,
    ) -> OperationalConversation | None:
        row = await session.get(OperationalConversationModel, conversation_id)
        if row is None:
            return None
        turns = await self._load_turns(session, (conversation_id,))
        return self._to_domain(row.payload, turns.get(conversation_id, ()))

    @staticmethod
    async def _load_turns(
        session: AsyncSession, conversation_ids: tuple[str, ...]
    ) -> dict[str, tuple[ConversationTurn, ...]]:
        if not conversation_ids:
            return {}
        rows = (
            await session.scalars(
                select(OperationalConversationTurnModel)
                .where(OperationalConversationTurnModel.conversation_id.in_(conversation_ids))
                .order_by(
                    OperationalConversationTurnModel.conversation_id,
                    OperationalConversationTurnModel.ordinal,
                )
            )
        ).all()
        grouped: dict[str, list[ConversationTurn]] = {}
        for row in rows:
            grouped.setdefault(row.conversation_id, []).append(
                PostgreSQLConversationRepository._turn_to_domain(row.payload)
            )
        return {key: tuple(value) for key, value in grouped.items()}

    @staticmethod
    def _validate_append_transition(
        *,
        current: OperationalConversation,
        candidate: OperationalConversation,
        expected_version: int,
    ) -> tuple[ConversationTurn, ...] | None:
        immutable_matches = (
            current.conversation_id == candidate.conversation_id
            and current.scope == candidate.scope
            and current.owner_subject_id == candidate.owner_subject_id
            and current.target_id == candidate.target_id
            and current.target_type == candidate.target_type
            and current.created_by == candidate.created_by
            and current.created_at == candidate.created_at
            and current.durable == candidate.durable
        )
        current_digests = tuple(turn.canonical_digest for turn in current.turns)
        candidate_prefix = tuple(
            turn.canonical_digest for turn in candidate.turns[: len(current.turns)]
        )
        appended = candidate.turns[len(current.turns) :]
        if (
            not immutable_matches
            or candidate.version != expected_version + 1
            or current_digests != candidate_prefix
            or len(appended) != 2
        ):
            return None
        return appended

    @classmethod
    def _conversation_from_claim(
        cls, claim: OperationalConversationIdempotencyModel
    ) -> OperationalConversation | None:
        raw_conversation = claim.payload.get("result_conversation")
        raw_turns = claim.payload.get("result_turns")
        if not isinstance(raw_conversation, dict) or not isinstance(raw_turns, list):
            return None
        try:
            turns = tuple(
                cls._turn_to_domain(cast(dict[str, Any], item))
                for item in raw_turns
                if isinstance(item, dict)
            )
            if len(turns) != len(raw_turns):
                return None
            conversation = cls._to_domain(cast(dict[str, Any], raw_conversation), turns)
        except (KeyError, TypeError, ValueError):
            return None
        if (
            claim.conversation_id != conversation.conversation_id
            or claim.owner_subject_id != conversation.owner_subject_id
            or claim.organization_id != conversation.scope.organization_id
            or claim.environment_id != conversation.scope.environment_id
            or claim.site_id != conversation.scope.site_id
            or claim.result_version != conversation.version
            or claim.result_digest != conversation.canonical_digest
        ):
            return None
        appended_turn_digests = tuple(
            str(value) for value in claim.payload.get("appended_turn_digests", ())
        )
        if claim.operation == "append" and appended_turn_digests != tuple(
            turn.canonical_digest for turn in conversation.turns[-2:]
        ):
            return None
        return conversation

    @classmethod
    def _conversation_model(cls, record: OperationalConversation) -> OperationalConversationModel:
        return OperationalConversationModel(**cls._conversation_columns(record))

    @classmethod
    def _conversation_columns(cls, record: OperationalConversation) -> dict[str, Any]:
        return {
            "conversation_id": record.conversation_id,
            "version": record.version,
            "lifecycle": record.lifecycle.value,
            "title": record.title,
            "target_type": record.target_type,
            "target_id": record.target_id,
            "owner_subject_id": record.owner_subject_id,
            "organization_id": record.scope.organization_id,
            "environment_id": record.scope.environment_id,
            "site_id": record.scope.site_id,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "canonical_digest": record.canonical_digest,
            "payload": cls._conversation_payload(record),
        }

    @classmethod
    def _conversation_payload(cls, record: OperationalConversation) -> dict[str, Any]:
        payload = cast(dict[str, Any], cls._normalize(asdict(record)))
        payload.pop("turns", None)
        return payload

    @classmethod
    def _turn_model(
        cls, conversation_id: str, turn: ConversationTurn
    ) -> OperationalConversationTurnModel:
        return OperationalConversationTurnModel(
            turn_id=turn.turn_id,
            conversation_id=conversation_id,
            ordinal=turn.ordinal,
            role=turn.role.value,
            status=turn.status.value,
            observed_at=turn.observed_at,
            canonical_digest=turn.canonical_digest,
            payload=cast(dict[str, Any], cls._normalize(asdict(turn))),
        )

    @classmethod
    def _idempotency_model(
        cls,
        *,
        operation: str,
        scope_id: str,
        idempotency_key: str,
        request_fingerprint: str,
        record: OperationalConversation,
        appended_turns: Sequence[ConversationTurn],
    ) -> OperationalConversationIdempotencyModel:
        payload: dict[str, Any] = {
            "appended_turn_digests": [turn.canonical_digest for turn in appended_turns],
            "conversation_id": record.conversation_id,
            "idempotency_key": idempotency_key,
            "idempotency_scope_id": scope_id,
            "operation": operation,
            "owner_subject_id": record.owner_subject_id,
            "request_fingerprint": request_fingerprint,
            "result_digest": record.canonical_digest,
            "result_conversation": cls._conversation_payload(record),
            "result_turns": [
                cast(dict[str, Any], cls._normalize(asdict(turn))) for turn in record.turns
            ],
            "result_version": record.version,
            "scope": record.scope.canonical_value(),
        }
        digest = canonical_digest(payload)
        created_at = record.created_at if operation == "create" else record.updated_at
        return OperationalConversationIdempotencyModel(
            record_id=f"conversation_idem_{sha256(digest.encode()).hexdigest()[:32]}",
            operation=operation,
            idempotency_scope_id=scope_id,
            owner_subject_id=record.owner_subject_id,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            result_digest=record.canonical_digest,
            conversation_id=record.conversation_id,
            result_version=record.version,
            organization_id=record.scope.organization_id,
            environment_id=record.scope.environment_id,
            site_id=record.scope.site_id,
            created_at=created_at,
            canonical_digest=digest,
            payload=payload,
        )

    @staticmethod
    def _normalize(value: object) -> object:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {
                str(key): PostgreSQLConversationRepository._normalize(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [PostgreSQLConversationRepository._normalize(item) for item in value]
        return value

    @staticmethod
    def _to_domain(
        raw: dict[str, Any], turns: tuple[ConversationTurn, ...]
    ) -> OperationalConversation:
        payload = dict(raw)
        payload["scope"] = ConversationScope(**cast(Any, payload["scope"]))
        payload["lifecycle"] = ConversationLifecycle(str(payload["lifecycle"]))
        payload["created_at"] = datetime.fromisoformat(str(payload["created_at"]))
        payload["updated_at"] = datetime.fromisoformat(str(payload["updated_at"]))
        payload["turns"] = turns
        return OperationalConversation(**cast(Any, payload))

    @staticmethod
    def _turn_to_domain(raw: dict[str, Any]) -> ConversationTurn:
        payload = dict(raw)
        payload["role"] = ConversationTurnRole(str(payload["role"]))
        payload["status"] = ConversationTurnStatus(str(payload["status"]))
        payload["observed_at"] = datetime.fromisoformat(str(payload["observed_at"]))
        evidence_references: list[ConversationEvidenceReference] = []
        for raw_evidence in payload["evidence_references"]:
            evidence = dict(raw_evidence)
            evidence["observed_at"] = datetime.fromisoformat(str(evidence["observed_at"]))
            evidence_references.append(ConversationEvidenceReference(**cast(Any, evidence)))
        payload["evidence_references"] = tuple(evidence_references)
        payload["artifact_references"] = tuple(
            ConversationArtifactReference(**cast(Any, item))
            for item in payload["artifact_references"]
        )
        for field in ("assumptions", "unknowns", "confidence_basis"):
            payload[field] = tuple(payload[field])
        payload["authority"] = ConversationAuthority(**cast(Any, payload["authority"]))
        return ConversationTurn(**cast(Any, payload))
