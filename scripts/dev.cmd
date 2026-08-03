@echo off
setlocal
set "REPOSITORY_ROOT=%~dp0.."
set "ATLAS_DEVELOPMENT_IDENTITY_ENABLED=true"

where uv >nul 2>nul
if errorlevel 1 (
  echo Required command "uv" is not available. Run scripts\bootstrap.cmd first.
  exit /b 1
)

where pnpm >nul 2>nul
if errorlevel 1 (
  echo Required command "pnpm" is not available. Run scripts\bootstrap.cmd first.
  exit /b 1
)

start "Atlas API" /D "%REPOSITORY_ROOT%\backend" uv run uvicorn atlas.main:app --app-dir src --host 127.0.0.1 --port 8000 --reload
start "Atlas Web" /D "%REPOSITORY_ROOT%\frontend" pnpm dev

echo Atlas API: http://localhost:8000
echo Atlas web: http://localhost:5173
echo The services are running in separate command windows.
exit /b 0
