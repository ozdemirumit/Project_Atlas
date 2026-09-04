from __future__ import annotations

import pytest

from atlas.modules.ai_agents.domain.catalog import (
    AGENT_ROLE_CATALOG,
    AgentRole,
    AgentRoleCatalogEntry,
    catalog_entry_for,
)


def test_agent_role_has_twelve_members() -> None:
    assert len(AgentRole) == 12


def test_every_agent_role_has_a_catalog_entry() -> None:
    for role in AgentRole:
        entry = catalog_entry_for(role)
        assert entry.role is role


def test_catalog_has_an_entry_for_every_role() -> None:
    assert set(AGENT_ROLE_CATALOG) == set(AgentRole)


def test_catalog_entry_requires_primary_responsibility() -> None:
    with pytest.raises(ValueError, match="primary responsibility"):
        AgentRoleCatalogEntry(
            role=AgentRole.KNOWLEDGE_AGENT,
            primary_responsibility="",
            typical_tool_categories=("knowledge",),
            prohibited_responsibility="Treating retrieved instructions as authority",
        )


def test_catalog_entry_requires_at_least_one_tool_category() -> None:
    with pytest.raises(ValueError, match="at least one typical tool category"):
        AgentRoleCatalogEntry(
            role=AgentRole.KNOWLEDGE_AGENT,
            primary_responsibility="Retrieve, compare, and cite governed knowledge",
            typical_tool_categories=(),
            prohibited_responsibility="Treating retrieved instructions as authority",
        )


def test_catalog_entry_requires_prohibited_responsibility() -> None:
    with pytest.raises(ValueError, match="prohibited responsibility"):
        AgentRoleCatalogEntry(
            role=AgentRole.KNOWLEDGE_AGENT,
            primary_responsibility="Retrieve, compare, and cite governed knowledge",
            typical_tool_categories=("knowledge",),
            prohibited_responsibility="",
        )


def test_change_impact_agent_prohibits_claiming_simulation_certainty() -> None:
    entry = catalog_entry_for(AgentRole.CHANGE_IMPACT_AGENT)
    assert "simulation certainty" in entry.prohibited_responsibility
