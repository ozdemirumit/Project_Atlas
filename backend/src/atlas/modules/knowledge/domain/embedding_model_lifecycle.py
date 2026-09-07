"""ATLAS-054 SS10: Embedding Model Lifecycle.

Throughout `embedding_generation.py`/`retrieval_index_publication.py`, `model_profile_id`/
`model_profile_digest` are only ever opaque reference strings folded into a content digest --
never an object with its own registration/evaluation/approval/activation/deprecation/suspension
state. This module represents SS10's seven-state lifecycle as its own real, independent type,
the same shape ATLAS-014's `ai.domain.model_lifecycle.ModelLifecycleStage` already established
for the model-gateway's own model lifecycle (a distinct governance concern from this one).
"""

from __future__ import annotations

from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class EmbeddingModelLifecycleStage(StrEnum):
    """SS10's seven named states."""

    CANDIDATE = "candidate"
    EVALUATING = "evaluating"
    APPROVED = "approved"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUSPENDED = "suspended"
    RETIRED = "retired"


_EMBEDDING_MODEL_LIFECYCLE_TRANSITIONS: dict[
    EmbeddingModelLifecycleStage, frozenset[EmbeddingModelLifecycleStage]
] = {
    EmbeddingModelLifecycleStage.CANDIDATE: frozenset({EmbeddingModelLifecycleStage.EVALUATING}),
    EmbeddingModelLifecycleStage.EVALUATING: frozenset(
        {EmbeddingModelLifecycleStage.CANDIDATE, EmbeddingModelLifecycleStage.APPROVED}
    ),
    EmbeddingModelLifecycleStage.APPROVED: frozenset({EmbeddingModelLifecycleStage.ACTIVE}),
    EmbeddingModelLifecycleStage.ACTIVE: frozenset(
        {EmbeddingModelLifecycleStage.DEPRECATED, EmbeddingModelLifecycleStage.SUSPENDED}
    ),
    EmbeddingModelLifecycleStage.DEPRECATED: frozenset({EmbeddingModelLifecycleStage.RETIRED}),
    EmbeddingModelLifecycleStage.SUSPENDED: frozenset(
        {EmbeddingModelLifecycleStage.ACTIVE, EmbeddingModelLifecycleStage.RETIRED}
    ),
    EmbeddingModelLifecycleStage.RETIRED: frozenset(),
}


def is_valid_embedding_model_transition(
    current: EmbeddingModelLifecycleStage, target: EmbeddingModelLifecycleStage
) -> bool:
    """SS10's seven-state lifecycle, reproduced as an explicit adjacency table (mirrors
    `RunbookLifecycleState`'s and `ModelLifecycleStage`'s established pattern elsewhere)."""
    return target in _EMBEDDING_MODEL_LIFECYCLE_TRANSITIONS[current]


def validate_embedding_model_id(model_id: str) -> None:
    validate_stable_identifier(model_id, "embedding model_id")


def an_embedding_model_becomes_active_without_passing_through_approval_or_revalidation() -> bool:
    """SS10: "Re-embedding runs side by side, is evaluated, and changes the active retrieval
    profile only after validation." `is_valid_embedding_model_transition` makes `ACTIVE` reachable
    only from `APPROVED` (post-evaluation) or `SUSPENDED` ("Revalidated") -- never directly from
    `CANDIDATE` or `EVALUATING`."""
    return is_valid_embedding_model_transition(
        EmbeddingModelLifecycleStage.CANDIDATE, EmbeddingModelLifecycleStage.ACTIVE
    ) or is_valid_embedding_model_transition(
        EmbeddingModelLifecycleStage.EVALUATING, EmbeddingModelLifecycleStage.ACTIVE
    )
