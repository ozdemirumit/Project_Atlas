"""ATLAS-040 SS5: the logical agent catalog.

SS5's closing line -- "organizations may add domain-specialized roles ... through the same
governed contract" -- means `AgentRole` is not meant to be exhaustive forever, but the twelve
named roles are what this document actually specifies; a registry for organization-added roles is
a real extension point left for whoever builds that governed contract, not modeled here ahead of
need.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AgentRole(StrEnum):
    """SS5's twelve logical agent roles."""

    CONVERSATION_ORCHESTRATOR = "conversation_orchestrator"
    HEALTH_ANALYSIS_AGENT = "health_analysis_agent"
    TROUBLESHOOTING_AGENT = "troubleshooting_agent"
    ROOT_CAUSE_AGENT = "root_cause_agent"
    CHANGE_IMPACT_AGENT = "change_impact_agent"
    RECOMMENDATION_AGENT = "recommendation_agent"
    KNOWLEDGE_AGENT = "knowledge_agent"
    RUNBOOK_AGENT = "runbook_agent"
    MCP_BUILDER_AGENT = "mcp_builder_agent"
    SECURITY_REVIEW_AGENT = "security_review_agent"
    AUDIT_EXPLANATION_AGENT = "audit_explanation_agent"
    REPORT_AGENT = "report_agent"


@dataclass(frozen=True, slots=True)
class AgentRoleCatalogEntry:
    """SS5's table columns."""

    role: AgentRole
    primary_responsibility: str
    typical_tool_categories: tuple[str, ...]
    prohibited_responsibility: str

    def __post_init__(self) -> None:
        if not self.primary_responsibility.strip():
            raise ValueError("a catalog entry requires a primary responsibility")
        if not self.typical_tool_categories:
            raise ValueError("a catalog entry requires at least one typical tool category")
        if not self.prohibited_responsibility.strip():
            raise ValueError("a catalog entry requires a prohibited responsibility")


AGENT_ROLE_CATALOG: dict[AgentRole, AgentRoleCatalogEntry] = {
    AgentRole.CONVERSATION_ORCHESTRATOR: AgentRoleCatalogEntry(
        role=AgentRole.CONVERSATION_ORCHESTRATOR,
        primary_responsibility=(
            "Interpret request, establish task contract, route roles, synthesize response"
        ),
        typical_tool_categories=("catalog", "task_state", "safe_retrieval"),
        prohibited_responsibility="Direct connector execution or approval",
    ),
    AgentRole.HEALTH_ANALYSIS_AGENT: AgentRoleCatalogEntry(
        role=AgentRole.HEALTH_ANALYSIS_AGENT,
        primary_responsibility="Interpret health observations and deviations",
        typical_tool_categories=("c0_c1_observations", "graph", "knowledge"),
        prohibited_responsibility="Declaring root cause without evidence",
    ),
    AgentRole.TROUBLESHOOTING_AGENT: AgentRoleCatalogEntry(
        role=AgentRole.TROUBLESHOOTING_AGENT,
        primary_responsibility="Build and refine diagnostic investigation plans",
        typical_tool_categories=("evidence_retrieval", "bounded_c1_c2_proposals"),
        prohibited_responsibility="Unapproved diagnostics or changes",
    ),
    AgentRole.ROOT_CAUSE_AGENT: AgentRoleCatalogEntry(
        role=AgentRole.ROOT_CAUSE_AGENT,
        primary_responsibility="Rank causal hypotheses and discriminating checks",
        typical_tool_categories=("timeline", "graph", "evidence", "atlas_042_services"),
        prohibited_responsibility="Presenting correlation as proven causation",
    ),
    AgentRole.CHANGE_IMPACT_AGENT: AgentRoleCatalogEntry(
        role=AgentRole.CHANGE_IMPACT_AGENT,
        primary_responsibility="Estimate blast radius, interruption, and uncertainty",
        typical_tool_categories=("graph", "live_state", "history", "atlas_044_services"),
        prohibited_responsibility="Claiming simulation certainty",
    ),
    AgentRole.RECOMMENDATION_AGENT: AgentRoleCatalogEntry(
        role=AgentRole.RECOMMENDATION_AGENT,
        primary_responsibility=(
            "Produce options, risk, prerequisites, recovery, and preferred recommendation"
        ),
        typical_tool_categories=("decision", "policy", "knowledge", "atlas_043_services"),
        prohibited_responsibility="Executing or approving an option",
    ),
    AgentRole.KNOWLEDGE_AGENT: AgentRoleCatalogEntry(
        role=AgentRole.KNOWLEDGE_AGENT,
        primary_responsibility="Retrieve, compare, and cite governed knowledge",
        typical_tool_categories=("atlas_015_services", "atlas_027_services"),
        prohibited_responsibility="Treating retrieved instructions as authority",
    ),
    AgentRole.RUNBOOK_AGENT: AgentRoleCatalogEntry(
        role=AgentRole.RUNBOOK_AGENT,
        primary_responsibility="Match and interpret approved procedures",
        typical_tool_categories=("atlas_045_service", "knowledge", "policy"),
        prohibited_responsibility="Converting ambiguous prose into silent automation",
    ),
    AgentRole.MCP_BUILDER_AGENT: AgentRoleCatalogEntry(
        role=AgentRole.MCP_BUILDER_AGENT,
        primary_responsibility="Draft connector artifacts from approved specifications",
        typical_tool_categories=("isolated_builder_environment", "validation_environment"),
        prohibited_responsibility="Signing, publishing, or deploying its own output",
    ),
    AgentRole.SECURITY_REVIEW_AGENT: AgentRoleCatalogEntry(
        role=AgentRole.SECURITY_REVIEW_AGENT,
        primary_responsibility="Identify unsafe requests, sensitive content, and control gaps",
        typical_tool_categories=("guardrail", "policy", "static_evidence"),
        prohibited_responsibility="Replacing deterministic security enforcement",
    ),
    AgentRole.AUDIT_EXPLANATION_AGENT: AgentRoleCatalogEntry(
        role=AgentRole.AUDIT_EXPLANATION_AGENT,
        primary_responsibility="Summarize an authorized activity chain",
        typical_tool_categories=("audit_search_projection",),
        prohibited_responsibility="Modifying or judging authoritative audit records",
    ),
    AgentRole.REPORT_AGENT: AgentRoleCatalogEntry(
        role=AgentRole.REPORT_AGENT,
        primary_responsibility="Render approved analysis into audience-specific reports",
        typical_tool_categories=("versioned_artifacts", "templates"),
        prohibited_responsibility="Adding unsupported facts",
    ),
}


def catalog_entry_for(role: AgentRole) -> AgentRoleCatalogEntry:
    return AGENT_ROLE_CATALOG[role]
