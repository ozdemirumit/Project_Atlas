"""ATLAS-021 SS20/SS21: the health API and test harness.

`HealthCheckResult`/`HealthReport` reuse `connectors.domain.models.ConnectorHealth` directly for
"health results distinguish healthy, degraded, unavailable, incompatible, and unknown" -- that
enum already has exactly those five members.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.connectors.domain.models import ConnectorHealth
from atlas.modules.identity.domain.models import validate_stable_identifier


class HealthCheckKind(StrEnum):
    """SS20's eight separate health check functions."""

    PACKAGE_SELF_TEST = "package_self_test"
    CONFIGURATION_VALIDATION = "configuration_validation"
    SECRET_AVAILABILITY = "secret_availability"
    ENDPOINT_RESOLUTION_AND_CERTIFICATE_TRUST = "endpoint_resolution_and_certificate_trust"
    AUTHENTICATION = "authentication"
    TARGET_PRODUCT_AND_VERSION_COMPATIBILITY = "target_product_and_version_compatibility"
    SAFE_READ_ONLY_CAPABILITY_PROBE = "safe_read_only_capability_probe"
    DEPENDENCY_STATUS = "dependency_status"


@dataclass(frozen=True, slots=True)
class HealthCheckResult:
    kind: HealthCheckKind
    status: ConnectorHealth
    detail: str
    checked_at: datetime

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("a health check result requires a detail")
        if self.checked_at.tzinfo is None:
            raise ValueError("checked_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class HealthReport:
    instance_id: str
    results: tuple[HealthCheckResult, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.instance_id, "instance_id")
        kinds = [result.kind for result in self.results]
        if len(set(kinds)) != len(kinds):
            raise ValueError("a health report must not repeat a health check kind")
        if set(kinds) != set(HealthCheckKind):
            raise ValueError("a health report requires every health check kind")

    @property
    def is_fully_healthy(self) -> bool:
        return all(result.status is ConnectorHealth.HEALTHY for result in self.results)


class HarnessCapability(StrEnum):
    """SS21's ten test harness capabilities."""

    FAKE_INVOCATION_CONTEXT_AND_CANCELLATION = "fake_invocation_context_and_cancellation"
    IN_MEMORY_SECRET_HANDLES_WITH_REDACTION_ASSERTIONS = (
        "in_memory_secret_handles_with_redaction_assertions"
    )
    MOCK_HTTP_SDK_CLI_AND_FILE_CLIENTS = "mock_http_sdk_cli_and_file_clients"
    SYNTHETIC_CLOCK_AND_DEADLINES = "synthetic_clock_and_deadlines"
    TARGET_FIXTURES_AND_SCENARIO_BUILDERS = "target_fixtures_and_scenario_builders"
    GOLDEN_STRUCTURED_RESULTS = "golden_structured_results"
    SCHEMA_AND_MANIFEST_VALIDATION = "schema_and_manifest_validation"
    AUDIT_AND_TELEMETRY_CAPTURE = "audit_and_telemetry_capture"
    FAULT_INJECTION = "fault_injection"
    RUNNER_LEVEL_SANDBOX_TEST_INTEGRATION = "runner_level_sandbox_test_integration"


@dataclass(frozen=True, slots=True)
class HarnessDeclaration:
    harness_id: str
    provided_capabilities: frozenset[HarnessCapability]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.harness_id, "harness_id")
        missing = set(HarnessCapability) - self.provided_capabilities
        if missing:
            raise ValueError(
                "a test harness declaration must provide every capability, missing "
                f"{sorted(capability.value for capability in missing)}"
            )
