from __future__ import annotations

from atlas.modules.runbook_engine.domain.applicability import (
    ApplicabilityFactor,
    ApplicabilityFactorKind,
    ApplicabilityFactorResult,
    ApplicabilityMatch,
)
from atlas.modules.runbook_engine.domain.models import RunbookLifecycleState
from atlas.modules.runbook_engine.domain.retrieval import (
    RunbookCandidate,
    find_authority_conflicts,
    is_eligible_for_retrieval,
    rank_candidates,
    resolve_pinned_or_ranked,
)


def applicability(**overrides: object) -> ApplicabilityMatch:
    factor = ApplicabilityFactor(
        kind=ApplicabilityFactorKind.VENDOR_AND_VERSION_COMPATIBILITY,
        result=overrides.pop("result", ApplicabilityFactorResult.EXACT),  # type: ignore[arg-type]
        explanation="The target's firmware version matches the runbook's tested version.",
    )
    defaults: dict[str, object] = {
        "runbook_id": "runbook.example",
        "version_id": "runbook-version.example",
        "target_id": "target.example",
        "factors": (factor,),
    }
    defaults.update(overrides)
    return ApplicabilityMatch(**defaults)  # type: ignore[arg-type]


def candidate(**overrides: object) -> RunbookCandidate:
    defaults: dict[str, object] = {
        "runbook_id": "runbook.example",
        "version_id": "runbook-version.example",
        "state": RunbookLifecycleState.PUBLISHED,
        "applicability": applicability(),
        "is_tested": True,
        "ai_generated": False,
        "is_exact_product_and_version_match": True,
        "authority": "source-authority.vendor",
    }
    defaults.update(overrides)
    return RunbookCandidate(**defaults)  # type: ignore[arg-type]


def test_is_eligible_for_retrieval_true_when_authorized() -> None:
    example = candidate()
    assert (
        is_eligible_for_retrieval(example, authorized_runbook_ids=frozenset({"runbook.example"}))
        is True
    )


def test_is_eligible_for_retrieval_false_when_not_authorized() -> None:
    example = candidate()
    assert is_eligible_for_retrieval(example, authorized_runbook_ids=frozenset()) is False


def test_rank_candidates_excludes_unauthorized() -> None:
    example = candidate(runbook_id="runbook.unauthorized")
    ranked = rank_candidates((example,), authorized_runbook_ids=frozenset({"runbook.example"}))
    assert ranked == ()


def test_rank_candidates_returns_empty_when_no_suitable_runbook_exists() -> None:
    ranked = rank_candidates((), authorized_runbook_ids=frozenset())
    assert ranked == ()


def test_published_tested_candidate_outranks_ai_generated() -> None:
    good = candidate(runbook_id="runbook.good", version_id="runbook-version.good")
    generated = candidate(
        runbook_id="runbook.generated",
        version_id="runbook-version.generated",
        ai_generated=True,
        state=RunbookLifecycleState.DRAFT,
    )
    ranked = rank_candidates(
        (generated, good),
        authorized_runbook_ids=frozenset({"runbook.good", "runbook.generated"}),
    )
    assert ranked[0].runbook_id == "runbook.good"


def test_historical_state_ranks_below_active() -> None:
    active = candidate(runbook_id="runbook.active", version_id="runbook-version.active")
    superseded = candidate(
        runbook_id="runbook.superseded",
        version_id="runbook-version.superseded",
        state=RunbookLifecycleState.SUPERSEDED,
    )
    ranked = rank_candidates(
        (superseded, active),
        authorized_runbook_ids=frozenset({"runbook.active", "runbook.superseded"}),
    )
    assert ranked[0].runbook_id == "runbook.active"


def test_exact_product_and_version_match_outranks_generic() -> None:
    exact = candidate(
        runbook_id="runbook.exact",
        version_id="runbook-version.exact",
        is_exact_product_and_version_match=True,
    )
    generic = candidate(
        runbook_id="runbook.generic",
        version_id="runbook-version.generic",
        is_exact_product_and_version_match=False,
    )
    ranked = rank_candidates(
        (generic, exact), authorized_runbook_ids=frozenset({"runbook.exact", "runbook.generic"})
    )
    assert ranked[0].runbook_id == "runbook.exact"


def test_resolve_pinned_or_ranked_returns_the_pinned_version() -> None:
    pinned = candidate(runbook_id="runbook.example", version_id="runbook-version.pinned")
    other = candidate(runbook_id="runbook.example", version_id="runbook-version.other")
    resolved = resolve_pinned_or_ranked(
        pinned_version_id="runbook-version.pinned",
        candidates=(other, pinned),
        authorized_runbook_ids=frozenset({"runbook.example"}),
    )
    assert resolved is not None
    assert resolved.version_id == "runbook-version.pinned"


def test_resolve_pinned_or_ranked_returns_none_when_pinned_version_is_unauthorized() -> None:
    pinned = candidate(runbook_id="runbook.example", version_id="runbook-version.pinned")
    resolved = resolve_pinned_or_ranked(
        pinned_version_id="runbook-version.pinned",
        candidates=(pinned,),
        authorized_runbook_ids=frozenset(),
    )
    assert resolved is None


def test_resolve_pinned_or_ranked_falls_back_to_top_ranked_when_no_pin() -> None:
    good = candidate(runbook_id="runbook.example", version_id="runbook-version.good")
    resolved = resolve_pinned_or_ranked(
        pinned_version_id=None,
        candidates=(good,),
        authorized_runbook_ids=frozenset({"runbook.example"}),
    )
    assert resolved is not None
    assert resolved.version_id == "runbook-version.good"


def test_find_authority_conflicts_between_differing_authorities() -> None:
    first = candidate(
        runbook_id="runbook.a", version_id="runbook-version.a", authority="source-authority.vendor"
    )
    second = candidate(
        runbook_id="runbook.b",
        version_id="runbook-version.b",
        authority="source-authority.internal",
    )
    conflicts = find_authority_conflicts((first, second))
    assert len(conflicts) == 1


def test_find_authority_conflicts_excludes_inapplicable_candidates() -> None:
    first = candidate(
        runbook_id="runbook.a",
        version_id="runbook-version.a",
        authority="source-authority.vendor",
        applicability=applicability(
            runbook_id="runbook.a",
            version_id="runbook-version.a",
            result=ApplicabilityFactorResult.INAPPLICABLE,
        ),
    )
    second = candidate(
        runbook_id="runbook.b",
        version_id="runbook-version.b",
        authority="source-authority.internal",
    )
    conflicts = find_authority_conflicts((first, second))
    assert conflicts == ()


def test_find_authority_conflicts_excludes_same_authority() -> None:
    first = candidate(
        runbook_id="runbook.a", version_id="runbook-version.a", authority="source-authority.vendor"
    )
    second = candidate(
        runbook_id="runbook.b", version_id="runbook-version.b", authority="source-authority.vendor"
    )
    conflicts = find_authority_conflicts((first, second))
    assert conflicts == ()
