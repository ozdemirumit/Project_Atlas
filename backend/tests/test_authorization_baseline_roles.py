from __future__ import annotations

from atlas.modules.authorization.domain.baseline_roles import (
    BASELINE_PERMISSION_FOR_AREA,
    BASELINE_PERMISSION_MATRIX,
    BaselinePermissionArea,
    BaselineRoleId,
    a_baseline_role_grants_c2_dispatch_or_c3_c5_execution_by_default,
    baseline_role_definition,
    baseline_role_definitions,
)


def test_eleven_baseline_roles_are_defined() -> None:
    assert len(BaselineRoleId) == 11


def test_fourteen_permission_areas_are_defined() -> None:
    assert len(BaselinePermissionArea) == 14


def test_every_area_has_a_representative_permission() -> None:
    assert set(BASELINE_PERMISSION_FOR_AREA) == set(BaselinePermissionArea)


def test_matrix_covers_every_role_and_every_area() -> None:
    assert set(BASELINE_PERMISSION_MATRIX) == set(BaselineRoleId)
    for role_id in BaselineRoleId:
        assert set(BASELINE_PERMISSION_MATRIX[role_id]) == set(BaselinePermissionArea)


def test_no_baseline_role_grants_c2_or_c3_c5_execution_by_default() -> None:
    assert a_baseline_role_grants_c2_dispatch_or_c3_c5_execution_by_default() is False


def test_baseline_role_definitions_produces_eleven_role_definitions() -> None:
    definitions = baseline_role_definitions()
    assert len(definitions) == 11
    assert {definition.role_id for definition in definitions} == {
        role_id.value for role_id in BaselineRoleId
    }


def test_every_baseline_role_grants_general_scoped_read() -> None:
    for role_id in BaselineRoleId:
        definition = baseline_role_definition(role_id)
        assert "inventory.read" in definition.permissions


def test_security_administrator_grants_identity_and_policy_permissions() -> None:
    definition = baseline_role_definition(BaselineRoleId.SECURITY_ADMINISTRATOR)
    assert "identity.role.administer" in definition.permissions
    assert "policy.publish" in definition.permissions
    assert "connector.execute.read" not in definition.permissions


def test_connector_administrator_grants_lifecycle_and_credential_permissions() -> None:
    definition = baseline_role_definition(BaselineRoleId.CONNECTOR_ADMINISTRATOR)
    assert "connector.install" in definition.permissions
    assert "connector.credential.reference" in definition.permissions
    assert "connector.execute.diagnostic" not in definition.permissions


def test_infrastructure_engineer_grants_c0_c1_but_not_c2_or_c3_c5() -> None:
    definition = baseline_role_definition(BaselineRoleId.INFRASTRUCTURE_ENGINEER)
    assert "connector.execute.read" in definition.permissions
    assert "connector.execute.diagnostic" not in definition.permissions
    assert "connector.execute.change" not in definition.permissions


def test_approver_grants_only_approval_decision_and_general_read() -> None:
    definition = baseline_role_definition(BaselineRoleId.APPROVER)
    assert definition.permissions == frozenset({"approval.decide", "inventory.read"})


def test_auditor_is_read_only_including_restricted_export() -> None:
    definition = baseline_role_definition(BaselineRoleId.AUDITOR)
    assert definition.permissions == frozenset({"audit.read", "audit.export", "inventory.read"})


def test_read_only_viewer_grants_only_general_scoped_read() -> None:
    definition = baseline_role_definition(BaselineRoleId.READ_ONLY_VIEWER)
    assert definition.permissions == frozenset({"inventory.read"})


def test_workflow_designer_grants_workflow_design() -> None:
    definition = baseline_role_definition(BaselineRoleId.WORKFLOW_DESIGNER)
    assert definition.permissions == frozenset({"workflow.design", "inventory.read"})


def test_infrastructure_architect_grants_only_general_scoped_read() -> None:
    definition = baseline_role_definition(BaselineRoleId.INFRASTRUCTURE_ARCHITECT)
    assert definition.permissions == frozenset({"inventory.read"})


def test_operations_analyst_grants_only_general_scoped_read() -> None:
    definition = baseline_role_definition(BaselineRoleId.OPERATIONS_ANALYST)
    assert definition.permissions == frozenset({"inventory.read"})
