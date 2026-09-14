@echo off
rem Builds and starts Project Atlas as plain Docker containers (no Compose, no YAML).
rem Delegates to install.ps1: the full logic (secure password generation, container
rem health polling) is impractical in plain batch. `-ExecutionPolicy Bypass` here only
rem affects this one invocation of powershell.exe; it does not change any system or
rem user execution-policy setting, so it does not weaken endpoint security controls.
setlocal
set "SCRIPT_DIR=%~dp0"

where powershell >nul 2>nul
if errorlevel 1 (
  echo PowerShell is required to run the installer. See README.md for prerequisites.
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%install.ps1" %*
exit /b %ERRORLEVEL%
