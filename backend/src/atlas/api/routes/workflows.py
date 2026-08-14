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
    browser_session_subject,
    workflow_outbox_publisher_subject,
    workflow_worker_subject,
)
from atlas.api.workflow_schemas import (
    AcquireWorkflowOrchestrationLeaseInput,
    AcquireWorkflowOutboxPublicationLeaseInput,
    CancelWorkflowPlanInput,
    CreateWorkflowPlanInput,
    HeartbeatWorkflowOrchestrationLeaseInput,
    HeartbeatWorkflowOutboxPublicationLeaseInput,
    MaterializeWorkflowAttemptInput,
    MaterializeWorkflowRunInput,
    ReleaseWorkflowOrchestrationLeaseInput,
    ReleaseWorkflowOutboxPublicationLeaseInput,
    StageWorkflowDispatchIntentInput,
    WorkflowAttemptInventoryData,
    WorkflowAttemptInventoryResponse,
    WorkflowDefinitionData,
    WorkflowDefinitionInventoryData,
    WorkflowDefinitionInventoryResponse,
    WorkflowDispatchIntentData,
    WorkflowDispatchIntentInventoryData,
    WorkflowDispatchIntentInventoryResponse,
    WorkflowDispatchIntentResponse,
    WorkflowDispatchOutboxEntryData,
    WorkflowDispatchOutboxInventoryData,
    WorkflowDispatchOutboxInventoryResponse,
    WorkflowExecutionAttemptData,
    WorkflowExecutionAttemptResponse,
    WorkflowExecutionRunData,
    WorkflowExecutionRunResponse,
    WorkflowMaterializedRunStatusData,
    WorkflowMaterializedRunStatusResponse,
    WorkflowOrchestrationLeaseData,
    WorkflowOrchestrationLeaseResponse,
    WorkflowOrchestrationLeaseStatusData,
    WorkflowOrchestrationLeaseStatusResponse,
    WorkflowOutboxPublicationLeaseData,
    WorkflowOutboxPublicationLeaseInventoryData,
    WorkflowOutboxPublicationLeaseInventoryResponse,
    WorkflowOutboxPublicationLeaseResponse,
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
    WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE,
    WORKFLOW_WORKER_AUDIENCE,
    WorkflowAccessContext,
    WorkflowAttemptMaterializationError,
    WorkflowAttemptMaterializationRepository,
    WorkflowAttemptMaterializationService,
    WorkflowDispatchIntentStagingError,
    WorkflowDispatchIntentStagingRepository,
    WorkflowDispatchIntentStagingService,
    WorkflowOrchestrationLeaseError,
    WorkflowOrchestrationLeaseRepository,
    WorkflowOrchestrationLeaseService,
    WorkflowOutboxPublicationLeaseError,
    WorkflowOutboxPublicationLeaseRepository,
    WorkflowOutboxPublicationLeaseService,
    WorkflowOutboxPublisherContext,
    WorkflowPlanningError,
    WorkflowPlanningService,
    WorkflowRunMaterializationError,
    WorkflowRunMaterializationRepository,
    WorkflowRunMaterializationService,
    WorkflowWorkerContext,
)
from atlas.modules.workflows.domain import (
    WorkflowDispatchIntent,
    WorkflowDispatchIntentState,
    WorkflowDispatchOutboxEntry,
    WorkflowDispatchOutboxState,
    WorkflowExecutionAttempt,
    WorkflowExecutionAttemptState,
    WorkflowExecutionRun,
    WorkflowExecutionRunState,
    WorkflowExecutionStepRunState,
    WorkflowOrchestrationLease,
    WorkflowOrchestrationLeaseEffectiveState,
    WorkflowOutboxPublicationLease,
    WorkflowRunPlan,
    WorkflowScope,
)

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


def _raise_lease(error: WorkflowOrchestrationLeaseError) -> NoReturn:
    if error.code.endswith("_invalid"):
        status = 422
    elif "repository" in error.code:
        status = 503
    elif error.code.endswith("_not_found"):
        status = 404
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=(
            "workflow_lease_request_invalid"
            if status == 422
            else "workflow_lease_service_unavailable"
            if status == 503
            else "workflow_resource_unavailable"
            if status == 404
            else "workflow_lease_conflict"
        ),
        title=(
            "Workflow lease request invalid"
            if status == 422
            else "Workflow lease service unavailable"
            if status == 503
            else "Workflow resource unavailable"
            if status == 404
            else "Workflow lease conflict"
        ),
        detail=(
            "The workflow lease request did not satisfy the bounded contract."
            if status == 422
            else "The workflow lease operation is unavailable."
        ),
        retryable=status == 503,
    ) from error


def _raise_materialization(error: WorkflowRunMaterializationError) -> NoReturn:
    if error.code.endswith("_invalid") or error.code.endswith("_required"):
        status = 422
    elif "repository" in error.code:
        status = 503
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=(
            "workflow_run_request_invalid"
            if status == 422
            else "workflow_run_service_unavailable"
            if status == 503
            else "workflow_run_conflict"
        ),
        title=(
            "Workflow run request invalid"
            if status == 422
            else "Workflow run service unavailable"
            if status == 503
            else "Workflow run conflict"
        ),
        detail=(
            "The workflow run request did not satisfy the bounded contract."
            if status == 422
            else "The workflow run operation is unavailable."
        ),
        retryable=status == 503,
    ) from error


def _raise_attempt(error: WorkflowAttemptMaterializationError) -> NoReturn:
    if error.code.endswith("_invalid") or error.code.endswith("_required"):
        status = 422
    elif "repository" in error.code:
        status = 503
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=(
            "workflow_attempt_request_invalid"
            if status == 422
            else "workflow_attempt_service_unavailable"
            if status == 503
            else "workflow_attempt_conflict"
        ),
        title=(
            "Workflow attempt request invalid"
            if status == 422
            else "Workflow attempt service unavailable"
            if status == 503
            else "Workflow attempt conflict"
        ),
        detail=(
            "The workflow attempt request did not satisfy the bounded contract."
            if status == 422
            else "The workflow attempt operation is unavailable."
        ),
        retryable=status == 503,
    ) from error


def _raise_dispatch_intent(error: WorkflowDispatchIntentStagingError) -> NoReturn:
    if error.code.endswith("_invalid") or error.code.endswith("_required"):
        status = 422
    elif "repository" in error.code:
        status = 503
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=(
            "workflow_dispatch_intent_request_invalid"
            if status == 422
            else "workflow_dispatch_intent_service_unavailable"
            if status == 503
            else "workflow_dispatch_intent_conflict"
        ),
        title=(
            "Workflow dispatch intent request invalid"
            if status == 422
            else "Workflow dispatch intent service unavailable"
            if status == 503
            else "Workflow dispatch intent conflict"
        ),
        detail=(
            "The dispatch intent request did not satisfy the bounded contract."
            if status == 422
            else "Workflow dispatch intent evidence is unavailable."
        ),
        retryable=status == 503,
    ) from error


def _raise_publication_lease(error: WorkflowOutboxPublicationLeaseError) -> NoReturn:
    if error.code.endswith("_invalid") or error.code.endswith("_required"):
        status = 422
    elif "repository" in error.code:
        status = 503
    elif error.code.endswith("_not_found"):
        status = 404
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=(
            "workflow_outbox_publication_lease_request_invalid"
            if status == 422
            else "workflow_outbox_publication_lease_service_unavailable"
            if status == 503
            else "workflow_resource_unavailable"
            if status == 404
            else "workflow_outbox_publication_lease_conflict"
        ),
        title=(
            "Workflow outbox publication lease request invalid"
            if status == 422
            else "Workflow outbox publication lease service unavailable"
            if status == 503
            else "Workflow resource unavailable"
            if status == 404
            else "Workflow outbox publication lease conflict"
        ),
        detail=(
            "The publication lease request did not satisfy the bounded contract."
            if status == 422
            else "Workflow outbox publication lease evidence is unavailable."
        ),
        retryable=status == 503,
    ) from error


async def _worker_context(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    target_id: str,
) -> WorkflowWorkerContext:
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
            detail="Authorized workflow targets could not be resolved safely.",
            retryable=True,
        ) from error
    target_ids = tuple(target.target_id for target in targets)
    if (
        len(target_ids) > 100
        or len(target_ids) != len(set(target_ids))
        or target_id not in target_ids
    ):
        raise AtlasError(
            status=404,
            code="workflow_resource_unavailable",
            title="Workflow resource unavailable",
            detail="The requested workflow resource is unavailable.",
        )
    return WorkflowWorkerContext(
        subject_id=subject.subject_id,
        actor_type=subject.kind.value,
        authentication_method=subject.authentication_method.value,
        credential_audience=WORKFLOW_WORKER_AUDIENCE,
        scope=scope,
        authorized_target_ids=frozenset(target_ids),
        correlation_id=str(request.state.correlation_id),
        decision_id="decision.workflow-worker-authenticated",
        requested_at=datetime.now(UTC),
    )


async def _publisher_context(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    target_id: str,
) -> WorkflowOutboxPublisherContext:
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
            detail="Authorized workflow targets could not be resolved safely.",
            retryable=True,
        ) from error
    target_ids = tuple(target.target_id for target in targets)
    if (
        len(target_ids) > 100
        or len(target_ids) != len(set(target_ids))
        or target_id not in target_ids
    ):
        raise AtlasError(
            status=404,
            code="workflow_resource_unavailable",
            title="Workflow resource unavailable",
            detail="The requested workflow resource is unavailable.",
        )
    return WorkflowOutboxPublisherContext(
        subject_id=subject.subject_id,
        actor_type=subject.kind.value,
        authentication_method=subject.authentication_method.value,
        credential_audience=WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE,
        scope=scope,
        authorized_target_ids=frozenset(target_ids),
        correlation_id=str(request.state.correlation_id),
        decision_id="decision.workflow-outbox-publisher-authenticated",
        requested_at=datetime.now(UTC),
    )


def _lease_response(
    lease: WorkflowOrchestrationLease,
    request: Request,
    response: Response,
) -> WorkflowOrchestrationLeaseResponse:
    requested_at = datetime.now(UTC)
    _no_store(response)
    return WorkflowOrchestrationLeaseResponse(
        data=WorkflowOrchestrationLeaseData.from_domain(lease, requested_at=requested_at),
        meta=_meta(request),
    )


def _publication_lease_response(
    lease: WorkflowOutboxPublicationLease,
    request: Request,
    response: Response,
) -> WorkflowOutboxPublicationLeaseResponse:
    _no_store(response)
    return WorkflowOutboxPublicationLeaseResponse(
        data=WorkflowOutboxPublicationLeaseData.from_domain(
            lease,
            requested_at=datetime.now(UTC),
        ),
        meta=_meta(request),
    )


def _run_response(
    run: WorkflowExecutionRun,
    request: Request,
    response: Response,
) -> WorkflowExecutionRunResponse:
    _no_store(response)
    return WorkflowExecutionRunResponse(
        data=WorkflowExecutionRunData.from_domain(run),
        meta=_meta(request),
    )


def _attempt_response(
    attempt: WorkflowExecutionAttempt,
    request: Request,
    response: Response,
) -> WorkflowExecutionAttemptResponse:
    _no_store(response)
    return WorkflowExecutionAttemptResponse(
        data=WorkflowExecutionAttemptData.from_domain(attempt),
        meta=_meta(request),
    )


def _dispatch_intent_response(
    intent: WorkflowDispatchIntent,
    request: Request,
    response: Response,
) -> WorkflowDispatchIntentResponse:
    _no_store(response)
    return WorkflowDispatchIntentResponse(
        data=WorkflowDispatchIntentData.from_domain(intent), meta=_meta(request)
    )


def _run_matches_plan(run: WorkflowExecutionRun, plan: WorkflowRunPlan) -> bool:
    return (
        run.plan_id == plan.plan_id
        and run.plan_digest == plan.canonical_digest
        and run.definition_id == plan.definition_id
        and run.definition_version == plan.definition_version
        and run.definition_digest == plan.definition_digest
        and run.scope == plan.scope
        and run.target_id == plan.target_id
        and run.target_type == plan.target_type
        and run.state is WorkflowExecutionRunState.CREATED
        and len(run.step_runs) == len(plan.steps)
        and all(
            step_run.run_id == run.run_id
            and step_run.step_id == plan_step.step_id
            and step_run.ordinal == plan_step.ordinal
            and step_run.kind == plan_step.kind
            and step_run.capability_class == plan_step.capability_class
            and step_run.state is WorkflowExecutionStepRunState.NOT_STARTED
            for step_run, plan_step in zip(run.step_runs, plan.steps, strict=True)
        )
        and not any(run.authority.canonical_value().values())
        and not run.grants_execution_authority
    )


def _attempt_matches_run(attempt: WorkflowExecutionAttempt, run: WorkflowExecutionRun) -> bool:
    step = next((item for item in run.step_runs if item.step_run_id == attempt.step_run_id), None)
    return bool(
        step is not None
        and attempt.run_id == run.run_id
        and attempt.run_digest == run.canonical_digest
        and attempt.step_run_digest == step.canonical_digest
        and attempt.step_id == step.step_id
        and attempt.plan_id == run.plan_id
        and attempt.plan_digest == run.plan_digest
        and attempt.definition_id == run.definition_id
        and attempt.definition_version == run.definition_version
        and attempt.definition_digest == run.definition_digest
        and attempt.scope == run.scope
        and attempt.target_id == run.target_id
        and attempt.target_type == run.target_type
        and attempt.lease_id == run.lease_id
        and attempt.fencing_token == run.fencing_token
        and attempt.attempt_number == 1
        and attempt.state is WorkflowExecutionAttemptState.CREATED
        and not any(attempt.authority.canonical_value().values())
        and not attempt.grants_execution_authority
    )


def _dispatch_intent_matches_attempt(
    intent: WorkflowDispatchIntent,
    attempt: WorkflowExecutionAttempt,
) -> bool:
    return bool(
        intent.plan_id == attempt.plan_id
        and intent.plan_digest == attempt.plan_digest
        and intent.run_id == attempt.run_id
        and intent.run_digest == attempt.run_digest
        and intent.step_run_id == attempt.step_run_id
        and intent.step_run_digest == attempt.step_run_digest
        and intent.step_id == attempt.step_id
        and intent.attempt_id == attempt.attempt_id
        and intent.attempt_digest == attempt.canonical_digest
        and intent.attempt_number == attempt.attempt_number
        and intent.scope == attempt.scope
        and intent.target_id == attempt.target_id
        and intent.target_type == attempt.target_type
        and intent.lease_id == attempt.lease_id
        and intent.fencing_token == attempt.fencing_token
        and intent.state is WorkflowDispatchIntentState.STAGED
        and not any(intent.authority.canonical_value().values())
        and not intent.grants_publication_authority
        and not intent.grants_delivery_authority
        and not intent.grants_dispatch_authority
        and not intent.grants_execution_authority
    )


def _outbox_entry_matches_intent(
    entry: WorkflowDispatchOutboxEntry,
    intent: WorkflowDispatchIntent,
) -> bool:
    return bool(
        entry.dispatch_intent_id == intent.dispatch_intent_id
        and entry.dispatch_intent_digest == intent.canonical_digest
        and entry.plan_id == intent.plan_id
        and entry.plan_digest == intent.plan_digest
        and entry.run_id == intent.run_id
        and entry.run_digest == intent.run_digest
        and entry.step_run_id == intent.step_run_id
        and entry.step_run_digest == intent.step_run_digest
        and entry.step_id == intent.step_id
        and entry.attempt_id == intent.attempt_id
        and entry.attempt_digest == intent.attempt_digest
        and entry.attempt_number == intent.attempt_number
        and entry.scope == intent.scope
        and entry.target_id == intent.target_id
        and entry.target_type == intent.target_type
        and entry.lease_id == intent.lease_id
        and entry.lease_digest == intent.lease_digest
        and entry.fencing_token == intent.fencing_token
        and entry.worker_subject_id == intent.worker_subject_id
        and entry.admitted_at == intent.staged_at
        and entry.state is WorkflowDispatchOutboxState.PENDING_PUBLICATION
        and not any(entry.authority.canonical_value().values())
        and not entry.grants_publication_authority
        and not entry.grants_delivery_authority
        and not entry.grants_dispatch_authority
        and not entry.grants_execution_authority
    )


def _outbox_entry_matches_route(
    entry: WorkflowDispatchOutboxEntry,
    *,
    plan_id: str,
    run_id: str,
    attempt_id: str,
    dispatch_intent_id: str,
    outbox_entry_id: str,
) -> bool:
    return bool(
        entry.plan_id == plan_id
        and entry.run_id == run_id
        and entry.attempt_id == attempt_id
        and entry.dispatch_intent_id == dispatch_intent_id
        and entry.outbox_entry_id == outbox_entry_id
        and entry.state is WorkflowDispatchOutboxState.PENDING_PUBLICATION
        and not any(entry.authority.canonical_value().values())
        and not entry.grants_publication_authority
        and not entry.grants_delivery_authority
        and not entry.grants_dispatch_authority
        and not entry.grants_execution_authority
    )


def _publication_lease_matches_outbox(
    lease: WorkflowOutboxPublicationLease,
    entry: WorkflowDispatchOutboxEntry,
) -> bool:
    return bool(
        lease.outbox_entry_id == entry.outbox_entry_id
        and lease.outbox_entry_digest == entry.canonical_digest
        and lease.dispatch_intent_id == entry.dispatch_intent_id
        and lease.dispatch_intent_digest == entry.dispatch_intent_digest
        and lease.plan_id == entry.plan_id
        and lease.plan_digest == entry.plan_digest
        and lease.run_id == entry.run_id
        and lease.run_digest == entry.run_digest
        and lease.step_run_id == entry.step_run_id
        and lease.step_run_digest == entry.step_run_digest
        and lease.step_id == entry.step_id
        and lease.attempt_id == entry.attempt_id
        and lease.attempt_digest == entry.attempt_digest
        and lease.attempt_number == entry.attempt_number
        and lease.scope == entry.scope
        and lease.target_id == entry.target_id
        and lease.target_type == entry.target_type
        and lease.orchestration_lease_id == entry.lease_id
        and lease.orchestration_lease_digest == entry.lease_digest
        and lease.orchestration_fencing_token == entry.fencing_token
        and not any(lease.authority.canonical_value().values())
        and not lease.grants_publication_authority
        and not lease.grants_delivery_authority
        and not lease.grants_dispatch_authority
        and not lease.grants_execution_authority
    )


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


@router.get(
    "/plans/{plan_id}/orchestration-lease",
    response_model=WorkflowOrchestrationLeaseStatusResponse,
)
async def get_workflow_orchestration_lease_status(
    plan_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_workflow_plan_read)],
) -> WorkflowOrchestrationLeaseStatusResponse:
    planning_service: WorkflowPlanningService = request.app.state.workflow_planning_service
    try:
        plan = await planning_service.get_plan(
            plan_id=plan_id,
            context=await _context(request, subject, decision),
        )
    except WorkflowPlanningError as error:
        _raise(error)
    repository: WorkflowOrchestrationLeaseRepository = (
        request.app.state.workflow_orchestration_lease_repository
    )
    try:
        lease = await repository.get_lease_by_plan_id(plan_id=plan.plan_id)
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_lease_service_unavailable",
            title="Workflow lease service unavailable",
            detail="The workflow lease status is unavailable.",
            retryable=True,
        ) from error
    if lease is not None and (
        lease.plan_id != plan.plan_id
        or lease.plan_digest != plan.canonical_digest
        or lease.scope != plan.scope
        or lease.target_id != plan.target_id
        or lease.target_type != plan.target_type
        or lease.grants_execution_authority
    ):
        raise AtlasError(
            status=503,
            code="workflow_lease_service_unavailable",
            title="Workflow lease service unavailable",
            detail="The workflow lease status is unavailable.",
            retryable=True,
        )
    server_time = datetime.now(UTC)
    _no_store(response)
    return WorkflowOrchestrationLeaseStatusResponse(
        data=WorkflowOrchestrationLeaseStatusData(
            plan_id=plan.plan_id,
            lease=(
                None
                if lease is None
                else WorkflowOrchestrationLeaseData.from_domain(
                    lease,
                    requested_at=server_time,
                )
            ),
            server_time=server_time,
            durable=repository.durable,
        ),
        meta=_meta(request),
    )


@router.get(
    "/plans/{plan_id}/materialized-run",
    response_model=WorkflowMaterializedRunStatusResponse,
)
async def get_workflow_materialized_run_status(
    plan_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_workflow_plan_read)],
) -> WorkflowMaterializedRunStatusResponse:
    planning_service: WorkflowPlanningService = request.app.state.workflow_planning_service
    try:
        plan = await planning_service.get_plan(
            plan_id=plan_id,
            context=await _context(request, subject, decision),
        )
    except WorkflowPlanningError as error:
        _raise(error)
    repository: WorkflowRunMaterializationRepository = (
        request.app.state.workflow_run_materialization_repository
    )
    try:
        run = await repository.get_materialized_run_by_plan_id(plan_id=plan.plan_id)
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_run_service_unavailable",
            title="Workflow run service unavailable",
            detail="The workflow run status is unavailable.",
            retryable=True,
        ) from error
    if run is not None and not _run_matches_plan(run, plan):
        raise AtlasError(
            status=503,
            code="workflow_run_service_unavailable",
            title="Workflow run service unavailable",
            detail="The workflow run status is unavailable.",
            retryable=True,
        )
    _no_store(response)
    return WorkflowMaterializedRunStatusResponse(
        data=WorkflowMaterializedRunStatusData(
            plan_id=plan.plan_id,
            run=None if run is None else WorkflowExecutionRunData.from_domain(run),
            server_time=datetime.now(UTC),
            durable=repository.durable,
        ),
        meta=_meta(request),
    )


@router.post(
    "/plans/{plan_id}/materialized-run",
    response_model=WorkflowExecutionRunResponse,
    status_code=201,
)
async def materialize_workflow_run(
    plan_id: Annotated[str, SAFE_ID],
    payload: MaterializeWorkflowRunInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(workflow_worker_subject)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> WorkflowExecutionRunResponse:
    service: WorkflowRunMaterializationService = (
        request.app.state.workflow_run_materialization_service
    )
    try:
        run = await service.materialize(
            plan_id=plan_id,
            plan_digest=payload.plan_digest,
            lease_id=payload.lease_id,
            lease_digest=payload.lease_digest,
            fencing_token=payload.fencing_token,
            idempotency_key=idempotency_key,
            context=await _worker_context(request, subject, target_id=payload.target_id),
        )
    except WorkflowRunMaterializationError as error:
        _raise_materialization(error)
    return _run_response(run, request, response)


@router.get(
    "/plans/{plan_id}/runs/{run_id}/attempts",
    response_model=WorkflowAttemptInventoryResponse,
)
async def list_workflow_attempts(
    plan_id: Annotated[str, SAFE_ID],
    run_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_workflow_plan_read)],
) -> WorkflowAttemptInventoryResponse:
    planning_service: WorkflowPlanningService = request.app.state.workflow_planning_service
    try:
        plan = await planning_service.get_plan(
            plan_id=plan_id,
            context=await _context(request, subject, decision),
        )
    except WorkflowPlanningError as error:
        _raise(error)
    run_repository: WorkflowRunMaterializationRepository = (
        request.app.state.workflow_run_materialization_repository
    )
    attempt_repository: WorkflowAttemptMaterializationRepository = (
        request.app.state.workflow_attempt_materialization_repository
    )
    try:
        run = await run_repository.get_materialized_run_by_plan_id(plan_id=plan.plan_id)
        if run is None or run.run_id != run_id or not _run_matches_plan(run, plan):
            raise AtlasError(
                status=404,
                code="workflow_resource_unavailable",
                title="Workflow resource unavailable",
                detail="The requested workflow resource is unavailable.",
            )
        attempts = await attempt_repository.list_attempts_by_run_id(run_id=run.run_id)
    except AtlasError:
        raise
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_attempt_service_unavailable",
            title="Workflow attempt service unavailable",
            detail="Workflow attempt evidence is unavailable.",
            retryable=True,
        ) from error
    if any(not _attempt_matches_run(attempt, run) for attempt in attempts) or len(
        {attempt.step_run_id for attempt in attempts}
    ) != len(attempts):
        raise AtlasError(
            status=503,
            code="workflow_attempt_service_unavailable",
            title="Workflow attempt service unavailable",
            detail="Workflow attempt evidence is unavailable.",
            retryable=True,
        )
    step_order = {step.step_run_id: step.ordinal for step in run.step_runs}
    attempts = tuple(sorted(attempts, key=lambda item: step_order[item.step_run_id]))
    _no_store(response)
    return WorkflowAttemptInventoryResponse(
        data=WorkflowAttemptInventoryData(
            run_id=run.run_id,
            attempts=[WorkflowExecutionAttemptData.from_domain(item) for item in attempts],
            server_time=datetime.now(UTC),
            durable=attempt_repository.durable,
        ),
        meta=_meta(request),
    )


@router.post(
    "/plans/{plan_id}/runs/{run_id}/steps/{step_run_id}/attempts",
    response_model=WorkflowExecutionAttemptResponse,
    status_code=201,
)
async def materialize_workflow_attempt(
    plan_id: Annotated[str, SAFE_ID],
    run_id: Annotated[str, SAFE_ID],
    step_run_id: Annotated[str, SAFE_ID],
    payload: MaterializeWorkflowAttemptInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(workflow_worker_subject)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> WorkflowExecutionAttemptResponse:
    service: WorkflowAttemptMaterializationService = (
        request.app.state.workflow_attempt_materialization_service
    )
    try:
        attempt = await service.materialize(
            plan_id=plan_id,
            plan_digest=payload.plan_digest,
            run_id=run_id,
            run_digest=payload.run_digest,
            step_run_id=step_run_id,
            step_run_digest=payload.step_run_digest,
            lease_id=payload.lease_id,
            lease_digest=payload.lease_digest,
            fencing_token=payload.fencing_token,
            idempotency_key=idempotency_key,
            context=await _worker_context(request, subject, target_id=payload.target_id),
        )
    except WorkflowAttemptMaterializationError as error:
        _raise_attempt(error)
    return _attempt_response(attempt, request, response)


@router.get(
    "/plans/{plan_id}/runs/{run_id}/attempts/{attempt_id}/dispatch-intents",
    response_model=WorkflowDispatchIntentInventoryResponse,
)
async def list_workflow_dispatch_intents(
    plan_id: Annotated[str, SAFE_ID],
    run_id: Annotated[str, SAFE_ID],
    attempt_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_workflow_plan_read)],
) -> WorkflowDispatchIntentInventoryResponse:
    planning_service: WorkflowPlanningService = request.app.state.workflow_planning_service
    try:
        plan = await planning_service.get_plan(
            plan_id=plan_id,
            context=await _context(request, subject, decision),
        )
    except WorkflowPlanningError as error:
        _raise(error)
    run_repository: WorkflowRunMaterializationRepository = (
        request.app.state.workflow_run_materialization_repository
    )
    attempt_repository: WorkflowAttemptMaterializationRepository = (
        request.app.state.workflow_attempt_materialization_repository
    )
    intent_repository: WorkflowDispatchIntentStagingRepository = (
        request.app.state.workflow_dispatch_intent_staging_repository
    )
    try:
        run = await run_repository.get_materialized_run_by_plan_id(plan_id=plan.plan_id)
        if run is None or run.run_id != run_id or not _run_matches_plan(run, plan):
            raise AtlasError(
                status=404,
                code="workflow_resource_unavailable",
                title="Workflow resource unavailable",
                detail="The requested workflow resource is unavailable.",
            )
        attempts = await attempt_repository.list_attempts_by_run_id(run_id=run.run_id)
        if any(not _attempt_matches_run(item, run) for item in attempts):
            raise RuntimeError("unsafe workflow attempt evidence")
        attempt = next((item for item in attempts if item.attempt_id == attempt_id), None)
        if attempt is None:
            raise AtlasError(
                status=404,
                code="workflow_resource_unavailable",
                title="Workflow resource unavailable",
                detail="The requested workflow resource is unavailable.",
            )
        all_intents = await intent_repository.list_dispatch_intents_by_run_id(run_id=run.run_id)
    except AtlasError:
        raise
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_dispatch_intent_service_unavailable",
            title="Workflow dispatch intent service unavailable",
            detail="Workflow dispatch intent evidence is unavailable.",
            retryable=True,
        ) from error
    attempt_by_id = {item.attempt_id: item for item in attempts}
    if (
        len({item.dispatch_intent_id for item in all_intents}) != len(all_intents)
        or len({item.attempt_id for item in all_intents}) != len(all_intents)
        or any(
            item.attempt_id not in attempt_by_id
            or not _dispatch_intent_matches_attempt(item, attempt_by_id[item.attempt_id])
            for item in all_intents
        )
    ):
        raise AtlasError(
            status=503,
            code="workflow_dispatch_intent_service_unavailable",
            title="Workflow dispatch intent service unavailable",
            detail="Workflow dispatch intent evidence is unavailable.",
            retryable=True,
        )
    intents = [item for item in all_intents if item.attempt_id == attempt.attempt_id]
    _no_store(response)
    return WorkflowDispatchIntentInventoryResponse(
        data=WorkflowDispatchIntentInventoryData(
            attempt_id=attempt.attempt_id,
            dispatch_intents=[WorkflowDispatchIntentData.from_domain(item) for item in intents],
            server_time=datetime.now(UTC),
            durable=intent_repository.durable,
        ),
        meta=_meta(request),
    )


@router.get(
    (
        "/plans/{plan_id}/runs/{run_id}/attempts/{attempt_id}/dispatch-intents/"
        "{dispatch_intent_id}/outbox"
    ),
    response_model=WorkflowDispatchOutboxInventoryResponse,
)
async def list_workflow_dispatch_outbox_entries(
    plan_id: Annotated[str, SAFE_ID],
    run_id: Annotated[str, SAFE_ID],
    attempt_id: Annotated[str, SAFE_ID],
    dispatch_intent_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_workflow_plan_read)],
) -> WorkflowDispatchOutboxInventoryResponse:
    planning_service: WorkflowPlanningService = request.app.state.workflow_planning_service
    try:
        plan = await planning_service.get_plan(
            plan_id=plan_id,
            context=await _context(request, subject, decision),
        )
    except WorkflowPlanningError as error:
        _raise(error)
    run_repository: WorkflowRunMaterializationRepository = (
        request.app.state.workflow_run_materialization_repository
    )
    attempt_repository: WorkflowAttemptMaterializationRepository = (
        request.app.state.workflow_attempt_materialization_repository
    )
    repository: WorkflowDispatchIntentStagingRepository = (
        request.app.state.workflow_dispatch_intent_staging_repository
    )
    try:
        run = await run_repository.get_materialized_run_by_plan_id(plan_id=plan.plan_id)
        if run is None or run.run_id != run_id or not _run_matches_plan(run, plan):
            raise AtlasError(
                status=404,
                code="workflow_resource_unavailable",
                title="Workflow resource unavailable",
                detail="The requested workflow resource is unavailable.",
            )
        attempts = await attempt_repository.list_attempts_by_run_id(run_id=run.run_id)
        if any(not _attempt_matches_run(item, run) for item in attempts):
            raise RuntimeError("unsafe workflow attempt evidence")
        attempt_by_id = {item.attempt_id: item for item in attempts}
        attempt = next((item for item in attempts if item.attempt_id == attempt_id), None)
        if attempt is None:
            raise AtlasError(
                status=404,
                code="workflow_resource_unavailable",
                title="Workflow resource unavailable",
                detail="The requested workflow resource is unavailable.",
            )
        intents = await repository.list_dispatch_intents_by_run_id(run_id=run.run_id)
        if (
            len({item.dispatch_intent_id for item in intents}) != len(intents)
            or len({item.attempt_id for item in intents}) != len(intents)
            or any(
                item.attempt_id not in attempt_by_id
                or not _dispatch_intent_matches_attempt(item, attempt_by_id[item.attempt_id])
                for item in intents
            )
        ):
            raise RuntimeError("unsafe workflow dispatch intent evidence")
        intent = next(
            (
                item
                for item in intents
                if item.dispatch_intent_id == dispatch_intent_id
                and item.attempt_id == attempt.attempt_id
            ),
            None,
        )
        if intent is None or not _dispatch_intent_matches_attempt(intent, attempt):
            raise AtlasError(
                status=404,
                code="workflow_resource_unavailable",
                title="Workflow resource unavailable",
                detail="The requested workflow resource is unavailable.",
            )
        all_entries = await repository.list_dispatch_outbox_entries_by_run_id(run_id=run.run_id)
    except AtlasError:
        raise
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_dispatch_outbox_service_unavailable",
            title="Workflow dispatch outbox service unavailable",
            detail="Workflow dispatch outbox evidence is unavailable.",
            retryable=True,
        ) from error
    intent_by_id = {item.dispatch_intent_id: item for item in intents}
    if (
        len(all_entries) != len(intents)
        or len({item.outbox_entry_id for item in all_entries}) != len(all_entries)
        or len({item.dispatch_intent_id for item in all_entries}) != len(all_entries)
        or any(
            item.dispatch_intent_id not in intent_by_id
            or not _outbox_entry_matches_intent(item, intent_by_id[item.dispatch_intent_id])
            for item in all_entries
        )
    ):
        raise AtlasError(
            status=503,
            code="workflow_dispatch_outbox_service_unavailable",
            title="Workflow dispatch outbox service unavailable",
            detail="Workflow dispatch outbox evidence is unavailable.",
            retryable=True,
        )
    entries = [item for item in all_entries if item.dispatch_intent_id == intent.dispatch_intent_id]
    if len(entries) != 1:
        raise AtlasError(
            status=503,
            code="workflow_dispatch_outbox_service_unavailable",
            title="Workflow dispatch outbox service unavailable",
            detail="Workflow dispatch outbox evidence is unavailable.",
            retryable=True,
        )
    _no_store(response)
    return WorkflowDispatchOutboxInventoryResponse(
        data=WorkflowDispatchOutboxInventoryData(
            dispatch_intent_id=intent.dispatch_intent_id,
            outbox_entries=[WorkflowDispatchOutboxEntryData.from_domain(item) for item in entries],
            server_time=datetime.now(UTC),
            durable=repository.durable,
        ),
        meta=_meta(request),
    )


@router.get(
    (
        "/plans/{plan_id}/runs/{run_id}/attempts/{attempt_id}/dispatch-intents/"
        "{dispatch_intent_id}/outbox/{outbox_entry_id}/publication-lease"
    ),
    response_model=WorkflowOutboxPublicationLeaseInventoryResponse,
)
async def get_workflow_outbox_publication_lease(
    plan_id: Annotated[str, SAFE_ID],
    run_id: Annotated[str, SAFE_ID],
    attempt_id: Annotated[str, SAFE_ID],
    dispatch_intent_id: Annotated[str, SAFE_ID],
    outbox_entry_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_workflow_plan_read)],
) -> WorkflowOutboxPublicationLeaseInventoryResponse:
    planning_service: WorkflowPlanningService = request.app.state.workflow_planning_service
    try:
        plan = await planning_service.get_plan(
            plan_id=plan_id,
            context=await _context(request, subject, decision),
        )
    except WorkflowPlanningError as error:
        _raise(error)
    repository: WorkflowOutboxPublicationLeaseRepository = (
        request.app.state.workflow_outbox_publication_lease_repository
    )
    try:
        entry = await repository.get_outbox_entry_by_id(outbox_entry_id=outbox_entry_id)
        lease = await repository.get_publication_lease_by_outbox_entry_id(
            outbox_entry_id=outbox_entry_id
        )
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_outbox_publication_lease_service_unavailable",
            title="Workflow outbox publication lease service unavailable",
            detail="Workflow outbox publication lease evidence is unavailable.",
            retryable=True,
        ) from error
    if (
        entry is None
        or not _outbox_entry_matches_route(
            entry,
            plan_id=plan_id,
            run_id=run_id,
            attempt_id=attempt_id,
            dispatch_intent_id=dispatch_intent_id,
            outbox_entry_id=outbox_entry_id,
        )
        or entry.plan_digest != plan.canonical_digest
        or entry.scope != plan.scope
        or entry.target_id != plan.target_id
        or entry.target_type != plan.target_type
    ):
        raise AtlasError(
            status=404,
            code="workflow_resource_unavailable",
            title="Workflow resource unavailable",
            detail="The requested workflow resource is unavailable.",
        )
    if lease is not None and not _publication_lease_matches_outbox(lease, entry):
        raise AtlasError(
            status=503,
            code="workflow_outbox_publication_lease_service_unavailable",
            title="Workflow outbox publication lease service unavailable",
            detail="Workflow outbox publication lease evidence is unavailable.",
            retryable=True,
        )
    server_time = datetime.now(UTC)
    if lease is not None and lease.effective_state(requested_at=server_time).value == "active":
        orchestration_repository: WorkflowOrchestrationLeaseRepository = (
            request.app.state.workflow_orchestration_lease_repository
        )
        try:
            orchestration_lease = await orchestration_repository.get_lease_by_plan_id(
                plan_id=plan.plan_id
            )
        except Exception as error:
            raise AtlasError(
                status=503,
                code="workflow_outbox_publication_lease_service_unavailable",
                title="Workflow outbox publication lease service unavailable",
                detail="Workflow outbox publication lease evidence is unavailable.",
                retryable=True,
            ) from error
        if (
            orchestration_lease is None
            or orchestration_lease.lease_id != lease.orchestration_lease_id
            or orchestration_lease.canonical_digest != lease.orchestration_lease_digest
            or orchestration_lease.fencing_token != lease.orchestration_fencing_token
            or orchestration_lease.effective_state(requested_at=server_time)
            is not WorkflowOrchestrationLeaseEffectiveState.ACTIVE
        ):
            raise AtlasError(
                status=503,
                code="workflow_outbox_publication_lease_service_unavailable",
                title="Workflow outbox publication lease service unavailable",
                detail="Workflow outbox publication lease evidence is unavailable.",
                retryable=True,
            )
    _no_store(response)
    return WorkflowOutboxPublicationLeaseInventoryResponse(
        data=WorkflowOutboxPublicationLeaseInventoryData(
            outbox_entry_id=entry.outbox_entry_id,
            publication_leases=(
                []
                if lease is None
                else [
                    WorkflowOutboxPublicationLeaseData.from_domain(
                        lease,
                        requested_at=server_time,
                    )
                ]
            ),
            server_time=server_time,
            durable=repository.durable,
        ),
        meta=_meta(request),
    )


async def _require_bound_publication_outbox(
    *,
    repository: WorkflowOutboxPublicationLeaseRepository,
    plan_id: str,
    run_id: str,
    attempt_id: str,
    dispatch_intent_id: str,
    outbox_entry_id: str,
) -> WorkflowDispatchOutboxEntry:
    try:
        entry = await repository.get_outbox_entry_by_id(outbox_entry_id=outbox_entry_id)
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_outbox_publication_lease_service_unavailable",
            title="Workflow outbox publication lease service unavailable",
            detail="Workflow outbox publication lease evidence is unavailable.",
            retryable=True,
        ) from error
    if entry is None or not _outbox_entry_matches_route(
        entry,
        plan_id=plan_id,
        run_id=run_id,
        attempt_id=attempt_id,
        dispatch_intent_id=dispatch_intent_id,
        outbox_entry_id=outbox_entry_id,
    ):
        raise AtlasError(
            status=404,
            code="workflow_resource_unavailable",
            title="Workflow resource unavailable",
            detail="The requested workflow resource is unavailable.",
        )
    return entry


@router.post(
    (
        "/plans/{plan_id}/runs/{run_id}/attempts/{attempt_id}/dispatch-intents/"
        "{dispatch_intent_id}/outbox/{outbox_entry_id}/publication-lease/acquisition"
    ),
    response_model=WorkflowOutboxPublicationLeaseResponse,
    status_code=201,
)
async def acquire_workflow_outbox_publication_lease(
    plan_id: Annotated[str, SAFE_ID],
    run_id: Annotated[str, SAFE_ID],
    attempt_id: Annotated[str, SAFE_ID],
    dispatch_intent_id: Annotated[str, SAFE_ID],
    outbox_entry_id: Annotated[str, SAFE_ID],
    payload: AcquireWorkflowOutboxPublicationLeaseInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(workflow_outbox_publisher_subject)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> WorkflowOutboxPublicationLeaseResponse:
    service: WorkflowOutboxPublicationLeaseService = (
        request.app.state.workflow_outbox_publication_lease_service
    )
    await _require_bound_publication_outbox(
        repository=service.repository,
        plan_id=plan_id,
        run_id=run_id,
        attempt_id=attempt_id,
        dispatch_intent_id=dispatch_intent_id,
        outbox_entry_id=outbox_entry_id,
    )
    try:
        lease = await service.acquire(
            outbox_entry_id=outbox_entry_id,
            outbox_entry_digest=payload.outbox_entry_digest,
            lease_seconds=payload.lease_duration_seconds,
            idempotency_key=idempotency_key,
            context=await _publisher_context(request, subject, target_id=payload.target_id),
        )
    except WorkflowOutboxPublicationLeaseError as error:
        _raise_publication_lease(error)
    return _publication_lease_response(lease, request, response)


@router.post(
    (
        "/plans/{plan_id}/runs/{run_id}/attempts/{attempt_id}/dispatch-intents/"
        "{dispatch_intent_id}/outbox/{outbox_entry_id}/publication-lease/"
        "{publication_lease_id}/heartbeat"
    ),
    response_model=WorkflowOutboxPublicationLeaseResponse,
)
async def heartbeat_workflow_outbox_publication_lease(
    plan_id: Annotated[str, SAFE_ID],
    run_id: Annotated[str, SAFE_ID],
    attempt_id: Annotated[str, SAFE_ID],
    dispatch_intent_id: Annotated[str, SAFE_ID],
    outbox_entry_id: Annotated[str, SAFE_ID],
    publication_lease_id: Annotated[str, SAFE_ID],
    payload: HeartbeatWorkflowOutboxPublicationLeaseInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(workflow_outbox_publisher_subject)],
) -> WorkflowOutboxPublicationLeaseResponse:
    service: WorkflowOutboxPublicationLeaseService = (
        request.app.state.workflow_outbox_publication_lease_service
    )
    await _require_bound_publication_outbox(
        repository=service.repository,
        plan_id=plan_id,
        run_id=run_id,
        attempt_id=attempt_id,
        dispatch_intent_id=dispatch_intent_id,
        outbox_entry_id=outbox_entry_id,
    )
    try:
        lease = await service.heartbeat(
            outbox_entry_id=outbox_entry_id,
            outbox_entry_digest=payload.outbox_entry_digest,
            publication_lease_id=publication_lease_id,
            publication_lease_digest=payload.publication_lease_digest,
            publication_fencing_token=payload.publication_fencing_token,
            lease_seconds=payload.lease_duration_seconds,
            context=await _publisher_context(request, subject, target_id=payload.target_id),
        )
    except WorkflowOutboxPublicationLeaseError as error:
        _raise_publication_lease(error)
    return _publication_lease_response(lease, request, response)


@router.post(
    (
        "/plans/{plan_id}/runs/{run_id}/attempts/{attempt_id}/dispatch-intents/"
        "{dispatch_intent_id}/outbox/{outbox_entry_id}/publication-lease/"
        "{publication_lease_id}/release"
    ),
    response_model=WorkflowOutboxPublicationLeaseResponse,
)
async def release_workflow_outbox_publication_lease(
    plan_id: Annotated[str, SAFE_ID],
    run_id: Annotated[str, SAFE_ID],
    attempt_id: Annotated[str, SAFE_ID],
    dispatch_intent_id: Annotated[str, SAFE_ID],
    outbox_entry_id: Annotated[str, SAFE_ID],
    publication_lease_id: Annotated[str, SAFE_ID],
    payload: ReleaseWorkflowOutboxPublicationLeaseInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(workflow_outbox_publisher_subject)],
) -> WorkflowOutboxPublicationLeaseResponse:
    service: WorkflowOutboxPublicationLeaseService = (
        request.app.state.workflow_outbox_publication_lease_service
    )
    await _require_bound_publication_outbox(
        repository=service.repository,
        plan_id=plan_id,
        run_id=run_id,
        attempt_id=attempt_id,
        dispatch_intent_id=dispatch_intent_id,
        outbox_entry_id=outbox_entry_id,
    )
    try:
        lease = await service.release(
            outbox_entry_id=outbox_entry_id,
            outbox_entry_digest=payload.outbox_entry_digest,
            publication_lease_id=publication_lease_id,
            publication_lease_digest=payload.publication_lease_digest,
            publication_fencing_token=payload.publication_fencing_token,
            context=await _publisher_context(request, subject, target_id=payload.target_id),
        )
    except WorkflowOutboxPublicationLeaseError as error:
        _raise_publication_lease(error)
    return _publication_lease_response(lease, request, response)


@router.post(
    "/plans/{plan_id}/runs/{run_id}/attempts/{attempt_id}/dispatch-intents",
    response_model=WorkflowDispatchIntentResponse,
    status_code=201,
)
async def stage_workflow_dispatch_intent(
    plan_id: Annotated[str, SAFE_ID],
    run_id: Annotated[str, SAFE_ID],
    attempt_id: Annotated[str, SAFE_ID],
    payload: StageWorkflowDispatchIntentInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(workflow_worker_subject)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> WorkflowDispatchIntentResponse:
    service: WorkflowDispatchIntentStagingService = (
        request.app.state.workflow_dispatch_intent_staging_service
    )
    try:
        intent = await service.stage(
            plan_id=plan_id,
            plan_digest=payload.plan_digest,
            run_id=run_id,
            run_digest=payload.run_digest,
            step_run_id=payload.step_run_id,
            step_run_digest=payload.step_run_digest,
            attempt_id=attempt_id,
            attempt_digest=payload.attempt_digest,
            lease_id=payload.lease_id,
            lease_digest=payload.lease_digest,
            fencing_token=payload.fencing_token,
            idempotency_key=idempotency_key,
            context=await _worker_context(request, subject, target_id=payload.target_id),
        )
    except WorkflowDispatchIntentStagingError as error:
        _raise_dispatch_intent(error)
    return _dispatch_intent_response(intent, request, response)


@router.post(
    "/plans/{plan_id}/orchestration-lease/acquisition",
    response_model=WorkflowOrchestrationLeaseResponse,
    status_code=201,
)
async def acquire_workflow_orchestration_lease(
    plan_id: Annotated[str, SAFE_ID],
    payload: AcquireWorkflowOrchestrationLeaseInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(workflow_worker_subject)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> WorkflowOrchestrationLeaseResponse:
    service: WorkflowOrchestrationLeaseService = (
        request.app.state.workflow_orchestration_lease_service
    )
    try:
        lease = await service.acquire(
            plan_id=plan_id,
            plan_digest=payload.plan_digest,
            lease_seconds=payload.lease_duration_seconds,
            idempotency_key=idempotency_key,
            context=await _worker_context(request, subject, target_id=payload.target_id),
        )
    except WorkflowOrchestrationLeaseError as error:
        _raise_lease(error)
    return _lease_response(lease, request, response)


@router.post(
    "/plans/{plan_id}/orchestration-lease/{lease_id}/heartbeat",
    response_model=WorkflowOrchestrationLeaseResponse,
)
async def heartbeat_workflow_orchestration_lease(
    plan_id: Annotated[str, SAFE_ID],
    lease_id: Annotated[str, SAFE_ID],
    payload: HeartbeatWorkflowOrchestrationLeaseInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(workflow_worker_subject)],
) -> WorkflowOrchestrationLeaseResponse:
    service: WorkflowOrchestrationLeaseService = (
        request.app.state.workflow_orchestration_lease_service
    )
    try:
        lease = await service.heartbeat(
            plan_id=plan_id,
            plan_digest=payload.plan_digest,
            lease_id=lease_id,
            lease_digest=payload.lease_digest,
            fencing_token=payload.fencing_token,
            lease_seconds=payload.lease_duration_seconds,
            context=await _worker_context(request, subject, target_id=payload.target_id),
        )
    except WorkflowOrchestrationLeaseError as error:
        _raise_lease(error)
    return _lease_response(lease, request, response)


@router.post(
    "/plans/{plan_id}/orchestration-lease/{lease_id}/release",
    response_model=WorkflowOrchestrationLeaseResponse,
)
async def release_workflow_orchestration_lease(
    plan_id: Annotated[str, SAFE_ID],
    lease_id: Annotated[str, SAFE_ID],
    payload: ReleaseWorkflowOrchestrationLeaseInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(workflow_worker_subject)],
) -> WorkflowOrchestrationLeaseResponse:
    service: WorkflowOrchestrationLeaseService = (
        request.app.state.workflow_orchestration_lease_service
    )
    try:
        lease = await service.release(
            plan_id=plan_id,
            plan_digest=payload.plan_digest,
            lease_id=lease_id,
            lease_digest=payload.lease_digest,
            fencing_token=payload.fencing_token,
            context=await _worker_context(request, subject, target_id=payload.target_id),
        )
    except WorkflowOrchestrationLeaseError as error:
        _raise_lease(error)
    return _lease_response(lease, request, response)


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
