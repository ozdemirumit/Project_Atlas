"""ATLAS-030 SS11 end to end over real HTTP: a freshly bootstrapped local administrator can
authenticate while `MUST_REPLACE`, read its own restricted identity, replace its temporary
password, and only then actually holds its real role tier -- closing the loop this session's
`scripts/bootstrap_admin` was built for. Reproduces, as an automated test, the exact "Identity
could not be verified" failure a real user hit before the RoleAssignment/role-tier work landed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import settings

from atlas.api.app import create_app
from atlas.modules.authorization.application.bootstrap import (
    DEVELOPMENT_ROLE_ID,
    current_identity_scope,
    local_credential_self_scope,
)
from atlas.modules.authorization.domain.models import CapabilityClass, RoleAssignment
from atlas.modules.identity.application.local_credentials import BOOTSTRAP_SETUP_ROLE_ID

_SUBJECT_ID = "subject.local-credential-replace-wiring.admin"
_TEMPORARY_PASSWORD = "TemporaryBootstrapPass1!"
_FINAL_PASSWORD = "FinalAdministratorPass2!"


async def _bootstrap(app, organization_id: str, environment: str) -> None:
    credential_service = app.state.local_credential_service
    await credential_service.bootstrap_administrator(
        subject_id=_SUBJECT_ID,
        organization_id=organization_id,
        display_name="Wiring Test Admin",
        role_ids=("role.local-administrator",),
        password=_TEMPORARY_PASSWORD,
        deployment_ownership_verified=True,
        correlation_id=f"cor_{uuid4().hex}",
    )
    role_assignment_repository = app.state.role_assignment_grant_service._repository
    authorization_service = app.state.authorization_service
    now = datetime.now(UTC)
    for scope in (
        current_identity_scope(organization_id, environment),
        local_credential_self_scope(
            organization_id, environment, CapabilityClass.C3_CONTROLLED_CHANGE
        ),
    ):
        await role_assignment_repository.create(
            RoleAssignment(
                assignment_id=f"assignment.{uuid4().hex}",
                version=1,
                subject_id=_SUBJECT_ID,
                role_id=BOOTSTRAP_SETUP_ROLE_ID,
                scope=scope,
                valid_from=now,
            )
        )
    for scope in authorization_service.static_role_scopes(DEVELOPMENT_ROLE_ID):
        await role_assignment_repository.create(
            RoleAssignment(
                assignment_id=f"assignment.{uuid4().hex}",
                version=1,
                subject_id=_SUBJECT_ID,
                role_id="role.local-administrator",
                scope=scope,
                valid_from=now,
            )
        )


@pytest.mark.asyncio
async def test_bootstrap_administrator_reaches_its_real_role_after_replacing_its_password() -> None:
    resolved_settings = settings(
        development_subject_id="subject.local-credential-replace-wiring.dev-operator"
    )
    app = create_app(resolved_settings)
    with TestClient(app) as client:
        await _bootstrap(
            app, resolved_settings.development_organization_id, resolved_settings.environment
        )

        login_1 = client.post(
            "/api/v1/authentication/sessions",
            json={"username": _SUBJECT_ID, "password": _TEMPORARY_PASSWORD},
        )
        assert login_1.status_code == 201, login_1.text
        csrf_1 = login_1.headers["X-CSRF-Token"]

        identity_before = client.get("/api/v1/identity/me")
        assert identity_before.status_code == 200, identity_before.text
        assert identity_before.json()["data"]["role_ids"] == [BOOTSTRAP_SETUP_ROLE_ID]

        replace = client.post(
            "/api/v1/identity/local-credential/replace",
            json={"current_password": _TEMPORARY_PASSWORD, "new_password": _FINAL_PASSWORD},
            headers={"X-CSRF-Token": csrf_1},
        )
        assert replace.status_code == 200, replace.text
        assert replace.json()["data"]["state"] == "active"

        client.cookies.clear()
        login_2 = client.post(
            "/api/v1/authentication/sessions",
            json={"username": _SUBJECT_ID, "password": _FINAL_PASSWORD},
        )
        assert login_2.status_code == 201, login_2.text

        identity_after = client.get("/api/v1/identity/me")
        assert identity_after.status_code == 200, identity_after.text
        assert identity_after.json()["data"]["role_ids"] == ["role.local-administrator"]


def test_local_credential_replace_requires_authentication() -> None:
    with TestClient(create_app(settings(development_identity_enabled=False))) as client:
        response = client.post(
            "/api/v1/identity/local-credential/replace",
            json={"current_password": "whatever12345", "new_password": "somethingelse123"},
        )
    assert response.status_code == 401, response.text


@pytest.mark.asyncio
async def test_local_credential_replace_rejects_the_wrong_current_password() -> None:
    resolved_settings = settings(
        development_subject_id="subject.local-credential-replace-wiring.wrong-password"
    )
    app = create_app(resolved_settings)
    with TestClient(app) as client:
        await _bootstrap(
            app, resolved_settings.development_organization_id, resolved_settings.environment
        )
        login = client.post(
            "/api/v1/authentication/sessions",
            json={"username": _SUBJECT_ID, "password": _TEMPORARY_PASSWORD},
        )
        assert login.status_code == 201, login.text
        csrf = login.headers["X-CSRF-Token"]

        response = client.post(
            "/api/v1/identity/local-credential/replace",
            json={
                "current_password": "definitely-the-wrong-password",
                "new_password": _FINAL_PASSWORD,
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 403, response.text
