from __future__ import annotations

import ast
import asyncio
import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from enum import Enum
from hashlib import sha256
from pathlib import PurePosixPath
from typing import cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.connectors.application.acquisition import PackageAcquisitionService
from atlas.modules.connectors.application.contract_validation_ports import (
    ContractAcquisitionSource,
    ContractArchiveSource,
    ContractInventorySource,
    ContractLicenseSource,
    PackageContractValidationError,
    PackageContractValidationRepository,
)
from atlas.modules.connectors.application.license_analysis import PackageLicenseAnalysisService
from atlas.modules.connectors.application.static_dependency_analysis import (
    PackageStaticDependencyAnalysisService,
)
from atlas.modules.connectors.application.supply_chain_inventory import (
    PackageSupplyChainInventoryService,
)
from atlas.modules.connectors.application.validation_intake import PackageValidationService
from atlas.modules.connectors.domain.acquisition import ConnectorPackageAcquisition
from atlas.modules.connectors.domain.contract_validation import (
    CONTRACT_CHECK_CODES,
    ConnectorPackageContractValidation,
    ContractArtifactScope,
    ContractCheck,
    ContractCheckSeverity,
    ContractCheckState,
    ContractCoverageSummary,
    ContractFinding,
    ContractLifecycle,
    ContractOutcome,
    ContractSeverity,
)
from atlas.modules.connectors.domain.license_analysis import (
    ConnectorPackageLicenseAnalysis,
    LicenseOutcome,
)
from atlas.modules.connectors.domain.supply_chain_inventory import (
    ConnectorPackageSupplyChainInventory,
    InventoryOutcome,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

CONTRACT_VALIDATION_CREATE_PERMISSION = "connectors.package-contract-validations.create"
CONTRACT_VALIDATION_READ_PERMISSION = "connectors.package-contract-validations.read"
CONTRACT_VALIDATION_SCHEMA = "atlas.connector-package-contract-validation.v1"
CONTRACT_VALIDATION_PROFILE = "atlas.connector-contract.python312.v1"
CONTRACT_VALIDATOR = "atlas.connector-contract-validator.v1"

CONTRACT_LIMITATIONS = (
    "This report proves static consistency of one exact quarantined generated-draft package only.",
    "Package source, tests, fixtures, schemas, paths, capability identities, permissions, and "
    "parser diagnostics are not retained.",
    "No package content was imported, compiled, built, installed, or executed.",
    "A passed result does not prove handler success, mock realism, vendor behavior, target "
    "compatibility, or execution safety.",
    "Runner, self-test, lab, final approval, registration, installation, enablement, "
    "runtime trust, execution, and deployment remain prohibited.",
)

_MANIFEST_PATH = "atlas-connector.yaml"
_CONFIG_PATH = "schemas/config/config.schema.json"
_CONTRACT_TEST_PATH = "tests/contract/test_quarantine_contract.py"
_FIXTURE_PATH = "tests/fixtures/synthetic-empty.json"


class PackageContractValidationService:
    def __init__(
        self,
        *,
        repository: PackageContractValidationRepository,
        license_source: ContractLicenseSource,
        inventory_source: ContractInventorySource,
        acquisition_source: ContractAcquisitionSource,
        archive_source: ContractArchiveSource,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._license_source = license_source
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
        source_license_analysis_id: str,
        source_license_analysis_digest: str,
        package_digest: str,
        validation_profile: str,
        acknowledged_static_contract_only: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorPackageContractValidation:
        self._require_enterprise_human(actor)
        if not acknowledged_static_contract_only:
            raise PackageContractValidationError("package_contract_acknowledgement_required")
        if validation_profile != CONTRACT_VALIDATION_PROFILE:
            raise PackageContractValidationError("package_contract_profile_unsupported")
        if not 8 <= len(idempotency_key) <= 128:
            raise PackageContractValidationError("package_contract_idempotency_key_invalid")
        fingerprint = self._digest(
            {
                "source_license_analysis_id": source_license_analysis_id,
                "source_license_analysis_digest": source_license_analysis_digest,
                "package_digest": package_digest,
                "validation_profile": validation_profile,
                "acknowledged_static_contract_only": True,
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
            raise PackageContractValidationError("package_contract_idempotency_conflict")

        source = await self._license_source.get_by_id(analysis_id=source_license_analysis_id)
        if source is None:
            raise PackageContractValidationError("package_contract_source_not_found")
        self._require_scope(actor, source.organization_id, source.environment_id)
        self._require_separation(actor, source)
        self._verify_source(source)
        if (
            source.canonical_digest != source_license_analysis_digest
            or source.package_digest != package_digest
        ):
            raise PackageContractValidationError("package_contract_source_not_found")

        inventory = await self._inventory_source.get_by_id(inventory_id=source.source_inventory_id)
        if inventory is None:
            raise PackageContractValidationError("package_contract_source_integrity_failed")
        self._verify_inventory_binding(source, inventory)
        acquisition = await self._acquisition_source.get_by_id(
            acquisition_id=source.source_acquisition_id
        )
        if acquisition is None:
            raise PackageContractValidationError("package_contract_source_integrity_failed")
        self._verify_acquisition_binding(source, acquisition)
        try:
            content = await self._archive_source.read(
                package_digest=package_digest, size_bytes=source.package_size_bytes
            )
            files, _ = PackageValidationService._verify_archive(acquisition, content)
            PackageStaticDependencyAnalysisService._verify_inventory_files(inventory, files)
        except Exception as error:
            raise PackageContractValidationError(
                "package_contract_archive_integrity_failed"
            ) from error

        coverage, findings, family_results = self._analyze(files)
        checks = self._checks(family_results)
        outcome = (
            ContractOutcome.PASSED
            if all(item.state is ContractCheckState.PASSED for item in checks)
            else ContractOutcome.FAILED
        )
        finding_set_digest = self._digest(self._finding_payload(findings))
        validation_digest = self._digest(
            {
                "validator_version": CONTRACT_VALIDATOR,
                "package_digest": source.package_digest,
                "inventory_digest": inventory.inventory_digest,
                "contract_set_digest": coverage.contract_set_digest,
                "finding_set_digest": finding_set_digest,
                "outcome": outcome.value,
            }
        )
        validation = ConnectorPackageContractValidation(
            validation_id=f"connector-contract-validation.{validation_digest[:24]}",
            schema_version=CONTRACT_VALIDATION_SCHEMA,
            version=1,
            lifecycle=ContractLifecycle.VALIDATING,
            outcome=outcome,
            source_license_analysis_id=source.analysis_id,
            source_license_analysis_digest=source.canonical_digest,
            source_malware_analysis_id=source.source_malware_analysis_id,
            source_malware_analysis_digest=source.source_malware_analysis_digest,
            source_vulnerability_analysis_id=source.source_vulnerability_analysis_id,
            source_vulnerability_analysis_digest=source.source_vulnerability_analysis_digest,
            source_static_dependency_analysis_id=source.source_static_dependency_analysis_id,
            source_static_dependency_analysis_digest=source.source_static_dependency_analysis_digest,
            source_authority_behavior_validation_id=source.source_authority_behavior_validation_id,
            source_schema_semantics_validation_id=source.source_schema_semantics_validation_id,
            source_content_policy_scan_id=source.source_content_policy_scan_id,
            source_inventory_id=source.source_inventory_id,
            source_validation_id=source.source_validation_id,
            source_acquisition_id=source.source_acquisition_id,
            source_handoff_id=source.source_handoff_id,
            source_project_id=source.source_project_id,
            source_acquired_by=source.source_acquired_by,
            source_manifest_validated_by=source.source_manifest_validated_by,
            source_inventoried_by=source.source_inventoried_by,
            source_content_scanned_by=source.source_content_scanned_by,
            source_schema_validated_by=source.source_schema_validated_by,
            source_authority_validated_by=source.source_authority_validated_by,
            source_static_analyzed_by=source.source_static_analyzed_by,
            source_vulnerability_analyzed_by=source.source_vulnerability_analyzed_by,
            source_malware_analyzed_by=source.source_malware_analyzed_by,
            source_license_analyzed_by=source.analyzed_by,
            source_custodied_by=source.source_custodied_by,
            source_domain_reviewed_by=source.source_domain_reviewed_by,
            source_security_reviewed_by=source.source_security_reviewed_by,
            source_lab_operated_by=source.source_lab_operated_by,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            validated_by=actor.subject_id,
            validation_profile=validation_profile,
            validator_version=CONTRACT_VALIDATOR,
            package_digest=source.package_digest,
            package_size_bytes=source.package_size_bytes,
            inventory_digest=inventory.inventory_digest,
            dependency_set_digest=inventory.dependency_set_digest,
            coverage=coverage,
            findings=findings,
            finding_set_digest=finding_set_digest,
            validation_digest=validation_digest,
            checks=checks,
            limitations=CONTRACT_LIMITATIONS,
            promotion_blocked=outcome is ContractOutcome.FAILED,
            canonical_digest="0" * 64,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            validated_at=self._clock(),
        )
        validation = replace(
            validation,
            canonical_digest=self._digest(self._canonical_payload_from_validation(validation)),
        )

        async with self._mutation_lock:
            existing = await self._repository.get_by_source_analysis(
                source_license_analysis_id=source.analysis_id
            )
            if existing is not None:
                self._verify_validation(existing)
                if (
                    existing.validated_by == actor.subject_id
                    and existing.idempotency_key == idempotency_key
                    and existing.request_fingerprint == fingerprint
                ):
                    return replace(existing, reused=True)
                raise PackageContractValidationError("package_contract_exists")
            await self._audit(
                actor=actor,
                correlation_id=correlation_id,
                permission_id=CONTRACT_VALIDATION_CREATE_PERMISSION,
                result_code=f"connector_contract_validation_{outcome.value}",
                validation=validation,
            )
            if not await self._repository.add(validation):
                raced = await self._repository.get_by_create_key(
                    validated_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    raise PackageContractValidationError("package_contract_conflict")
                self._verify_validation(raced)
                return replace(raced, reused=True)
        return validation

    async def get(
        self, *, actor: AuthenticatedSubject, validation_id: str, correlation_id: str
    ) -> ConnectorPackageContractValidation:
        self._require_enterprise_human(actor)
        validation = await self._repository.get_by_id(validation_id=validation_id)
        if validation is None:
            raise PackageContractValidationError("package_contract_not_found")
        self._require_scope(actor, validation.organization_id, validation.environment_id)
        if actor.subject_id in validation.source_actor_ids:
            raise PackageContractValidationError("package_contract_not_found")
        self._verify_validation(validation)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=CONTRACT_VALIDATION_READ_PERMISSION,
            result_code="connector_contract_validation_read",
            validation=validation,
        )
        return validation

    async def close(self) -> None:
        await self._repository.close()

    @property
    def repository(self) -> PackageContractValidationRepository:
        return self._repository

    @classmethod
    def _analyze(
        cls, files: dict[str, bytes]
    ) -> tuple[ContractCoverageSummary, tuple[ContractFinding, ...], dict[str, bool]]:
        manifest = cls._json_object(files, _MANIFEST_PATH)
        config = cls._json_object(files, _CONFIG_PATH)
        capabilities = manifest.get("capabilities") if manifest else None
        config_properties = config.get("properties") if config else None
        config_required = config.get("required") if config else None

        manifest_ok = bool(
            manifest
            and manifest.get("schema_version") == "atlas.connector-manifest.v1"
            and manifest.get("status") == "quarantined_generated_draft"
            and manifest.get("sdk_profile") == "atlas.python312.v1"
            and manifest.get("runtime_trust") is False
            and manifest.get("execution_authorized") is False
            and isinstance(capabilities, list)
            and 1 <= len(capabilities) <= 64
        )
        config_ok = bool(
            config
            and config.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
            and config.get("type") == "object"
            and config.get("additionalProperties") is False
            and isinstance(config_properties, dict)
            and isinstance(config_required, list)
            and sorted(config_properties) == sorted(str(item) for item in config_required)
        )

        expected_paths: set[str] = set()
        covered = 0
        schemas_ok = manifest_ok
        handlers_ok = manifest_ok
        tests_ok = manifest_ok
        capability_count = len(capabilities) if isinstance(capabilities, list) else 0
        input_count = output_count = handler_count = 0
        handler_paths = sorted(
            path
            for path in files
            if path.startswith("src/atlas_generated_connector/capabilities/")
            and path.endswith(".py")
            and not path.endswith("/__init__.py")
        )
        input_paths = sorted(
            path for path in files if path.startswith("schemas/inputs/") and path.endswith(".json")
        )
        output_paths = sorted(
            path for path in files if path.startswith("schemas/outputs/") and path.endswith(".json")
        )
        contract_test_paths = sorted(
            path for path in files if path.startswith("tests/contract/") and path.endswith(".py")
        )
        fixture_paths = sorted(
            path for path in files if path.startswith("tests/fixtures/") and path.endswith(".json")
        )
        if manifest_ok and isinstance(capabilities, list):
            seen_ids: set[str] = set()
            for manifest_item in capabilities:
                if not isinstance(manifest_item, dict):
                    schemas_ok = handlers_ok = tests_ok = False
                    continue
                candidate_id = manifest_item.get("id")
                if not isinstance(candidate_id, str) or candidate_id in seen_ids:
                    schemas_ok = handlers_ok = tests_ok = False
                    continue
                seen_ids.add(candidate_id)
                handler_matches = [
                    (path, result)
                    for path in handler_paths
                    if (
                        result := cls._handler_contract(
                            files.get(path), candidate_id, manifest_item
                        )
                    )
                    is not None
                ]
                input_matches = [
                    (path, value)
                    for path in input_paths
                    if (value := cls._json_object(files, path)) is not None
                    and value.get("$id") == f"atlas://generated/{candidate_id}/input.schema.json"
                ]
                output_matches = [
                    (path, value)
                    for path in output_paths
                    if (value := cls._json_object(files, path)) is not None
                    and value.get("$id") == f"atlas://generated/{candidate_id}/output.schema.json"
                ]
                one_binding = len(handler_matches) == len(input_matches) == len(output_matches) == 1
                if not one_binding:
                    schemas_ok = handlers_ok = tests_ok = False
                    continue
                handler_path, (handler_mode, literal_output) = handler_matches[0]
                input_path, input_schema = input_matches[0]
                output_path, output_schema = output_matches[0]
                module = PurePosixPath(handler_path).stem
                expected_paths.update((handler_path, input_path, output_path))
                input_count += 1
                output_count += 1
                handler_count += 1
                schema_status = (
                    "draft_requires_schema_review" if handler_mode == "fail_closed" else "reviewed"
                )
                one_schema_ok = bool(
                    input_schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
                    and input_schema.get("type") == "object"
                    and input_schema.get("additionalProperties") is False
                    and input_schema.get("x-atlas-generation-status") == schema_status
                    and output_schema.get("$schema")
                    == "https://json-schema.org/draft/2020-12/schema"
                    and output_schema.get("type") == "object"
                    and output_schema.get("x-atlas-generation-status") == schema_status
                    and (
                        output_schema.get("additionalProperties") is False
                        or handler_mode == "fail_closed"
                    )
                )
                if handler_mode == "fail_closed":
                    test_path = _CONTRACT_TEST_PATH
                    fixture_path = _FIXTURE_PATH
                    one_test_ok = cls._contract_test(files.get(test_path))
                    one_fixture_ok = cls._synthetic_fixture(files.get(fixture_path))
                else:
                    test_path = f"tests/contract/test_{module}.py"
                    fixture_path = f"tests/fixtures/{module}.json"
                    one_fixture_ok = cls._capability_fixture(
                        files.get(fixture_path), candidate_id, input_schema, output_schema
                    )
                    one_test_ok = cls._capability_contract_test(files.get(test_path), fixture_path)
                    fixture = cls._json_object(files, fixture_path)
                    one_fixture_ok = bool(
                        one_fixture_ok
                        and fixture
                        and literal_output == fixture.get("expected_output")
                    )
                expected_paths.update((test_path, fixture_path))
                schemas_ok = schemas_ok and one_schema_ok
                handlers_ok = handlers_ok and handler_mode in {"fail_closed", "bounded_literal"}
                tests_ok = tests_ok and one_test_ok and one_fixture_ok
                if one_schema_ok and one_test_ok and one_fixture_ok:
                    covered += 1

        actual_paths = {
            path
            for path in files
            if (
                path.startswith("src/atlas_generated_connector/capabilities/")
                and path.endswith(".py")
                and not path.endswith("/__init__.py")
            )
            or (path.startswith("schemas/inputs/") and path.endswith(".json"))
            or (path.startswith("schemas/outputs/") and path.endswith(".json"))
            or (path.startswith("tests/contract/") and path.endswith(".py"))
            or (path.startswith("tests/fixtures/") and path.endswith(".json"))
        }
        orphan_count = len(actual_paths.symmetric_difference(expected_paths))
        coverage_ok = bool(
            manifest_ok
            and config_ok
            and schemas_ok
            and handlers_ok
            and tests_ok
            and covered == capability_count
            and orphan_count == 0
        )
        contract_paths = sorted(
            {
                _MANIFEST_PATH,
                _CONFIG_PATH,
                *expected_paths,
            }
        )
        contract_set_digest = cls._digest(
            [
                {
                    "scope": cls._path_scope(path),
                    "fingerprint": sha256(files.get(path, b"")).hexdigest(),
                }
                for path in contract_paths
            ]
        )
        coverage = ContractCoverageSummary(
            manifest_count=int(_MANIFEST_PATH in files),
            configuration_schema_count=int(_CONFIG_PATH in files),
            capability_count=capability_count,
            input_schema_count=input_count,
            output_schema_count=output_count,
            handler_count=handler_count,
            covered_capability_count=covered,
            contract_test_count=len(contract_test_paths),
            synthetic_fixture_count=len(fixture_paths),
            orphan_artifact_count=orphan_count,
            contract_set_digest=contract_set_digest,
        )
        family_results = {
            "contract.source.accepted": True,
            "contract.archive.contract": True,
            "contract.manifest.binding": manifest_ok,
            "contract.schemas.binding": config_ok and schemas_ok,
            "contract.handlers.binding": handlers_ok,
            "contract.tests.synthetic": tests_ok,
            "contract.coverage.complete": coverage_ok,
        }
        scopes = {
            "contract.manifest.binding": ContractArtifactScope.MANIFEST,
            "contract.schemas.binding": ContractArtifactScope.CAPABILITY_SCHEMA,
            "contract.handlers.binding": ContractArtifactScope.HANDLER,
            "contract.tests.synthetic": ContractArtifactScope.CONTRACT_TEST,
            "contract.coverage.complete": ContractArtifactScope.COVERAGE,
        }
        findings = tuple(
            sorted(
                (
                    ContractFinding(
                        rule_id=code,
                        category="contract_consistency",
                        severity=(
                            ContractSeverity.CRITICAL
                            if code == "contract.handlers.binding"
                            else ContractSeverity.HIGH
                        ),
                        artifact_scope=scopes[code],
                        subject_fingerprint=cls._digest(
                            {"package_contract": contract_set_digest, "rule": code}
                        ),
                        summary="A required generated-draft contract family is inconsistent.",
                        remediation=(
                            "Regenerate the package through the governed Builder and repeat every "
                            "prior validation gate."
                        ),
                    )
                    for code, passed in family_results.items()
                    if not passed and code in scopes
                ),
                key=lambda item: (item.artifact_scope, item.subject_fingerprint, item.rule_id),
            )
        )
        return coverage, findings, family_results

    @staticmethod
    def _json_object(files: dict[str, bytes], path: str) -> dict[str, object] | None:
        raw = files.get(path)
        if raw is None or not raw or len(raw) > 65_536:
            return None
        try:
            value: object = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    @staticmethod
    def _handler_contract(
        raw: bytes | None, candidate_id: str, manifest_item: dict[str, object]
    ) -> tuple[str, dict[str, object] | None] | None:
        if raw is None or not raw or len(raw) > 65_536:
            return None
        try:
            tree = ast.parse(raw.decode("utf-8"), mode="exec")
        except (UnicodeError, SyntaxError):
            return None
        constants: dict[str, object] = {}
        handlers: list[ast.AsyncFunctionDef] = []
        for node in tree.body:
            if isinstance(node, ast.Expr):
                if not isinstance(node.value, ast.Constant) or not isinstance(
                    node.value.value, str
                ):
                    return None
            elif isinstance(node, ast.ImportFrom):
                allowed_imports = {
                    ("typing", ("Any",)),
                    ("typing", ("Any", "Never")),
                    (
                        "atlas_generated_connector.errors",
                        ("GeneratedDraftNotExecutable",),
                    ),
                }
                if (node.module, tuple(alias.name for alias in node.names)) not in allowed_imports:
                    return None
            elif isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name):
                    try:
                        constants[target.id] = ast.literal_eval(node.value)
                    except (ValueError, TypeError):
                        return None
                else:
                    return None
            elif isinstance(node, ast.AsyncFunctionDef):
                handlers.append(node)
            else:
                return None
        generated_constants = {
            "CAPABILITY_ID",
            "CAPABILITY_CLASS",
            "REQUIRED_PERMISSION",
            "SOURCE_CITATION",
            "HTTP_METHOD",
            "PATH_TEMPLATE",
        }
        reviewed_constants = {
            "CAPABILITY_ID",
            "CAPABILITY_CLASS",
            "REQUIRED_PERMISSION",
        }
        if frozenset(constants) not in {
            frozenset(generated_constants),
            frozenset(reviewed_constants),
        }:
            return None
        if any(not isinstance(value, str) for value in constants.values()):
            return None
        if constants.get("CAPABILITY_ID") != candidate_id:
            return None
        if constants.get("CAPABILITY_CLASS") != manifest_item.get("class"):
            return None
        if constants.get("REQUIRED_PERMISSION") != manifest_item.get("permission"):
            return None
        if manifest_item.get("handler_status") != "draft_fail_closed" or len(handlers) != 1:
            return None
        handler = handlers[0]
        if (
            handler.name != "handle"
            or len(handler.args.args) != 1
            or handler.args.vararg is not None
            or handler.args.kwarg is not None
            or handler.decorator_list
            or handler.args.defaults
            or len(handler.body) != 1
        ):
            return None
        if isinstance(handler.body[0], ast.Raise):
            raised = handler.body[0].exc
            if (
                isinstance(handler.returns, ast.Name)
                and handler.returns.id == "Never"
                and isinstance(raised, ast.Call)
                and isinstance(raised.func, ast.Name)
                and raised.func.id == "GeneratedDraftNotExecutable"
                and len(raised.args) == 1
                and isinstance(raised.args[0], ast.Constant)
                and isinstance(raised.args[0].value, str)
            ):
                return "fail_closed", None
            return None
        if isinstance(handler.body[0], ast.Return):
            if handler.body[0].value is None:
                return None
            try:
                value = ast.literal_eval(handler.body[0].value)
            except (ValueError, TypeError):
                return None
            if isinstance(value, dict) and value and all(isinstance(key, str) for key in value):
                return "bounded_literal", cast(dict[str, object], value)
        return None

    @classmethod
    def _capability_fixture(
        cls,
        raw: bytes | None,
        candidate_id: str,
        input_schema: dict[str, object],
        output_schema: dict[str, object],
    ) -> bool:
        if raw is None or not raw or len(raw) > 65_536:
            return False
        try:
            value: object = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            return False
        if not isinstance(value, dict) or set(value) != {
            "schema_version",
            "classification",
            "target_connected",
            "secret_values_present",
            "capability_id",
            "input",
            "expected_output",
        }:
            return False
        request = value.get("input")
        expected = value.get("expected_output")
        return bool(
            value.get("schema_version") == "atlas.generated.capability-fixture.v1"
            and value.get("classification") == "synthetic"
            and value.get("target_connected") is False
            and value.get("secret_values_present") is False
            and value.get("capability_id") == candidate_id
            and isinstance(request, dict)
            and isinstance(expected, dict)
            and cls._schema_accepts_object(input_schema, request)
            and cls._schema_accepts_object(output_schema, expected)
        )

    @staticmethod
    def _schema_accepts_object(schema: dict[str, object], value: dict[object, object]) -> bool:
        properties = schema.get("properties")
        required = schema.get("required", [])
        if not isinstance(properties, dict) or not isinstance(required, list):
            return False
        if schema.get("additionalProperties") is False and any(
            key not in properties for key in value
        ):
            return False
        if any(key not in value for key in required if isinstance(key, str)):
            return False
        for key, item in value.items():
            declaration = properties.get(key)
            if not isinstance(key, str) or not isinstance(declaration, dict):
                return False
            if declaration.get("type") == "string":
                if not isinstance(item, str):
                    return False
                minimum = declaration.get("minLength", 0)
                maximum = declaration.get("maxLength", 10_000)
                if not isinstance(minimum, int) or not isinstance(maximum, int):
                    return False
                if not minimum <= len(item) <= maximum:
                    return False
                choices = declaration.get("enum")
                if choices is not None and (not isinstance(choices, list) or item not in choices):
                    return False
            else:
                return False
        return True

    @staticmethod
    def _capability_contract_test(raw: bytes | None, fixture_path: str) -> bool:
        if raw is None or not raw or len(raw) > 32_768:
            return False
        try:
            tree = ast.parse(raw.decode("utf-8"), mode="exec")
        except (UnicodeError, SyntaxError):
            return False
        functions = [item for item in tree.body if isinstance(item, ast.FunctionDef)]
        if len(functions) != 1 or functions[0].name != "test_capability_contract":
            return False
        if len(functions[0].body) != 5 or not isinstance(functions[0].body[0], ast.Assign):
            return False
        expected_assignment = ast.parse(
            f"fixture = json.loads(Path({fixture_path!r}).read_text(encoding='utf-8'))"
        ).body[0]
        if ast.dump(functions[0].body[0]) != ast.dump(expected_assignment):
            return False
        assertions = {
            ast.unparse(item.test) for item in functions[0].body if isinstance(item, ast.Assert)
        }
        expected = {
            "fixture['classification'] == 'synthetic'",
            "fixture['target_connected'] is False",
            "fixture['secret_values_present'] is False",
            "fixture['schema_version'] == 'atlas.generated.capability-fixture.v1'",
        }
        imports = {
            alias.name for node in tree.body if isinstance(node, ast.Import) for alias in node.names
        }
        from_imports = {
            (node.module, alias.name)
            for node in tree.body
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        return bool(
            assertions == expected
            and imports == {"json"}
            and from_imports == {("pathlib", "Path")}
            and all(
                isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef))
                for node in tree.body
            )
        )

    @staticmethod
    def _contract_test(raw: bytes | None) -> bool:
        if raw is None or not raw or len(raw) > 32_768:
            return False
        try:
            tree = ast.parse(raw.decode("utf-8"), mode="exec")
        except (UnicodeError, SyntaxError):
            return False
        functions = [item for item in tree.body if isinstance(item, ast.FunctionDef)]
        if (
            len(functions) != 1
            or functions[0].name != "test_generated_scaffold_declares_quarantine"
        ):
            return False
        if len(functions[0].body) != 4 or not isinstance(functions[0].body[0], ast.Assign):
            return False
        expected_assignment = ast.parse(
            "manifest = json.loads(Path('atlas-connector.yaml').read_text(encoding='utf-8'))"
        ).body[0]
        if ast.dump(functions[0].body[0]) != ast.dump(expected_assignment):
            return False
        rendered_assertions = {
            ast.unparse(item.test) for item in functions[0].body if isinstance(item, ast.Assert)
        }
        expected = {
            "manifest['status'] == 'quarantined_generated_draft'",
            "manifest['runtime_trust'] is False",
            "manifest['execution_authorized'] is False",
        }
        prohibited = (ast.ImportFrom, ast.Lambda, ast.ClassDef, ast.AsyncFunctionDef)
        imports = {
            alias.name for node in tree.body if isinstance(node, ast.Import) for alias in node.names
        }
        from_imports = {
            (node.module, alias.name)
            for node in tree.body
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        top_level_ok = all(
            isinstance(node, (ast.Expr, ast.Import, ast.ImportFrom, ast.FunctionDef))
            for node in tree.body
        )
        return bool(
            rendered_assertions == expected
            and imports == {"json"}
            and from_imports == {("pathlib", "Path")}
            and top_level_ok
            and not any(
                isinstance(node, prohibited)
                and not (
                    isinstance(node, ast.ImportFrom)
                    and node.module == "pathlib"
                    and [alias.name for alias in node.names] == ["Path"]
                )
                for node in ast.walk(functions[0])
            )
        )

    @staticmethod
    def _synthetic_fixture(raw: bytes | None) -> bool:
        if raw is None or not raw or len(raw) > 65_536:
            return False
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            return False
        return bool(
            value
            == {
                "schema_version": "atlas.generated.synthetic-fixture.v1",
                "classification": "synthetic",
                "target_connected": False,
                "secret_values_present": False,
                "responses": [],
            }
        )

    @staticmethod
    def _path_scope(path: str) -> str:
        parts = PurePosixPath(path).parts
        if path == _MANIFEST_PATH:
            return "manifest"
        if parts and parts[0] == "schemas":
            return "schema"
        if parts and parts[0] == "src":
            return "handler"
        if path == _CONTRACT_TEST_PATH:
            return "contract_test"
        return "synthetic_fixture"

    @staticmethod
    def _checks(results: dict[str, bool]) -> tuple[ContractCheck, ...]:
        remediations = {
            "contract.source.accepted": "Repeat all prior promotion gates for the exact package.",
            "contract.archive.contract": (
                "Restore the exact immutable package and inventory evidence."
            ),
            "contract.manifest.binding": "Regenerate the manifest through the governed Builder.",
            "contract.schemas.binding": "Regenerate bounded schemas through the governed Builder.",
            "contract.handlers.binding": (
                "Regenerate bounded handler declarations through the governed Builder."
            ),
            "contract.tests.synthetic": (
                "Regenerate the quarantine test and disconnected synthetic fixture."
            ),
            "contract.coverage.complete": (
                "Regenerate the complete package and repeat every prior gate."
            ),
        }
        return tuple(
            ContractCheck(
                code=code,
                state=ContractCheckState.PASSED if results[code] else ContractCheckState.FAILED,
                severity=(
                    ContractCheckSeverity.INFORMATIONAL
                    if results[code]
                    else ContractCheckSeverity.ERROR
                ),
                summary=(
                    "The required contract family is consistent."
                    if results[code]
                    else "The required contract family is inconsistent."
                ),
                remediation=(
                    "No remediation is required." if results[code] else remediations[code]
                ),
            )
            for code in CONTRACT_CHECK_CODES
        )

    @staticmethod
    def _finding_payload(items: tuple[ContractFinding, ...]) -> list[dict[str, object]]:
        return [
            {
                "rule_id": item.rule_id,
                "category": item.category,
                "severity": item.severity.value,
                "artifact_scope": item.artifact_scope.value,
                "subject_fingerprint": item.subject_fingerprint,
                "summary": item.summary,
                "remediation": item.remediation,
            }
            for item in items
        ]

    @staticmethod
    def _check_payload(items: tuple[ContractCheck, ...]) -> list[dict[str, object]]:
        return [
            {
                "code": item.code,
                "state": item.state.value,
                "severity": item.severity.value,
                "summary": item.summary,
                "remediation": item.remediation,
            }
            for item in items
        ]

    @staticmethod
    def _coverage_payload(item: ContractCoverageSummary) -> dict[str, object]:
        return asdict(item)

    @classmethod
    def _canonical_payload_from_validation(
        cls, validation: ConnectorPackageContractValidation
    ) -> dict[str, object]:
        payload = cls._canonical_payload_with_internal_fields(validation)
        for field in ("canonical_digest", "request_fingerprint", "idempotency_key", "reused"):
            payload.pop(field)
        return cast(dict[str, object], cls._normalize(payload))

    @staticmethod
    def _canonical_payload_with_internal_fields(
        validation: ConnectorPackageContractValidation,
    ) -> dict[str, object]:
        return cast(dict[str, object], asdict(validation))

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

    @classmethod
    def _verify_validation(cls, validation: ConnectorPackageContractValidation) -> None:
        if (
            cls._digest(cls._canonical_payload_from_validation(validation))
            != validation.canonical_digest
        ):
            raise PackageContractValidationError("package_contract_integrity_failed")

    @staticmethod
    def _verify_source(source: ConnectorPackageLicenseAnalysis) -> None:
        try:
            PackageLicenseAnalysisService._verify_analysis(source)
        except Exception as error:
            raise PackageContractValidationError(
                "package_contract_source_integrity_failed"
            ) from error
        if (
            source.outcome is not LicenseOutcome.PASSED
            or source.promotion_blocked
            or not source.license_scan_completed
            or source.contract_validation_completed
            or source.connector_rejected
            or source.connector_registered
            or source.runtime_trust_granted
            or source.execution_authorized
            or source.infrastructure_mutation_performed
        ):
            raise PackageContractValidationError("package_contract_source_unsupported")

    @staticmethod
    def _verify_inventory_binding(
        source: ConnectorPackageLicenseAnalysis,
        inventory: ConnectorPackageSupplyChainInventory,
    ) -> None:
        try:
            PackageSupplyChainInventoryService._verify_inventory(inventory)
        except Exception as error:
            raise PackageContractValidationError(
                "package_contract_source_integrity_failed"
            ) from error
        if (
            inventory.outcome is not InventoryOutcome.PASSED
            or inventory.inventory_id != source.source_inventory_id
            or inventory.package_digest != source.package_digest
            or inventory.package_size_bytes != source.package_size_bytes
            or inventory.inventory_digest != source.inventory_digest
            or inventory.dependency_set_digest != source.dependency_set_digest
            or inventory.organization_id != source.organization_id
            or inventory.environment_id != source.environment_id
        ):
            raise PackageContractValidationError("package_contract_source_integrity_failed")

    @staticmethod
    def _verify_acquisition_binding(
        source: ConnectorPackageLicenseAnalysis,
        acquisition: ConnectorPackageAcquisition,
    ) -> None:
        try:
            PackageAcquisitionService._verify_acquisition(acquisition)
        except Exception as error:
            raise PackageContractValidationError(
                "package_contract_source_integrity_failed"
            ) from error
        if (
            acquisition.acquisition_id != source.source_acquisition_id
            or acquisition.package_digest != source.package_digest
            or acquisition.package_size_bytes != source.package_size_bytes
            or acquisition.organization_id != source.organization_id
            or acquisition.environment_id != source.environment_id
        ):
            raise PackageContractValidationError("package_contract_source_integrity_failed")

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
            raise PackageContractValidationError("package_contract_enterprise_human_mfa_required")

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise PackageContractValidationError("package_contract_not_found")

    @staticmethod
    def _require_separation(
        actor: AuthenticatedSubject, source: ConnectorPackageLicenseAnalysis
    ) -> None:
        if actor.subject_id in PackageLicenseAnalysisService._source_actor_ids(source) | {
            source.analyzed_by
        }:
            raise PackageContractValidationError("package_contract_separation_required")

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        validation: ConnectorPackageContractValidation,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.package-contract-validation",
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
                resource_type="resource.connector.package-contract-validation",
                scope_reference=validation.validation_id,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=validation.idempotency_key,
                target_metadata=(
                    ("validation_id", validation.validation_id),
                    ("source_license_analysis_id", validation.source_license_analysis_id),
                    ("package_digest", validation.package_digest),
                    ("validation_profile", validation.validation_profile),
                    ("validation_outcome", validation.outcome.value),
                    ("capability_count", str(validation.coverage.capability_count)),
                    ("covered_capability_count", str(validation.coverage.covered_capability_count)),
                    ("finding_count", str(len(validation.findings))),
                ),
            )
        )
