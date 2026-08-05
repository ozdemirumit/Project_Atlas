from __future__ import annotations

import asyncio
import json
import re
import tomllib
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from typing import TypeGuard
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.connectors.application.acquisition import PackageAcquisitionService
from atlas.modules.connectors.application.supply_chain_inventory_ports import (
    InventoryAcquisitionSource,
    InventoryArchiveSource,
    PackageSupplyChainInventoryError,
    PackageSupplyChainInventoryRepository,
    PackageValidationSource,
)
from atlas.modules.connectors.application.validation_intake import (
    VALIDATION_PROFILE,
    VALIDATOR_VERSION,
    PackageValidationService,
)
from atlas.modules.connectors.domain.acquisition import ConnectorPackageAcquisition
from atlas.modules.connectors.domain.supply_chain_inventory import (
    ConnectorPackageSupplyChainInventory,
    DependencyKind,
    InventoryCheckState,
    InventoryLifecycle,
    InventoryOutcome,
    InventorySeverity,
    PackageContentClass,
    PackageDependencyEvidence,
    PackageFileEvidence,
    PackageInventoryCheck,
)
from atlas.modules.connectors.domain.validation_intake import (
    ConnectorPackageValidation,
    PackageValidationOutcome,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

INVENTORY_CREATE_PERMISSION = "connectors.package-supply-chain-inventories.create"
INVENTORY_READ_PERMISSION = "connectors.package-supply-chain-inventories.read"
INVENTORY_SCHEMA = "atlas.connector-package-supply-chain-inventory.v1"
INVENTORY_PROFILE = "atlas.connector-supply-chain-inventory.python312.v1"
INSPECTOR_VERSION = "atlas.connector-content-dependency-inspector.v1"
PYPROJECT_PATH = "pyproject.toml"

INVENTORY_LIMITATIONS = (
    "This report proves exact package-content and dependency-declaration inventory only.",
    "Vulnerability, malware, secret, prohibited-content, license, provenance, static-code, "
    "contract, runner, self-test, and lab validation remain incomplete.",
    "Dependency artifacts were not resolved, downloaded, built, imported, or executed.",
    "Signing, attestation, rejection, registration, approval, installation, enablement, runtime "
    "trust, execution, and deployment remain prohibited.",
)

_DEPENDENCY = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]{0,99})(.+)$")
_GENERATED_NAME = re.compile(r"^atlas-generated-[a-f0-9]{12}$")


class PackageSupplyChainInventoryService:
    def __init__(
        self,
        *,
        repository: PackageSupplyChainInventoryRepository,
        validation_source: PackageValidationSource,
        acquisition_source: InventoryAcquisitionSource,
        archive_source: InventoryArchiveSource,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._validation_source = validation_source
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
        source_validation_id: str,
        source_validation_digest: str,
        package_digest: str,
        inventory_profile: str,
        acknowledged_untrusted_package_content: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorPackageSupplyChainInventory:
        self._require_enterprise_human(actor)
        if not acknowledged_untrusted_package_content:
            raise PackageSupplyChainInventoryError("package_inventory_acknowledgement_required")
        if inventory_profile != INVENTORY_PROFILE:
            raise PackageSupplyChainInventoryError("package_inventory_profile_unsupported")
        if not 8 <= len(idempotency_key) <= 128:
            raise PackageSupplyChainInventoryError("package_inventory_idempotency_key_invalid")
        fingerprint = self._digest(
            {
                "source_validation_id": source_validation_id,
                "source_validation_digest": source_validation_digest,
                "package_digest": package_digest,
                "inventory_profile": inventory_profile,
                "acknowledged_untrusted_package_content": True,
                "inventoried_by": actor.subject_id,
            }
        )
        replay = await self._repository.get_by_create_key(
            inventoried_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if replay is not None:
            self._verify_inventory(replay)
            if replay.request_fingerprint == fingerprint:
                return replace(replay, reused=True)
            raise PackageSupplyChainInventoryError("package_inventory_idempotency_conflict")

        validation = await self._validation_source.get_by_id(validation_id=source_validation_id)
        if validation is None:
            raise PackageSupplyChainInventoryError("package_inventory_source_not_found")
        self._require_scope(actor, validation.organization_id, validation.environment_id)
        self._require_separation(actor, validation)
        self._verify_source_validation(validation)
        if (
            validation.canonical_digest != source_validation_digest
            or validation.package_digest != package_digest
        ):
            raise PackageSupplyChainInventoryError("package_inventory_source_not_found")
        acquisition = await self._acquisition_source.get_by_id(
            acquisition_id=validation.source_acquisition_id
        )
        if acquisition is None:
            raise PackageSupplyChainInventoryError("package_inventory_source_integrity_failed")
        self._verify_acquisition_binding(validation, acquisition)
        try:
            content = await self._archive_source.read(
                package_digest=package_digest, size_bytes=acquisition.package_size_bytes
            )
            files, _ = PackageValidationService._verify_archive(acquisition, content)
        except Exception as error:
            raise PackageSupplyChainInventoryError(
                "package_inventory_archive_integrity_failed"
            ) from error

        file_evidence, content_valid = self._inventory_files(files)
        dependencies, project_valid = self._inventory_dependencies(files)
        dependency_valid = project_valid and dependencies is not None
        normalized_dependencies = dependencies or ()
        inventory_digest = self._digest(self._file_payload(file_evidence))
        dependency_digest = self._digest(self._dependency_payload(normalized_dependencies))
        checks = self._checks(
            content_valid=content_valid,
            project_valid=project_valid,
            dependency_valid=dependency_valid,
            files=file_evidence,
        )
        outcome = (
            InventoryOutcome.PASSED
            if all(item.state is InventoryCheckState.PASSED for item in checks)
            else InventoryOutcome.FAILED
        )
        payload = self._canonical_payload(
            validation=validation,
            actor_id=actor.subject_id,
            inventory_profile=inventory_profile,
            files=file_evidence,
            dependencies=normalized_dependencies,
            inventory_digest=inventory_digest,
            dependency_digest=dependency_digest,
            checks=checks,
            outcome=outcome,
        )
        canonical_digest = self._digest(payload)
        inventory = ConnectorPackageSupplyChainInventory(
            inventory_id=f"connector-package-inventory.{canonical_digest[:24]}",
            schema_version=INVENTORY_SCHEMA,
            version=1,
            lifecycle=InventoryLifecycle.VALIDATING,
            outcome=outcome,
            source_validation_id=validation.validation_id,
            source_validation_digest=validation.canonical_digest,
            source_acquisition_id=validation.source_acquisition_id,
            source_acquisition_digest=validation.source_acquisition_digest,
            source_handoff_id=validation.source_handoff_id,
            source_project_id=validation.source_project_id,
            source_acquired_by=validation.source_acquired_by,
            source_validated_by=validation.validated_by,
            source_custodied_by=validation.source_custodied_by,
            source_domain_reviewed_by=validation.source_domain_reviewed_by,
            source_security_reviewed_by=validation.source_security_reviewed_by,
            source_lab_operated_by=validation.source_lab_operated_by,
            organization_id=validation.organization_id,
            environment_id=validation.environment_id,
            inventoried_by=actor.subject_id,
            inventory_profile=inventory_profile,
            inspector_version=INSPECTOR_VERSION,
            package_digest=validation.package_digest,
            package_size_bytes=validation.package_size_bytes,
            files=file_evidence,
            dependencies=normalized_dependencies,
            inventory_digest=inventory_digest,
            dependency_set_digest=dependency_digest,
            runtime_dependency_count=sum(
                item.kind is DependencyKind.RUNTIME for item in normalized_dependencies
            ),
            build_dependency_count=sum(
                item.kind is DependencyKind.BUILD for item in normalized_dependencies
            ),
            dependency_lock_present=False,
            checks=checks,
            limitations=INVENTORY_LIMITATIONS,
            canonical_digest=canonical_digest,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            inventoried_at=self._clock(),
        )
        async with self._mutation_lock:
            existing = await self._repository.get_by_validation(
                source_validation_id=source_validation_id
            )
            if existing is not None:
                self._verify_inventory(existing)
                if (
                    existing.inventoried_by == actor.subject_id
                    and existing.idempotency_key == idempotency_key
                    and existing.request_fingerprint == fingerprint
                ):
                    return replace(existing, reused=True)
                raise PackageSupplyChainInventoryError("package_inventory_exists")
            await self._audit(
                actor=actor,
                correlation_id=correlation_id,
                permission_id=INVENTORY_CREATE_PERMISSION,
                result_code=f"connector_package_inventory_{outcome.value}",
                inventory=inventory,
            )
            if not await self._repository.add(inventory):
                raced = await self._repository.get_by_create_key(
                    inventoried_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    raise PackageSupplyChainInventoryError("package_inventory_conflict")
                self._verify_inventory(raced)
                return replace(raced, reused=True)
        return inventory

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        inventory_id: str,
        correlation_id: str,
    ) -> ConnectorPackageSupplyChainInventory:
        self._require_enterprise_human(actor)
        inventory = await self._repository.get_by_id(inventory_id=inventory_id)
        if inventory is None:
            raise PackageSupplyChainInventoryError("package_inventory_not_found")
        self._require_scope(actor, inventory.organization_id, inventory.environment_id)
        if actor.subject_id in self._source_actors(inventory):
            raise PackageSupplyChainInventoryError("package_inventory_not_found")
        self._verify_inventory(inventory)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=INVENTORY_READ_PERMISSION,
            result_code="connector_package_inventory_read",
            inventory=inventory,
        )
        return inventory

    async def close(self) -> None:
        await self._repository.close()

    @property
    def repository(self) -> PackageSupplyChainInventoryRepository:
        return self._repository

    @property
    def acquisition_source(self) -> InventoryAcquisitionSource:
        return self._acquisition_source

    @property
    def archive_source(self) -> InventoryArchiveSource:
        return self._archive_source

    @staticmethod
    def _verify_source_validation(validation: ConnectorPackageValidation) -> None:
        try:
            PackageValidationService._verify_validation(validation)
        except Exception as error:
            raise PackageSupplyChainInventoryError(
                "package_inventory_source_integrity_failed"
            ) from error
        if (
            validation.outcome is not PackageValidationOutcome.PASSED
            or validation.validation_profile != VALIDATION_PROFILE
            or validation.validator_version != VALIDATOR_VERSION
            or not validation.source_integrity_accepted
            or not validation.manifest_schema_validation_completed
            or validation.connector_registered
            or validation.runtime_trust_granted
            or validation.execution_authorized
            or validation.infrastructure_mutation_performed
        ):
            raise PackageSupplyChainInventoryError("package_inventory_source_unsupported")

    @staticmethod
    def _verify_acquisition_binding(
        validation: ConnectorPackageValidation, acquisition: ConnectorPackageAcquisition
    ) -> None:
        try:
            PackageAcquisitionService._verify_acquisition(acquisition)
        except Exception as error:
            raise PackageSupplyChainInventoryError(
                "package_inventory_source_integrity_failed"
            ) from error
        if (
            acquisition.acquisition_id != validation.source_acquisition_id
            or acquisition.canonical_digest != validation.source_acquisition_digest
            or acquisition.package_digest != validation.package_digest
            or acquisition.package_size_bytes != validation.package_size_bytes
            or acquisition.organization_id != validation.organization_id
            or acquisition.environment_id != validation.environment_id
        ):
            raise PackageSupplyChainInventoryError("package_inventory_source_integrity_failed")

    @classmethod
    def _inventory_files(
        cls, files: dict[str, bytes]
    ) -> tuple[tuple[PackageFileEvidence, ...], bool]:
        evidence: list[PackageFileEvidence] = []
        valid = len(files) == len({path.casefold() for path in files})
        for path, raw in sorted(files.items()):
            content_class = cls._classify(path)
            if content_class is None:
                valid = False
                continue
            evidence.append(
                PackageFileEvidence(
                    relative_path=path,
                    digest=sha256(raw).hexdigest(),
                    size_bytes=len(raw),
                    content_class=content_class,
                )
            )
        required = {
            "ATLAS-CANDIDATE-HANDOFF.json",
            "atlas-connector.yaml",
            "pyproject.toml",
            "README.md",
        }
        valid = valid and required.issubset(files) and len(evidence) == len(files)
        return tuple(evidence), valid

    @staticmethod
    def _classify(path: str) -> PackageContentClass | None:
        if path == "ATLAS-CANDIDATE-HANDOFF.json":
            return PackageContentClass.PROVENANCE
        if path == "atlas-connector.yaml":
            return PackageContentClass.MANIFEST
        if path == "pyproject.toml":
            return PackageContentClass.BUILD_METADATA
        if path == "README.md":
            return PackageContentClass.DOCUMENTATION
        if path.startswith("src/atlas_generated_connector/") and path.endswith(".py"):
            return PackageContentClass.SOURCE
        if path == "schemas/config/config.schema.json":
            return PackageContentClass.CONFIGURATION_SCHEMA
        if path.startswith(("schemas/inputs/", "schemas/outputs/")) and path.endswith(
            ".schema.json"
        ):
            return PackageContentClass.CAPABILITY_SCHEMA
        if path.startswith("tests/contract/") and path.endswith(".py"):
            return PackageContentClass.CONTRACT_TEST
        if path.startswith("tests/fixtures/") and path.endswith(".json"):
            return PackageContentClass.SYNTHETIC_FIXTURE
        return None

    @classmethod
    def _inventory_dependencies(
        cls, files: dict[str, bytes]
    ) -> tuple[tuple[PackageDependencyEvidence, ...] | None, bool]:
        raw = files.get(PYPROJECT_PATH)
        if raw is None or len(raw) > 100_000 or b"\x00" in raw:
            return None, False
        try:
            value = tomllib.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, tomllib.TOMLDecodeError):
            return None, False
        if set(value) != {"build-system", "project", "tool"}:
            return None, False
        build = value.get("build-system")
        project = value.get("project")
        tool = value.get("tool")
        if (
            not isinstance(build, dict)
            or not isinstance(project, dict)
            or not isinstance(tool, dict)
        ):
            return None, False
        if set(build) != {"requires", "build-backend"} or set(project) != {
            "name",
            "version",
            "description",
            "requires-python",
            "dependencies",
        }:
            return None, False
        if (
            not isinstance(project.get("name"), str)
            or _GENERATED_NAME.fullmatch(project["name"]) is None
            or project.get("version") != "0.1.0.dev0"
            or project.get("description") != "Quarantined Project Atlas connector review scaffold"
            or project.get("requires-python") != ">=3.12,<3.13"
            or build.get("build-backend") != "setuptools.build_meta"
            or set(tool) != {"ruff", "mypy", "pytest"}
            or not cls._valid_tool_contract(tool)
        ):
            return None, False
        build_items = build.get("requires")
        runtime_items = project.get("dependencies")
        if not cls._safe_dependency_list(
            build_items, allow_empty=False
        ) or not cls._safe_dependency_list(runtime_items, allow_empty=True):
            return None, False
        dependencies: list[PackageDependencyEvidence] = []
        for kind, declarations in (
            (DependencyKind.BUILD, build_items),
            (DependencyKind.RUNTIME, runtime_items),
        ):
            for declaration in declarations:
                match = _DEPENDENCY.fullmatch(declaration)
                if match is None:
                    return None, False
                try:
                    dependencies.append(
                        PackageDependencyEvidence(
                            name=match.group(1).lower().replace("_", "-"),
                            version_constraint=match.group(2),
                            kind=kind,
                            source_path=PYPROJECT_PATH,
                        )
                    )
                except ValueError:
                    return None, False
        return tuple(sorted(dependencies, key=lambda item: (item.kind, item.name))), True

    @staticmethod
    def _valid_tool_contract(tool: dict[object, object]) -> bool:
        ruff = tool.get("ruff")
        mypy = tool.get("mypy")
        pytest = tool.get("pytest")
        return bool(
            isinstance(ruff, dict)
            and set(ruff) == {"target-version", "line-length"}
            and ruff.get("target-version") == "py312"
            and ruff.get("line-length") == 100
            and isinstance(mypy, dict)
            and set(mypy) == {"python_version", "strict"}
            and mypy.get("python_version") == "3.12"
            and mypy.get("strict") is True
            and isinstance(pytest, dict)
            and set(pytest) == {"ini_options"}
            and isinstance(pytest.get("ini_options"), dict)
            and pytest["ini_options"] == {"testpaths": ["tests"]}
        )

    @staticmethod
    def _safe_dependency_list(value: object, *, allow_empty: bool) -> TypeGuard[list[str]]:
        return bool(
            isinstance(value, list)
            and (allow_empty or value)
            and len(value) <= 100
            and len(value) == len(set(value))
            and all(isinstance(item, str) and 2 <= len(item) <= 300 for item in value)
        )

    @classmethod
    def _checks(
        cls,
        *,
        content_valid: bool,
        project_valid: bool,
        dependency_valid: bool,
        files: tuple[PackageFileEvidence, ...],
    ) -> tuple[PackageInventoryCheck, ...]:
        paths = tuple(item.relative_path for item in files)
        return (
            cls._check(
                "inventory.source.accepted",
                True,
                "Exact passed validation evidence accepted.",
                (),
                "Restore exact passed source evidence.",
            ),
            cls._check(
                "inventory.archive.contract",
                True,
                "Exact acquired archive contract accepted.",
                ("ATLAS-CANDIDATE-HANDOFF.json",),
                "Restore exact acquired archive bytes.",
            ),
            cls._check(
                "inventory.content.classified",
                content_valid,
                "Every package entry has a bounded generated-profile content class.",
                paths,
                "Remove extraneous content and restore every required profile file.",
            ),
            cls._check(
                "inventory.project-metadata.contract",
                project_valid,
                "Python project metadata remains bounded and generated-profile compatible.",
                (PYPROJECT_PATH,) if PYPROJECT_PATH in paths else (),
                "Restore the exact bounded Python 3.12 project metadata contract.",
            ),
            cls._check(
                "inventory.dependencies.normalized",
                dependency_valid,
                "Build and runtime dependency declarations are normalized without resolution.",
                (PYPROJECT_PATH,) if PYPROJECT_PATH in paths else (),
                "Use bounded version-constrained dependency declarations without URLs or markers.",
            ),
        )

    @staticmethod
    def _check(
        code: str,
        passed: bool,
        summary: str,
        evidence_paths: tuple[str, ...],
        remediation: str,
    ) -> PackageInventoryCheck:
        return PackageInventoryCheck(
            code=code,
            state=InventoryCheckState.PASSED if passed else InventoryCheckState.FAILED,
            severity=InventorySeverity.INFORMATIONAL if passed else InventorySeverity.ERROR,
            summary=summary,
            evidence_paths=evidence_paths,
            remediation=remediation,
        )

    @classmethod
    def _canonical_payload(
        cls,
        *,
        validation: ConnectorPackageValidation,
        actor_id: str,
        inventory_profile: str,
        files: tuple[PackageFileEvidence, ...],
        dependencies: tuple[PackageDependencyEvidence, ...],
        inventory_digest: str,
        dependency_digest: str,
        checks: tuple[PackageInventoryCheck, ...],
        outcome: InventoryOutcome,
    ) -> dict[str, object]:
        return {
            "lifecycle": InventoryLifecycle.VALIDATING.value,
            "outcome": outcome.value,
            "source_validation_id": validation.validation_id,
            "source_validation_digest": validation.canonical_digest,
            "source_acquisition_id": validation.source_acquisition_id,
            "source_acquisition_digest": validation.source_acquisition_digest,
            "source_handoff_id": validation.source_handoff_id,
            "source_project_id": validation.source_project_id,
            "source_acquired_by": validation.source_acquired_by,
            "source_validated_by": validation.validated_by,
            "source_custodied_by": validation.source_custodied_by,
            "source_domain_reviewed_by": validation.source_domain_reviewed_by,
            "source_security_reviewed_by": validation.source_security_reviewed_by,
            "source_lab_operated_by": validation.source_lab_operated_by,
            "organization_id": validation.organization_id,
            "environment_id": validation.environment_id,
            "inventoried_by": actor_id,
            "inventory_profile": inventory_profile,
            "inspector_version": INSPECTOR_VERSION,
            "package_digest": validation.package_digest,
            "package_size_bytes": validation.package_size_bytes,
            "files": cls._file_payload(files),
            "dependencies": cls._dependency_payload(dependencies),
            "inventory_digest": inventory_digest,
            "dependency_set_digest": dependency_digest,
            "runtime_dependency_count": sum(
                item.kind is DependencyKind.RUNTIME for item in dependencies
            ),
            "build_dependency_count": sum(
                item.kind is DependencyKind.BUILD for item in dependencies
            ),
            "dependency_lock_present": False,
            "checks": cls._check_payload(checks),
            "limitations": INVENTORY_LIMITATIONS,
        }

    @classmethod
    def _verify_inventory(cls, inventory: ConnectorPackageSupplyChainInventory) -> None:
        payload = {
            "lifecycle": inventory.lifecycle.value,
            "outcome": inventory.outcome.value,
            "source_validation_id": inventory.source_validation_id,
            "source_validation_digest": inventory.source_validation_digest,
            "source_acquisition_id": inventory.source_acquisition_id,
            "source_acquisition_digest": inventory.source_acquisition_digest,
            "source_handoff_id": inventory.source_handoff_id,
            "source_project_id": inventory.source_project_id,
            "source_acquired_by": inventory.source_acquired_by,
            "source_validated_by": inventory.source_validated_by,
            "source_custodied_by": inventory.source_custodied_by,
            "source_domain_reviewed_by": inventory.source_domain_reviewed_by,
            "source_security_reviewed_by": inventory.source_security_reviewed_by,
            "source_lab_operated_by": inventory.source_lab_operated_by,
            "organization_id": inventory.organization_id,
            "environment_id": inventory.environment_id,
            "inventoried_by": inventory.inventoried_by,
            "inventory_profile": inventory.inventory_profile,
            "inspector_version": inventory.inspector_version,
            "package_digest": inventory.package_digest,
            "package_size_bytes": inventory.package_size_bytes,
            "files": cls._file_payload(inventory.files),
            "dependencies": cls._dependency_payload(inventory.dependencies),
            "inventory_digest": inventory.inventory_digest,
            "dependency_set_digest": inventory.dependency_set_digest,
            "runtime_dependency_count": inventory.runtime_dependency_count,
            "build_dependency_count": inventory.build_dependency_count,
            "dependency_lock_present": inventory.dependency_lock_present,
            "checks": cls._check_payload(inventory.checks),
            "limitations": inventory.limitations,
        }
        if cls._digest(payload) != inventory.canonical_digest:
            raise PackageSupplyChainInventoryError("package_inventory_integrity_failed")

    @staticmethod
    def _file_payload(files: tuple[PackageFileEvidence, ...]) -> list[dict[str, object]]:
        return [
            {
                "relative_path": item.relative_path,
                "digest": item.digest,
                "size_bytes": item.size_bytes,
                "content_class": item.content_class.value,
            }
            for item in files
        ]

    @staticmethod
    def _dependency_payload(
        dependencies: tuple[PackageDependencyEvidence, ...],
    ) -> list[dict[str, object]]:
        return [
            {
                "name": item.name,
                "version_constraint": item.version_constraint,
                "kind": item.kind.value,
                "source_path": item.source_path,
            }
            for item in dependencies
        ]

    @staticmethod
    def _check_payload(checks: tuple[PackageInventoryCheck, ...]) -> list[dict[str, object]]:
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
            raise PackageSupplyChainInventoryError(
                "package_inventory_enterprise_human_mfa_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise PackageSupplyChainInventoryError("package_inventory_not_found")

    @classmethod
    def _require_separation(
        cls, actor: AuthenticatedSubject, validation: ConnectorPackageValidation
    ) -> None:
        if actor.subject_id in {
            validation.validated_by,
            validation.source_acquired_by,
            validation.source_custodied_by,
            validation.source_domain_reviewed_by,
            validation.source_security_reviewed_by,
            validation.source_lab_operated_by,
        }:
            raise PackageSupplyChainInventoryError("package_inventory_not_found")

    @staticmethod
    def _source_actors(inventory: ConnectorPackageSupplyChainInventory) -> set[str]:
        return {
            inventory.source_validated_by,
            inventory.source_acquired_by,
            inventory.source_custodied_by,
            inventory.source_domain_reviewed_by,
            inventory.source_security_reviewed_by,
            inventory.source_lab_operated_by,
        }

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        inventory: ConnectorPackageSupplyChainInventory,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.package-supply-chain-inventory",
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
                resource_type="resource.connector.package-supply-chain-inventory",
                scope_reference=inventory.inventory_id,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=inventory.idempotency_key,
                target_metadata=(
                    ("inventory_id", inventory.inventory_id),
                    ("source_validation_id", inventory.source_validation_id),
                    ("package_digest", inventory.package_digest),
                    ("inventory_outcome", inventory.outcome.value),
                ),
            )
        )
