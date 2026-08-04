from __future__ import annotations

import os
import shutil
from hashlib import sha256
from pathlib import Path

from atlas.modules.platform.application.bootstrap_service_ports import BootstrapServiceError
from atlas.modules.platform.domain.bootstrap_service_deployment import (
    BootstrapServicePlan,
    ServiceDeploymentReceipt,
    ServiceRuntimeState,
    ServiceStateDisposition,
    ServiceStateEvidence,
    ServiceStatusEvidence,
    ServiceTargetState,
)

SERVICE_STATE_FILE_NAME = "atlas-service-state.json"
SERVICE_STATE_EVIDENCE_ID = "services.deployment-state"


class FilesystemBootstrapServiceTarget:
    def __init__(self, *, root: Path, max_state_bytes: int) -> None:
        self._root = root.resolve()
        self._max_state_bytes = max_state_bytes

    async def inspect(self, *, plan: BootstrapServicePlan) -> ServiceTargetState:
        destination = self._target_root(plan)
        if not destination.exists() and not destination.is_symlink():
            return ServiceTargetState.EMPTY
        if destination.is_symlink() or not destination.is_dir():
            raise BootstrapServiceError("bootstrap_service_unknown_target")
        entries = tuple(destination.rglob("*"))
        if any(item.is_symlink() for item in entries):
            raise BootstrapServiceError("bootstrap_service_path_unsafe")
        files = tuple(item for item in entries if item.is_file())
        if len(files) != 1 or files[0].name != SERVICE_STATE_FILE_NAME:
            raise BootstrapServiceError("bootstrap_service_unknown_target")
        expected = self._state_document(plan)
        if files[0].read_bytes() != expected:
            raise BootstrapServiceError("bootstrap_service_existing_conflict")
        return ServiceTargetState.REUSABLE

    async def deploy(
        self, *, execution_id: str, plan: BootstrapServicePlan, state_document: bytes
    ) -> ServiceDeploymentReceipt:
        expected = self._state_document(plan)
        if (
            not state_document
            or state_document != expected
            or len(state_document) > self._max_state_bytes
        ):
            raise BootstrapServiceError("bootstrap_service_state_invalid")
        attempt = self._attempt_root(execution_id)
        destination = self._target_root(plan)
        self._prepare_attempt(attempt)
        try:
            output = attempt / SERVICE_STATE_FILE_NAME
            with output.open("xb") as target:
                target.write(state_document)
                target.flush()
                os.fsync(target.fileno())
            output.chmod(0o640)
            disposition = (
                ServiceStateDisposition.PUBLISHED
                if self._publish_attempt(attempt, destination, state_document)
                else ServiceStateDisposition.REUSED
            )
            statuses = tuple(
                ServiceStatusEvidence(
                    service_id=item.service_id,
                    state=ServiceRuntimeState.READY,
                    startup_passed=True,
                    readiness_passed=True,
                    liveness_passed=True,
                )
                for item in plan.services
            )
            return ServiceDeploymentReceipt(
                service_statuses=statuses,
                evidence=(
                    ServiceStateEvidence(
                        evidence_id=SERVICE_STATE_EVIDENCE_ID,
                        sha256=sha256(state_document).hexdigest(),
                        size_bytes=len(state_document),
                        disposition=disposition,
                    ),
                ),
            )
        except BootstrapServiceError:
            self._cleanup_owned_attempt(attempt)
            raise
        except (OSError, ValueError) as error:
            self._cleanup_owned_attempt(attempt)
            raise BootstrapServiceError("bootstrap_service_deployment_failed") from error

    async def cleanup_attempt(self, execution_id: str) -> None:
        self._cleanup_owned_attempt(self._attempt_root(execution_id))

    def _prepare_attempt(self, attempt: Path) -> None:
        self._mkdir_without_symlink(self._root)
        self._mkdir_without_symlink(self._root / ".staging")
        if attempt.exists() or attempt.is_symlink():
            raise BootstrapServiceError("bootstrap_service_attempt_conflict")
        attempt.mkdir()

    def _publish_attempt(self, attempt: Path, destination: Path, expected: bytes) -> bool:
        self._mkdir_without_symlink(destination.parent)
        if destination.exists() or destination.is_symlink():
            if self._verify_existing(destination, expected):
                self._cleanup_owned_attempt(attempt)
                return False
            raise BootstrapServiceError("bootstrap_service_existing_conflict")
        try:
            attempt.rename(destination)
            return True
        except FileExistsError:
            if self._verify_existing(destination, expected):
                self._cleanup_owned_attempt(attempt)
                return False
            raise BootstrapServiceError("bootstrap_service_existing_conflict") from None

    @staticmethod
    def _verify_existing(destination: Path, expected: bytes) -> bool:
        if destination.is_symlink() or not destination.is_dir():
            raise BootstrapServiceError("bootstrap_service_existing_conflict")
        entries = tuple(destination.rglob("*"))
        if any(item.is_symlink() for item in entries):
            raise BootstrapServiceError("bootstrap_service_path_unsafe")
        files = tuple(item for item in entries if item.is_file())
        if len(files) != 1 or files[0].name != SERVICE_STATE_FILE_NAME:
            raise BootstrapServiceError("bootstrap_service_existing_conflict")
        return files[0].read_bytes() == expected

    def _cleanup_owned_attempt(self, attempt: Path) -> None:
        try:
            attempt.relative_to(self._root / ".staging")
        except ValueError as error:
            raise BootstrapServiceError("bootstrap_service_path_unsafe") from error
        if attempt.is_symlink():
            raise BootstrapServiceError("bootstrap_service_path_unsafe")
        if attempt.exists():
            shutil.rmtree(attempt)

    @staticmethod
    def _mkdir_without_symlink(path: Path) -> None:
        for candidate in (path, *path.parents):
            if candidate.is_symlink():
                raise BootstrapServiceError("bootstrap_service_path_unsafe")
        path.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or not path.is_dir():
            raise BootstrapServiceError("bootstrap_service_path_unsafe")

    def _attempt_root(self, execution_id: str) -> Path:
        return self._root / ".staging" / execution_id

    def _target_root(self, plan: BootstrapServicePlan) -> Path:
        return (
            self._root
            / "deployments"
            / plan.organization_id
            / plan.environment_id
            / plan.site_id
            / plan.release_id
            / "service-plans"
            / plan.service_plan_digest
            / plan.target_id
        )

    @staticmethod
    def _state_document(plan: BootstrapServicePlan) -> bytes:
        from atlas.modules.platform.application.bootstrap_service_deployment import (
            BootstrapServicePlanService,
        )

        return BootstrapServicePlanService.render(plan)
