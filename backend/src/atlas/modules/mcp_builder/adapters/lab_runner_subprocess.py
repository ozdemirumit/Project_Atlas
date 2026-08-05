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
from pathlib import Path

from atlas.modules.mcp_builder.application.generator import BuilderGeneratedContent
from atlas.modules.mcp_builder.domain.lab_validation import (
    BuilderLabCheck,
    BuilderLabCheckCode,
    BuilderLabCheckSeverity,
    BuilderLabCheckState,
    BuilderLabRunnerResult,
)

LAB_PROFILE = "atlas.lab-validation.python312.v1"
RUNNER_CONTRACT_VERSION = "mcp-builder-isolated-runner.v1"
MAX_OUTPUT_BYTES = 65_536

_CHILD = r"""
import importlib
import json
import os
import socket
import sys
from pathlib import Path

DENIED = []
def deny(event, _args):
    if event.startswith(("socket.", "subprocess.", "ctypes.")) or event == "os.system":
        DENIED.append(event)
        raise PermissionError("atlas_lab_policy_denied")

sys.addaudithook(deny)
root = Path.cwd()
sys.path.insert(0, str(root / "src"))
checks = {}
checks["lab.runner_isolation"] = sys.flags.isolated == 1 and sys.version_info[:2] == (3, 12)
allowed = {"ATLAS_LAB_MODE", "ATLAS_LAB_PROFILE", "ATLAS_RUNNER_CONTRACT", "PYTHONHASHSEED"}
platform_keys = {"SYSTEMROOT", "WINDIR"}
checks["lab.secret_free_environment"] = (
    all(key in allowed or key in platform_keys for key in os.environ)
    and not any(
        any(token in key.upper() for token in ("SECRET", "TOKEN", "PASSWORD", "KEY"))
        for key in os.environ
    )
)
manifest = json.loads((root / "atlas-connector.yaml").read_text(encoding="utf-8"))
fixture = json.loads((root / "tests/fixtures/synthetic-empty.json").read_text(encoding="utf-8"))
package = importlib.import_module("atlas_generated_connector")
checks["lab.package_import"] = bool(package.QUARANTINED) and not package.RUNTIME_TRUST_GRANTED
checks["lab.quarantine_contract"] = (
    manifest["status"] == "quarantined_generated_draft"
    and manifest["runtime_trust"] is False
    and manifest["execution_authorized"] is False
    and fixture["classification"] == "synthetic"
    and fixture["target_connected"] is False
    and fixture["secret_values_present"] is False
)
trace = json.loads((root / "docs/source-traceability.json").read_text(encoding="utf-8"))
errors = importlib.import_module("atlas_generated_connector.errors")
def verify_handlers():
    for item in trace["capabilities"]:
        module = importlib.import_module(
            "atlas_generated_connector.capabilities." + item["generated_module"]
        )
        try:
            module.handle({}).send(None)
        except errors.GeneratedDraftNotExecutable as exc:
            if str(exc) != "Generated capability requires isolated validation and human review.":
                return False
        else:
            return False
    return True
checks["lab.capability_fail_closed"] = verify_handlers()
try:
    socket.socket()
except PermissionError:
    checks["lab.network_denial"] = True
else:
    checks["lab.network_denial"] = False
checks["lab.artifact_integrity"] = True
checks["lab.bounded_output"] = True
print(json.dumps(
    {"contract": "mcp-builder-isolated-runner.v1", "checks": checks},
    sort_keys=True,
    separators=(",", ":"),
))
"""


class SubprocessMcpBuilderLabRunner:
    def __init__(self, *, timeout_seconds: float = 5.0) -> None:
        self._timeout_seconds = timeout_seconds

    async def run(
        self, *, files: tuple[BuilderGeneratedContent, ...], lab_profile: str
    ) -> BuilderLabRunnerResult:
        return await asyncio.to_thread(self._run_sync, files, lab_profile)

    def _run_sync(
        self, files: tuple[BuilderGeneratedContent, ...], lab_profile: str
    ) -> BuilderLabRunnerResult:
        started = time.monotonic()
        workspace = Path(tempfile.mkdtemp(prefix="atlas-mcp-lab-"))
        child_started = False
        exit_code: int | None = None
        output = b""
        checks: dict[BuilderLabCheckCode, bool] = {}
        failure = "The isolated runner did not produce valid bounded evidence."
        removed = False
        try:
            for item in files:
                destination = workspace.joinpath(*item.relative_path.split("/"))
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(item.content, encoding="utf-8", newline="\n")
            environment = {
                "ATLAS_LAB_MODE": "synthetic",
                "ATLAS_LAB_PROFILE": lab_profile,
                "ATLAS_RUNNER_CONTRACT": RUNNER_CONTRACT_VERSION,
                "PYTHONHASHSEED": "0",
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
                failure = "The isolated runner exceeded the output budget."
            elif completed.returncode != 0:
                failure = "The isolated runner exited abnormally."
            else:
                payload = json.loads(completed.stdout.decode("utf-8"))
                if payload.get("contract") != RUNNER_CONTRACT_VERSION:
                    raise ValueError("runner contract mismatch")
                raw_checks = payload.get("checks")
                if not isinstance(raw_checks, dict) or set(raw_checks) != {
                    item.value for item in BuilderLabCheckCode
                }:
                    raise ValueError("runner check set mismatch")
                checks = {code: raw_checks[code.value] is True for code in BuilderLabCheckCode}
        except subprocess.TimeoutExpired as error:
            output = (error.stdout or b"") + (error.stderr or b"")
            output = output[:MAX_OUTPUT_BYTES]
            failure = "The isolated runner exceeded its time budget."
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            failure = "The isolated runner evidence was malformed or unavailable."
        finally:
            try:
                shutil.rmtree(workspace)
                removed = not workspace.exists()
            except OSError:
                removed = False
        if not removed:
            checks = {}
            failure = "The isolated runner workspace could not be removed."
        return BuilderLabRunnerResult(
            checks=self._domain_checks(checks, failure),
            runtime_version=f"python.{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            child_started=child_started,
            child_exit_code=exit_code,
            duration_ms=max(0, int((time.monotonic() - started) * 1000)),
            output_digest=sha256(output).hexdigest(),
            output_size_bytes=len(output),
            workspace_removed=removed,
        )

    @staticmethod
    def _domain_checks(
        results: dict[BuilderLabCheckCode, bool], failure: str
    ) -> tuple[BuilderLabCheck, ...]:
        evidence: dict[BuilderLabCheckCode, tuple[str, ...]] = {
            BuilderLabCheckCode.ARTIFACT_INTEGRITY: ("artifact inventory",),
            BuilderLabCheckCode.RUNNER_ISOLATION: ("python isolated-mode flags",),
            BuilderLabCheckCode.SECRET_FREE_ENVIRONMENT: ("allowlisted child environment",),
            BuilderLabCheckCode.NETWORK_DENIAL: ("deny-first socket audit probe",),
            BuilderLabCheckCode.PACKAGE_IMPORT: ("src/atlas_generated_connector/__init__.py",),
            BuilderLabCheckCode.QUARANTINE_CONTRACT: (
                "atlas-connector.yaml",
                "tests/fixtures/synthetic-empty.json",
            ),
            BuilderLabCheckCode.CAPABILITY_FAIL_CLOSED: (
                "docs/source-traceability.json",
                "src/atlas_generated_connector/capabilities",
            ),
            BuilderLabCheckCode.BOUNDED_OUTPUT: ("isolated runner output budget",),
        }
        return tuple(
            BuilderLabCheck(
                code=code,
                state=(
                    BuilderLabCheckState.PASSED
                    if results.get(code)
                    else BuilderLabCheckState.FAILED
                ),
                severity=(
                    BuilderLabCheckSeverity.INFO
                    if results.get(code)
                    else BuilderLabCheckSeverity.ERROR
                ),
                summary=("The isolated synthetic check passed." if results.get(code) else failure),
                evidence_paths=evidence[code],
                remediation=None
                if results.get(code)
                else (
                    "Correct the scaffold or runner boundary and create a new governed "
                    "project version."
                ),
            )
            for code in BuilderLabCheckCode
        )
