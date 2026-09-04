"""ATLAS-021 SS22/SS23: required test categories and mock/fixture governance."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.guardrails.domain.input_guardrails import detect_secret_patterns
from atlas.modules.identity.domain.models import validate_stable_identifier


class RequiredTestCategory(StrEnum):
    """SS22's seven required test categories."""

    UNIT = "unit"
    CONTRACT = "contract"
    SECURITY = "security"
    FAILURE = "failure"
    IDEMPOTENCY = "idempotency"
    INTEGRATION = "integration"
    UPGRADE = "upgrade"


@dataclass(frozen=True, slots=True)
class CategoryCoverage:
    category: RequiredTestCategory
    covered_scenario_names: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.covered_scenario_names:
            raise ValueError("a test category requires at least one covered scenario")


@dataclass(frozen=True, slots=True)
class CapabilityTestCoverageReport:
    capability_id: str
    coverage: tuple[CategoryCoverage, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.capability_id, "capability_id")
        categories = [item.category for item in self.coverage]
        if len(set(categories)) != len(categories):
            raise ValueError("a capability test coverage report must not repeat a category")
        if set(categories) != set(RequiredTestCategory):
            raise ValueError(
                "a capability test coverage report requires every required test category"
            )


class FailureFixtureKind(StrEnum):
    """SS23: "failure fixtures include vendor error, malformed, truncated, delayed, and
    contradictory responses.\""""

    VENDOR_ERROR = "vendor_error"
    MALFORMED = "malformed"
    TRUNCATED = "truncated"
    DELAYED = "delayed"
    CONTRADICTORY = "contradictory"


@dataclass(frozen=True, slots=True)
class Fixture:
    """SS23's declared elements. `sanitized`/`reviewed` must be `True` to construct at all, and
    `payload` is scanned with Guardrails' `detect_secret_patterns` -- "fixtures contain no real
    customer identifiers, credentials, IP addresses, or sensitive data" as a construction-time
    guarantee rather than a review-process convention."""

    fixture_id: str
    target_product: str
    target_version: str
    sanitized: bool
    reviewed: bool
    capability_schema_version: str
    failure_kind: FailureFixtureKind | None
    payload: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.fixture_id, "fixture_id")
        if not self.target_product.strip():
            raise ValueError("a fixture requires a target product")
        if not self.target_version.strip():
            raise ValueError("a fixture requires a target version")
        if not self.capability_schema_version.strip():
            raise ValueError("a fixture requires a capability schema version")
        if not self.sanitized or not self.reviewed:
            raise ValueError("SS23: recorded vendor responses are sanitized and reviewed")
        for _, value in self.payload:
            if detect_secret_patterns(value):
                raise ValueError(
                    "SS23: fixtures contain no real customer identifiers, credentials, IP "
                    "addresses, or sensitive data"
                )
