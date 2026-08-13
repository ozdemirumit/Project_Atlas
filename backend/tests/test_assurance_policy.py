from __future__ import annotations

import pytest

from atlas.modules.identity.domain.models import AssuranceLevel, assurance_satisfies_policy


@pytest.mark.parametrize(
    ("actual", "required", "expected"),
    [
        (AssuranceLevel.DEVELOPMENT, AssuranceLevel.SINGLE_FACTOR, True),
        (AssuranceLevel.SINGLE_FACTOR, AssuranceLevel.SINGLE_FACTOR, True),
        (AssuranceLevel.MULTI_FACTOR, AssuranceLevel.SINGLE_FACTOR, True),
        (AssuranceLevel.HARDWARE_BACKED, AssuranceLevel.SINGLE_FACTOR, True),
        (AssuranceLevel.DEVELOPMENT, AssuranceLevel.MULTI_FACTOR, False),
        (AssuranceLevel.SINGLE_FACTOR, AssuranceLevel.MULTI_FACTOR, False),
        (AssuranceLevel.MULTI_FACTOR, AssuranceLevel.MULTI_FACTOR, True),
        (AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED, False),
        (AssuranceLevel.HARDWARE_BACKED, AssuranceLevel.HARDWARE_BACKED, True),
    ],
)
def test_assurance_satisfies_only_an_explicit_policy_requirement(
    actual: AssuranceLevel,
    required: AssuranceLevel,
    expected: bool,
) -> None:
    assert assurance_satisfies_policy(actual, required) is expected
