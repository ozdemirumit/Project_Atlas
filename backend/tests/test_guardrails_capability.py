from __future__ import annotations

import pytest

from atlas.core.capabilities import CapabilityClass
from atlas.modules.guardrails.domain.capability_guardrails import (
    is_direct_invocation_permitted,
    is_proposal_permitted,
    posture_for,
)


def test_every_capability_class_has_a_posture() -> None:
    for capability_class in CapabilityClass:
        assert posture_for(capability_class) is not None


def test_none_resolves_to_no_posture() -> None:
    assert posture_for(None) is None


@pytest.mark.parametrize(
    "capability_class",
    [
        CapabilityClass.C0_INFORMATIONAL,
        CapabilityClass.C1_READ_ONLY,
        CapabilityClass.C2_DIAGNOSTIC,
        CapabilityClass.C3_CONTROLLED_CHANGE,
        CapabilityClass.C4_SERVICE_IMPACTING,
    ],
)
def test_c0_through_c4_may_be_proposed(capability_class: CapabilityClass) -> None:
    assert is_proposal_permitted(capability_class) is True


def test_c5_may_never_be_proposed() -> None:
    assert is_proposal_permitted(CapabilityClass.C5_DESTRUCTIVE) is False


def test_an_unrecognized_or_missing_class_may_never_be_proposed() -> None:
    assert is_proposal_permitted(None) is False


@pytest.mark.parametrize(
    "capability_class", [CapabilityClass.C0_INFORMATIONAL, CapabilityClass.C1_READ_ONLY]
)
def test_c0_and_c1_may_be_directly_invoked_by_atlas(capability_class: CapabilityClass) -> None:
    assert is_direct_invocation_permitted(capability_class) is True


@pytest.mark.parametrize(
    "capability_class",
    [
        CapabilityClass.C2_DIAGNOSTIC,
        CapabilityClass.C3_CONTROLLED_CHANGE,
        CapabilityClass.C4_SERVICE_IMPACTING,
        CapabilityClass.C5_DESTRUCTIVE,
    ],
)
def test_c2_through_c5_may_never_be_directly_invoked_by_atlas(
    capability_class: CapabilityClass,
) -> None:
    assert is_direct_invocation_permitted(capability_class) is False


def test_posture_descriptions_are_never_empty() -> None:
    for capability_class in CapabilityClass:
        posture = posture_for(capability_class)
        assert posture is not None
        assert posture.description.strip()
