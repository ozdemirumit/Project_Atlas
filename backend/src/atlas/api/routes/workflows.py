from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_workflow_definition_read,
    authorize_workflow_plan_cancel,
    authorize_workflow_plan_create,
    authorize_workflow_plan_read,
)
from atlas.api.workflow_schemas import (
    CancelWorkflowPlanInput,
    CreateWorkflowPlanInput,
    WorkflowDefinitionData,
    WorkflowDefinitionInventoryData,
    WorkflowDefinitionInventoryResponse,
    WorkflowPlanInventoryData,
    WorkflowPlanInventoryResponse,
    WorkflowRunPlanData,
    WorkflowRunPlanResponse,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.conversations.application.ports import (
    ConversationTargetAccessRequest,
    ConversationTargetAccessSource,
)
from atlas.modules.conversations.domain.models import ConversationScope
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.workflows.application import (
    WorkflowAccessContext,
    WorkflowPlanningError,
    WorkflowPlanningService,
)
from atlas.modules.workflows.domain import WorkflowRunPlan, WorkflowScope

router = APIRouter(prefix="/workflows", tags=["workflows"])
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
) -> WorkflowAccessContext:
    settings = request.app.state.settings
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{settings.environment}",
        site_id="site.local",
    )
    source: ConversationTargetAccessSource = request.app.state.conversation_target_access_source
    try:
        targets = await source.authorized_storage_targets(
            ConversationTargetAccessRequest(
                subject_id=subject.subject_id,
                principal_ids=frozenset((*subject.role_ids, *subject.group_ids)),
                scope=ConversationScope(
                    organization_id=scope.organization_id,
                    environment_id=scope.environment_id,
                    site_id=scope.site_id,
                ),
            )
        )
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_target_authority_unavailable",
            title="Workflow target authority unavailable",
            detail="Authorized storage targets could not be resolved safely.",
            retryable=True,
        ) from error
    target_ids = tuple(target.target_id for target in targets)
    if len(target_ids) > 100 or len(target_ids) != len(set(target_ids)):
        raise AtlasError(
            status=503,
            code="workflow_target_authority_invalid",
            title="Workflow target authority invalid",
            detail="Authorized workflow targets did not satisfy the bounded contract.",
        )
    return WorkflowAccessContext(
        subject_id=subject.subject_id,
        role_ids=frozenset((*subject.role_ids, *subject.group_ids)),
        actor_type=subject.kind.value,
        authentication_method=subject.authentication_method.value,
        assurance_level=subject.assurance_level.value,
        scope=scope,
        authorized_target_ids=frozenset(target_ids),
        correlation_id=str(request.state.correlation_id),
        decision_id=decision.decision_id,
        requested_at=datetime.now(UTC),
    )


def _raise(error: WorkflowPlanningError) -> NoReturn:
    if error.code in {"workflow_plan_not_found", "workflow_target_unavailable"}:
        status, title = 404, "Workflow resource unavailable"
    elif error.code == "workflow_idempotency_conflict":
        status, title = 409, "Workflow plan conflict"
    elif error.code.endswith("_invalid") or error.code.endswith("_required"):
        status, title = 422, "Workflow request invalid"
    elif "repository" in error.code:
        status, title = 503, "Workflow service unavailable"
    else:
        status, title = 409, "Workflow operation unavailable"
    raise AtlasError(
        status=status,
        code=error.code,
        title=title,
        detail=error.detail,
        retryable=status == 503,
    ) from error


def _plan_response(
    plan: WorkflowRunPlan, request: Request, response: Response
) -> WorkflowRunPlanResponse:
    _no_store(response)
    return WorkflowRunPlanResponse(data=WorkflowRunPlanData.from_domain(plan), meta=_meta(request))


@router.get("/definitions", response_model=WorkflowDefinitionInventoryResponse)
async def list_workflow_definitions(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_workflow_definition_read)],
) -> WorkflowDefinitionInventoryResponse:
    service: WorkflowPlanningService = request.app.state.workflow_planning_service
    try:
        definitions = await service.list_definitions(
            context=await _context(request, subject, decision)
        )
    except WorkflowPlanningError as error:
        _raise(error)
    _no_store(response)
    return WorkflowDefinitionInventoryResponse(
        data=WorkflowDefinitionInventoryData(
            definitions=[WorkflowDefinitionData.from_domain(item) for item in definitions]
        ),
        meta=_meta(request),
    )


@router.post("/plans", response_model=WorkflowRunPlanResponse, status_code=201)
async def create_workflow_plan(
    payload: CreateWorkflowPlanInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_workflow_plan_create)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> WorkflowRunPlanResponse:
    service: WorkflowPlanningService = request.app.state.workflow_planning_service
    try:
        plan = await service.create_plan(
            definition_id=payload.definition_id,
            definition_version=payload.definition_version,
            target_id=payload.target_id,
            inputs=payload.inputs,
            idempotency_key=idempotency_key,
            context=await _context(request, subject, decision),
        )
    except WorkflowPlanningError as error:
        _raise(error)
    return _plan_response(plan, request, response)


@router.get("/plans", response_model=WorkflowPlanInventoryResponse)
async def list_workflow_plans(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_workflow_plan_read)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> WorkflowPlanInventoryResponse:
    service: WorkflowPlanningService = request.app.state.workflow_planning_service
    try:
        plans = await service.list_plans(
            context=await _context(request, subject, decision), limit=limit
        )
    except WorkflowPlanningError as error:
        _raise(error)
    _no_store(response)
    return WorkflowPlanInventoryResponse(
        data=WorkflowPlanInventoryData(
            plans=[WorkflowRunPlanData.from_domain(item) for item in plans],
            durable=service.durable,
            truncated=len(plans) == limit,
        ),
        meta=_meta(request),
    )


@router.post("/plans/{plan_id}/cancellation", response_model=WorkflowRunPlanResponse)
async def cancel_workflow_plan(
    plan_id: Annotated[str, SAFE_ID],
    payload: CancelWorkflowPlanInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_workflow_plan_cancel)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> WorkflowRunPlanResponse:
    service: WorkflowPlanningService = request.app.state.workflow_planning_service
    try:
        plan = await service.cancel_plan(
            plan_id=plan_id,
            reason=payload.reason,
            acknowledge_no_external_undo=payload.acknowledge_no_external_undo,
            idempotency_key=idempotency_key,
            context=await _context(request, subject, decision),
        )
    except WorkflowPlanningError as error:
        _raise(error)
    return _plan_response(plan, request, response)


@router.get("/plans/{plan_id}", response_model=WorkflowRunPlanResponse)
async def get_workflow_plan(
    plan_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_workflow_plan_read)],
) -> WorkflowRunPlanResponse:
    service: WorkflowPlanningService = request.app.state.workflow_planning_service
    try:
        plan = await service.get_plan(
            plan_id=plan_id, context=await _context(request, subject, decision)
        )
    except WorkflowPlanningError as error:
        _raise(error)
    return _plan_response(plan, request, response)
