"""ATLAS-047 SS17: tool result guardrails.

`ToolResult.state` is the normalized outcome, and nothing in this module ever lets a model's own
claim about a result change it -- SS17: "model summaries cannot change the normalized result
state." `normalize_result_state` accepts a model claim only to make that guarantee visible in
its own signature: the parameter is never read.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class ToolResultState(StrEnum):
    """SS17: "timeout, partial, unknown, and ambiguous outcomes remain distinct.\""""

    SUCCESS = "success"
    TIMEOUT = "timeout"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    AMBIGUOUS = "ambiguous"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ToolResult:
    result_id: str
    tool_id: str
    state: ToolResultState
    size_bytes: int
    vendor_status: str | None
    external_request_id: str | None
    returned_target_id: str | None
    requested_target_id: str
    unexpected_side_effect_detected: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.result_id, "result_id")
        validate_stable_identifier(self.tool_id, "tool_id")
        validate_stable_identifier(self.requested_target_id, "requested_target_id")
        if self.size_bytes < 0:
            raise ValueError("size_bytes must not be negative")

    @property
    def target_mismatch(self) -> bool:
        """SS17: "target identity and requested scope are compared with returned objects.\""""
        return (
            self.returned_target_id is not None
            and self.returned_target_id != self.requested_target_id
        )


def normalize_result_state(
    result: ToolResult, *, model_summary_claims_success: bool
) -> ToolResultState:
    del model_summary_claims_success
    return result.state


@dataclass(frozen=True, slots=True)
class ResultLimits:
    max_size_bytes: int

    def __post_init__(self) -> None:
        if self.max_size_bytes < 1:
            raise ValueError("max_size_bytes must be positive")


def validate_result(result: ToolResult, *, limits: ResultLimits) -> tuple[str, ...]:
    violations: list[str] = []
    if result.size_bytes > limits.max_size_bytes:
        violations.append(f"result exceeds the maximum size of {limits.max_size_bytes} bytes")
    if result.target_mismatch:
        violations.append(
            f"returned target {result.returned_target_id} does not match requested target"
            f" {result.requested_target_id}"
        )
    if result.unexpected_side_effect_detected:
        violations.append("result indicates an unexpected side effect")
    return tuple(violations)


def requires_incident(result: ToolResult) -> bool:
    """SS17: "unexpected side-effect indicators stop further related calls and raise an
    incident." A target mismatch is an equally serious confused-deputy / target-substitution
    signal and is treated the same way, even though SS17 names only side effects explicitly."""
    return result.unexpected_side_effect_detected or result.target_mismatch
