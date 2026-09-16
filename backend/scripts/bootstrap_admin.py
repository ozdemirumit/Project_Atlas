"""Create the first durable local administrator account (ATLAS-030 SS11 bootstrap).

Run once, on the server, by someone with shell access -- that is the whole authorization model:
there is deliberately no HTTP endpoint for this, so an attacker who cannot already reach a shell
on the box can never create an administrator account through the API. Requires a configured
``ATLAS_DATABASE_URL`` (see ``.env``); without one, the account would only live in process memory
and vanish the moment this script exits.

Also durably grants the new account one of the three LOCAL-reachable role tiers
(administrator/operator/monitor) -- without this, the account authenticates but is authorized for
nothing, since `AuthorizationService` otherwise only recognizes subjects hand-written into a
static, code-level list. SS11 requires the bootstrap password be replaced before the account's
real role grants apply, so this script also collects a separate final password and replaces the
temporary one immediately, in the same run -- the operator never has to touch the API directly.

Usage (from ``backend/``):

    uv run python scripts/bootstrap_admin.py

Passwords are always read from an interactive, masked terminal prompt -- never accepted as a
command-line argument, so they never land in shell history.
"""

from __future__ import annotations

import asyncio
import getpass
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

# The `atlas` package is not pip-installed in this project -- every entry point adds `src/` to
# the path itself (uvicorn's `--app-dir src`, pytest's `pythonpath = ["src"]`). This script is no
# different: it must do the same before importing anything from `atlas`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from atlas.core.audit import LoggingAuditSink
from atlas.core.capabilities import CapabilityClass
from atlas.core.config import Settings
from atlas.modules.authorization.adapters.role_assignment_postgres import (
    PostgreSQLRoleAssignmentRepository,
)
from atlas.modules.authorization.application.bootstrap import (
    DEVELOPMENT_ROLE_ID,
    LOCAL_ADMINISTRATOR_ROLE_ID,
    LOCAL_MONITOR_ROLE_ID,
    LOCAL_OPERATOR_ROLE_ID,
    build_development_authorization_service,
    current_identity_scope,
    local_credential_self_scope,
)
from atlas.modules.authorization.domain.models import RoleAssignment
from atlas.modules.identity.adapters.local_credentials_postgres import (
    PostgreSQLLocalCredentialRepository,
)
from atlas.modules.identity.application.local_credentials import (
    BOOTSTRAP_SETUP_ROLE_ID,
    LocalCredentialError,
    LocalCredentialService,
)

_GRANTABLE_ROLE_IDS = (LOCAL_ADMINISTRATOR_ROLE_ID, LOCAL_OPERATOR_ROLE_ID, LOCAL_MONITOR_ROLE_ID)
_DEFAULT_ROLE_ID = LOCAL_ADMINISTRATOR_ROLE_ID


def _resolve_database_url() -> str | None:
    """``ATLAS_DATABASE_URL`` is never a literal line in ``.env`` -- install/start build it from
    ``ATLAS_POSTGRES_HOST``/``_PORT``/``_PASSWORD`` and set it only in the backend process's own
    environment (see those scripts). This script is a separate, short-lived process launched by
    its own wrapper script, so rather than depend on that wrapper correctly forwarding an
    explicit environment variable across a `uv run` subprocess boundary, read the same three
    values directly out of the repository-root ``.env`` and build the same URL here."""
    if existing := os.environ.get("ATLAS_DATABASE_URL"):
        return existing
    env_file = Path(__file__).resolve().parent.parent.parent / ".env"
    if not env_file.is_file():
        return None
    values: dict[str, str] = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] == "'":
            value = value[1:-1]
        values[key.strip()] = value
    password = values.get("ATLAS_POSTGRES_PASSWORD")
    if not password:
        return None
    host = values.get("ATLAS_POSTGRES_HOST") or "localhost"
    port = values.get("ATLAS_POSTGRES_PORT") or "5432"
    return f"postgresql+psycopg://atlas:{password}@{host}:{port}/atlas"


def _prompt(label: str, *, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    if not value and default is not None:
        return default
    if not value:
        print(f"{label} is required.", file=sys.stderr)
        raise SystemExit(1)
    return value


def _prompt_role_id() -> str:
    while True:
        role_id = _prompt(
            f"Role id to grant ({', '.join(_GRANTABLE_ROLE_IDS)})", default=_DEFAULT_ROLE_ID
        )
        if role_id in _GRANTABLE_ROLE_IDS:
            return role_id
        print(
            f"'{role_id}' is not one of the three LOCAL-reachable tiers: "
            f"{', '.join(_GRANTABLE_ROLE_IDS)}.",
            file=sys.stderr,
        )


def _prompt_password(label: str, *, not_equal_to: str | None = None) -> str:
    while True:
        password = getpass.getpass(f"{label}: ")
        confirmation = getpass.getpass("Confirm: ")
        if password != confirmation:
            print("Passwords did not match; try again.", file=sys.stderr)
            continue
        if len(password) < 12:
            print("Use at least 12 characters.", file=sys.stderr)
            continue
        if not_equal_to is not None and password == not_equal_to:
            print("This must be different from the temporary bootstrap password.", file=sys.stderr)
            continue
        return password


async def _main() -> None:
    database_url = _resolve_database_url()
    if not database_url:
        print(
            "Could not determine the database URL. Set ATLAS_POSTGRES_PASSWORD (and, if not "
            "default, ATLAS_POSTGRES_HOST/_PORT) in .env at the repository root, or export "
            "ATLAS_DATABASE_URL yourself. Refusing to bootstrap an administrator account that "
            "would only live in process memory.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    os.environ["ATLAS_DATABASE_URL"] = database_url
    settings = Settings()

    print("Project Atlas -- local administrator bootstrap")
    subject_id = _prompt(
        "Administrator subject id", default="subject.bootstrap-administrator.primary"
    )
    display_name = _prompt("Display name")
    # Not a free-form prompt: this Atlas deployment is single-organization, and every durably
    # granted role-assignment scope (see static_role_scopes(DEVELOPMENT_ROLE_ID) below) is pinned
    # to this exact value. A different organization id here would silently make every granted
    # assignment invisible to this account (scope.organization_id would never match), reproducing
    # the same "Identity could not be verified" failure this whole script exists to prevent.
    organization_id = settings.development_organization_id
    print(f"Organization id: {organization_id} (fixed -- this deployment is single-organization)")
    role_id = _prompt_role_id()
    temporary_password = _prompt_password("Temporary bootstrap password")
    final_password = _prompt_password(
        "Final administrator password", not_equal_to=temporary_password
    )

    audit_sink = LoggingAuditSink(logging.getLogger("atlas.bootstrap_admin"))
    credential_repository = PostgreSQLLocalCredentialRepository.from_url(database_url)
    credential_service = LocalCredentialService(
        repository=credential_repository, audit_sink=audit_sink
    )
    role_assignment_repository = PostgreSQLRoleAssignmentRepository.from_url(database_url)
    try:
        await credential_service.bootstrap_administrator(
            subject_id=subject_id,
            organization_id=organization_id,
            display_name=display_name,
            role_ids=(role_id,),
            password=temporary_password,
            deployment_ownership_verified=True,
            correlation_id=f"cor_bootstrap_{uuid4().hex}",
        )

        # BOOTSTRAP_SETUP_ROLE_ID assignments: a safety net so /identity/me and the
        # replace-credential route both work over real HTTP too, in case the immediate
        # replace_credential call below doesn't run to completion.
        now = datetime.now(UTC)
        for scope in (
            current_identity_scope(organization_id, settings.environment),
            local_credential_self_scope(
                organization_id, settings.environment, CapabilityClass.C3_CONTROLLED_CHANGE
            ),
        ):
            await role_assignment_repository.create(
                RoleAssignment(
                    assignment_id=f"assignment.{uuid4().hex}",
                    version=1,
                    subject_id=subject_id,
                    role_id=BOOTSTRAP_SETUP_ROLE_ID,
                    scope=scope,
                    valid_from=now,
                )
            )

        await credential_service.replace_credential(
            subject_id=subject_id,
            current_password=temporary_password,
            new_password=final_password,
            correlation_id=f"cor_bootstrap_{uuid4().hex}",
        )

        # The chosen tier's assignments -- mechanically derived from DEVELOPMENT_ROLE_ID's own
        # already-exhaustive scope list (see AuthorizationService.static_role_scopes), not a
        # second, hand-maintained list that would drift out of sync.
        authorization_service = build_development_authorization_service(settings, audit_sink)
        scopes = authorization_service.static_role_scopes(DEVELOPMENT_ROLE_ID)
        for scope in scopes:
            await role_assignment_repository.create(
                RoleAssignment(
                    assignment_id=f"assignment.{uuid4().hex}",
                    version=1,
                    subject_id=subject_id,
                    role_id=role_id,
                    scope=scope,
                    valid_from=now,
                )
            )
    except LocalCredentialError as error:
        print(f"Could not create the administrator account: {error.code}", file=sys.stderr)
        raise SystemExit(1) from error
    finally:
        await credential_repository.close()
        await role_assignment_repository.close()

    print(
        f"Created administrator '{subject_id}' with role '{role_id}', active and ready to sign "
        "in with the final password."
    )


if __name__ == "__main__":
    # uvicorn's default --loop resolves to ProactorEventLoop on Windows (see install.ps1's
    # --loop asyncio:SelectorEventLoop, the same fix for the backend server), which psycopg's
    # async driver refuses to run under. asyncio.run() has the identical default on Windows, so
    # this script needs the same fix.
    if sys.platform == "win32":
        asyncio.run(_main(), loop_factory=asyncio.SelectorEventLoop)
    else:
        asyncio.run(_main())
