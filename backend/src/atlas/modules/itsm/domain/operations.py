"""ATLAS-036 SS7: operation direction and governed capability class.

"Every outbound operation is a governed connector capability with an assigned ATLAS-003
capability class" -- reuses `atlas.core.capabilities.CapabilityClass` directly rather than
defining a parallel ITSM-specific risk tier.
"""

from __future__ import annotations

from enum import StrEnum

from atlas.core.capabilities import CapabilityClass
from atlas.modules.itsm.domain.models import ItsmAllowedOperation


class ItsmOperationDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


_INBOUND_OPERATIONS = frozenset(
    {
        ItsmAllowedOperation.RETRIEVE_RECORD,
        ItsmAllowedOperation.READ_RECORD_STATE,
        ItsmAllowedOperation.RECEIVE_CHANGE_NOTIFICATION,
        ItsmAllowedOperation.RETRIEVE_RECORD_HISTORY,
        ItsmAllowedOperation.RETRIEVE_CONFIGURATION_ITEMS,
        ItsmAllowedOperation.VALIDATE_RECORD_CURRENT,
    }
)

_CAPABILITY_CLASS: dict[ItsmAllowedOperation, CapabilityClass] = {
    ItsmAllowedOperation.RETRIEVE_RECORD: CapabilityClass.C1_READ_ONLY,
    ItsmAllowedOperation.READ_RECORD_STATE: CapabilityClass.C1_READ_ONLY,
    ItsmAllowedOperation.RECEIVE_CHANGE_NOTIFICATION: CapabilityClass.C0_INFORMATIONAL,
    ItsmAllowedOperation.RETRIEVE_RECORD_HISTORY: CapabilityClass.C1_READ_ONLY,
    ItsmAllowedOperation.RETRIEVE_CONFIGURATION_ITEMS: CapabilityClass.C1_READ_ONLY,
    ItsmAllowedOperation.VALIDATE_RECORD_CURRENT: CapabilityClass.C1_READ_ONLY,
    ItsmAllowedOperation.APPEND_ANALYSIS: CapabilityClass.C2_DIAGNOSTIC,
    ItsmAllowedOperation.CREATE_INCIDENT_DRAFT: CapabilityClass.C2_DIAGNOSTIC,
    ItsmAllowedOperation.LINK_EVIDENCE_REFERENCE: CapabilityClass.C2_DIAGNOSTIC,
    ItsmAllowedOperation.CREATE_OR_UPDATE_TASK: CapabilityClass.C3_CONTROLLED_CHANGE,
    ItsmAllowedOperation.ATTACH_EVIDENCE_PACKAGE: CapabilityClass.C2_DIAGNOSTIC,
    ItsmAllowedOperation.RECORD_WORKFLOW_OUTCOME: CapabilityClass.C2_DIAGNOSTIC,
    ItsmAllowedOperation.UPDATE_INTEGRATION_OWNED_FIELD: CapabilityClass.C3_CONTROLLED_CHANGE,
}


def operation_direction(operation: ItsmAllowedOperation) -> ItsmOperationDirection:
    return (
        ItsmOperationDirection.INBOUND
        if operation in _INBOUND_OPERATIONS
        else ItsmOperationDirection.OUTBOUND
    )


def operation_capability_class(operation: ItsmAllowedOperation) -> CapabilityClass:
    return _CAPABILITY_CLASS[operation]


def every_outbound_operation_has_an_assigned_capability_class() -> bool:
    return all(
        operation in _CAPABILITY_CLASS
        for operation in ItsmAllowedOperation
        if operation_direction(operation) is ItsmOperationDirection.OUTBOUND
    )
