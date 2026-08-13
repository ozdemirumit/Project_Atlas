from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings, subject
from test_upgrade_change_review import (
    change_review_context,
    packet_request,
    preview_request,
)

from atlas.api.app import create_app
from atlas.core.capabilities import CapabilityClass
from atlas.core.persistence.models import UpgradeChangeHumanReviewModel
from atlas.modules.authorization.application.bootstrap import (
    UPGRADE_HUMAN_REVIEW_DECIDE,
    UPGRADE_HUMAN_REVIEW_READ,
    upgrade_human_review_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import (
    PermissionDefinition,
    RoleAssignment,
    RoleDefinition,
)
from atlas.modules.change_review.adapters.human_review_memory import (
    InMemoryHumanReviewRepository,
)
from atlas.modules.change_review.adapters.human_review_postgres import (
    PostgreSQLHumanReviewRepository,
)
from atlas.modules.change_review.application.human_review_service import HumanReviewService
from atlas.modules.change_review.application.ports import ChangeReviewError
from atlas.modules.change_review.domain.human_review import (
    HumanReviewOutcome,
    HumanReviewStageState,
    HumanReviewState,
)
from atlas.modules.identity.domain.models import AssuranceLevel, SubjectKind


async def human_review_context(tmp_path: Path) -> tuple[Any, ...]:
    context, plan, simulation, packet_repository, change_review = await change_review_context(
        tmp_path
    )
    preview = await change_review.preview(**preview_request(plan, simulation))
    packet = await change_review.create_packet(**packet_request(preview, plan, simulation))
    review_repository = InMemoryHumanReviewRepository()
    review = HumanReviewService(
        packet_repository=packet_repository,
        review_repository=review_repository,
        audit_sink=context[0],
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: context[1].now if hasattr(context[1], "now") else packet.created_at,
    )
    return context, packet, packet_repository, review_repository, review


def create_request(packet: Any, *, key: str = "human-review-create-0001") -> dict[str, Any]:
    return {
        "actor": subject(),
        "packet_id": packet.packet_id,
        "packet_digest": packet.packet_digest,
        "justification": "Route the exact upgrade evidence through separated human review",
        "confirmed": True,
        "acknowledged_no_authority": True,
        "idempotency_key": key,
        "correlation_id": "correlation.human-review.create",
    }


def reviewer(sequence: int, role_id: str):  # type: ignore[no-untyped-def]
    return replace(
        subject(),
        subject_id=f"subject.enterprise.reviewer-{sequence}",
        display_name=f"Enterprise Reviewer {sequence}",
        role_ids=(role_id,),
    )


@pytest.mark.asyncio
async def test_four_distinct_humans_complete_review_without_execution_authority(
    tmp_path: Path,
) -> None:
    _, packet, _, _, service = await human_review_context(tmp_path)
    record = await service.create(**create_request(packet))
    replay = await service.create(**create_request(packet))
    assert replay.review_id == record.review_id
    assert replay.reused is True
    assert [stage.state for stage in record.stages] == [
        HumanReviewStageState.PENDING,
        HumanReviewStageState.WAITING,
        HumanReviewStageState.WAITING,
        HumanReviewStageState.WAITING,
    ]

    for sequence, stage in enumerate(record.stages, start=1):
        record = await service.decide(
            actor=reviewer(sequence, stage.required_role_id),
            review_id=record.review_id,
            stage_id=stage.stage_id,
            outcome=HumanReviewOutcome.APPROVE,
            rationale=f"Stage {sequence} evidence and boundaries were reviewed and accepted",
            acknowledged_no_authority=True,
            expected_version=record.version,
            idempotency_key=f"human-review-decision-{sequence:04d}",
            correlation_id=f"correlation.human-review.decision-{sequence}",
        )

    assert record.state is HumanReviewState.COMPLETED
    assert record.human_review_completed is True
    assert len(record.decisions) == 4
    assert len({decision.reviewer_id for decision in record.decisions}) == 4
    assert all(stage.state is HumanReviewStageState.APPROVED for stage in record.stages)
    assert not any(
        (
            record.approval_granted,
            record.itsm_dispatched,
            record.handoff_issued,
            record.workflow_executed,
            record.execution_authorized,
            record.infrastructure_mutation_performed,
        )
    )


@pytest.mark.asyncio
async def test_review_rejects_self_wrong_role_duplicate_reviewer_and_stale_version(
    tmp_path: Path,
) -> None:
    _, packet, _, _, service = await human_review_context(tmp_path)
    record = await service.create(**create_request(packet))
    stage = record.stages[0]
    common = {
        "review_id": record.review_id,
        "stage_id": stage.stage_id,
        "outcome": HumanReviewOutcome.APPROVE,
        "rationale": "The bounded evidence was reviewed for this exact stage",
        "acknowledged_no_authority": True,
        "expected_version": record.version,
        "correlation_id": "correlation.human-review.guard",
    }
    with pytest.raises(ChangeReviewError, match="separation_required"):
        await service.decide(
            actor=replace(subject(), role_ids=(stage.required_role_id,)),
            idempotency_key="human-review-self-0001",
            **common,
        )
    with pytest.raises(ChangeReviewError, match="role_required"):
        await service.decide(
            actor=reviewer(1, "role.unrelated-reviewer"),
            idempotency_key="human-review-role-0001",
            **common,
        )
    with pytest.raises(ChangeReviewError, match="human_reviewer_required"):
        await service.decide(
            actor=replace(
                reviewer(1, stage.required_role_id),
                subject_id="service.enterprise.reviewer",
                kind=SubjectKind.SERVICE,
            ),
            idempotency_key="human-review-service-0001",
            **common,
        )
    first_reviewer = replace(
        reviewer(1, stage.required_role_id),
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )
    updated = await service.decide(
        actor=first_reviewer,
        idempotency_key="human-review-development-assurance-0001",
        **common,
    )
    assert updated.decisions[-1].reviewer_id == first_reviewer.subject_id
    with pytest.raises(ChangeReviewError, match="distinct_reviewer_required"):
        await service.decide(
            actor=replace(first_reviewer, role_ids=(updated.stages[1].required_role_id,)),
            review_id=updated.review_id,
            stage_id=updated.stages[1].stage_id,
            outcome=HumanReviewOutcome.APPROVE,
            rationale="The same reviewer must not count twice across required stages",
            acknowledged_no_authority=True,
            expected_version=updated.version,
            idempotency_key="human-review-duplicate-0001",
            correlation_id="correlation.human-review.duplicate",
        )
    with pytest.raises(ChangeReviewError, match="state_conflict"):
        await service.decide(
            actor=reviewer(2, updated.stages[1].required_role_id),
            review_id=updated.review_id,
            stage_id=updated.stages[1].stage_id,
            outcome=HumanReviewOutcome.APPROVE,
            rationale="This request intentionally uses an obsolete expected version",
            acknowledged_no_authority=True,
            expected_version=record.version,
            idempotency_key="human-review-stale-0001",
            correlation_id="correlation.human-review.stale",
        )


@pytest.mark.asyncio
async def test_decision_replay_and_changed_replay_are_deterministic(tmp_path: Path) -> None:
    _, packet, _, _, service = await human_review_context(tmp_path)
    record = await service.create(**create_request(packet))
    stage = record.stages[0]
    request = {
        "actor": reviewer(1, stage.required_role_id),
        "review_id": record.review_id,
        "stage_id": stage.stage_id,
        "outcome": HumanReviewOutcome.NEEDS_EVIDENCE,
        "rationale": "A current customer dependency map is required before approval",
        "acknowledged_no_authority": True,
        "expected_version": record.version,
        "idempotency_key": "human-review-replay-0001",
        "correlation_id": "correlation.human-review.replay",
    }
    first = await service.decide(**request)
    replay = await service.decide(**request)
    assert replay.version == first.version
    assert replay.reused is True
    assert first.state is HumanReviewState.NEEDS_EVIDENCE
    with pytest.raises(ChangeReviewError, match="idempotency_conflict"):
        await service.decide(**{**request, "rationale": "A materially changed rationale"})


@pytest.mark.asyncio
async def test_inbox_filters_before_pagination_and_advances_to_distinct_role(
    tmp_path: Path,
) -> None:
    _, packet, _, _, service = await human_review_context(tmp_path)
    first_request = create_request(packet, key="human-review-inbox-first")
    first_request["justification"] = "Route first exact packet through the separated review inbox"
    second_request = create_request(packet, key="human-review-inbox-second")
    second_request["justification"] = "Route second exact packet through the separated review inbox"
    first = await service.create(**first_request)
    second = await service.create(**second_request)
    platform_reviewer = reviewer(1, first.stages[0].required_role_id)

    requester_page = await service.inbox(
        actor=subject(),
        role_id=None,
        cursor=None,
        limit=20,
        correlation_id="correlation.human-review.inbox.requester",
    )
    wrong_role_page = await service.inbox(
        actor=reviewer(9, "role.unrelated-reviewer"),
        role_id=None,
        cursor=None,
        limit=20,
        correlation_id="correlation.human-review.inbox.wrong-role",
    )
    first_page = await service.inbox(
        actor=platform_reviewer,
        role_id=first.stages[0].required_role_id,
        cursor=None,
        limit=1,
        correlation_id="correlation.human-review.inbox.first-page",
    )
    second_page = await service.inbox(
        actor=platform_reviewer,
        role_id=None,
        cursor=first_page.next_cursor,
        limit=1,
        correlation_id="correlation.human-review.inbox.second-page",
    )

    assert requester_page.items == ()
    assert wrong_role_page.items == ()
    assert len(first_page.items) == 1
    assert first_page.next_cursor == first_page.items[0].review_id
    assert len(second_page.items) == 1
    assert second_page.next_cursor is None
    assert {first_page.items[0].review_id, second_page.items[0].review_id} == {
        first.review_id,
        second.review_id,
    }

    updated = await service.decide(
        actor=platform_reviewer,
        review_id=first.review_id,
        stage_id=first.stages[0].stage_id,
        outcome=HumanReviewOutcome.APPROVE,
        rationale="The platform evidence is exact and the no-execution boundary is accepted",
        acknowledged_no_authority=True,
        expected_version=first.version,
        idempotency_key="human-review-inbox-decision",
        correlation_id="correlation.human-review.inbox.decision",
    )
    prior_reviewer_page = await service.inbox(
        actor=replace(
            platform_reviewer,
            role_ids=(updated.stages[1].required_role_id,),
        ),
        role_id=None,
        cursor=None,
        limit=20,
        correlation_id="correlation.human-review.inbox.prior-reviewer",
    )
    service_owner_page = await service.inbox(
        actor=reviewer(2, updated.stages[1].required_role_id),
        role_id=None,
        cursor=None,
        limit=20,
        correlation_id="correlation.human-review.inbox.service-owner",
    )
    assert first.review_id not in {item.review_id for item in prior_reviewer_page.items}
    assert first.review_id in {item.review_id for item in service_owner_page.items}


@pytest.mark.asyncio
async def test_inbox_audit_failure_discloses_no_page(tmp_path: Path) -> None:
    _, packet, packet_repository, review_repository, service = await human_review_context(tmp_path)
    record = await service.create(**create_request(packet))

    class FailingAuditSink:
        async def record(self, event) -> None:  # type: ignore[no-untyped-def]
            raise RuntimeError("audit unavailable")

    failing = HumanReviewService(
        packet_repository=packet_repository,
        review_repository=review_repository,
        audit_sink=FailingAuditSink(),
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: packet.created_at,
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await failing.inbox(
            actor=reviewer(1, record.stages[0].required_role_id),
            role_id=None,
            cursor=None,
            limit=20,
            correlation_id="correlation.human-review.inbox.audit-failure",
        )


@pytest.mark.asyncio
async def test_required_audit_failure_leaves_no_human_review(tmp_path: Path) -> None:
    _, packet, packet_repository, review_repository, _ = await human_review_context(tmp_path)

    class FailingAuditSink:
        async def record(self, event) -> None:  # type: ignore[no-untyped-def]
            raise RuntimeError("audit unavailable")

    service = HumanReviewService(
        packet_repository=packet_repository,
        review_repository=review_repository,
        audit_sink=FailingAuditSink(),
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: packet.created_at,
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await service.create(**create_request(packet))
    assert review_repository._records == {}


@pytest.mark.asyncio
async def test_required_decision_audit_failure_leaves_review_unchanged(tmp_path: Path) -> None:
    context, packet, packet_repository, review_repository, service = await human_review_context(
        tmp_path
    )
    record = await service.create(**create_request(packet))

    class FailingAuditSink:
        async def record(self, event) -> None:  # type: ignore[no-untyped-def]
            raise RuntimeError("audit unavailable")

    failing = HumanReviewService(
        packet_repository=packet_repository,
        review_repository=review_repository,
        audit_sink=FailingAuditSink(),
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: packet.created_at,
    )
    stage = record.stages[0]
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await failing.decide(
            actor=reviewer(1, stage.required_role_id),
            review_id=record.review_id,
            stage_id=stage.stage_id,
            outcome=HumanReviewOutcome.APPROVE,
            rationale="This decision must not persist when required audit is unavailable",
            acknowledged_no_authority=True,
            expected_version=record.version,
            idempotency_key="human-review-audit-decision",
            correlation_id="correlation.human-review.audit-failure",
        )
    unchanged = await review_repository.get_by_id(review_id=record.review_id)
    assert unchanged == record
    assert context[0].records[-1].result_code == "upgrade_human_review_created"


def test_postgres_human_review_mapping_preserves_stages(tmp_path: Path) -> None:
    _, packet, _, _, service = asyncio.run(human_review_context(tmp_path))
    record = asyncio.run(service.create(**create_request(packet)))
    record = asyncio.run(
        service.decide(
            actor=reviewer(1, record.stages[0].required_role_id),
            review_id=record.review_id,
            stage_id=record.stages[0].stage_id,
            outcome=HumanReviewOutcome.APPROVE,
            rationale="The exact stage evidence was reviewed without execution authority",
            acknowledged_no_authority=True,
            expected_version=record.version,
            idempotency_key="human-review-postgres-decision",
            correlation_id="correlation.human-review.postgres-decision",
        )
    )
    values = PostgreSQLHumanReviewRepository._values(record)
    row = UpgradeChangeHumanReviewModel(**values)
    restored = PostgreSQLHumanReviewRepository._to_domain(row)
    assert restored.canonical_digest == record.canonical_digest
    assert restored.stages == record.stages
    assert restored.decisions[0].acknowledged_no_authority is True
    assert restored.execution_authorized is False
    legacy_values = PostgreSQLHumanReviewRepository._values(record)
    legacy_values["decisions"][0].pop("acknowledged_no_authority")
    legacy = PostgreSQLHumanReviewRepository._to_domain(
        UpgradeChangeHumanReviewModel(**legacy_values)
    )
    assert legacy.decisions[0].acknowledged_no_authority is False


def test_human_review_api_requires_csrf_and_keeps_requester_ineligible(tmp_path: Path) -> None:
    context, packet, packet_repository, _, _ = asyncio.run(human_review_context(tmp_path))
    repository = InMemoryHumanReviewRepository()
    service = HumanReviewService(
        packet_repository=packet_repository,
        review_repository=repository,
        audit_sink=context[0],
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: packet.created_at,
    )
    with TestClient(
        create_app(
            settings(logical_backup_root=tmp_path / "default-backups"),
            identity_provider=BasicTestIdentityProvider(),
            audit_sink=context[0],
            recovery_service=context[4],
            upgrade_service=context[8],
            human_review_service=service,
        )
    ) as client:
        session = login(client)
        csrf = session.headers["X-CSRF-Token"]
        payload = {
            "schema_version": "atlas.upgrade-change-human-review-create-request.v1",
            "packet_id": packet.packet_id,
            "packet_digest": packet.packet_digest,
            "justification": "Route exact packet evidence through separated human review",
            "confirmed": True,
            "acknowledged_no_authority": True,
        }
        missing_csrf = client.post(
            f"/api/v1/platform/upgrade-change-reviews/{packet.packet_id}/human-reviews",
            headers={"Idempotency-Key": "human-review-api-missing"},
            json=payload,
        )
        created = client.post(
            f"/api/v1/platform/upgrade-change-reviews/{packet.packet_id}/human-reviews",
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "human-review-api-create",
            },
            json=payload,
        )
        data = created.json()["data"]
        read = client.get(
            f"/api/v1/platform/upgrade-change-reviews/human-reviews/{data['review_id']}"
        )
        self_decision = client.post(
            f"/api/v1/platform/upgrade-change-reviews/human-reviews/{data['review_id']}/decisions",
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "human-review-api-decision",
            },
            json={
                "schema_version": "atlas.upgrade-change-human-review-decision-request.v1",
                "stage_id": data["stages"][0]["stage_id"],
                "outcome": "approve",
                "rationale": "The requester must not approve their own review request",
                "acknowledged_no_authority": True,
                "expected_version": data["version"],
            },
        )
    assert missing_csrf.status_code == 403
    assert created.status_code == 200, created.text
    assert read.status_code == 200, read.text
    assert read.headers["Cache-Control"] == "no-store"
    assert data["execution_authorized"] is False
    assert self_decision.status_code == 409
    assert self_decision.json()["code"] == "human_review_separation_required"


def test_reviewer_inbox_api_lists_and_decides_only_current_assigned_stage(tmp_path: Path) -> None:
    context, packet, packet_repository, _, _ = asyncio.run(human_review_context(tmp_path))
    repository = InMemoryHumanReviewRepository()
    service = HumanReviewService(
        packet_repository=packet_repository,
        review_repository=repository,
        audit_sink=context[0],
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: packet.created_at,
    )
    record = asyncio.run(service.create(**create_request(packet)))
    review_actor = reviewer(1, record.stages[0].required_role_id)
    read_scope = upgrade_human_review_scope(
        "organization.development", "test", CapabilityClass.C1_READ_ONLY
    )
    decide_scope = upgrade_human_review_scope(
        "organization.development", "test", CapabilityClass.C2_DIAGNOSTIC
    )
    authorization = AuthorizationService(
        permissions=(
            PermissionDefinition(
                permission_id=UPGRADE_HUMAN_REVIEW_READ,
                description="Read assigned upgrade human reviews.",
            ),
            PermissionDefinition(
                permission_id=UPGRADE_HUMAN_REVIEW_DECIDE,
                description="Decide assigned upgrade human review stages.",
            ),
        ),
        roles=(
            RoleDefinition(
                role_id=record.stages[0].required_role_id,
                version=1,
                permissions=frozenset({UPGRADE_HUMAN_REVIEW_READ, UPGRADE_HUMAN_REVIEW_DECIDE}),
            ),
        ),
        assignments=(
            RoleAssignment(
                assignment_id="assignment.test.platform-reviewer.read",
                version=1,
                subject_id=review_actor.subject_id,
                role_id=record.stages[0].required_role_id,
                scope=read_scope,
                valid_from=packet.created_at,
            ),
            RoleAssignment(
                assignment_id="assignment.test.platform-reviewer.decide",
                version=1,
                subject_id=review_actor.subject_id,
                role_id=record.stages[0].required_role_id,
                scope=decide_scope,
                valid_from=packet.created_at,
            ),
        ),
        audit_sink=context[0],
        clock=lambda: packet.created_at,
    )
    with TestClient(
        create_app(
            settings(logical_backup_root=tmp_path / "reviewer-backups"),
            identity_provider=BasicTestIdentityProvider(authenticated_subject=review_actor),
            authorization_service=authorization,
            audit_sink=context[0],
            recovery_service=context[4],
            upgrade_service=context[8],
            human_review_service=service,
        )
    ) as client:
        session = login(client)
        csrf = session.headers["X-CSRF-Token"]
        inbox = client.get("/api/v1/platform/upgrade-change-reviews/human-reviews")
        item = inbox.json()["data"]["items"][0]
        unacknowledged = client.post(
            f"/api/v1/platform/upgrade-change-reviews/human-reviews/{record.review_id}/decisions",
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "human-review-api-unacknowledged",
            },
            json={
                "schema_version": "atlas.upgrade-change-human-review-decision-request.v1",
                "stage_id": record.stages[0].stage_id,
                "outcome": "approve",
                "rationale": "Exact evidence was reviewed without execution authority",
                "acknowledged_no_authority": False,
                "expected_version": record.version,
            },
        )
        decided = client.post(
            f"/api/v1/platform/upgrade-change-reviews/human-reviews/{record.review_id}/decisions",
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "human-review-api-reviewer-decision",
            },
            json={
                "schema_version": "atlas.upgrade-change-human-review-decision-request.v1",
                "stage_id": record.stages[0].stage_id,
                "outcome": "approve",
                "rationale": "Exact evidence and the no-execution boundary were reviewed",
                "acknowledged_no_authority": True,
                "expected_version": record.version,
            },
        )
        refreshed = client.get("/api/v1/platform/upgrade-change-reviews/human-reviews")

    assert inbox.status_code == 200, inbox.text
    assert inbox.headers["Cache-Control"] == "no-store"
    assert item["review_id"] == record.review_id
    assert item["stages"][0]["state"] == "pending"
    assert unacknowledged.status_code == 409
    assert unacknowledged.json()["code"] == "human_review_decision_confirmation_required"
    assert decided.status_code == 200, decided.text
    assert decided.json()["data"]["stages"][1]["state"] == "pending"
    assert decided.json()["data"]["execution_authorized"] is False
    assert refreshed.status_code == 200
    assert refreshed.json()["data"]["items"] == []
