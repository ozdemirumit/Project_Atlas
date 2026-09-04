from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.classification import DataClassification
from atlas.modules.decision_engine.domain.models import DecisionRequest, EvidencePackage
from atlas.modules.reasoning.domain.models import EvidenceUnit

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def request(**overrides: object) -> DecisionRequest:
    defaults: dict[str, object] = {
        "request_id": "decision-request.example",
        "workflow_id": "workflow.example",
        "requesting_identity": "subject.requester",
        "authorized_scope_reference": "authorization.example",
        "decision_type": "root_cause_diagnosis",
        "question": "Why did controller B degrade?",
        "target_ids": ("target.example",),
        "service_ids": ("service.file-shares",),
        "environment_id": "environment.production",
        "time_window_start": NOW - timedelta(hours=2),
        "time_window_end": NOW,
        "required_evidence_domains": ("health_check",),
        "required_output_schema": "decision-record.v1",
        "deadline": NOW + timedelta(hours=1),
        "required_freshness_seconds": 300,
        "applicable_domain": "storage",
        "applicable_product_versions": ("6.1.x",),
    }
    defaults.update(overrides)
    return DecisionRequest(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_request_constructs_cleanly() -> None:
    example = request()
    assert example.decision_type == "root_cause_diagnosis"


def test_rejects_blank_requesting_identity() -> None:
    with pytest.raises(ValueError, match="requesting identity"):
        request(requesting_identity="   ")


def test_rejects_blank_question() -> None:
    with pytest.raises(ValueError, match="question"):
        request(question="   ")


def test_rejects_no_targets() -> None:
    with pytest.raises(ValueError, match="at least one target"):
        request(target_ids=())


def test_rejects_naive_time_window() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        request(time_window_start=NOW.replace(tzinfo=None))


def test_rejects_time_window_end_before_start() -> None:
    with pytest.raises(ValueError, match="must not precede"):
        request(time_window_start=NOW, time_window_end=NOW - timedelta(hours=1))


def test_workflow_id_may_be_none() -> None:
    example = request(workflow_id=None)
    assert example.workflow_id is None


def test_rejects_naive_deadline() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        request(deadline=NOW.replace(tzinfo=None))


def test_deadline_may_be_none() -> None:
    example = request(deadline=None)
    assert example.deadline is None


def test_rejects_non_positive_required_freshness() -> None:
    with pytest.raises(ValueError, match="positive"):
        request(required_freshness_seconds=0)


def evidence_unit(**overrides: object) -> EvidenceUnit:
    defaults: dict[str, object] = {
        "evidence_id": "evidence.example",
        "artifact_version": "1",
        "source_type": "health_check",
        "source_system": "storage.health-check.example",
        "owner": None,
        "authority_class": "connector_observation",
        "collected_at": NOW,
        "applicable_from": NOW,
        "applicable_to": None,
        "target_id": "target.example",
        "environment_id": "environment.production",
        "site_id": "site.example",
        "classification": DataClassification.INTERNAL,
        "authorization_reference": "authorization.example",
        "observation_or_retrieval_method": "Polled via storage health-check connector.",
        "normalized_content": "Controller B reports a degraded status.",
        "integrity_confirmed": True,
        "completeness_confirmed": True,
        "is_fresh": True,
        "conflicts_with_evidence_ids": (),
        "superseded_by_evidence_id": None,
        "citation_reference": "evidence://storage.health-check.example/evidence.example",
    }
    defaults.update(overrides)
    return EvidenceUnit(**defaults)  # type: ignore[arg-type]


def package(**overrides: object) -> EvidencePackage:
    defaults: dict[str, object] = {
        "package_id": "decision-evidence-package.example",
        "request_id": "decision-request.example",
        "items": (evidence_unit(),),
        "created_at": NOW,
    }
    defaults.update(overrides)
    return EvidencePackage(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_package_constructs_cleanly() -> None:
    example = package()
    assert len(example.items) == 1


def test_package_requires_at_least_one_item() -> None:
    with pytest.raises(ValueError, match="at least one evidence unit"):
        package(items=())


def test_package_rejects_naive_created_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        package(created_at=NOW.replace(tzinfo=None))


def test_package_is_frozen() -> None:
    example = package()
    with pytest.raises(AttributeError):
        example.items = ()  # type: ignore[misc]
