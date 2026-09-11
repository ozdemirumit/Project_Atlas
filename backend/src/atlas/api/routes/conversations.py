from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Response
from fastapi.responses import StreamingResponse

from atlas.api.conversation_schemas import (
    AppendOperationalConversationTurnInput,
    AuthorizedConversationTargetData,
    ConversationEvidenceReferenceData,
    CreateOperationalConversationInput,
    OperationalConversationData,
    OperationalConversationInventoryData,
    OperationalConversationInventoryResponse,
    OperationalConversationResponse,
    OperationalConversationSummaryData,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_ai_grounded_query,
    authorize_conversation_create,
    authorize_conversation_read,
    authorize_conversation_turn_append,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.conversations.application.ports import (
    ConversationOperationsError,
    ConversationTargetAccessRequest,
    ConversationTargetAccessSource,
)
from atlas.modules.conversations.application.service import (
    ConversationAccessContext,
    ConversationService,
)
from atlas.modules.conversations.domain.models import (
    AuthorizedConversationTarget,
    ConversationScope,
    OperationalConversation,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/conversations", tags=["conversations"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")
LAST_EVENT_ID = Header(alias="Last-Event-ID", max_length=128)

# How often a heartbeat comment is emitted while the real `ConversationService.append_turn`
# call is still pending, so the connection is provably alive during the wait. This is a plain
# module constant (rather than a Settings field) so tests can patch it directly to exercise the
# heartbeat path deterministically without waiting on the production interval.
CONVERSATION_STREAM_HEARTBEAT_INTERVAL_SECONDS: float = 15.0


@dataclass(frozen=True, slots=True)
class ConversationTurnStreamEvent:
    """One Server-Sent Event in the `turns/stream` wire format.

    Every field is real: `sequence_id` is a monotonically increasing counter starting at 0,
    `event` is one of the typed names from docs/050_API.md §21 (`started`, `evidence_added`,
    `status`, `error`, `completed`), and `data` holds values copied directly from the real
    domain/service result -- nothing here is synthesized or simulated.
    """

    event: str
    sequence_id: int
    data: dict[str, object]

    def encode(self) -> str:
        payload = json.dumps(self.data, sort_keys=True, separators=(",", ":"), default=str)
        return f"event: {self.event}\ndata: {payload}\nid: {self.sequence_id}\n\n"


_STREAM_HEADERS = {
    "Cache-Control": "no-store, max-age=0",
    "Pragma": "no-cache",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    # Server-Sent Events must not be buffered by an intermediary proxy, or heartbeats and
    # events would arrive in one delayed burst instead of as they are genuinely produced.
    "X-Accel-Buffering": "no",
}


def _meta(request: Request) -> ResponseMeta:
    return ResponseMeta(
        correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
    )


def _no_store(response: Response) -> None:
    response.headers.update(
        {
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        }
    )


async def _context(
    request: Request,
    subject: AuthenticatedSubject,
    decision: AuthorizationDecision,
    *,
    generation_decision: AuthorizationDecision | None = None,
) -> tuple[ConversationAccessContext, tuple[AuthorizedConversationTarget, ...]]:
    settings = request.app.state.settings
    scope = ConversationScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{settings.environment}",
        site_id="site.local",
    )
    principal_ids = frozenset((*subject.role_ids, *subject.group_ids))
    source: ConversationTargetAccessSource = request.app.state.conversation_target_access_source
    try:
        targets = await source.authorized_storage_targets(
            ConversationTargetAccessRequest(
                subject_id=subject.subject_id,
                principal_ids=principal_ids,
                scope=scope,
            )
        )
    except Exception as error:
        raise AtlasError(
            status=503,
            code="conversation_target_authority_unavailable",
            title="Conversation target authority unavailable",
            detail="Authorized storage targets could not be resolved safely.",
            retryable=True,
        ) from error
    target_ids = tuple(target.target_id for target in targets)
    if len(target_ids) > 100 or len(target_ids) != len(set(target_ids)):
        raise AtlasError(
            status=503,
            code="conversation_target_authority_invalid",
            title="Conversation target authority invalid",
            detail="Authorized storage targets did not satisfy the bounded contract.",
            retryable=False,
        )
    context = ConversationAccessContext(
        subject_id=subject.subject_id,
        role_ids=principal_ids,
        actor_type=subject.kind.value,
        authentication_method=subject.authentication_method.value,
        assurance_level=subject.assurance_level.value,
        scope=scope,
        authorized_target_ids=frozenset(target_ids),
        correlation_id=str(request.state.correlation_id),
        decision_id=decision.decision_id,
        generation_decision_id=(generation_decision or decision).decision_id,
        requested_at=datetime.now(UTC),
    )
    return context, targets


def _raise(error: ConversationOperationsError) -> NoReturn:
    code = error.code
    if code in {"conversation_not_found", "conversation_target_unavailable"}:
        status = 404
        detail = "The requested conversation resource is unavailable."
        title = "Conversation unavailable"
    elif code.endswith("_invalid") or code.endswith("_required"):
        status = 422
        detail = "The conversation request did not satisfy the governed contract."
        title = "Conversation request invalid"
    elif code in {
        "conversation_repository_unavailable",
        "conversation_repository_scope_violation",
        "conversation_generation_validation_failed",
    }:
        status = 503
        detail = "The governed conversation service could not safely complete the request."
        title = "Conversation service unavailable"
    else:
        status = 409
        detail = "The conversation state no longer permits this operation."
        title = "Conversation operation conflict"
    raise AtlasError(
        status=status,
        code=code,
        title=title,
        detail=detail,
        retryable=False,
    ) from error


def _response(
    conversation: OperationalConversation, request: Request, response: Response
) -> OperationalConversationResponse:
    _no_store(response)
    return OperationalConversationResponse(
        data=OperationalConversationData.from_domain(conversation), meta=_meta(request)
    )


@router.get("", response_model=OperationalConversationInventoryResponse)
async def list_operational_conversations(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_conversation_read)],
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
) -> OperationalConversationInventoryResponse:
    service: ConversationService = request.app.state.conversation_service
    try:
        context, targets = await _context(request, subject, decision)
        conversations = await service.list(context=context, limit=limit)
    except ConversationOperationsError as error:
        _raise(error)
    _no_store(response)
    return OperationalConversationInventoryResponse(
        data=OperationalConversationInventoryData(
            conversations=[
                OperationalConversationSummaryData.from_domain(item) for item in conversations
            ],
            authorized_targets=[
                AuthorizedConversationTargetData.from_domain(item) for item in targets
            ],
            durable=service.durable,
            truncated=len(conversations) == limit,
        ),
        meta=_meta(request),
    )


@router.post("", response_model=OperationalConversationResponse, status_code=201)
async def create_operational_conversation(
    payload: CreateOperationalConversationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_conversation_create)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> OperationalConversationResponse:
    service: ConversationService = request.app.state.conversation_service
    try:
        context, _ = await _context(request, subject, decision)
        conversation = await service.create(
            title=payload.title,
            target_id=payload.target_id,
            idempotency_key=idempotency_key,
            context=context,
        )
    except ConversationOperationsError as error:
        _raise(error)
    return _response(conversation, request, response)


@router.get("/{conversation_id}", response_model=OperationalConversationResponse)
async def get_operational_conversation(
    conversation_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_conversation_read)],
) -> OperationalConversationResponse:
    service: ConversationService = request.app.state.conversation_service
    try:
        context, _ = await _context(request, subject, decision)
        conversation = await service.get(
            conversation_id=conversation_id,
            context=context,
        )
    except ConversationOperationsError as error:
        _raise(error)
    return _response(conversation, request, response)


@router.post(
    "/{conversation_id}/turns",
    response_model=OperationalConversationResponse,
)
async def append_operational_conversation_turn(
    conversation_id: Annotated[str, SAFE_ID],
    payload: AppendOperationalConversationTurnInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_conversation_turn_append)],
    generation_decision: Annotated[AuthorizationDecision, Depends(authorize_ai_grounded_query)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> OperationalConversationResponse:
    service: ConversationService = request.app.state.conversation_service
    try:
        context, _ = await _context(
            request,
            subject,
            decision,
            generation_decision=generation_decision,
        )
        conversation = await service.append_turn(
            conversation_id=conversation_id,
            question=payload.question,
            expected_version=payload.expected_version,
            idempotency_key=idempotency_key,
            context=context,
        )
    except ConversationOperationsError as error:
        _raise(error)
    return _response(conversation, request, response)


@router.post(
    "/{conversation_id}/turns/stream",
    responses={
        200: {"description": "Server-Sent Events stream", "content": {"text/event-stream": {}}}
    },
)
async def append_operational_conversation_turn_stream(
    conversation_id: Annotated[str, SAFE_ID],
    payload: AppendOperationalConversationTurnInput,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_conversation_turn_append)],
    generation_decision: Annotated[AuthorizationDecision, Depends(authorize_ai_grounded_query)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
    last_event_id: Annotated[str | None, LAST_EVENT_ID] = None,
) -> StreamingResponse:
    """Additive SSE counterpart to `append_operational_conversation_turn`.

    This does not reimplement or duplicate any generation/business logic: it runs the exact
    same `ConversationService.append_turn(...)` call as the synchronous endpoint, as an
    `asyncio` task, and narrates its real progress as typed SSE events while genuinely waiting
    for it. There is no per-token or per-stage streaming from the model -- `append_turn` calls
    `GroundedAnswerService.answer()` as one atomic, already-validated unit (draft tokens are
    never treated as validated output; see docs/050_API.md §21), so this endpoint is honest
    about only having two real moments to report: "the governed call started" and "the governed
    call produced a real, validated result (or a real, governed failure)". Everything emitted
    between those two moments is a heartbeat comment proving the connection is alive while a
    real awaitable is genuinely still pending -- never a fabricated intermediate stage.

    Reconnection: `service.append_turn` is already idempotent on `Idempotency-Key` (see
    `conversation_turn_replayed` in `ConversationService.append_turn`). A client that reconnects
    with the *same* `Idempotency-Key` after a dropped connection will drive the exact same real
    call, which replays the exact same real result, so this stream re-emits the same real events
    in the same order. No separate server-side event-replay buffer is built for this -- the
    `Last-Event-ID` header is accepted per SSE spec convention (and echoed into the `started`
    event for observability) but reconnection semantics come entirely from that already-real
    idempotency mechanism, not from a fabricated cursor implementation.
    """
    service: ConversationService = request.app.state.conversation_service
    context, _ = await _context(
        request,
        subject,
        decision,
        generation_decision=generation_decision,
    )
    correlation_id = context.correlation_id

    async def event_stream() -> AsyncIterator[str]:
        sequence = 0
        yield ConversationTurnStreamEvent(
            event="started",
            sequence_id=sequence,
            data={
                "conversation_id": conversation_id,
                "correlation_id": correlation_id,
                "idempotency_key": idempotency_key,
                "last_event_id": last_event_id,
            },
        ).encode()
        sequence += 1

        task = asyncio.create_task(
            service.append_turn(
                conversation_id=conversation_id,
                question=payload.question,
                expected_version=payload.expected_version,
                idempotency_key=idempotency_key,
                context=context,
            )
        )
        while not task.done():
            await asyncio.wait({task}, timeout=CONVERSATION_STREAM_HEARTBEAT_INTERVAL_SECONDS)
            if not task.done():
                yield ": heartbeat\n\n"

        try:
            conversation = task.result()
        except ConversationOperationsError as error:
            yield ConversationTurnStreamEvent(
                event="error",
                sequence_id=sequence,
                data={"code": error.code, "detail": error.detail},
            ).encode()
            return
        except Exception as error:  # pragma: no cover - defensive, not expected in practice
            yield ConversationTurnStreamEvent(
                event="error",
                sequence_id=sequence,
                data={
                    "code": "conversation_stream_internal_error",
                    "detail": str(error) or "An unexpected error interrupted the stream.",
                },
            ).encode()
            return

        assistant_turn = conversation.turns[-1]
        for evidence in assistant_turn.evidence_references:
            yield ConversationTurnStreamEvent(
                event="evidence_added",
                sequence_id=sequence,
                data=ConversationEvidenceReferenceData.from_domain(evidence).model_dump(
                    mode="json"
                ),
            ).encode()
            sequence += 1
        yield ConversationTurnStreamEvent(
            event="status",
            sequence_id=sequence,
            data={
                "turn_id": assistant_turn.turn_id,
                "ordinal": assistant_turn.ordinal,
                "status": assistant_turn.status.value,
            },
        ).encode()
        sequence += 1
        yield ConversationTurnStreamEvent(
            event="completed",
            sequence_id=sequence,
            data=OperationalConversationData.from_domain(conversation).model_dump(mode="json"),
        ).encode()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=_STREAM_HEADERS,
    )
