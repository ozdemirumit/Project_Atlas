from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.runbook_engine.domain.dry_run import (
    DryRunCheck,
    DryRunCheckKind,
    DryRunCheckResult,
    DryRunReport,
    SimulationMaturityLevel,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def check(**overrides: object) -> DryRunCheck:
    defaults: dict[str, object] = {
        "kind": DryRunCheckKind.TARGET_RESOLUTION_AND_SCOPE,
        "result": DryRunCheckResult.PASSED,
        "detail": "Target resolved to a single storage controller within authorized scope.",
    }
    defaults.update(overrides)
    return DryRunCheck(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_check_constructs_cleanly() -> None:
    example = check()
    assert example.result is DryRunCheckResult.PASSED


def test_check_requires_a_detail_statement() -> None:
    with pytest.raises(ValueError, match="detail"):
        check(detail="   ")


def report(**overrides: object) -> DryRunReport:
    defaults: dict[str, object] = {
        "report_id": "runbook-dry-run.example",
        "plan_id": "runbook-plan.example",
        "checks": (check(),),
        "maturity_level": SimulationMaturityLevel.STRUCTURAL_ONLY,
        "performed_at": NOW,
    }
    defaults.update(overrides)
    return DryRunReport(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_report_constructs_cleanly() -> None:
    example = report()
    assert example.maturity_level is SimulationMaturityLevel.STRUCTURAL_ONLY


def test_report_requires_at_least_one_check() -> None:
    with pytest.raises(ValueError, match="at least one check"):
        report(checks=())


def test_report_rejects_duplicate_check_kinds() -> None:
    duplicated = (check(), check(result=DryRunCheckResult.FAILED))
    with pytest.raises(ValueError, match="cannot evaluate the same check kind twice"):
        report(checks=duplicated)


def test_report_rejects_naive_performed_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        report(performed_at=NOW.replace(tzinfo=None))


def test_report_never_claims_to_change_infrastructure() -> None:
    example = report()
    assert example.is_infrastructure_changing is False


def test_all_checks_passed_true_when_every_check_passes() -> None:
    checks = (
        check(kind=DryRunCheckKind.TARGET_RESOLUTION_AND_SCOPE, result=DryRunCheckResult.PASSED),
        check(
            kind=DryRunCheckKind.PARAMETER_TYPES_AND_REQUIRED_VALUES,
            result=DryRunCheckResult.PASSED,
        ),
    )
    assert report(checks=checks).all_checks_passed is True


def test_all_checks_passed_false_when_any_check_fails() -> None:
    checks = (
        check(kind=DryRunCheckKind.TARGET_RESOLUTION_AND_SCOPE, result=DryRunCheckResult.PASSED),
        check(
            kind=DryRunCheckKind.PARAMETER_TYPES_AND_REQUIRED_VALUES,
            result=DryRunCheckResult.FAILED,
        ),
    )
    assert report(checks=checks).all_checks_passed is False


def test_all_checks_passed_false_when_a_check_is_unavailable() -> None:
    checks = (
        check(
            kind=DryRunCheckKind.PRECONDITION_QUERY_AVAILABILITY,
            result=DryRunCheckResult.UNAVAILABLE,
        ),
    )
    assert report(checks=checks).all_checks_passed is False
