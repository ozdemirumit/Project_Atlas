from __future__ import annotations

from typing import Protocol

from atlas.modules.policy_engine.domain.policy_set import PolicySet


class PolicySetRepository(Protocol):
    """Supplies every known policy set as resolution candidates. Filtering to what actually
    applies (active, in-scope) is `resolve_policy_sets`'s job, not the repository's -- this
    keeps a real backing store's indexing free to change without touching resolution logic."""

    async def list_all(self) -> tuple[PolicySet, ...]: ...
