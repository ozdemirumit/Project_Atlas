from __future__ import annotations

import asyncio
import io
import json
import re
import stat
import zipfile
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import PurePosixPath
from typing import Any, TypeGuard
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.connectors.application.acquisition import (
    ACQUISITION_PROFILE,
    PackageAcquisitionService,
)
from atlas.modules.connectors.application.validation_intake_ports import (
    AcquiredPackageSource,
    PackageAcquisitionSource,
    PackageValidationError,
    PackageValidationRepository,
)
from atlas.modules.connectors.domain.acquisition import ConnectorPackageAcquisition
from atlas.modules.connectors.domain.validation_intake import (
    ConnectorPackageValidation,
    PackageValidationCheck,
    PackageValidationCheckState,
    PackageValidationLifecycle,
    PackageValidationOutcome,
    PackageValidationSeverity,
    ValidatedSchemaEvidence,
    ValidatedSchemaPurpose,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

PACKAGE_VALIDATION_CREATE_PERMISSION = "connectors.package-validations.create"
PACKAGE_VALIDATION_READ_PERMISSION = "connectors.package-validations.read"
VALIDATION_SCHEMA = "atlas.connector-package-validation.v1"
VALIDATION_PROFILE = "atlas.connector-validation-intake.builder-v1"
VALIDATOR_VERSION = "atlas.connector-manifest-schema-validator.v1"
SUPPORTED_ARCHIVE_CONTRACT = "mcp-builder-candidate-zip.v1"
MANIFEST_PATH = "atlas-connector.yaml"
HANDOFF_PATH = "ATLAS-CANDIDATE-HANDOFF.json"
CONFIG_SCHEMA_PATH = "schemas/config/config.schema.json"
JSON_SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"

VALIDATION_LIMITATIONS = (
    "This report covers exact acquisition, archive, manifest, and JSON Schema intake only.",
    "Dependency, vulnerability, malware, secret-content, license, static-code, contract, runner, "
    "self-test, and lab validation remain incomplete.",
    "Signing, publisher attestation, registration, approval, installation, enablement, "
    "configuration, runtime trust, execution, and deployment remain prohibited.",
)

_MANIFEST_KEYS = {
    "schema_version",
    "connector_id",
    "version",
    "status",
    "sdk_profile",
    "target_products",
    "network_destinations",
    "configuration_keys",
    "secret_reference_ids",
    "capabilities",
    "runtime_trust",
    "execution_authorized",
}
_HANDOFF_KEYS = {
    "schema_version",
    "project_id",
    "project_version",
    "project_digest",
    "source_digest",
    "checkpoint_id",
    "checkpoint_digest",
    "generation_id",
    "generation_digest",
    "artifact_digest",
    "validation_id",
    "validation_digest",
    "domain_review_id",
    "domain_review_digest",
    "domain_reviewed_by",
    "security_review_id",
    "security_review_digest",
    "security_reviewed_by",
    "lab_validation_id",
    "lab_validation_digest",
    "lab_operated_by",
    "organization_id",
    "environment_id",
    "custodied_by",
    "handoff_profile",
    "archive_contract_version",
    "state",
    "signature_state",
    "capabilities",
    "network_destinations",
    "limitations",
    "unsupported_behavior",
    "generated_file_count",
    "manual_change_count",
    "package_signed",
    "connector_registered",
    "connector_installed",
    "connector_enabled",
    "runtime_trust_granted",
    "execution_authorized",
    "infrastructure_mutation_performed",
}
_SAFE_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")
_SEMANTIC_DRAFT = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)-draft$")


class _DuplicateJsonKey(ValueError):
    pass


class PackageValidationService:
    def __init__(
        self,
        *,
        repository: PackageValidationRepository,
        acquisition_source: PackageAcquisitionSource,
        archive_source: AcquiredPackageSource,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._acquisition_source = acquisition_source
        self._archive_source = archive_source
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    @property
    def repository(self) -> PackageValidationRepository:
        return self._repository

    @property
    def acquisition_source(self) -> PackageAcquisitionSource:
        return self._acquisition_source

    @property
    def archive_source(self) -> AcquiredPackageSource:
        return self._archive_source

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_acquisition_id: str,
        source_acquisition_digest: str,
        package_digest: str,
        validation_profile: str,
        acknowledged_untrusted_quarantined_package: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorPackageValidation:
        self._require_enterprise_human(actor)
        if not acknowledged_untrusted_quarantined_package:
            raise PackageValidationError("package_validation_acknowledgement_required")
        if validation_profile != VALIDATION_PROFILE:
            raise PackageValidationError("package_validation_profile_unsupported")
        if not 8 <= len(idempotency_key) <= 128:
            raise PackageValidationError("package_validation_idempotency_key_invalid")

        request_fingerprint = self._digest(
            {
                "source_acquisition_id": source_acquisition_id,
                "source_acquisition_digest": source_acquisition_digest,
                "package_digest": package_digest,
                "validation_profile": validation_profile,
                "acknowledged_untrusted_quarantined_package": True,
                "validated_by": actor.subject_id,
            }
        )
        existing_by_key = await self._repository.get_by_create_key(
            validated_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if existing_by_key is not None:
            self._verify_validation(existing_by_key)
            if existing_by_key.request_fingerprint == request_fingerprint:
                return replace(existing_by_key, reused=True)
            raise PackageValidationError("package_validation_idempotency_conflict")

        acquisition = await self._acquisition_source.get_by_id(acquisition_id=source_acquisition_id)
        if acquisition is None:
            raise PackageValidationError("package_validation_source_not_found")
        self._require_scope(actor, acquisition.organization_id, acquisition.environment_id)
        self._require_separation(actor, acquisition)
        self._verify_acquisition(acquisition)
        if (
            acquisition.canonical_digest != source_acquisition_digest
            or acquisition.package_digest != package_digest
        ):
            raise PackageValidationError("package_validation_source_not_found")

        try:
            content = await self._archive_source.read(
                package_digest=package_digest, size_bytes=acquisition.package_size_bytes
            )
        except Exception as error:
            raise PackageValidationError("package_validation_archive_integrity_failed") from error
        files, envelope = self._verify_archive(acquisition, content)
        checks, manifest_digest, schema_evidence = self._validate_manifest_and_schemas(
            acquisition=acquisition,
            files=files,
            envelope=envelope,
        )
        outcome = (
            PackageValidationOutcome.PASSED
            if all(item.state is PackageValidationCheckState.PASSED for item in checks)
            else PackageValidationOutcome.FAILED
        )
        capability_ids = tuple(sorted(item.capability_id for item in acquisition.capabilities))
        payload = {
            "lifecycle": PackageValidationLifecycle.VALIDATING.value,
            "outcome": outcome.value,
            "source_acquisition_id": acquisition.acquisition_id,
            "source_acquisition_digest": acquisition.canonical_digest,
            "source_handoff_id": acquisition.source_handoff_id,
            "source_handoff_digest": acquisition.source_handoff_digest,
            "source_project_id": acquisition.source_project_id,
            "source_acquired_by": acquisition.acquired_by,
            "source_custodied_by": acquisition.source_custodied_by,
            "source_domain_reviewed_by": acquisition.source_domain_reviewed_by,
            "source_security_reviewed_by": acquisition.source_security_reviewed_by,
            "source_lab_operated_by": acquisition.source_lab_operated_by,
            "organization_id": acquisition.organization_id,
            "environment_id": acquisition.environment_id,
            "validated_by": actor.subject_id,
            "validation_profile": validation_profile,
            "validator_version": VALIDATOR_VERSION,
            "package_digest": acquisition.package_digest,
            "package_size_bytes": acquisition.package_size_bytes,
            "manifest_path": MANIFEST_PATH,
            "manifest_digest": manifest_digest,
            "capability_ids": capability_ids,
            "schema_evidence": self._schema_payload(schema_evidence),
            "checks": self._check_payload(checks),
            "limitations": VALIDATION_LIMITATIONS,
        }
        canonical_digest = self._digest(payload)
        validation = ConnectorPackageValidation(
            validation_id=f"connector-package-validation.{canonical_digest[:24]}",
            schema_version=VALIDATION_SCHEMA,
            version=1,
            lifecycle=PackageValidationLifecycle.VALIDATING,
            outcome=outcome,
            source_acquisition_id=acquisition.acquisition_id,
            source_acquisition_digest=acquisition.canonical_digest,
            source_handoff_id=acquisition.source_handoff_id,
            source_handoff_digest=acquisition.source_handoff_digest,
            source_project_id=acquisition.source_project_id,
            source_acquired_by=acquisition.acquired_by,
            source_custodied_by=acquisition.source_custodied_by,
            source_domain_reviewed_by=acquisition.source_domain_reviewed_by,
            source_security_reviewed_by=acquisition.source_security_reviewed_by,
            source_lab_operated_by=acquisition.source_lab_operated_by,
            organization_id=acquisition.organization_id,
            environment_id=acquisition.environment_id,
            validated_by=actor.subject_id,
            validation_profile=validation_profile,
            validator_version=VALIDATOR_VERSION,
            package_digest=acquisition.package_digest,
            package_size_bytes=acquisition.package_size_bytes,
            manifest_path=MANIFEST_PATH,
            manifest_digest=manifest_digest,
            capability_ids=capability_ids,
            schema_evidence=schema_evidence,
            checks=checks,
            limitations=VALIDATION_LIMITATIONS,
            canonical_digest=canonical_digest,
            request_fingerprint=request_fingerprint,
            idempotency_key=idempotency_key,
            validated_at=self._clock(),
        )

        async with self._mutation_lock:
            existing = await self._repository.get_by_acquisition(
                source_acquisition_id=source_acquisition_id
            )
            if existing is not None:
                self._verify_validation(existing)
                if (
                    existing.validated_by == actor.subject_id
                    and existing.idempotency_key == idempotency_key
                    and existing.request_fingerprint == request_fingerprint
                ):
                    return replace(existing, reused=True)
                raise PackageValidationError("package_validation_exists")
            await self._audit(
                actor=actor,
                correlation_id=correlation_id,
                permission_id=PACKAGE_VALIDATION_CREATE_PERMISSION,
                result_code=f"connector_package_manifest_schema_{outcome.value}",
                validation=validation,
            )
            if not await self._repository.add(validation):
                raced = await self._repository.get_by_create_key(
                    validated_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != request_fingerprint:
                    raise PackageValidationError("package_validation_conflict")
                self._verify_validation(raced)
                return replace(raced, reused=True)
        return validation

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        validation_id: str,
        correlation_id: str,
    ) -> ConnectorPackageValidation:
        self._require_enterprise_human(actor)
        validation = await self._repository.get_by_id(validation_id=validation_id)
        if validation is None:
            raise PackageValidationError("package_validation_not_found")
        self._require_scope(actor, validation.organization_id, validation.environment_id)
        if actor.subject_id in {
            validation.source_acquired_by,
            validation.source_custodied_by,
            validation.source_domain_reviewed_by,
            validation.source_security_reviewed_by,
            validation.source_lab_operated_by,
        }:
            raise PackageValidationError("package_validation_not_found")
        self._verify_validation(validation)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=PACKAGE_VALIDATION_READ_PERMISSION,
            result_code="connector_package_validation_read",
            validation=validation,
        )
        return validation

    async def close(self) -> None:
        await self._repository.close()

    @classmethod
    def _verify_acquisition(cls, acquisition: ConnectorPackageAcquisition) -> None:
        try:
            PackageAcquisitionService._verify_acquisition(acquisition)
        except Exception as error:
            raise PackageValidationError("package_validation_source_integrity_failed") from error
        if (
            acquisition.acquisition_profile != ACQUISITION_PROFILE
            or acquisition.archive_contract_version != SUPPORTED_ARCHIVE_CONTRACT
            or not acquisition.package_acquired
            or not acquisition.integrity_verified
            or acquisition.package_signed
            or acquisition.publisher_attested
            or acquisition.registry_validation_completed
            or acquisition.connector_registered
            or acquisition.connector_approved
            or acquisition.connector_installed
            or acquisition.connector_enabled
            or acquisition.target_configured
            or acquisition.credentials_resolved
            or acquisition.runtime_trust_granted
            or acquisition.execution_authorized
            or acquisition.deployment_approved
            or acquisition.infrastructure_mutation_performed
        ):
            raise PackageValidationError("package_validation_source_integrity_failed")

    @classmethod
    def _verify_archive(
        cls, acquisition: ConnectorPackageAcquisition, content: bytes
    ) -> tuple[dict[str, bytes], dict[str, Any]]:
        if (
            not content
            or len(content) != acquisition.package_size_bytes
            or len(content) > 25_000_000
            or sha256(content).hexdigest() != acquisition.package_digest
        ):
            raise PackageValidationError("package_validation_archive_integrity_failed")
        files: dict[str, bytes] = {}
        try:
            with zipfile.ZipFile(io.BytesIO(content), "r") as archive:
                infos = archive.infolist()
                names = [item.filename for item in infos]
                if (
                    not 3 <= len(infos) <= 500
                    or len(names) != len(set(names))
                    or names != sorted(names)
                    or MANIFEST_PATH not in names
                    or HANDOFF_PATH not in names
                    or any(not cls._safe_archive_entry(item) for item in infos)
                    or sum(item.file_size for item in infos) > 20_000_000
                ):
                    raise PackageValidationError("package_validation_archive_contract_failed")
                files = {item.filename: archive.read(item) for item in infos}
        except PackageValidationError:
            raise
        except (OSError, ValueError, zipfile.BadZipFile, KeyError) as error:
            raise PackageValidationError("package_validation_archive_integrity_failed") from error
        envelope = cls._strict_json(files[HANDOFF_PATH], 1_000_000)
        cls._verify_envelope(acquisition, envelope)
        return files, envelope

    @classmethod
    def _verify_envelope(
        cls, acquisition: ConnectorPackageAcquisition, envelope: dict[str, Any]
    ) -> None:
        expected_values: dict[str, object] = {
            "schema_version": "atlas.mcp-builder-candidate-handoff-envelope.v1",
            "project_id": acquisition.source_project_id,
            "domain_reviewed_by": acquisition.source_domain_reviewed_by,
            "security_reviewed_by": acquisition.source_security_reviewed_by,
            "lab_operated_by": acquisition.source_lab_operated_by,
            "organization_id": acquisition.organization_id,
            "environment_id": acquisition.environment_id,
            "custodied_by": acquisition.source_custodied_by,
            "archive_contract_version": acquisition.archive_contract_version,
            "state": "candidate_quarantined",
            "signature_state": "unsigned",
            "manual_change_count": 0,
            "package_signed": False,
            "connector_registered": False,
            "connector_installed": False,
            "connector_enabled": False,
            "runtime_trust_granted": False,
            "execution_authorized": False,
            "infrastructure_mutation_performed": False,
        }
        if set(envelope) != _HANDOFF_KEYS or any(
            envelope.get(key) != value for key, value in expected_values.items()
        ):
            raise PackageValidationError("package_validation_handoff_contract_failed")
        raw_capabilities = envelope.get("capabilities")
        if not isinstance(raw_capabilities, list) or len(raw_capabilities) != len(
            acquisition.capabilities
        ):
            raise PackageValidationError("package_validation_handoff_contract_failed")
        expected = {
            item.capability_id: (
                item.capability_class,
                item.required_permission,
                list(item.supported_product_versions),
            )
            for item in acquisition.capabilities
        }
        observed: dict[str, tuple[str, str, list[str]]] = {}
        for item in raw_capabilities:
            if not isinstance(item, dict) or set(item) != {
                "candidate_id",
                "capability_class",
                "required_permission",
                "supported_product_versions",
                "source_citations",
            }:
                raise PackageValidationError("package_validation_handoff_contract_failed")
            candidate_id = item.get("candidate_id")
            capability_class = item.get("capability_class")
            permission = item.get("required_permission")
            versions = item.get("supported_product_versions")
            citations = item.get("source_citations")
            if (
                not isinstance(candidate_id, str)
                or not isinstance(capability_class, str)
                or not isinstance(permission, str)
                or not cls._safe_string_list(versions, maximum_items=20, maximum_length=80)
                or not cls._safe_string_list(citations, maximum_items=50, maximum_length=500)
            ):
                raise PackageValidationError("package_validation_handoff_contract_failed")
            observed[candidate_id] = (capability_class, permission, versions)
        if observed != expected:
            raise PackageValidationError("package_validation_handoff_contract_failed")
        if not cls._safe_string_list(
            envelope.get("network_destinations"), maximum_items=100, maximum_length=500
        ):
            raise PackageValidationError("package_validation_handoff_contract_failed")

    @classmethod
    def _validate_manifest_and_schemas(
        cls,
        *,
        acquisition: ConnectorPackageAcquisition,
        files: dict[str, bytes],
        envelope: dict[str, Any],
    ) -> tuple[
        tuple[PackageValidationCheck, ...],
        str | None,
        tuple[ValidatedSchemaEvidence, ...],
    ]:
        manifest: dict[str, Any] | None = None
        manifest_digest: str | None = None
        manifest_valid = False
        raw_manifest = files.get(MANIFEST_PATH)
        if raw_manifest is not None:
            manifest_digest = sha256(raw_manifest).hexdigest()
            try:
                manifest = cls._strict_json(raw_manifest, 65_536)
                manifest_valid = cls._manifest_valid(acquisition, envelope, manifest, raw_manifest)
            except PackageValidationError:
                manifest = None

        schema_evidence: tuple[ValidatedSchemaEvidence, ...] = ()
        schemas_valid = False
        if manifest is not None:
            schema_evidence, schemas_valid = cls._validate_schemas(files, manifest)

        checks = (
            cls._check(
                "validation.source.accepted",
                True,
                "The immutable acquisition source and no-authority state are accepted.",
                (),
                "Reacquire the exact package through the approved source profile.",
            ),
            cls._check(
                "validation.archive.contract",
                True,
                "The exact archive, entry inventory, and handoff envelope satisfy the contract.",
                (HANDOFF_PATH,),
                "Restore the unchanged content-addressed archive from connector quarantine.",
            ),
            cls._check(
                "validation.manifest.contract",
                manifest_valid,
                "The connector manifest is canonical, bounded, source-bound, and quarantined.",
                (MANIFEST_PATH,) if raw_manifest is not None else (),
                (
                    "Restore the exact generated manifest contract without expanding "
                    "scope or authority."
                ),
            ),
            cls._check(
                "validation.schemas.contract",
                schemas_valid,
                "Configuration and capability schemas retain bounded generated-draft contracts.",
                tuple(item.relative_path for item in schema_evidence),
                "Restore the exact draft 2020-12 schema inventory and manifest property bindings.",
            ),
        )
        return checks, manifest_digest, schema_evidence

    @classmethod
    def _manifest_valid(
        cls,
        acquisition: ConnectorPackageAcquisition,
        envelope: dict[str, Any],
        manifest: dict[str, Any],
        raw_manifest: bytes,
    ) -> bool:
        if set(manifest) != _MANIFEST_KEYS or not cls._canonical_json_matches(
            raw_manifest, manifest
        ):
            return False
        connector_id = manifest.get("connector_id")
        if not isinstance(connector_id, str) or _SAFE_KEY.fullmatch(connector_id) is None:
            return False
        if (
            manifest.get("schema_version") != "atlas.connector-manifest.v1"
            or not isinstance(manifest.get("version"), str)
            or _SEMANTIC_DRAFT.fullmatch(manifest["version"]) is None
            or manifest.get("status") != "quarantined_generated_draft"
            or manifest.get("sdk_profile") != "atlas.python312.v1"
            or manifest.get("runtime_trust") is not False
            or manifest.get("execution_authorized") is not False
        ):
            return False
        products = manifest.get("target_products")
        destinations = manifest.get("network_destinations")
        configuration_keys = manifest.get("configuration_keys")
        secret_reference_ids = manifest.get("secret_reference_ids")
        if (
            not cls._safe_string_list(products, maximum_items=20, maximum_length=80)
            or not cls._safe_string_list(destinations, maximum_items=100, maximum_length=500)
            or not cls._safe_key_list(configuration_keys)
            or not cls._safe_key_list(secret_reference_ids)
            or set(configuration_keys) & set(secret_reference_ids)
            or destinations != envelope.get("network_destinations")
        ):
            return False
        supported_versions = [
            version
            for capability in acquisition.capabilities
            for version in capability.supported_product_versions
        ]
        if not all(
            any(version.casefold().startswith(product.casefold()) for product in products)
            for version in supported_versions
        ) or not all(
            any(version.casefold().startswith(product.casefold()) for version in supported_versions)
            for product in products
        ):
            return False
        raw_capabilities = manifest.get("capabilities")
        if not isinstance(raw_capabilities, list):
            return False
        expected = [
            {
                "id": item.capability_id,
                "class": item.capability_class,
                "permission": item.required_permission,
                "handler_status": "draft_fail_closed",
            }
            for item in sorted(acquisition.capabilities, key=lambda value: value.capability_id)
        ]
        return raw_capabilities == expected

    @classmethod
    def _validate_schemas(
        cls, files: dict[str, bytes], manifest: dict[str, Any]
    ) -> tuple[tuple[ValidatedSchemaEvidence, ...], bool]:
        raw_capabilities = manifest.get("capabilities")
        if not isinstance(raw_capabilities, list):
            return (), False
        raw_capability_ids = [item.get("id") for item in raw_capabilities if isinstance(item, dict)]
        if not cls._safe_string_list(raw_capability_ids, maximum_items=500, maximum_length=120):
            return (), False
        capability_ids = raw_capability_ids
        modules = [cls._module_name(item) for item in capability_ids]
        if len(modules) != len(set(modules)):
            return (), False
        expected_paths = {CONFIG_SCHEMA_PATH}
        for module in modules:
            expected_paths.add(f"schemas/inputs/{module}.schema.json")
            expected_paths.add(f"schemas/outputs/{module}.schema.json")
        observed_paths = {
            path for path in files if path.startswith("schemas/") and path.endswith(".json")
        }
        if observed_paths != expected_paths:
            return (), False

        evidence: list[ValidatedSchemaEvidence] = []
        valid = True
        configuration_keys = manifest.get("configuration_keys")
        secret_reference_ids = manifest.get("secret_reference_ids")
        for path in sorted(expected_paths):
            raw = files[path]
            try:
                value = cls._strict_json(raw, 65_536)
            except PackageValidationError:
                valid = False
                continue
            if not cls._canonical_json_matches(raw, value):
                valid = False
                continue
            if path == CONFIG_SCHEMA_PATH:
                schema_valid = cls._configuration_schema_valid(
                    value, configuration_keys, secret_reference_ids
                )
                purpose = ValidatedSchemaPurpose.CONFIGURATION
                capability_id = None
            else:
                index = modules.index(PurePosixPath(path).name.removesuffix(".schema.json"))
                capability_id = capability_ids[index]
                purpose = (
                    ValidatedSchemaPurpose.CAPABILITY_INPUT
                    if path.startswith("schemas/inputs/")
                    else ValidatedSchemaPurpose.CAPABILITY_OUTPUT
                )
                schema_valid = cls._capability_schema_valid(
                    value,
                    capability_id,
                    input_schema=purpose is ValidatedSchemaPurpose.CAPABILITY_INPUT,
                )
            if not schema_valid:
                valid = False
                continue
            schema_id = value.get("$id")
            if not isinstance(schema_id, str):
                valid = False
                continue
            evidence.append(
                ValidatedSchemaEvidence(
                    relative_path=path,
                    digest=sha256(raw).hexdigest(),
                    schema_id=schema_id,
                    purpose=purpose,
                    capability_id=capability_id,
                )
            )
        return tuple(evidence), valid and len(evidence) == len(expected_paths)

    @staticmethod
    def _configuration_schema_valid(
        value: dict[str, Any], configuration_keys: object, secret_reference_ids: object
    ) -> bool:
        if set(value) != {
            "$schema",
            "$id",
            "type",
            "additionalProperties",
            "properties",
            "required",
        }:
            return False
        if (
            value.get("$schema") != JSON_SCHEMA_DRAFT
            or value.get("$id") != "atlas://generated/config.schema.json"
            or value.get("type") != "object"
            or value.get("additionalProperties") is not False
            or not isinstance(value.get("properties"), dict)
            or not isinstance(configuration_keys, list)
            or not isinstance(secret_reference_ids, list)
            or value.get("required") != sorted((*configuration_keys, *secret_reference_ids))
            or set(value["properties"]) != set(configuration_keys) | set(secret_reference_ids)
        ):
            return False
        for key in configuration_keys:
            if value["properties"].get(key) != {
                "type": "string",
                "x-atlas-sensitive": False,
            }:
                return False
        for key in secret_reference_ids:
            if value["properties"].get(key) != {
                "type": "string",
                "format": "atlas-secret-reference",
                "x-atlas-secret-value": False,
            }:
                return False
        return True

    @staticmethod
    def _capability_schema_valid(
        value: dict[str, Any], capability_id: str, *, input_schema: bool
    ) -> bool:
        common = (
            value.get("$schema") == JSON_SCHEMA_DRAFT
            and value.get("type") == "object"
            and value.get("x-atlas-generation-status") == "draft_requires_schema_review"
        )
        if input_schema:
            return bool(
                common
                and set(value)
                == {
                    "$schema",
                    "$id",
                    "type",
                    "additionalProperties",
                    "properties",
                    "x-atlas-parameter-evidence-count",
                    "x-atlas-generation-status",
                }
                and value.get("$id") == f"atlas://generated/{capability_id}/input.schema.json"
                and value.get("additionalProperties") is False
                and value.get("properties") == {}
                and isinstance(value.get("x-atlas-parameter-evidence-count"), int)
                and 0 <= value["x-atlas-parameter-evidence-count"] <= 1000
            )
        codes = value.get("x-atlas-response-code-evidence")
        return bool(
            common
            and set(value)
            == {
                "$schema",
                "$id",
                "type",
                "additionalProperties",
                "x-atlas-response-code-evidence",
                "x-atlas-generation-status",
            }
            and value.get("$id") == f"atlas://generated/{capability_id}/output.schema.json"
            and value.get("additionalProperties") is True
            and PackageValidationService._safe_string_list(
                codes, maximum_items=100, maximum_length=20, allow_empty=True
            )
        )

    @staticmethod
    def _check(
        code: str,
        passed: bool,
        summary: str,
        evidence_paths: tuple[str, ...],
        remediation: str,
    ) -> PackageValidationCheck:
        return PackageValidationCheck(
            code=code,
            state=(
                PackageValidationCheckState.PASSED if passed else PackageValidationCheckState.FAILED
            ),
            severity=(
                PackageValidationSeverity.INFORMATIONAL
                if passed
                else PackageValidationSeverity.ERROR
            ),
            summary=summary,
            evidence_paths=evidence_paths,
            remediation=remediation,
        )

    @classmethod
    def _verify_validation(cls, validation: ConnectorPackageValidation) -> None:
        payload = {
            "lifecycle": validation.lifecycle.value,
            "outcome": validation.outcome.value,
            "source_acquisition_id": validation.source_acquisition_id,
            "source_acquisition_digest": validation.source_acquisition_digest,
            "source_handoff_id": validation.source_handoff_id,
            "source_handoff_digest": validation.source_handoff_digest,
            "source_project_id": validation.source_project_id,
            "source_acquired_by": validation.source_acquired_by,
            "source_custodied_by": validation.source_custodied_by,
            "source_domain_reviewed_by": validation.source_domain_reviewed_by,
            "source_security_reviewed_by": validation.source_security_reviewed_by,
            "source_lab_operated_by": validation.source_lab_operated_by,
            "organization_id": validation.organization_id,
            "environment_id": validation.environment_id,
            "validated_by": validation.validated_by,
            "validation_profile": validation.validation_profile,
            "validator_version": validation.validator_version,
            "package_digest": validation.package_digest,
            "package_size_bytes": validation.package_size_bytes,
            "manifest_path": validation.manifest_path,
            "manifest_digest": validation.manifest_digest,
            "capability_ids": validation.capability_ids,
            "schema_evidence": cls._schema_payload(validation.schema_evidence),
            "checks": cls._check_payload(validation.checks),
            "limitations": validation.limitations,
        }
        if cls._digest(payload) != validation.canonical_digest:
            raise PackageValidationError("package_validation_integrity_failed")

    @staticmethod
    def _strict_json(raw: bytes, maximum: int) -> dict[str, Any]:
        if not raw or len(raw) > maximum or b"\x00" in raw:
            raise PackageValidationError("package_validation_json_invalid")

        def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise _DuplicateJsonKey(key)
                result[key] = value
            return result

        try:
            value = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicates)
        except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateJsonKey) as error:
            raise PackageValidationError("package_validation_json_invalid") from error
        if not isinstance(value, dict):
            raise PackageValidationError("package_validation_json_invalid")
        return value

    @staticmethod
    def _canonical_json_matches(raw: bytes, value: object) -> bool:
        expected = (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode(
            "utf-8"
        )
        return raw == expected

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
    def _safe_string_list(
        value: object,
        *,
        maximum_items: int,
        maximum_length: int,
        allow_empty: bool = False,
    ) -> TypeGuard[list[str]]:
        return bool(
            isinstance(value, list)
            and (allow_empty or value)
            and len(value) <= maximum_items
            and len(value) == len(set(value))
            and all(
                isinstance(item, str) and item.strip() and len(item) <= maximum_length
                for item in value
            )
        )

    @staticmethod
    def _safe_key_list(value: object) -> TypeGuard[list[str]]:
        return bool(
            isinstance(value, list)
            and len(value) <= 100
            and len(value) == len(set(value))
            and all(isinstance(item, str) and _SAFE_KEY.fullmatch(item) for item in value)
        )

    @staticmethod
    def _module_name(capability_id: str) -> str:
        suffix = capability_id.rsplit(".", 1)[-1]
        return f"capability_{re.sub(r'[^a-z0-9_]', '_', suffix.lower())}"

    @staticmethod
    def _schema_payload(
        evidence: tuple[ValidatedSchemaEvidence, ...],
    ) -> list[dict[str, object]]:
        return [
            {
                "relative_path": item.relative_path,
                "digest": item.digest,
                "schema_id": item.schema_id,
                "purpose": item.purpose.value,
                "capability_id": item.capability_id,
            }
            for item in evidence
        ]

    @staticmethod
    def _check_payload(checks: tuple[PackageValidationCheck, ...]) -> list[dict[str, object]]:
        return [
            {
                "code": item.code,
                "state": item.state.value,
                "severity": item.severity.value,
                "summary": item.summary,
                "evidence_paths": item.evidence_paths,
                "remediation": item.remediation,
            }
            for item in checks
        ]

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
            raise PackageValidationError("package_validation_enterprise_human_mfa_required")

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise PackageValidationError("package_validation_not_found")

    @staticmethod
    def _require_separation(
        actor: AuthenticatedSubject, acquisition: ConnectorPackageAcquisition
    ) -> None:
        if actor.subject_id in {
            acquisition.acquired_by,
            acquisition.source_custodied_by,
            acquisition.source_domain_reviewed_by,
            acquisition.source_security_reviewed_by,
            acquisition.source_lab_operated_by,
        }:
            raise PackageValidationError("package_validation_not_found")

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        validation: ConnectorPackageValidation,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.package-validation",
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
                resource_type="resource.connector.package-validation",
                scope_reference=validation.validation_id,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=validation.idempotency_key,
                target_metadata=(
                    ("validation_id", validation.validation_id),
                    ("source_acquisition_id", validation.source_acquisition_id),
                    ("package_digest", validation.package_digest),
                    ("validation_outcome", validation.outcome.value),
                ),
            )
        )
