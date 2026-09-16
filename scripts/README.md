# Scripts

Project automation is available in POSIX shell, Windows Command Prompt, and PowerShell formats.
The `.cmd` entry points do not require a PowerShell execution-policy change.

## Deployment (native, no Docker, no containers, no YAML)

`install`/`uninstall` bring up or tear down the backend as a plain background process against a
PostgreSQL server you install yourself -- no containers of any kind, and no Node.js/npm/pnpm on
the target either, since the frontend is the pre-built `frontend/dist/` bundle already committed
to the repository, served directly by the backend on the same port. This is the script to run
when deploying Atlas in a new environment.

`uv` is installed automatically if missing everywhere. PostgreSQL + pgvector are installed
automatically too: on macOS (Homebrew) and Debian/Ubuntu (the official PGDG apt repository) after
a one-line confirmation, and on Windows via `winget` for PostgreSQL plus an automatic Visual
Studio C++ Build Tools install and source build for pgvector (which has no Windows binary
distribution) -- the Windows path needs an elevated (Administrator) PowerShell session. Either
way, the scripts handle everything after PostgreSQL exists -- creating the `atlas`
role/database/extension, running migrations, and starting the backend.

```bash
scripts/install.sh          # Linux, macOS, WSL
scripts/uninstall.sh        # stop the backend; add --purge to also drop the database
```

```powershell
scripts\install.cmd         # Windows Command Prompt
scripts\uninstall.cmd
# or, directly in PowerShell:
./scripts/install.ps1
./scripts/uninstall.ps1 -Purge   # -Purge also drops the atlas database and role
```

`install` is idempotent: re-running it reinstalls dependencies and restarts the backend process
without touching existing database data (it only performs the one-time PostgreSQL superuser
setup -- role, database, `CREATE EXTENSION vector` -- the first time the `atlas` role isn't
reachable yet). If `.env` does not already exist, `install` creates one from `.env.example` with
a freshly generated, randomly-created database password. Process ID and logs live under the
gitignored `.atlas/` directory at the repository root.

`install` refuses to run if `frontend/dist/index.html` is missing -- rebuild and commit it after
a frontend source change (see README.md's Contributing section: `pnpm build` from `frontend/`).

## Local development (foreground, with hot reload)

Requires an already-running PostgreSQL server pointed to by `ATLAS_DATABASE_URL` in `.env`, or
running in synthetic mode (`ATLAS_DATABASE_REQUIRED=false`, the default). Unlike `install`, these
scripts run the backend and frontend in the foreground with live reload, for active development.

```bat
scripts\bootstrap.cmd
scripts\check.cmd
scripts\dev.cmd
```

```powershell
./scripts/bootstrap.ps1
./scripts/check.ps1
./scripts/dev.ps1
```

Do not weaken endpoint security controls to run these scripts. Use the `.cmd` entry points or
the individual `uv` and `pnpm` commands documented in the component READMEs when PowerShell is
restricted by organizational policy or endpoint protection.
