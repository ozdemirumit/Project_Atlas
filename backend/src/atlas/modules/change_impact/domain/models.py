"""ATLAS-044 SS4/SS6: change categories and the change request contract.

`ChangeParameter` reuses `guardrails.domain.input_guardrails.detect_secret_patterns` to enforce
SS6's "typed parameters with secret references instead of values" structurally: a parameter whose
literal `value` looks like a secret is rejected outright, forcing the caller to supply a
`secret_reference` instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.guardrails.domain.input_guardrails import detect_secret_patterns
from atlas.modules.identity.domain.models import validate_stable_identifier


class ChangeCategory(StrEnum):
    """SS4's eleven change categories."""

    CONFIGURATION_MODIFICATION = "configuration_modification"
    SOFTWARE_FIRMWARE_DRIVER_OR_PATCH_UPDATE = "software_firmware_driver_or_patch_update"
    RESTART_FAILOVER_TAKEOVER_OR_CONTROLLER_TRANSITION = (
        "restart_failover_takeover_or_controller_transition"
    )
    PATH_ZONING_FABRIC_NETWORK_DNS_OR_CERTIFICATE_CHANGE = (
        "path_zoning_fabric_network_dns_or_certificate_change"
    )
    STORAGE_VOLUME_POOL_REPLICATION_SNAPSHOT_OR_PROTECTION_CHANGE = (
        "storage_volume_pool_replication_snapshot_or_protection_change"
    )
    VIRTUALIZATION_HOST_CLUSTER_DATASTORE_OR_VM_CHANGE = (
        "virtualization_host_cluster_datastore_or_vm_change"
    )
    OPERATING_SYSTEM_SERVICE_OR_HOST_MAINTENANCE = "operating_system_service_or_host_maintenance"
    BACKUP_RESTORE_RETENTION_OR_POLICY_CHANGE = "backup_restore_retention_or_policy_change"
    CAPACITY_EXPANSION_REBALANCE_MIGRATION_OR_RETIREMENT = (
        "capacity_expansion_rebalance_migration_or_retirement"
    )
    IDENTITY_SECURITY_TRUST_OR_ACCESS_CONTROL_CHANGE = (
        "identity_security_trust_or_access_control_change"
    )
    ATLAS_PLATFORM_CONNECTOR_POLICY_OR_INTEGRATION_CHANGE = (
        "atlas_platform_connector_policy_or_integration_change"
    )


@dataclass(frozen=True, slots=True)
class ChangeStepSpec:
    """SS6: "exact actions or conceptual steps and their order" plus "connector capabilities or
    manual procedure references." A step must be executable by at least one of those two means."""

    step_id: str
    order: int
    description: str
    connector_capability_id: str | None
    manual_procedure_reference: str | None
    capability_class: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.step_id, "step_id")
        if self.order < 1:
            raise ValueError("order must be a positive 1-based step number")
        if not self.description.strip():
            raise ValueError("a change step requires a description")
        if self.connector_capability_id is None and self.manual_procedure_reference is None:
            raise ValueError(
                "a change step requires a connector capability id or a manual procedure reference"
            )
        if not self.capability_class.strip():
            raise ValueError(
                "a change step requires an ATLAS-003 capability class based on realistic "
                "worst-case behavior"
            )


@dataclass(frozen=True, slots=True)
class ChangeParameter:
    """SS6: "typed parameters with secret references instead of values." Exactly one of `value`
    or `secret_reference` is set; a literal `value` that looks like a secret is rejected."""

    name: str
    value_type: str
    value: str | None
    secret_reference: str | None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("a change parameter requires a name")
        if not self.value_type.strip():
            raise ValueError("a change parameter requires a value_type")
        if (self.value is None) == (self.secret_reference is None):
            raise ValueError("a change parameter requires exactly one of value or secret_reference")
        if self.value is not None and detect_secret_patterns(self.value):
            raise ValueError(
                "a change parameter value looks like a secret -- use secret_reference instead"
            )


@dataclass(frozen=True, slots=True)
class ChangeRequest:
    """SS6's change request contract."""

    request_id: str
    proposed_change_version: int
    purpose: str
    expected_outcome: str
    change_category: ChangeCategory
    steps: tuple[ChangeStepSpec, ...]
    target_ids: tuple[str, ...]
    organization_id: str
    environment_id: str
    site_id: str | None
    parameters: tuple[ChangeParameter, ...]
    proposed_start: datetime | None
    maintenance_window_start: datetime | None
    maintenance_window_end: datetime | None
    deadline: datetime | None
    preconditions: tuple[str, ...]
    success_criteria: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    rollback_plan: str | None
    current_incident_or_change_reference: str | None
    allowed_data_classes: tuple[str, ...]
    required_freshness_seconds: int
    requested_scenario_kinds: tuple[str, ...]
    audience: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.request_id, "request_id")
        if self.proposed_change_version < 1:
            raise ValueError("proposed_change_version must be a positive, 1-based version")
        if not self.purpose.strip():
            raise ValueError("a change request requires a purpose")
        if not self.expected_outcome.strip():
            raise ValueError("a change request requires an expected outcome")
        if not self.steps:
            raise ValueError("a change request requires at least one step")
        orders = [step.order for step in self.steps]
        if orders != sorted(orders) or len(set(orders)) != len(orders):
            raise ValueError("steps must have a unique, strictly increasing order")
        if not self.target_ids:
            raise ValueError("a change request requires at least one target")
        validate_stable_identifier(self.organization_id, "organization_id")
        validate_stable_identifier(self.environment_id, "environment_id")
        for field_name, value in (
            ("proposed_start", self.proposed_start),
            ("maintenance_window_start", self.maintenance_window_start),
            ("maintenance_window_end", self.maintenance_window_end),
            ("deadline", self.deadline),
        ):
            if value is not None and value.tzinfo is None:
                raise ValueError(f"{field_name} must be timezone-aware")
        if (
            self.maintenance_window_start is not None
            and self.maintenance_window_end is not None
            and self.maintenance_window_end < self.maintenance_window_start
        ):
            raise ValueError("maintenance_window_end must not precede maintenance_window_start")
        if not self.success_criteria:
            raise ValueError("a change request requires at least one success criterion")
        if not self.allowed_data_classes:
            raise ValueError("a change request requires at least one allowed data class")
        if self.required_freshness_seconds < 1:
            raise ValueError("required_freshness_seconds must be positive")
        if not self.audience.strip():
            raise ValueError("a change request requires an audience")


def is_ambiguous_or_materially_incomplete(request: ChangeRequest) -> bool:
    """SS6: "an ambiguous target or materially incomplete plan cannot produce a high-confidence
    impact result." Disambiguating which of several named targets a given step applies to would
    require step-level target scoping this contract does not carry, so the concrete, checkable
    proxy used here is plan completeness: a request with no rollback plan, or no stop condition,
    is materially incomplete regardless of how many targets are named."""
    return request.rollback_plan is None or not request.stop_conditions
