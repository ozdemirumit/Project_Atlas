"""ATLAS-031 SS9/SS10: the eleven baseline roles and the baseline permission matrix.

The generic RBAC engine (`domain/models.py`'s `PermissionDefinition`/`RoleDefinition`/
`RoleAssignment`/`AuthorizationRequest`/`AuthorizationDecision`) was already real and well-tested
before this module -- what was missing was SS9's own eleven-role catalog and SS10's fourteen-area
permission matrix as actual, tested `RoleDefinition`s, matching the same "doc's own default
catalog realized as tested code" pattern `policy_engine.domain.default_capability_policies`
already establishes for ATLAS-025 SS11.

SS10's matrix rows are permission *areas* ("Connector package lifecycle", "Restricted export"),
not single atomic permissions -- SS6 says permissions are atomic
(`<resource-domain>.<action>[.<qualifier>]`). Each area below maps to one representative atomic
permission id, reusing SS6's own worked examples wherever it gives one
(`connector.execute.read`, `connector.execute.diagnostic`, `knowledge.publish`, `workflow.design`,
`policy.publish`, `approval.decide`, `audit.read`, `audit.export`, `connector.install`,
`inventory.read`); the rest follow the same naming convention. This is the closest faithful
approximation of a qualitative matrix as one real permission each, not a claim that these are the
only permissions each area will ever contain.

SS10's own table only has eight of SS9's eleven role columns (Platform Administrator, Security
Administrator, Connector Administrator, Knowledge Manager, Infrastructure Engineer, Approver,
Auditor, Read-Only Viewer). Workflow Designer, Infrastructure Architect, and Operations Analyst
are reasoned from their SS9 "primary responsibility"/"notable restrictions" text rather than
copied from a table row that does not exist for them -- each is called out below, not silently
invented. Every one of the eleven baseline roles grants `general_scoped_read` (SS10's row is `A`
for every column) and none grants `c2_diagnostic_execution` or `c3_c5_execution` as an automatic
`A`, matching SS10's own closing rule: "No Atlas role grants C2 operational dispatch or C3-C5
execution."
"""

from __future__ import annotations

from enum import StrEnum

from atlas.modules.authorization.domain.models import RoleDefinition


class BaselineRoleId(StrEnum):
    """SS9's eleven baseline composite roles."""

    PLATFORM_ADMINISTRATOR = "role.platform-administrator"
    SECURITY_ADMINISTRATOR = "role.security-administrator"
    CONNECTOR_ADMINISTRATOR = "role.connector-administrator"
    KNOWLEDGE_MANAGER = "role.knowledge-manager"
    WORKFLOW_DESIGNER = "role.workflow-designer"
    INFRASTRUCTURE_ARCHITECT = "role.infrastructure-architect"
    INFRASTRUCTURE_ENGINEER = "role.infrastructure-engineer"
    OPERATIONS_ANALYST = "role.operations-analyst"
    APPROVER = "role.approver"
    AUDITOR = "role.auditor"
    READ_ONLY_VIEWER = "role.read-only-viewer"


class BaselinePermissionArea(StrEnum):
    """SS10's fourteen permission-area rows."""

    PLATFORM_CONFIGURATION = "platform_configuration"
    IDENTITY_AND_ROLE_ADMINISTRATION = "identity_and_role_administration"
    CONNECTOR_PACKAGE_LIFECYCLE = "connector_package_lifecycle"
    CONNECTOR_CREDENTIAL_REFERENCE = "connector_credential_reference"
    C0_C1_CAPABILITY_EXECUTION = "c0_c1_capability_execution"
    C2_DIAGNOSTIC_EXECUTION = "c2_diagnostic_execution"
    C3_C5_EXECUTION = "c3_c5_execution"
    KNOWLEDGE_ADMINISTRATION = "knowledge_administration"
    WORKFLOW_DESIGN = "workflow_design"
    POLICY_PUBLICATION = "policy_publication"
    APPROVAL_DECISION = "approval_decision"
    AUDIT_READ = "audit_read"
    RESTRICTED_EXPORT = "restricted_export"
    GENERAL_SCOPED_READ = "general_scoped_read"


#: One representative atomic permission id per SS10 area (see module docstring for rationale).
BASELINE_PERMISSION_FOR_AREA: dict[BaselinePermissionArea, str] = {
    BaselinePermissionArea.PLATFORM_CONFIGURATION: "platform.configure",
    BaselinePermissionArea.IDENTITY_AND_ROLE_ADMINISTRATION: "identity.role.administer",
    BaselinePermissionArea.CONNECTOR_PACKAGE_LIFECYCLE: "connector.install",
    BaselinePermissionArea.CONNECTOR_CREDENTIAL_REFERENCE: "connector.credential.reference",
    BaselinePermissionArea.C0_C1_CAPABILITY_EXECUTION: "connector.execute.read",
    BaselinePermissionArea.C2_DIAGNOSTIC_EXECUTION: "connector.execute.diagnostic",
    BaselinePermissionArea.C3_C5_EXECUTION: "connector.execute.change",
    BaselinePermissionArea.KNOWLEDGE_ADMINISTRATION: "knowledge.publish",
    BaselinePermissionArea.WORKFLOW_DESIGN: "workflow.design",
    BaselinePermissionArea.POLICY_PUBLICATION: "policy.publish",
    BaselinePermissionArea.APPROVAL_DECISION: "approval.decide",
    BaselinePermissionArea.AUDIT_READ: "audit.read",
    BaselinePermissionArea.RESTRICTED_EXPORT: "audit.export",
    BaselinePermissionArea.GENERAL_SCOPED_READ: "inventory.read",
}


class MatrixCell(StrEnum):
    """SS10's legend: `A` allowed by role, `S` separately assigned, `-` not included."""

    ALLOWED = "allowed"
    SEPARATELY_ASSIGNED = "separately_assigned"
    NOT_INCLUDED = "not_included"


_A = MatrixCell.ALLOWED
_S = MatrixCell.SEPARATELY_ASSIGNED
_N = MatrixCell.NOT_INCLUDED
_AREA = BaselinePermissionArea

#: SS10's baseline permission matrix, transcribed exactly for the eight roles its own table
#: names, plus the three (Workflow Designer, Infrastructure Architect, Operations Analyst)
#: reasoned from SS9 -- see the module docstring for how each of those three was derived.
BASELINE_PERMISSION_MATRIX: dict[BaselineRoleId, dict[BaselinePermissionArea, MatrixCell]] = {
    BaselineRoleId.PLATFORM_ADMINISTRATOR: {
        _AREA.PLATFORM_CONFIGURATION: _A,
        _AREA.IDENTITY_AND_ROLE_ADMINISTRATION: _S,
        _AREA.CONNECTOR_PACKAGE_LIFECYCLE: _S,
        _AREA.CONNECTOR_CREDENTIAL_REFERENCE: _S,
        _AREA.C0_C1_CAPABILITY_EXECUTION: _S,
        _AREA.C2_DIAGNOSTIC_EXECUTION: _N,
        _AREA.C3_C5_EXECUTION: _N,
        _AREA.KNOWLEDGE_ADMINISTRATION: _S,
        _AREA.WORKFLOW_DESIGN: _S,
        _AREA.POLICY_PUBLICATION: _S,
        _AREA.APPROVAL_DECISION: _N,
        _AREA.AUDIT_READ: _S,
        _AREA.RESTRICTED_EXPORT: _S,
        _AREA.GENERAL_SCOPED_READ: _A,
    },
    BaselineRoleId.SECURITY_ADMINISTRATOR: {
        _AREA.PLATFORM_CONFIGURATION: _S,
        _AREA.IDENTITY_AND_ROLE_ADMINISTRATION: _A,
        _AREA.CONNECTOR_PACKAGE_LIFECYCLE: _S,
        _AREA.CONNECTOR_CREDENTIAL_REFERENCE: _S,
        _AREA.C0_C1_CAPABILITY_EXECUTION: _N,
        _AREA.C2_DIAGNOSTIC_EXECUTION: _N,
        _AREA.C3_C5_EXECUTION: _N,
        _AREA.KNOWLEDGE_ADMINISTRATION: _N,
        _AREA.WORKFLOW_DESIGN: _N,
        _AREA.POLICY_PUBLICATION: _A,
        _AREA.APPROVAL_DECISION: _N,
        _AREA.AUDIT_READ: _S,
        _AREA.RESTRICTED_EXPORT: _S,
        _AREA.GENERAL_SCOPED_READ: _A,
    },
    BaselineRoleId.CONNECTOR_ADMINISTRATOR: {
        _AREA.PLATFORM_CONFIGURATION: _N,
        _AREA.IDENTITY_AND_ROLE_ADMINISTRATION: _N,
        _AREA.CONNECTOR_PACKAGE_LIFECYCLE: _A,
        _AREA.CONNECTOR_CREDENTIAL_REFERENCE: _A,
        _AREA.C0_C1_CAPABILITY_EXECUTION: _S,
        _AREA.C2_DIAGNOSTIC_EXECUTION: _S,
        _AREA.C3_C5_EXECUTION: _N,
        _AREA.KNOWLEDGE_ADMINISTRATION: _N,
        _AREA.WORKFLOW_DESIGN: _N,
        _AREA.POLICY_PUBLICATION: _N,
        _AREA.APPROVAL_DECISION: _N,
        _AREA.AUDIT_READ: _N,
        _AREA.RESTRICTED_EXPORT: _N,
        _AREA.GENERAL_SCOPED_READ: _A,
    },
    BaselineRoleId.KNOWLEDGE_MANAGER: {
        _AREA.PLATFORM_CONFIGURATION: _N,
        _AREA.IDENTITY_AND_ROLE_ADMINISTRATION: _N,
        _AREA.CONNECTOR_PACKAGE_LIFECYCLE: _N,
        _AREA.CONNECTOR_CREDENTIAL_REFERENCE: _N,
        _AREA.C0_C1_CAPABILITY_EXECUTION: _N,
        _AREA.C2_DIAGNOSTIC_EXECUTION: _N,
        _AREA.C3_C5_EXECUTION: _N,
        _AREA.KNOWLEDGE_ADMINISTRATION: _A,
        _AREA.WORKFLOW_DESIGN: _S,
        _AREA.POLICY_PUBLICATION: _N,
        _AREA.APPROVAL_DECISION: _N,
        _AREA.AUDIT_READ: _N,
        _AREA.RESTRICTED_EXPORT: _S,
        _AREA.GENERAL_SCOPED_READ: _A,
    },
    # SS10 has no dedicated column for Workflow Designer. Reasoned from SS9: its primary
    # responsibility is workflow creation and testing, so WORKFLOW_DESIGN is A here (unlike
    # Knowledge Manager's and Infrastructure Engineer's S) -- but SS9's own restriction, "cannot
    # publish or execute consequential workflows by default," has no separate matrix row to
    # express, so it is not modeled as a distinct denial here; it constrains a permission this
    # matrix does not yet enumerate.
    BaselineRoleId.WORKFLOW_DESIGNER: {
        _AREA.PLATFORM_CONFIGURATION: _N,
        _AREA.IDENTITY_AND_ROLE_ADMINISTRATION: _N,
        _AREA.CONNECTOR_PACKAGE_LIFECYCLE: _N,
        _AREA.CONNECTOR_CREDENTIAL_REFERENCE: _N,
        _AREA.C0_C1_CAPABILITY_EXECUTION: _N,
        _AREA.C2_DIAGNOSTIC_EXECUTION: _N,
        _AREA.C3_C5_EXECUTION: _N,
        _AREA.KNOWLEDGE_ADMINISTRATION: _N,
        _AREA.WORKFLOW_DESIGN: _A,
        _AREA.POLICY_PUBLICATION: _N,
        _AREA.APPROVAL_DECISION: _N,
        _AREA.AUDIT_READ: _N,
        _AREA.RESTRICTED_EXPORT: _N,
        _AREA.GENERAL_SCOPED_READ: _A,
    },
    # SS10 has no dedicated column for Infrastructure Architect. Reasoned from SS9: an analysis
    # role over topology/impact/recommendations/reports with "no platform or credential
    # administration by default" -- every specific area is N, matching a purely analytical role
    # that the matrix's own areas do not otherwise name a permission for.
    BaselineRoleId.INFRASTRUCTURE_ARCHITECT: {
        _AREA.PLATFORM_CONFIGURATION: _N,
        _AREA.IDENTITY_AND_ROLE_ADMINISTRATION: _N,
        _AREA.CONNECTOR_PACKAGE_LIFECYCLE: _N,
        _AREA.CONNECTOR_CREDENTIAL_REFERENCE: _N,
        _AREA.C0_C1_CAPABILITY_EXECUTION: _N,
        _AREA.C2_DIAGNOSTIC_EXECUTION: _N,
        _AREA.C3_C5_EXECUTION: _N,
        _AREA.KNOWLEDGE_ADMINISTRATION: _N,
        _AREA.WORKFLOW_DESIGN: _N,
        _AREA.POLICY_PUBLICATION: _N,
        _AREA.APPROVAL_DECISION: _N,
        _AREA.AUDIT_READ: _N,
        _AREA.RESTRICTED_EXPORT: _N,
        _AREA.GENERAL_SCOPED_READ: _A,
    },
    BaselineRoleId.INFRASTRUCTURE_ENGINEER: {
        _AREA.PLATFORM_CONFIGURATION: _N,
        _AREA.IDENTITY_AND_ROLE_ADMINISTRATION: _N,
        _AREA.CONNECTOR_PACKAGE_LIFECYCLE: _N,
        _AREA.CONNECTOR_CREDENTIAL_REFERENCE: _N,
        _AREA.C0_C1_CAPABILITY_EXECUTION: _A,
        _AREA.C2_DIAGNOSTIC_EXECUTION: _S,
        _AREA.C3_C5_EXECUTION: _S,
        _AREA.KNOWLEDGE_ADMINISTRATION: _N,
        _AREA.WORKFLOW_DESIGN: _S,
        _AREA.POLICY_PUBLICATION: _N,
        _AREA.APPROVAL_DECISION: _N,
        _AREA.AUDIT_READ: _N,
        _AREA.RESTRICTED_EXPORT: _S,
        _AREA.GENERAL_SCOPED_READ: _A,
    },
    # SS10 has no dedicated column for Operations Analyst. Reasoned from SS9: "read and bounded
    # diagnostic access only by default" -- unlike Infrastructure Engineer, C0/C1 execution is
    # not granted outright (this role reviews, it does not run capabilities); C2 diagnostic
    # access is S, matching "bounded" rather than an automatic grant.
    BaselineRoleId.OPERATIONS_ANALYST: {
        _AREA.PLATFORM_CONFIGURATION: _N,
        _AREA.IDENTITY_AND_ROLE_ADMINISTRATION: _N,
        _AREA.CONNECTOR_PACKAGE_LIFECYCLE: _N,
        _AREA.CONNECTOR_CREDENTIAL_REFERENCE: _N,
        _AREA.C0_C1_CAPABILITY_EXECUTION: _N,
        _AREA.C2_DIAGNOSTIC_EXECUTION: _S,
        _AREA.C3_C5_EXECUTION: _N,
        _AREA.KNOWLEDGE_ADMINISTRATION: _N,
        _AREA.WORKFLOW_DESIGN: _N,
        _AREA.POLICY_PUBLICATION: _N,
        _AREA.APPROVAL_DECISION: _N,
        _AREA.AUDIT_READ: _N,
        _AREA.RESTRICTED_EXPORT: _N,
        _AREA.GENERAL_SCOPED_READ: _A,
    },
    BaselineRoleId.APPROVER: {
        _AREA.PLATFORM_CONFIGURATION: _N,
        _AREA.IDENTITY_AND_ROLE_ADMINISTRATION: _N,
        _AREA.CONNECTOR_PACKAGE_LIFECYCLE: _N,
        _AREA.CONNECTOR_CREDENTIAL_REFERENCE: _N,
        _AREA.C0_C1_CAPABILITY_EXECUTION: _N,
        _AREA.C2_DIAGNOSTIC_EXECUTION: _N,
        _AREA.C3_C5_EXECUTION: _N,
        _AREA.KNOWLEDGE_ADMINISTRATION: _N,
        _AREA.WORKFLOW_DESIGN: _N,
        _AREA.POLICY_PUBLICATION: _N,
        _AREA.APPROVAL_DECISION: _A,
        _AREA.AUDIT_READ: _N,
        _AREA.RESTRICTED_EXPORT: _N,
        _AREA.GENERAL_SCOPED_READ: _A,
    },
    BaselineRoleId.AUDITOR: {
        _AREA.PLATFORM_CONFIGURATION: _N,
        _AREA.IDENTITY_AND_ROLE_ADMINISTRATION: _N,
        _AREA.CONNECTOR_PACKAGE_LIFECYCLE: _N,
        _AREA.CONNECTOR_CREDENTIAL_REFERENCE: _N,
        _AREA.C0_C1_CAPABILITY_EXECUTION: _N,
        _AREA.C2_DIAGNOSTIC_EXECUTION: _N,
        _AREA.C3_C5_EXECUTION: _N,
        _AREA.KNOWLEDGE_ADMINISTRATION: _N,
        _AREA.WORKFLOW_DESIGN: _N,
        _AREA.POLICY_PUBLICATION: _N,
        _AREA.APPROVAL_DECISION: _N,
        _AREA.AUDIT_READ: _A,
        _AREA.RESTRICTED_EXPORT: _A,
        _AREA.GENERAL_SCOPED_READ: _A,
    },
    BaselineRoleId.READ_ONLY_VIEWER: {
        _AREA.PLATFORM_CONFIGURATION: _N,
        _AREA.IDENTITY_AND_ROLE_ADMINISTRATION: _N,
        _AREA.CONNECTOR_PACKAGE_LIFECYCLE: _N,
        _AREA.CONNECTOR_CREDENTIAL_REFERENCE: _N,
        _AREA.C0_C1_CAPABILITY_EXECUTION: _N,
        _AREA.C2_DIAGNOSTIC_EXECUTION: _N,
        _AREA.C3_C5_EXECUTION: _N,
        _AREA.KNOWLEDGE_ADMINISTRATION: _N,
        _AREA.WORKFLOW_DESIGN: _N,
        _AREA.POLICY_PUBLICATION: _N,
        _AREA.APPROVAL_DECISION: _N,
        _AREA.AUDIT_READ: _N,
        _AREA.RESTRICTED_EXPORT: _N,
        _AREA.GENERAL_SCOPED_READ: _A,
    },
}


def baseline_role_definition(role_id: BaselineRoleId, *, version: int = 1) -> RoleDefinition:
    """Builds one baseline role's `RoleDefinition` from the matrix -- only its `A` (allowed by
    default) cells become real permissions; `S` (separately assigned) and `-` (not included) do
    not, matching SS10's own "S permissions require explicit role composition and review.\""""
    row = BASELINE_PERMISSION_MATRIX[role_id]
    permissions = frozenset(
        BASELINE_PERMISSION_FOR_AREA[area] for area, cell in row.items() if cell is _A
    )
    return RoleDefinition(role_id=role_id.value, version=version, permissions=permissions)


def baseline_role_definitions(*, version: int = 1) -> tuple[RoleDefinition, ...]:
    """All eleven baseline roles, in SS9's own listed order."""
    return tuple(baseline_role_definition(role_id, version=version) for role_id in BaselineRoleId)


def a_baseline_role_grants_c2_dispatch_or_c3_c5_execution_by_default() -> bool:
    """SS10: "No Atlas role grants C2 operational dispatch or C3-C5 execution." Computed from
    the real matrix above rather than hardcoded, so a future matrix edit that violated this rule
    would fail the invariant test immediately."""
    restricted = (
        BaselinePermissionArea.C2_DIAGNOSTIC_EXECUTION,
        BaselinePermissionArea.C3_C5_EXECUTION,
    )
    return any(
        BASELINE_PERMISSION_MATRIX[role_id][area] is _A
        for role_id in BaselineRoleId
        for area in restricted
    )
