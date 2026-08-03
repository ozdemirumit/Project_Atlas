# Development Scripts

Project automation is available in both Windows Command Prompt and PowerShell formats.
The `.cmd` entry points do not require PowerShell execution-policy changes.

## Windows Command Prompt

```bat
scripts\bootstrap.cmd
scripts\check.cmd
scripts\dev.cmd
```

## PowerShell

```powershell
./scripts/bootstrap.ps1
./scripts/check.ps1
./scripts/dev.ps1
```

Do not weaken endpoint security controls to run these scripts. Use the `.cmd` entry points or
the individual `uv` and `pnpm` commands documented in the component READMEs when PowerShell is
restricted by organizational policy or endpoint protection.
