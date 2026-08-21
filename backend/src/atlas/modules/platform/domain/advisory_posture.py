from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass

ADVISORY_ONLY_CONTRACT_ID = "platform-posture.advisory-only"
ADVISORY_ONLY_CONTRACT_VERSION = "1.0.0"
OPERATIONAL_ENABLEMENT_ENVIRONMENT_KEYS = (
    "ATLAS_OPERATIONAL_EXECUTION_ENABLED",
    "ATLAS_PROCESS_RESUME_CONSUMPTION_ENABLED",
    "ATLAS_WORKFLOW_DISPATCH_ENABLED",
    "ATLAS_INFRASTRUCTURE_MUTATION_ENABLED",
)
_DISABLED_VALUES = frozenset({"", "0", "false", "no", "off", "disabled"})
_PROHIBITED_COMPONENT_NAME_FRAGMENTS = (
    "operational_execution",
    "infrastructure_mutation",
    "process_resume_consumption",
    "process_resumer",
    "process_dispatcher",
    "runtime_executor",
)


@dataclass(frozen=True, slots=True)
class AdvisoryOnlyPosture:
    contract_id: str
    contract_version: str
    platform_mode: str
    operational_execution_enabled: bool
    process_resume_consumption_enabled: bool
    dispatch_enabled: bool
    infrastructure_mutation_enabled: bool
    ai_execution_authorized: bool
    contract_digest: str


class AdvisoryOnlyBoundaryViolation(RuntimeError):
    """Raised when application composition attempts to cross the advisory-only boundary."""


def build_advisory_only_posture() -> AdvisoryOnlyPosture:
    payload: dict[str, str | bool] = {
        "contract_id": ADVISORY_ONLY_CONTRACT_ID,
        "contract_version": ADVISORY_ONLY_CONTRACT_VERSION,
        "platform_mode": "advisory_only",
        "operational_execution_enabled": False,
        "process_resume_consumption_enabled": False,
        "dispatch_enabled": False,
        "infrastructure_mutation_enabled": False,
        "ai_execution_authorized": False,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()
    return AdvisoryOnlyPosture(
        contract_id=ADVISORY_ONLY_CONTRACT_ID,
        contract_version=ADVISORY_ONLY_CONTRACT_VERSION,
        platform_mode="advisory_only",
        operational_execution_enabled=False,
        process_resume_consumption_enabled=False,
        dispatch_enabled=False,
        infrastructure_mutation_enabled=False,
        ai_execution_authorized=False,
        contract_digest=digest,
    )


def assert_advisory_only_composition(
    *,
    environment: Mapping[str, str] | None = None,
) -> AdvisoryOnlyPosture:
    values = os.environ if environment is None else environment
    unsafe_keys = tuple(
        key
        for key in OPERATIONAL_ENABLEMENT_ENVIRONMENT_KEYS
        if key in values and values[key].strip().lower() not in _DISABLED_VALUES
    )
    if unsafe_keys:
        raise AdvisoryOnlyBoundaryViolation(
            "operational execution cannot be enabled in advisory-only mode"
        )

    posture = build_advisory_only_posture()
    if any(
        (
            posture.operational_execution_enabled,
            posture.process_resume_consumption_enabled,
            posture.dispatch_enabled,
            posture.infrastructure_mutation_enabled,
            posture.ai_execution_authorized,
        )
    ):
        raise AdvisoryOnlyBoundaryViolation("advisory-only posture is internally inconsistent")
    return posture


def assert_advisory_only_component_registry(
    component_registry: Mapping[str, object],
) -> None:
    for name, component in component_registry.items():
        normalized_name = name.strip().lower()
        normalized_type = type(component).__name__.lower()
        named_as_operational = any(
            fragment in normalized_name or fragment in normalized_type
            for fragment in _PROHIBITED_COMPONENT_NAME_FRAGMENTS
        )
        marked_as_operational = (
            getattr(type(component), "operational_execution_component", False) is True
        )
        if named_as_operational or marked_as_operational:
            raise AdvisoryOnlyBoundaryViolation(
                "operational execution components cannot be registered in advisory-only mode"
            )
