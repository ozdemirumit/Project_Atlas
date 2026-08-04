from __future__ import annotations

import os
import shutil
from hashlib import sha256
from pathlib import Path

from atlas.modules.platform.application.bootstrap_identity_ports import BootstrapIdentityError
from atlas.modules.platform.domain.bootstrap_identity_handoff import (
    BootstrapIdentityPlan,
    IdentityHandoffReceipt,
    IdentityStateDisposition,
    IdentityStateEvidence,
    IdentityTargetState,
)

IDENTITY_STATE_FILE_NAME = "atlas-identity-state.json"
IDENTITY_STATE_EVIDENCE_ID = "identity.handoff-state"


class FilesystemBootstrapIdentityTarget:
    def __init__(self, *, root: Path, max_state_bytes: int) -> None:
        self._root = root.resolve()
        self._max_state_bytes = max_state_bytes

    async def inspect(self, *, plan: BootstrapIdentityPlan) -> IdentityTargetState:
        destination = self._target_root(plan)
        if not destination.exists() and not destination.is_symlink():
            return IdentityTargetState.EMPTY
        if destination.is_symlink() or not destination.is_dir():
            raise BootstrapIdentityError("bootstrap_identity_unknown_target")
        entries = tuple(destination.rglob("*"))
        if any(item.is_symlink() for item in entries):
            raise BootstrapIdentityError("bootstrap_identity_path_unsafe")
        files = tuple(item for item in entries if item.is_file())
        if len(files) != 1 or files[0].name != IDENTITY_STATE_FILE_NAME:
            raise BootstrapIdentityError("bootstrap_identity_unknown_target")
        if files[0].read_bytes() != self._state_document(plan):
            raise BootstrapIdentityError("bootstrap_identity_existing_conflict")
        return IdentityTargetState.REUSABLE

    async def publish(
        self, *, execution_id: str, plan: BootstrapIdentityPlan, state_document: bytes
    ) -> IdentityHandoffReceipt:
        expected = self._state_document(plan)
        if (
            not state_document
            or state_document != expected
            or len(expected) > self._max_state_bytes
        ):
            raise BootstrapIdentityError("bootstrap_identity_state_invalid")
        attempt = self._root / ".staging" / execution_id
        destination = self._target_root(plan)
        self._prepare_attempt(attempt)
        try:
            output = attempt / IDENTITY_STATE_FILE_NAME
            with output.open("xb") as target:
                target.write(expected)
                target.flush()
                os.fsync(target.fileno())
            output.chmod(0o640)
            disposition = (
                IdentityStateDisposition.PUBLISHED
                if self._publish_attempt(attempt, destination, expected)
                else IdentityStateDisposition.REUSED
            )
            return IdentityHandoffReceipt(
                group_mapping_count=len(plan.group_mappings),
                validation_count=5,
                evidence=(
                    IdentityStateEvidence(
                        evidence_id=IDENTITY_STATE_EVIDENCE_ID,
                        sha256=sha256(expected).hexdigest(),
                        size_bytes=len(expected),
                        disposition=disposition,
                    ),
                ),
            )
        except BootstrapIdentityError:
            self._cleanup(attempt)
            raise
        except (OSError, ValueError) as error:
            self._cleanup(attempt)
            raise BootstrapIdentityError("bootstrap_identity_handoff_failed") from error

    async def cleanup_attempt(self, execution_id: str) -> None:
        self._cleanup(self._root / ".staging" / execution_id)

    def _prepare_attempt(self, attempt: Path) -> None:
        self._mkdir(self._root)
        self._mkdir(self._root / ".staging")
        if attempt.exists() or attempt.is_symlink():
            raise BootstrapIdentityError("bootstrap_identity_attempt_conflict")
        attempt.mkdir()

    def _publish_attempt(self, attempt: Path, destination: Path, expected: bytes) -> bool:
        self._mkdir(destination.parent)
        if destination.exists() or destination.is_symlink():
            if self._verify(destination, expected):
                self._cleanup(attempt)
                return False
            raise BootstrapIdentityError("bootstrap_identity_existing_conflict")
        try:
            attempt.rename(destination)
            return True
        except FileExistsError:
            if self._verify(destination, expected):
                self._cleanup(attempt)
                return False
            raise BootstrapIdentityError("bootstrap_identity_existing_conflict") from None

    @staticmethod
    def _verify(destination: Path, expected: bytes) -> bool:
        if destination.is_symlink() or not destination.is_dir():
            raise BootstrapIdentityError("bootstrap_identity_existing_conflict")
        entries = tuple(destination.rglob("*"))
        if any(item.is_symlink() for item in entries):
            raise BootstrapIdentityError("bootstrap_identity_path_unsafe")
        files = tuple(item for item in entries if item.is_file())
        if len(files) != 1 or files[0].name != IDENTITY_STATE_FILE_NAME:
            raise BootstrapIdentityError("bootstrap_identity_existing_conflict")
        return files[0].read_bytes() == expected

    def _cleanup(self, attempt: Path) -> None:
        try:
            attempt.relative_to(self._root / ".staging")
        except ValueError as error:
            raise BootstrapIdentityError("bootstrap_identity_path_unsafe") from error
        if attempt.is_symlink():
            raise BootstrapIdentityError("bootstrap_identity_path_unsafe")
        if attempt.exists():
            shutil.rmtree(attempt)

    @staticmethod
    def _mkdir(path: Path) -> None:
        for candidate in (path, *path.parents):
            if candidate.is_symlink():
                raise BootstrapIdentityError("bootstrap_identity_path_unsafe")
        path.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or not path.is_dir():
            raise BootstrapIdentityError("bootstrap_identity_path_unsafe")

    def _target_root(self, plan: BootstrapIdentityPlan) -> Path:
        return (
            self._root
            / "deployments"
            / plan.organization_id
            / plan.environment_id
            / plan.site_id
            / plan.release_id
            / "identity-plans"
            / plan.identity_plan_digest
            / plan.target_id
        )

    @staticmethod
    def _state_document(plan: BootstrapIdentityPlan) -> bytes:
        from atlas.modules.platform.application.bootstrap_identity_handoff import (
            BootstrapIdentityPlanService,
        )

        return BootstrapIdentityPlanService.render(plan)
