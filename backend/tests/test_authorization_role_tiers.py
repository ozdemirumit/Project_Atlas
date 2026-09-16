"""Durable RBAC role assignments (docs/031_RBAC.md Sec.11/26): the three LOCAL-reachable role
tiers (admin/operator/monitor) are mechanically derived from DEVELOPMENT_ROLE_ID's own permission
set rather than hand-curated, so this proves the derivation actually holds the invariants it's
supposed to -- not just that it happened to look right once by inspection.
"""

from __future__ import annotations

import logging

from atlas.core.audit import LoggingAuditSink
from atlas.core.config import Settings
from atlas.modules.authorization.application.bootstrap import (
    DEVELOPMENT_ROLE_ID,
    LOCAL_ADMINISTRATOR_ROLE_ID,
    LOCAL_CREDENTIAL_SELF_REPLACE,
    LOCAL_MONITOR_ROLE_ID,
    LOCAL_OPERATOR_ROLE_ID,
    RBAC_ROLE_ASSIGNMENT_CREATE,
    build_development_authorization_service,
)
from atlas.modules.identity.application.local_credentials import BOOTSTRAP_SETUP_ROLE_ID


def _build():
    settings = Settings(environment="test", development_identity_enabled=True)
    return build_development_authorization_service(
        settings, LoggingAuditSink(logging.getLogger("t"))
    )


def test_local_operator_permissions_are_a_strict_subset_of_local_administrator() -> None:
    service = _build()
    admin = service._roles[LOCAL_ADMINISTRATOR_ROLE_ID]
    operator = service._roles[LOCAL_OPERATOR_ROLE_ID]
    assert operator.permissions <= admin.permissions
    assert operator.permissions != admin.permissions


def test_local_monitor_permissions_are_a_strict_subset_of_local_operator() -> None:
    service = _build()
    operator = service._roles[LOCAL_OPERATOR_ROLE_ID]
    monitor = service._roles[LOCAL_MONITOR_ROLE_ID]
    assert monitor.permissions <= operator.permissions
    assert monitor.permissions != operator.permissions


def test_local_monitor_permissions_are_all_read_only_or_self_service() -> None:
    service = _build()
    monitor = service._roles[LOCAL_MONITOR_ROLE_ID]
    for permission_id in monitor.permissions:
        assert permission_id.endswith(".read") or permission_id == LOCAL_CREDENTIAL_SELF_REPLACE


def test_only_local_administrator_can_grant_role_assignments() -> None:
    service = _build()
    admin = service._roles[LOCAL_ADMINISTRATOR_ROLE_ID]
    operator = service._roles[LOCAL_OPERATOR_ROLE_ID]
    monitor = service._roles[LOCAL_MONITOR_ROLE_ID]
    assert RBAC_ROLE_ASSIGNMENT_CREATE in admin.permissions
    assert RBAC_ROLE_ASSIGNMENT_CREATE not in operator.permissions
    assert RBAC_ROLE_ASSIGNMENT_CREATE not in monitor.permissions


def test_bootstrap_setup_role_is_minimal() -> None:
    service = _build()
    role = service._roles[BOOTSTRAP_SETUP_ROLE_ID]
    assert role.permissions == frozenset({"identity.self.read", LOCAL_CREDENTIAL_SELF_REPLACE})


def test_static_role_scopes_returns_a_non_empty_stable_set() -> None:
    service = _build()
    scopes = service.static_role_scopes(DEVELOPMENT_ROLE_ID)
    assert len(scopes) > 100
    # Idempotent and order-independent as a set of references.
    assert {scope.reference for scope in scopes} == {
        scope.reference for scope in service.static_role_scopes(DEVELOPMENT_ROLE_ID)
    }


def test_static_role_scopes_returns_empty_for_an_unknown_role() -> None:
    service = _build()
    assert service.static_role_scopes("role.does-not-exist") == ()
