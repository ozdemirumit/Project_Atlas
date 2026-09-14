# Scripts

Project automation is available in POSIX shell, Windows Command Prompt, and PowerShell formats.
The `.cmd` entry points do not require a PowerShell execution-policy change.

## Deployment (Docker, no Compose, no YAML)

`install`/`uninstall` bring up or tear down the full stack (PostgreSQL, backend, frontend) as
plain Docker containers, built and started with imperative `docker build`/`docker run` commands.
This is the script to run when deploying Atlas in a new environment.

```bash
scripts/install.sh          # Linux, macOS, WSL
scripts/uninstall.sh        # stop and remove; add --purge to also delete the database volume
```

```powershell
scripts\install.cmd         # Windows Command Prompt
scripts\uninstall.cmd
# or, directly in PowerShell:
./scripts/install.ps1
./scripts/uninstall.ps1 -Purge   # -Purge also deletes the database volume
```

`install` is idempotent: re-running it rebuilds the images and replaces any existing Atlas
containers without touching the named database volume, so data survives a re-install. If `.env`
does not already exist, `install` creates one from `.env.example` with a freshly generated,
randomly-created database password.

## Local development (no Docker)

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
