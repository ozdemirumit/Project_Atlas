from __future__ import annotations

import pytest

from atlas.core.capabilities import CapabilityClass
from atlas.modules.itsm.domain.models import ItsmAllowedOperation
from atlas.modules.itsm.domain.operations import (
    ItsmOperationDirection,
    every_outbound_operation_has_an_assigned_capability_class,
    operation_capability_class,
    operation_direction,
)


def test_operation_has_thirteen_members() -> None:
    assert len(ItsmAllowedOperation) == 13


def test_every_operation_has_a_capability_class() -> None:
    for operation in ItsmAllowedOperation:
        assert operation_capability_class(operation) in CapabilityClass


def test_every_outbound_operation_has_an_assigned_capability_class() -> None:
    assert every_outbound_operation_has_an_assigned_capability_class() is True


@pytest.mark.parametrize(
    "operation",
    [
        ItsmAllowedOperation.RETRIEVE_RECORD,
        ItsmAllowedOperation.READ_RECORD_STATE,
        ItsmAllowedOperation.RECEIVE_CHANGE_NOTIFICATION,
        ItsmAllowedOperation.RETRIEVE_RECORD_HISTORY,
        ItsmAllowedOperation.RETRIEVE_CONFIGURATION_ITEMS,
        ItsmAllowedOperation.VALIDATE_RECORD_CURRENT,
    ],
)
def test_inbound_operations_are_classified_inbound(operation: ItsmAllowedOperation) -> None:
    assert operation_direction(operation) is ItsmOperationDirection.INBOUND


@pytest.mark.parametrize(
    "operation",
    [
        ItsmAllowedOperation.APPEND_ANALYSIS,
        ItsmAllowedOperation.CREATE_INCIDENT_DRAFT,
        ItsmAllowedOperation.LINK_EVIDENCE_REFERENCE,
        ItsmAllowedOperation.CREATE_OR_UPDATE_TASK,
        ItsmAllowedOperation.ATTACH_EVIDENCE_PACKAGE,
        ItsmAllowedOperation.RECORD_WORKFLOW_OUTCOME,
        ItsmAllowedOperation.UPDATE_INTEGRATION_OWNED_FIELD,
    ],
)
def test_outbound_operations_are_classified_outbound(operation: ItsmAllowedOperation) -> None:
    assert operation_direction(operation) is ItsmOperationDirection.OUTBOUND
