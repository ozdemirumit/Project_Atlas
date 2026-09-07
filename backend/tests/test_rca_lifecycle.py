from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.rca.adapters.synthetic import SyntheticStorageRcaAssembler
from atlas.modules.rca.application.service import (
    RcaAccessContext,
    RcaOperationsError,
    RcaService,
)
from atlas.modules.rca.domain.models import (
    RcaCase,
    RcaCaseState,
    RcaCreateRequest,
    ReviewStatus,
    is_valid_rca_case_transition,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
TARGET = "asset.storage.lab.b28"


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


def _context(**overrides: object) -> RcaAccessContext:
    values: dict[str, object] = {
        "subject_id": "subject.development.operator",
        "actor_type": "human",
        "authentication_method": "development",
        "assurance_level": "development",
        "organization_id": "organization.development",
        "environment_id": "environment.test",
        "site_id": "site.local",
        "resource_id": "resource.rca.storage.synthetic",
        "correlation_id": "cor_rca",
        "decision_id": "dec_rca",
        "requested_at": NOW,
    }
    values.update(overrides)
    return RcaAccessContext(**values)  # type: ignore[arg-type]


def _request(**overrides: object) -> RcaCreateRequest:
    values: dict[str, object] = {
        "incident_id": "INC-2026-0042",
        "target_id": TARGET,
        "user_report": "Storage warning appeared during the service window.",
        "expected_behavior": "Storage paths remain healthy and redundant.",
        "actual_behavior": "Controller CTL01 reports a warning.",
        "window_start": NOW - timedelta(hours=24),
        "window_end": NOW,
        "max_evidence_records": 12,
    }
    values.update(overrides)
    return RcaCreateRequest(**values)  # type: ignore[arg-type]


def test_reviewed_state_is_reachable_only_from_provisional_or_inconclusive() -> None:
    assert is_valid_rca_case_transition(RcaCaseState.PROVISIONAL, RcaCaseState.CONFIRMED) is True
    assert is_valid_rca_case_transition(RcaCaseState.CONFIRMED, RcaCaseState.REVIEWED) is True
    assert is_valid_rca_case_transition(RcaCaseState.INCONCLUSIVE, RcaCaseState.REVIEWED) is True
    assert is_valid_rca_case_transition(RcaCaseState.INTAKE, RcaCaseState.REVIEWED) is False


def test_closed_and_cancelled_are_terminal() -> None:
    for target in RcaCaseState:
        assert is_valid_rca_case_transition(RcaCaseState.CLOSED, target) is False
        assert is_valid_rca_case_transition(RcaCaseState.CANCELLED, target) is False


async def _create_case(service: RcaService) -> RcaCase:
    return await service.create(_request(), context=_context())


@pytest.mark.asyncio
async def test_review_transitions_a_provisional_case_to_reviewed() -> None:
    audit_sink = CollectingAuditSink()
    service = RcaService(assembler=SyntheticStorageRcaAssembler(), audit_sink=audit_sink)
    case = await _create_case(service)
    assert case.state is RcaCaseState.PROVISIONAL

    reviewed = await service.review(
        case.case_id,
        version=case.version,
        reviewer_id="subject.domain-expert.primary",
        status=ReviewStatus.ACCEPTED,
        decision_reason="Evidence and hypotheses are sound for the provisional finding.",
        domain_confirmation_criterion=None,
        context=_context(),
    )
    assert reviewed.state is RcaCaseState.REVIEWED
    assert reviewed.human_review.status is ReviewStatus.ACCEPTED
    assert reviewed.human_review.reviewer_id == "subject.domain-expert.primary"
    assert any(item.event_type == "atlas.rca.reviewed" for item in audit_sink.records)


@pytest.mark.asyncio
async def test_review_requires_an_explicit_decision() -> None:
    service = RcaService(assembler=SyntheticStorageRcaAssembler(), audit_sink=CollectingAuditSink())
    case = await _create_case(service)
    with pytest.raises(RcaOperationsError) as exc_info:
        await service.review(
            case.case_id,
            version=case.version,
            reviewer_id="subject.domain-expert.primary",
            status=ReviewStatus.PENDING,
            decision_reason="",
            domain_confirmation_criterion=None,
            context=_context(),
        )
    assert exc_info.value.code == "rca_review_requires_decision"


@pytest.mark.asyncio
async def test_review_cannot_be_repeated_from_reviewed_state() -> None:
    service = RcaService(assembler=SyntheticStorageRcaAssembler(), audit_sink=CollectingAuditSink())
    case = await _create_case(service)
    reviewed = await service.review(
        case.case_id,
        version=case.version,
        reviewer_id="subject.domain-expert.primary",
        status=ReviewStatus.ACCEPTED,
        decision_reason="Sound provisional finding.",
        domain_confirmation_criterion=None,
        context=_context(),
    )
    with pytest.raises(RcaOperationsError) as exc_info:
        await service.review(
            reviewed.case_id,
            version=reviewed.version,
            reviewer_id="subject.domain-expert.primary",
            status=ReviewStatus.ACCEPTED,
            decision_reason="Repeat review attempt.",
            domain_confirmation_criterion=None,
            context=_context(),
        )
    assert exc_info.value.code == "rca_review_invalid_state"


@pytest.mark.asyncio
async def test_close_requires_prior_review() -> None:
    service = RcaService(assembler=SyntheticStorageRcaAssembler(), audit_sink=CollectingAuditSink())
    case = await _create_case(service)
    with pytest.raises(RcaOperationsError) as exc_info:
        await service.close(case.case_id, version=case.version, context=_context())
    assert exc_info.value.code == "rca_close_invalid_state"


@pytest.mark.asyncio
async def test_review_then_close() -> None:
    audit_sink = CollectingAuditSink()
    service = RcaService(assembler=SyntheticStorageRcaAssembler(), audit_sink=audit_sink)
    case = await _create_case(service)
    reviewed = await service.review(
        case.case_id,
        version=case.version,
        reviewer_id="subject.domain-expert.primary",
        status=ReviewStatus.ACCEPTED,
        decision_reason="Sound provisional finding.",
        domain_confirmation_criterion=None,
        context=_context(),
    )
    closed = await service.close(reviewed.case_id, version=reviewed.version, context=_context())
    assert closed.state is RcaCaseState.CLOSED
    assert any(item.event_type == "atlas.rca.closed" for item in audit_sink.records)


@pytest.mark.asyncio
async def test_review_requires_an_existing_case() -> None:
    service = RcaService(assembler=SyntheticStorageRcaAssembler(), audit_sink=CollectingAuditSink())
    with pytest.raises(RcaOperationsError) as exc_info:
        await service.review(
            "case.no-such-one",
            version=1,
            reviewer_id="subject.domain-expert.primary",
            status=ReviewStatus.ACCEPTED,
            decision_reason="N/A",
            domain_confirmation_criterion=None,
            context=_context(),
        )
    assert exc_info.value.code == "rca_case_unavailable"
