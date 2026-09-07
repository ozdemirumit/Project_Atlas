from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.mcp_builder.adapters.draft_and_supersession_memory import (
    InMemoryBuilderDraftRepository,
)
from atlas.modules.mcp_builder.application.draft_and_supersession import (
    BuilderDraftError,
    BuilderDraftService,
)
from atlas.modules.mcp_builder.domain.draft_and_supersession import (
    a_builder_project_supersedes_itself,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


def _service() -> tuple[BuilderDraftService, CollectingAuditSink]:
    audit_sink = CollectingAuditSink()
    service = BuilderDraftService(
        repository=InMemoryBuilderDraftRepository(),
        audit_sink=audit_sink,
        clock=lambda: NOW,
    )
    return service, audit_sink


def test_absolute_rule_is_false() -> None:
    assert a_builder_project_supersedes_itself() is False


@pytest.mark.asyncio
async def test_create_draft_is_assembling_until_analyzed() -> None:
    service, audit_sink = _service()
    draft = await service.create_draft(
        draft_id="draft.brocade-sannav.primary",
        organization_id="organization.atlas.local",
        environment_id="environment.development",
        owner_id="subject.builder-operator.primary",
        vendor="Brocade",
        product="SANnav",
        target_environment="lab",
        notes="Initial source assembly for the SANnav REST API reference.",
        correlation_id="correlation.test",
    )
    assert draft.is_assembling is True
    assert any(item.outcome == "created" for item in audit_sink.records)


@pytest.mark.asyncio
async def test_mark_analyzed_transitions_out_of_assembling() -> None:
    service, audit_sink = _service()
    draft = await service.create_draft(
        draft_id="draft.brocade-sannav.primary",
        organization_id="organization.atlas.local",
        environment_id="environment.development",
        owner_id="subject.builder-operator.primary",
        vendor="Brocade",
        product="SANnav",
        target_environment="lab",
        notes="Initial source assembly.",
        correlation_id="correlation.test",
    )
    updated = await service.mark_analyzed(
        draft_id=draft.draft_id,
        analyzed_project_id="project.brocade-sannav.primary",
        correlation_id="correlation.test",
    )
    assert updated.is_assembling is False
    assert updated.analyzed_project_id == "project.brocade-sannav.primary"
    assert any(item.outcome == "analyzed" for item in audit_sink.records)


@pytest.mark.asyncio
async def test_mark_analyzed_twice_is_refused() -> None:
    service, _audit = _service()
    draft = await service.create_draft(
        draft_id="draft.brocade-sannav.primary",
        organization_id="organization.atlas.local",
        environment_id="environment.development",
        owner_id="subject.builder-operator.primary",
        vendor="Brocade",
        product="SANnav",
        target_environment="lab",
        notes="Initial source assembly.",
        correlation_id="correlation.test",
    )
    await service.mark_analyzed(
        draft_id=draft.draft_id,
        analyzed_project_id="project.brocade-sannav.primary",
        correlation_id="correlation.test",
    )
    with pytest.raises(BuilderDraftError, match="builder_draft_already_analyzed"):
        await service.mark_analyzed(
            draft_id=draft.draft_id,
            analyzed_project_id="project.brocade-sannav.secondary",
            correlation_id="correlation.test",
        )


@pytest.mark.asyncio
async def test_record_supersession() -> None:
    service, audit_sink = _service()
    supersession = await service.record_supersession(
        supersession_id="supersession.primary",
        superseded_project_id="project.brocade-sannav.v1",
        superseding_project_id="project.brocade-sannav.v2",
        reason="Vendor published a new API version; regenerated against it.",
        recorded_by="subject.builder-operator.primary",
        correlation_id="correlation.test",
    )
    assert supersession.superseded_project_id == "project.brocade-sannav.v1"
    assert any(item.outcome == "recorded" for item in audit_sink.records)


@pytest.mark.asyncio
async def test_record_supersession_refuses_a_second_supersession_of_the_same_project() -> None:
    service, _audit = _service()
    await service.record_supersession(
        supersession_id="supersession.primary",
        superseded_project_id="project.brocade-sannav.v1",
        superseding_project_id="project.brocade-sannav.v2",
        reason="Vendor published a new API version.",
        recorded_by="subject.builder-operator.primary",
        correlation_id="correlation.test",
    )
    with pytest.raises(BuilderDraftError, match="builder_project_already_superseded"):
        await service.record_supersession(
            supersession_id="supersession.secondary",
            superseded_project_id="project.brocade-sannav.v1",
            superseding_project_id="project.brocade-sannav.v3",
            reason="Another attempt.",
            recorded_by="subject.builder-operator.primary",
            correlation_id="correlation.test",
        )


@pytest.mark.asyncio
async def test_record_supersession_rejects_self_supersession() -> None:
    service, _audit = _service()
    with pytest.raises(BuilderDraftError, match="builder_project_supersession_invalid"):
        await service.record_supersession(
            supersession_id="supersession.primary",
            superseded_project_id="project.brocade-sannav.v1",
            superseding_project_id="project.brocade-sannav.v1",
            reason="Self-reference attempt.",
            recorded_by="subject.builder-operator.primary",
            correlation_id="correlation.test",
        )
