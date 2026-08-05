from __future__ import annotations

import asyncio
import io
import json
import stat
import zipfile
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import PurePosixPath
from typing import Any
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.connectors.application.acquisition_ports import (
    AcquiredPackagePublisher,
    CandidateArchiveSource,
    CandidateHandoffSource,
    PackageAcquisitionError,
    PackageAcquisitionRepository,
)
from atlas.modules.connectors.domain.acquisition import (
    AcquiredCapabilityEvidence,
    ConnectorPackageAcquisition,
    PackageAcquisitionSource,
    PackageAcquisitionState,
    PackageSignatureState,
    PublisherAttestationState,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.mcp_builder.application.ports import McpBuilderArtifactError
from atlas.modules.mcp_builder.domain.candidate_handoff import (
    CandidateHandoffState,
    CandidateSignatureState,
    McpBuilderCandidateHandoff,
)

PACKAGE_ACQUIRE_PERMISSION = "connectors.packages.acquire"
PACKAGE_ACQUISITION_READ_PERMISSION = "connectors.package-acquisitions.read"
ACQUISITION_SCHEMA = "atlas.connector-package-acquisition.v1"
ACQUISITION_PROFILE = "atlas.connector-acquisition.builder-handoff.v1"
SUPPORTED_HANDOFF_PROFILE = "atlas.candidate-handoff.python312.v1"
SUPPORTED_ARCHIVE_CONTRACT = "mcp-builder-candidate-zip.v1"
PUBLISHER_IDENTITY = "unattested.generated"
ACQUISITION_LIMITATIONS = (
    "Acquisition preserves exact Builder package bytes in connector quarantine only.",
    "Signing, publisher attestation, registry validation, approval, installation, "
    "enablement, and runtime trust remain required.",
    "No dependency, vulnerability, malware, secret, license, schema, static, contract, "
    "runner, or target validation was performed by acquisition.",
)


class PackageAcquisitionService:
    def __init__(
        self,
        *,
        repository: PackageAcquisitionRepository,
        handoff_source: CandidateHandoffSource,
        archive_source: CandidateArchiveSource,
        publisher: AcquiredPackagePublisher,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._handoff_source = handoff_source
        self._archive_source = archive_source
        self._publisher = publisher
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_handoff_id: str,
        source_handoff_digest: str,
        package_digest: str,
        acquisition_profile: str,
        acknowledged_unsigned_unattested_quarantine: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorPackageAcquisition:
        self._require_enterprise_human(actor)
        if not acknowledged_unsigned_unattested_quarantine:
            raise PackageAcquisitionError("package_acquisition_acknowledgement_required")
        if acquisition_profile != ACQUISITION_PROFILE:
            raise PackageAcquisitionError("package_acquisition_profile_unsupported")
        if not 8 <= len(idempotency_key) <= 128:
            raise PackageAcquisitionError("package_acquisition_idempotency_key_invalid")

        request_fingerprint = self._digest(
            {
                "source_handoff_id": source_handoff_id,
                "source_handoff_digest": source_handoff_digest,
                "package_digest": package_digest,
                "acquisition_profile": acquisition_profile,
                "acknowledged_unsigned_unattested_quarantine": True,
                "idempotency_key": idempotency_key,
            }
        )
        prior = await self._repository.get_by_create_key(
            acquired_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if prior is not None:
            self._verify_acquisition(prior)
            self._require_scope(actor, prior.organization_id, prior.environment_id)
            if prior.request_fingerprint != request_fingerprint:
                raise PackageAcquisitionError("package_acquisition_idempotency_conflict")
            return replace(prior, reused=True)

        handoff = await self._handoff_source.get_by_id(handoff_id=source_handoff_id)
        if handoff is None:
            raise PackageAcquisitionError("package_acquisition_source_not_found")
        self._require_scope(actor, handoff.organization_id, handoff.environment_id)
        self._verify_handoff(handoff)
        if actor.subject_id in {
            handoff.custodied_by,
            handoff.domain_reviewed_by,
            handoff.security_reviewed_by,
            handoff.lab_operated_by,
        }:
            raise PackageAcquisitionError("package_acquisition_separation_of_duties_required")
        if (
            handoff.handoff_id != source_handoff_id
            or handoff.canonical_digest != source_handoff_digest
            or handoff.package_digest != package_digest
        ):
            raise PackageAcquisitionError("package_acquisition_source_mismatch")
        if (
            handoff.handoff_profile != SUPPORTED_HANDOFF_PROFILE
            or handoff.archive_contract_version != SUPPORTED_ARCHIVE_CONTRACT
            or handoff.state is not CandidateHandoffState.CANDIDATE_QUARANTINED
            or handoff.signature_state is not CandidateSignatureState.UNSIGNED
        ):
            raise PackageAcquisitionError("package_acquisition_source_unsupported")

        try:
            content = await self._archive_source.read(
                package_digest=handoff.package_digest,
                size_bytes=handoff.package_size_bytes,
            )
        except McpBuilderArtifactError as error:
            raise PackageAcquisitionError("package_acquisition_source_unavailable") from error
        self._verify_source_archive(handoff, content)

        capabilities = tuple(
            AcquiredCapabilityEvidence(
                capability_id=item.candidate_id,
                capability_class=item.capability_class,
                required_permission=item.required_permission,
                supported_product_versions=item.supported_product_versions,
            )
            for item in handoff.capabilities
        )
        payload: dict[str, Any] = {
            "state": PackageAcquisitionState.QUARANTINED.value,
            "source_type": PackageAcquisitionSource.MCP_BUILDER_HANDOFF.value,
            "source_handoff_id": handoff.handoff_id,
            "source_handoff_digest": handoff.canonical_digest,
            "source_project_id": handoff.project_id,
            "source_custodied_by": handoff.custodied_by,
            "source_domain_reviewed_by": handoff.domain_reviewed_by,
            "source_security_reviewed_by": handoff.security_reviewed_by,
            "source_lab_operated_by": handoff.lab_operated_by,
            "organization_id": handoff.organization_id,
            "environment_id": handoff.environment_id,
            "acquired_by": actor.subject_id,
            "acquisition_profile": acquisition_profile,
            "archive_contract_version": handoff.archive_contract_version,
            "package_filename": handoff.package_filename,
            "package_digest": handoff.package_digest,
            "package_size_bytes": handoff.package_size_bytes,
            "publisher_identity": PUBLISHER_IDENTITY,
            "signature_state": PackageSignatureState.UNSIGNED.value,
            "attestation_state": PublisherAttestationState.UNATTESTED.value,
            "capabilities": self._capability_payload(capabilities),
            "limitations": ACQUISITION_LIMITATIONS,
        }
        canonical_digest = self._digest(payload)
        acquisition = ConnectorPackageAcquisition(
            acquisition_id=f"connector-package-acquisition.{canonical_digest[:24]}",
            schema_version=ACQUISITION_SCHEMA,
            version=1,
            state=PackageAcquisitionState.QUARANTINED,
            source_type=PackageAcquisitionSource.MCP_BUILDER_HANDOFF,
            source_handoff_id=handoff.handoff_id,
            source_handoff_digest=handoff.canonical_digest,
            source_project_id=handoff.project_id,
            source_custodied_by=handoff.custodied_by,
            source_domain_reviewed_by=handoff.domain_reviewed_by,
            source_security_reviewed_by=handoff.security_reviewed_by,
            source_lab_operated_by=handoff.lab_operated_by,
            organization_id=handoff.organization_id,
            environment_id=handoff.environment_id,
            acquired_by=actor.subject_id,
            acquisition_profile=acquisition_profile,
            archive_contract_version=handoff.archive_contract_version,
            package_filename=handoff.package_filename,
            package_digest=handoff.package_digest,
            package_size_bytes=handoff.package_size_bytes,
            publisher_identity=PUBLISHER_IDENTITY,
            signature_state=PackageSignatureState.UNSIGNED,
            attestation_state=PublisherAttestationState.UNATTESTED,
            capabilities=capabilities,
            limitations=ACQUISITION_LIMITATIONS,
            canonical_digest=canonical_digest,
            request_fingerprint=request_fingerprint,
            idempotency_key=idempotency_key,
            acquired_at=self._clock(),
        )

        async with self._mutation_lock:
            existing = await self._repository.get_by_handoff(source_handoff_id=source_handoff_id)
            if existing is not None:
                self._verify_acquisition(existing)
                if (
                    existing.acquired_by == actor.subject_id
                    and existing.idempotency_key == idempotency_key
                    and existing.request_fingerprint == request_fingerprint
                ):
                    return replace(existing, reused=True)
                raise PackageAcquisitionError("package_acquisition_exists")
            await self._publisher.publish(package_digest=package_digest, content=content)
            copied = await self._publisher.read(
                package_digest=package_digest, size_bytes=handoff.package_size_bytes
            )
            if copied != content:
                raise PackageAcquisitionError("package_acquisition_archive_integrity_failed")
            await self._audit(
                actor=actor,
                correlation_id=correlation_id,
                permission_id=PACKAGE_ACQUIRE_PERMISSION,
                result_code="connector_package_acquired_quarantined",
                acquisition=acquisition,
            )
            if not await self._repository.add(acquisition):
                raced = await self._repository.get_by_create_key(
                    acquired_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != request_fingerprint:
                    raise PackageAcquisitionError("package_acquisition_conflict")
                self._verify_acquisition(raced)
                return replace(raced, reused=True)
        return acquisition

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        acquisition_id: str,
        correlation_id: str,
    ) -> ConnectorPackageAcquisition:
        self._require_enterprise_human(actor)
        acquisition = await self._repository.get_by_id(acquisition_id=acquisition_id)
        if acquisition is None:
            raise PackageAcquisitionError("package_acquisition_not_found")
        self._require_scope(actor, acquisition.organization_id, acquisition.environment_id)
        self._verify_acquisition(acquisition)
        await self._publisher.read(
            package_digest=acquisition.package_digest,
            size_bytes=acquisition.package_size_bytes,
        )
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=PACKAGE_ACQUISITION_READ_PERMISSION,
            result_code="connector_package_acquisition_read",
            acquisition=acquisition,
        )
        return acquisition

    async def read_acquired_archive(
        self, *, actor: AuthenticatedSubject, acquisition_id: str
    ) -> bytes:
        self._require_enterprise_human(actor)
        acquisition = await self._repository.get_by_id(acquisition_id=acquisition_id)
        if acquisition is None:
            raise PackageAcquisitionError("package_acquisition_not_found")
        self._require_scope(actor, acquisition.organization_id, acquisition.environment_id)
        self._verify_acquisition(acquisition)
        return await self._publisher.read(
            package_digest=acquisition.package_digest,
            size_bytes=acquisition.package_size_bytes,
        )

    async def close(self) -> None:
        await self._repository.close()

    @classmethod
    def _verify_handoff(cls, handoff: McpBuilderCandidateHandoff) -> None:
        payload = {
            "project_id": handoff.project_id,
            "project_version": handoff.project_version,
            "project_digest": handoff.project_digest,
            "source_digest": handoff.source_digest,
            "checkpoint_id": handoff.checkpoint_id,
            "checkpoint_digest": handoff.checkpoint_digest,
            "generation_id": handoff.generation_id,
            "generation_digest": handoff.generation_digest,
            "artifact_digest": handoff.artifact_digest,
            "validation_id": handoff.validation_id,
            "validation_digest": handoff.validation_digest,
            "domain_review_id": handoff.domain_review_id,
            "domain_review_digest": handoff.domain_review_digest,
            "domain_reviewed_by": handoff.domain_reviewed_by,
            "security_review_id": handoff.security_review_id,
            "security_review_digest": handoff.security_review_digest,
            "security_reviewed_by": handoff.security_reviewed_by,
            "lab_validation_id": handoff.lab_validation_id,
            "lab_validation_digest": handoff.lab_validation_digest,
            "lab_operated_by": handoff.lab_operated_by,
            "organization_id": handoff.organization_id,
            "environment_id": handoff.environment_id,
            "custodied_by": handoff.custodied_by,
            "handoff_profile": handoff.handoff_profile,
            "archive_contract_version": handoff.archive_contract_version,
            "state": handoff.state.value,
            "package_filename": handoff.package_filename,
            "package_digest": handoff.package_digest,
            "package_size_bytes": handoff.package_size_bytes,
            "package_entry_count": handoff.package_entry_count,
            "generated_file_count": handoff.generated_file_count,
            "generated_size_bytes": handoff.generated_size_bytes,
            "envelope_digest": handoff.envelope_digest,
            "signature_state": handoff.signature_state.value,
            "capabilities": [
                {
                    "candidate_id": item.candidate_id,
                    "capability_class": item.capability_class,
                    "required_permission": item.required_permission,
                    "supported_product_versions": item.supported_product_versions,
                    "source_citations": item.source_citations,
                }
                for item in handoff.capabilities
            ],
            "network_destinations": handoff.network_destinations,
            "limitations": handoff.limitations,
            "unsupported_behavior": handoff.unsupported_behavior,
            "manual_change_count": handoff.manual_change_count,
        }
        if cls._digest(payload) != handoff.canonical_digest:
            raise PackageAcquisitionError("package_acquisition_source_integrity_failed")

    @classmethod
    def _verify_acquisition(cls, acquisition: ConnectorPackageAcquisition) -> None:
        payload = {
            "state": acquisition.state.value,
            "source_type": acquisition.source_type.value,
            "source_handoff_id": acquisition.source_handoff_id,
            "source_handoff_digest": acquisition.source_handoff_digest,
            "source_project_id": acquisition.source_project_id,
            "source_custodied_by": acquisition.source_custodied_by,
            "source_domain_reviewed_by": acquisition.source_domain_reviewed_by,
            "source_security_reviewed_by": acquisition.source_security_reviewed_by,
            "source_lab_operated_by": acquisition.source_lab_operated_by,
            "organization_id": acquisition.organization_id,
            "environment_id": acquisition.environment_id,
            "acquired_by": acquisition.acquired_by,
            "acquisition_profile": acquisition.acquisition_profile,
            "archive_contract_version": acquisition.archive_contract_version,
            "package_filename": acquisition.package_filename,
            "package_digest": acquisition.package_digest,
            "package_size_bytes": acquisition.package_size_bytes,
            "publisher_identity": acquisition.publisher_identity,
            "signature_state": acquisition.signature_state.value,
            "attestation_state": acquisition.attestation_state.value,
            "capabilities": cls._capability_payload(acquisition.capabilities),
            "limitations": acquisition.limitations,
        }
        if cls._digest(payload) != acquisition.canonical_digest:
            raise PackageAcquisitionError("package_acquisition_integrity_failed")

    @classmethod
    def _verify_source_archive(cls, handoff: McpBuilderCandidateHandoff, content: bytes) -> None:
        if (
            not content
            or len(content) != handoff.package_size_bytes
            or len(content) > 25_000_000
            or sha256(content).hexdigest() != handoff.package_digest
        ):
            raise PackageAcquisitionError("package_acquisition_source_integrity_failed")
        try:
            with zipfile.ZipFile(io.BytesIO(content), "r") as archive:
                infos = archive.infolist()
                names = [item.filename for item in infos]
                if (
                    len(infos) != handoff.package_entry_count
                    or len(names) != len(set(names))
                    or names != sorted(names)
                    or "ATLAS-CANDIDATE-HANDOFF.json" not in names
                    or any(not cls._safe_archive_entry(item) for item in infos)
                ):
                    raise PackageAcquisitionError("package_acquisition_source_integrity_failed")
                envelope_info = archive.getinfo("ATLAS-CANDIDATE-HANDOFF.json")
                if envelope_info.file_size > 1_000_000:
                    raise PackageAcquisitionError("package_acquisition_source_integrity_failed")
                envelope_bytes = archive.read(envelope_info)
        except (OSError, ValueError, zipfile.BadZipFile, KeyError) as error:
            raise PackageAcquisitionError("package_acquisition_source_integrity_failed") from error
        if sha256(envelope_bytes).hexdigest() != handoff.envelope_digest:
            raise PackageAcquisitionError("package_acquisition_source_integrity_failed")
        try:
            envelope = json.loads(envelope_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise PackageAcquisitionError("package_acquisition_source_integrity_failed") from error
        if not isinstance(envelope, dict):
            raise PackageAcquisitionError("package_acquisition_source_integrity_failed")
        expected = {
            "schema_version": "atlas.mcp-builder-candidate-handoff-envelope.v1",
            "project_id": handoff.project_id,
            "project_digest": handoff.project_digest,
            "state": handoff.state.value,
            "signature_state": handoff.signature_state.value,
            "generated_file_count": handoff.generated_file_count,
            "manual_change_count": 0,
            "capabilities": [
                {
                    "candidate_id": item.candidate_id,
                    "capability_class": item.capability_class,
                    "required_permission": item.required_permission,
                    "supported_product_versions": list(item.supported_product_versions),
                    "source_citations": list(item.source_citations),
                }
                for item in handoff.capabilities
            ],
            "network_destinations": list(handoff.network_destinations),
            "package_signed": False,
            "connector_registered": False,
            "connector_installed": False,
            "connector_enabled": False,
            "runtime_trust_granted": False,
            "execution_authorized": False,
            "infrastructure_mutation_performed": False,
        }
        if any(envelope.get(key) != value for key, value in expected.items()):
            raise PackageAcquisitionError("package_acquisition_source_integrity_failed")

    @staticmethod
    def _safe_archive_entry(info: zipfile.ZipInfo) -> bool:
        path = PurePosixPath(info.filename)
        mode = (info.external_attr >> 16) & 0o170000
        return (
            bool(info.filename)
            and "\\" not in info.filename
            and not info.filename.endswith("/")
            and not path.is_absolute()
            and all(part not in {"", ".", ".."} for part in path.parts)
            and info.date_time == (1980, 1, 1, 0, 0, 0)
            and info.compress_type == zipfile.ZIP_STORED
            and mode == stat.S_IFREG
            and 0 < info.file_size <= 1_000_000
        )

    @staticmethod
    def _capability_payload(
        capabilities: tuple[AcquiredCapabilityEvidence, ...],
    ) -> list[dict[str, object]]:
        return [
            {
                "capability_id": item.capability_id,
                "capability_class": item.capability_class,
                "required_permission": item.required_permission,
                "supported_product_versions": item.supported_product_versions,
            }
            for item in capabilities
        ]

    @staticmethod
    def _digest(payload: object) -> str:
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        return sha256(encoded).hexdigest()

    @staticmethod
    def _require_enterprise_human(actor: AuthenticatedSubject) -> None:
        if (
            actor.kind is not SubjectKind.HUMAN
            or actor.authentication_method is AuthenticationMethod.DEVELOPMENT
            or actor.assurance_level
            not in {AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED}
        ):
            raise PackageAcquisitionError("package_acquisition_enterprise_human_mfa_required")

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise PackageAcquisitionError("package_acquisition_not_found")

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        acquisition: ConnectorPackageAcquisition,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.package-acquisition",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id=permission_id,
                resource_type="resource.connector.package-acquisition",
                scope_reference=acquisition.acquisition_id,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
            )
        )
