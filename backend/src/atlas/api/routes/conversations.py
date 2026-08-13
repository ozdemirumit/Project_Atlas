from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Response

from atlas.api.conversation_schemas import (
    AppendOperationalConversationTurnInput,
    AuthorizedConversationTargetData,
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
