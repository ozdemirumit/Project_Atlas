from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.health_checks.domain.models import FreshnessState
from atlas.modules.policy_engine.domain.evidence import (
    EvidenceKind,
    EvidenceReference,
    EvidenceRequirement,
    validate_evidence_conditions,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def reference(
    *,
    kind: EvidenceKind = EvidenceKind.TARGET_HEALTH,
    reference: str = "evidence.example",
    observed_at: datetime = NOW,
    freshness: FreshnessState = FreshnessState.CURRENT,
    satisfied: bool = True,
) -> EvidenceReference:
    return EvidenceReference(
        reference=reference,
        kind=kind,
        observed_at=observed_at,
        freshness=freshness,
        satisfied=satisfied,
    )


def requirement(
    *, kind: EvidenceKind = EvidenceKind.TARGET_HEALTH, maximum_age_seconds: int = 300
) -> EvidenceRequirement:
    return EvidenceRequirement(kind=kind, maximum_age_seconds=maximum_age_seconds)


def test_no_requirements_are_trivially_satisfied() -> None:
    result = validate_evidence_conditions((), (), now=NOW)
    assert result.satisfied is True
    assert result.unmet_requirements == ()


def test_a_fresh_satisfied_reference_meets_its_requirement() -> None:
    result = validate_evidence_conditions((requirement(),), (reference(),), now=NOW)
    assert result.satisfied is True
    assert result.unmet_requirements == ()


def test_a_missing_reference_is_unmet() -> None:
    result = validate_evidence_conditions((requirement(),), (), now=NOW)
    assert result.satisfied is False
    assert result.unmet_requirements == (EvidenceKind.TARGET_HEALTH,)


def test_an_unsatisfied_reference_is_unmet_even_if_present_and_fresh() -> None:
    result = validate_evidence_conditions((requirement(),), (reference(satisfied=False),), now=NOW)
    assert result.satisfied is False
    assert result.unmet_requirements == (EvidenceKind.TARGET_HEALTH,)


def test_a_reference_older_than_its_requirements_maximum_age_is_unmet_and_stale() -> None:
    old_reference = reference(observed_at=NOW - timedelta(seconds=301))
    result = validate_evidence_conditions(
        (requirement(maximum_age_seconds=300),), (old_reference,), now=NOW
    )
    assert result.satisfied is False
    assert result.unmet_requirements == (EvidenceKind.TARGET_HEALTH,)
    assert result.stale_references == ("evidence.example",)


def test_a_reference_within_its_maximum_age_is_met() -> None:
    recent_reference = reference(observed_at=NOW - timedelta(seconds=299))
    result = validate_evidence_conditions(
        (requirement(maximum_age_seconds=300),), (recent_reference,), now=NOW
    )
    assert result.satisfied is True


@pytest.mark.parametrize("freshness", [FreshnessState.STALE, FreshnessState.UNKNOWN])
def test_a_stale_or_unknown_freshness_reference_is_unmet_regardless_of_age(
    freshness: FreshnessState,
) -> None:
    result = validate_evidence_conditions(
        (requirement(),), (reference(freshness=freshness),), now=NOW
    )
    assert result.satisfied is False


@pytest.mark.parametrize("freshness", [FreshnessState.CURRENT, FreshnessState.AGING])
def test_current_or_aging_freshness_does_not_block_by_itself(
    freshness: FreshnessState,
) -> None:
    result = validate_evidence_conditions(
        (requirement(),), (reference(freshness=freshness),), now=NOW
    )
    assert result.satisfied is True


def test_a_reference_observed_in_the_future_is_unmet() -> None:
    future_reference = reference(observed_at=NOW + timedelta(seconds=1))
    result = validate_evidence_conditions((requirement(),), (future_reference,), now=NOW)
    assert result.satisfied is False


def test_only_the_most_recent_reference_of_a_kind_is_considered() -> None:
    stale_older = reference(reference="evidence.older", observed_at=NOW - timedelta(hours=1))
    fresh_newer = reference(reference="evidence.newer", observed_at=NOW, satisfied=False)
    result = validate_evidence_conditions((requirement(),), (stale_older, fresh_newer), now=NOW)
    # The newer, unsatisfied reference wins over the older, satisfied one -- an old satisfied
    # claim cannot paper over the fact that the current one reports unsatisfied.
    assert result.satisfied is False


def test_multiple_requirements_are_all_independently_checked() -> None:
    result = validate_evidence_conditions(
        (
            requirement(kind=EvidenceKind.TARGET_HEALTH),
            requirement(kind=EvidenceKind.ROLLBACK_OR_RECOVERY_PLAN),
        ),
        (reference(kind=EvidenceKind.TARGET_HEALTH),),
        now=NOW,
    )
    assert result.satisfied is False
    assert result.unmet_requirements == (EvidenceKind.ROLLBACK_OR_RECOVERY_PLAN,)


def test_requirement_rejects_a_non_positive_maximum_age() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        EvidenceRequirement(kind=EvidenceKind.TARGET_HEALTH, maximum_age_seconds=0)


def test_reference_rejects_a_blank_reference_string() -> None:
    with pytest.raises(ValueError, match="non-empty reference"):
        reference(reference="   ")


def test_reference_rejects_a_naive_observed_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        EvidenceReference(
            reference="evidence.example",
            kind=EvidenceKind.TARGET_HEALTH,
            observed_at=datetime(2026, 9, 4, 12, 0),
            freshness=FreshnessState.CURRENT,
            satisfied=True,
        )
