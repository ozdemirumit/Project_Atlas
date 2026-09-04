from __future__ import annotations

import pytest

from atlas.modules.guardrails.domain.retrieval_guardrails import (
    Citation,
    RetrievalLimits,
    RetrievalSource,
    SourceLifecycleState,
    bounded_retrieval,
    filter_authorized_sources,
    invalid_citations,
)


def source(**overrides: object) -> RetrievalSource:
    defaults: dict[str, object] = {
        "source_id": "retrieval-source.example",
        "trust": "high",
        "authority": "vendor-documented",
        "applicability": "storage.health",
        "freshness": "current",
        "lifecycle_state": SourceLifecycleState.ACTIVE,
        "authorized_organization_ids": frozenset({"organization.example"}),
    }
    defaults.update(overrides)
    return RetrievalSource(**defaults)  # type: ignore[arg-type]


def test_an_authorized_active_source_passes_the_filter() -> None:
    example = source()
    assert filter_authorized_sources((example,), organization_id="organization.example") == (
        example,
    )


def test_an_unauthorized_organization_is_filtered_out_entirely() -> None:
    example = source()
    assert filter_authorized_sources((example,), organization_id="organization.other") == ()


@pytest.mark.parametrize(
    "state",
    [
        SourceLifecycleState.MALICIOUS,
        SourceLifecycleState.QUARANTINED,
        SourceLifecycleState.SUSPENDED,
        SourceLifecycleState.EXPIRED,
        SourceLifecycleState.DELETED,
    ],
)
def test_every_excluded_lifecycle_state_is_filtered_out(state: SourceLifecycleState) -> None:
    example = source(lifecycle_state=state)
    assert filter_authorized_sources((example,), organization_id="organization.example") == ()


def test_active_lifecycle_is_not_excluded() -> None:
    example = source(lifecycle_state=SourceLifecycleState.ACTIVE)
    assert example.is_excluded_by_lifecycle is False


def test_source_rejects_blank_metadata_fields() -> None:
    with pytest.raises(ValueError, match="trust"):
        source(trust="   ")
    with pytest.raises(ValueError, match="authority"):
        source(authority="   ")
    with pytest.raises(ValueError, match="applicability"):
        source(applicability="   ")
    with pytest.raises(ValueError, match="freshness"):
        source(freshness="   ")


def test_bounded_retrieval_caps_at_the_smaller_of_breadth_and_results() -> None:
    sources = tuple(source(source_id=f"retrieval-source.{i}") for i in range(10))
    limits = RetrievalLimits(max_breadth=5, max_depth=1, max_results=3)
    result = bounded_retrieval(sources, limits=limits)
    assert len(result) == 3


def test_bounded_retrieval_does_not_exceed_the_candidate_count() -> None:
    sources = (source(),)
    limits = RetrievalLimits(max_breadth=5, max_depth=1, max_results=10)
    assert bounded_retrieval(sources, limits=limits) == sources


def test_retrieval_limits_reject_non_positive_values() -> None:
    with pytest.raises(ValueError, match="max_breadth"):
        RetrievalLimits(max_breadth=0, max_depth=1, max_results=1)
    with pytest.raises(ValueError, match="max_depth"):
        RetrievalLimits(max_breadth=1, max_depth=-1, max_results=1)
    with pytest.raises(ValueError, match="max_results"):
        RetrievalLimits(max_breadth=1, max_depth=1, max_results=0)


def citation(**overrides: object) -> Citation:
    defaults: dict[str, object] = {
        "citation_id": "citation.example",
        "target_reference": "document.example",
        "supports_claim": True,
        "accessible_to_user": True,
    }
    defaults.update(overrides)
    return Citation(**defaults)  # type: ignore[arg-type]


def test_a_valid_citation_is_not_reported_invalid() -> None:
    example = citation()
    assert example.is_valid is True
    assert invalid_citations((example,)) == ()


def test_a_citation_not_supporting_the_claim_is_invalid() -> None:
    example = citation(supports_claim=False)
    assert invalid_citations((example,)) == (example,)


def test_a_citation_not_accessible_to_the_user_is_invalid() -> None:
    example = citation(accessible_to_user=False)
    assert invalid_citations((example,)) == (example,)


def test_citation_rejects_a_blank_target_reference() -> None:
    with pytest.raises(ValueError, match="target reference"):
        citation(target_reference="   ")


def test_invalid_citations_returns_only_the_invalid_ones() -> None:
    valid = citation(citation_id="citation.valid")
    invalid = citation(citation_id="citation.invalid", supports_claim=False)
    assert invalid_citations((valid, invalid)) == (invalid,)
