from __future__ import annotations

from atlas.modules.policy_engine.domain.policy_set import PolicySet


class InMemoryPolicySetRepository:
    def __init__(self, policy_sets: tuple[PolicySet, ...] = ()) -> None:
        self._policy_sets: dict[tuple[str, int], PolicySet] = {
            (item.set_id, item.version): item for item in policy_sets
        }

    async def list_all(self) -> tuple[PolicySet, ...]:
        return tuple(self._policy_sets.values())

    def add(self, policy_set: PolicySet) -> None:
        self._policy_sets[(policy_set.set_id, policy_set.version)] = policy_set
