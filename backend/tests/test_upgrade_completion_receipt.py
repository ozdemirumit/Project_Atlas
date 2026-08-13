from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_upgrade_human_review import create_request, human_review_context, reviewer

from atlas.api.app import create_app
from atlas.core.capabilities import CapabilityClass
from atlas.core.persistence.models import HumanReviewCompletionReceiptModel
from atlas.modules.authorization.application.bootstrap import (
    UPGRADE_COMPLETION_RECEIPT_CREATE,
    UPGRADE_COMPLETION_RECEIPT_READ,
    upgrade_completion_receipt_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import (
    PermissionDefinition,
    RoleAssignment,
    RoleDefinition,
)
from atlas.modules.change_review.adapters.completion_receipt_memory import (
    InMemoryCompletionReceiptRepository,
)
from atlas.modules.change_review.adapters.completion_receipt_postgres import (
    PostgreSQLCompletionReceiptRepository,
)
from atlas.modules.change_review.application.completion_receipt_service import (
    CompletionReceiptService,
)
from atlas.modules.change_review.application.ports import ChangeReviewError
from atlas.modules.change_review.domain.human_review import HumanReviewOutcome
from atlas.modules.identity.domain.models import AssuranceLevel, SubjectKind


async def completion_context(tmp_path: Path) -> tuple[Any, ...]:
    (
        context,
        packet,
        packet_repository,
        review_repository,
        review_service,
    ) = await human_review_context(tmp_path)
    review = await review_service.create(**create_request(packet))
    reviewers = []
    for sequence, stage in enumerate(review.stages, start=1):
        actor = reviewer(sequence, stage.required_role_id)
        reviewers.append(actor)
        review = await review_service.decide(
            actor=actor,
            review_id=review.review_id,
            stage_id=stage.stage_id,
            outcome=HumanReviewOutcome.APPROVE,
            rationale=f"Stage {sequence} exact evidence and boundaries were accepted",
            acknowledged_no_authority=True,
            expected_version=review.version,
            idempotency_key=f"completion-source-decision-{sequence:04d}",
            correlation_id=f"correlation.completion.source-{sequence}",
        )
    receipt_repository = InMemoryCompletionReceiptRepository()
    receipt_service = CompletionReceiptService(
        packet_repository=packet_repository,
        review_repository=review_repository,
        receipt_repository=receipt_repository,
        audit_sink=context[0],
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: packet.created_at,
    )
    return (
        context,
        packet,
        packet_repository,
        review_repository,
        review_service,
        review,
        tuple(reviewers),
        receipt_repository,
        receipt_service,
    )


def receipt_request(
    review: Any, creator: Any, *, key: str = "completion-receipt-0001"
) -> dict[str, Any]:
    return {
        "actor": creator,
        "review_id": review.review_id,
        "expected_review_version": review.version,
        "acknowledged_evidence_only": True,
        "idempotency_key": key,
        "correlation_id": "correlation.completion-receipt.create",
    }


@pytest.mark.asyncio
async def test_completion_receipt_binds_four_humans_without_authority(tmp_path: Path) -> None:
    *_, review, reviewers, repository, service = await completion_context(tmp_path)
    development_creator = replace(reviewers[-1], assurance_level=AssuranceLevel.DEVELOPMENT)
    receipt = await service.create(**receipt_request(review, development_creator))
    replay = await service.create(**receipt_request(review, development_creator))
    read = await service.get(
        actor=development_creator,
        receipt_id=receipt.receipt_id,
        correlation_id="correlation.completion-receipt.read",
    )

    assert replay == replace(receipt, reused=True)
    assert read == receipt
    assert await repository.get_by_review_id(review_id=review.review_id) == receipt
    assert [stage.sequence for stage in receipt.stages] == [1, 2, 3, 4]
    assert len({stage.reviewer_id for stage in receipt.stages}) == 4
    assert all(stage.outcome is HumanReviewOutcome.APPROVE for stage in receipt.stages)
    assert all(stage.acknowledged_no_authority for stage in receipt.stages)
    assert receipt.human_review_completed is True
    assert receipt.completion_evidence_only is True
    assert not any(
        (
            receipt.approval_granted,
            receipt.itsm_dispatched,
            receipt.notification_sent,
            receipt.handoff_issued,
            receipt.workflow_executed,
            receipt.execution_authorized,
            receipt.infrastructure_mutation_performed,
        )
    )


@pytest.mark.asyncio
async def test_completion_receipt_rejects_incomplete_stale_and_wrong_creator(
    tmp_path: Path,
) -> None:
    (
        context,
        packet,
        packet_repository,
        review_repository,
        review_service,
    ) = await human_review_context(tmp_path)
    pending = await review_service.create(**create_request(packet))
    service = CompletionReceiptService(
        packet_repository=packet_repository,
        review_repository=review_repository,
        receipt_repository=InMemoryCompletionReceiptRepository(),
        audit_sink=context[0],
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: packet.created_at,
    )
    with pytest.raises(ChangeReviewError, match="confirmation_required"):
        await service.create(
            **{
                **receipt_request(pending, reviewer(1, pending.stages[-1].required_role_id)),
                "acknowledged_evidence_only": False,
            }
        )
    with pytest.raises(ChangeReviewError, match="human_required"):
        await service.create(
            **receipt_request(
                pending,
                replace(
                    reviewer(1, pending.stages[-1].required_role_id),
                    subject_id="service.enterprise.receipt-reader",
                    kind=SubjectKind.SERVICE,
                    assurance_level=AssuranceLevel.DEVELOPMENT,
                ),
                key="completion-receipt-service-creator",
            )
        )
    with pytest.raises(ChangeReviewError, match="review_ineligible"):
        await service.create(
            **receipt_request(pending, reviewer(1, pending.stages[-1].required_role_id))
        )

    *_, completed, reviewers, _, completed_service = await completion_context(tmp_path / "complete")
    with pytest.raises(ChangeReviewError, match="state_conflict"):
        await completed_service.create(
            **{
                **receipt_request(completed, reviewers[-1]),
                "expected_review_version": completed.version - 1,
            }
        )
    with pytest.raises(ChangeReviewError, match="creator_ineligible"):
        await completed_service.create(
            **receipt_request(
                completed,
                reviewer(99, completed.stages[-1].required_role_id),
                key="completion-receipt-wrong-creator",
            )
        )


@pytest.mark.asyncio
async def test_completion_receipt_changed_replay_and_source_tampering_fail_closed(
    tmp_path: Path,
) -> None:
    *_, review, reviewers, _, service = await completion_context(tmp_path)
    receipt = await service.create(**receipt_request(review, reviewers[-1]))
    with pytest.raises(ChangeReviewError, match="idempotency_conflict"):
        await service.create(
            **{
                **receipt_request(review, reviewers[-1]),
                "expected_review_version": review.version + 1,
            }
        )
    repository = service._review_repository
    changed = replace(review, canonical_digest="f" * 64)
    assert await repository.update(changed, expected_version=review.version)
    with pytest.raises(ChangeReviewError, match="source_changed"):
        await service.get(
            actor=reviewers[-1],
            receipt_id=receipt.receipt_id,
            correlation_id="correlation.completion-receipt.tampered",
        )


@pytest.mark.asyncio
async def test_required_receipt_audit_failure_leaves_repository_empty(tmp_path: Path) -> None:
    (
        _,
        packet,
        packet_repository,
        review_repository,
        _,
        review,
        reviewers,
        _,
        _,
    ) = await completion_context(tmp_path)

    class FailingAuditSink:
        async def record(self, event) -> None:  # type: ignore[no-untyped-def]
            raise RuntimeError("audit unavailable")

    repository = InMemoryCompletionReceiptRepository()
    service = CompletionReceiptService(
        packet_repository=packet_repository,
        review_repository=review_repository,
        receipt_repository=repository,
        audit_sink=FailingAuditSink(),
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: packet.created_at,
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await service.create(**receipt_request(review, reviewers[-1]))
    assert repository._records == {}


def test_postgres_completion_receipt_mapping_preserves_evidence(tmp_path: Path) -> None:
    *_, review, reviewers, _, service = asyncio.run(completion_context(tmp_path))
    receipt = asyncio.run(service.create(**receipt_request(review, reviewers[-1])))
    values = PostgreSQLCompletionReceiptRepository._values(receipt)
    restored = PostgreSQLCompletionReceiptRepository._to_domain(
        HumanReviewCompletionReceiptModel(**values)
    )
    assert restored == receipt
    assert restored.stages[0].rationale_digest == receipt.stages[0].rationale_digest
    assert restored.execution_authorized is False


def test_completion_receipt_api_requires_csrf_and_exact_permission(tmp_path: Path) -> None:
    (
        context,
        packet,
        packet_repository,
        review_repository,
        review_service,
        review,
        reviewers,
        _,
        _,
    ) = asyncio.run(completion_context(tmp_path))
    creator = reviewers[-1]
    receipt_service = CompletionReceiptService(
        packet_repository=packet_repository,
        review_repository=review_repository,
        receipt_repository=InMemoryCompletionReceiptRepository(),
        audit_sink=context[0],
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: packet.created_at,
    )
    role_id = review.stages[-1].required_role_id
    authorization = AuthorizationService(
        permissions=(
            PermissionDefinition(
                permission_id=UPGRADE_COMPLETION_RECEIPT_CREATE,
                description="Create exact completion evidence.",
            ),
            PermissionDefinition(
                permission_id=UPGRADE_COMPLETION_RECEIPT_READ,
                description="Read exact completion evidence.",
            ),
        ),
        roles=(
            RoleDefinition(
                role_id=role_id,
                version=1,
                permissions=frozenset(
                    {UPGRADE_COMPLETION_RECEIPT_CREATE, UPGRADE_COMPLETION_RECEIPT_READ}
                ),
            ),
        ),
        assignments=(
            RoleAssignment(
                assignment_id="assignment.test.completion.create",
                version=1,
                subject_id=creator.subject_id,
                role_id=role_id,
                scope=upgrade_completion_receipt_scope(
                    creator.organization_id, "test", CapabilityClass.C2_DIAGNOSTIC
                ),
                valid_from=packet.created_at,
            ),
            RoleAssignment(
                assignment_id="assignment.test.completion.read",
                version=1,
                subject_id=creator.subject_id,
                role_id=role_id,
                scope=upgrade_completion_receipt_scope(
                    creator.organization_id, "test", CapabilityClass.C1_READ_ONLY
                ),
                valid_from=packet.created_at,
            ),
        ),
        audit_sink=context[0],
        clock=lambda: packet.created_at,
    )
    with TestClient(
        create_app(
            settings(logical_backup_root=tmp_path / "api-backups"),
            identity_provider=BasicTestIdentityProvider(authenticated_subject=creator),
            authorization_service=authorization,
            audit_sink=context[0],
            recovery_service=context[4],
            upgrade_service=context[8],
            human_review_service=review_service,
            completion_receipt_service=receipt_service,
        )
    ) as client:
        session = login(client)
        payload = {
            "schema_version": "atlas.upgrade-human-review-completion-receipt-request.v1",
            "expected_review_version": review.version,
            "acknowledged_evidence_only": True,
        }
        path = (
            "/api/v1/platform/upgrade-change-reviews/human-reviews/"
            f"{review.review_id}/completion-receipts"
        )
        missing_csrf = client.post(
            path,
            headers={"Idempotency-Key": "completion-api-missing-csrf"},
            json=payload,
        )
        created = client.post(
            path,
            headers={
                "X-CSRF-Token": session.headers["X-CSRF-Token"],
                "Idempotency-Key": "completion-api-create",
            },
            json=payload,
        )
        data = created.json()["data"]
        replay = client.post(
            path,
            headers={
                "X-CSRF-Token": session.headers["X-CSRF-Token"],
                "Idempotency-Key": "completion-api-create",
            },
            json=payload,
        )
        read = client.get(
            f"/api/v1/platform/upgrade-change-reviews/completion-receipts/{data['receipt_id']}"
        )

    assert missing_csrf.status_code == 403
    assert created.status_code == 200, created.text
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["reused"] is True
    assert read.status_code == 200, read.text
    assert read.headers["Cache-Control"] == "no-store"
    assert data["schema_version"] == "atlas.upgrade-human-review-completion-receipt.v1"
    assert data["completion_evidence_only"] is True
    assert data["approval_granted"] is False
    assert data["execution_authorized"] is False
