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
import os
import sys
from pathlib import Path
from uuid import uuid4

# The `atlas` package is not pip-installed in this project -- every entry point adds `src/` to
# the path itself (uvicorn's `--app-dir src`, pytest's `pythonpath = ["src"]`). This script is no
# different: it must do the same before importing anything from `atlas`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

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
