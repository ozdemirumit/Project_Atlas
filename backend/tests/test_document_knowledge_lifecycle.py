"""Pass 37: docs/027_Knowledge_Engine.md SS8 (lifecycle transitions) and SS21 (Conflict and
Supersession) closed for the real document-sourced knowledge pipeline -- see
atlas.modules.knowledge.domain.document_knowledge_lifecycle for why this targets
document_knowledge.py/document_retrieval.py and not the older, still-synthetic Operational-chain
``KnowledgeLifecycle`` enum.

Covers: domain-model construction invariants; service-level state-machine enforcement (suspend
only from ACTIVE, resume only from SUSPENDED, supersede only from ACTIVE and only to a real ACTIVE
replacement, retire only from SUPERSEDED -- each wrong-state attempt a real error, never a silent
no-op); conflict recording/resolution with the paired-optional-field invariant; and the
load-bearing proof that a suspended or superseded item's chunks genuinely stop appearing in
DocumentKnowledgeRetrievalService.retrieve()'s real results.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.classification import DataClassification
from atlas.core.protected_content import InMemoryProtectedContentStore
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.knowledge.adapters.document_chunking import ParagraphBoundedChunker
from atlas.modules.knowledge.adapters.document_embedding_fastembed import FastEmbedDocumentEmbedder
from atlas.modules.knowledge.adapters.document_knowledge_lifecycle_memory import (
    InMemoryDocumentKnowledgeLifecycleRepository,
)
from atlas.modules.knowledge.adapters.document_knowledge_memory import (
    InMemoryDocumentKnowledgeRepository,
)
from atlas.modules.knowledge.adapters.document_vector_index_memory import (
    InMemoryDocumentVectorIndex,
)
from atlas.modules.knowledge.application.document_knowledge import DocumentKnowledgeService
from atlas.modules.knowledge.application.document_knowledge_lifecycle import (
    DocumentKnowledgeLifecycleService,
)
from atlas.modules.knowledge.application.document_knowledge_lifecycle_ports import (
    DocumentKnowledgeError,
)
from atlas.modules.knowledge.application.document_retrieval import (
    DocumentKnowledgeRetrievalService,
)
from atlas.modules.knowledge.domain.document_knowledge import (
    REVIEW_DECISION_PASSED,
    DocumentKnowledgePublicationPreparation,
)
from atlas.modules.knowledge.domain.document_knowledge_lifecycle import (
    DocumentKnowledgeConflict,
    DocumentKnowledgeConflictType,
    DocumentKnowledgeItemLifecycleRecord,
    DocumentKnowledgeItemLifecycleState,
    canonical_conflict_pair,
)

ORG = "organization.development"
ENV = "environment.test"
NOW = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)

STORAGE_DOC = """# Storage Controller Runbook

When a storage controller reports a warning status, engineers should first confirm
the condition persists across two consecutive read-only health checks before taking
any action.

# Escalation Procedure

If the warning persists, open a change record and notify the on-call storage
engineer. Do not restart the controller without an approved change window.
"""


class AllowAllAuthorizer:
    async def authorize(self, **_kwargs: object) -> None:
        return None

    async def classification_ceiling(self, **_kwargs: object) -> DataClassification:
        return DataClassification.RESTRICTED


class _NullAuditSink:
    def __init__(self) -> None:
        self.records: list[object] = []

    async def record(self, event: object) -> None:
        self.records.append(event)


def _subject(subject_id: str) -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id=subject_id,
        display_name=subject_id,
        kind=SubjectKind.HUMAN,
        provider_id="provider.development",
        organization_id=ORG,
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.SINGLE_FACTOR,
        authenticated_at=NOW,
        role_ids=(),
    )


def _lifecycle_service() -> DocumentKnowledgeLifecycleService:
    return DocumentKnowledgeLifecycleService(
        repository=InMemoryDocumentKnowledgeLifecycleRepository(),
        permission_authorizer=AllowAllAuthorizer(),
        audit_sink=_NullAuditSink(),
        clock=lambda: NOW,
    )


# ---------------------------------------------------------------------------
# Domain: DocumentKnowledgeItemLifecycleRecord invariants.
# ---------------------------------------------------------------------------


def _lifecycle_record(**overrides: object) -> DocumentKnowledgeItemLifecycleRecord:
    values: dict[str, object] = {
        "knowledge_item_id": "knowledge-item.abc123",
        "organization_id": ORG,
        "environment_id": ENV,
        "state": DocumentKnowledgeItemLifecycleState.ACTIVE,
        "reason": "Confirmed accurate after quarterly review.",
        "updated_by": "subject.reviewer",
        "updated_at": NOW,
        "created_at": NOW,
        "superseded_by_item_id": None,
    }
    values.update(overrides)
    return DocumentKnowledgeItemLifecycleRecord(**values)  # type: ignore[arg-type]


def test_lifecycle_record_rejects_blank_reason() -> None:
    with pytest.raises(ValueError, match="reason"):
        _lifecycle_record(reason="   ")


def test_lifecycle_record_rejects_oversized_reason() -> None:
    with pytest.raises(ValueError, match="reason"):
        _lifecycle_record(reason="x" * 2001)


def test_lifecycle_record_superseded_requires_target() -> None:
    with pytest.raises(ValueError, match="SUPERSEDED"):
        _lifecycle_record(state=DocumentKnowledgeItemLifecycleState.SUPERSEDED)


def test_lifecycle_record_non_superseded_rejects_target() -> None:
    with pytest.raises(ValueError, match="SUPERSEDED"):
        _lifecycle_record(
            state=DocumentKnowledgeItemLifecycleState.ACTIVE,
            superseded_by_item_id="knowledge-item.other",
        )


def test_lifecycle_record_rejects_self_supersession() -> None:
    with pytest.raises(ValueError, match="itself"):
        _lifecycle_record(
            state=DocumentKnowledgeItemLifecycleState.SUPERSEDED,
            superseded_by_item_id="knowledge-item.abc123",
        )


def test_lifecycle_record_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _lifecycle_record(updated_at=datetime(2026, 9, 11, 12, 0))


def test_lifecycle_record_rejects_updated_before_created() -> None:
    with pytest.raises(ValueError, match="before it was created"):
        _lifecycle_record(created_at=NOW, updated_at=datetime(2020, 1, 1, tzinfo=UTC))


# ---------------------------------------------------------------------------
# Domain: DocumentKnowledgeConflict invariants + canonical pair ordering.
# ---------------------------------------------------------------------------


def _conflict(**overrides: object) -> DocumentKnowledgeConflict:
    values: dict[str, object] = {
        "conflict_id": "document-knowledge-conflict.abc123",
        "organization_id": ORG,
        "environment_id": ENV,
        "knowledge_item_id_a": "knowledge-item.aaa",
        "knowledge_item_id_b": "knowledge-item.bbb",
        "conflict_type": DocumentKnowledgeConflictType.CONTRADICTORY_GUIDANCE,
        "detected_by": "subject.detector",
        "detected_at": NOW,
        "resolution": None,
        "resolved_by": None,
        "resolved_at": None,
    }
    values.update(overrides)
    return DocumentKnowledgeConflict(**values)  # type: ignore[arg-type]


def test_canonical_conflict_pair_orders_lexicographically() -> None:
    assert canonical_conflict_pair("knowledge-item.bbb", "knowledge-item.aaa") == (
        "knowledge-item.aaa",
        "knowledge-item.bbb",
    )
    assert canonical_conflict_pair("knowledge-item.aaa", "knowledge-item.bbb") == (
        "knowledge-item.aaa",
        "knowledge-item.bbb",
    )


def test_conflict_requires_distinct_items() -> None:
    with pytest.raises(ValueError, match="distinct"):
        _conflict(
            knowledge_item_id_a="knowledge-item.same", knowledge_item_id_b="knowledge-item.same"
        )


def test_conflict_requires_canonical_order() -> None:
    with pytest.raises(ValueError, match="canonical"):
        _conflict(
            knowledge_item_id_a="knowledge-item.bbb", knowledge_item_id_b="knowledge-item.aaa"
        )


def test_conflict_resolution_fields_must_travel_together() -> None:
    with pytest.raises(ValueError, match="all-or-nothing"):
        _conflict(resolution="Superseded the older item.")
    with pytest.raises(ValueError, match="all-or-nothing"):
        _conflict(resolved_by="subject.resolver")
    with pytest.raises(ValueError, match="all-or-nothing"):
        _conflict(resolved_at=NOW)


def test_conflict_resolution_all_set_together_succeeds() -> None:
    conflict = _conflict(
        resolution="Superseded the older item.", resolved_by="subject.resolver", resolved_at=NOW
    )
    assert conflict.is_resolved is True


def test_conflict_unresolved_is_not_resolved() -> None:
    assert _conflict().is_resolved is False


def test_conflict_rejects_resolution_before_detection() -> None:
    with pytest.raises(ValueError, match="before it was detected"):
        _conflict(
            detected_at=NOW,
            resolution="Too early.",
            resolved_by="subject.resolver",
            resolved_at=datetime(2020, 1, 1, tzinfo=UTC),
        )


def test_conflict_rejects_blank_resolution_text() -> None:
    with pytest.raises(ValueError, match="blank"):
        _conflict(resolution="   ", resolved_by="subject.resolver", resolved_at=NOW)


# ---------------------------------------------------------------------------
# Service: state-machine enforcement.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_suspend_only_from_active() -> None:
    service = _lifecycle_service()
    item = "knowledge-item.suspend-test"
    record = await service.suspend(
        actor=_subject("subject.admin"),
        organization_id=ORG,
        environment_id=ENV,
        knowledge_item_id=item,
        reason="Content under dispute pending investigation.",
        correlation_id="cor_1",
    )
    assert record.state is DocumentKnowledgeItemLifecycleState.SUSPENDED

    with pytest.raises(DocumentKnowledgeError) as excinfo:
        await service.suspend(
            actor=_subject("subject.admin"),
            organization_id=ORG,
            environment_id=ENV,
            knowledge_item_id=item,
            reason="Attempting to suspend an already-suspended item.",
            correlation_id="cor_2",
        )
    assert excinfo.value.code == "document_knowledge_lifecycle_transition_not_allowed"


@pytest.mark.asyncio
async def test_resume_only_from_suspended() -> None:
    service = _lifecycle_service()
    item = "knowledge-item.resume-test"

    with pytest.raises(DocumentKnowledgeError) as excinfo:
        await service.resume(
            actor=_subject("subject.admin"),
            organization_id=ORG,
            environment_id=ENV,
            knowledge_item_id=item,
            reason="Nothing to resume yet.",
            correlation_id="cor_1",
        )
    assert excinfo.value.code == "document_knowledge_lifecycle_transition_not_allowed"

    await service.suspend(
        actor=_subject("subject.admin"),
        organization_id=ORG,
        environment_id=ENV,
        knowledge_item_id=item,
        reason="Content under dispute.",
        correlation_id="cor_2",
    )
    resumed = await service.resume(
        actor=_subject("subject.admin"),
        organization_id=ORG,
        environment_id=ENV,
        knowledge_item_id=item,
        reason="Dispute resolved in favor of the content.",
        correlation_id="cor_3",
    )
    assert resumed.state is DocumentKnowledgeItemLifecycleState.ACTIVE


@pytest.mark.asyncio
async def test_full_round_trip_active_suspended_active() -> None:
    """SS8's "Published -> Suspended -> Published": ACTIVE and SUSPENDED are mutually
    reachable, proven by actually round-tripping through both real service calls."""
    service = _lifecycle_service()
    item = "knowledge-item.round-trip"

    view_before = await service.get_lifecycle(
        actor=_subject("subject.admin"),
        organization_id=ORG,
        environment_id=ENV,
        knowledge_item_id=item,
        correlation_id="cor_0",
    )
    assert view_before.state is DocumentKnowledgeItemLifecycleState.ACTIVE
    assert view_before.reason is None

    await service.suspend(
        actor=_subject("subject.admin"),
        organization_id=ORG,
        environment_id=ENV,
        knowledge_item_id=item,
        reason="Under review.",
        correlation_id="cor_1",
    )
    await service.resume(
        actor=_subject("subject.admin"),
        organization_id=ORG,
        environment_id=ENV,
        knowledge_item_id=item,
        reason="Review concluded; content stands.",
        correlation_id="cor_2",
    )
    view_after = await service.get_lifecycle(
        actor=_subject("subject.admin"),
        organization_id=ORG,
        environment_id=ENV,
        knowledge_item_id=item,
        correlation_id="cor_3",
    )
    assert view_after.state is DocumentKnowledgeItemLifecycleState.ACTIVE
    assert view_after.reason == "Review concluded; content stands."


@pytest.mark.asyncio
async def test_supersede_only_from_active() -> None:
    service = _lifecycle_service()
    item = "knowledge-item.supersede-source"
    replacement = "knowledge-item.supersede-target"

    record = await service.supersede(
        actor=_subject("subject.admin"),
        organization_id=ORG,
        environment_id=ENV,
        knowledge_item_id=item,
        superseded_by_item_id=replacement,
        reason="Replaced by an updated runbook.",
        correlation_id="cor_1",
    )
    assert record.state is DocumentKnowledgeItemLifecycleState.SUPERSEDED
    assert record.superseded_by_item_id == replacement

    with pytest.raises(DocumentKnowledgeError) as excinfo:
        await service.supersede(
            actor=_subject("subject.admin"),
            organization_id=ORG,
            environment_id=ENV,
            knowledge_item_id=item,
            superseded_by_item_id=replacement,
            reason="Attempting to supersede an already-superseded item.",
            correlation_id="cor_2",
        )
    assert excinfo.value.code == "document_knowledge_lifecycle_transition_not_allowed"


@pytest.mark.asyncio
async def test_supersede_rejects_self_target() -> None:
    service = _lifecycle_service()
    with pytest.raises(DocumentKnowledgeError) as excinfo:
        await service.supersede(
            actor=_subject("subject.admin"),
            organization_id=ORG,
            environment_id=ENV,
            knowledge_item_id="knowledge-item.self",
            superseded_by_item_id="knowledge-item.self",
            reason="Cannot supersede by itself.",
            correlation_id="cor_1",
        )
    assert excinfo.value.code == "document_knowledge_lifecycle_supersession_target_invalid"


@pytest.mark.asyncio
async def test_supersede_rejects_a_non_active_replacement() -> None:
    """The real, proportionate substitute for full cross-repository existence verification --
    see the module docstring in document_knowledge_lifecycle.py. The replacement's own
    lifecycle state must resolve to ACTIVE."""
    service = _lifecycle_service()
    replacement = "knowledge-item.already-suspended"
    await service.suspend(
        actor=_subject("subject.admin"),
        organization_id=ORG,
        environment_id=ENV,
        knowledge_item_id=replacement,
        reason="Suspended for unrelated reasons.",
        correlation_id="cor_1",
    )

    with pytest.raises(DocumentKnowledgeError) as excinfo:
        await service.supersede(
            actor=_subject("subject.admin"),
            organization_id=ORG,
            environment_id=ENV,
            knowledge_item_id="knowledge-item.source",
            superseded_by_item_id=replacement,
            reason="Attempting to supersede by a suspended item.",
            correlation_id="cor_2",
        )
    assert excinfo.value.code == "document_knowledge_lifecycle_supersession_target_invalid"


@pytest.mark.asyncio
async def test_retire_only_from_superseded_and_is_terminal() -> None:
    """SS8's "Published -> Superseded -> Retired": one-directional, and RETIRED is terminal --
    proven by attempting every other transition out of RETIRED and confirming each is rejected."""
    service = _lifecycle_service()
    item = "knowledge-item.retire-test"
    replacement = "knowledge-item.retire-replacement"

    with pytest.raises(DocumentKnowledgeError) as excinfo:
        await service.retire(
            actor=_subject("subject.admin"),
            organization_id=ORG,
            environment_id=ENV,
            knowledge_item_id=item,
            reason="Nothing to retire yet.",
            correlation_id="cor_1",
        )
    assert excinfo.value.code == "document_knowledge_lifecycle_transition_not_allowed"

    await service.supersede(
        actor=_subject("subject.admin"),
        organization_id=ORG,
        environment_id=ENV,
        knowledge_item_id=item,
        superseded_by_item_id=replacement,
        reason="Replaced by an updated runbook.",
        correlation_id="cor_2",
    )
    retired = await service.retire(
        actor=_subject("subject.admin"),
        organization_id=ORG,
        environment_id=ENV,
        knowledge_item_id=item,
        reason="Retention period elapsed.",
        correlation_id="cor_3",
    )
    assert retired.state is DocumentKnowledgeItemLifecycleState.RETIRED

    with pytest.raises(DocumentKnowledgeError) as retire_again_excinfo:
        await service.retire(
            actor=_subject("subject.admin"),
            organization_id=ORG,
            environment_id=ENV,
            knowledge_item_id=item,
            reason="Already retired.",
            correlation_id="cor_4",
        )
    assert retire_again_excinfo.value.code == "document_knowledge_lifecycle_transition_not_allowed"

    with pytest.raises(DocumentKnowledgeError) as resume_excinfo:
        await service.resume(
            actor=_subject("subject.admin"),
            organization_id=ORG,
            environment_id=ENV,
            knowledge_item_id=item,
            reason="Cannot resume a retired item.",
            correlation_id="cor_5",
        )
    assert resume_excinfo.value.code == "document_knowledge_lifecycle_transition_not_allowed"

    with pytest.raises(DocumentKnowledgeError) as suspend_excinfo:
        await service.suspend(
            actor=_subject("subject.admin"),
            organization_id=ORG,
            environment_id=ENV,
            knowledge_item_id=item,
            reason="Cannot suspend a retired item.",
            correlation_id="cor_6",
        )
    assert suspend_excinfo.value.code == "document_knowledge_lifecycle_transition_not_allowed"


@pytest.mark.asyncio
async def test_transition_rejects_blank_reason() -> None:
    service = _lifecycle_service()
    with pytest.raises(DocumentKnowledgeError) as excinfo:
        await service.suspend(
            actor=_subject("subject.admin"),
            organization_id=ORG,
            environment_id=ENV,
            knowledge_item_id="knowledge-item.blank-reason",
            reason="   ",
            correlation_id="cor_1",
        )
    assert excinfo.value.code == "document_knowledge_lifecycle_reason_invalid"


# ---------------------------------------------------------------------------
# Service: conflict recording/resolution.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_and_list_conflict() -> None:
    service = _lifecycle_service()
    conflict = await service.record_conflict(
        actor=_subject("subject.detector"),
        organization_id=ORG,
        environment_id=ENV,
        knowledge_item_id_a="knowledge-item.zzz",
        knowledge_item_id_b="knowledge-item.aaa",
        conflict_type=DocumentKnowledgeConflictType.DUPLICATE_COVERAGE,
        correlation_id="cor_1",
    )
    # Recorded in canonical order regardless of the caller's argument order.
    assert (conflict.knowledge_item_id_a, conflict.knowledge_item_id_b) == (
        "knowledge-item.aaa",
        "knowledge-item.zzz",
    )
    assert conflict.is_resolved is False

    for item_id in ("knowledge-item.aaa", "knowledge-item.zzz"):
        listed = await service.list_conflicts(
            actor=_subject("subject.reader"),
            organization_id=ORG,
            environment_id=ENV,
            knowledge_item_id=item_id,
            correlation_id="cor_2",
        )
        assert [item.conflict_id for item in listed] == [conflict.conflict_id]


@pytest.mark.asyncio
async def test_record_conflict_rejects_identical_items() -> None:
    service = _lifecycle_service()
    with pytest.raises(DocumentKnowledgeError) as excinfo:
        await service.record_conflict(
            actor=_subject("subject.detector"),
            organization_id=ORG,
            environment_id=ENV,
            knowledge_item_id_a="knowledge-item.same",
            knowledge_item_id_b="knowledge-item.same",
            conflict_type=DocumentKnowledgeConflictType.VERSION_MISMATCH,
            correlation_id="cor_1",
        )
    assert excinfo.value.code == "document_knowledge_conflict_target_invalid"


@pytest.mark.asyncio
async def test_resolve_conflict_requires_existing_conflict() -> None:
    service = _lifecycle_service()
    with pytest.raises(DocumentKnowledgeError) as excinfo:
        await service.resolve_conflict(
            actor=_subject("subject.resolver"),
            organization_id=ORG,
            environment_id=ENV,
            conflict_id="document-knowledge-conflict.does-not-exist",
            resolution="N/A",
            correlation_id="cor_1",
        )
    assert excinfo.value.code == "document_knowledge_conflict_not_found"


@pytest.mark.asyncio
async def test_resolve_conflict_rejects_blank_resolution() -> None:
    service = _lifecycle_service()
    conflict = await service.record_conflict(
        actor=_subject("subject.detector"),
        organization_id=ORG,
        environment_id=ENV,
        knowledge_item_id_a="knowledge-item.a1",
        knowledge_item_id_b="knowledge-item.b1",
        conflict_type=DocumentKnowledgeConflictType.SCOPE_OVERLAP,
        correlation_id="cor_1",
    )
    with pytest.raises(DocumentKnowledgeError) as excinfo:
        await service.resolve_conflict(
            actor=_subject("subject.resolver"),
            organization_id=ORG,
            environment_id=ENV,
            conflict_id=conflict.conflict_id,
            resolution="   ",
            correlation_id="cor_2",
        )
    assert excinfo.value.code == "document_knowledge_conflict_resolution_invalid"


@pytest.mark.asyncio
async def test_resolve_conflict_rejects_already_resolved() -> None:
    service = _lifecycle_service()
    conflict = await service.record_conflict(
        actor=_subject("subject.detector"),
        organization_id=ORG,
        environment_id=ENV,
        knowledge_item_id_a="knowledge-item.a2",
        knowledge_item_id_b="knowledge-item.b2",
        conflict_type=DocumentKnowledgeConflictType.CONTRADICTORY_GUIDANCE,
        correlation_id="cor_1",
    )
    resolved = await service.resolve_conflict(
        actor=_subject("subject.resolver"),
        organization_id=ORG,
        environment_id=ENV,
        conflict_id=conflict.conflict_id,
        resolution="Superseded the older guidance.",
        correlation_id="cor_2",
    )
    assert resolved.is_resolved is True
    assert resolved.resolved_by == "subject.resolver"

    with pytest.raises(DocumentKnowledgeError) as excinfo:
        await service.resolve_conflict(
            actor=_subject("subject.resolver"),
            organization_id=ORG,
            environment_id=ENV,
            conflict_id=conflict.conflict_id,
            resolution="Trying again.",
            correlation_id="cor_3",
        )
    assert excinfo.value.code == "document_knowledge_conflict_already_resolved"


# ---------------------------------------------------------------------------
# End-to-end: real retrieval-time enforcement (the load-bearing proof).
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def embedder() -> FastEmbedDocumentEmbedder:
    return FastEmbedDocumentEmbedder()


def _build_services(
    embedder: FastEmbedDocumentEmbedder,
) -> tuple[
    DocumentKnowledgeService, DocumentKnowledgeRetrievalService, DocumentKnowledgeLifecycleService
]:
    document_repository = InMemoryDocumentKnowledgeRepository()
    protected_content = InMemoryProtectedContentStore()
    lifecycle_repository = InMemoryDocumentKnowledgeLifecycleRepository()
    knowledge_service = DocumentKnowledgeService(
        repository=document_repository,
        protected_content=protected_content,
        permission_authorizer=AllowAllAuthorizer(),
        audit_sink=_NullAuditSink(),
        subject_salt="lifecycle-test-salt",
        clock=lambda: NOW,
    )
    retrieval_service = DocumentKnowledgeRetrievalService(
        repository=document_repository,
        protected_content=protected_content,
        chunker=ParagraphBoundedChunker(maximum_chunk_characters=200),
        embedder=embedder,
        vector_index=InMemoryDocumentVectorIndex(),
        permission_authorizer=AllowAllAuthorizer(),
        audit_sink=_NullAuditSink(),
        clock=lambda: NOW,
        lifecycle_reader=lifecycle_repository,
    )
    lifecycle_service = DocumentKnowledgeLifecycleService(
        repository=lifecycle_repository,
        permission_authorizer=AllowAllAuthorizer(),
        audit_sink=_NullAuditSink(),
        clock=lambda: NOW,
    )
    return knowledge_service, retrieval_service, lifecycle_service


async def _approved_preparation(
    knowledge_service: DocumentKnowledgeService, *, content: bytes, prefix: str
) -> DocumentKnowledgePublicationPreparation:
    draft = await knowledge_service.curate_draft(
        actor=_subject(f"subject.{prefix}-curator"),
        organization_id=ORG,
        environment_id=ENV,
        content=content,
        title="Storage Controller Runbook",
        draft_domain="domain.vendor",
        content_type="text/markdown",
        classification="classification.internal",
        access_policy_id="access-policy.default",
        retention_policy_id="retention-policy.default",
        purpose="A runbook used to validate real retrieval-time lifecycle enforcement.",
        correlation_id=f"cor_{prefix}_1",
    )
    review = await knowledge_service.submit_review_decision(
        actor=_subject(f"subject.{prefix}-reviewer"),
        organization_id=ORG,
        environment_id=ENV,
        draft_id=draft.draft_id,
        decision=REVIEW_DECISION_PASSED,
        findings=("No issues found.",),
        correlation_id=f"cor_{prefix}_2",
    )
    approval = await knowledge_service.record_final_approval(
        actor=_subject(f"subject.{prefix}-approver"),
        organization_id=ORG,
        environment_id=ENV,
        review_id=review.review_id,
        decision="approved",
        rationale="Content is accurate and ready for indexing.",
        correlation_id=f"cor_{prefix}_3",
    )
    return await knowledge_service.prepare_publication(
        actor=_subject(f"subject.{prefix}-approver"),
        organization_id=ORG,
        environment_id=ENV,
        approval_id=approval.approval_id,
        chunking_profile_digest="a" * 64,
        correlation_id=f"cor_{prefix}_4",
    )


@pytest.mark.asyncio
async def test_suspended_item_is_excluded_from_retrieval_results(
    embedder: FastEmbedDocumentEmbedder,
) -> None:
    """The load-bearing proof: index a document, retrieve it successfully, suspend it, retrieve
    again with the same query, and confirm it is now excluded."""
    knowledge_service, retrieval_service, lifecycle_service = _build_services(embedder)
    preparation = await _approved_preparation(
        knowledge_service, content=STORAGE_DOC.encode("utf-8"), prefix="suspend"
    )
    await retrieval_service.index_document(
        actor=_subject("subject.indexer"),
        organization_id=ORG,
        environment_id=ENV,
        preparation_id=preparation.preparation_id,
        correlation_id="cor_index",
    )

    before = await retrieval_service.retrieve(
        actor=_subject("subject.searcher"),
        organization_id=ORG,
        environment_id=ENV,
        query="storage controller warning status escalation",
        top_k=3,
        correlation_id="cor_before",
    )
    assert before
    assert before[0].knowledge_item_id == preparation.knowledge_item_id

    await lifecycle_service.suspend(
        actor=_subject("subject.admin"),
        organization_id=ORG,
        environment_id=ENV,
        knowledge_item_id=preparation.knowledge_item_id,
        reason="Under investigation for accuracy.",
        correlation_id="cor_suspend",
    )

    after = await retrieval_service.retrieve(
        actor=_subject("subject.searcher"),
        organization_id=ORG,
        environment_id=ENV,
        query="storage controller warning status escalation",
        top_k=3,
        correlation_id="cor_after",
    )
    assert after == []


@pytest.mark.asyncio
async def test_superseded_item_is_excluded_from_retrieval_results(
    embedder: FastEmbedDocumentEmbedder,
) -> None:
    knowledge_service, retrieval_service, lifecycle_service = _build_services(embedder)
    preparation = await _approved_preparation(
        knowledge_service, content=STORAGE_DOC.encode("utf-8"), prefix="supersede"
    )
    await retrieval_service.index_document(
        actor=_subject("subject.indexer"),
        organization_id=ORG,
        environment_id=ENV,
        preparation_id=preparation.preparation_id,
        correlation_id="cor_index",
    )
    before = await retrieval_service.retrieve(
        actor=_subject("subject.searcher"),
        organization_id=ORG,
        environment_id=ENV,
        query="storage controller warning status escalation",
        top_k=3,
        correlation_id="cor_before",
    )
    assert before

    await lifecycle_service.supersede(
        actor=_subject("subject.admin"),
        organization_id=ORG,
        environment_id=ENV,
        knowledge_item_id=preparation.knowledge_item_id,
        superseded_by_item_id="knowledge-item.replacement-runbook",
        reason="Replaced by an updated runbook covering the same procedure.",
        correlation_id="cor_supersede",
    )

    after = await retrieval_service.retrieve(
        actor=_subject("subject.searcher"),
        organization_id=ORG,
        environment_id=ENV,
        query="storage controller warning status escalation",
        top_k=3,
        correlation_id="cor_after",
    )
    assert after == []


@pytest.mark.asyncio
async def test_resumed_item_reappears_in_retrieval_results(
    embedder: FastEmbedDocumentEmbedder,
) -> None:
    """Round-trips the exclusion proof: suspend removes it, resume brings it back -- proof the
    filter reflects genuinely *current* state, not a one-way flag."""
    knowledge_service, retrieval_service, lifecycle_service = _build_services(embedder)
    preparation = await _approved_preparation(
        knowledge_service, content=STORAGE_DOC.encode("utf-8"), prefix="resume"
    )
    await retrieval_service.index_document(
        actor=_subject("subject.indexer"),
        organization_id=ORG,
        environment_id=ENV,
        preparation_id=preparation.preparation_id,
        correlation_id="cor_index",
    )
    await lifecycle_service.suspend(
        actor=_subject("subject.admin"),
        organization_id=ORG,
        environment_id=ENV,
        knowledge_item_id=preparation.knowledge_item_id,
        reason="Temporary suspension.",
        correlation_id="cor_suspend",
    )
    suspended_results = await retrieval_service.retrieve(
        actor=_subject("subject.searcher"),
        organization_id=ORG,
        environment_id=ENV,
        query="storage controller warning status escalation",
        top_k=3,
        correlation_id="cor_during",
    )
    assert suspended_results == []

    await lifecycle_service.resume(
        actor=_subject("subject.admin"),
        organization_id=ORG,
        environment_id=ENV,
        knowledge_item_id=preparation.knowledge_item_id,
        reason="Suspension lifted after review.",
        correlation_id="cor_resume",
    )
    resumed_results = await retrieval_service.retrieve(
        actor=_subject("subject.searcher"),
        organization_id=ORG,
        environment_id=ENV,
        query="storage controller warning status escalation",
        top_k=3,
        correlation_id="cor_resumed",
    )
    assert resumed_results
    assert resumed_results[0].knowledge_item_id == preparation.knowledge_item_id


@pytest.mark.asyncio
async def test_item_with_no_lifecycle_record_is_unaffected_by_the_filter(
    embedder: FastEmbedDocumentEmbedder,
) -> None:
    """The overwhelming common case (docs/027 SS8's "Published" default): an item nobody has
    ever suspended/superseded/retired must retrieve exactly as if the lifecycle reader were
    absent entirely -- this is the zero-regression guarantee for existing retrieval behavior."""
    knowledge_service, retrieval_service, _lifecycle_service = _build_services(embedder)
    preparation = await _approved_preparation(
        knowledge_service, content=STORAGE_DOC.encode("utf-8"), prefix="untouched"
    )
    await retrieval_service.index_document(
        actor=_subject("subject.indexer"),
        organization_id=ORG,
        environment_id=ENV,
        preparation_id=preparation.preparation_id,
        correlation_id="cor_index",
    )
    results = await retrieval_service.retrieve(
        actor=_subject("subject.searcher"),
        organization_id=ORG,
        environment_id=ENV,
        query="storage controller warning status escalation",
        top_k=3,
        correlation_id="cor_search",
    )
    assert results
    assert results[0].knowledge_item_id == preparation.knowledge_item_id
