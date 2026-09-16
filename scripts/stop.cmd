@echo off
rem Stops the backend process start.cmd/install.cmd started. Delegates to stop.ps1; see
rem install.cmd for why -ExecutionPolicy Bypass here is scoped to this one invocation and does
rem not weaken any system security control.
setlocal
set "SCRIPT_DIR=%~dp0"

where powershell >nul 2>nul
if errorlevel 1 (
  echo PowerShell is required to run this script. See README.md for prerequisites.
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%stop.ps1" %*
exit /b %ERRORLEVEL%
