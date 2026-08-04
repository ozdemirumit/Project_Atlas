from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from test_bootstrap_identity_handoff import NOW
from test_bootstrap_operational_handoff import prepared_handoff
from test_browser_sessions import BasicTestIdentityProvider, login, settings, subject

from atlas.api.app import create_app
from atlas.core.persistence.models import SupportBundleExportModel
from atlas.modules.platform.application.bootstrap_operational_handoff import (
    BootstrapOperationalHandoffService,
)
from atlas.modules.support.adapters.filesystem import FilesystemSupportBundlePublisher
from atlas.modules.support.adapters.memory import InMemorySupportBundleExportRepository
from atlas.modules.support.adapters.postgres import PostgreSQLSupportBundleExportRepository
from atlas.modules.support.application.ports import SupportBundleError
from atlas.modules.support.application.service import CATALOG, SupportBundleService
from atlas.modules.support.domain.support_bundle import SupportTargetState

ALL_COMPONENTS = tuple(item[0] for item in CATALOG)


async def completed_source(tmp_path: Path):  # type: ignore[no-untyped-def]
    sink, repository, seeded, target, plan_service, inputs = await prepared_handoff(
        tmp_path / "bootstrap"
    )
    plan = await plan_service.prepare(**inputs)
    handoff = BootstrapOperationalHandoffService(
        repository=repository,
        plan_service=plan_service,
        target=target,
        audit_sink=sink,
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: NOW,
    )
    result = await handoff.execute(
        actor=subject(),
        lease_holder_id="session.handoff.primary",
        run_id=seeded.run_id,
        organization_id=seeded.identity.organization_id,
        environment_id=seeded.identity.environment_id,
        site_id=seeded.identity.site_id,
        expected_version=seeded.version,
        plan_digest=seeded.identity.plan_digest,
        resume_key=seeded.identity.resume_key,
        release_id=seeded.identity.release_id,
        profile=seeded.identity.profile,
        configuration_digest=plan.configuration_digest,
        trust_plan_digest=plan.trust_plan_digest,
        data_plan_digest=plan.data_plan_digest,
        service_plan_digest=plan.service_plan_digest,
        identity_plan_digest=plan.identity_plan_digest,
        integration_plan_digest=plan.integration_plan_digest,
        verification_plan_digest=plan.verification_plan_digest,
        verification_report_digest=plan.verification_report_digest,
        source_evidence_digest=plan.source_evidence_digest,
        handoff_schema_version=plan.schema_version,
        suite_version=plan.suite_version,
        handoff_plan_digest=plan.handoff_plan_digest,
        target_id=plan.target_id,
        expected_target_state=plan.target_state,
        justification="Publish reviewed developer and lab handoff evidence",
        idempotency_key="support-source-handoff-0001",
        correlation_id="correlation.support.source",
    )
    return sink, repository, result.record


async def support_service(tmp_path: Path):  # type: ignore[no-untyped-def]
    sink, bootstrap_repository, run = await completed_source(tmp_path)
    export_repository = InMemorySupportBundleExportRepository()
    publisher = FilesystemSupportBundlePublisher(
        root=tmp_path / "support", max_archive_bytes=1024 * 1024
    )
    service = SupportBundleService(
        bootstrap_repository=bootstrap_repository,
        export_repository=export_repository,
        publisher=publisher,
        audit_sink=sink,
        environment_id="environment.test",
        site_id="site.local",
        max_content_bytes=512 * 1024,
        clock=lambda: NOW,
    )
    return sink, bootstrap_repository, run, export_repository, publisher, service


@pytest.mark.asyncio
async def test_preview_is_deterministic_bounded_and_local_only(tmp_path: Path) -> None:
    _, _, run, _, _, service = await support_service(tmp_path)
    first = await service.preview(
        actor=subject(),
        source_run_id=run.run_id,
        component_ids=ALL_COMPONENTS,
        lookback_hours=24,
    )
    second = await service.preview(
        actor=subject(),
        source_run_id=run.run_id,
        component_ids=tuple(reversed(ALL_COMPONENTS)),
        lookback_hours=24,
    )
    assert first.preview_digest == second.preview_digest
    assert first.archive_sha256 == second.archive_sha256
    assert first.archive_size_bytes == second.archive_size_bytes
    assert first.target_state is SupportTargetState.EMPTY
    assert first.included_count == 5
    assert first.excluded_count == 0
    assert first.content_bytes < first.max_content_bytes
    assert first.redaction_check_count == 54
    assert first.exportable is True
    assert first.external_transfer_performed is False
    assert first.arbitrary_file_collection_performed is False
    assert first.network_request_performed is False
    assert first.model_inference_performed is False
    assert first.infrastructure_mutation_performed is False


@pytest.mark.asyncio
async def test_export_is_atomic_integrity_manifested_and_exactly_replayable(
    tmp_path: Path,
) -> None:
    sink, _, run, _, _, service = await support_service(tmp_path)
    preview = await service.preview(
        actor=subject(), source_run_id=run.run_id, component_ids=ALL_COMPONENTS, lookback_hours=24
    )
    request = {
        "actor": subject(),
        "source_run_id": run.run_id,
        "source_run_version": run.version,
        "component_ids": ALL_COMPONENTS,
        "lookback_hours": 24,
        "preview_digest": preview.preview_digest,
        "archive_sha256": preview.archive_sha256,
        "target_id": preview.target_id,
        "expected_target_state": preview.target_state,
        "justification": "Create a reviewed local diagnostic package for support triage",
        "confirmed": True,
        "idempotency_key": "support-export-0001",
        "correlation_id": "correlation.support.export",
    }
    first = await service.export(**request)
    replay = await service.export(**request)
    assert first.state.value == "completed"
    assert first.archive_sha256 == preview.archive_sha256
    assert replay.reused is True
    with pytest.raises(SupportBundleError, match="idempotency_conflict"):
        await service.export(
            **{**request, "justification": "Create a changed local package for another purpose"}
        )
    restored = PostgreSQLSupportBundleExportRepository._to_domain(
        SupportBundleExportModel(
            export_id=first.export_id,
            state=first.state.value,
            actor_id=first.actor_id,
            organization_id=first.organization_id,
            environment_id=first.environment_id,
            site_id=first.site_id,
            source_run_id=first.source_run_id,
            source_run_version=first.source_run_version,
            preview_digest=first.preview_digest,
            request_fingerprint=first.request_fingerprint,
            idempotency_key=first.idempotency_key,
            archive_sha256=first.archive_sha256,
            archive_size_bytes=first.archive_size_bytes,
            archive_name=first.archive_name,
            included_count=first.included_count,
            excluded_count=first.excluded_count,
            expires_at=first.expires_at,
            created_at=first.created_at,
        )
    )
    assert restored.archive_sha256 == first.archive_sha256
    assert restored.preview_digest == first.preview_digest
    archives = tuple((tmp_path / "support").rglob("*.zip"))
    assert len(archives) == 1
    with ZipFile(archives[0]) as archive:
        assert archive.namelist() == sorted(archive.namelist())
        assert archive.namelist()[0] == "00-integrity-manifest.json"
        manifest = json.loads(archive.read("00-integrity-manifest.json"))
        assert manifest["preview_digest"] == preview.preview_digest
        assert len(manifest["entries"]) == 5
        assert all(value is False for value in manifest["safety"].values())
        combined = b"".join(archive.read(name).lower() for name in archive.namelist())
    for marker in (
        b'"password"',
        b'"authorization"',
        b"bearer ",
        b"private key",
        b"reader token",
        b'"prompt"',
        b"://",
    ):
        assert marker not in combined
    assert [item.result_code for item in sink.records[-2:]] == [
        "support_bundle_export_authorized",
        "support_bundle_export_completed",
    ]


@pytest.mark.asyncio
async def test_required_audit_failure_blocks_archive_publication(tmp_path: Path) -> None:
    _, bootstrap_repository, run = await completed_source(tmp_path)

    class FailingAuditSink:
        async def record(self, event) -> None:  # type: ignore[no-untyped-def]
            raise RuntimeError("audit unavailable")

    service = SupportBundleService(
        bootstrap_repository=bootstrap_repository,
        export_repository=InMemorySupportBundleExportRepository(),
        publisher=FilesystemSupportBundlePublisher(
            root=tmp_path / "blocked", max_archive_bytes=1024 * 1024
        ),
        audit_sink=FailingAuditSink(),
        environment_id="environment.test",
        site_id="site.local",
        max_content_bytes=512 * 1024,
        clock=lambda: NOW,
    )
    preview = await service.preview(
        actor=subject(), source_run_id=run.run_id, component_ids=ALL_COMPONENTS, lookback_hours=24
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await service.export(
            actor=subject(),
            source_run_id=run.run_id,
            source_run_version=run.version,
            component_ids=ALL_COMPONENTS,
            lookback_hours=24,
            preview_digest=preview.preview_digest,
            archive_sha256=preview.archive_sha256,
            target_id=preview.target_id,
            expected_target_state=preview.target_state,
            justification="Create a reviewed local diagnostic package for support triage",
            confirmed=True,
            idempotency_key="support-export-audit-0001",
            correlation_id="correlation.support.audit",
        )
    assert tuple((tmp_path / "blocked").rglob("*.zip")) == ()


@pytest.mark.asyncio
async def test_preview_and_export_fail_closed_for_unsafe_or_changed_input(tmp_path: Path) -> None:
    _, bootstrap_repository, run, _, _, service = await support_service(tmp_path)
    with pytest.raises(SupportBundleError, match="required_component_missing"):
        await service.preview(
            actor=subject(),
            source_run_id=run.run_id,
            component_ids=("support.release-manifest", "support.service-health"),
            lookback_hours=24,
        )
    preview = await service.preview(
        actor=subject(), source_run_id=run.run_id, component_ids=ALL_COMPONENTS, lookback_hours=24
    )
    bootstrap_repository._records[
        (run.identity.organization_id, run.identity.environment_id, run.identity.site_id)
    ] = replace(run, version=run.version + 1)
    with pytest.raises(SupportBundleError, match="preview_stale"):
        await service.export(
            actor=subject(),
            source_run_id=run.run_id,
            source_run_version=run.version,
            component_ids=ALL_COMPONENTS,
            lookback_hours=24,
            preview_digest=preview.preview_digest,
            archive_sha256=preview.archive_sha256,
            target_id=preview.target_id,
            expected_target_state=preview.target_state,
            justification="Create a reviewed local diagnostic package for support triage",
            confirmed=True,
            idempotency_key="support-export-stale-0001",
            correlation_id="correlation.support.stale",
        )


@pytest.mark.asyncio
async def test_redaction_and_target_conflict_fail_closed(tmp_path: Path) -> None:
    _, _, run, _, _, service = await support_service(tmp_path)
    original = service._entry_content

    def unsafe_content(*args, **kwargs):  # type: ignore[no-untyped-def]
        values = original(*args, **kwargs)
        values["support.sanitized-diagnostics"] = b'{"password":"unsafe"}'
        return values

    service._entry_content = unsafe_content
    with pytest.raises(SupportBundleError, match="redaction_failed"):
        await service.preview(
            actor=subject(),
            source_run_id=run.run_id,
            component_ids=ALL_COMPONENTS,
            lookback_hours=24,
        )

    _, _, run, _, _, clean = await support_service(tmp_path / "conflict")
    preview = await clean.preview(
        actor=subject(), source_run_id=run.run_id, component_ids=ALL_COMPONENTS, lookback_hours=24
    )
    target = tmp_path / "conflict" / "support" / "exports" / f"{preview.target_id}.zip"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"unknown")
    with pytest.raises(SupportBundleError, match="target_conflict"):
        await clean.preview(
            actor=subject(),
            source_run_id=run.run_id,
            component_ids=ALL_COMPONENTS,
            lookback_hours=24,
        )


def test_support_bundle_api_requires_session_csrf_and_strict_schema(tmp_path: Path) -> None:
    sink, bootstrap_repository, run = asyncio.run(completed_source(tmp_path))
    service = SupportBundleService(
        bootstrap_repository=bootstrap_repository,
        export_repository=InMemorySupportBundleExportRepository(),
        publisher=FilesystemSupportBundlePublisher(
            root=tmp_path / "api-support", max_archive_bytes=1024 * 1024
        ),
        audit_sink=sink,
        environment_id="environment.test",
        site_id="site.local",
        max_content_bytes=512 * 1024,
        clock=lambda: NOW,
    )
    preview_request = {
        "schema_version": "atlas.support-bundle-preview-request.v1",
        "source_run_id": run.run_id,
        "component_ids": list(ALL_COMPONENTS),
        "lookback_hours": 24,
    }
    with TestClient(
        create_app(
            settings(support_bundle_root=tmp_path / "default-support"),
            identity_provider=BasicTestIdentityProvider(),
            audit_sink=sink,
            support_bundle_service=service,
        )
    ) as client:
        denied = client.post("/api/v1/platform/support-bundles/preview", json=preview_request)
        session = login(client)
        csrf = session.headers["X-CSRF-Token"]
        missing_csrf = client.post("/api/v1/platform/support-bundles/preview", json=preview_request)
        malformed = client.post(
            "/api/v1/platform/support-bundles/preview",
            headers={"X-CSRF-Token": csrf},
            json={**preview_request, "reader_token": "must-not-be-accepted"},
        )
        preview_response = client.post(
            "/api/v1/platform/support-bundles/preview",
            headers={"X-CSRF-Token": csrf},
            json=preview_request,
        )
        preview = preview_response.json()["data"]
        export_response = client.post(
            f"/api/v1/platform/support-bundles/{run.run_id}/exports",
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "support-api-export-0001",
            },
            json={
                "schema_version": "atlas.support-bundle-export-request.v1",
                "source_run_version": preview["source_run_version"],
                "component_ids": preview["component_ids"],
                "lookback_hours": preview["lookback_hours"],
                "preview_digest": preview["preview_digest"],
                "archive_sha256": preview["archive_sha256"],
                "target_id": preview["target_id"],
                "expected_target_state": preview["target_state"],
                "justification": "Create a reviewed local package for support triage",
                "confirmed": True,
            },
        )
    assert denied.status_code == 401
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["code"] == "csrf_validation_failed"
    assert malformed.status_code == 422
    assert preview_response.status_code == 200
    assert preview["included_count"] == 5
    assert preview["external_transfer_performed"] is False
    assert export_response.status_code == 200
    assert export_response.json()["data"]["state"] == "completed"
    assert export_response.json()["data"]["external_transfer_performed"] is False
