"""Pass 36: docs/050_API.md SS15/SS19/SS20's operation resource framework -- HTTP-level wiring.

Proves: (a) the new additive `POST /api/v1/knowledge/documents/index-operations` route returns a
real `202` with a real, pollable operation resource that genuinely transitions
`queued -> running -> succeeded` (or `failed` for a real error, an unknown `preparation_id`) as the
real FastEmbed-backed `DocumentKnowledgeRetrievalService.index_document()` call actually runs via
FastAPI's `BackgroundTasks`; (b) `GET /api/v1/operations/{operation_id}` and
`POST /api/v1/operations/{operation_id}/cancellations` both enforce real RBAC and real
owner-or-elevated-cross-subject-access logic; (c) cancellation is genuinely idempotent and genuinely
rejected once an operation reaches a terminal state; (d) the established two-stage denial pattern
(true 401, true 403) for both new operation routes and the new async indexing route; (e) the
existing synchronous `POST /api/v1/knowledge/documents/index` route is untouched -- its own test
suite (`test_knowledge_document_lifecycle_wiring_api.py`) is run standalone, unmodified, to confirm
zero regression.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.capabilities import CapabilityClass
from atlas.core.classification import DataClassification
from atlas.core.config import Settings
from atlas.core.protected_content import InMemoryProtectedContentStore
from atlas.modules.authorization.application.bootstrap import (
    KNOWLEDGE_DOCUMENT_INDEXING_CREATE,
    OPERATION_RESOURCE_CANCEL,
    OPERATION_RESOURCE_CROSS_SUBJECT_ACCESS,
    OPERATION_RESOURCE_READ,
    document_knowledge_scope,
    operation_resource_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import (
    PermissionDefinition,
    RoleAssignment,
    RoleDefinition,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.knowledge.adapters.document_chunking import ParagraphBoundedChunker
from atlas.modules.knowledge.adapters.document_embedding_fastembed import FastEmbedDocumentEmbedder
from atlas.modules.knowledge.adapters.document_knowledge_memory import (
    InMemoryDocumentKnowledgeRepository,
)
from atlas.modules.knowledge.adapters.document_vector_index_memory import (
    InMemoryDocumentVectorIndex,
)
from atlas.modules.knowledge.application.document_knowledge import DocumentKnowledgeService
from atlas.modules.knowledge.application.document_retrieval import (
    DocumentKnowledgeRetrievalService,
)
from atlas.modules.knowledge.domain.document_knowledge import (
    REVIEW_DECISION_PASSED,
    DocumentKnowledgePublicationPreparation,
)
from atlas.modules.operations.adapters.memory import InMemoryOperationResourceRepository
from atlas.modules.operations.adapters.permission import (
    AuthorizationOperationResourcePermissionAuthorizer,
)
from atlas.modules.operations.application.service import OperationResourceService
from atlas.modules.operations.domain.models import OperationResource

_ORGANIZATION_ID = Settings().development_organization_id
_ENVIRONMENT_ID = "environment.test"
_NOW = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "development_identity_enabled": True,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/authentication/sessions",
        json={"username": "atlas-demo", "password": "local-demo"},
    )
    assert response.status_code == 201, response.text
    return str(response.headers["X-CSRF-Token"])


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[object] = []

    async def record(self, event: object) -> None:
        self.records.append(event)


class _AllowAllDocumentKnowledgeAuthorizer:
    async def authorize(self, **_kwargs: object) -> None:
        return None

    async def classification_ceiling(self, **_kwargs: object) -> DataClassification:
        return DataClassification.RESTRICTED


def _subject(subject_id: str) -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id=subject_id,
        display_name=subject_id,
        kind=SubjectKind.HUMAN,
        provider_id="provider.development",
        organization_id=_ORGANIZATION_ID,
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.SINGLE_FACTOR,
        authenticated_at=_NOW,
        role_ids=(),
    )


async def _approved_preparation(
    knowledge_service: DocumentKnowledgeService, *, content: bytes, correlation_prefix: str
) -> DocumentKnowledgePublicationPreparation:
    # Real separation-of-duties: curator, reviewer, and approver must all be distinct subjects
    # (see `DocumentKnowledgeService.submit_review_decision`/`record_final_approval`).
    curator = _subject(f"subject.operations-wiring-test.{correlation_prefix}-curator")
    reviewer = _subject(f"subject.operations-wiring-test.{correlation_prefix}-reviewer")
    approver = _subject(f"subject.operations-wiring-test.{correlation_prefix}-approver")
    draft = await knowledge_service.curate_draft(
        actor=curator,
        organization_id=_ORGANIZATION_ID,
        environment_id=_ENVIRONMENT_ID,
        content=content,
        title="Storage Controller Runbook",
        draft_domain="domain.vendor",
        content_type="text/markdown",
        classification="classification.internal",
        access_policy_id="access-policy.default",
        retention_policy_id="retention-policy.default",
        purpose="Validate the async operation-resource indexing route end to end.",
        correlation_id=f"cor_{correlation_prefix}_1",
    )
    review = await knowledge_service.submit_review_decision(
        actor=reviewer,
        organization_id=_ORGANIZATION_ID,
        environment_id=_ENVIRONMENT_ID,
        draft_id=draft.draft_id,
        decision=REVIEW_DECISION_PASSED,
        findings=("No issues found.",),
        correlation_id=f"cor_{correlation_prefix}_2",
    )
    approval = await knowledge_service.record_final_approval(
        actor=approver,
        organization_id=_ORGANIZATION_ID,
        environment_id=_ENVIRONMENT_ID,
        review_id=review.review_id,
        decision="approved",
        rationale="Independent final approval after a passed domain review.",
        correlation_id=f"cor_{correlation_prefix}_3",
    )
    return await knowledge_service.prepare_publication(
        actor=approver,
        organization_id=_ORGANIZATION_ID,
        environment_id=_ENVIRONMENT_ID,
        approval_id=approval.approval_id,
        chunking_profile_digest="a" * 64,
        correlation_id=f"cor_{correlation_prefix}_4",
    )


def _build_retrieval_service() -> DocumentKnowledgeRetrievalService:
    return DocumentKnowledgeRetrievalService(
        repository=InMemoryDocumentKnowledgeRepository(),
        protected_content=InMemoryProtectedContentStore(),
        chunker=ParagraphBoundedChunker(maximum_chunk_characters=200),
        embedder=FastEmbedDocumentEmbedder(),
        vector_index=InMemoryDocumentVectorIndex(),
        permission_authorizer=_AllowAllDocumentKnowledgeAuthorizer(),
        audit_sink=CollectingAuditSink(),
    )


def _poll_until_terminal(
    client: TestClient, operation_id: str, *, attempts: int = 40
) -> dict[str, Any]:
    last: dict[str, Any] = {}
    for _ in range(attempts):
        response = client.get(f"/api/v1/operations/{operation_id}")
        assert response.status_code == 200, response.text
        data: dict[str, Any] = response.json()["data"]
        last = data
        if data["state"] in ("succeeded", "failed", "cancelled", "timed_out"):
            return data
        time.sleep(0.05)
    raise AssertionError(f"operation {operation_id} did not reach a terminal state: {last}")


# ---------------------------------------------------------------------------
# (a) The async indexing route: real 202, real background transition.
# ---------------------------------------------------------------------------


def test_index_document_knowledge_as_operation_returns_202_and_completes_via_background_task() -> (
    None
):
    repository = InMemoryDocumentKnowledgeRepository()
    protected_content = InMemoryProtectedContentStore()
    knowledge_service = DocumentKnowledgeService(
        repository=repository,
        protected_content=protected_content,
        permission_authorizer=_AllowAllDocumentKnowledgeAuthorizer(),
        audit_sink=CollectingAuditSink(),
        subject_salt="operations-wiring-test-salt",
    )
    retrieval_service = DocumentKnowledgeRetrievalService(
        repository=repository,
        protected_content=protected_content,
        chunker=ParagraphBoundedChunker(maximum_chunk_characters=200),
        embedder=FastEmbedDocumentEmbedder(),
        vector_index=InMemoryDocumentVectorIndex(),
        permission_authorizer=_AllowAllDocumentKnowledgeAuthorizer(),
        audit_sink=CollectingAuditSink(),
    )
    preparation = asyncio.run(
        _approved_preparation(
            knowledge_service,
            content=(
                b"# Storage Controller Runbook\n\n"
                b"When a storage controller reports a warning status, engineers should first "
                b"confirm the condition persists across two consecutive read-only health checks "
                b"before taking any action."
            ),
            correlation_prefix="success",
        )
    )

    with TestClient(
        create_app(
            _settings(development_subject_id="subject.operations-wiring-test.indexer-success"),
            document_knowledge_retrieval_service=retrieval_service,
        )
    ) as client:
        csrf = _login(client)
        response = client.post(
            "/api/v1/knowledge/documents/index-operations",
            json={"preparation_id": preparation.preparation_id},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 202, response.text
        assert response.headers["Cache-Control"] == "no-store"
        created = response.json()["data"]
        assert created["operation_type"] == "operation.knowledge-document-indexing"
        assert created["input_artifact_reference"] == preparation.preparation_id
        assert created["cancellation_eligible"] is True
        operation_id = created["operation_id"]

        final = _poll_until_terminal(client, operation_id)

    assert final["state"] == "succeeded"
    assert final["result_reference"].startswith("chunks.")
    assert final["started_at"] is not None
    assert final["cancellation_eligible"] is False
    assert final["error_reference"] is None


def test_index_document_knowledge_as_operation_transitions_to_failed_for_unknown_preparation() -> (
    None
):
    retrieval_service = _build_retrieval_service()

    with TestClient(
        create_app(
            _settings(development_subject_id="subject.operations-wiring-test.indexer-failure"),
            document_knowledge_retrieval_service=retrieval_service,
        )
    ) as client:
        csrf = _login(client)
        response = client.post(
            "/api/v1/knowledge/documents/index-operations",
            json={"preparation_id": "document-knowledge-preparation.does-not-exist"},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 202, response.text
        operation_id = response.json()["data"]["operation_id"]

        final = _poll_until_terminal(client, operation_id)

    assert final["state"] == "failed"
    assert final["error_reference"] == "error.document_knowledge_preparation_not_found"
    assert final["result_reference"] is None
    assert final["cancellation_eligible"] is False


def test_existing_synchronous_index_route_still_returns_201_unmodified() -> None:
    """A narrow regression check that the additive `/index-operations` route did not disturb the
    existing synchronous `/index` route's own behavior; the full suite for that route
    (`test_knowledge_document_lifecycle_wiring_api.py`) is run separately, unmodified."""
    repository = InMemoryDocumentKnowledgeRepository()
    protected_content = InMemoryProtectedContentStore()
    knowledge_service = DocumentKnowledgeService(
        repository=repository,
        protected_content=protected_content,
        permission_authorizer=_AllowAllDocumentKnowledgeAuthorizer(),
        audit_sink=CollectingAuditSink(),
        subject_salt="operations-wiring-test-sync-salt",
    )
    retrieval_service = DocumentKnowledgeRetrievalService(
        repository=repository,
        protected_content=protected_content,
        chunker=ParagraphBoundedChunker(maximum_chunk_characters=200),
        embedder=FastEmbedDocumentEmbedder(),
        vector_index=InMemoryDocumentVectorIndex(),
        permission_authorizer=_AllowAllDocumentKnowledgeAuthorizer(),
        audit_sink=CollectingAuditSink(),
    )
    preparation = asyncio.run(
        _approved_preparation(
            knowledge_service,
            content=b"# Backup Policy\n\nBackups run nightly at 02:00 local time.",
            correlation_prefix="sync",
        )
    )

    with TestClient(
        create_app(
            _settings(development_subject_id="subject.operations-wiring-test.indexer-sync"),
            document_knowledge_retrieval_service=retrieval_service,
        )
    ) as client:
        csrf = _login(client)
        response = client.post(
            "/api/v1/knowledge/documents/index",
            json={"preparation_id": preparation.preparation_id},
            headers={"X-CSRF-Token": csrf},
        )
    assert response.status_code == 201, response.text
    assert response.json()["data"]["chunk_count"] >= 1


# ---------------------------------------------------------------------------
# (d) Two-stage denial pattern for all three routes.
# ---------------------------------------------------------------------------


def test_get_operation_resource_requires_authentication() -> None:
    app = create_app(_settings(development_identity_enabled=False))
    with TestClient(app) as client:
        response = client.get("/api/v1/operations/operation.example-0001")
    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_get_operation_resource_requires_permission() -> None:
    app = create_app(_settings(development_role_ids=()))
    with TestClient(app) as client:
        _login(client)
        response = client.get("/api/v1/operations/operation.example-0001")
    assert response.status_code == 403
    assert response.json()["code"] == "authorization_denied"


def test_cancel_operation_resource_requires_authentication() -> None:
    app = create_app(_settings(development_identity_enabled=False))
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/operations/operation.example-0001/cancellations",
            json={"reason": "Example reason."},
        )
    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_cancel_operation_resource_requires_permission() -> None:
    app = create_app(_settings(development_role_ids=()))
    with TestClient(app) as client:
        csrf = _login(client)
        response = client.post(
            "/api/v1/operations/operation.example-0001/cancellations",
            json={"reason": "Example reason."},
            headers={"X-CSRF-Token": csrf},
        )
    assert response.status_code == 403
    assert response.json()["code"] == "authorization_denied"


def test_index_document_knowledge_as_operation_requires_authentication() -> None:
    app = create_app(_settings(development_identity_enabled=False))
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/knowledge/documents/index-operations",
            json={"preparation_id": "document-knowledge-preparation.example"},
        )
    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_index_document_knowledge_as_operation_requires_permission() -> None:
    app = create_app(_settings(development_role_ids=()))
    with TestClient(app) as client:
        csrf = _login(client)
        response = client.post(
            "/api/v1/knowledge/documents/index-operations",
            json={"preparation_id": "document-knowledge-preparation.example"},
            headers={"X-CSRF-Token": csrf},
        )
    assert response.status_code == 403
    assert response.json()["code"] == "authorization_denied"


# ---------------------------------------------------------------------------
# (b)/(c) Owner-or-elevated-cross-subject-access, and cancellation idempotency/terminal rejection.
# ---------------------------------------------------------------------------


def _build_operations_authorization_service(
    *, owner_subject_id: str, stranger_subject_id: str, elevated_subject_id: str
) -> AuthorizationService:
    """A real, bespoke `AuthorizationService` covering only the permissions these tests need,
    mirroring `test_knowledge_document_lifecycle_wiring_api.py`'s
    `_build_classification_retrieval_authorization_service` precedent: `owner_subject_id` and
    `stranger_subject_id` hold only the base operation-resource permissions (no cross-subject
    access); `elevated_subject_id` additionally holds `OPERATION_RESOURCE_CROSS_SUBJECT_ACCESS`.
    """
    base_role_id = "role.operations-wiring-test.base"
    elevated_role_id = "role.operations-wiring-test.elevated"
    indexing_scope = document_knowledge_scope(
        _ORGANIZATION_ID, "test", CapabilityClass.C2_DIAGNOSTIC
    )
    read_scope = operation_resource_scope(_ORGANIZATION_ID, "test", CapabilityClass.C1_READ_ONLY)
    cancel_scope = operation_resource_scope(_ORGANIZATION_ID, "test", CapabilityClass.C2_DIAGNOSTIC)
    return AuthorizationService(
        permissions=tuple(
            PermissionDefinition(permission_id=permission, description=permission)
            for permission in (
                KNOWLEDGE_DOCUMENT_INDEXING_CREATE,
                OPERATION_RESOURCE_READ,
                OPERATION_RESOURCE_CANCEL,
                OPERATION_RESOURCE_CROSS_SUBJECT_ACCESS,
            )
        ),
        roles=(
            RoleDefinition(
                role_id=base_role_id,
                version=1,
                permissions=frozenset(
                    {
                        KNOWLEDGE_DOCUMENT_INDEXING_CREATE,
                        OPERATION_RESOURCE_READ,
                        OPERATION_RESOURCE_CANCEL,
                    }
                ),
            ),
            RoleDefinition(
                role_id=elevated_role_id,
                version=1,
                permissions=frozenset(
                    {
                        OPERATION_RESOURCE_READ,
                        OPERATION_RESOURCE_CANCEL,
                        OPERATION_RESOURCE_CROSS_SUBJECT_ACCESS,
                    }
                ),
            ),
        ),
        assignments=tuple(
            RoleAssignment(
                assignment_id=f"assignment.operations-wiring-test.{index}",
                version=1,
                subject_id=subject_id,
                role_id=role_id,
                scope=scope,
                valid_from=datetime.min.replace(tzinfo=UTC),
            )
            for index, (subject_id, role_id, scope) in enumerate(
                (
                    (owner_subject_id, base_role_id, indexing_scope),
                    (owner_subject_id, base_role_id, read_scope),
                    (owner_subject_id, base_role_id, cancel_scope),
                    (stranger_subject_id, base_role_id, read_scope),
                    (stranger_subject_id, base_role_id, cancel_scope),
                    (elevated_subject_id, elevated_role_id, read_scope),
                    (elevated_subject_id, elevated_role_id, cancel_scope),
                )
            )
        ),
        audit_sink=CollectingAuditSink(),
    )


def _seed_operation(
    operation_service: OperationResourceService, *, owner_subject_id: str, correlation_id: str
) -> OperationResource:
    async def _create() -> OperationResource:
        return await operation_service.create(
            actor=_subject(owner_subject_id),
            organization_id=_ORGANIZATION_ID,
            environment_id=_ENVIRONMENT_ID,
            operation_type="operation.knowledge-document-indexing",
            input_artifact_reference="document-knowledge-preparation.wiring-test",
            correlation_id=correlation_id,
        )

    return asyncio.run(_create())


def _client_for(
    subject_id: str,
    role_id: str,
    *,
    authorization_service: AuthorizationService,
    operation_service: OperationResourceService,
) -> TestClient:
    return TestClient(
        create_app(
            _settings(
                development_subject_id=subject_id,
                development_role_ids=(role_id,),
            ),
            authorization_service=authorization_service,
            operation_resource_service=operation_service,
        )
    )


def test_get_operation_resource_enforces_ownership_and_cross_subject_access() -> None:
    owner_subject = "subject.operations-wiring-test.get-owner"
    stranger_subject = "subject.operations-wiring-test.get-stranger"
    elevated_subject = "subject.operations-wiring-test.get-elevated"
    auth_service = _build_operations_authorization_service(
        owner_subject_id=owner_subject,
        stranger_subject_id=stranger_subject,
        elevated_subject_id=elevated_subject,
    )
    operation_service = OperationResourceService(
        repository=InMemoryOperationResourceRepository(),
        permission_authorizer=AuthorizationOperationResourcePermissionAuthorizer(
            service=auth_service, environment="test"
        ),
        audit_sink=CollectingAuditSink(),
    )
    resource = _seed_operation(
        operation_service, owner_subject_id=owner_subject, correlation_id="cor_get_seed"
    )

    with _client_for(
        owner_subject,
        "role.operations-wiring-test.base",
        authorization_service=auth_service,
        operation_service=operation_service,
    ) as owner_client:
        _login(owner_client)
        response = owner_client.get(f"/api/v1/operations/{resource.operation_id}")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["operation_id"] == resource.operation_id

    with _client_for(
        stranger_subject,
        "role.operations-wiring-test.base",
        authorization_service=auth_service,
        operation_service=operation_service,
    ) as stranger_client:
        _login(stranger_client)
        response = stranger_client.get(f"/api/v1/operations/{resource.operation_id}")
    assert response.status_code == 404
    assert response.json()["code"] == "operation_resource_not_found"

    with _client_for(
        elevated_subject,
        "role.operations-wiring-test.elevated",
        authorization_service=auth_service,
        operation_service=operation_service,
    ) as elevated_client:
        _login(elevated_client)
        response = elevated_client.get(f"/api/v1/operations/{resource.operation_id}")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["operation_id"] == resource.operation_id


def test_cancel_operation_resource_enforces_ownership_and_cross_subject_access() -> None:
    owner_subject = "subject.operations-wiring-test.cancel-owner"
    stranger_subject = "subject.operations-wiring-test.cancel-stranger"
    elevated_subject = "subject.operations-wiring-test.cancel-elevated"
    auth_service = _build_operations_authorization_service(
        owner_subject_id=owner_subject,
        stranger_subject_id=stranger_subject,
        elevated_subject_id=elevated_subject,
    )
    operation_service = OperationResourceService(
        repository=InMemoryOperationResourceRepository(),
        permission_authorizer=AuthorizationOperationResourcePermissionAuthorizer(
            service=auth_service, environment="test"
        ),
        audit_sink=CollectingAuditSink(),
    )
    stranger_target = _seed_operation(
        operation_service, owner_subject_id=owner_subject, correlation_id="cor_cancel_seed_1"
    )
    elevated_target = _seed_operation(
        operation_service, owner_subject_id=owner_subject, correlation_id="cor_cancel_seed_2"
    )
    owner_target = _seed_operation(
        operation_service, owner_subject_id=owner_subject, correlation_id="cor_cancel_seed_3"
    )

    with _client_for(
        stranger_subject,
        "role.operations-wiring-test.base",
        authorization_service=auth_service,
        operation_service=operation_service,
    ) as stranger_client:
        response = stranger_client.post(
            f"/api/v1/operations/{stranger_target.operation_id}/cancellations",
            json={"reason": "Not mine to cancel."},
            headers={"X-CSRF-Token": _login(stranger_client)},
        )
    assert response.status_code == 404
    assert response.json()["code"] == "operation_resource_not_found"

    with _client_for(
        elevated_subject,
        "role.operations-wiring-test.elevated",
        authorization_service=auth_service,
        operation_service=operation_service,
    ) as elevated_client:
        response = elevated_client.post(
            f"/api/v1/operations/{elevated_target.operation_id}/cancellations",
            json={"reason": "Elevated cleanup."},
            headers={"X-CSRF-Token": _login(elevated_client)},
        )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["state"] == "cancelled"

    with _client_for(
        owner_subject,
        "role.operations-wiring-test.base",
        authorization_service=auth_service,
        operation_service=operation_service,
    ) as owner_client:
        csrf = _login(owner_client)
        first = owner_client.post(
            f"/api/v1/operations/{owner_target.operation_id}/cancellations",
            json={"reason": "Duplicate submission."},
            headers={"X-CSRF-Token": csrf},
        )
        assert first.status_code == 200, first.text
        assert first.json()["data"]["state"] == "cancelled"

        # (c) idempotent: cancelling an already-cancelled operation succeeds, reason unchanged.
        second = owner_client.post(
            f"/api/v1/operations/{owner_target.operation_id}/cancellations",
            json={"reason": "A different reason should not matter."},
            headers={"X-CSRF-Token": csrf},
        )
        assert second.status_code == 200, second.text
        assert second.json()["data"]["state"] == "cancelled"
        assert (
            second.json()["data"]["cancellation_reason"]
            == first.json()["data"]["cancellation_reason"]
        )


def test_cancel_operation_resource_rejects_an_already_terminal_operation() -> None:
    owner_subject = "subject.operations-wiring-test.cancel-terminal-owner"
    auth_service = _build_operations_authorization_service(
        owner_subject_id=owner_subject,
        stranger_subject_id="subject.operations-wiring-test.cancel-terminal-stranger",
        elevated_subject_id="subject.operations-wiring-test.cancel-terminal-elevated",
    )
    operation_service = OperationResourceService(
        repository=InMemoryOperationResourceRepository(),
        permission_authorizer=AuthorizationOperationResourcePermissionAuthorizer(
            service=auth_service, environment="test"
        ),
        audit_sink=CollectingAuditSink(),
    )
    resource = _seed_operation(
        operation_service, owner_subject_id=owner_subject, correlation_id="cor_terminal_seed"
    )

    async def _succeed() -> None:
        await operation_service.mark_succeeded(
            actor=_subject(owner_subject),
            organization_id=_ORGANIZATION_ID,
            environment_id=_ENVIRONMENT_ID,
            operation_id=resource.operation_id,
            result_reference="chunks.1",
            correlation_id="cor_terminal_succeed",
        )

    asyncio.run(_succeed())

    with _client_for(
        owner_subject,
        "role.operations-wiring-test.base",
        authorization_service=auth_service,
        operation_service=operation_service,
    ) as owner_client:
        csrf = _login(owner_client)
        response = owner_client.post(
            f"/api/v1/operations/{resource.operation_id}/cancellations",
            json={"reason": "Too late."},
            headers={"X-CSRF-Token": csrf},
        )
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "operation_resource_already_terminal"
