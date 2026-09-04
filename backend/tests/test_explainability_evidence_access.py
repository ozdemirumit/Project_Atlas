from __future__ import annotations

import pytest

from atlas.modules.explainability.domain.evidence_access import (
    EvidenceAccessGrant,
    EvidenceInspectionLevel,
    contains_prohibited_content,
    filter_authorized_evidence,
    is_inspection_permitted,
)


def grant(**overrides: object) -> EvidenceAccessGrant:
    defaults: dict[str, object] = {
        "evidence_reference": "evidence.example",
        "organization_id": "organization.example",
        "environment_id": "environment.production",
        "maximum_permitted_level": EvidenceInspectionLevel.CONTEXT,
        "original_artifact_permitted": False,
    }
    defaults.update(overrides)
    return EvidenceAccessGrant(**defaults)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "requested_level",
    [
        EvidenceInspectionLevel.LABEL,
        EvidenceInspectionLevel.EXCERPT,
        EvidenceInspectionLevel.CONTEXT,
    ],
)
def test_levels_at_or_below_the_grant_maximum_are_permitted(
    requested_level: EvidenceInspectionLevel,
) -> None:
    assert is_inspection_permitted(requested_level=requested_level, grant=grant()) is True


def test_a_level_above_the_grant_maximum_is_not_permitted() -> None:
    example = grant(maximum_permitted_level=EvidenceInspectionLevel.EXCERPT)
    assert (
        is_inspection_permitted(requested_level=EvidenceInspectionLevel.CONTEXT, grant=example)
        is False
    )


def test_original_artifact_requires_its_own_explicit_flag_even_at_the_top_level() -> None:
    example = grant(
        maximum_permitted_level=EvidenceInspectionLevel.RELATED_EVIDENCE,
        original_artifact_permitted=False,
    )
    assert (
        is_inspection_permitted(
            requested_level=EvidenceInspectionLevel.ORIGINAL_ARTIFACT, grant=example
        )
        is False
    )


def test_original_artifact_is_permitted_when_explicitly_granted() -> None:
    example = grant(
        maximum_permitted_level=EvidenceInspectionLevel.RELATED_EVIDENCE,
        original_artifact_permitted=True,
    )
    assert (
        is_inspection_permitted(
            requested_level=EvidenceInspectionLevel.ORIGINAL_ARTIFACT, grant=example
        )
        is True
    )


def test_related_evidence_above_a_lower_maximum_is_not_permitted() -> None:
    example = grant(maximum_permitted_level=EvidenceInspectionLevel.LABEL)
    assert (
        is_inspection_permitted(
            requested_level=EvidenceInspectionLevel.RELATED_EVIDENCE, grant=example
        )
        is False
    )


def test_grant_rejects_a_blank_reference() -> None:
    with pytest.raises(ValueError, match="reference"):
        grant(evidence_reference="   ")


def test_filter_returns_only_references_with_a_matching_grant() -> None:
    grants = {"evidence.a": grant(evidence_reference="evidence.a")}
    filtered = filter_authorized_evidence(
        ("evidence.a", "evidence.b"),
        grants=grants,
        requesting_organization_id="organization.example",
        requesting_environment_id="environment.production",
    )
    assert filtered == ("evidence.a",)


def test_filter_excludes_a_grant_for_a_different_organization() -> None:
    grants = {
        "evidence.a": grant(evidence_reference="evidence.a", organization_id="organization.other")
    }
    filtered = filter_authorized_evidence(
        ("evidence.a",),
        grants=grants,
        requesting_organization_id="organization.example",
        requesting_environment_id="environment.production",
    )
    assert filtered == ()


def test_filter_excludes_a_grant_for_a_different_environment() -> None:
    grants = {
        "evidence.a": grant(evidence_reference="evidence.a", environment_id="environment.staging")
    }
    filtered = filter_authorized_evidence(
        ("evidence.a",),
        grants=grants,
        requesting_organization_id="organization.example",
        requesting_environment_id="environment.production",
    )
    assert filtered == ()


def test_filter_preserves_no_hidden_reference_count_beyond_what_is_returned() -> None:
    # No grant at all for evidence.b -- it is simply absent from the result, not surfaced as an
    # error or count that would reveal something restricted exists.
    grants = {"evidence.a": grant(evidence_reference="evidence.a")}
    filtered = filter_authorized_evidence(
        ("evidence.a", "evidence.b", "evidence.c"),
        grants=grants,
        requesting_organization_id="organization.example",
        requesting_environment_id="environment.production",
    )
    assert filtered == ("evidence.a",)


def test_prohibited_content_is_detected() -> None:
    assert contains_prohibited_content("here is my key AKIAIOSFODNN7EXAMPLE") is True


def test_ordinary_content_is_not_prohibited() -> None:
    assert contains_prohibited_content("The controller reports a degraded status.") is False
