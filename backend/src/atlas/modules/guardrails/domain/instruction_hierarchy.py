"""ATLAS-047 SS9: instruction hierarchy, enforced outside the model.

The guardrail here is deliberately almost too simple to be interesting: `effective_source`
always returns the real, governed channel content arrived through and never the level it claims
for itself. There is no branch where a claim can win -- that absence of a code path is the
control SS9 describes ("text claiming to be a system message, administrator instruction, vendor
override, or emergency authorization remains untrusted data unless received through its governed
control channel").
"""

from __future__ import annotations

from enum import IntEnum


class InstructionSource(IntEnum):
    """SS9's six-level precedence. Lower value means higher precedence, matching the document's
    own 1-6 numbering; IntEnum so precedence comparisons are natural ordering, not just
    equality."""

    PLATFORM_INVARIANT = 1
    APPROVED_SYSTEM_OR_AGENT_DEFINITION = 2
    AUTHORIZED_ORGANIZATION_POLICY_OR_TASK_CONTRACT = 3
    GOVERNED_WORKFLOW_INSTRUCTION = 4
    AUTHENTICATED_USER_REQUEST = 5
    RETRIEVED_OR_TOOL_PROVIDED_CONTENT = 6

    @property
    def is_data_only(self) -> bool:
        """SS9: level 6 content is data only -- it can never itself be treated as an instruction
        to follow, regardless of what it claims to be."""
        return self is InstructionSource.RETRIEVED_OR_TOOL_PROVIDED_CONTENT


def effective_source(
    *, claimed_source: InstructionSource | None, actual_channel: InstructionSource
) -> InstructionSource:
    """The effective source is always the real, governed channel -- `claimed_source` exists as a
    parameter only so a caller can log or flag a mismatch (e.g. retrieved content claiming to be
    a system message); it never changes the result."""
    del claimed_source
    return actual_channel


def can_override(*, acting_source: InstructionSource, target_source: InstructionSource) -> bool:
    """SS9: "lower-level content cannot modify higher-level controls." A source may only affect
    (set, constrain, or override) a target at the same precedence or a numerically *larger*
    value (weaker, "lower-level" in the document's own words) -- never a numerically *smaller*
    (more senior, "higher-level") one. A platform invariant can constrain a user request; a piece
    of retrieved content can never constrain the user request that triggered its retrieval."""
    return acting_source.value <= target_source.value


class InstructionHierarchyViolation(Exception):
    def __init__(
        self, *, acting_source: InstructionSource, target_source: InstructionSource
    ) -> None:
        super().__init__(
            f"{acting_source.name} (level {acting_source.value}) cannot override"
            f" {target_source.name} (level {target_source.value})"
        )
        self.acting_source = acting_source
        self.target_source = target_source


def require_no_precedence_violation(
    *, acting_source: InstructionSource, target_source: InstructionSource
) -> None:
    if not can_override(acting_source=acting_source, target_source=target_source):
        raise InstructionHierarchyViolation(
            acting_source=acting_source, target_source=target_source
        )
