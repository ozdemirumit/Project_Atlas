from __future__ import annotations

import pytest

from atlas.modules.change_impact.domain.validation_freshness import (
    RecalculationEvent,
    RecalculationTrigger,
    ValidationCheck,
    ValidationCheckKind,
    ValidationReport,
)


def check(**overrides: object) -> ValidationCheck:
    defaults: dict[str, object] = {
        "kind": ValidationCheckKind.EVERY_TARGET_RESOLVES_TO_CURRENT_AUTHORIZED_INVENTORY,
        "passed": True,
        "detail": "target.controller-b resolves to a current inventory record.",
    }
    defaults.update(overrides)
    return ValidationCheck(**defaults)  # type: ignore[arg-type]


def report(**overrides: object) -> ValidationReport:
    defaults: dict[str, object] = {
        "impact_result_id": "impact-result.example",
        "checks": (check(),),
        "is_consequential": False,
        "domain_owner_reviewed": False,
        "service_owner_reviewed": False,
    }
    defaults.update(overrides)
    return ValidationReport(**defaults)  # type: ignore[arg-type]


def test_validation_check_requires_detail() -> None:
    with pytest.raises(ValueError, match="requires a detail"):
        check(detail="")


def test_validation_report_requires_at_least_one_check() -> None:
    with pytest.raises(ValueError, match="at least one check"):
        report(checks=())


def test_validation_report_rejects_duplicate_check_kind() -> None:
    with pytest.raises(ValueError, match="must not repeat a check kind"):
        report(checks=(check(), check()))


def test_all_checks_passed_false_when_one_fails() -> None:
    failing = check(passed=False)
    assert report(checks=(failing,)).all_checks_passed is False


def test_non_consequential_analysis_ready_without_owner_review() -> None:
    assert report(is_consequential=False).is_ready_for_formal_approval is True


def test_consequential_analysis_not_ready_without_owner_review() -> None:
    result = report(is_consequential=True, domain_owner_reviewed=False)
    assert result.is_ready_for_formal_approval is False


def test_consequential_analysis_ready_after_both_reviews() -> None:
    result = report(is_consequential=True, domain_owner_reviewed=True, service_owner_reviewed=True)
    assert result.is_ready_for_formal_approval is True


def test_not_ready_when_checks_fail_even_if_reviewed() -> None:
    failing = check(passed=False)
    result = report(
        checks=(failing,),
        is_consequential=True,
        domain_owner_reviewed=True,
        service_owner_reviewed=True,
    )
    assert result.is_ready_for_formal_approval is False


def test_recalculation_event_requires_changed_section_notes() -> None:
    with pytest.raises(ValueError, match="which sections changed and why"):
        RecalculationEvent(
            impact_result_id="impact-result.example",
            trigger=RecalculationTrigger.EVIDENCE_EXCEEDS_RISK_BASED_FRESHNESS_LIMIT,
            detail="Health telemetry is 20 minutes older than the required freshness.",
            changed_section_notes=(),
            is_invalidation=False,
        )


def test_recalculation_event_accepts_valid_state() -> None:
    event = RecalculationEvent(
        impact_result_id="impact-result.example",
        trigger=RecalculationTrigger.TOPOLOGY_HEALTH_CAPACITY_REDUNDANCY_PROTECTION_OR_SERVICE_MAPPING_CHANGE,
        detail="Controller A's health status changed since the snapshot was generated.",
        changed_section_notes=("Redundancy analysis now reflects a degraded controller A.",),
        is_invalidation=True,
    )
    assert event.is_invalidation is True
