"""Regression test for a real bug a user hit on their own server: `scripts/bootstrap_admin.py`
granted a brand-new administrator zero role-assignment rows for its chosen tier, leaving the
account authenticated but authorized for nothing (the exact "Identity could not be verified"
failure). Root cause: the script's own `Settings()` reads `.env` directly, where
`ATLAS_DEVELOPMENT_IDENTITY_ENABLED=false` is the correct, secure default for a real deployment --
unlike the *running backend*, which only ever sees `true` as a process-only override from
install.ps1/start.ps1. `AuthorizationService`'s static assignment list (the one
`static_role_scopes(DEVELOPMENT_ROLE_ID)` reads) is empty unless `development_identity_enabled`
is true, so the script silently derived zero scopes to grant. `_local_tier_scopes` must force
that override for its own internal scope computation regardless of what `.env` says.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from types import ModuleType

from atlas.core.audit import LoggingAuditSink
from atlas.core.config import Settings
from atlas.modules.authorization.application.bootstrap import (
    build_development_authorization_service,
)


def _load_bootstrap_admin_module() -> ModuleType:
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "bootstrap_admin.py"
    spec = importlib.util.spec_from_file_location("bootstrap_admin_under_test", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_local_tier_scopes_is_non_empty_even_when_dot_env_disables_development_identity() -> None:
    """The exact failure mode the user hit: a real .env with development identity disabled
    (the correct, secure default) must not silently starve the grant of any scopes."""
    module = _load_bootstrap_admin_module()
    audit_sink = LoggingAuditSink(logging.getLogger("test.bootstrap_admin"))

    # Sanity-check the premise: with development identity disabled, the *unforced* static list
    # really is empty -- otherwise this test would not be exercising the bug it guards against.
    unforced_settings = Settings(environment="development", development_identity_enabled=False)
    unforced_service = build_development_authorization_service(unforced_settings, audit_sink)
    assert unforced_service.static_role_scopes("role.development.operator") == ()

    scopes = module._local_tier_scopes("organization.development", audit_sink)
    assert len(scopes) > 100


def test_local_tier_scopes_uses_the_given_organization_id() -> None:
    module = _load_bootstrap_admin_module()
    audit_sink = LoggingAuditSink(logging.getLogger("test.bootstrap_admin"))

    scopes = module._local_tier_scopes("organization.custom-test", audit_sink)
    assert scopes
    assert all(scope.organization_id == "organization.custom-test" for scope in scopes)
