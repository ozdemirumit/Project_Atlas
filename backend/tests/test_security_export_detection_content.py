from __future__ import annotations

import pytest

from atlas.modules.security_export.domain.detection_content import (
    DetectionContentContract,
    DetectionTestFixture,
    DetectionTestFixtureKind,
    DetectionUseCaseId,
    generated_detection_logic_is_trusted_without_review,
)
from atlas.modules.security_export.domain.models import SecuritySeverity


def _fixture(kind: DetectionTestFixtureKind) -> DetectionTestFixture:
    return DetectionTestFixture(
        kind=kind,
        description=f"{kind.value} fixture",
        expected_outcome="documented outcome",
    )


def _all_fixtures() -> tuple[DetectionTestFixture, ...]:
    return tuple(_fixture(kind) for kind in DetectionTestFixtureKind)


def _build(**overrides: object) -> DetectionContentContract:
    defaults: dict[str, object] = {
        "detection_id": DetectionUseCaseId.SIEM_UC_001,
        "version": "1.0.0",
        "name": "Repeated Authentication Failure",
        "purpose": "Detect brute-force or credential-stuffing attempts.",
        "threat_or_compliance_hypothesis": "Repeated failures indicate a credential attack.",
        "limitations": "Rate limits and provider outages can mimic this pattern.",
        "required_event_types": ("atlas.authentication.failed",),
        "required_fields": ("subject_reference", "source"),
        "query_logic_summary": "Count failures per subject reference within the time window.",
        "time_window": "15 minutes",
        "thresholds": "5 failures",
        "grouping": "by subject reference and source",
        "suppression_behavior": "suppress duplicate alerts for the same window",
        "expected_false_positives": "shared NAT or forgotten credentials",
        "tuning_guidance": "raise the threshold for high-traffic shared sources",
        "severity": SecuritySeverity.MEDIUM,
        "escalation_recommendation": "triage within one business day",
        "investigation_steps": ("review the correlation chain",),
        "evidence_link_kinds": ("audit_ledger_reference",),
        "test_fixtures": _all_fixtures(),
        "owner": "security-operations-integration-owner",
        "review_interval_days": 180,
        "supported_schema_versions": ("atlas-security-event.v1",),
        "change_history": ("1.0.0: initial specification",),
    }
    defaults.update(overrides)
    return DetectionContentContract(**defaults)  # type: ignore[arg-type]


def test_generated_detection_logic_is_never_trusted_without_review() -> None:
    assert generated_detection_logic_is_trusted_without_review() is False


def test_detection_use_case_has_ten_members() -> None:
    assert len(DetectionUseCaseId) == 10


def test_detection_test_fixture_kind_has_five_members() -> None:
    assert len(DetectionTestFixtureKind) == 5


def test_detection_test_fixture_requires_description_and_outcome() -> None:
    with pytest.raises(ValueError, match="description and an outcome"):
        DetectionTestFixture(
            kind=DetectionTestFixtureKind.POSITIVE,
            description="",
            expected_outcome="triggers",
        )


def test_valid_contract_builds() -> None:
    contract = _build()
    assert contract.detection_id is DetectionUseCaseId.SIEM_UC_001
    assert len(contract.test_fixtures) == 5


@pytest.mark.parametrize(
    "field",
    [
        "version",
        "name",
        "purpose",
        "threat_or_compliance_hypothesis",
        "limitations",
        "query_logic_summary",
        "time_window",
        "thresholds",
        "grouping",
        "suppression_behavior",
        "expected_false_positives",
        "tuning_guidance",
        "escalation_recommendation",
        "owner",
    ],
)
def test_contract_requires_every_narrative_field(field: str) -> None:
    with pytest.raises(ValueError, match="every narrative field"):
        _build(**{field: "  "})


@pytest.mark.parametrize(
    "field",
    [
        "required_event_types",
        "required_fields",
        "investigation_steps",
        "evidence_link_kinds",
        "supported_schema_versions",
        "change_history",
    ],
)
def test_contract_requires_every_declared_group(field: str) -> None:
    with pytest.raises(ValueError, match="every declared group"):
        _build(**{field: ()})


def test_contract_requires_positive_review_interval() -> None:
    with pytest.raises(ValueError, match="positive review interval"):
        _build(review_interval_days=0)


def test_contract_requires_all_five_fixture_kinds() -> None:
    with pytest.raises(ValueError, match="all five test fixture kinds"):
        _build(test_fixtures=(_fixture(DetectionTestFixtureKind.POSITIVE),))
