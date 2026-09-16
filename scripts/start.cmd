@echo off
rem Starts the already-installed Atlas backend as a background process (no dependency/database
rem setup -- run install.cmd first). Delegates to start.ps1; see install.cmd for why
rem -ExecutionPolicy Bypass here is scoped to this one invocation and does not weaken any system
rem security control.
setlocal
set "SCRIPT_DIR=%~dp0"

where powershell >nul 2>nul
if errorlevel 1 (
  echo PowerShell is required to run this script. See README.md for prerequisites.
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start.ps1" %*
exit /b %ERRORLEVEL%
