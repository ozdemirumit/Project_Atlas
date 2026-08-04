from __future__ import annotations

import os
import shutil
from hashlib import sha256
from pathlib import Path

from atlas.modules.platform.application.bootstrap_trust_ports import BootstrapTrustError
from atlas.modules.platform.domain.bootstrap_trust_provisioning import (
    BootstrapTrustPlan,
    TrustFileDisposition,
    TrustFileEvidence,
    TrustProvisioningReceipt,
)

TRUST_BUNDLE_FILE_ID = "trust.bundle"
TRUST_BUNDLE_FILE_NAME = "trust-bundle.pem"
WORKLOAD_CATALOG_FILE_ID = "trust.workload-identities"
WORKLOAD_CATALOG_FILE_NAME = "workload-identities.json"


class FilesystemBootstrapTrustPublisher:
    def __init__(self, *, root: Path, max_total_bytes: int) -> None:
        self._root = root.resolve()
        self._max_total_bytes = max_total_bytes

    async def cleanup_attempt(self, execution_id: str) -> None:
        self._cleanup_owned_attempt(self._attempt_root(execution_id))

    async def publish(
        self,
        *,
        execution_id: str,
        plan: BootstrapTrustPlan,
        trust_bundle: bytes,
        identity_catalog: bytes,
    ) -> TrustProvisioningReceipt:
        contents = {
            TRUST_BUNDLE_FILE_NAME: trust_bundle,
            WORKLOAD_CATALOG_FILE_NAME: identity_catalog,
        }
        total_bytes = sum(len(content) for content in contents.values())
        if (
            any(not content for content in contents.values())
            or total_bytes > self._max_total_bytes
            or b"PRIVATE KEY" in trust_bundle
            or b"PRIVATE KEY" in identity_catalog
        ):
            raise BootstrapTrustError("bootstrap_trust_content_invalid")
        attempt_root = self._attempt_root(execution_id)
        destination_root = self._trust_root(plan)
        self._prepare_attempt(attempt_root)
        try:
            for name, content in contents.items():
                output = attempt_root / name
                with output.open("xb") as target:
                    target.write(content)
                    target.flush()
                    os.fsync(target.fileno())
                output.chmod(0o644 if name == TRUST_BUNDLE_FILE_NAME else 0o640)
            disposition = (
                TrustFileDisposition.PUBLISHED
                if self._publish_attempt(attempt_root, destination_root, contents)
                else TrustFileDisposition.REUSED
            )
            return TrustProvisioningReceipt(
                anchor_count=len(plan.anchors),
                workload_identity_count=len(plan.workload_identities),
                evidence=(
                    self._evidence(TRUST_BUNDLE_FILE_ID, trust_bundle, disposition),
                    self._evidence(WORKLOAD_CATALOG_FILE_ID, identity_catalog, disposition),
                ),
            )
        except BootstrapTrustError:
            self._cleanup_owned_attempt(attempt_root)
            raise
        except (OSError, ValueError) as error:
            self._cleanup_owned_attempt(attempt_root)
            raise BootstrapTrustError("bootstrap_trust_publish_failed") from error

    def _prepare_attempt(self, attempt_root: Path) -> None:
        self._mkdir_without_symlink(self._root)
        self._mkdir_without_symlink(self._root / ".staging")
        if attempt_root.exists() or attempt_root.is_symlink():
            raise BootstrapTrustError("bootstrap_trust_attempt_conflict")
        attempt_root.mkdir()

    def _publish_attempt(
        self, attempt_root: Path, destination_root: Path, contents: dict[str, bytes]
    ) -> bool:
        self._mkdir_without_symlink(destination_root.parent)
        if destination_root.exists() or destination_root.is_symlink():
            if self._verify_existing(destination_root, contents):
                self._cleanup_owned_attempt(attempt_root)
                return False
            raise BootstrapTrustError("bootstrap_trust_existing_conflict")
        try:
            attempt_root.rename(destination_root)
            return True
        except FileExistsError:
            if self._verify_existing(destination_root, contents):
                self._cleanup_owned_attempt(attempt_root)
                return False
            raise BootstrapTrustError("bootstrap_trust_existing_conflict") from None

    @staticmethod
    def _verify_existing(destination_root: Path, contents: dict[str, bytes]) -> bool:
        if destination_root.is_symlink() or not destination_root.is_dir():
            raise BootstrapTrustError("bootstrap_trust_existing_conflict")
        entries = tuple(destination_root.rglob("*"))
        if any(item.is_symlink() for item in entries):
            raise BootstrapTrustError("bootstrap_trust_path_unsafe")
        regular_files = tuple(sorted(item.name for item in entries if item.is_file()))
        if regular_files != tuple(sorted(contents)):
            raise BootstrapTrustError("bootstrap_trust_existing_conflict")
        for name, expected in contents.items():
            if (destination_root / name).read_bytes() != expected:
                raise BootstrapTrustError("bootstrap_trust_existing_conflict")
        return True

    def _cleanup_owned_attempt(self, attempt_root: Path) -> None:
        staging_root = self._root / ".staging"
        try:
            attempt_root.relative_to(staging_root)
        except ValueError as error:
            raise BootstrapTrustError("bootstrap_trust_path_unsafe") from error
        if attempt_root.is_symlink():
            raise BootstrapTrustError("bootstrap_trust_path_unsafe")
        if attempt_root.exists():
            shutil.rmtree(attempt_root)

    @staticmethod
    def _mkdir_without_symlink(path: Path) -> None:
        for candidate in (path, *path.parents):
            if candidate.is_symlink():
                raise BootstrapTrustError("bootstrap_trust_path_unsafe")
        path.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or not path.is_dir():
            raise BootstrapTrustError("bootstrap_trust_path_unsafe")

    def _attempt_root(self, execution_id: str) -> Path:
        return self._root / ".staging" / execution_id

    def _trust_root(self, plan: BootstrapTrustPlan) -> Path:
        return (
            self._root
            / "deployments"
            / plan.organization_id
            / plan.environment_id
            / plan.site_id
            / plan.release_id
            / "trust-plans"
            / plan.trust_plan_digest
        )

    @staticmethod
    def _evidence(
        file_id: str, content: bytes, disposition: TrustFileDisposition
    ) -> TrustFileEvidence:
        return TrustFileEvidence(
            file_id=file_id,
            sha256=sha256(content).hexdigest(),
            size_bytes=len(content),
            disposition=disposition,
        )
