from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.classification import DataClassification
from atlas.modules.reasoning.domain.models import EpistemicType, EvidenceUnit

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def evidence(**overrides: object) -> EvidenceUnit:
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


def test_epistemic_type_has_nine_members() -> None:
    assert len(EpistemicType) == 9


def test_a_well_formed_evidence_unit_constructs_cleanly() -> None:
    example = evidence()
    assert example.classification is DataClassification.INTERNAL


def test_rejects_blank_artifact_version() -> None:
    with pytest.raises(ValueError, match="artifact version"):
        evidence(artifact_version="   ")


def test_rejects_blank_source_type() -> None:
    with pytest.raises(ValueError, match="source type"):
        evidence(source_type="   ")


def test_rejects_naive_collected_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        evidence(collected_at=NOW.replace(tzinfo=None))


def test_rejects_naive_applicable_from() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        evidence(applicable_from=NOW.replace(tzinfo=None))


def test_rejects_naive_applicable_to() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        evidence(applicable_to=NOW.replace(tzinfo=None))


def test_rejects_applicable_to_before_applicable_from() -> None:
    with pytest.raises(ValueError, match="must not precede"):
        evidence(applicable_from=NOW, applicable_to=NOW - timedelta(hours=1))


def test_applicable_to_may_be_none() -> None:
    example = evidence(applicable_to=None)
    assert example.applicable_to is None


def test_rejects_blank_authorization_reference() -> None:
    with pytest.raises(ValueError, match="authorization reference"):
        evidence(authorization_reference="   ")


def test_rejects_blank_normalized_content() -> None:
    with pytest.raises(ValueError, match="normalized content"):
        evidence(normalized_content="   ")


def test_rejects_blank_citation_reference() -> None:
    with pytest.raises(ValueError, match="citation reference"):
        evidence(citation_reference="   ")


def test_can_support_consequential_claim_when_integrity_and_completeness_confirmed() -> None:
    example = evidence(integrity_confirmed=True, completeness_confirmed=True)
    assert example.can_support_a_consequential_claim is True


def test_cannot_support_consequential_claim_when_integrity_not_confirmed() -> None:
    example = evidence(integrity_confirmed=False, completeness_confirmed=True)
    assert example.can_support_a_consequential_claim is False


def test_cannot_support_consequential_claim_when_completeness_not_confirmed() -> None:
    example = evidence(integrity_confirmed=True, completeness_confirmed=False)
    assert example.can_support_a_consequential_claim is False
