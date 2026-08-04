from __future__ import annotations

import io
import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4
from zipfile import ZIP_STORED, ZipFile, ZipInfo

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.platform.application.bootstrap_state_ports import BootstrapStateRepository
from atlas.modules.platform.domain.bootstrap_state import BootstrapRunRecord, BootstrapRunState
from atlas.modules.support.application.ports import (
    SupportBundleError,
    SupportBundleExportRepository,
    SupportBundlePublisher,
)
from atlas.modules.support.domain.support_bundle import (
    SupportBundleEntry,
    SupportBundleExport,
    SupportBundlePreview,
    SupportEntryDisposition,
    SupportExportState,
    SupportTargetState,
)

SCHEMA_VERSION = "atlas.support-bundle-preview.v1"
CATALOG_VERSION = "atlas.synthetic-support-catalog.v1"
MANIFEST_FILE = "00-integrity-manifest.json"
CATALOG: tuple[tuple[str, str, bool], ...] = (
    ("support.release-manifest", "10-release-manifest.json", True),
    ("support.bootstrap-summary", "20-bootstrap-summary.json", True),
    ("support.service-health", "30-service-health.json", False),
    ("support.configuration-schema", "40-configuration-schema.json", False),
    ("support.sanitized-diagnostics", "50-sanitized-diagnostics.json", False),
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


class SupportBundleService:
    def __init__(
        self,
        *,
        bootstrap_repository: BootstrapStateRepository,
        export_repository: SupportBundleExportRepository,
        publisher: SupportBundlePublisher,
        audit_sink: AuditSink,
        environment_id: str,
        site_id: str,
        max_content_bytes: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._bootstrap_repository = bootstrap_repository
        self._export_repository = export_repository
        self._publisher = publisher
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._site_id = site_id
        self._max_content_bytes = max_content_bytes
        self._clock = clock or (lambda: datetime.now(UTC))

    async def close(self) -> None:
        await self._export_repository.close()

    async def preview(
        self,
        *,
        actor: AuthenticatedSubject,
        source_run_id: str,
        component_ids: tuple[str, ...],
        lookback_hours: int,
    ) -> SupportBundlePreview:
        run = await self._source_run(actor, source_run_id)
        normalized = tuple(sorted(set(component_ids)))
        catalog_ids = {item[0] for item in CATALOG}
        if not normalized or any(item not in catalog_ids for item in normalized):
            raise SupportBundleError("support_bundle_component_invalid")
        required = {item[0] for item in CATALOG if item[2]}
        if not required.issubset(normalized):
            raise SupportBundleError("support_bundle_required_component_missing")
        if not 1 <= lookback_hours <= 168:
            raise SupportBundleError("support_bundle_window_invalid")

        content = self._entry_content(run, lookback_hours)
        entries: list[SupportBundleEntry] = []
        included_content: dict[str, bytes] = {}
        for entry_id, file_name, mandatory in CATALOG:
            if entry_id not in normalized:
                entries.append(
                    SupportBundleEntry(
                        entry_id=entry_id,
                        file_name=file_name,
                        classification="internal",
                        mandatory=mandatory,
                        disposition=SupportEntryDisposition.EXCLUDED,
                        reason_code="not_selected",
                        size_bytes=0,
                        sha256=None,
                    )
                )
                continue
            payload = content[entry_id]
            self._scan(payload)
            included_content[file_name] = payload
            entries.append(
                SupportBundleEntry(
                    entry_id=entry_id,
                    file_name=file_name,
                    classification="internal",
                    mandatory=mandatory,
                    disposition=SupportEntryDisposition.INCLUDED,
                    reason_code="selected_and_sanitized",
                    size_bytes=len(payload),
                    sha256=sha256(payload).hexdigest(),
                )
            )
        total = sum(item.size_bytes for item in entries)
        if total > self._max_content_bytes:
            raise SupportBundleError("support_bundle_content_budget_exceeded")
        handoff = run.operational_handoff
        assert handoff is not None and handoff.completed_at is not None
        handoff_digest = handoff.evidence[0].sha256
        source_digest = self._source_digest(run)
        preview_digest = self._digest(
            {
                "schema_version": SCHEMA_VERSION,
                "catalog_version": CATALOG_VERSION,
                "source_run_id": run.run_id,
                "source_run_version": run.version,
                "release_id": run.identity.release_id,
                "handoff_report_digest": handoff_digest,
                "source_evidence_digest": source_digest,
                "component_ids": normalized,
                "lookback_hours": lookback_hours,
                "entries": [
                    {
                        "entry_id": item.entry_id,
                        "disposition": item.disposition.value,
                        "sha256": item.sha256,
                        "size_bytes": item.size_bytes,
                    }
                    for item in entries
                ],
            }
        )
        manifest = self._manifest(
            run=run,
            preview_digest=preview_digest,
            source_evidence_digest=source_digest,
            handoff_report_digest=handoff_digest,
            entries=tuple(entries),
        )
        self._scan(manifest)
        archive = self._archive({MANIFEST_FILE: manifest, **included_content})
        target_id = f"target.support-bundle.{preview_digest[:24]}"
        target_state = SupportTargetState(
            await self._publisher.inspect(target_id=target_id, expected=archive)
        )
        now = self._clock()
        included_count = sum(
            item.disposition is SupportEntryDisposition.INCLUDED for item in entries
        )
        return SupportBundlePreview(
            preview_id=f"support-preview.{preview_digest[:24]}",
            schema_version=SCHEMA_VERSION,
            catalog_version=CATALOG_VERSION,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
            source_run_id=run.run_id,
            source_run_version=run.version,
            release_id=run.identity.release_id,
            handoff_report_digest=handoff_digest,
            source_evidence_digest=source_digest,
            component_ids=normalized,
            lookback_hours=lookback_hours,
            window_start=handoff.completed_at - timedelta(hours=lookback_hours),
            window_end=handoff.completed_at,
            entries=tuple(entries),
            included_count=included_count,
            excluded_count=len(entries) - included_count,
            content_bytes=total,
            max_content_bytes=self._max_content_bytes,
            redaction_check_count=len(PROHIBITED_MARKERS) * (included_count + 1),
            preview_digest=preview_digest,
            target_id=target_id,
            target_state=target_state,
            archive_sha256=sha256(archive).hexdigest(),
            archive_size_bytes=len(archive),
            generated_at=now,
            expires_at=now + timedelta(hours=24),
            exportable=True,
        )

    async def export(
        self,
        *,
        actor: AuthenticatedSubject,
        source_run_id: str,
        source_run_version: int,
        component_ids: tuple[str, ...],
        lookback_hours: int,
        preview_digest: str,
        archive_sha256: str,
        target_id: str,
        expected_target_state: SupportTargetState,
        justification: str,
        confirmed: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> SupportBundleExport:
        if not confirmed or not 12 <= len(justification.strip()) <= 500:
            raise SupportBundleError("support_bundle_confirmation_required")
        fingerprint = self._digest(
            {
                "source_run_id": source_run_id,
                "source_run_version": source_run_version,
                "component_ids": tuple(sorted(set(component_ids))),
                "lookback_hours": lookback_hours,
                "preview_digest": preview_digest,
                "archive_sha256": archive_sha256,
                "target_id": target_id,
                "expected_target_state": expected_target_state.value,
                "justification": justification.strip(),
                "confirmed": confirmed,
            }
        )
        prior = await self._export_repository.get(
            actor_id=actor.subject_id, idempotency_key=idempotency_key
        )
        if prior is not None:
            if prior.request_fingerprint != fingerprint:
                raise SupportBundleError("support_bundle_idempotency_conflict")
            return replace(prior, reused=True)

        preview = await self.preview(
            actor=actor,
            source_run_id=source_run_id,
            component_ids=component_ids,
            lookback_hours=lookback_hours,
        )
        if (
            preview.source_run_version != source_run_version
            or preview.preview_digest != preview_digest
            or preview.archive_sha256 != archive_sha256
            or preview.target_id != target_id
            or preview.target_state is not expected_target_state
        ):
            raise SupportBundleError("support_bundle_preview_stale")
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            result_code="support_bundle_export_authorized",
            metadata=(("preview_digest", preview_digest),),
        )
        run = await self._source_run(actor, source_run_id)
        archive = self._render_archive(run, preview)
        export_key = f"{actor.subject_id}:{idempotency_key}:{fingerprint}"
        export_id = f"support-export.{sha256(export_key.encode()).hexdigest()[:24]}"
        digest, size, archive_name, reused = await self._publisher.publish(
            export_id=export_id,
            target_id=target_id,
            expected=archive,
        )
        if digest != preview.archive_sha256 or size != preview.archive_size_bytes:
            raise SupportBundleError("support_bundle_archive_changed")
        now = self._clock()
        record = SupportBundleExport(
            export_id=export_id,
            state=SupportExportState.COMPLETED,
            actor_id=actor.subject_id,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
            source_run_id=source_run_id,
            source_run_version=source_run_version,
            preview_digest=preview_digest,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            archive_sha256=digest,
            archive_size_bytes=size,
            archive_name=archive_name,
            included_count=preview.included_count,
            excluded_count=preview.excluded_count,
            created_at=now,
            expires_at=now + timedelta(days=7),
            reused=reused,
        )
        if not await self._export_repository.add(record):
            raced = await self._export_repository.get(
                actor_id=actor.subject_id, idempotency_key=idempotency_key
            )
            if raced is None or raced.request_fingerprint != fingerprint:
                raise SupportBundleError("support_bundle_idempotency_conflict")
            return replace(raced, reused=True)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            result_code="support_bundle_export_completed",
            metadata=(("export_id", export_id), ("archive_sha256", digest)),
        )
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
            or run.operational_handoff.state.value != "completed"
            or len(run.operational_handoff.evidence) != 1
        ):
            raise SupportBundleError("support_bundle_source_unavailable")
        return run

    def _entry_content(self, run: BootstrapRunRecord, lookback_hours: int) -> dict[str, bytes]:
        handoff = run.operational_handoff
        assert handoff is not None
        return {
            "support.release-manifest": self._json(
                {
                    "schema_version": "atlas.support-release-manifest.v1",
                    "release_id": run.identity.release_id,
                    "profile": run.identity.profile.value,
                    "plan_digest": run.identity.plan_digest,
                    "configuration_digest": run.identity.configuration_digest,
                }
            ),
            "support.bootstrap-summary": self._json(
                {
                    "schema_version": "atlas.support-bootstrap-summary.v1",
                    "run_id": run.run_id,
                    "run_version": run.version,
                    "state": run.state.value,
                    "completed_phase_ids": [item.phase_id for item in run.checkpoints],
                    "verification": {
                        "passed": handoff.passed_count,
                        "failed": 0,
                        "not_applicable": handoff.not_applicable_count,
                    },
                    "readiness_class": handoff.readiness_class.value,
                    "production_ready": False,
                }
            ),
            "support.service-health": self._json(
                {
                    "schema_version": "atlas.support-service-health.v1",
                    "source": "governed_operational_handoff",
                    "bootstrap_state": run.state.value,
                    "completed_phase_count": len(run.checkpoints),
                    "mandatory_check_count": handoff.mandatory_pass_count,
                    "external_probe_performed": False,
                }
            ),
            "support.configuration-schema": self._json(
                {
                    "schema_version": "atlas.support-configuration-schema.v1",
                    "configuration_schema": "atlas.effective-configuration.v1",
                    "secret_values_included": False,
                    "private_endpoints_included": False,
                    "supported_profile": run.identity.profile.value,
                }
            ),
            "support.sanitized-diagnostics": self._json(
                {
                    "schema_version": "atlas.support-sanitized-diagnostics.v1",
                    "lookback_hours": lookback_hours,
                    "checkpoint_states": [
                        {"phase_id": item.phase_id, "state": item.state.value}
                        for item in run.checkpoints
                    ],
                    "raw_logs_included": False,
                    "arbitrary_files_collected": False,
                    "external_transfer_performed": False,
                }
            ),
        }

    def _render_archive(self, run: BootstrapRunRecord, preview: SupportBundlePreview) -> bytes:
        all_content = self._entry_content(run, preview.lookback_hours)
        selected = {
            file_name: all_content[entry_id]
            for entry_id, file_name, _mandatory in CATALOG
            if entry_id in preview.component_ids
        }
        manifest = self._manifest(
            run=run,
            preview_digest=preview.preview_digest,
            source_evidence_digest=preview.source_evidence_digest,
            handoff_report_digest=preview.handoff_report_digest,
            entries=preview.entries,
        )
        return self._archive({MANIFEST_FILE: manifest, **selected})

    @classmethod
    def _manifest(
        cls,
        *,
        run: BootstrapRunRecord,
        preview_digest: str,
        source_evidence_digest: str,
        handoff_report_digest: str,
        entries: tuple[SupportBundleEntry, ...],
    ) -> bytes:
        return cls._json(
            {
                "schema_version": "atlas.support-bundle-integrity-manifest.v1",
                "catalog_version": CATALOG_VERSION,
                "preview_digest": preview_digest,
                "source_run_id": run.run_id,
                "source_run_version": run.version,
                "source_evidence_digest": source_evidence_digest,
                "handoff_report_digest": handoff_report_digest,
                "entries": [
                    {
                        "entry_id": item.entry_id,
                        "file_name": item.file_name,
                        "classification": item.classification,
                        "mandatory": item.mandatory,
                        "disposition": item.disposition.value,
                        "reason_code": item.reason_code,
                        "size_bytes": item.size_bytes,
                        "sha256": item.sha256,
                    }
                    for item in entries
                ],
                "safety": {
                    "arbitrary_file_collection_performed": False,
                    "external_transfer_performed": False,
                    "network_request_performed": False,
                    "model_inference_performed": False,
                    "infrastructure_mutation_performed": False,
                },
            }
        )

    @staticmethod
    def _archive(files: dict[str, bytes]) -> bytes:
        output = io.BytesIO()
        with ZipFile(output, mode="w", compression=ZIP_STORED, strict_timestamps=True) as archive:
            for file_name in sorted(files):
                info = ZipInfo(file_name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = ZIP_STORED
                info.external_attr = 0o640 << 16
                info.create_system = 3
                archive.writestr(info, files[file_name])
        return output.getvalue()

    @staticmethod
    def _source_digest(run: BootstrapRunRecord) -> str:
        handoff = run.operational_handoff
        assert handoff is not None
        return SupportBundleService._digest(
            {
                "run_id": run.run_id,
                "version": run.version,
                "release_id": run.identity.release_id,
                "configuration_digest": run.identity.configuration_digest,
                "checkpoints": [
                    {
                        "phase_id": item.phase_id,
                        "state": item.state.value,
                        "outputs": item.safe_output_references,
                    }
                    for item in run.checkpoints
                ],
                "handoff_plan_digest": handoff.handoff_plan_digest,
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
            raise SupportBundleError("support_bundle_redaction_failed")

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        idempotency_key: str,
        result_code: str,
        metadata: tuple[tuple[str, str], ...],
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.support.bundle.export",
                schema_version="1.0",
                producer="atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id="support.bundle.export",
                resource_type="resource.support.bundle",
                scope_reference=(
                    f"{actor.organization_id}/{self._environment_id}/{self._site_id}/domain.support/resource.support.bundle/C2"
                ),
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=metadata,
            )
        )
