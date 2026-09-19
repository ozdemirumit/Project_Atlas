@echo off
rem Updates an already-installed Project Atlas deployment: stops the backend, pulls the latest
rem code, then reinstalls dependencies/migrations and restarts it. Delegates to update.ps1;
rem -ExecutionPolicy Bypass here is scoped to this one invocation and does not weaken any system
rem security control.
setlocal
set "SCRIPT_DIR=%~dp0"

where powershell >nul 2>nul
if errorlevel 1 (
  echo PowerShell is required to run this script. See README.md for prerequisites.
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%update.ps1" %*
exit /b %ERRORLEVEL%
