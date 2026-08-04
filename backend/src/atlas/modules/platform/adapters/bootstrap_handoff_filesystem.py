from __future__ import annotations

import os
import shutil
from hashlib import sha256
from pathlib import Path

from atlas.modules.platform.application.bootstrap_handoff_ports import (
    BootstrapHandoffError,
)
from atlas.modules.platform.domain.bootstrap_operational_handoff import (
    BootstrapHandoffPlan,
    HandoffReportDisposition,
    HandoffReportEvidence,
    HandoffTargetState,
    OperationalHandoffReceipt,
)

HANDOFF_REPORT_FILE_NAME = "atlas-operational-handoff-report.json"
HANDOFF_REPORT_EVIDENCE_ID = "handoff.operational-report"


class FilesystemBootstrapHandoffTarget:
    def __init__(self, *, root: Path, max_report_bytes: int) -> None:
        self._root = root.resolve()
        self._max_report_bytes = max_report_bytes

    async def inspect(self, *, plan: BootstrapHandoffPlan) -> HandoffTargetState:
        destination = self._target_root(plan)
        if not destination.exists() and not destination.is_symlink():
            return HandoffTargetState.EMPTY
        if destination.is_symlink() or not destination.is_dir():
            raise BootstrapHandoffError("bootstrap_handoff_unknown_target")
        files = self._safe_files(destination)
        if len(files) != 1 or files[0].name != HANDOFF_REPORT_FILE_NAME:
            raise BootstrapHandoffError("bootstrap_handoff_unknown_target")
        if files[0].read_bytes() != self._report(plan):
            raise BootstrapHandoffError("bootstrap_handoff_existing_conflict")
        return HandoffTargetState.REUSABLE

    async def publish(
        self, *, execution_id: str, plan: BootstrapHandoffPlan, report: bytes
    ) -> OperationalHandoffReceipt:
        expected = self._report(plan)
        if not report or report != expected or len(expected) > self._max_report_bytes:
            raise BootstrapHandoffError("bootstrap_handoff_report_invalid")
        attempt = self._root / ".staging" / execution_id
        destination = self._target_root(plan)
        self._prepare_attempt(attempt)
        try:
            output = attempt / HANDOFF_REPORT_FILE_NAME
            with output.open("xb") as target:
                target.write(expected)
                target.flush()
                os.fsync(target.fileno())
            output.chmod(0o640)
            disposition = (
                HandoffReportDisposition.PUBLISHED
                if self._publish_attempt(attempt, destination, expected)
                else HandoffReportDisposition.REUSED
            )
            return OperationalHandoffReceipt(
                checks=plan.checks,
                evidence=(
                    HandoffReportEvidence(
                        evidence_id=HANDOFF_REPORT_EVIDENCE_ID,
                        sha256=sha256(expected).hexdigest(),
                        size_bytes=len(expected),
                        disposition=disposition,
                    ),
                ),
            )
        except BootstrapHandoffError:
            self._cleanup(attempt)
            raise
        except (OSError, ValueError) as error:
            self._cleanup(attempt)
            raise BootstrapHandoffError("bootstrap_handoff_failed") from error

    async def cleanup_attempt(self, execution_id: str) -> None:
        self._cleanup(self._root / ".staging" / execution_id)

    def _prepare_attempt(self, attempt: Path) -> None:
        self._mkdir(self._root)
        self._mkdir(self._root / ".staging")
        if attempt.exists() or attempt.is_symlink():
            raise BootstrapHandoffError("bootstrap_handoff_attempt_conflict")
        attempt.mkdir()

    def _publish_attempt(self, attempt: Path, destination: Path, expected: bytes) -> bool:
        self._mkdir(destination.parent)
        if destination.exists() or destination.is_symlink():
            if self._verify(destination, expected):
                self._cleanup(attempt)
                return False
            raise BootstrapHandoffError("bootstrap_handoff_existing_conflict")
        try:
            attempt.rename(destination)
            return True
        except FileExistsError:
            if self._verify(destination, expected):
                self._cleanup(attempt)
                return False
            raise BootstrapHandoffError("bootstrap_handoff_existing_conflict") from None

    def _verify(self, destination: Path, expected: bytes) -> bool:
        if destination.is_symlink() or not destination.is_dir():
            raise BootstrapHandoffError("bootstrap_handoff_existing_conflict")
        files = self._safe_files(destination)
        if len(files) != 1 or files[0].name != HANDOFF_REPORT_FILE_NAME:
            raise BootstrapHandoffError("bootstrap_handoff_existing_conflict")
        return files[0].read_bytes() == expected

    @staticmethod
    def _safe_files(destination: Path) -> tuple[Path, ...]:
        entries = tuple(destination.rglob("*"))
        if any(item.is_symlink() for item in entries):
            raise BootstrapHandoffError("bootstrap_handoff_path_unsafe")
        return tuple(item for item in entries if item.is_file())

    def _cleanup(self, attempt: Path) -> None:
        try:
            attempt.relative_to(self._root / ".staging")
        except ValueError as error:
            raise BootstrapHandoffError("bootstrap_handoff_path_unsafe") from error
        if attempt.is_symlink():
            raise BootstrapHandoffError("bootstrap_handoff_path_unsafe")
        if attempt.exists():
            shutil.rmtree(attempt)

    @staticmethod
    def _mkdir(path: Path) -> None:
        for candidate in (path, *path.parents):
            if candidate.is_symlink():
                raise BootstrapHandoffError("bootstrap_handoff_path_unsafe")
        path.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or not path.is_dir():
            raise BootstrapHandoffError("bootstrap_handoff_path_unsafe")

    def _target_root(self, plan: BootstrapHandoffPlan) -> Path:
        return (
            self._root
            / "deployments"
            / plan.organization_id
            / plan.environment_id
            / plan.site_id
            / plan.release_id
            / "handoff-plans"
            / plan.handoff_plan_digest
            / plan.target_id
        )

    @staticmethod
    def _report(plan: BootstrapHandoffPlan) -> bytes:
        from atlas.modules.platform.application.bootstrap_operational_handoff import (
            BootstrapHandoffPlanService,
        )

        return BootstrapHandoffPlanService.render(plan)
