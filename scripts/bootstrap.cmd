@echo off
setlocal
set "REPOSITORY_ROOT=%~dp0.."

where uv >nul 2>nul
if errorlevel 1 (
  echo Required command "uv" is not available. See README.md for prerequisites.
  exit /b 1
)

where pnpm >nul 2>nul
if errorlevel 1 (
  echo Required command "pnpm" is not available. See README.md for prerequisites.
  exit /b 1
)

echo Preparing Atlas backend...
pushd "%REPOSITORY_ROOT%\backend"
call uv sync --frozen
set "RESULT=%ERRORLEVEL%"
popd
if not "%RESULT%"=="0" exit /b %RESULT%

echo Preparing Atlas web application...
pushd "%REPOSITORY_ROOT%\frontend"
call pnpm install --frozen-lockfile
set "RESULT=%ERRORLEVEL%"
popd
if not "%RESULT%"=="0" exit /b %RESULT%

echo Atlas development dependencies are ready.
exit /b 0
