@echo off
setlocal
set "REPOSITORY_ROOT=%~dp0.."

pushd "%REPOSITORY_ROOT%\backend"
call uv run ruff format --check .
if errorlevel 1 goto backend_failed
call uv run ruff check .
if errorlevel 1 goto backend_failed
call uv run mypy
if errorlevel 1 goto backend_failed
call uv run pytest
if errorlevel 1 goto backend_failed
popd

pushd "%REPOSITORY_ROOT%\frontend"
call pnpm lint
if errorlevel 1 goto frontend_failed
call pnpm typecheck
if errorlevel 1 goto frontend_failed
call pnpm test
if errorlevel 1 goto frontend_failed
call pnpm build
if errorlevel 1 goto frontend_failed
popd

echo All available Atlas checks passed.
exit /b 0

:backend_failed
set "RESULT=%ERRORLEVEL%"
popd
exit /b %RESULT%

:frontend_failed
set "RESULT=%ERRORLEVEL%"
popd
exit /b %RESULT%
