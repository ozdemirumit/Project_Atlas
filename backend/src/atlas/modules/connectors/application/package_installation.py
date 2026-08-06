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
from atlas.modules.connectors.application.package_installation_ports import (
    ConnectorPackageInstaller,
    PackageInstallationArtifactReader,
    PackageInstallationError,
    PackageInstallationManifestInspector,
    PackageInstallationPolicySource,
    PackageInstallationRegistrationSource,
    PackageInstallationRepository,
)
from atlas.modules.connectors.application.package_registration_ports import PackageRegistrationError
from atlas.modules.connectors.domain.package_installation import (
    ConnectorPackageInstallationPolicySnapshot,
    ConnectorPackageInstallationReceipt,
    ConnectorPackageInstallationResult,
)
from atlas.modules.connectors.domain.package_registration import ConnectorPackageRegistrationRecord
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

INSTALLATION_CREATE_PERMISSION = "connectors.package-installation-receipts.create"
INSTALLATION_READ_PERMISSION = "connectors.package-installation-receipts.read"
INSTALLATION_RECEIPT_SCHEMA = "atlas.connector-package-installation-receipt.v1"


class PackageInstallationService:
    def __init__(
        self,
        *,
        repository: PackageInstallationRepository,
        registration_source: PackageInstallationRegistrationSource,
        policy_source: PackageInstallationPolicySource,
        artifact_reader: PackageInstallationArtifactReader,
        manifest_inspector: PackageInstallationManifestInspector,
        installer: ConnectorPackageInstaller,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._registration_source = registration_source
        self._policy_source = policy_source
        self._artifact_reader = artifact_reader
        self._manifest_inspector = manifest_inspector
        self._installer = installer
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    @property
    def repository(self) -> PackageInstallationRepository:
        return self._repository

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_registration_record_id: str,
        source_registration_record_digest: str,
        package_digest: str,
        installation_policy_id: str,
        installation_policy_digest: str,
        purpose: str,
        acknowledged_installation_grants_no_instance_or_runtime_authority: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorPackageInstallationReceipt:
        self._require_enterprise_human(actor)
        if not acknowledged_installation_grants_no_instance_or_runtime_authority:
            raise PackageInstallationError("package_installation_acknowledgement_required")
        purpose = purpose.strip()
        if not 20 <= len(purpose) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise PackageInstallationError("package_installation_request_invalid")
        fingerprint = self._digest(
            {
                "source_registration_record_id": source_registration_record_id,
                "source_registration_record_digest": source_registration_record_digest,
                "package_digest": package_digest,
                "installation_policy_id": installation_policy_id,
                "installation_policy_digest": installation_policy_digest,
                "purpose": purpose,
            }
        )
        existing = await self._repository.get_by_create_key(
            installed_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            return self._reuse(existing, actor, fingerprint)

        try:
            (
                registration,
                publication,
                handoff,
                source_actors,
            ) = await self._registration_source.package_installation_source(
                record_id=source_registration_record_id
            )
        except PackageRegistrationError as error:
            raise PackageInstallationError("package_installation_source_not_found") from error
        policy = await self._policy_source.get_by_id(policy_id=installation_policy_id)
        if policy is None:
            raise PackageInstallationError("package_installation_policy_not_found")
        self._verify_policy(policy)
        self._require_scope(actor, registration.organization_id, registration.environment_id)
        now = self._clock()
        self._verify_source(
            actor=actor,
            registration=registration,
            publication=publication,
            handoff=handoff,
            policy=policy,
            source_registration_record_digest=source_registration_record_digest,
            package_digest=package_digest,
            installation_policy_digest=installation_policy_digest,
            now=now,
        )
        forbidden = source_actors | {
            policy.signed_by,
            policy.reader_workload_id,
            policy.installer_workload_id,
            policy.installation_custodian_id,
        }
        if actor.subject_id in forbidden:
            raise PackageInstallationError("package_installation_separation_required")

        async with self._mutation_lock:
            prior = await self._repository.get_by_registration_record(
                source_registration_record_id=registration.record_id
            )
            if prior is not None:
                if (
                    prior.installed_by == actor.subject_id
                    and prior.request_fingerprint == fingerprint
                ):
                    return replace(prior, reused=True)
                raise PackageInstallationError("package_installation_receipt_exists")
            collision = await self._repository.get_by_package_release(
                connector_id=registration.connector_id,
                release_version=registration.release_version,
            )
            if collision is not None:
                raise PackageInstallationError("package_installation_release_conflict")
            await self._audit(
                actor,
                correlation_id,
                "connector_package_installation_requested",
                registration.record_id,
                idempotency_key,
                (("package_digest", package_digest),),
            )
            try:
                content = await self._artifact_reader.read(
                    publication=publication.publication, policy=policy
                )
            except Exception as error:
                raise PackageInstallationError(
                    "package_installation_registry_artifact_unavailable"
                ) from error
            if (
                len(content) != registration.package_size_bytes
                or sha256(content).hexdigest() != registration.package_digest
            ):
                raise PackageInstallationError("package_installation_archive_integrity_failed")
            try:
                manifest = self._manifest_inspector.inspect(content=content, policy=policy)
            except PackageRegistrationError as error:
                raise PackageInstallationError("package_installation_manifest_invalid") from error
            if manifest != registration.manifest:
                raise PackageInstallationError("package_installation_manifest_binding_invalid")
            try:
                result = await self._installer.install(
                    content=content,
                    registration=registration,
                    policy=policy,
                    idempotency_key=idempotency_key,
                )
            except PackageInstallationError:
                raise
            except Exception as error:
                raise PackageInstallationError(
                    "package_installation_installer_unavailable"
                ) from error
            self._verify_result(result, registration, policy)
            receipt_seed = self._digest([registration.record_id, result.artifact_reference])
            receipt = ConnectorPackageInstallationReceipt(
                receipt_id=f"connector-package-installation-receipt.{receipt_seed[:24]}",
                schema_version=INSTALLATION_RECEIPT_SCHEMA,
                version=1,
                source_registration_record_id=registration.record_id,
                source_registration_record_digest=registration.canonical_digest,
                source_publication_receipt_id=registration.source_publication_receipt_id,
                source_publication_receipt_digest=registration.source_publication_receipt_digest,
                source_signing_receipt_id=registration.source_signing_receipt_id,
                source_signing_receipt_digest=registration.source_signing_receipt_digest,
                source_approval_request_id=registration.source_approval_request_id,
                source_approval_request_digest=registration.source_approval_request_digest,
                source_final_validation_id=registration.source_final_validation_id,
                source_final_validation_digest=registration.source_final_validation_digest,
                source_acquisition_id=registration.source_acquisition_id,
                source_acquisition_digest=registration.source_acquisition_digest,
                organization_id=registration.organization_id,
                environment_id=registration.environment_id,
                package_digest=registration.package_digest,
                package_size_bytes=registration.package_size_bytes,
                publisher_id=registration.publisher_id,
                connector_id=registration.connector_id,
                release_version=registration.release_version,
                provenance_digest=registration.provenance_digest,
                manifest_digest=registration.manifest.manifest_digest,
                sdk_profile=registration.manifest.sdk_profile,
                registry_profile_id=registration.registry_profile_id,
                registration_policy_id=registration.registration_policy_id,
                registration_policy_digest=registration.registration_policy_digest,
                installation_policy_id=policy.policy_id,
                installation_policy_digest=policy.canonical_digest,
                installation_policy_version=policy.policy_version,
                installation=result,
                installed_by=actor.subject_id,
                purpose=purpose,
                installed_at=now,
                canonical_digest="0" * 64,
                request_fingerprint=fingerprint,
                idempotency_key=idempotency_key,
            )
            receipt = replace(
                receipt, canonical_digest=self._digest(self._receipt_payload(receipt))
            )
            await self._audit(
                actor,
                correlation_id,
                "connector_package_installation_completed",
                receipt.receipt_id,
                idempotency_key,
                (
                    ("manifest_digest", receipt.manifest_digest),
                    ("installation_store_profile_id", result.installation_store_profile_id),
                ),
            )
            if not await self._repository.add(receipt):
                raced = await self._repository.get_by_create_key(
                    installed_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    raise PackageInstallationError("package_installation_receipt_conflict")
                self._verify_receipt(raced)
                return replace(raced, reused=True)
        return receipt

    async def get(
        self, *, actor: AuthenticatedSubject, receipt_id: str, correlation_id: str
    ) -> ConnectorPackageInstallationReceipt:
        self._require_enterprise_human(actor)
        receipt = await self._repository.get(receipt_id=receipt_id)
        if receipt is None:
            raise PackageInstallationError("package_installation_receipt_not_found")
        self._verify_receipt(receipt)
        self._require_scope(actor, receipt.organization_id, receipt.environment_id)
        await self._audit(
            actor,
            correlation_id,
            "connector_package_installation_read",
            receipt.receipt_id,
            None,
            (),
            permission_id=INSTALLATION_READ_PERMISSION,
        )
        return receipt

    async def connector_instance_creation_source(
        self, *, receipt_id: str
    ) -> tuple[
        ConnectorPackageInstallationReceipt,
        ConnectorPackageInstallationPolicySnapshot,
        ConnectorPackageRegistrationRecord,
        frozenset[str],
    ]:
        receipt = await self._repository.get(receipt_id=receipt_id)
        if receipt is None:
            raise PackageInstallationError("package_installation_receipt_not_found")
        self._verify_receipt(receipt)
        try:
            (
                registration,
                _publication,
                _handoff,
                source_actors,
            ) = await self._registration_source.package_installation_source(
                record_id=receipt.source_registration_record_id
            )
        except PackageRegistrationError as error:
            raise PackageInstallationError("package_installation_source_not_found") from error
        policy = await self._policy_source.get_by_id(policy_id=receipt.installation_policy_id)
        if policy is None:
            raise PackageInstallationError("package_installation_policy_not_found")
        self._verify_policy(policy)
        self._verify_result(receipt.installation, registration, policy)
        if (
            receipt.source_registration_record_digest != registration.canonical_digest
            or receipt.source_publication_receipt_id != registration.source_publication_receipt_id
            or receipt.source_publication_receipt_digest
            != registration.source_publication_receipt_digest
            or receipt.source_signing_receipt_id != registration.source_signing_receipt_id
            or receipt.source_signing_receipt_digest != registration.source_signing_receipt_digest
            or receipt.source_approval_request_id != registration.source_approval_request_id
            or receipt.source_approval_request_digest != registration.source_approval_request_digest
            or receipt.source_final_validation_id != registration.source_final_validation_id
            or receipt.source_final_validation_digest != registration.source_final_validation_digest
            or receipt.source_acquisition_id != registration.source_acquisition_id
            or receipt.source_acquisition_digest != registration.source_acquisition_digest
            or receipt.organization_id != registration.organization_id
            or receipt.environment_id != registration.environment_id
            or receipt.package_digest != registration.package_digest
            or receipt.package_size_bytes != registration.package_size_bytes
            or receipt.publisher_id != registration.publisher_id
            or receipt.connector_id != registration.connector_id
            or receipt.release_version != registration.release_version
            or receipt.provenance_digest != registration.provenance_digest
            or receipt.manifest_digest != registration.manifest.manifest_digest
            or receipt.sdk_profile != registration.manifest.sdk_profile
            or receipt.registry_profile_id != registration.registry_profile_id
            or receipt.registration_policy_id != registration.registration_policy_id
            or receipt.registration_policy_digest != registration.registration_policy_digest
            or receipt.installation_policy_digest != policy.canonical_digest
            or receipt.installation_policy_version != policy.policy_version
            or not receipt.package_installed
            or not receipt.eligible_for_instance_governance
            or receipt.instance_created
            or receipt.promotion_blocked
            or any(
                (
                    receipt.target_configured,
                    receipt.credentials_resolved,
                    receipt.connector_enabled,
                    receipt.runtime_trust_granted,
                    receipt.execution_authorized,
                    receipt.deployment_approved,
                    receipt.infrastructure_mutation_performed,
                )
            )
        ):
            raise PackageInstallationError("package_installation_source_binding_invalid")
        actors = source_actors | {
            receipt.installed_by,
            policy.signed_by,
            policy.reader_workload_id,
            policy.installer_workload_id,
            policy.installation_custodian_id,
        }
        return receipt, policy, registration, frozenset(actors)

    async def close(self) -> None:
        await self._repository.close()

    def _reuse(
        self,
        receipt: ConnectorPackageInstallationReceipt,
        actor: AuthenticatedSubject,
        fingerprint: str,
    ) -> ConnectorPackageInstallationReceipt:
        if receipt.installed_by != actor.subject_id or receipt.request_fingerprint != fingerprint:
            raise PackageInstallationError("package_installation_idempotency_conflict")
        self._verify_receipt(receipt)
        return replace(receipt, reused=True)

    @classmethod
    def _verify_policy(cls, policy: ConnectorPackageInstallationPolicySnapshot) -> None:
        payload = cast(dict[str, object], asdict(policy))
        payload.pop("canonical_digest")
        if cls._digest(cls._normalize(payload)) != policy.canonical_digest:
            raise PackageInstallationError("package_installation_policy_integrity_failed")

    @staticmethod
    def _verify_source(
        *,
        actor: AuthenticatedSubject,
        registration: ConnectorPackageRegistrationRecord,
        publication: ConnectorInternalRegistryPublicationReceipt,
        handoff: McpBuilderCandidateHandoff,
        policy: ConnectorPackageInstallationPolicySnapshot,
        source_registration_record_digest: str,
        package_digest: str,
        installation_policy_digest: str,
        now: datetime,
    ) -> None:
        classes = {item.capability_class for item in registration.manifest.capabilities}
        if (
            registration.canonical_digest != source_registration_record_digest
            or registration.package_digest != package_digest
            or policy.canonical_digest != installation_policy_digest
            or policy.required_registration_record_schema != registration.schema_version
            or policy.receipt_schema != INSTALLATION_RECEIPT_SCHEMA
            or policy.required_registry_profile_id != registration.registry_profile_id
            or registration.source_publication_receipt_id != publication.receipt_id
            or registration.source_publication_receipt_digest != publication.canonical_digest
            or registration.package_digest != publication.package_digest
            or registration.manifest.sdk_profile != policy.required_sdk_profile
            or registration.manifest.source_status != policy.required_manifest_status
            or registration.manifest.schema_version != policy.required_manifest_schema
            or not classes.issubset(set(policy.allowed_capability_classes))
            or registration.package_size_bytes > policy.maximum_package_bytes
            or not policy.issued_at <= now < policy.expires_at
            or registration.registered_at > now
            or now - registration.registered_at
            > timedelta(hours=policy.maximum_registration_age_hours)
            or not registration.connector_registered
            or not registration.eligible_for_installation_governance
            or registration.connector_installed
            or registration.promotion_blocked
            or (
                policy.required_assurance_level is AssuranceLevel.HARDWARE_BACKED
                and actor.assurance_level is not AssuranceLevel.HARDWARE_BACKED
            )
        ):
            raise PackageInstallationError("package_installation_binding_invalid")

    @staticmethod
    def _verify_result(
        result: ConnectorPackageInstallationResult,
        registration: ConnectorPackageRegistrationRecord,
        policy: ConnectorPackageInstallationPolicySnapshot,
    ) -> None:
        if (
            result.installer_profile_id != policy.installer_profile_id
            or result.installer_workload_id != policy.installer_workload_id
            or result.installation_custodian_id != policy.installation_custodian_id
            or result.installation_store_profile_id != policy.installation_store_profile_id
            or result.artifact_reference_schema != policy.installation_artifact_reference_schema
            or result.package_digest != registration.package_digest
            or result.package_size_bytes != registration.package_size_bytes
        ):
            raise PackageInstallationError("package_installation_result_binding_invalid")

    @classmethod
    def _verify_receipt(cls, receipt: ConnectorPackageInstallationReceipt) -> None:
        if cls._digest(cls._receipt_payload(receipt)) != receipt.canonical_digest:
            raise PackageInstallationError("package_installation_receipt_integrity_failed")

    @classmethod
    def _receipt_payload(cls, receipt: ConnectorPackageInstallationReceipt) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(receipt))
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
            raise PackageInstallationError("package_installation_enterprise_human_mfa_required")

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise PackageInstallationError("package_installation_receipt_not_found")

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        idempotency_key: str | None,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = INSTALLATION_CREATE_PERMISSION,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.package-installation",
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
                resource_type="resource.connector.package-installation-receipt",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=metadata,
            )
        )


def build_development_package_installation_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> ConnectorPackageInstallationPolicySnapshot:
    policy = ConnectorPackageInstallationPolicySnapshot(
        policy_id="connector-package-installation-policy.development",
        schema_version="atlas.connector-package-installation-policy.v1",
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="version.1.0",
        required_registration_record_schema="atlas.connector-package-registration-record.v1",
        maximum_registration_age_hours=168,
        maximum_package_bytes=25_000_000,
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
        installer_profile_id="installer-profile.nonexecuting-v1",
        installer_workload_id="workload.connector-package-installer",
        installation_custodian_id="subject.connector-installation-custodian",
        installation_store_profile_id="installation-store.nonproduction-immutable",
        installation_artifact_reference_schema="atlas.connector-installation-artifact-reference.v1",
        receipt_schema=INSTALLATION_RECEIPT_SCHEMA,
        signed_by="subject.package-installation-policy-owner",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    payload = cast(dict[str, object], asdict(policy))
    payload.pop("canonical_digest")
    return replace(
        policy,
        canonical_digest=PackageInstallationService._digest(
            PackageInstallationService._normalize(payload)
        ),
    )
