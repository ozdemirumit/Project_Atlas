from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.runbook_engine.domain.preconditions import (
    PreconditionCategory,
    PreconditionFailureBehavior,
    RunbookPrecondition,
    is_precondition_evidence_fresh,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def precondition(**overrides: object) -> RunbookPrecondition:
    defaults: dict[str, object] = {
        "precondition_id": "runbook-precondition.example",
        "category": PreconditionCategory.HEALTH_AND_PROTECTION_STATE,
        "description": "The redundant storage path reports healthy.",
        "verification_method": "Query the storage array's path health API.",
        "freshness_limit_seconds": 300,
        "failure_behavior": PreconditionFailureBehavior.BLOCKS,
        "alternative_procedure_reference": None,
    }
    defaults.update(overrides)
    return RunbookPrecondition(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_precondition_constructs_cleanly() -> None:
    example = precondition()
    assert example.failure_behavior is PreconditionFailureBehavior.BLOCKS


def test_rejects_blank_description() -> None:
    with pytest.raises(ValueError, match="description"):
        precondition(description="   ")


def test_rejects_blank_verification_method() -> None:
    with pytest.raises(ValueError, match="verifiable"):
        precondition(verification_method="   ")


def test_rejects_non_positive_freshness_limit() -> None:
    with pytest.raises(ValueError, match="positive freshness limit"):
        precondition(freshness_limit_seconds=0)


def test_routes_to_alternative_requires_a_reference() -> None:
    with pytest.raises(ValueError, match="requires alternative_procedure_reference"):
        precondition(
            failure_behavior=PreconditionFailureBehavior.ROUTES_TO_ALTERNATIVE,
            alternative_procedure_reference=None,
        )


def test_routes_to_alternative_constructs_with_a_reference() -> None:
    example = precondition(
        failure_behavior=PreconditionFailureBehavior.ROUTES_TO_ALTERNATIVE,
        alternative_procedure_reference="runbook.alternative-example",
    )
    assert example.alternative_procedure_reference == "runbook.alternative-example"


def test_non_alternative_failure_behavior_cannot_carry_a_reference() -> None:
    with pytest.raises(ValueError, match="only meaningful"):
        precondition(
            failure_behavior=PreconditionFailureBehavior.WARNS,
            alternative_procedure_reference="runbook.alternative-example",
        )


def test_evidence_within_the_freshness_limit_is_fresh() -> None:
    assert (
        is_precondition_evidence_fresh(
            verified_at=NOW - timedelta(seconds=60), freshness_limit_seconds=300, now=NOW
        )
        is True
    )


def test_evidence_beyond_the_freshness_limit_is_not_fresh() -> None:
    assert (
        is_precondition_evidence_fresh(
            verified_at=NOW - timedelta(seconds=600), freshness_limit_seconds=300, now=NOW
        )
        is False
    )


def test_evidence_exactly_at_the_limit_is_fresh() -> None:
    assert (
        is_precondition_evidence_fresh(
            verified_at=NOW - timedelta(seconds=300), freshness_limit_seconds=300, now=NOW
        )
        is True
    )


def test_freshness_check_rejects_naive_datetimes() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        is_precondition_evidence_fresh(
            verified_at=NOW.replace(tzinfo=None), freshness_limit_seconds=300, now=NOW
        )
