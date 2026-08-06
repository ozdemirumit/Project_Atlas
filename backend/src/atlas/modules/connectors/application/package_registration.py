from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from hashlib import sha256
from typing import cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.connectors.application.package_registration_ports import (
    ConnectorPackageManifestInspector,
    InternalRegistryArtifactReader,
    PackageRegistrationError,
    PackageRegistrationPolicySource,
    PackageRegistrationPublicationSource,
    PackageRegistrationRepository,
)
from atlas.modules.connectors.application.registry_publication_ports import RegistryPublicationError
from atlas.modules.connectors.domain.package_registration import (
    ConnectorPackageRegistrationPolicySnapshot,
    ConnectorPackageRegistrationRecord,
    ConnectorRegisteredManifestSnapshot,
)
from atlas.modules.connectors.domain.registry_publication import (
    ConnectorInternalRegistryPublicationReceipt,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.mcp_builder.domain.candidate_handoff import McpBuilderCandidateHandoff

REGISTRATION_CREATE_PERMISSION = "connectors.package-registration-records.create"
REGISTRATION_READ_PERMISSION = "connectors.package-registration-records.read"
REGISTRATION_RECORD_SCHEMA = "atlas.connector-package-registration-record.v1"


class PackageRegistrationService:
    def __init__(
        self,
        *,
        repository: PackageRegistrationRepository,
        publication_source: PackageRegistrationPublicationSource,
        policy_source: PackageRegistrationPolicySource,
        artifact_reader: InternalRegistryArtifactReader,
        manifest_inspector: ConnectorPackageManifestInspector,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._publication_source = publication_source
        self._policy_source = policy_source
        self._artifact_reader = artifact_reader
        self._manifest_inspector = manifest_inspector
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    @property
    def repository(self) -> PackageRegistrationRepository:
        return self._repository

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_publication_receipt_id: str,
        source_publication_receipt_digest: str,
        package_digest: str,
        registration_policy_id: str,
        registration_policy_digest: str,
        purpose: str,
        acknowledged_registration_grants_no_installation_or_runtime_authority: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorPackageRegistrationRecord:
        self._require_enterprise_human(actor)
        if not acknowledged_registration_grants_no_installation_or_runtime_authority:
            raise PackageRegistrationError("package_registration_acknowledgement_required")
        purpose = purpose.strip()
        if not 20 <= len(purpose) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise PackageRegistrationError("package_registration_request_invalid")
        fingerprint = self._digest(
            {
                "source_publication_receipt_id": source_publication_receipt_id,
                "source_publication_receipt_digest": source_publication_receipt_digest,
                "package_digest": package_digest,
                "registration_policy_id": registration_policy_id,
                "registration_policy_digest": registration_policy_digest,
                "purpose": purpose,
            }
        )
        existing = await self._repository.get_by_create_key(
            registered_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            return self._reuse(existing, actor, fingerprint)

        try:
            (
                publication,
                handoff,
                source_actors,
            ) = await self._publication_source.package_registration_source(
                receipt_id=source_publication_receipt_id
            )
        except RegistryPublicationError as error:
            raise PackageRegistrationError("package_registration_source_not_found") from error
        policy = await self._policy_source.get_by_id(policy_id=registration_policy_id)
        if policy is None:
            raise PackageRegistrationError("package_registration_policy_not_found")
        self._verify_policy(policy)
        self._require_scope(actor, publication.organization_id, publication.environment_id)
        now = self._clock()
        self._verify_source(
            actor=actor,
            publication=publication,
            handoff=handoff,
            policy=policy,
            source_publication_receipt_digest=source_publication_receipt_digest,
            package_digest=package_digest,
            registration_policy_digest=registration_policy_digest,
            now=now,
        )
        forbidden = source_actors | {policy.signed_by, policy.reader_workload_id}
        if actor.subject_id in forbidden:
            raise PackageRegistrationError("package_registration_separation_required")

        async with self._mutation_lock:
            prior = await self._repository.get_by_publication_receipt(
                source_publication_receipt_id=publication.receipt_id
            )
            if prior is not None:
                if (
                    prior.registered_by == actor.subject_id
                    and prior.request_fingerprint == fingerprint
                ):
                    return replace(prior, reused=True)
                raise PackageRegistrationError("package_registration_record_exists")
            collision = await self._repository.get_by_package_release(
                connector_id=publication.connector_id,
                release_version=publication.release_version,
            )
            if collision is not None:
                raise PackageRegistrationError("package_registration_release_conflict")
            await self._audit(
                actor,
                correlation_id,
                "connector_package_registration_requested",
                publication.receipt_id,
                idempotency_key,
                (("package_digest", package_digest),),
            )
            try:
                content = await self._artifact_reader.read(
                    publication=publication.publication, policy=policy
                )
            except Exception as error:
                raise PackageRegistrationError(
                    "package_registration_registry_artifact_unavailable"
                ) from error
            if (
                len(content) != publication.package_size_bytes
                or sha256(content).hexdigest() != publication.package_digest
            ):
                raise PackageRegistrationError("package_registration_archive_integrity_failed")
            manifest = self._manifest_inspector.inspect(content=content, policy=policy)
            self._verify_manifest(manifest, publication, handoff)
            record_seed = self._digest([publication.receipt_id, manifest.manifest_digest])
            record = ConnectorPackageRegistrationRecord(
                record_id=f"connector-package-registration-record.{record_seed[:24]}",
                schema_version=REGISTRATION_RECORD_SCHEMA,
                version=1,
                source_publication_receipt_id=publication.receipt_id,
                source_publication_receipt_digest=publication.canonical_digest,
                source_signing_receipt_id=publication.source_signing_receipt_id,
                source_signing_receipt_digest=publication.source_signing_receipt_digest,
                source_approval_request_id=publication.source_approval_request_id,
                source_approval_request_digest=publication.source_approval_request_digest,
                source_final_validation_id=publication.source_final_validation_id,
                source_final_validation_digest=publication.source_final_validation_digest,
                source_acquisition_id=publication.source_acquisition_id,
                source_acquisition_digest=publication.source_acquisition_digest,
                organization_id=publication.organization_id,
                environment_id=publication.environment_id,
                package_digest=publication.package_digest,
                package_size_bytes=publication.package_size_bytes,
                publisher_id=publication.publisher_id,
                connector_id=publication.connector_id,
                release_version=publication.release_version,
                provenance_digest=publication.provenance_digest,
                registry_profile_id=publication.publication.registry_profile_id,
                reader_workload_id=policy.reader_workload_id,
                registration_policy_id=policy.policy_id,
                registration_policy_digest=policy.canonical_digest,
                registration_policy_version=policy.policy_version,
                manifest=manifest,
                registered_by=actor.subject_id,
                purpose=purpose,
                registered_at=now,
                canonical_digest="0" * 64,
                request_fingerprint=fingerprint,
                idempotency_key=idempotency_key,
            )
            record = replace(record, canonical_digest=self._digest(self._record_payload(record)))
            await self._audit(
                actor,
                correlation_id,
                "connector_package_registration_completed",
                record.record_id,
                idempotency_key,
                (
                    ("manifest_digest", manifest.manifest_digest),
                    ("capability_count", str(len(manifest.capabilities))),
                ),
            )
            if not await self._repository.add(record):
                raced = await self._repository.get_by_create_key(
                    registered_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    raise PackageRegistrationError("package_registration_record_conflict")
                self._verify_record(raced)
                return replace(raced, reused=True)
        return record

    async def get(
        self, *, actor: AuthenticatedSubject, record_id: str, correlation_id: str
    ) -> ConnectorPackageRegistrationRecord:
        self._require_enterprise_human(actor)
        record = await self._repository.get(record_id=record_id)
        if record is None:
            raise PackageRegistrationError("package_registration_record_not_found")
        self._verify_record(record)
        self._require_scope(actor, record.organization_id, record.environment_id)
        await self._audit(
            actor,
            correlation_id,
            "connector_package_registration_read",
            record.record_id,
            None,
            (),
            permission_id=REGISTRATION_READ_PERMISSION,
        )
        return record

    async def close(self) -> None:
        await self._repository.close()

    def _reuse(
        self,
        record: ConnectorPackageRegistrationRecord,
        actor: AuthenticatedSubject,
        fingerprint: str,
    ) -> ConnectorPackageRegistrationRecord:
        if record.registered_by != actor.subject_id or record.request_fingerprint != fingerprint:
            raise PackageRegistrationError("package_registration_idempotency_conflict")
        self._verify_record(record)
        return replace(record, reused=True)

    @classmethod
    def _verify_policy(cls, policy: ConnectorPackageRegistrationPolicySnapshot) -> None:
        payload = cast(dict[str, object], asdict(policy))
        payload.pop("canonical_digest")
        if cls._digest(cls._normalize(payload)) != policy.canonical_digest:
            raise PackageRegistrationError("package_registration_policy_integrity_failed")

    @staticmethod
    def _verify_source(
        *,
        actor: AuthenticatedSubject,
        publication: ConnectorInternalRegistryPublicationReceipt,
        handoff: McpBuilderCandidateHandoff,
        policy: ConnectorPackageRegistrationPolicySnapshot,
        source_publication_receipt_digest: str,
        package_digest: str,
        registration_policy_digest: str,
        now: datetime,
    ) -> None:
        if (
            publication.canonical_digest != source_publication_receipt_digest
            or publication.package_digest != package_digest
            or policy.canonical_digest != registration_policy_digest
            or policy.required_publication_receipt_schema != publication.schema_version
            or policy.required_registry_profile_id != publication.publication.registry_profile_id
            or policy.required_artifact_reference_schema
            != publication.publication.artifact_reference_schema
            or policy.record_schema != REGISTRATION_RECORD_SCHEMA
            or not (
                publication.organization_id == handoff.organization_id == policy.organization_id
            )
            or not (publication.environment_id == handoff.environment_id == policy.environment_id)
            or not policy.issued_at <= now < policy.expires_at
            or publication.published_at > now
            or now - publication.published_at
            > timedelta(hours=policy.maximum_publication_age_hours)
            or not publication.package_published
            or not publication.eligible_for_registration_governance
            or publication.promotion_blocked
            or (
                policy.required_assurance_level is AssuranceLevel.HARDWARE_BACKED
                and actor.assurance_level is not AssuranceLevel.HARDWARE_BACKED
            )
        ):
            raise PackageRegistrationError("package_registration_binding_invalid")

    @staticmethod
    def _verify_manifest(
        manifest: ConnectorRegisteredManifestSnapshot,
        publication: ConnectorInternalRegistryPublicationReceipt,
        handoff: McpBuilderCandidateHandoff,
    ) -> None:
        declared = tuple(
            sorted(
                (
                    item.capability_id,
                    item.capability_class,
                    item.required_permission,
                )
                for item in manifest.capabilities
            )
        )
        governed = tuple(
            sorted(
                (
                    item.candidate_id,
                    item.capability_class,
                    item.required_permission,
                )
                for item in handoff.capabilities
            )
        )
        supported_products = {
            version
            for capability in handoff.capabilities
            for version in capability.supported_product_versions
        }
        target_products_match = all(
            any(
                version == target or version.startswith(f"{target} ")
                for version in supported_products
            )
            for target in manifest.target_products
        ) and all(
            any(
                version == target or version.startswith(f"{target} ")
                for target in manifest.target_products
            )
            for version in supported_products
        )
        if (
            manifest.connector_id != publication.connector_id
            or manifest.release_version != publication.release_version
            or declared != governed
            or not target_products_match
            or manifest.network_destinations != handoff.network_destinations
        ):
            raise PackageRegistrationError("package_registration_manifest_binding_invalid")

    @classmethod
    def _verify_record(cls, record: ConnectorPackageRegistrationRecord) -> None:
        if cls._digest(cls._record_payload(record)) != record.canonical_digest:
            raise PackageRegistrationError("package_registration_record_integrity_failed")

    @classmethod
    def _record_payload(cls, record: ConnectorPackageRegistrationRecord) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(record))
        for field in ("canonical_digest", "request_fingerprint", "idempotency_key", "reused"):
            payload.pop(field)
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _normalize(cls, value: object) -> object:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(key): cls._normalize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._normalize(item) for item in value]
        return value

    @staticmethod
    def _digest(payload: object) -> str:
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
                "ascii"
            )
        ).hexdigest()

    @staticmethod
    def _require_enterprise_human(actor: AuthenticatedSubject) -> None:
        if (
            actor.kind is not SubjectKind.HUMAN
            or actor.authentication_method is AuthenticationMethod.DEVELOPMENT
            or actor.assurance_level
            not in {AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED}
        ):
            raise PackageRegistrationError("package_registration_enterprise_human_mfa_required")

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise PackageRegistrationError("package_registration_record_not_found")

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        idempotency_key: str | None,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = REGISTRATION_CREATE_PERMISSION,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.package-registration",
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
                resource_type="resource.connector.package-registration-record",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=metadata,
            )
        )


def build_development_package_registration_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> ConnectorPackageRegistrationPolicySnapshot:
    policy = ConnectorPackageRegistrationPolicySnapshot(
        policy_id="connector-package-registration-policy.development",
        schema_version="atlas.connector-package-registration-policy.v1",
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="version.1.0",
        required_publication_receipt_schema="atlas.connector-registry-publication-receipt.v1",
        maximum_publication_age_hours=168,
        required_assurance_level=AssuranceLevel.MULTI_FACTOR,
        required_registry_profile_id="registry-profile.nonproduction-internal",
        reader_workload_id="workload.connector-registry-reader",
        required_artifact_reference_schema="atlas.connector-registry-artifact-reference.v1",
        required_manifest_path="atlas-connector.yaml",
        required_manifest_schema="atlas.connector-manifest.v1",
        required_manifest_status="quarantined_generated_draft",
        required_sdk_profile="atlas.python312.v1",
        allowed_capability_classes=("C0", "C1"),
        maximum_archive_entries=500,
        maximum_manifest_bytes=262_144,
        maximum_capabilities=500,
        maximum_target_products=100,
        maximum_network_destinations=100,
        record_schema=REGISTRATION_RECORD_SCHEMA,
        signed_by="subject.package-registration-policy-owner",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    payload = cast(dict[str, object], asdict(policy))
    payload.pop("canonical_digest")
    return replace(
        policy,
        canonical_digest=PackageRegistrationService._digest(
            PackageRegistrationService._normalize(payload)
        ),
    )
