from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.conversations.application.ports import (
    ConversationGenerator,
    ConversationMutationResult,
    ConversationMutationStatus,
    ConversationOperationsError,
    ConversationRepository,
)
from atlas.modules.conversations.domain.models import (
    NO_EXECUTION_SAFETY_NOTICE,
    ConversationArtifactReference,
    ConversationAuthority,
    ConversationEvidenceReference,
    ConversationGenerationRequest,
    ConversationGenerationResult,
    ConversationLifecycle,
    ConversationScope,
    ConversationTurn,
    ConversationTurnRole,
    ConversationTurnStatus,
    OperationalConversation,
    canonical_digest,
)


@dataclass(frozen=True, slots=True)
class ConversationAccessContext:
    subject_id: str
    role_ids: frozenset[str]
    actor_type: str
    authentication_method: str
    assurance_level: str
    scope: ConversationScope
    authorized_target_ids: frozenset[str]
    correlation_id: str
    decision_id: str
    generation_decision_id: str
    requested_at: datetime

    def __post_init__(self) -> None:
        values = (
            self.subject_id,
            self.actor_type,
            self.authentication_method,
            self.assurance_level,
            self.correlation_id,
            self.decision_id,
            self.generation_decision_id,
        )
        if any(value != value.strip() or not value or len(value) > 240 for value in values):
            raise ValueError("conversation access context contains an invalid identifier")
        if self.requested_at.tzinfo is None:
            raise ValueError("conversation requested_at must be timezone-aware")
        if any(not target.strip() or len(target) > 240 for target in self.authorized_target_ids):
            raise ValueError("conversation context contains an invalid authorized target")


class ConversationService:
    def __init__(
        self,
        *,
        repository: ConversationRepository,
        generator: ConversationGenerator,
        audit_sink: AuditSink,
    ) -> None:
        self._repository = repository
        self._generator = generator
        self._audit_sink = audit_sink

    @property
    def durable(self) -> bool:
        return self._repository.durable

    async def close(self) -> None:
        await self._repository.close()

    async def create(
        self,
        *,
        title: str,
        target_id: str,
        idempotency_key: str,
        context: ConversationAccessContext,
    ) -> OperationalConversation:
        normalized_title = self._normalized_text(title, name="title", maximum=120)
        normalized_target = self._normalized_identifier(target_id, name="target_id")
        normalized_key = self._idempotency_key(idempotency_key)
        fingerprint = canonical_digest(
            {
                "operation": "conversation.create",
                "owner_subject_id": context.subject_id,
                "scope": context.scope.canonical_value(),
                "target_id": normalized_target,
                "target_type": "storage",
                "title": normalized_title,
            }
        )
        prior = await self._repository.get_create_request(
            owner_subject_id=context.subject_id,
            idempotency_key=normalized_key,
        )
        if prior is not None:
            if prior.request_fingerprint != fingerprint:
                await self._audit(
                    context,
                    event_type="atlas.conversation.create.denied",
                    outcome="denied",
                    result_code="conversation_idempotency_conflict",
                    idempotency_key=normalized_key,
                )
                raise ConversationOperationsError(
                    "conversation_idempotency_conflict",
                    "The idempotency key was already used for a different request.",
                )
            self._validate_owned(prior.conversation, context)
            await self._audit(
                context,
                event_type="atlas.conversation.create.replayed",
                outcome="succeeded",
                result_code="conversation_create_replayed",
                idempotency_key=normalized_key,
                conversation=prior.conversation,
            )
            return prior.conversation
        if normalized_target not in context.authorized_target_ids:
            await self._audit(
                context,
                event_type="atlas.conversation.create.denied",
                outcome="denied",
                result_code="conversation_target_unavailable",
                idempotency_key=normalized_key,
            )
            raise ConversationOperationsError(
                "conversation_target_unavailable",
                "The requested conversation target is unavailable.",
            )
        identity_seed = ":".join((context.subject_id, normalized_key, fingerprint))
        conversation_id = f"conversation.{sha256(identity_seed.encode()).hexdigest()[:24]}"
        record = self._build_conversation(
            conversation_id=conversation_id,
            version=1,
            lifecycle=ConversationLifecycle.OPEN,
            title=normalized_title,
            scope=context.scope,
            owner_subject_id=context.subject_id,
            target_id=normalized_target,
            created_at=context.requested_at,
            updated_at=context.requested_at,
            durable=self._repository.durable,
            turns=(),
        )
        await self._audit(
            context,
            event_type="atlas.conversation.create.authorized",
            outcome="succeeded",
            result_code="conversation_create_authorized",
            idempotency_key=normalized_key,
            conversation=record,
        )
        result = await self._repository.create(
            record,
            idempotency_key=normalized_key,
            request_fingerprint=fingerprint,
        )
        return await self._resolve_mutation(
            result,
            context=context,
            idempotency_key=normalized_key,
            expected_fingerprint=fingerprint,
            replay_event="atlas.conversation.create.replayed",
        )

    async def list(
        self, *, context: ConversationAccessContext, limit: int = 50
    ) -> tuple[OperationalConversation, ...]:
        if not 1 <= limit <= 100:
            raise ConversationOperationsError(
                "conversation_limit_invalid", "Conversation list limit must be between 1 and 100."
            )
        records = await self._repository.list_owned(
            scope=context.scope,
            owner_subject_id=context.subject_id,
            authorized_target_ids=context.authorized_target_ids,
            limit=limit,
        )
        if any(
            record.scope != context.scope
            or record.owner_subject_id != context.subject_id
            or record.target_id not in context.authorized_target_ids
            for record in records
        ):
            raise ConversationOperationsError(
                "conversation_repository_scope_violation",
                "The conversation repository returned data outside the authorized scope.",
            )
        await self._audit(
            context,
            event_type="atlas.conversation.list.read",
            outcome="succeeded",
            result_code="conversation_list_returned",
            metadata=(("result_count", str(len(records))),),
        )
        return records

    async def get(
        self, *, conversation_id: str, context: ConversationAccessContext
    ) -> OperationalConversation:
        normalized_id = self._normalized_identifier(conversation_id, name="conversation_id")
        record = await self._repository.get_by_id(conversation_id=normalized_id)
        if record is None or not self._is_owned(record, context):
            await self._audit(
                context,
                event_type="atlas.conversation.read.denied",
                outcome="denied",
                result_code="conversation_not_found",
            )
            raise ConversationOperationsError(
                "conversation_not_found", "The requested conversation is unavailable."
            )
        await self._audit(
            context,
            event_type="atlas.conversation.read",
            outcome="succeeded",
            result_code="conversation_returned",
            conversation=record,
        )
        return record

    async def append_turn(
        self,
        *,
        conversation_id: str,
        question: str,
        expected_version: int,
        idempotency_key: str,
        context: ConversationAccessContext,
    ) -> OperationalConversation:
        normalized_id = self._normalized_identifier(conversation_id, name="conversation_id")
        normalized_question = self._normalized_text(question, name="question", maximum=700)
        normalized_key = self._idempotency_key(idempotency_key)
        if expected_version < 1:
            raise ConversationOperationsError(
                "conversation_version_invalid", "Expected version must be positive."
            )
        current = await self._repository.get_by_id(conversation_id=normalized_id)
        if current is None or not self._is_owned(current, context):
            await self._audit(
                context,
                event_type="atlas.conversation.turn.denied",
                outcome="denied",
                result_code="conversation_not_found",
                idempotency_key=normalized_key,
            )
            raise ConversationOperationsError(
                "conversation_not_found", "The requested conversation is unavailable."
            )
        fingerprint = canonical_digest(
            {
                "conversation_id": current.conversation_id,
                "expected_version": expected_version,
                "operation": "conversation.turn.append",
                "owner_subject_id": context.subject_id,
                "question": normalized_question,
                "scope": context.scope.canonical_value(),
                "target_id": current.target_id,
            }
        )
        prior = await self._repository.get_append_request(
            conversation_id=current.conversation_id,
            idempotency_key=normalized_key,
        )
        if prior is not None:
            if prior.request_fingerprint != fingerprint:
                await self._audit(
                    context,
                    event_type="atlas.conversation.turn.denied",
                    outcome="denied",
                    result_code="conversation_idempotency_conflict",
                    idempotency_key=normalized_key,
                    conversation=current,
                )
                raise ConversationOperationsError(
                    "conversation_idempotency_conflict",
                    "The idempotency key was already used for a different request.",
                )
            self._validate_owned(prior.conversation, context)
            await self._audit(
                context,
                event_type="atlas.conversation.turn.replayed",
                outcome="succeeded",
                result_code="conversation_turn_replayed",
                idempotency_key=normalized_key,
                conversation=prior.conversation,
            )
            return prior.conversation
        if current.lifecycle is not ConversationLifecycle.OPEN:
            raise ConversationOperationsError(
                "conversation_closed", "Closed conversations cannot accept new turns."
            )
        if current.version != expected_version:
            raise ConversationOperationsError(
                "conversation_version_conflict",
                "The conversation changed; reload it before appending a turn.",
            )
        if len(current.turns) >= 200:
            raise ConversationOperationsError(
                "conversation_turn_limit_reached",
                "The conversation has reached its bounded turn limit.",
            )
        generation_request = ConversationGenerationRequest(
            request_digest=fingerprint,
            conversation_id=current.conversation_id,
            conversation_version=current.version,
            scope=current.scope,
            owner_subject_id=current.owner_subject_id,
            role_ids=context.role_ids,
            decision_id=context.generation_decision_id,
            target_id=current.target_id,
            question=normalized_question,
            prior_turns=current.turns,
            requested_at=context.requested_at,
            correlation_id=context.correlation_id,
        )
        try:
            generated = await self._generator.generate(generation_request)
        except Exception:
            generated = self._failed_generation(generation_request)
        try:
            self._validate_generated(generated, generation_request)
            user_turn = self._build_turn(
                turn_id=self._turn_id(current.conversation_id, normalized_key, fingerprint, "user"),
                ordinal=len(current.turns) + 1,
                role=ConversationTurnRole.USER,
                status=ConversationTurnStatus.COMPLETED,
                text=normalized_question,
                observed_at=context.requested_at,
            )
            assistant_turn = self._build_turn(
                turn_id=self._turn_id(
                    current.conversation_id, normalized_key, fingerprint, "assistant"
                ),
                ordinal=len(current.turns) + 2,
                role=ConversationTurnRole.ASSISTANT,
                status=generated.status,
                text=generated.text,
                observed_at=generated.observed_at,
                evidence_references=generated.evidence_references,
                artifact_references=generated.artifact_references,
                assumptions=generated.assumptions,
                unknowns=generated.unknowns,
                confidence_basis=generated.confidence_basis,
                failure_code=generated.failure_code,
                safety_notice=generated.safety_notice,
                authority=generated.authority,
            )
        except ValueError as error:
            await self._audit(
                context,
                event_type="atlas.conversation.generation.failed",
                outcome="failed",
                result_code="conversation_generation_validation_failed",
                idempotency_key=normalized_key,
                conversation=current,
            )
            raise ConversationOperationsError(
                "conversation_generation_validation_failed",
                "The generated answer did not satisfy the governed conversation contract.",
            ) from error
        updated = self._build_conversation(
            conversation_id=current.conversation_id,
            version=current.version + 1,
            lifecycle=current.lifecycle,
            title=current.title,
            scope=current.scope,
            owner_subject_id=current.owner_subject_id,
            target_id=current.target_id,
            created_at=current.created_at,
            updated_at=context.requested_at,
            durable=current.durable,
            turns=(*current.turns, user_turn, assistant_turn),
        )
        result_code = (
            "conversation_turn_failed"
            if generated.status is ConversationTurnStatus.FAILED
            else "conversation_turn_authorized"
        )
        await self._audit(
            context,
            event_type="atlas.conversation.turn.append.authorized",
            outcome="failed" if generated.status is ConversationTurnStatus.FAILED else "succeeded",
            result_code=result_code,
            idempotency_key=normalized_key,
            conversation=updated,
            metadata=(("assistant_status", generated.status.value),),
        )
        result = await self._repository.append(
            updated,
            expected_version=expected_version,
            idempotency_key=normalized_key,
            request_fingerprint=fingerprint,
        )
        return await self._resolve_mutation(
            result,
            context=context,
            idempotency_key=normalized_key,
            expected_fingerprint=fingerprint,
            replay_event="atlas.conversation.turn.replayed",
        )

    @staticmethod
    def _validate_generated(
        generated: ConversationGenerationResult,
        request: ConversationGenerationRequest,
    ) -> None:
        if (
            generated.request_digest != request.request_digest
            or generated.conversation_id != request.conversation_id
            or generated.scope != request.scope
            or generated.owner_subject_id != request.owner_subject_id
            or generated.target_id != request.target_id
            or generated.observed_at != request.requested_at
            or generated.safety_notice != NO_EXECUTION_SAFETY_NOTICE
            or any(generated.authority.canonical_value().values())
        ):
            raise ValueError("generated response binding mismatch")

    @staticmethod
    def _failed_generation(
        request: ConversationGenerationRequest,
    ) -> ConversationGenerationResult:
        payload = {
            "artifact_references": [],
            "assumptions": (),
            "authority": ConversationAuthority().canonical_value(),
            "confidence_basis": ("No model result was accepted.",),
            "conversation_id": request.conversation_id,
            "evidence_references": [],
            "failure_code": "conversation_generation_unavailable",
            "observed_at": request.requested_at.isoformat(),
            "owner_subject_id": request.owner_subject_id,
            "request_digest": request.request_digest,
            "safety_notice": NO_EXECUTION_SAFETY_NOTICE,
            "scope": request.scope.canonical_value(),
            "status": ConversationTurnStatus.FAILED.value,
            "target_id": request.target_id,
            "text": (
                "Atlas could not produce a governed answer. No conclusion or action was generated."
            ),
            "unknowns": ("The requested question remains unanswered.",),
        }
        return ConversationGenerationResult(
            request_digest=request.request_digest,
            conversation_id=request.conversation_id,
            scope=request.scope,
            owner_subject_id=request.owner_subject_id,
            target_id=request.target_id,
            status=ConversationTurnStatus.FAILED,
            text=str(payload["text"]),
            observed_at=request.requested_at,
            evidence_references=(),
            artifact_references=(),
            assumptions=(),
            unknowns=("The requested question remains unanswered.",),
            confidence_basis=("No model result was accepted.",),
            failure_code="conversation_generation_unavailable",
            safety_notice=NO_EXECUTION_SAFETY_NOTICE,
            authority=ConversationAuthority(),
            result_digest=canonical_digest(payload),
        )

    async def _resolve_mutation(
        self,
        result: ConversationMutationResult,
        *,
        context: ConversationAccessContext,
        idempotency_key: str,
        expected_fingerprint: str,
        replay_event: str,
    ) -> OperationalConversation:
        if result.status is ConversationMutationStatus.CREATED and result.conversation is not None:
            self._validate_owned(result.conversation, context)
            return result.conversation
        if result.status is ConversationMutationStatus.REPLAY and result.conversation is not None:
            self._validate_owned(result.conversation, context)
            await self._audit(
                context,
                event_type=replay_event,
                outcome="succeeded",
                result_code="conversation_mutation_replayed",
                idempotency_key=idempotency_key,
                conversation=result.conversation,
                metadata=(("request_fingerprint", expected_fingerprint),),
            )
            return result.conversation
        if result.status is ConversationMutationStatus.VERSION_CONFLICT:
            await self._audit(
                context,
                event_type=(
                    "atlas.conversation.turn.denied"
                    if ".turn." in replay_event
                    else "atlas.conversation.create.denied"
                ),
                outcome="denied",
                result_code="conversation_version_conflict",
                idempotency_key=idempotency_key,
                conversation=result.conversation,
            )
            raise ConversationOperationsError(
                "conversation_version_conflict",
                "The conversation changed; reload it before retrying.",
            )
        if result.status is ConversationMutationStatus.IDEMPOTENCY_CONFLICT:
            await self._audit(
                context,
                event_type=(
                    "atlas.conversation.turn.denied"
                    if ".turn." in replay_event
                    else "atlas.conversation.create.denied"
                ),
                outcome="denied",
                result_code="conversation_idempotency_conflict",
                idempotency_key=idempotency_key,
                conversation=result.conversation,
            )
            raise ConversationOperationsError(
                "conversation_idempotency_conflict",
                "The idempotency key was already used for a different request.",
            )
        raise ConversationOperationsError(
            "conversation_not_found", "The requested conversation is unavailable."
        )

    @staticmethod
    def _build_turn(
        *,
        turn_id: str,
        ordinal: int,
        role: ConversationTurnRole,
        status: ConversationTurnStatus,
        text: str,
        observed_at: datetime,
        evidence_references: tuple[ConversationEvidenceReference, ...] = (),
        artifact_references: tuple[ConversationArtifactReference, ...] = (),
        assumptions: tuple[str, ...] = (),
        unknowns: tuple[str, ...] = (),
        confidence_basis: tuple[str, ...] = (),
        failure_code: str | None = None,
        safety_notice: str = NO_EXECUTION_SAFETY_NOTICE,
        authority: ConversationAuthority | None = None,
    ) -> ConversationTurn:
        resolved_authority = authority or ConversationAuthority()
        payload = {
            "artifact_references": [item.canonical_value() for item in artifact_references],
            "assumptions": assumptions,
            "authority": resolved_authority.canonical_value(),
            "confidence_basis": confidence_basis,
            "evidence_references": [item.canonical_value() for item in evidence_references],
            "failure_code": failure_code,
            "observed_at": observed_at.isoformat(),
            "ordinal": ordinal,
            "role": role.value,
            "safety_notice": safety_notice,
            "status": status.value,
            "text": text,
            "turn_id": turn_id,
            "unknowns": unknowns,
        }
        return ConversationTurn(
            turn_id=turn_id,
            ordinal=ordinal,
            role=role,
            status=status,
            text=text,
            observed_at=observed_at,
            evidence_references=evidence_references,
            artifact_references=artifact_references,
            assumptions=assumptions,
            unknowns=unknowns,
            confidence_basis=confidence_basis,
            failure_code=failure_code,
            safety_notice=safety_notice,
            authority=resolved_authority,
            canonical_digest=canonical_digest(payload),
        )

    @staticmethod
    def _build_conversation(
        *,
        conversation_id: str,
        version: int,
        lifecycle: ConversationLifecycle,
        title: str,
        scope: ConversationScope,
        owner_subject_id: str,
        target_id: str,
        created_at: datetime,
        updated_at: datetime,
        durable: bool,
        turns: tuple[ConversationTurn, ...],
    ) -> OperationalConversation:
        payload = {
            "conversation_id": conversation_id,
            "created_at": created_at.isoformat(),
            "created_by": owner_subject_id,
            "durable": durable,
            "lifecycle": lifecycle.value,
            "owner_subject_id": owner_subject_id,
            "scope": scope.canonical_value(),
            "target_id": target_id,
            "target_type": "storage",
            "title": title,
            "turn_digests": [turn.canonical_digest for turn in turns],
            "updated_at": updated_at.isoformat(),
            "updated_by": owner_subject_id,
            "version": version,
        }
        return OperationalConversation(
            conversation_id=conversation_id,
            version=version,
            lifecycle=lifecycle,
            title=title,
            scope=scope,
            owner_subject_id=owner_subject_id,
            target_id=target_id,
            target_type="storage",
            created_by=owner_subject_id,
            updated_by=owner_subject_id,
            created_at=created_at,
            updated_at=updated_at,
            durable=durable,
            turns=turns,
            canonical_digest=canonical_digest(payload),
        )

    @staticmethod
    def _turn_id(conversation_id: str, idempotency_key: str, fingerprint: str, role: str) -> str:
        seed = ":".join((conversation_id, idempotency_key, fingerprint, role))
        return f"turn.{sha256(seed.encode()).hexdigest()[:24]}"

    @staticmethod
    def _normalized_text(value: str, *, name: str, maximum: int) -> str:
        normalized = value.strip()
        if not normalized or len(normalized) > maximum:
            raise ConversationOperationsError(
                f"conversation_{name}_invalid",
                f"{name.replace('_', ' ').title()} must contain 1 to {maximum} characters.",
            )
        return normalized

    @staticmethod
    def _normalized_identifier(value: str, *, name: str) -> str:
        normalized = value.strip()
        if (
            not normalized
            or len(normalized) > 240
            or any(character.isspace() for character in normalized)
        ):
            raise ConversationOperationsError(f"conversation_{name}_invalid", f"{name} is invalid.")
        return normalized

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._normalized_identifier(value, name="idempotency_key")
        if not 8 <= len(normalized) <= 200:
            raise ConversationOperationsError(
                "conversation_idempotency_key_invalid",
                "Idempotency key must contain 8 to 200 characters.",
            )
        return normalized

    @staticmethod
    def _is_owned(record: OperationalConversation, context: ConversationAccessContext) -> bool:
        return (
            record.scope == context.scope
            and record.owner_subject_id == context.subject_id
            and record.target_id in context.authorized_target_ids
            and record.target_type == "storage"
        )

    @classmethod
    def _validate_owned(
        cls, record: OperationalConversation, context: ConversationAccessContext
    ) -> None:
        if not cls._is_owned(record, context):
            raise ConversationOperationsError(
                "conversation_not_found", "The requested conversation is unavailable."
            )

    async def _audit(
        self,
        context: ConversationAccessContext,
        *,
        event_type: str,
        outcome: str,
        result_code: str,
        idempotency_key: str | None = None,
        conversation: OperationalConversation | None = None,
        metadata: tuple[tuple[str, str], ...] = (),
    ) -> None:
        if ".turn." in event_type:
            permission_id = "conversation.turn.append"
        elif ".create." in event_type:
            permission_id = "conversation.create"
        else:
            permission_id = "conversation.read"
        target_metadata = list(metadata)
        if conversation is not None:
            target_metadata.extend(
                (
                    ("conversation_id", conversation.conversation_id),
                    ("conversation_version", str(conversation.version)),
                    ("conversation_digest", conversation.canonical_digest),
                    ("target_id", conversation.target_id),
                )
            )
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
                resource_type="resource.operational-conversation",
                scope_reference="/".join(
                    (
                        context.scope.organization_id,
                        context.scope.environment_id,
                        context.scope.site_id,
                        "operational-conversation",
                    )
                ),
                decision_id=context.decision_id,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=tuple(target_metadata),
            )
        )
