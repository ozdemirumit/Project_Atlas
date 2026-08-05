from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from hashlib import sha256
from pathlib import Path, PurePosixPath

from atlas.modules.connectors.domain.runner_validation import (
    RUNNER_CHECK_CODES,
    RunnerCheck,
    RunnerCheckSeverity,
    RunnerCheckState,
    RunnerExecutionResult,
)

RUNNER_VALIDATION_PROFILE = "atlas.connector-runner.python312.v1"
RUNNER_ADAPTER_CONTRACT = "atlas.connector-isolated-subprocess.v1"
RUNNER_HARNESS_VERSION = "atlas.connector-runner-harness.v1"
MAX_OUTPUT_BYTES = 65_536

_CHILD = r"""
import ctypes
import importlib
import json
import os
import pkgutil
import socket
import subprocess
import sys
from pathlib import Path

root = Path.cwd()
denied = []
def deny(event, args):
    blocked = event.startswith(("socket.", "subprocess.", "ctypes.")) or event == "os.system"
    if event == "open" and len(args) >= 2:
        mode = args[1]
        blocked = blocked or (isinstance(mode, str) and any(item in mode for item in "wax+"))
    if event.startswith(("os.remove", "os.rename", "os.rmdir", "os.mkdir", "os.chdir")):
        blocked = True
    if blocked:
        denied.append(event)
        raise PermissionError("atlas_runner_policy_denied")

sys.addaudithook(deny)
sys.path.insert(0, str(root / "src"))
checks = {}
checks["runner.process.isolation"] = (
    sys.flags.isolated == 1
    and sys.flags.no_site == 1
    and sys.flags.dont_write_bytecode == 1
    and sys.version_info[:2] == (3, 12)
    and os.environ.get("ATLAS_RUNNER_ADAPTER") == "atlas.connector-isolated-subprocess.v1"
    and os.environ.get("ATLAS_RUNNER_HARNESS") == "atlas.connector-runner-harness.v1"
)
allowed = {
    "ATLAS_RUNNER_ADAPTER",
    "ATLAS_RUNNER_HARNESS",
    "ATLAS_RUNNER_MODE",
    "ATLAS_RUNNER_PROFILE",
    "LC_ALL",
    "PYTHONCOERCECLOCALE",
    "PYTHONHASHSEED",
    "PYTHONUTF8",
}
platform_keys = {"SYSTEMROOT", "WINDIR"}
checks["runner.environment.secret-free"] = (
    all(key in allowed or key in platform_keys for key in os.environ)
    and not any(
        any(token in key.upper() for token in ("SECRET", "TOKEN", "PASSWORD", "CREDENTIAL"))
        for key in os.environ
    )
)
probes = []
for probe in (
    lambda: socket.socket(),
    lambda: subprocess.Popen([sys.executable, "-c", "pass"]),
    lambda: ctypes.CDLL("atlas-runner-denied"),
    lambda: open(root / "__atlas_denied__", "w", encoding="utf-8"),
):
    try:
        probe()
    except PermissionError:
        probes.append(True)
    else:
        probes.append(False)
checks["runner.authority.denied"] = all(probes) and len(denied) >= len(probes)

manifest = json.loads((root / "atlas-connector.yaml").read_text(encoding="utf-8"))
package = importlib.import_module("atlas_generated_connector")
checks["runner.package.import"] = (
    package.__name__ == "atlas_generated_connector"
    and package.__spec__ is not None
    and package.__file__ is not None
)
checks["runner.quarantine.contract"] = (
    manifest.get("status") == "quarantined_generated_draft"
    and manifest.get("runtime_trust") is False
    and manifest.get("execution_authorized") is False
    and manifest.get("sdk_profile") == "atlas.python312.v1"
)

fixtures = {}
global_fixture = None
for path in sorted((root / "tests" / "fixtures").glob("*.json")):
    value = json.loads(path.read_text(encoding="utf-8"))
    capability_id = value.get("capability_id")
    if capability_id is not None:
        fixtures[capability_id] = value
    elif path.name == "synthetic-empty.json":
        global_fixture = value

capabilities_package = importlib.import_module("atlas_generated_connector.capabilities")
modules = [
    importlib.import_module(f"atlas_generated_connector.capabilities.{item.name}")
    for item in pkgutil.iter_modules(capabilities_package.__path__)
    if not item.name.startswith("_")
]
errors = importlib.import_module("atlas_generated_connector.errors")
invoked = 0
fail_closed = 0
bounded_literal = 0
global_fixture_ok = (
    isinstance(global_fixture, dict)
    and global_fixture.get("classification") == "synthetic"
    and global_fixture.get("target_connected") is False
    and global_fixture.get("secret_values_present") is False
)
behavior_ok = len(modules) == len(manifest.get("capabilities", [])) and (
    len(fixtures) == len(modules) or global_fixture_ok
)
for module in modules:
    fixture = fixtures.get(module.CAPABILITY_ID) or global_fixture
    if fixture is None:
        behavior_ok = False
        continue
    capability_fixture = fixture.get("capability_id") is not None
    if capability_fixture and not (
        fixture.get("classification") == "synthetic"
        and fixture.get("target_connected") is False
        and fixture.get("secret_values_present") is False
        and isinstance(fixture.get("input"), dict)
        and isinstance(fixture.get("expected_output"), dict)
    ):
        behavior_ok = False
        continue
    invoked += 1
    invocation = module.handle(fixture.get("input", {}))
    try:
        invocation.send(None)
    except StopIteration as completed:
        result = completed.value
        bounded_literal += 1
        behavior_ok = (
            behavior_ok
            and capability_fixture
            and result == fixture["expected_output"]
        )
    except Exception as exc:
        generated_error = getattr(errors, "GeneratedDraftNotExecutable", None)
        if generated_error is not None and isinstance(exc, generated_error):
            fail_closed += 1
            behavior_ok = behavior_ok and str(exc) == (
                "Generated capability requires isolated validation and human review."
            )
        else:
            behavior_ok = False
    else:
        invocation.close()
        behavior_ok = False
checks["runner.capabilities.synthetic"] = (
    behavior_ok
    and invoked == len(modules)
    and fail_closed + bounded_literal == invoked
)
checks["runner.output.bounded"] = True
print(json.dumps(
    {
        "adapter_contract": "atlas.connector-isolated-subprocess.v1",
        "harness_version": "atlas.connector-runner-harness.v1",
        "checks": checks,
        "capability_count": len(modules),
        "invoked_capability_count": invoked,
        "fail_closed_count": fail_closed,
        "bounded_literal_count": bounded_literal,
    },
    sort_keys=True,
    separators=(",", ":"),
))
"""


class SubprocessPackageRunner:
    def __init__(self, *, timeout_seconds: float = 5.0) -> None:
        self._timeout_seconds = timeout_seconds

    async def run(
        self, *, files: dict[str, bytes], validation_profile: str
    ) -> RunnerExecutionResult:
        return await asyncio.to_thread(self._run_sync, files, validation_profile)

    def _run_sync(self, files: dict[str, bytes], validation_profile: str) -> RunnerExecutionResult:
        started = time.monotonic()
        workspace = Path(tempfile.mkdtemp(prefix="atlas-connector-runner-"))
        child_started = False
        exit_code: int | None = None
        output = b""
        raw_checks: dict[str, bool] = {}
        metrics = {
            "capability_count": 0,
            "invoked_capability_count": 0,
            "fail_closed_count": 0,
            "bounded_literal_count": 0,
        }
        failure = "The isolated runner did not produce valid bounded evidence."
        removed = False
        try:
            for relative_path, content in sorted(files.items()):
                path = PurePosixPath(relative_path)
                if path.is_absolute() or ".." in path.parts:
                    raise ValueError("unsafe package path")
                destination = workspace.joinpath(*path.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
            environment = {
                "ATLAS_RUNNER_ADAPTER": RUNNER_ADAPTER_CONTRACT,
                "ATLAS_RUNNER_HARNESS": RUNNER_HARNESS_VERSION,
                "ATLAS_RUNNER_MODE": "disconnected-synthetic",
                "ATLAS_RUNNER_PROFILE": validation_profile,
                "LC_ALL": "C",
                "PYTHONCOERCECLOCALE": "0",
                "PYTHONHASHSEED": "0",
                "PYTHONUTF8": "1",
            }
            for key in ("SYSTEMROOT", "WINDIR"):
                if value := os.environ.get(key):
                    environment[key] = value
            child_started = True
            completed = subprocess.run(
                [sys.executable, "-I", "-S", "-B", "-c", _CHILD],
                cwd=workspace,
                env=environment,
                capture_output=True,
                timeout=self._timeout_seconds,
                check=False,
            )
            exit_code = completed.returncode
            output = completed.stdout + completed.stderr
            if len(output) > MAX_OUTPUT_BYTES:
                output = output[:MAX_OUTPUT_BYTES]
                failure = "The isolated runner exceeded its output budget."
            elif completed.returncode != 0:
                failure = "The isolated runner exited abnormally."
            else:
                payload = json.loads(completed.stdout.decode("utf-8"))
                if (
                    payload.get("adapter_contract") != RUNNER_ADAPTER_CONTRACT
                    or payload.get("harness_version") != RUNNER_HARNESS_VERSION
                ):
                    raise ValueError("runner identity mismatch")
                check_payload = payload.get("checks")
                expected = set(RUNNER_CHECK_CODES[2:-1])
                if not isinstance(check_payload, dict) or set(check_payload) != expected:
                    raise ValueError("runner check set mismatch")
                raw_checks = {key: check_payload[key] is True for key in expected}
                for key in metrics:
                    value = payload.get(key)
                    if not isinstance(value, int) or value < 0:
                        raise ValueError("runner metric invalid")
                    metrics[key] = value
        except subprocess.TimeoutExpired as error:
            output = ((error.stdout or b"") + (error.stderr or b""))[:MAX_OUTPUT_BYTES]
            failure = "The isolated runner exceeded its time budget."
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            failure = "The isolated runner evidence was malformed or unavailable."
        finally:
            try:
                shutil.rmtree(workspace)
                removed = not workspace.exists()
            except OSError:
                removed = False
        raw_checks["runner.workspace.cleaned"] = removed
        if not removed:
            failure = "The isolated runner workspace could not be removed."
        checks = tuple(
            RunnerCheck(
                code=code,
                state=(
                    RunnerCheckState.PASSED if raw_checks.get(code) else RunnerCheckState.FAILED
                ),
                severity=(
                    RunnerCheckSeverity.INFORMATIONAL
                    if raw_checks.get(code)
                    else RunnerCheckSeverity.ERROR
                ),
                summary=(
                    "The required isolated runner control passed."
                    if raw_checks.get(code)
                    else failure
                ),
                remediation=(
                    "No remediation is required."
                    if raw_checks.get(code)
                    else "Regenerate the package or correct the runner boundary before retrying."
                ),
            )
            for code in RUNNER_CHECK_CODES[2:]
        )
        return RunnerExecutionResult(
            runtime_version=(
                f"python.{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            ),
            adapter_contract=RUNNER_ADAPTER_CONTRACT,
            harness_version=RUNNER_HARNESS_VERSION,
            checks=checks,
            child_started=child_started,
            child_exit_code=exit_code,
            duration_ms=max(0, int((time.monotonic() - started) * 1000)),
            output_digest=sha256(output).hexdigest(),
            output_size_bytes=len(output),
            workspace_removed=removed,
            **metrics,
        )
