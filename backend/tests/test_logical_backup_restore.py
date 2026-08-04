from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from test_bootstrap_identity_handoff import NOW
from test_browser_sessions import BasicTestIdentityProvider, login, settings, subject
from test_support_bundles import completed_source

from atlas.api.app import create_app
from atlas.core.persistence.models import LogicalBackupModel, RestoreValidationModel
from atlas.modules.recovery.adapters.filesystem import FilesystemBackupArchiveStore
from atlas.modules.recovery.adapters.memory import InMemoryRecoveryRepository
from atlas.modules.recovery.adapters.postgres import PostgreSQLRecoveryRepository
from atlas.modules.recovery.application.ports import RecoveryError
from atlas.modules.recovery.application.service import CATALOG, RecoveryService

ALL_COMPONENTS = tuple(item[0] for item in CATALOG)


async def recovery_service(tmp_path: Path):  # type: ignore[no-untyped-def]
    sink, bootstrap_repository, run = await completed_source(tmp_path / "bootstrap")
    repository = InMemoryRecoveryRepository()
    store = FilesystemBackupArchiveStore(root=tmp_path / "backups", max_archive_bytes=1024 * 1024)
    service = RecoveryService(
        bootstrap_repository=bootstrap_repository,
        repository=repository,
        archive_store=store,
        audit_sink=sink,
        environment_id="environment.test",
        site_id="site.local",
        max_content_bytes=512 * 1024,
        max_archive_bytes=1024 * 1024,
        clock=lambda: NOW,
    )
    return sink, bootstrap_repository, run, repository, store, service


@pytest.mark.asyncio
async def test_preview_backup_and_isolated_restore_are_deterministic(tmp_path: Path) -> None:
    sink, _, run, _, _, service = await recovery_service(tmp_path)
    first = await service.preview(
        actor=subject(), source_run_id=run.run_id, component_ids=ALL_COMPONENTS
    )
    second = await service.preview(
        actor=subject(), source_run_id=run.run_id, component_ids=tuple(reversed(ALL_COMPONENTS))
    )
    assert first.preview_digest == second.preview_digest
    assert first.archive_sha256 == second.archive_sha256
    assert len(first.entries) == 7
    assert first.target_state.value == "empty"
    request = {
        "actor": subject(),
        "source_run_id": run.run_id,
        "source_run_version": run.version,
        "component_ids": ALL_COMPONENTS,
        "preview_digest": first.preview_digest,
        "archive_sha256": first.archive_sha256,
        "target_id": first.target_id,
        "expected_target_state": first.target_state,
        "justification": "Create reviewed local logical recovery evidence",
        "confirmed": True,
        "idempotency_key": "backup-create-0001",
        "correlation_id": "correlation.backup.create",
    }
    backup = await service.create_backup(**request)
    replay = await service.create_backup(**request)
    validation = await service.validate_restore(
        actor=subject(),
        backup_id=backup.backup_id,
        archive_sha256=backup.archive_sha256,
        confirmed_isolated=True,
        idempotency_key="restore-validation-0001",
        correlation_id="correlation.restore.validation",
    )
    assert replay.reused is True
    assert validation.state.value == "passed"
    assert validation.isolated_target is True
    assert validation.active_repository_write_performed is False
    assert validation.operational_recovery_performed is False
    assert len(validation.check_ids) == 6
    archives = tuple((tmp_path / "backups").rglob("*.zip"))
    assert len(archives) == 1
    with ZipFile(archives[0]) as archive:
        assert archive.namelist() == sorted(archive.namelist())
        manifest = json.loads(archive.read("00-backup-integrity-manifest.json"))
        assert len(manifest["entries"]) == 7
        assert all(value is False for value in manifest["safety"].values())
    assert [item.result_code for item in sink.records[-3:]] == [
        "logical_backup_create_authorized",
        "logical_backup_create_completed",
        "isolated_restore_validation_passed",
    ]


@pytest.mark.asyncio
async def test_backup_fails_closed_for_stale_source_and_changed_archive(tmp_path: Path) -> None:
    _, bootstrap_repository, run, _, _, service = await recovery_service(tmp_path)
    preview = await service.preview(
        actor=subject(), source_run_id=run.run_id, component_ids=ALL_COMPONENTS
    )
    bootstrap_repository._records[
        (run.identity.organization_id, run.identity.environment_id, run.identity.site_id)
    ] = replace(run, version=run.version + 1)
    with pytest.raises(RecoveryError, match="preview_stale"):
        await service.create_backup(
            actor=subject(),
            source_run_id=run.run_id,
            source_run_version=run.version,
            component_ids=ALL_COMPONENTS,
            preview_digest=preview.preview_digest,
            archive_sha256=preview.archive_sha256,
            target_id=preview.target_id,
            expected_target_state=preview.target_state,
            justification="Create reviewed local logical recovery evidence",
            confirmed=True,
            idempotency_key="backup-stale-0001",
            correlation_id="correlation.backup.stale",
        )

    _, _, clean_run, _, _, clean = await recovery_service(tmp_path / "changed")
    clean_preview = await clean.preview(
        actor=subject(), source_run_id=clean_run.run_id, component_ids=ALL_COMPONENTS
    )
    backup = await clean.create_backup(
        actor=subject(),
        source_run_id=clean_run.run_id,
        source_run_version=clean_run.version,
        component_ids=ALL_COMPONENTS,
        preview_digest=clean_preview.preview_digest,
        archive_sha256=clean_preview.archive_sha256,
        target_id=clean_preview.target_id,
        expected_target_state=clean_preview.target_state,
        justification="Create reviewed local logical recovery evidence",
        confirmed=True,
        idempotency_key="backup-changed-0001",
        correlation_id="correlation.backup.changed",
    )
    archive = next((tmp_path / "changed" / "backups").rglob("*.zip"))
    archive.write_bytes(archive.read_bytes() + b"changed")
    with pytest.raises(RecoveryError, match="archive_changed"):
        await clean.validate_restore(
            actor=subject(),
            backup_id=backup.backup_id,
            archive_sha256=backup.archive_sha256,
            confirmed_isolated=True,
            idempotency_key="restore-changed-0001",
            correlation_id="correlation.restore.changed",
        )


def test_postgres_recovery_mapping_preserves_metadata(tmp_path: Path) -> None:
    _, _, run, _, _, service = asyncio.run(recovery_service(tmp_path))
    preview = asyncio.run(
        service.preview(actor=subject(), source_run_id=run.run_id, component_ids=ALL_COMPONENTS)
    )
    backup = asyncio.run(
        service.create_backup(
            actor=subject(),
            source_run_id=run.run_id,
            source_run_version=run.version,
            component_ids=ALL_COMPONENTS,
            preview_digest=preview.preview_digest,
            archive_sha256=preview.archive_sha256,
            target_id=preview.target_id,
            expected_target_state=preview.target_state,
            justification="Create reviewed local logical recovery evidence",
            confirmed=True,
            idempotency_key="backup-map-0001",
            correlation_id="correlation.backup.map",
        )
    )
    validation = asyncio.run(
        service.validate_restore(
            actor=subject(),
            backup_id=backup.backup_id,
            archive_sha256=backup.archive_sha256,
            confirmed_isolated=True,
            idempotency_key="restore-map-0001",
            correlation_id="correlation.restore.map",
        )
    )
    restored_backup = PostgreSQLRecoveryRepository._backup_to_domain(
        LogicalBackupModel(
            backup_id=backup.backup_id,
            state=backup.state.value,
            actor_id=backup.actor_id,
            organization_id=backup.organization_id,
            environment_id=backup.environment_id,
            site_id=backup.site_id,
            source_run_id=backup.source_run_id,
            source_run_version=backup.source_run_version,
            preview_digest=backup.preview_digest,
            request_fingerprint=backup.request_fingerprint,
            idempotency_key=backup.idempotency_key,
            target_id=backup.target_id,
            archive_sha256=backup.archive_sha256,
            archive_size_bytes=backup.archive_size_bytes,
            archive_name=backup.archive_name,
            entry_count=backup.entry_count,
            created_at=backup.created_at,
            expires_at=backup.expires_at,
        )
    )
    restored_validation = PostgreSQLRecoveryRepository._validation_to_domain(
        RestoreValidationModel(
            validation_id=validation.validation_id,
            state=validation.state.value,
            backup_id=validation.backup_id,
            actor_id=validation.actor_id,
            request_fingerprint=validation.request_fingerprint,
            idempotency_key=validation.idempotency_key,
            archive_sha256=validation.archive_sha256,
            validation_digest=validation.validation_digest,
            check_ids=list(validation.check_ids),
            entry_count=validation.entry_count,
            validated_at=validation.validated_at,
        )
    )
    assert restored_backup.archive_sha256 == backup.archive_sha256
    assert restored_validation.validation_digest == validation.validation_digest


def test_recovery_api_requires_session_csrf_and_strict_payload(tmp_path: Path) -> None:
    sink, bootstrap_repository, run = asyncio.run(completed_source(tmp_path / "source"))
    service = RecoveryService(
        bootstrap_repository=bootstrap_repository,
        repository=InMemoryRecoveryRepository(),
        archive_store=FilesystemBackupArchiveStore(
            root=tmp_path / "api-backups", max_archive_bytes=1024 * 1024
        ),
        audit_sink=sink,
        environment_id="environment.test",
        site_id="site.local",
        max_content_bytes=512 * 1024,
        max_archive_bytes=1024 * 1024,
        clock=lambda: NOW,
    )
    preview_request = {
        "schema_version": "atlas.logical-backup-preview-request.v1",
        "source_run_id": run.run_id,
        "component_ids": list(ALL_COMPONENTS),
    }
    with TestClient(
        create_app(
            settings(logical_backup_root=tmp_path / "default-backups"),
            identity_provider=BasicTestIdentityProvider(),
            audit_sink=sink,
            recovery_service=service,
        )
    ) as client:
        denied = client.post("/api/v1/platform/backups/preview", json=preview_request)
        session = login(client)
        csrf = session.headers["X-CSRF-Token"]
        missing_csrf = client.post("/api/v1/platform/backups/preview", json=preview_request)
        malformed = client.post(
            "/api/v1/platform/backups/preview",
            headers={"X-CSRF-Token": csrf},
            json={**preview_request, "secret": "not-accepted"},
        )
        preview_response = client.post(
            "/api/v1/platform/backups/preview", headers={"X-CSRF-Token": csrf}, json=preview_request
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()["data"]
        backup_response = client.post(
            f"/api/v1/platform/backups/{run.run_id}",
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "backup-api-create-0001"},
            json={
                "schema_version": "atlas.logical-backup-create-request.v1",
                "source_run_version": preview["source_run_version"],
                "component_ids": preview["component_ids"],
                "preview_digest": preview["preview_digest"],
                "archive_sha256": preview["archive_sha256"],
                "target_id": preview["target_id"],
                "expected_target_state": preview["target_state"],
                "justification": "Create reviewed local logical recovery evidence",
                "confirmed": True,
            },
        )
        backup = backup_response.json()["data"]
        validation_response = client.post(
            f"/api/v1/platform/backups/{backup['backup_id']}/restore-validations",
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "restore-api-validate-0001"},
            json={
                "schema_version": "atlas.isolated-restore-validation-request.v1",
                "archive_sha256": backup["archive_sha256"],
                "confirmed_isolated": True,
            },
        )
    assert denied.status_code == 401
    assert missing_csrf.status_code == 403
    assert malformed.status_code == 422
    assert preview_response.status_code == 200
    assert backup_response.status_code == 200
    assert validation_response.status_code == 200
    assert validation_response.json()["data"]["operational_recovery_performed"] is False
