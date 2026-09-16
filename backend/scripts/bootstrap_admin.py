"""Create the first durable local administrator account (ATLAS-030 SS11 bootstrap).

Run once, on the server, by someone with shell access -- that is the whole authorization model:
there is deliberately no HTTP endpoint for this, so an attacker who cannot already reach a shell
on the box can never create an administrator account through the API. Requires a configured
``ATLAS_DATABASE_URL`` (see ``.env``); without one, the account would only live in process memory
and vanish the moment this script exits.

Usage (from ``backend/``):

    uv run python scripts/bootstrap_admin.py

The password is always read from an interactive, masked terminal prompt -- never accepted as a
command-line argument, so it never lands in shell history.
"""

from __future__ import annotations

import asyncio
import getpass
import logging
import sys
from uuid import uuid4

from atlas.core.audit import LoggingAuditSink
from atlas.core.config import Settings
from atlas.modules.identity.adapters.local_credentials_postgres import (
    PostgreSQLLocalCredentialRepository,
)
from atlas.modules.identity.application.local_credentials import (
    LocalCredentialError,
    LocalCredentialService,
)

_DEFAULT_ROLE_ID = "role.security-administrator"


def _prompt(label: str, *, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    if not value and default is not None:
        return default
    if not value:
        print(f"{label} is required.", file=sys.stderr)
        raise SystemExit(1)
    return value


def _prompt_password() -> str:
    while True:
        password = getpass.getpass("Administrator password: ")
        confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            print("Passwords did not match; try again.", file=sys.stderr)
            continue
        if len(password) < 12:
            print("Use at least 12 characters.", file=sys.stderr)
            continue
        return password


async def _main() -> None:
    settings = Settings()
    if not settings.database_url:
        print(
            "ATLAS_DATABASE_URL is not configured (see .env). Refusing to bootstrap an "
            "administrator account that would only live in process memory.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print("Project Atlas -- local administrator bootstrap")
    subject_id = _prompt(
        "Administrator subject id", default="subject.bootstrap-administrator.primary"
    )
    display_name = _prompt("Display name")
    organization_id = _prompt("Organization id", default=settings.development_organization_id)
    role_id = _prompt("Role id to grant", default=_DEFAULT_ROLE_ID)
    password = _prompt_password()

    repository = PostgreSQLLocalCredentialRepository.from_url(settings.database_url)
    service = LocalCredentialService(
        repository=repository,
        audit_sink=LoggingAuditSink(logging.getLogger("atlas.bootstrap_admin")),
    )
    try:
        await service.bootstrap_administrator(
            subject_id=subject_id,
            organization_id=organization_id,
            display_name=display_name,
            role_ids=(role_id,),
            password=password,
            deployment_ownership_verified=True,
            correlation_id=f"cor_bootstrap_{uuid4().hex}",
        )
    except LocalCredentialError as error:
        print(f"Could not create the administrator account: {error.code}", file=sys.stderr)
        raise SystemExit(1) from error
    finally:
        await repository.close()

    print(f"Created administrator '{subject_id}'. It must replace its password on first sign-in.")


if __name__ == "__main__":
    asyncio.run(_main())
