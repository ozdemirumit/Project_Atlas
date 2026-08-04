from __future__ import annotations

import json
import os
import shutil
from hashlib import sha256
from pathlib import Path

from atlas.modules.platform.application.bootstrap_data_ports import BootstrapDataError
from atlas.modules.platform.domain.bootstrap_data_initialization import (
    BootstrapDataPlan,
    DataInitializationReceipt,
    DataStateDisposition,
    DataStateEvidence,
    DataTargetState,
)

DATA_STATE_FILE_NAME = "atlas-schema-state.json"
DATA_STATE_EVIDENCE_ID = "data.schema-state"


class FilesystemBootstrapDataTarget:
    def __init__(self, *, root: Path, max_state_bytes: int) -> None:
        self._root = root.resolve()
        self._max_state_bytes = max_state_bytes

    async def inspect(self, *, plan: BootstrapDataPlan) -> DataTargetState:
        destination = self._target_root(plan)
        if not destination.exists() and not destination.is_symlink():
            return DataTargetState.EMPTY
        if destination.is_symlink() or not destination.is_dir():
            raise BootstrapDataError("bootstrap_data_unknown_target")
        entries = tuple(destination.rglob("*"))
        if any(item.is_symlink() for item in entries):
            raise BootstrapDataError("bootstrap_data_path_unsafe")
        files = tuple(item for item in entries if item.is_file())
        if len(files) != 1 or files[0].name != DATA_STATE_FILE_NAME:
            raise BootstrapDataError("bootstrap_data_unknown_target")
        content = files[0].read_bytes()
        if content != self._expected_state_document(plan):
            raise BootstrapDataError("bootstrap_data_existing_conflict")
        return DataTargetState.REUSABLE

    async def initialize(
        self, *, execution_id: str, plan: BootstrapDataPlan, state_document: bytes
    ) -> DataInitializationReceipt:
        if not state_document or len(state_document) > self._max_state_bytes:
            raise BootstrapDataError("bootstrap_data_state_invalid")
        attempt = self._attempt_root(execution_id)
        destination = self._target_root(plan)
        self._prepare_attempt(attempt)
        try:
            output = attempt / DATA_STATE_FILE_NAME
            with output.open("xb") as target:
                target.write(state_document)
                target.flush()
                os.fsync(target.fileno())
            output.chmod(0o640)
            disposition = (
                DataStateDisposition.PUBLISHED
                if self._publish_attempt(attempt, destination, state_document)
                else DataStateDisposition.REUSED
            )
            return DataInitializationReceipt(
                migration_count=len(plan.migrations),
                verified_object_count=sum(item.expected_object_count for item in plan.migrations),
                evidence=(
                    DataStateEvidence(
                        evidence_id=DATA_STATE_EVIDENCE_ID,
                        sha256=sha256(state_document).hexdigest(),
                        size_bytes=len(state_document),
                        disposition=disposition,
                    ),
                ),
            )
        except BootstrapDataError:
            self._cleanup_owned_attempt(attempt)
            raise
        except (OSError, ValueError) as error:
            self._cleanup_owned_attempt(attempt)
            raise BootstrapDataError("bootstrap_data_initialization_failed") from error

    async def cleanup_attempt(self, execution_id: str) -> None:
        self._cleanup_owned_attempt(self._attempt_root(execution_id))

    def _prepare_attempt(self, attempt: Path) -> None:
        self._mkdir_without_symlink(self._root)
        self._mkdir_without_symlink(self._root / ".staging")
        if attempt.exists() or attempt.is_symlink():
            raise BootstrapDataError("bootstrap_data_attempt_conflict")
        attempt.mkdir()

    def _publish_attempt(self, attempt: Path, destination: Path, expected: bytes) -> bool:
        self._mkdir_without_symlink(destination.parent)
        if destination.exists() or destination.is_symlink():
            if self._verify_existing(destination, expected):
                self._cleanup_owned_attempt(attempt)
                return False
            raise BootstrapDataError("bootstrap_data_existing_conflict")
        try:
            attempt.rename(destination)
            return True
        except FileExistsError:
            if self._verify_existing(destination, expected):
                self._cleanup_owned_attempt(attempt)
                return False
            raise BootstrapDataError("bootstrap_data_existing_conflict") from None

    @staticmethod
    def _verify_existing(destination: Path, expected: bytes) -> bool:
        if destination.is_symlink() or not destination.is_dir():
            raise BootstrapDataError("bootstrap_data_existing_conflict")
        entries = tuple(destination.rglob("*"))
        if any(item.is_symlink() for item in entries):
            raise BootstrapDataError("bootstrap_data_path_unsafe")
        files = tuple(item for item in entries if item.is_file())
        if len(files) != 1 or files[0].name != DATA_STATE_FILE_NAME:
            raise BootstrapDataError("bootstrap_data_existing_conflict")
        return files[0].read_bytes() == expected

    def _cleanup_owned_attempt(self, attempt: Path) -> None:
        try:
            attempt.relative_to(self._root / ".staging")
        except ValueError as error:
            raise BootstrapDataError("bootstrap_data_path_unsafe") from error
        if attempt.is_symlink():
            raise BootstrapDataError("bootstrap_data_path_unsafe")
        if attempt.exists():
            shutil.rmtree(attempt)

    @staticmethod
    def _mkdir_without_symlink(path: Path) -> None:
        for candidate in (path, *path.parents):
            if candidate.is_symlink():
                raise BootstrapDataError("bootstrap_data_path_unsafe")
        path.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or not path.is_dir():
            raise BootstrapDataError("bootstrap_data_path_unsafe")

    def _attempt_root(self, execution_id: str) -> Path:
        return self._root / ".staging" / execution_id

    def _target_root(self, plan: BootstrapDataPlan) -> Path:
        return (
            self._root
            / "deployments"
            / plan.organization_id
            / plan.environment_id
            / plan.site_id
            / plan.release_id
            / "data-plans"
            / plan.data_plan_digest
            / plan.target_id
        )

    @staticmethod
    def _expected_state_document(plan: BootstrapDataPlan) -> bytes:
        payload = {
            "schema_version": "atlas.synthetic-schema-state.v1",
            "release_id": plan.release_id,
            "profile": plan.profile.value,
            "organization_id": plan.organization_id,
            "environment_id": plan.environment_id,
            "site_id": plan.site_id,
            "configuration_digest": plan.configuration_digest,
            "trust_plan_digest": plan.trust_plan_digest,
            "migration_artifact_digest": plan.migration_artifact_digest,
            "data_plan_digest": plan.data_plan_digest,
            "target_id": plan.target_id,
            "target_kind": plan.target_kind,
            "schema_revision": plan.target_revision,
            "owner_id": "owner.project-atlas",
            "backup_applicability": plan.backup_applicability.value,
            "migrations": [
                {
                    "migration_id": item.migration_id,
                    "sequence": item.sequence,
                    "sha256": item.sha256,
                    "from_revision": item.from_revision,
                    "to_revision": item.to_revision,
                    "compatibility": item.compatibility.value,
                    "reversible": item.reversible,
                    "destructive": item.destructive,
                    "recovery_code": item.recovery_code,
                    "expected_object_count": item.expected_object_count,
                }
                for item in plan.migrations
            ],
            "verified_object_count": sum(item.expected_object_count for item in plan.migrations),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
