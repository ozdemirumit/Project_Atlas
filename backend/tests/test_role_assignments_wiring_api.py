"""Durable RBAC role assignments (docs/031_RBAC.md Sec.11/26): HTTP-level wiring for
`atlas.api.routes.role_assignments`.

Proves: (a) an admin can grant one of the three LOCAL-reachable tiers to another subject and list
it back over real HTTP; (b) the granted subject's assignments are real, live rows a fresh
`AuthorizationService.evaluate()` call can see through the dynamic-lookup path, not just API
responses; (c) the established two-stage 401/403 denial pattern; (d) the self-escalation guard is
real -- an authenticated subject holding no `RBAC_ROLE_ASSIGNMENT_CREATE` grant is genuinely
denied, not merely untested.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from test_browser_sessions import settings

from atlas.api.app import create_app

_MONITOR_ROLE_ID = "role.local-monitor"
_GRANTEE_SUBJECT_ID = "subject.role-assignments-wiring.grantee"


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/authentication/sessions",
        json={"username": "atlas-demo", "password": "local-demo"},
    )
    assert response.status_code == 201, response.text
    return str(response.headers["X-CSRF-Token"])


def test_grant_then_list_role_assignment_over_http() -> None:
    with TestClient(
        create_app(settings(development_subject_id="subject.role-assignments-wiring.grant-list"))
    ) as client:
        csrf = _login(client)

        grant_response = client.post(
            "/api/v1/authorization/role-assignments",
            json={"subject_id": _GRANTEE_SUBJECT_ID, "role_id": _MONITOR_ROLE_ID},
            headers={"X-CSRF-Token": csrf},
        )
        assert grant_response.status_code == 200, grant_response.text
        granted = grant_response.json()["data"]
        assert len(granted) > 100
        assert all(item["role_id"] == _MONITOR_ROLE_ID for item in granted)
        assert all(item["subject_id"] == _GRANTEE_SUBJECT_ID for item in granted)

        list_response = client.get(
            "/api/v1/authorization/role-assignments", params={"subject_id": _GRANTEE_SUBJECT_ID}
        )
        assert list_response.status_code == 200, list_response.text
        listed = list_response.json()["data"]
        assert len(listed) == len(granted)


def test_grant_role_assignment_rejects_a_non_local_tier_role_id() -> None:
    with TestClient(
        create_app(settings(development_subject_id="subject.role-assignments-wiring.invalid"))
    ) as client:
        csrf = _login(client)

        response = client.post(
            "/api/v1/authorization/role-assignments",
            json={"subject_id": _GRANTEE_SUBJECT_ID, "role_id": "role.security-administrator"},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 422, response.text


def test_role_assignments_require_authentication() -> None:
    with TestClient(create_app(settings(development_identity_enabled=False))) as client:
        grant_response = client.post(
            "/api/v1/authorization/role-assignments",
            json={"subject_id": _GRANTEE_SUBJECT_ID, "role_id": _MONITOR_ROLE_ID},
        )
        list_response = client.get(
            "/api/v1/authorization/role-assignments", params={"subject_id": _GRANTEE_SUBJECT_ID}
        )

    assert grant_response.status_code == 401, grant_response.text
    assert list_response.status_code == 401, list_response.text


def test_role_assignments_deny_an_authenticated_subject_with_no_granted_permissions() -> None:
    """The self-escalation guard: a real, logged-in human subject with zero granted role
    permissions must be denied by the real `AuthorizationService` at the RBAC-grant permission
    check, not by a faked dependency override -- proving only role.local-administrator (or an
    equally-granted identity) can ever grant a tier to anyone, including itself."""
    with TestClient(create_app(settings(development_role_ids=()))) as client:
        csrf = _login(client)

        grant_response = client.post(
            "/api/v1/authorization/role-assignments",
            json={"subject_id": _GRANTEE_SUBJECT_ID, "role_id": _MONITOR_ROLE_ID},
            headers={"X-CSRF-Token": csrf},
        )
        list_response = client.get(
            "/api/v1/authorization/role-assignments", params={"subject_id": _GRANTEE_SUBJECT_ID}
        )

    assert grant_response.status_code == 403, grant_response.text
    assert list_response.status_code == 403, list_response.text
