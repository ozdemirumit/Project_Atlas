from __future__ import annotations

import io
import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4
from zipfile import ZIP_STORED, BadZipFile, ZipFile, ZipInfo

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.platform.application.bootstrap_state_ports import BootstrapStateRepository
from atlas.modules.platform.domain.bootstrap_state import BootstrapRunRecord, BootstrapRunState
from atlas.modules.recovery.application.ports import (
    BackupArchiveStore,
    RecoveryError,
    RecoveryRepository,
)
from atlas.modules.recovery.domain.backup import (
    BackupEntry,
    BackupPreview,
    BackupRecord,
    BackupState,
    BackupTargetState,
    RestoreValidation,
    RestoreValidationState,
)

SCHEMA_VERSION = "atlas.logical-backup-preview.v1"
CATALOG_VERSION = "atlas.synthetic-logical-backup-catalog.v1"
MANIFEST_FILE = "00-backup-integrity-manifest.json"
CATALOG: tuple[tuple[str, str, bool], ...] = (
    ("backup.release-state", "10-release-state.json", True),
    ("backup.configuration-state", "20-configuration-state.json", True),
    ("backup.checkpoint-state", "30-checkpoint-state.json", True),
    ("backup.verification-state", "40-verification-state.json", True),
    ("backup.identity-handoff", "50-identity-handoff.json", False),
    ("backup.integration-validation", "60-integration-validation.json", False),
    ("backup.operational-handoff", "70-operational-handoff.json", True),
)
PROHIBITED_MARKERS = (
    b'"password"',
    b'"authorization"',
    b"bearer ",
    b"private key",
    b"reader token",
    b'"prompt"',
    b"customer document",
    b"command line",
    b"://",
)
VALIDATION_CHECKS = (
    "restore.check.archive-digest",
    "restore.check.manifest-schema",
    "restore.check.entry-digests",
    "restore.check.component-schemas",
    "restore.check.source-consistency",
    "restore.check.isolation-boundary",
)


class RecoveryService:
    def __init__(
        self,
        *,
        bootstrap_repository: BootstrapStateRepository,
        repository: RecoveryRepository,
        archive_store: BackupArchiveStore,
        audit_sink: AuditSink,
        environment_id: str,
        site_id: str,
        max_content_bytes: int,
        max_archive_bytes: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._bootstrap_repository = bootstrap_repository
        self._repository = repository
        self._archive_store = archive_store
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._site_id = site_id
        self._max_content_bytes = max_content_bytes
        self._max_archive_bytes = max_archive_bytes
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def repository(self) -> RecoveryRepository:
        return self._repository

    async def close(self) -> None:
        await self._repository.close()

    async def preview(
        self, *, actor: AuthenticatedSubject, source_run_id: str, component_ids: tuple[str, ...]
    ) -> BackupPreview:
        run = await self._source_run(actor, source_run_id)
        normalized = tuple(sorted(set(component_ids)))
        catalog_ids = {item[0] for item in CATALOG}
        required = {item[0] for item in CATALOG if item[2]}
        if not normalized or any(item not in catalog_ids for item in normalized):
            raise RecoveryError("backup_component_invalid")
        if not required.issubset(normalized):
            raise RecoveryError("backup_required_component_missing")
        content = self._entry_content(run)
        selected: dict[str, bytes] = {}
        entries: list[BackupEntry] = []
        for entry_id, file_name, mandatory in CATALOG:
            if entry_id not in normalized:
                continue
            payload = content[entry_id]
            self._scan(payload)
            selected[file_name] = payload
            entries.append(
                BackupEntry(
                    entry_id,
                    file_name,
                    "internal",
                    mandatory,
                    len(payload),
                    sha256(payload).hexdigest(),
                )
            )
        content_bytes = sum(len(value) for value in selected.values())
        if content_bytes > self._max_content_bytes:
            raise RecoveryError("backup_content_budget_exceeded")
        source_digest = self._source_digest(run)
        preview_digest = self._digest(
            {
                "schema_version": SCHEMA_VERSION,
                "catalog_version": CATALOG_VERSION,
                "organization_id": actor.organization_id,
                "environment_id": self._environment_id,
                "site_id": self._site_id,
                "source_run_id": run.run_id,
                "source_run_version": run.version,
                "source_evidence_digest": source_digest,
                "component_ids": normalized,
                "entries": [(item.entry_id, item.sha256, item.size_bytes) for item in entries],
            }
        )
        target_id = f"target.logical-backup.{preview_digest[:24]}"
        archive = self._render_archive(run, tuple(entries), selected, preview_digest, source_digest)
        if len(archive) > self._max_archive_bytes:
            raise RecoveryError("backup_archive_budget_exceeded")
        state = BackupTargetState(
            await self._archive_store.inspect(target_id=target_id, expected=archive)
        )
        now = self._clock()
        return BackupPreview(
            preview_id=f"backup-preview.{preview_digest[:24]}",
            schema_version=SCHEMA_VERSION,
            catalog_version=CATALOG_VERSION,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
            source_run_id=run.run_id,
            source_run_version=run.version,
            release_id=run.identity.release_id,
            source_evidence_digest=source_digest,
            component_ids=normalized,
            entries=tuple(entries),
            content_bytes=content_bytes,
            max_content_bytes=self._max_content_bytes,
            preview_digest=preview_digest,
            target_id=target_id,
            target_state=state,
            archive_sha256=sha256(archive).hexdigest(),
            archive_size_bytes=len(archive),
            generated_at=now,
            expires_at=now + timedelta(hours=24),
            creatable=True,
        )

    async def create_backup(
        self,
        *,
        actor: AuthenticatedSubject,
        source_run_id: str,
        source_run_version: int,
        component_ids: tuple[str, ...],
        preview_digest: str,
        archive_sha256: str,
        target_id: str,
        expected_target_state: BackupTargetState,
        justification: str,
        confirmed: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> BackupRecord:
        if not confirmed or not 12 <= len(justification.strip()) <= 500:
            raise RecoveryError("backup_confirmation_required")
        fingerprint = self._digest(
            {
                "source_run_id": source_run_id,
                "source_run_version": source_run_version,
                "component_ids": tuple(sorted(set(component_ids))),
                "preview_digest": preview_digest,
                "archive_sha256": archive_sha256,
                "target_id": target_id,
                "expected_target_state": expected_target_state.value,
                "justification": justification.strip(),
                "confirmed": confirmed,
            }
        )
        prior = await self._repository.get_backup(
            actor_id=actor.subject_id, idempotency_key=idempotency_key
        )
        if prior is not None:
            if prior.request_fingerprint != fingerprint:
                raise RecoveryError("backup_idempotency_conflict")
            return replace(prior, reused=True)
        preview = await self.preview(
            actor=actor, source_run_id=source_run_id, component_ids=component_ids
        )
        if (
            preview.source_run_version != source_run_version
            or preview.preview_digest != preview_digest
            or preview.archive_sha256 != archive_sha256
            or preview.target_id != target_id
            or preview.target_state is not expected_target_state
        ):
            raise RecoveryError("backup_preview_stale")
        await self._audit(
            actor,
            correlation_id,
            idempotency_key,
            "logical_backup_create_authorized",
            (("preview_digest", preview_digest),),
            "backup.logical.create",
            "C2",
        )
        run = await self._source_run(actor, source_run_id)
        content = self._entry_content(run)
        selected = {
            file_name: content[entry_id]
            for entry_id, file_name, _ in CATALOG
            if entry_id in preview.component_ids
        }
        archive = self._render_archive(
            run, preview.entries, selected, preview.preview_digest, preview.source_evidence_digest
        )
        backup_key = f"{actor.subject_id}:{idempotency_key}:{fingerprint}"
        backup_id = f"logical-backup.{sha256(backup_key.encode()).hexdigest()[:24]}"
        digest, size, name, reused = await self._archive_store.publish(
            backup_id=backup_id, target_id=target_id, expected=archive
        )
        if digest != preview.archive_sha256 or size != preview.archive_size_bytes:
            raise RecoveryError("backup_archive_changed")
        now = self._clock()
        record = BackupRecord(
            backup_id=backup_id,
            state=BackupState.COMPLETED,
            actor_id=actor.subject_id,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
            source_run_id=source_run_id,
            source_run_version=source_run_version,
            preview_digest=preview_digest,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            target_id=target_id,
            archive_sha256=digest,
            archive_size_bytes=size,
            archive_name=name,
            entry_count=len(preview.entries),
            created_at=now,
            expires_at=now + timedelta(days=7),
            reused=reused,
        )
        if not await self._repository.add_backup(record):
            raced = await self._repository.get_backup(
                actor_id=actor.subject_id, idempotency_key=idempotency_key
            )
            if raced is None or raced.request_fingerprint != fingerprint:
                raise RecoveryError("backup_idempotency_conflict")
            return replace(raced, reused=True)
        await self._audit(
            actor,
            correlation_id,
            idempotency_key,
            "logical_backup_create_completed",
            (("backup_id", backup_id), ("archive_sha256", digest)),
            "backup.logical.create",
            "C2",
        )
        return record

    async def validate_restore(
        self,
        *,
        actor: AuthenticatedSubject,
        backup_id: str,
        archive_sha256: str,
        confirmed_isolated: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> RestoreValidation:
        if not confirmed_isolated:
            raise RecoveryError("restore_validation_confirmation_required")
        fingerprint = self._digest(
            {
                "backup_id": backup_id,
                "archive_sha256": archive_sha256,
                "confirmed_isolated": confirmed_isolated,
            }
        )
        prior = await self._repository.get_validation(
            actor_id=actor.subject_id, idempotency_key=idempotency_key
        )
        if prior is not None:
            if prior.request_fingerprint != fingerprint:
                raise RecoveryError("restore_validation_idempotency_conflict")
            return replace(prior, reused=True)
        backup = await self._repository.get_backup_by_id(
            actor_id=actor.subject_id, backup_id=backup_id
        )
        if backup is None:
            raise RecoveryError("backup_archive_unavailable")
        if backup.archive_sha256 != archive_sha256:
            raise RecoveryError("restore_validation_archive_changed")
        archive = await self._archive_store.read(
            target_id=backup.target_id, max_bytes=self._max_archive_bytes
        )
        if sha256(archive).hexdigest() != archive_sha256:
            raise RecoveryError("restore_validation_archive_changed")
        self._validate_archive(archive, backup)
        validation_digest = self._digest(
            {
                "backup_id": backup_id,
                "archive_sha256": archive_sha256,
                "check_ids": VALIDATION_CHECKS,
                "entry_count": backup.entry_count,
                "isolated_target": True,
            }
        )
        await self._audit(
            actor,
            correlation_id,
            idempotency_key,
            "isolated_restore_validation_passed",
            (("backup_id", backup_id), ("validation_digest", validation_digest)),
            "backup.logical.restore-validate",
            "C1",
        )
        record = RestoreValidation(
            validation_id=f"restore-validation.{validation_digest[:24]}",
            state=RestoreValidationState.PASSED,
            backup_id=backup_id,
            actor_id=actor.subject_id,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            archive_sha256=archive_sha256,
            validation_digest=validation_digest,
            check_ids=VALIDATION_CHECKS,
            entry_count=backup.entry_count,
            validated_at=self._clock(),
        )
        if not await self._repository.add_validation(record):
            raced = await self._repository.get_validation(
                actor_id=actor.subject_id, idempotency_key=idempotency_key
            )
            if raced is None or raced.request_fingerprint != fingerprint:
                raise RecoveryError("restore_validation_idempotency_conflict")
            return replace(raced, reused=True)
        return record

    async def _source_run(
        self, actor: AuthenticatedSubject, source_run_id: str
    ) -> BootstrapRunRecord:
        run = await self._bootstrap_repository.get_current(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
        )
        if (
            run is None
            or run.run_id != source_run_id
            or run.state is not BootstrapRunState.COMPLETED
            or run.operational_handoff is None
            or run.end_to_end_verification is None
            or run.identity_handoff is None
            or run.integration_validation is None
        ):
            raise RecoveryError("backup_source_unavailable")
        return run

    def _entry_content(self, run: BootstrapRunRecord) -> dict[str, bytes]:
        identity = run.identity_handoff
        integrations = run.integration_validation
        verification = run.end_to_end_verification
        handoff = run.operational_handoff
        assert identity and integrations and verification and handoff
        common = {
            "source_run_id": run.run_id,
            "source_run_version": run.version,
            "release_id": run.identity.release_id,
            "configuration_digest": run.identity.configuration_digest,
        }
        return {
            "backup.release-state": self._json(
                {
                    **common,
                    "schema_version": "atlas.logical-backup-release-state.v1",
                    "profile": run.identity.profile.value,
                    "plan_digest": run.identity.plan_digest,
                }
            ),
            "backup.configuration-state": self._json(
                {
                    **common,
                    "schema_version": "atlas.logical-backup-configuration-state.v1",
                    "configuration_schema": "atlas.effective-configuration.v1",
                    "secret_values_included": False,
                    "private_endpoints_included": False,
                }
            ),
            "backup.checkpoint-state": self._json(
                {
                    **common,
                    "schema_version": "atlas.logical-backup-checkpoint-state.v1",
                    "run_state": run.state.value,
                    "phase_order": list(run.identity.phase_ids),
                    "checkpoints": [
                        {
                            "phase_id": item.phase_id,
                            "state": item.state.value,
                            "safe_output_references": list(item.safe_output_references),
                        }
                        for item in run.checkpoints
                    ],
                }
            ),
            "backup.verification-state": self._json(
                {
                    **common,
                    "schema_version": "atlas.logical-backup-verification-state.v1",
                    "verification_report_digest": handoff.verification_report_digest,
                    "passed_count": verification.passed_count,
                    "mandatory_pass_count": verification.mandatory_pass_count,
                    "external_operation_count": verification.external_operation_count,
                }
            ),
            "backup.identity-handoff": self._json(
                {
                    **common,
                    "schema_version": "atlas.logical-backup-identity-handoff.v1",
                    "state": identity.state.value,
                    "group_mapping_count": identity.group_mapping_count,
                    "validation_count": identity.validation_count,
                    "evidence_digests": [item.sha256 for item in identity.evidence],
                    "secret_values_included": False,
                }
            ),
            "backup.integration-validation": self._json(
                {
                    **common,
                    "schema_version": "atlas.logical-backup-integration-validation.v1",
                    "state": integrations.state.value,
                    "mandatory_pass_count": integrations.mandatory_pass_count,
                    "activation_count": integrations.activation_count,
                    "network_request_count": integrations.network_request_count,
                    "secret_resolution_count": integrations.secret_resolution_count,
                }
            ),
            "backup.operational-handoff": self._json(
                {
                    **common,
                    "schema_version": "atlas.logical-backup-operational-handoff.v1",
                    "state": handoff.state.value,
                    "readiness_class": handoff.readiness_class.value,
                    "handoff_report_digest": handoff.evidence[0].sha256,
                    "backup_restore_validated": False,
                    "production_ready": False,
                    "external_operation_count": handoff.external_operation_count,
                }
            ),
        }

    def _render_archive(
        self,
        run: BootstrapRunRecord,
        entries: tuple[BackupEntry, ...],
        selected: dict[str, bytes],
        preview_digest: str,
        source_digest: str,
    ) -> bytes:
        manifest = self._json(
            {
                "schema_version": "atlas.logical-backup-integrity-manifest.v1",
                "catalog_version": CATALOG_VERSION,
                "preview_digest": preview_digest,
                "source_run_id": run.run_id,
                "source_run_version": run.version,
                "release_id": run.identity.release_id,
                "configuration_digest": run.identity.configuration_digest,
                "source_evidence_digest": source_digest,
                "entries": [
                    {
                        "entry_id": item.entry_id,
                        "file_name": item.file_name,
                        "classification": item.classification,
                        "mandatory": item.mandatory,
                        "size_bytes": item.size_bytes,
                        "sha256": item.sha256,
                    }
                    for item in entries
                ],
                "safety": {
                    "external_transfer_performed": False,
                    "active_restore_performed": False,
                    "secret_export_performed": False,
                    "network_request_performed": False,
                    "infrastructure_mutation_performed": False,
                },
            }
        )
        return self._archive({MANIFEST_FILE: manifest, **selected})

    def _validate_archive(self, payload: bytes, backup: BackupRecord) -> None:
        try:
            with ZipFile(io.BytesIO(payload)) as archive:
                infos = archive.infolist()
                names = [item.filename for item in infos]
                if names != sorted(names) or len(names) != len(set(names)) or not names:
                    raise RecoveryError("restore_validation_archive_invalid")
                if any(item.compress_type != ZIP_STORED or item.is_dir() for item in infos):
                    raise RecoveryError("restore_validation_archive_invalid")
                if names[0] != MANIFEST_FILE:
                    raise RecoveryError("restore_validation_manifest_invalid")
                raw_manifest = archive.read(MANIFEST_FILE)
                self._scan(raw_manifest)
                manifest = json.loads(raw_manifest)
                if (
                    not isinstance(manifest, dict)
                    or manifest.get("schema_version")
                    != "atlas.logical-backup-integrity-manifest.v1"
                    or manifest.get("catalog_version") != CATALOG_VERSION
                    or manifest.get("source_run_id") != backup.source_run_id
                    or manifest.get("source_run_version") != backup.source_run_version
                ):
                    raise RecoveryError("restore_validation_manifest_invalid")
                entries = manifest.get("entries")
                if not isinstance(entries, list) or len(entries) != backup.entry_count:
                    raise RecoveryError("restore_validation_manifest_invalid")
                expected_names = {MANIFEST_FILE}
                isolated: dict[str, dict[str, object]] = {}
                for item in entries:
                    if not isinstance(item, dict):
                        raise RecoveryError("restore_validation_manifest_invalid")
                    name, digest = item.get("file_name"), item.get("sha256")
                    if not isinstance(name, str) or not isinstance(digest, str):
                        raise RecoveryError("restore_validation_manifest_invalid")
                    expected_names.add(name)
                    content = archive.read(name)
                    self._scan(content)
                    if sha256(content).hexdigest() != digest or len(content) != item.get(
                        "size_bytes"
                    ):
                        raise RecoveryError("restore_validation_entry_changed")
                    restored = json.loads(content)
                    if (
                        not isinstance(restored, dict)
                        or not str(restored.get("schema_version", "")).startswith(
                            "atlas.logical-backup-"
                        )
                        or restored.get("source_run_id") != backup.source_run_id
                        or restored.get("source_run_version") != backup.source_run_version
                        or restored.get("release_id") != manifest.get("release_id")
                        or restored.get("configuration_digest")
                        != manifest.get("configuration_digest")
                    ):
                        raise RecoveryError("restore_validation_relationship_invalid")
                    isolated[name] = restored
                if set(names) != expected_names or len(isolated) != backup.entry_count:
                    raise RecoveryError("restore_validation_archive_invalid")
                safety = manifest.get("safety")
                if not isinstance(safety, dict) or any(safety.values()):
                    raise RecoveryError("restore_validation_safety_failed")
        except (BadZipFile, KeyError, json.JSONDecodeError, RuntimeError) as error:
            if isinstance(error, RecoveryError):
                raise
            raise RecoveryError("restore_validation_archive_invalid") from error

    @staticmethod
    def _archive(files: dict[str, bytes]) -> bytes:
        output = io.BytesIO()
        with ZipFile(output, "w", compression=ZIP_STORED, strict_timestamps=True) as archive:
            for name in sorted(files):
                info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = ZIP_STORED
                info.external_attr = 0o640 << 16
                info.create_system = 3
                archive.writestr(info, files[name])
        return output.getvalue()

    @staticmethod
    def _source_digest(run: BootstrapRunRecord) -> str:
        handoff = run.operational_handoff
        assert handoff is not None
        return RecoveryService._digest(
            {
                "run_id": run.run_id,
                "version": run.version,
                "release_id": run.identity.release_id,
                "configuration_digest": run.identity.configuration_digest,
                "checkpoints": [
                    (item.phase_id, item.state.value, item.safe_output_references)
                    for item in run.checkpoints
                ],
                "handoff_report_digest": handoff.evidence[0].sha256,
            }
        )

    @staticmethod
    def _json(payload: object) -> bytes:
        return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()

    @staticmethod
    def _digest(payload: object) -> str:
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    @staticmethod
    def _scan(payload: bytes) -> None:
        lowered = payload.lower()
        if any(marker in lowered for marker in PROHIBITED_MARKERS):
            raise RecoveryError("backup_redaction_failed")

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        idempotency_key: str,
        result_code: str,
        metadata: tuple[tuple[str, str], ...],
        permission_id: str,
        capability: str,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.backup.recovery",
                schema_version="1.0",
                producer="atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id=permission_id,
                resource_type="resource.backup.logical",
                scope_reference=f"{actor.organization_id}/{self._environment_id}/{self._site_id}/domain.recovery/resource.backup.logical/{capability}",
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=metadata,
            )
        )
