from __future__ import annotations

import json
from dataclasses import replace
from hashlib import sha256

from atlas.modules.connectors.domain.lab_self_test import (
    LAB_RUNNER_CHECK_CODES,
    ConnectorLabPlan,
    LabCheck,
    LabCheckSeverity,
    LabCheckState,
    LabExecutionLease,
    LabExecutionResult,
)

LAB_SELF_TEST_PROFILE = "atlas.connector-lab-self-test.readonly.v1"
LAB_ADAPTER_CONTRACT = "atlas.connector-lab-mock-target.v1"
LAB_RUNNER_RUNTIME = "mock-target.python312.v1"


class MockTargetConnectorLabRunner:
    def __init__(
        self,
        *,
        failed_check: str | None = None,
        observed_product_version: str | None = None,
        workspace_removed: bool = True,
    ) -> None:
        self._failed_check = failed_check
        self._observed_product_version = observed_product_version
        self._workspace_removed = workspace_removed

    async def run(
        self,
        *,
        files: dict[str, bytes],
        plan: ConnectorLabPlan,
        lease: LabExecutionLease,
    ) -> LabExecutionResult:
        if plan.validation_profile != LAB_SELF_TEST_PROFILE:
            raise ValueError("unsupported lab profile")
        if plan.adapter_contract != LAB_ADAPTER_CONTRACT or lease.plan_id != plan.plan_id:
            raise ValueError("lab adapter or lease mismatch")
        checks = tuple(
            self._check(code, code != self._failed_check) for code in LAB_RUNNER_CHECK_CODES
        )
        if not self._workspace_removed:
            checks = tuple(
                replace(
                    item,
                    state=LabCheckState.FAILED,
                    severity=LabCheckSeverity.ERROR,
                    summary="The isolated lab workspace was not removed.",
                    remediation="Remove residual evidence and repeat under an approved lab runner.",
                )
                if item.code == "lab.workspace.cleaned"
                else item
                for item in checks
            )
        request_count = plan.capability_count + 2
        request_bytes = min(plan.max_request_bytes, request_count * 128)
        response_bytes = min(plan.max_response_bytes, request_count * 512)
        digest_payload = {
            "adapter": LAB_ADAPTER_CONTRACT,
            "files": [
                (path, sha256(content).hexdigest()) for path, content in sorted(files.items())
            ],
            "plan_digest": plan.canonical_digest,
            "checks": [(item.code, item.state.value) for item in checks],
            "capability_count": plan.capability_count,
            "request_count": request_count,
            "request_bytes": request_bytes,
            "response_bytes": response_bytes,
        }
        evidence_digest = sha256(
            json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode("ascii")
        ).hexdigest()
        return LabExecutionResult(
            adapter_contract=LAB_ADAPTER_CONTRACT,
            runner_runtime=LAB_RUNNER_RUNTIME,
            observed_product_version=self._observed_product_version or plan.product_version,
            checks=checks,
            capability_count=plan.capability_count,
            tested_capability_count=plan.capability_count,
            request_count=request_count,
            request_bytes=request_bytes,
            response_bytes=response_bytes,
            duration_ms=25,
            evidence_digest=evidence_digest,
            lease_issued=True,
            session_closed=self._failed_check != "lab.session.closed",
            workspace_removed=self._workspace_removed,
        )

    @staticmethod
    def _check(code: str, passed: bool) -> LabCheck:
        return LabCheck(
            code=code,
            state=LabCheckState.PASSED if passed else LabCheckState.FAILED,
            severity=(LabCheckSeverity.INFORMATIONAL if passed else LabCheckSeverity.ERROR),
            summary=(
                "The required isolated lab control passed."
                if passed
                else "The required isolated lab control failed."
            ),
            remediation=(
                "No remediation is required."
                if passed
                else "Correct the approved lab boundary and repeat with a new governed package."
            ),
        )
