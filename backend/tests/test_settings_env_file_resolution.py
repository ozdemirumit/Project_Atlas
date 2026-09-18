"""Regression test for a real bug a user hit on their own server: after setting
``ATLAS_PROTECTED_CONTENT_ENCRYPTION_KEY_B64`` in the repository-root ``.env`` and restarting,
the connector-credential vault still silently fell back to an unencrypted in-memory store --
writes appeared to succeed (the pointer row landed in Postgres) but the encrypted blob never did
(``protected_content_blobs`` stayed empty), so nothing set through the vault could ever be read
back. Root cause: ``Settings.model_config["env_file"]`` was the relative string ``".env"``, which
pydantic-settings resolves against the process's *current working directory* -- but
``scripts/install.ps1``/``start.ps1`` launch the backend with
``-WorkingDirectory backend/`` (required for ``uv run uvicorn ... --app-dir src``), while
``README.md`` and ``.env.example`` both document a single ``.env`` at the repository root. The
relative path silently looked for a nonexistent ``backend/.env`` instead, leaving every
``.env``-only setting (anything not one of ``install.ps1``'s few explicitly-forwarded process env
vars) at its default with no error anywhere.
"""

from __future__ import annotations

from pathlib import Path

from atlas.core.config import Settings


def test_settings_env_file_is_an_absolute_repository_root_path() -> None:
    """The configured env_file must not be a bare relative ".env" -- that resolves against
    whatever the process's cwd happens to be at startup, not this package's own location."""
    env_file = Settings.model_config["env_file"]
    assert isinstance(env_file, Path)
    assert env_file.is_absolute()
    assert env_file.name == ".env"
    # .env.example ships in the repository root alongside the real (gitignored) .env -- its
    # presence next to the configured path confirms this resolved to the repository root and not
    # some other absolute-but-wrong location (e.g. backend/.env).
    assert (env_file.parent / ".env.example").is_file()


def test_settings_loads_env_file_values_regardless_of_process_working_directory(
    tmp_path: Path,
) -> None:
    """Exercises the actual failure mode end to end: a value that only exists in a dotenv file
    (never one of install.ps1's explicitly-forwarded process env vars) must still reach Settings
    even when instantiated from a working directory that isn't the repository root -- mirroring
    scripts/install.ps1's `-WorkingDirectory backend/`."""
    import os

    env_path = tmp_path / ".env"
    key_b64 = "3xVR4cbo2Qs8gGG/gAXSbjuh+SwEVRnOtDrc8SKOUgE="
    env_path.write_text(f"ATLAS_PROTECTED_CONTENT_ENCRYPTION_KEY_B64={key_b64}\n", encoding="utf-8")

    unrelated_cwd = tmp_path / "backend"
    unrelated_cwd.mkdir()
    original_cwd = Path.cwd()
    os.chdir(unrelated_cwd)
    try:
        settings = Settings(_env_file=env_path)
    finally:
        os.chdir(original_cwd)

    assert settings.protected_content_encryption_key_b64 is not None
    assert settings.protected_content_encryption_key_b64.get_secret_value() == key_b64
