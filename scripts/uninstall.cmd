@echo off
rem Stops the backend/frontend processes install.cmd/install.ps1 started.
rem Delegates to uninstall.ps1 -- see install.cmd for why -ExecutionPolicy Bypass here
rem is scoped to this one invocation and does not weaken any system security control.
setlocal
set "SCRIPT_DIR=%~dp0"

where powershell >nul 2>nul
if errorlevel 1 (
  echo PowerShell is required to run this script. See README.md for prerequisites.
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%uninstall.ps1" %*
exit /b %ERRORLEVEL%
