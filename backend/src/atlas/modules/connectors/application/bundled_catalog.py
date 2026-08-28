from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from enum import Enum
from hashlib import sha256
from typing import cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.connectors.application.instance_creation import (
    INSTANCE_CREATE_PERMISSION,
    INSTANCE_READ_PERMISSION,
    INSTANCE_RECORD_SCHEMA,
)
from atlas.modules.connectors.application.instance_creation_ports import (
    ConnectorInstanceRepository,
)
from atlas.modules.connectors.domain.bundled_catalog import BundledConnectorDescriptor
from atlas.modules.connectors.domain.instance_creation import (
    DISABLED_UNCONFIGURED,
    ConnectorInstanceRecord,
)
from atlas.modules.connectors.vendors.brocade_sannav.manifest import (
    FABRIC_HEALTH_CAPABILITY_ID,
    FABRIC_INVENTORY_CAPABILITY_ID,
)
from atlas.modules.connectors.vendors.brocade_sannav.manifest import (
    PACKAGE_ID as BROCADE_PACKAGE_ID,
)
from atlas.modules.connectors.vendors.hitachi_ops_center.manifest import (
    HEALTH_CAPABILITY_ID,
    INVENTORY_CAPABILITY_ID,
    PACKAGE_ID,
)
from atlas.modules.connectors.vendors.huawei_dorado.manifest import (
    CAPACITY_CAPABILITY_ID as HUAWEI_CAPACITY_CAPABILITY_ID,
)
from atlas.modules.connectors.vendors.huawei_dorado.manifest import (
    CONTROLLER_HEALTH_CAPABILITY_ID as HUAWEI_CONTROLLER_HEALTH_CAPABILITY_ID,
)
from atlas.modules.connectors.vendors.huawei_dorado.manifest import (
    PACKAGE_ID as HUAWEI_PACKAGE_ID,
)
from atlas.modules.connectors.vendors.huawei_dorado.manifest import (
    SYSTEM_IDENTITY_CAPABILITY_ID as HUAWEI_SYSTEM_IDENTITY_CAPABILITY_ID,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject, SubjectKind

_INSTANCE_KEY = re.compile(r"^[a-z][a-z0-9_.:-]{2,127}$")
_DESCRIPTOR_SCHEMA = "atlas.bundled-connector-descriptor.v1"


class BundledConnectorCatalogError(RuntimeError):
    pass


class BundledConnectorCatalogService:
    def __init__(
        self,
        *,
        descriptors: tuple[BundledConnectorDescriptor, ...],
        repository: ConnectorInstanceRepository,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._descriptors = {item.catalog_item_id: item for item in descriptors}
        if len(self._descriptors) != len(descriptors):
            raise ValueError("Bundled connector catalog item identifiers must be unique")
        for descriptor in descriptors:
            self._verify_descriptor(descriptor)
        self._repository = repository
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    async def list(
        self, *, actor: AuthenticatedSubject, correlation_id: str
    ) -> tuple[BundledConnectorDescriptor, ...]:
        self._require_human(actor)
        descriptors = tuple(
            sorted(self._descriptors.values(), key=lambda item: item.display_name.casefold())
        )
        for descriptor in descriptors:
            self._verify_descriptor(descriptor)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=INSTANCE_READ_PERMISSION,
            result_code="bundled_connector_catalog_listed",
            scope_reference=self._environment_id,
            idempotency_key=None,
            metadata=(("count", str(len(descriptors))),),
        )
        return descriptors

    async def create_instance(
        self,
        *,
        actor: AuthenticatedSubject,
        catalog_item_id: str,
        catalog_item_digest: str,
        instance_key: str,
        display_name: str,
        purpose: str,
        acknowledged_instance_is_disabled_and_grants_no_authority: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorInstanceRecord:
        self._require_human(actor)
        if not acknowledged_instance_is_disabled_and_grants_no_authority:
            raise BundledConnectorCatalogError("bundled_connector_acknowledgement_required")
        descriptor = self._descriptors.get(catalog_item_id)
        if descriptor is None:
            raise BundledConnectorCatalogError("bundled_connector_catalog_item_not_found")
        self._verify_descriptor(descriptor)
        if descriptor.canonical_digest != catalog_item_digest:
            raise BundledConnectorCatalogError("bundled_connector_catalog_digest_conflict")

        instance_key = instance_key.strip().lower()
        display_name = display_name.strip()
        purpose = purpose.strip()
        if (
            _INSTANCE_KEY.fullmatch(instance_key) is None
            or not 3 <= len(display_name) <= 200
            or not 20 <= len(purpose) <= 1000
            or not 8 <= len(idempotency_key) <= 128
        ):
            raise BundledConnectorCatalogError("bundled_connector_request_invalid")
        fingerprint = self._digest(
            {
                "catalog_item_id": catalog_item_id,
                "catalog_item_digest": catalog_item_digest,
                "organization_id": actor.organization_id,
                "environment_id": self._environment_id,
                "instance_key": instance_key,
                "display_name": display_name,
                "purpose": purpose,
            }
        )
        existing = await self._repository.get_by_create_key(
            created_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            return self._reuse(existing, actor, descriptor, fingerprint)

        async with self._mutation_lock:
            prior = await self._repository.get_by_scope_key(
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
                instance_key=instance_key,
            )
            if prior is not None:
                raise BundledConnectorCatalogError("bundled_connector_instance_key_conflict")
            await self._audit(
                actor=actor,
                correlation_id=correlation_id,
                permission_id=INSTANCE_CREATE_PERMISSION,
                result_code="bundled_connector_instance_creation_requested",
                scope_reference=descriptor.catalog_item_id,
                idempotency_key=idempotency_key,
                metadata=(("instance_key", instance_key),),
            )
            record = self._build_record(
                descriptor=descriptor,
                actor=actor,
                instance_key=instance_key,
                display_name=display_name,
                purpose=purpose,
                fingerprint=fingerprint,
                idempotency_key=idempotency_key,
            )
            await self._audit(
                actor=actor,
                correlation_id=correlation_id,
                permission_id=INSTANCE_CREATE_PERMISSION,
                result_code="bundled_connector_instance_creation_completed",
                scope_reference=record.instance_id,
                idempotency_key=idempotency_key,
                metadata=(("instance_state", record.instance_state),),
            )
            if not await self._repository.add(record):
                raced = await self._repository.get_by_create_key(
                    created_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None:
                    raise BundledConnectorCatalogError("bundled_connector_instance_conflict")
                return self._reuse(raced, actor, descriptor, fingerprint)
        return record

    def _build_record(
        self,
        *,
        descriptor: BundledConnectorDescriptor,
        actor: AuthenticatedSubject,
        instance_key: str,
        display_name: str,
        purpose: str,
        fingerprint: str,
        idempotency_key: str,
    ) -> ConnectorInstanceRecord:
        seed = self._digest(
            [
                actor.organization_id,
                self._environment_id,
                descriptor.catalog_item_id,
                descriptor.canonical_digest,
                instance_key,
            ]
        )

        def lineage(name: str) -> str:
            return self._digest(
                ["atlas.bundled-connector-catalog-lineage.v1", descriptor.canonical_digest, name]
            )

        record = ConnectorInstanceRecord(
            record_id=f"connector-instance-record.{seed[:24]}",
            schema_version=INSTANCE_RECORD_SCHEMA,
            version=1,
            source_installation_receipt_id=f"bundled-installation-receipt.{seed[:24]}",
            source_installation_receipt_digest=lineage("installation-receipt"),
            source_registration_record_id=f"bundled-registration-record.{seed[:24]}",
            source_registration_record_digest=lineage("registration-record"),
            source_publication_receipt_id=f"bundled-publication-receipt.{seed[:24]}",
            source_publication_receipt_digest=lineage("publication-receipt"),
            source_signing_receipt_id=f"bundled-signing-receipt.{seed[:24]}",
            source_signing_receipt_digest=lineage("signing-receipt"),
            source_approval_request_id=f"bundled-approval-evidence.{seed[:24]}",
            source_approval_request_digest=lineage("approval-evidence"),
            source_final_validation_id=f"bundled-validation-evidence.{seed[:24]}",
            source_final_validation_digest=lineage("validation-evidence"),
            source_acquisition_id=f"bundled-acquisition-evidence.{seed[:24]}",
            source_acquisition_digest=lineage("acquisition-evidence"),
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            package_digest=descriptor.package_digest,
            package_size_bytes=1,
            publisher_id=descriptor.publisher_id,
            connector_id=descriptor.connector_id,
            release_version=descriptor.release_version,
            provenance_digest=descriptor.provenance_digest,
            manifest_digest=descriptor.manifest_digest,
            sdk_profile=descriptor.sdk_profile,
            registry_profile_id="registry-profile.bundled-development",
            installation_policy_id="installation-policy.bundled-development",
            installation_policy_digest=lineage("installation-policy"),
            installation_store_profile_id="installation-store.bundled-development-evidence",
            installation_artifact_reference_schema="atlas.bundled-catalog-evidence-reference.v1",
            instance_policy_id="connector-instance-policy.bundled-development",
            instance_policy_digest=lineage("instance-policy"),
            instance_policy_version="version.1.0",
            instance_id=f"connector-instance.{seed[:24]}",
            instance_key=instance_key,
            display_name=display_name,
            instance_state=DISABLED_UNCONFIGURED,
            owner_id=actor.subject_id,
            support_group_id=descriptor.support_group_id,
            created_by=actor.subject_id,
            purpose=purpose,
            created_at=self._clock(),
            canonical_digest="0" * 64,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
        )
        return replace(record, canonical_digest=self._digest(self._record_payload(record)))

    def _reuse(
        self,
        record: ConnectorInstanceRecord,
        actor: AuthenticatedSubject,
        descriptor: BundledConnectorDescriptor,
        fingerprint: str,
    ) -> ConnectorInstanceRecord:
        if (
            record.created_by != actor.subject_id
            or record.request_fingerprint != fingerprint
            or record.connector_id != descriptor.connector_id
            or not record.source_installation_receipt_id.startswith("bundled-installation-receipt.")
        ):
            raise BundledConnectorCatalogError("bundled_connector_idempotency_conflict")
        self._verify_record(record)
        return replace(record, reused=True)

    @classmethod
    def _verify_descriptor(cls, descriptor: BundledConnectorDescriptor) -> None:
        if cls._digest(cls._descriptor_payload(descriptor)) != descriptor.canonical_digest:
            raise BundledConnectorCatalogError("bundled_connector_catalog_integrity_failed")

    @classmethod
    def _verify_record(cls, record: ConnectorInstanceRecord) -> None:
        if cls._digest(cls._record_payload(record)) != record.canonical_digest:
            raise BundledConnectorCatalogError("bundled_connector_instance_integrity_failed")
        if (
            record.instance_state != DISABLED_UNCONFIGURED
            or not record.eligible_for_configuration_governance
            or record.target_configured
            or record.credentials_resolved
            or record.connector_enabled
            or record.runtime_trust_granted
            or record.execution_authorized
            or record.deployment_approved
            or record.infrastructure_mutation_performed
        ):
            raise BundledConnectorCatalogError("bundled_connector_authority_boundary_failed")

    @classmethod
    def _descriptor_payload(cls, descriptor: BundledConnectorDescriptor) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(descriptor))
        payload.pop("canonical_digest")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _record_payload(cls, record: ConnectorInstanceRecord) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(record))
        for field in (
            "canonical_digest",
            "request_fingerprint",
            "idempotency_key",
            "retirement_request_fingerprint",
            "retirement_idempotency_key",
            "reused",
        ):
            payload.pop(field)
        if record.retired_by is None:
            for field in ("retired_by", "retired_at", "retirement_reason"):
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
    def _require_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise BundledConnectorCatalogError("bundled_connector_human_required")

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        scope_reference: str,
        idempotency_key: str | None,
        metadata: tuple[tuple[str, str], ...],
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.bundled_catalog",
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
                resource_type="resource.connector.catalog",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=metadata,
            )
        )


def build_hitachi_ops_center_bundled_descriptor() -> BundledConnectorDescriptor:
    package_digest = BundledConnectorCatalogService._digest(
        [PACKAGE_ID, "version.0.1.0", "bundled-development-package-evidence"]
    )
    descriptor = BundledConnectorDescriptor(
        catalog_item_id="catalog.connector.hitachi.opscenter",
        schema_version=_DESCRIPTOR_SCHEMA,
        version=1,
        connector_id=PACKAGE_ID,
        display_name="Hitachi Ops Center API Configuration Manager",
        vendor_name="Hitachi Vantara",
        release_version="version.0.1.0",
        sdk_profile="atlas.python312.v1",
        publisher_id="publisher.project-atlas",
        support_group_id="group.connector-platform-support",
        capability_ids=(INVENTORY_CAPABILITY_ID, HEALTH_CAPABILITY_ID),
        capability_classes=("C1",),
        package_digest=package_digest,
        provenance_digest=BundledConnectorCatalogService._digest(
            [PACKAGE_ID, "bundled-development-provenance-evidence"]
        ),
        manifest_digest=BundledConnectorCatalogService._digest(
            [PACKAGE_ID, "bundled-development-manifest-evidence"]
        ),
        canonical_digest="0" * 64,
    )
    return replace(
        descriptor,
        canonical_digest=BundledConnectorCatalogService._digest(
            BundledConnectorCatalogService._descriptor_payload(descriptor)
        ),
    )


def build_huawei_dorado_bundled_descriptor() -> BundledConnectorDescriptor:
    package_digest = BundledConnectorCatalogService._digest(
        [HUAWEI_PACKAGE_ID, "version.0.1.0", "bundled-development-package-evidence"]
    )
    descriptor = BundledConnectorDescriptor(
        catalog_item_id="catalog.connector.huawei.dorado",
        schema_version=_DESCRIPTOR_SCHEMA,
        version=1,
        connector_id=HUAWEI_PACKAGE_ID,
        display_name="Huawei OceanStor Dorado DeviceManager",
        vendor_name="Huawei Technologies Co., Ltd.",
        release_version="version.0.1.0",
        sdk_profile="atlas.python312.v1",
        publisher_id="publisher.project-atlas",
        support_group_id="group.connector-platform-support",
        capability_ids=(
            HUAWEI_SYSTEM_IDENTITY_CAPABILITY_ID,
            HUAWEI_CONTROLLER_HEALTH_CAPABILITY_ID,
            HUAWEI_CAPACITY_CAPABILITY_ID,
        ),
        capability_classes=("C1",),
        package_digest=package_digest,
        provenance_digest=BundledConnectorCatalogService._digest(
            [HUAWEI_PACKAGE_ID, "bundled-development-provenance-evidence"]
        ),
        manifest_digest=BundledConnectorCatalogService._digest(
            [HUAWEI_PACKAGE_ID, "bundled-development-manifest-evidence"]
        ),
        canonical_digest="0" * 64,
    )
    return replace(
        descriptor,
        canonical_digest=BundledConnectorCatalogService._digest(
            BundledConnectorCatalogService._descriptor_payload(descriptor)
        ),
    )


def build_brocade_sannav_bundled_descriptor() -> BundledConnectorDescriptor:
    package_digest = BundledConnectorCatalogService._digest(
        [BROCADE_PACKAGE_ID, "version.0.1.0", "bundled-development-package-evidence"]
    )
    descriptor = BundledConnectorDescriptor(
        catalog_item_id="catalog.connector.brocade.sannav",
        schema_version=_DESCRIPTOR_SCHEMA,
        version=1,
        connector_id=BROCADE_PACKAGE_ID,
        display_name="Brocade SANnav Management Portal",
        vendor_name="Broadcom (Brocade)",
        release_version="version.0.1.0",
        sdk_profile="atlas.python312.v1",
        publisher_id="publisher.project-atlas",
        support_group_id="group.connector-platform-support",
        capability_ids=(FABRIC_INVENTORY_CAPABILITY_ID, FABRIC_HEALTH_CAPABILITY_ID),
        capability_classes=("C1",),
        package_digest=package_digest,
        provenance_digest=BundledConnectorCatalogService._digest(
            [BROCADE_PACKAGE_ID, "bundled-development-provenance-evidence"]
        ),
        manifest_digest=BundledConnectorCatalogService._digest(
            [BROCADE_PACKAGE_ID, "bundled-development-manifest-evidence"]
        ),
        canonical_digest="0" * 64,
    )
    return replace(
        descriptor,
        canonical_digest=BundledConnectorCatalogService._digest(
            BundledConnectorCatalogService._descriptor_payload(descriptor)
        ),
    )
