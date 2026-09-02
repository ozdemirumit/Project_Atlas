from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

import pytest

if sys.platform == "win32":
    # asyncio's default event loop policy on Windows is the proactor policy, but psycopg's
    # async mode only implements the selector-based reader/writer transport, raising
    # `psycopg.InterfaceError: Psycopg cannot use the 'ProactorEventLoop' to run in async
    # mode` on every ATLAS_TEST_POSTGRES_DSN-backed test. This project's actual CI target
    # (Linux, see `.github/workflows/ci.yml`) never hits this -- POSIX event loops are
    # already selector-based. Nothing in this codebase's async tests uses
    # `asyncio.create_subprocess_*` (the one capability the proactor policy adds over the
    # selector policy on Windows), so switching policy for the whole Windows test run is safe.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    @pytest.fixture
    def tmp_path(tmp_path_factory: pytest.TempPathFactory, request: pytest.FixtureRequest) -> Path:
        """Wraps pytest's normal per-test temp directory in Windows' `\\?\\` extended-length
        path prefix. This project's own deep, content-addressed test fixture paths (e.g.
        `deployments/<org>/<env>/<site>/<release>/.../<64-char digest>`), stacked on pytest's own
        `%TEMP%\\pytest-of-<user>\\pytest-<N>\\<test-name><index>` naming, routinely exceed
        Windows' 260-character MAX_PATH limit -- causing spurious `WinError 3`/`WinError 206`
        failures, and even silently-wrong `Path.is_file()`/`Path.exists()` results (the
        underlying `stat()` call fails and both methods swallow the `OSError`), on filesystem
        operations that never fail on this project's actual CI target (Linux, see
        `.github/workflows/ci.yml`). The `\\?\\` prefix makes Windows accept paths up to
        roughly 32,767 characters, bypassing MAX_PATH entirely, with no machine-wide registry
        change required -- confirmed to work correctly through `resolve()`, `mkdir()`,
        `rename()`, `is_file()`, `rglob()`, and `relative_to()`, everything this project's
        filesystem publishers use. Only defined on `win32`, so every other platform (including
        CI) keeps pytest's own default `tmp_path` untouched."""

        name = re.sub(r"[\W]", "_", request.node.name)[:30]
        path = tmp_path_factory.mktemp(name, numbered=True)
        return Path(f"\\\\?\\{path}")
