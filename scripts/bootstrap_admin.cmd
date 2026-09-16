@echo off
setlocal
set "REPOSITORY_ROOT=%~dp0.."

where uv >nul 2>nul
if errorlevel 1 (
  echo Required command "uv" is not available. See README.md for prerequisites.
  exit /b 1
)

pushd "%REPOSITORY_ROOT%\backend"
call uv run python scripts/bootstrap_admin.py
set "RESULT=%ERRORLEVEL%"
popd
exit /b %RESULT%
