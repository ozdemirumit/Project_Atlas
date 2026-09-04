"""ATLAS-024 SS6/SS7: decision request and evidence package.

Reuses `reasoning.domain.models.EvidenceUnit` (ATLAS-041 SS5) for evidence package items -- SS7's
own requirements (reference/type, source/owner/provenance/authority, observation/publication/
retrieval/expiry time, product/version/target/environment applicability, access/classification,
integrity, conflict/stale/superseded/missing/partial labels) are essentially the same shape
`EvidenceUnit` already models, and ATLAS-041's own dependency section states plainly that
"ATLAS-024 consumes validated reasoning artifacts for decisions" -- Decision Engine sits
downstream of Reasoning, not the reverse.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.reasoning.domain.models import EvidenceUnit


@dataclass(frozen=True, slots=True)
class DecisionRequest:
    """SS6's required fields. `decision_type` is a plain string rather than an enum: SS6 does
    not enumerate a fixed, closed set of decision types, only that one is required."""

    request_id: str
    workflow_id: str | None
    requesting_identity: str
    authorized_scope_reference: str
    decision_type: str
    question: str
    target_ids: tuple[str, ...]
    service_ids: tuple[str, ...]
    environment_id: str
    time_window_start: datetime
    time_window_end: datetime
    required_evidence_domains: tuple[str, ...]
    required_output_schema: str
    deadline: datetime | None
    required_freshness_seconds: int
    applicable_domain: str
    applicable_product_versions: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.request_id, "request_id")
        if self.workflow_id is not None:
            validate_stable_identifier(self.workflow_id, "workflow_id")
        if not self.requesting_identity.strip():
            raise ValueError("a decision request requires a requesting identity")
        if not self.authorized_scope_reference.strip():
            raise ValueError("a decision request requires an authorized scope reference")
        if not self.decision_type.strip():
            raise ValueError("a decision request requires a decision type")
        if not self.question.strip():
            raise ValueError("a decision request requires a question")
        if not self.target_ids:
            raise ValueError("a decision request requires at least one target")
        validate_stable_identifier(self.environment_id, "environment_id")
        if self.time_window_start.tzinfo is None or self.time_window_end.tzinfo is None:
            raise ValueError("the time window must be timezone-aware")
        if self.time_window_end < self.time_window_start:
            raise ValueError("time_window_end must not precede time_window_start")
        if self.deadline is not None and self.deadline.tzinfo is None:
            raise ValueError("deadline must be timezone-aware")
        if not self.required_output_schema.strip():
            raise ValueError("a decision request requires a required output schema")
        if self.required_freshness_seconds < 1:
            raise ValueError("required_freshness_seconds must be positive")
        if not self.applicable_domain.strip():
            raise ValueError("a decision request requires an applicable domain")


@dataclass(frozen=True, slots=True)
class EvidencePackage:
    """SS7: "evidence content is immutable for one decision record. Later evidence creates a new
    decision version." Immutability comes from the dataclass being frozen; each item is a real
    `EvidenceUnit` (ATLAS-041), not a parallel evidence shape."""

    package_id: str
    request_id: str
    items: tuple[EvidenceUnit, ...]
    created_at: datetime

    def __post_init__(self) -> None:
        validate_stable_identifier(self.package_id, "package_id")
        validate_stable_identifier(self.request_id, "request_id")
        if not self.items:
            raise ValueError("an evidence package requires at least one evidence unit")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
