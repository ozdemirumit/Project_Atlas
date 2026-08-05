from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.connectors.application.acquisition import PackageAcquisitionService
from atlas.modules.connectors.application.content_policy_scan import (
    CONTENT_POLICY_PROFILE,
    CONTENT_POLICY_SCANNER,
    PackageContentPolicyScanService,
)
from atlas.modules.connectors.application.schema_semantics_validation_ports import (
    PackageSchemaSemanticsValidationError,
    PackageSchemaSemanticsValidationRepository,
    SchemaSemanticsAcquisitionSource,
    SchemaSemanticsArchiveSource,
    SchemaSemanticsContentPolicySource,
    SchemaSemanticsInventorySource,
)
from atlas.modules.connectors.application.supply_chain_inventory import (
    PackageSupplyChainInventoryService,
)
from atlas.modules.connectors.application.validation_intake import PackageValidationService
from atlas.modules.connectors.domain.acquisition import ConnectorPackageAcquisition
from atlas.modules.connectors.domain.content_policy_scan import (
    ConnectorPackageContentPolicyScan,
    ContentPolicyOutcome,
)
from atlas.modules.connectors.domain.schema_semantics_validation import (
    ConnectorPackageSchemaSemanticsValidation,
    SchemaPurpose,
    SchemaSemanticsCheck,
    SchemaSemanticsCheckState,
    SchemaSemanticsFinding,
    SchemaSemanticsFindingKind,
    SchemaSemanticsLifecycle,
    SchemaSemanticsOutcome,
    SchemaSemanticsSeverity,
    SchemaSemanticsSummary,
)
from atlas.modules.connectors.domain.supply_chain_inventory import (
    ConnectorPackageSupplyChainInventory,
    PackageContentClass,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

SCHEMA_SEMANTICS_CREATE_PERMISSION = "connectors.package-schema-semantics-validations.create"
SCHEMA_SEMANTICS_READ_PERMISSION = "connectors.package-schema-semantics-validations.read"
SCHEMA_SEMANTICS_SCHEMA = "atlas.connector-package-schema-semantics-validation.v1"
SCHEMA_SEMANTICS_PROFILE = "atlas.connector-schema-semantics.python312.v1"
SCHEMA_SEMANTICS_VALIDATOR = "atlas.connector-configuration-capability-schema-validator.v1"

SCHEMA_SEMANTICS_LIMITATIONS = (
    "This report proves only bounded configuration and capability schema semantics.",
    "Raw schema bodies, defaults, patterns, enum values, examples, and secret-like content are not "
    "retained.",
    "Implementation behavior, permissions, network access, risk, static code, contracts, runner, "
    "self-test, and lab validation remain incomplete.",
    "Rejection, registration, approval, installation, enablement, runtime trust, execution, and "
    "deployment remain prohibited.",
)

_CONFIG_PATH = "schemas/config/config.schema.json"
_JSON_SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"
_SAFE_KEY = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
_SUPPORTED_PROPERTY_KEYS = frozenset(
    {
        "type",
        "format",
        "enum",
        "default",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
        "items",
        "pattern",
        "x-atlas-sensitive",
        "x-atlas-secret-value",
    }
)
_UNSAFE_SCHEMA_KEYS = frozenset(
    {"$ref", "$dynamicRef", "$recursiveRef", "allOf", "anyOf", "oneOf", "not", "if", "then", "else"}
)


class PackageSchemaSemanticsValidationService:
    def __init__(
        self,
        *,
        repository: PackageSchemaSemanticsValidationRepository,
        content_policy_source: SchemaSemanticsContentPolicySource,
        inventory_source: SchemaSemanticsInventorySource,
        acquisition_source: SchemaSemanticsAcquisitionSource,
        archive_source: SchemaSemanticsArchiveSource,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._content_policy_source = content_policy_source
        self._inventory_source = inventory_source
        self._acquisition_source = acquisition_source
        self._archive_source = archive_source
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_content_policy_scan_id: str,
        source_content_policy_scan_digest: str,
        package_digest: str,
        validation_profile: str,
        acknowledged_untrusted_schema_content: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorPackageSchemaSemanticsValidation:
        self._require_enterprise_human(actor)
        if not acknowledged_untrusted_schema_content:
            raise PackageSchemaSemanticsValidationError(
                "package_schema_semantics_acknowledgement_required"
            )
        if validation_profile != SCHEMA_SEMANTICS_PROFILE:
            raise PackageSchemaSemanticsValidationError(
                "package_schema_semantics_profile_unsupported"
            )
        if not 8 <= len(idempotency_key) <= 128:
            raise PackageSchemaSemanticsValidationError(
                "package_schema_semantics_idempotency_key_invalid"
            )
        fingerprint = self._digest(
            {
                "source_content_policy_scan_id": source_content_policy_scan_id,
                "source_content_policy_scan_digest": source_content_policy_scan_digest,
                "package_digest": package_digest,
                "validation_profile": validation_profile,
                "acknowledged_untrusted_schema_content": True,
                "validated_by": actor.subject_id,
            }
        )
        replay = await self._repository.get_by_create_key(
            validated_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if replay is not None:
            self._verify_validation(replay)
            if replay.request_fingerprint == fingerprint:
                return replace(replay, reused=True)
            raise PackageSchemaSemanticsValidationError(
                "package_schema_semantics_idempotency_conflict"
            )

        source_scan = await self._content_policy_source.get_by_id(
            scan_id=source_content_policy_scan_id
        )
        if source_scan is None:
            raise PackageSchemaSemanticsValidationError("package_schema_semantics_source_not_found")
        self._require_scope(actor, source_scan.organization_id, source_scan.environment_id)
        self._require_separation(actor, source_scan)
        self._verify_source_scan(source_scan)
        if (
            source_scan.canonical_digest != source_content_policy_scan_digest
            or source_scan.package_digest != package_digest
        ):
            raise PackageSchemaSemanticsValidationError("package_schema_semantics_source_not_found")

        inventory = await self._inventory_source.get_by_id(
            inventory_id=source_scan.source_inventory_id
        )
        if inventory is None:
            raise PackageSchemaSemanticsValidationError(
                "package_schema_semantics_source_integrity_failed"
            )
        self._verify_inventory_binding(source_scan, inventory)
        acquisition = await self._acquisition_source.get_by_id(
            acquisition_id=inventory.source_acquisition_id
        )
        if acquisition is None:
            raise PackageSchemaSemanticsValidationError(
                "package_schema_semantics_source_integrity_failed"
            )
        self._verify_acquisition_binding(inventory, acquisition)
        try:
            content = await self._archive_source.read(
                package_digest=package_digest, size_bytes=inventory.package_size_bytes
            )
            files, _ = PackageValidationService._verify_archive(acquisition, content)
            self._verify_inventory_files(inventory, files)
        except PackageSchemaSemanticsValidationError:
            raise
        except Exception as error:
            raise PackageSchemaSemanticsValidationError(
                "package_schema_semantics_archive_integrity_failed"
            ) from error

        manifest = self._strict_object(files.get("atlas-connector.yaml"), "manifest")
        schemas, findings = self._validate_schemas(package_digest, files, manifest)
        config_findings = tuple(
            item for item in findings if item.kind is SchemaSemanticsFindingKind.CONFIGURATION
        )
        capability_findings = tuple(
            item for item in findings if item.kind is not SchemaSemanticsFindingKind.CONFIGURATION
        )
        checks = self._checks(
            config_findings=config_findings, capability_findings=capability_findings
        )
        outcome = (
            SchemaSemanticsOutcome.PASSED
            if all(item.state is SchemaSemanticsCheckState.PASSED for item in checks)
            else SchemaSemanticsOutcome.FAILED
        )
        schema_set_digest = self._digest(self._schema_payload(schemas))
        finding_set_digest = self._digest(self._finding_payload(findings))
        semantic_validation_digest = self._digest(
            {
                "validator_version": SCHEMA_SEMANTICS_VALIDATOR,
                "package_digest": package_digest,
                "schema_set_digest": schema_set_digest,
                "finding_set_digest": finding_set_digest,
            }
        )
        payload = self._canonical_payload(
            source_scan=source_scan,
            actor_id=actor.subject_id,
            validation_profile=validation_profile,
            schemas=schemas,
            schema_set_digest=schema_set_digest,
            findings=findings,
            finding_set_digest=finding_set_digest,
            semantic_validation_digest=semantic_validation_digest,
            checks=checks,
            outcome=outcome,
        )
        canonical_digest = self._digest(payload)
        validation = ConnectorPackageSchemaSemanticsValidation(
            validation_id=f"connector-schema-semantics-validation.{canonical_digest[:24]}",
            schema_version=SCHEMA_SEMANTICS_SCHEMA,
            version=1,
            lifecycle=SchemaSemanticsLifecycle.VALIDATING,
            outcome=outcome,
            source_content_policy_scan_id=source_scan.scan_id,
            source_content_policy_scan_digest=source_scan.canonical_digest,
            source_inventory_id=source_scan.source_inventory_id,
            source_inventory_digest=source_scan.source_inventory_digest,
            source_validation_id=source_scan.source_validation_id,
            source_validation_digest=source_scan.source_validation_digest,
            source_acquisition_id=source_scan.source_acquisition_id,
            source_acquisition_digest=source_scan.source_acquisition_digest,
            source_handoff_id=source_scan.source_handoff_id,
            source_project_id=source_scan.source_project_id,
            source_acquired_by=source_scan.source_acquired_by,
            source_manifest_validated_by=source_scan.source_validated_by,
            source_inventoried_by=source_scan.source_inventoried_by,
            source_content_scanned_by=source_scan.scanned_by,
            source_custodied_by=source_scan.source_custodied_by,
            source_domain_reviewed_by=source_scan.source_domain_reviewed_by,
            source_security_reviewed_by=source_scan.source_security_reviewed_by,
            source_lab_operated_by=source_scan.source_lab_operated_by,
            organization_id=source_scan.organization_id,
            environment_id=source_scan.environment_id,
            validated_by=actor.subject_id,
            validation_profile=validation_profile,
            validator_version=SCHEMA_SEMANTICS_VALIDATOR,
            package_digest=source_scan.package_digest,
            package_size_bytes=source_scan.package_size_bytes,
            inventory_digest=source_scan.inventory_digest,
            content_scan_digest=source_scan.content_scan_digest,
            schemas=schemas,
            schema_set_digest=schema_set_digest,
            findings=findings,
            finding_set_digest=finding_set_digest,
            semantic_validation_digest=semantic_validation_digest,
            checks=checks,
            limitations=SCHEMA_SEMANTICS_LIMITATIONS,
            promotion_blocked=outcome is SchemaSemanticsOutcome.FAILED,
            canonical_digest=canonical_digest,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            validated_at=self._clock(),
        )
        async with self._mutation_lock:
            existing = await self._repository.get_by_source_scan(
                source_content_policy_scan_id=source_content_policy_scan_id
            )
            if existing is not None:
                self._verify_validation(existing)
                if (
                    existing.validated_by == actor.subject_id
                    and existing.idempotency_key == idempotency_key
                    and existing.request_fingerprint == fingerprint
                ):
                    return replace(existing, reused=True)
                raise PackageSchemaSemanticsValidationError("package_schema_semantics_exists")
            await self._audit(
                actor=actor,
                correlation_id=correlation_id,
                permission_id=SCHEMA_SEMANTICS_CREATE_PERMISSION,
                result_code=f"connector_schema_semantics_validation_{outcome.value}",
                validation=validation,
            )
            if not await self._repository.add(validation):
                raced = await self._repository.get_by_create_key(
                    validated_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    raise PackageSchemaSemanticsValidationError("package_schema_semantics_conflict")
                self._verify_validation(raced)
                return replace(raced, reused=True)
        return validation

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        validation_id: str,
        correlation_id: str,
    ) -> ConnectorPackageSchemaSemanticsValidation:
        self._require_enterprise_human(actor)
        validation = await self._repository.get_by_id(validation_id=validation_id)
        if validation is None:
            raise PackageSchemaSemanticsValidationError("package_schema_semantics_not_found")
        self._require_scope(actor, validation.organization_id, validation.environment_id)
        if actor.subject_id in self._validation_source_actors(validation):
            raise PackageSchemaSemanticsValidationError("package_schema_semantics_not_found")
        self._verify_validation(validation)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=SCHEMA_SEMANTICS_READ_PERMISSION,
            result_code="connector_schema_semantics_validation_read",
            validation=validation,
        )
        return validation

    async def close(self) -> None:
        await self._repository.close()

    @staticmethod
    def _strict_object(raw: bytes | None, label: str) -> dict[str, Any]:
        if raw is None or len(raw) > 65_536:
            raise PackageSchemaSemanticsValidationError(f"package_schema_semantics_{label}_invalid")

        def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate key")
                result[key] = value
            return result

        try:
            value = json.loads(
                raw.decode("utf-8", errors="strict"), object_pairs_hook=reject_duplicates
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            raise PackageSchemaSemanticsValidationError(
                f"package_schema_semantics_{label}_invalid"
            ) from error
        if not isinstance(value, dict):
            raise PackageSchemaSemanticsValidationError(f"package_schema_semantics_{label}_invalid")
        return value

    @classmethod
    def _validate_schemas(
        cls, package_digest: str, files: dict[str, bytes], manifest: dict[str, Any]
    ) -> tuple[tuple[SchemaSemanticsSummary, ...], tuple[SchemaSemanticsFinding, ...]]:
        capabilities = manifest.get("capabilities")
        if not isinstance(capabilities, list):
            raise PackageSchemaSemanticsValidationError("package_schema_semantics_manifest_invalid")
        capability_ids_list: list[str] = []
        for item in capabilities:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            capability_ids_list.append(item["id"])
        capability_ids = tuple(capability_ids_list)
        if len(capability_ids) != len(capabilities):
            raise PackageSchemaSemanticsValidationError("package_schema_semantics_manifest_invalid")
        modules = tuple(PackageValidationService._module_name(item) for item in capability_ids)
        paths: list[tuple[str, SchemaPurpose, str | None]] = [
            (_CONFIG_PATH, SchemaPurpose.CONFIGURATION, None)
        ]
        for capability_id, module in zip(capability_ids, modules, strict=True):
            paths.extend(
                (
                    (
                        f"schemas/inputs/{module}.schema.json",
                        SchemaPurpose.CAPABILITY_INPUT,
                        capability_id,
                    ),
                    (
                        f"schemas/outputs/{module}.schema.json",
                        SchemaPurpose.CAPABILITY_OUTPUT,
                        capability_id,
                    ),
                )
            )
        summaries: list[SchemaSemanticsSummary] = []
        findings: list[SchemaSemanticsFinding] = []
        for path, purpose, bound_capability_id in sorted(paths):
            raw = files.get(path)
            schema = cls._strict_object(raw, "schema")
            schema_findings = cls._schema_findings(
                package_digest, path, purpose, bound_capability_id, schema, manifest
            )
            properties = schema.get("properties")
            required = schema.get("required")
            summaries.append(
                SchemaSemanticsSummary(
                    relative_path=path,
                    digest=sha256(raw or b"").hexdigest(),
                    purpose=purpose,
                    capability_id=bound_capability_id,
                    property_count=len(properties) if isinstance(properties, dict) else 0,
                    required_count=len(required) if isinstance(required, list) else 0,
                    closed_object=schema.get("additionalProperties") is False,
                    semantically_complete=not schema_findings,
                )
            )
            findings.extend(schema_findings)
        return tuple(sorted(summaries, key=lambda item: item.relative_path)), tuple(
            sorted(
                findings, key=lambda item: (item.relative_path, item.json_pointer, item.rule_code)
            )
        )

    @classmethod
    def _schema_findings(
        cls,
        package_digest: str,
        path: str,
        purpose: SchemaPurpose,
        capability_id: str | None,
        schema: dict[str, Any],
        manifest: dict[str, Any],
    ) -> list[SchemaSemanticsFinding]:
        kind = SchemaSemanticsFindingKind(purpose.value)
        findings: list[SchemaSemanticsFinding] = []

        def add(rule: str, pointer: str, summary: str, remediation: str) -> None:
            findings.append(
                cls._finding(package_digest, path, pointer, rule, kind, summary, remediation)
            )

        if schema.get("$schema") != _JSON_SCHEMA_DRAFT or schema.get("type") != "object":
            add(
                "schema.root.invalid",
                "",
                "Schema root is not the supported JSON Schema object contract.",
                "Use the approved JSON Schema 2020-12 object profile.",
            )
        if any(key in schema for key in _UNSAFE_SCHEMA_KEYS):
            add(
                "schema.composition.unsupported",
                "",
                "Schema uses unsupported reference or composition behavior.",
                "Replace references and composition with explicit bounded properties.",
            )
        if schema.get("additionalProperties") is not False:
            add(
                "schema.object.open",
                "/additionalProperties",
                "Schema permits undeclared object properties.",
                "Set additionalProperties to false and declare every field.",
            )
        properties = schema.get("properties")
        if not isinstance(properties, dict) or len(properties) > 500:
            add(
                "schema.properties.invalid",
                "/properties",
                "Schema properties are missing or exceed the bounded profile.",
                "Declare a bounded properties object.",
            )
            properties = {}
        required = schema.get("required", [])
        if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
            add(
                "schema.required.invalid",
                "/required",
                "Required fields are malformed.",
                "Use a unique list of declared property names.",
            )
            required = []
        elif len(required) != len(set(required)) or not set(required).issubset(properties):
            add(
                "schema.required.inconsistent",
                "/required",
                "Required fields are duplicated or undeclared.",
                "Bind required fields exactly to declared properties.",
            )
        if purpose is not SchemaPurpose.CONFIGURATION and not properties:
            add(
                "schema.capability.placeholder",
                "/properties",
                "Capability schema is an empty placeholder.",
                "Define the reviewed typed capability contract.",
            )
        if (
            purpose is not SchemaPurpose.CONFIGURATION
            and schema.get("x-atlas-generation-status") != "reviewed"
        ):
            add(
                "schema.review.unresolved",
                "/x-atlas-generation-status",
                "Schema review remains unresolved.",
                "Set the marker to reviewed only after independent contract review.",
            )
        if purpose is SchemaPurpose.CONFIGURATION:
            expected = set(manifest.get("configuration_keys", [])) | set(
                manifest.get("secret_reference_ids", [])
            )
            if set(properties) != expected:
                add(
                    "schema.configuration.binding",
                    "/properties",
                    "Configuration fields do not exactly match the manifest.",
                    "Declare every manifest configuration and secret-reference field exactly once.",
                )
        for name, definition in sorted(properties.items()):
            pointer = f"/properties/{name.replace('~', '~0').replace('/', '~1')}"
            if _SAFE_KEY.fullmatch(name) is None or not isinstance(definition, dict):
                add(
                    "schema.property.invalid",
                    pointer,
                    "Property name or definition is invalid.",
                    "Use a safely named property with an explicit object definition.",
                )
                continue
            if set(definition) - _SUPPORTED_PROPERTY_KEYS or any(
                key in definition for key in _UNSAFE_SCHEMA_KEYS
            ):
                add(
                    "schema.property.keyword",
                    pointer,
                    "Property uses unsupported or ambiguous keywords.",
                    "Use only the approved bounded property keyword subset.",
                )
            cls._validate_property(add, pointer, name, definition, purpose, manifest)
        return findings

    @staticmethod
    def _validate_property(
        add: Callable[[str, str, str, str], None],
        pointer: str,
        name: str,
        definition: dict[str, Any],
        purpose: SchemaPurpose,
        manifest: dict[str, Any],
    ) -> None:
        value_type = definition.get("type")
        if value_type not in {"string", "integer", "number", "boolean", "array"}:
            add(
                "schema.property.type",
                pointer,
                "Property type is unsupported or missing.",
                "Declare one supported scalar or bounded array type.",
            )
            return
        secret_ids = set(manifest.get("secret_reference_ids", []))
        is_secret = purpose is SchemaPurpose.CONFIGURATION and name in secret_ids
        if is_secret:
            if definition != {
                "type": "string",
                "format": "atlas-secret-reference",
                "x-atlas-secret-value": False,
            }:
                add(
                    "schema.secret-reference.invalid",
                    pointer,
                    "Secret field is not an exact opaque secret reference.",
                    "Use only the atlas-secret-reference contract without defaults or literals.",
                )
            return
        if (
            definition.get("x-atlas-secret-value") is True
            or definition.get("x-atlas-sensitive") is True
        ):
            add(
                "schema.secret.literal",
                pointer,
                "Ordinary schema field is marked to carry sensitive content.",
                "Use a manifest-bound opaque secret-reference field.",
            )
        if "default" in definition and purpose is SchemaPurpose.CONFIGURATION:
            add(
                "schema.configuration.default",
                pointer,
                "Configuration defaults are not retained in the governed package profile.",
                "Provide defaults through reviewed non-secret environment policy.",
            )
        if value_type == "string" and not (
            isinstance(definition.get("minLength"), int)
            and 0 <= definition["minLength"] <= 10_000
            and isinstance(definition.get("maxLength"), int)
            and definition["minLength"] <= definition["maxLength"] <= 10_000
        ):
            add(
                "schema.string.unbounded",
                pointer,
                "String property has no coherent bounded length.",
                "Set coherent minLength and maxLength within the approved profile.",
            )
        if value_type in {"integer", "number"} and not (
            isinstance(definition.get("minimum"), (int, float))
            and isinstance(definition.get("maximum"), (int, float))
            and definition["minimum"] <= definition["maximum"]
        ):
            add(
                "schema.number.unbounded",
                pointer,
                "Numeric property has no coherent range.",
                "Set coherent minimum and maximum bounds.",
            )
        if value_type == "array" and not (
            isinstance(definition.get("minItems"), int)
            and isinstance(definition.get("maxItems"), int)
            and 0 <= definition["minItems"] <= definition["maxItems"] <= 1000
            and isinstance(definition.get("items"), dict)
        ):
            add(
                "schema.array.unbounded",
                pointer,
                "Array property has no coherent item contract and bounds.",
                "Set bounded minItems, maxItems, and an approved item schema.",
            )

    @staticmethod
    def _finding(
        package_digest: str,
        path: str,
        pointer: str,
        rule_code: str,
        kind: SchemaSemanticsFindingKind,
        summary: str,
        remediation: str,
    ) -> SchemaSemanticsFinding:
        fingerprint = sha256(
            b"atlas-schema-semantics-v1\0"
            + package_digest.encode("ascii")
            + b"\0"
            + path.encode("utf-8")
            + b"\0"
            + pointer.encode("utf-8")
            + b"\0"
            + rule_code.encode("ascii")
        ).hexdigest()
        return SchemaSemanticsFinding(
            rule_code=rule_code,
            kind=kind,
            severity=SchemaSemanticsSeverity.ERROR,
            relative_path=path,
            json_pointer=pointer,
            evidence_fingerprint=fingerprint,
            summary=summary,
            remediation=remediation,
        )

    @classmethod
    def _checks(
        cls,
        *,
        config_findings: tuple[SchemaSemanticsFinding, ...],
        capability_findings: tuple[SchemaSemanticsFinding, ...],
    ) -> tuple[SchemaSemanticsCheck, ...]:
        return (
            cls._check(
                "schema-semantics.source.accepted",
                True,
                "Exact passed content-policy evidence accepted.",
                (),
                "Restore exact passed content-policy evidence.",
            ),
            cls._check(
                "schema-semantics.archive.contract",
                True,
                "Exact acquired archive contract accepted.",
                (),
                "Restore exact acquired archive bytes.",
            ),
            cls._check(
                "schema-semantics.inventory.contract",
                True,
                "Schema bytes match the exact passed inventory.",
                (),
                "Restore exact schema path, digest, size, and class bindings.",
            ),
            cls._check(
                "schema-semantics.configuration.contract",
                not config_findings,
                "Configuration schema satisfies the bounded semantic profile.",
                tuple(sorted({item.relative_path for item in config_findings})),
                "Resolve every configuration semantic finding.",
            ),
            cls._check(
                "schema-semantics.capability.contracts",
                not capability_findings,
                "Capability input and output schemas satisfy the bounded semantic profile.",
                tuple(sorted({item.relative_path for item in capability_findings})),
                "Resolve every capability semantic finding.",
            ),
        )

    @staticmethod
    def _check(
        code: str, passed: bool, summary: str, evidence_paths: tuple[str, ...], remediation: str
    ) -> SchemaSemanticsCheck:
        return SchemaSemanticsCheck(
            code=code,
            state=SchemaSemanticsCheckState.PASSED if passed else SchemaSemanticsCheckState.FAILED,
            severity=SchemaSemanticsSeverity.INFORMATIONAL
            if passed
            else SchemaSemanticsSeverity.ERROR,
            summary=summary,
            evidence_paths=evidence_paths,
            remediation=remediation,
        )

    @classmethod
    def _canonical_payload(
        cls,
        *,
        source_scan: ConnectorPackageContentPolicyScan,
        actor_id: str,
        validation_profile: str,
        schemas: tuple[SchemaSemanticsSummary, ...],
        schema_set_digest: str,
        findings: tuple[SchemaSemanticsFinding, ...],
        finding_set_digest: str,
        semantic_validation_digest: str,
        checks: tuple[SchemaSemanticsCheck, ...],
        outcome: SchemaSemanticsOutcome,
    ) -> dict[str, object]:
        return {
            "lifecycle": SchemaSemanticsLifecycle.VALIDATING.value,
            "outcome": outcome.value,
            "source_content_policy_scan_id": source_scan.scan_id,
            "source_content_policy_scan_digest": source_scan.canonical_digest,
            "source_inventory_id": source_scan.source_inventory_id,
            "source_inventory_digest": source_scan.source_inventory_digest,
            "source_validation_id": source_scan.source_validation_id,
            "source_validation_digest": source_scan.source_validation_digest,
            "source_acquisition_id": source_scan.source_acquisition_id,
            "source_acquisition_digest": source_scan.source_acquisition_digest,
            "source_handoff_id": source_scan.source_handoff_id,
            "source_project_id": source_scan.source_project_id,
            "source_acquired_by": source_scan.source_acquired_by,
            "source_manifest_validated_by": source_scan.source_validated_by,
            "source_inventoried_by": source_scan.source_inventoried_by,
            "source_content_scanned_by": source_scan.scanned_by,
            "source_custodied_by": source_scan.source_custodied_by,
            "source_domain_reviewed_by": source_scan.source_domain_reviewed_by,
            "source_security_reviewed_by": source_scan.source_security_reviewed_by,
            "source_lab_operated_by": source_scan.source_lab_operated_by,
            "organization_id": source_scan.organization_id,
            "environment_id": source_scan.environment_id,
            "validated_by": actor_id,
            "validation_profile": validation_profile,
            "validator_version": SCHEMA_SEMANTICS_VALIDATOR,
            "package_digest": source_scan.package_digest,
            "package_size_bytes": source_scan.package_size_bytes,
            "inventory_digest": source_scan.inventory_digest,
            "content_scan_digest": source_scan.content_scan_digest,
            "schemas": cls._schema_payload(schemas),
            "schema_set_digest": schema_set_digest,
            "findings": cls._finding_payload(findings),
            "finding_set_digest": finding_set_digest,
            "semantic_validation_digest": semantic_validation_digest,
            "checks": cls._check_payload(checks),
            "limitations": SCHEMA_SEMANTICS_LIMITATIONS,
            "promotion_blocked": outcome is SchemaSemanticsOutcome.FAILED,
        }

    @classmethod
    def _verify_validation(cls, validation: ConnectorPackageSchemaSemanticsValidation) -> None:
        payload = {
            key: value for key, value in cls._canonical_payload_from_validation(validation).items()
        }
        if cls._digest(payload) != validation.canonical_digest:
            raise PackageSchemaSemanticsValidationError("package_schema_semantics_integrity_failed")

    @classmethod
    def _canonical_payload_from_validation(
        cls, validation: ConnectorPackageSchemaSemanticsValidation
    ) -> dict[str, object]:
        return {
            "lifecycle": validation.lifecycle.value,
            "outcome": validation.outcome.value,
            "source_content_policy_scan_id": validation.source_content_policy_scan_id,
            "source_content_policy_scan_digest": validation.source_content_policy_scan_digest,
            "source_inventory_id": validation.source_inventory_id,
            "source_inventory_digest": validation.source_inventory_digest,
            "source_validation_id": validation.source_validation_id,
            "source_validation_digest": validation.source_validation_digest,
            "source_acquisition_id": validation.source_acquisition_id,
            "source_acquisition_digest": validation.source_acquisition_digest,
            "source_handoff_id": validation.source_handoff_id,
            "source_project_id": validation.source_project_id,
            "source_acquired_by": validation.source_acquired_by,
            "source_manifest_validated_by": validation.source_manifest_validated_by,
            "source_inventoried_by": validation.source_inventoried_by,
            "source_content_scanned_by": validation.source_content_scanned_by,
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
            "inventory_digest": validation.inventory_digest,
            "content_scan_digest": validation.content_scan_digest,
            "schemas": cls._schema_payload(validation.schemas),
            "schema_set_digest": validation.schema_set_digest,
            "findings": cls._finding_payload(validation.findings),
            "finding_set_digest": validation.finding_set_digest,
            "semantic_validation_digest": validation.semantic_validation_digest,
            "checks": cls._check_payload(validation.checks),
            "limitations": validation.limitations,
            "promotion_blocked": validation.promotion_blocked,
        }

    @staticmethod
    def _schema_payload(schemas: tuple[SchemaSemanticsSummary, ...]) -> list[dict[str, object]]:
        return [
            {
                "relative_path": item.relative_path,
                "digest": item.digest,
                "purpose": item.purpose.value,
                "capability_id": item.capability_id,
                "property_count": item.property_count,
                "required_count": item.required_count,
                "closed_object": item.closed_object,
                "semantically_complete": item.semantically_complete,
            }
            for item in schemas
        ]

    @staticmethod
    def _finding_payload(findings: tuple[SchemaSemanticsFinding, ...]) -> list[dict[str, object]]:
        return [
            {
                "rule_code": item.rule_code,
                "kind": item.kind.value,
                "severity": item.severity.value,
                "relative_path": item.relative_path,
                "json_pointer": item.json_pointer,
                "evidence_fingerprint": item.evidence_fingerprint,
                "summary": item.summary,
                "remediation": item.remediation,
            }
            for item in findings
        ]

    @staticmethod
    def _check_payload(checks: tuple[SchemaSemanticsCheck, ...]) -> list[dict[str, object]]:
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
    def _verify_source_scan(scan: ConnectorPackageContentPolicyScan) -> None:
        try:
            PackageContentPolicyScanService._verify_scan(scan)
        except Exception as error:
            raise PackageSchemaSemanticsValidationError(
                "package_schema_semantics_source_integrity_failed"
            ) from error
        if (
            scan.outcome is not ContentPolicyOutcome.PASSED
            or scan.promotion_blocked
            or scan.scan_profile != CONTENT_POLICY_PROFILE
            or scan.scanner_version != CONTENT_POLICY_SCANNER
            or not scan.secret_content_scan_completed
            or not scan.prohibited_content_scan_completed
            or scan.schema_semantic_validation_completed
            or scan.connector_rejected
            or scan.connector_registered
            or scan.runtime_trust_granted
            or scan.execution_authorized
            or scan.infrastructure_mutation_performed
        ):
            raise PackageSchemaSemanticsValidationError(
                "package_schema_semantics_source_unsupported"
            )

    @staticmethod
    def _verify_inventory_binding(
        scan: ConnectorPackageContentPolicyScan, inventory: ConnectorPackageSupplyChainInventory
    ) -> None:
        try:
            PackageSupplyChainInventoryService._verify_inventory(inventory)
        except Exception as error:
            raise PackageSchemaSemanticsValidationError(
                "package_schema_semantics_source_integrity_failed"
            ) from error
        if (
            inventory.inventory_id != scan.source_inventory_id
            or inventory.canonical_digest != scan.source_inventory_digest
            or inventory.package_digest != scan.package_digest
            or inventory.package_size_bytes != scan.package_size_bytes
            or inventory.inventory_digest != scan.inventory_digest
            or inventory.organization_id != scan.organization_id
            or inventory.environment_id != scan.environment_id
        ):
            raise PackageSchemaSemanticsValidationError(
                "package_schema_semantics_source_integrity_failed"
            )

    @staticmethod
    def _verify_acquisition_binding(
        inventory: ConnectorPackageSupplyChainInventory, acquisition: ConnectorPackageAcquisition
    ) -> None:
        try:
            PackageAcquisitionService._verify_acquisition(acquisition)
        except Exception as error:
            raise PackageSchemaSemanticsValidationError(
                "package_schema_semantics_source_integrity_failed"
            ) from error
        if (
            acquisition.acquisition_id != inventory.source_acquisition_id
            or acquisition.canonical_digest != inventory.source_acquisition_digest
            or acquisition.package_digest != inventory.package_digest
            or acquisition.package_size_bytes != inventory.package_size_bytes
            or acquisition.organization_id != inventory.organization_id
            or acquisition.environment_id != inventory.environment_id
        ):
            raise PackageSchemaSemanticsValidationError(
                "package_schema_semantics_source_integrity_failed"
            )

    @staticmethod
    def _verify_inventory_files(
        inventory: ConnectorPackageSupplyChainInventory, files: dict[str, bytes]
    ) -> None:
        actual = tuple(
            (
                path,
                sha256(raw).hexdigest(),
                len(raw),
                PackageSupplyChainInventoryService._classify(path),
            )
            for path, raw in sorted(files.items())
        )
        expected = tuple(
            (item.relative_path, item.digest, item.size_bytes, item.content_class)
            for item in inventory.files
        )
        schema_items = tuple(
            item
            for item in inventory.files
            if item.content_class
            in {PackageContentClass.CONFIGURATION_SCHEMA, PackageContentClass.CAPABILITY_SCHEMA}
        )
        if actual != expected or not schema_items:
            raise PackageSchemaSemanticsValidationError(
                "package_schema_semantics_inventory_mismatch"
            )

    @staticmethod
    def _digest(payload: object) -> str:
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
        return sha256(encoded).hexdigest()

    @staticmethod
    def _require_enterprise_human(actor: AuthenticatedSubject) -> None:
        if (
            actor.kind is not SubjectKind.HUMAN
            or actor.authentication_method is AuthenticationMethod.DEVELOPMENT
            or actor.assurance_level
            not in {AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED}
        ):
            raise PackageSchemaSemanticsValidationError(
                "package_schema_semantics_enterprise_human_mfa_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise PackageSchemaSemanticsValidationError("package_schema_semantics_not_found")

    @classmethod
    def _require_separation(
        cls, actor: AuthenticatedSubject, scan: ConnectorPackageContentPolicyScan
    ) -> None:
        if actor.subject_id in cls._scan_source_actors(scan) | {scan.scanned_by}:
            raise PackageSchemaSemanticsValidationError("package_schema_semantics_not_found")

    @staticmethod
    def _scan_source_actors(scan: ConnectorPackageContentPolicyScan) -> set[str]:
        return {
            scan.source_acquired_by,
            scan.source_validated_by,
            scan.source_inventoried_by,
            scan.source_custodied_by,
            scan.source_domain_reviewed_by,
            scan.source_security_reviewed_by,
            scan.source_lab_operated_by,
        }

    @staticmethod
    def _validation_source_actors(
        validation: ConnectorPackageSchemaSemanticsValidation,
    ) -> set[str]:
        return {
            validation.source_acquired_by,
            validation.source_manifest_validated_by,
            validation.source_inventoried_by,
            validation.source_content_scanned_by,
            validation.source_custodied_by,
            validation.source_domain_reviewed_by,
            validation.source_security_reviewed_by,
            validation.source_lab_operated_by,
        }

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        validation: ConnectorPackageSchemaSemanticsValidation,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.package-schema-semantics-validation",
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
                resource_type="resource.connector.package-schema-semantics-validation",
                scope_reference=validation.validation_id,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=validation.idempotency_key,
                target_metadata=(
                    ("validation_id", validation.validation_id),
                    ("source_content_policy_scan_id", validation.source_content_policy_scan_id),
                    ("package_digest", validation.package_digest),
                    ("validation_outcome", validation.outcome.value),
                    ("finding_count", str(len(validation.findings))),
                ),
            )
        )
