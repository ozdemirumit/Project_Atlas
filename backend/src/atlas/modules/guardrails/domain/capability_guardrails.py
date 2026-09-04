"""ATLAS-047 SS16: capability guardrails.

Distinct from Policy Engine's default capability posture (ATLAS-025 SS11): that table describes
what Policy *allows* to proceed; this one describes what the AI agent itself may ever *propose*
or *directly cause Atlas to invoke or dispatch*, before Policy is even consulted. The two happen
to agree in spirit (both grow stricter from C0 to C5) but answer different questions, so this is
its own table, not a re-export of Policy Engine's.
"""

from __future__ import annotations

from dataclasses import dataclass

from atlas.core.capabilities import CapabilityClass


@dataclass(frozen=True, slots=True)
class AIToolPosture:
    capability_class: CapabilityClass
    ai_may_propose: bool
    atlas_may_invoke_or_dispatch: bool
    description: str


_POSTURE_TABLE: dict[CapabilityClass, AIToolPosture] = {
    CapabilityClass.C0_INFORMATIONAL: AIToolPosture(
        capability_class=CapabilityClass.C0_INFORMATIONAL,
        ai_may_propose=True,
        atlas_may_invoke_or_dispatch=True,
        description="Allowed within data permissions and task scope.",
    ),
    CapabilityClass.C1_READ_ONLY: AIToolPosture(
        capability_class=CapabilityClass.C1_READ_ONLY,
        ai_may_propose=True,
        atlas_may_invoke_or_dispatch=True,
        description=(
            "Allowed only through approved live-read capabilities, current authorization,"
            " policy, and audit."
        ),
    ),
    CapabilityClass.C2_DIAGNOSTIC: AIToolPosture(
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
        ai_may_propose=True,
        atlas_may_invoke_or_dispatch=False,
        description=(
            "Proposal allowed; execution remains external unless the capability is reclassified"
            " as C1 read-only."
        ),
    ),
    CapabilityClass.C3_CONTROLLED_CHANGE: AIToolPosture(
        capability_class=CapabilityClass.C3_CONTROLLED_CHANGE,
        ai_may_propose=True,
        atlas_may_invoke_or_dispatch=False,
        description="AI can draft plan and impact; Atlas cannot invoke or dispatch it.",
    ),
    CapabilityClass.C4_SERVICE_IMPACTING: AIToolPosture(
        capability_class=CapabilityClass.C4_SERVICE_IMPACTING,
        ai_may_propose=True,
        atlas_may_invoke_or_dispatch=False,
        description="AI can analyze and recommend; Atlas cannot invoke or dispatch it.",
    ),
    CapabilityClass.C5_DESTRUCTIVE: AIToolPosture(
        capability_class=CapabilityClass.C5_DESTRUCTIVE,
        ai_may_propose=False,
        atlas_may_invoke_or_dispatch=False,
        description="Prohibited in Atlas; exceptional external human-governed procedures only.",
    ),
}


def posture_for(capability_class: CapabilityClass | None) -> AIToolPosture | None:
    """SS16: "misclassified or unknown capabilities are denied until reviewed." A `None` input
    or an unrecognized class both resolve to `None` here -- deny-until-reviewed, never a
    permissive default for something this table does not recognize."""
    if capability_class is None:
        return None
    return _POSTURE_TABLE.get(capability_class)


def is_proposal_permitted(capability_class: CapabilityClass | None) -> bool:
    posture = posture_for(capability_class)
    return posture is not None and posture.ai_may_propose


def is_direct_invocation_permitted(capability_class: CapabilityClass | None) -> bool:
    posture = posture_for(capability_class)
    return posture is not None and posture.atlas_may_invoke_or_dispatch
