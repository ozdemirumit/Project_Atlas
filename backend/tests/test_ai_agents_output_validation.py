from __future__ import annotations

import pytest

from atlas.modules.ai_agents.domain.output_validation import (
    OutputValidationCheck,
    OutputValidationCheckKind,
    OutputValidationResult,
    ValidationDisposition,
)


def check(**overrides: object) -> OutputValidationCheck:
    defaults: dict[str, object] = {
        "kind": OutputValidationCheckKind.SCHEMA_AND_ENUM_VALIDATION,
        "passed": True,
        "detail": "Output matches root-cause-output.v1 schema.",
    }
    defaults.update(overrides)
    return OutputValidationCheck(**defaults)  # type: ignore[arg-type]


def result(**overrides: object) -> OutputValidationResult:
    defaults: dict[str, object] = {
        "envelope_id": "output-envelope.example",
        "checks": (check(),),
        "disposition": ValidationDisposition.ACCEPT,
        "repair_attempt_count": 0,
        "max_repair_attempts": 2,
    }
    defaults.update(overrides)
    return OutputValidationResult(**defaults)  # type: ignore[arg-type]


def test_check_requires_detail() -> None:
    with pytest.raises(ValueError, match="requires a detail"):
        check(detail="")


def test_result_requires_at_least_one_check() -> None:
    with pytest.raises(ValueError, match="at least one check"):
        result(checks=())


def test_result_rejects_duplicate_check_kind() -> None:
    with pytest.raises(ValueError, match="must not repeat a check kind"):
        result(checks=(check(), check()))


def test_result_rejects_repair_attempts_exceeding_maximum() -> None:
    with pytest.raises(ValueError, match="repeated repair is bounded"):
        result(repair_attempt_count=3, max_repair_attempts=2)


def test_result_rejects_accept_with_a_failing_check() -> None:
    failing = check(passed=False)
    with pytest.raises(ValueError, match="cannot be ACCEPT"):
        result(checks=(failing,), disposition=ValidationDisposition.ACCEPT)


def test_result_allows_reject_with_a_failing_check() -> None:
    failing = check(passed=False)
    outcome = result(checks=(failing,), disposition=ValidationDisposition.REJECT)
    assert outcome.all_checks_passed is False


def test_all_checks_passed_true_for_valid_result() -> None:
    assert result().all_checks_passed is True
