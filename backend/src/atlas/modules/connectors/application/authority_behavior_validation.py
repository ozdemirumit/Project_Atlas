from __future__ import annotations

import ast
import asyncio
import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.connectors.application.acquisition import PackageAcquisitionService
from atlas.modules.connectors.application.authority_behavior_validation_ports import (
    AuthorityBehaviorAcquisitionSource,
    AuthorityBehaviorArchiveSource,
    AuthorityBehaviorInventorySource,
    AuthorityBehaviorSchemaSemanticsSource,
    PackageAuthorityBehaviorValidationError,
    PackageAuthorityBehaviorValidationRepository,
)
from atlas.modules.connectors.application.schema_semantics_validation import (
    SCHEMA_SEMANTICS_PROFILE,
    SCHEMA_SEMANTICS_VALIDATOR,
    PackageSchemaSemanticsValidationService,
)
from atlas.modules.connectors.application.supply_chain_inventory import (
    PackageSupplyChainInventoryService,
)
from atlas.modules.connectors.application.validation_intake import PackageValidationService
from atlas.modules.connectors.domain.acquisition import ConnectorPackageAcquisition
from atlas.modules.connectors.domain.authority_behavior_validation import (
    AuthorityBehaviorCheck,
    AuthorityBehaviorCheckState,
    AuthorityBehaviorFinding,
    AuthorityBehaviorLifecycle,
    AuthorityBehaviorOutcome,
    AuthorityBehaviorSeverity,
    BehaviorCategory,
    CapabilityBehaviorSummary,
    ConnectorPackageAuthorityBehaviorValidation,
)
from atlas.modules.connectors.domain.schema_semantics_validation import (
    ConnectorPackageSchemaSemanticsValidation,
    SchemaSemanticsOutcome,
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

AUTHORITY_BEHAVIOR_CREATE_PERMISSION = "connectors.package-authority-behavior-validations.create"
AUTHORITY_BEHAVIOR_READ_PERMISSION = "connectors.package-authority-behavior-validations.read"
AUTHORITY_BEHAVIOR_SCHEMA = "atlas.connector-package-authority-behavior-validation.v1"
AUTHORITY_BEHAVIOR_PROFILE = "atlas.connector-authority-behavior.python312.v1"
AUTHORITY_BEHAVIOR_ANALYZER = "atlas.connector-declared-authority-ast-analyzer.v1"

AUTHORITY_BEHAVIOR_LIMITATIONS = (
    "This report compares only bounded statically observable Python behavior to declarations.",
    "Source snippets, literals, destinations, arguments, credentials, and request bodies are not "
    "retained.",
    "Dependency, vulnerability, malware, license, general static-code, contract, runner, "
    "self-test, "
    "and lab validation remain incomplete.",
    "Rejection, registration, approval, installation, enablement, runtime trust, execution, and "
    "deployment remain prohibited.",
)

_MANIFEST_PATH = "atlas-connector.yaml"
_SOURCE_PREFIX = "src/atlas_generated_connector/capabilities/"
_PURE_CALLS = frozenset(
    {
        "bool",
        "dict",
        "enumerate",
        "float",
        "int",
        "len",
        "list",
        "max",
        "min",
        "range",
        "set",
        "sorted",
        "str",
        "sum",
        "tuple",
        "zip",
        "GeneratedDraftNotExecutable",
    }
)
_SAFE_METHODS = frozenset(
    {"get", "items", "keys", "values", "copy", "casefold", "lower", "upper", "strip"}
)
_NETWORK_ROOTS = frozenset({"aiohttp", "httpx", "requests", "socket", "urllib", "urllib3"})
_PROCESS_ROOTS = frozenset({"subprocess"})
_PROCESS_NAMES = frozenset({"system", "popen", "spawnl", "spawnlp", "spawnv", "spawnvp"})
_DYNAMIC_NAMES = frozenset(
    {"eval", "exec", "compile", "__import__", "getattr", "setattr", "delattr", "globals", "locals"}
)
_FILESYSTEM_WRITE_METHODS = frozenset(
    {"write_text", "write_bytes", "unlink", "rename", "replace", "mkdir", "rmdir", "touch"}
)
_NETWORK_MUTATING_METHODS = frozenset({"post", "put", "patch", "delete"})


class _ModuleObservation:
    def __init__(self, path: str, package_digest: str) -> None:
        self.path = path
        self.package_digest = package_digest
        self.constants: dict[str, str] = {}
        self.handler_count = 0
        self.categories: set[BehaviorCategory] = {BehaviorCategory.READ}
        self.network_calls = 0
        self.mutation_calls = 0
        self.findings: list[AuthorityBehaviorFinding] = []

    def add(
        self,
        rule: str,
        category: BehaviorCategory,
        line: int,
        summary: str,
        remediation: str,
    ) -> None:
        self.categories.add(category)
        self.findings.append(
            AuthorityBehaviorFinding(
                rule_code=rule,
                category=category,
                severity=AuthorityBehaviorSeverity.ERROR,
                relative_path=self.path,
                line_number=max(0, line),
                evidence_fingerprint=PackageAuthorityBehaviorValidationService._digest(
                    {
                        "package_digest": self.package_digest,
                        "path": self.path,
                        "line": max(0, line),
                        "rule": rule,
                    }
                ),
                summary=summary,
                remediation=remediation,
            )
        )


class _BoundedAstAnalyzer(ast.NodeVisitor):
    def __init__(self, observation: _ModuleObservation) -> None:
        self.observation = observation
        self.node_count = 0
        self.import_roots: set[str] = set()

    def generic_visit(self, node: ast.AST) -> None:
        self.node_count += 1
        if self.node_count > 20_000:
            raise ValueError("AST node budget exceeded")
        super().generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root = alias.name.split(".", 1)[0]
            self.import_roots.add(alias.asname or root)
            if root == "importlib":
                self.observation.add(
                    "behavior.dynamic-import.declared",
                    BehaviorCategory.DYNAMIC_EXECUTION,
                    node.lineno,
                    "Module declares dynamic import support.",
                    "Remove dynamic import behavior and use reviewed static imports.",
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        root = (node.module or "").split(".", 1)[0]
        for alias in node.names:
            self.import_roots.add(alias.asname or alias.name)
        if root == "importlib":
            self.observation.add(
                "behavior.dynamic-import.declared",
                BehaviorCategory.DYNAMIC_EXECUTION,
                node.lineno,
                "Module declares dynamic import support.",
                "Remove dynamic import behavior and use reviewed static imports.",
            )
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            value = node.value.value if isinstance(node.value, ast.Constant) else None
            if isinstance(value, str):
                self.observation.constants[node.targets[0].id] = value
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if node.name == "handle":
            self.observation.handler_count += 1
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name == "handle":
            self.observation.handler_count += 1
            self.observation.add(
                "behavior.handler.not-async",
                BehaviorCategory.DECLARATION,
                node.lineno,
                "Capability handler is not asynchronous.",
                "Expose exactly one reviewed async handle function.",
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = self._qualified_name(node.func)
        root = name.split(".", 1)[0]
        leaf = name.rsplit(".", 1)[-1]
        if root in _NETWORK_ROOTS:
            self.observation.categories.add(BehaviorCategory.NETWORK)
            self.observation.network_calls += 1
            if leaf.casefold() in _NETWORK_MUTATING_METHODS:
                self.observation.categories.add(BehaviorCategory.MUTATION)
                self.observation.mutation_calls += 1
        elif root in _PROCESS_ROOTS or leaf.casefold() in _PROCESS_NAMES:
            self.observation.add(
                "behavior.process.observed",
                BehaviorCategory.PROCESS,
                node.lineno,
                "Process creation or shell behavior is statically observable.",
                "Remove process behavior from the connector capability.",
            )
        elif leaf in _DYNAMIC_NAMES or root == "importlib":
            self.observation.add(
                "behavior.dynamic-execution.observed",
                BehaviorCategory.DYNAMIC_EXECUTION,
                node.lineno,
                "Dynamic execution or reflection is statically observable.",
                "Replace dynamic behavior with explicit reviewed code paths.",
            )
        elif leaf in _FILESYSTEM_WRITE_METHODS or self._open_writes(node, name):
            self.observation.add(
                "behavior.filesystem-write.observed",
                BehaviorCategory.FILESYSTEM,
                node.lineno,
                "Filesystem mutation is statically observable.",
                "Remove filesystem writes or move them to an explicitly reviewed capability class.",
            )
            self.observation.mutation_calls += 1
            self.observation.categories.add(BehaviorCategory.MUTATION)
        elif name and leaf not in _PURE_CALLS and leaf not in _SAFE_METHODS:
            self.observation.add(
                "behavior.call.unresolved",
                BehaviorCategory.AMBIGUOUS,
                node.lineno,
                "A call target cannot be safely classified by the bounded profile.",
                "Use an approved explicit client call or remove unresolved indirection.",
            )
        self.generic_visit(node)

    @staticmethod
    def _qualified_name(node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = _BoundedAstAnalyzer._qualified_name(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        return ""

    @staticmethod
    def _open_writes(node: ast.Call, name: str) -> bool:
        if name.rsplit(".", 1)[-1] != "open":
            return False
        mode: object = None
        if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
            mode = node.args[1].value
        for keyword in node.keywords:
            if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
                mode = keyword.value.value
        return isinstance(mode, str) and any(flag in mode for flag in "wax+")


class PackageAuthorityBehaviorValidationService:
    def __init__(
        self,
        *,
        repository: PackageAuthorityBehaviorValidationRepository,
        schema_semantics_source: AuthorityBehaviorSchemaSemanticsSource,
        inventory_source: AuthorityBehaviorInventorySource,
        acquisition_source: AuthorityBehaviorAcquisitionSource,
        archive_source: AuthorityBehaviorArchiveSource,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._schema_semantics_source = schema_semantics_source
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
        source_schema_semantics_validation_id: str,
        source_schema_semantics_validation_digest: str,
        package_digest: str,
        validation_profile: str,
        acknowledged_static_analysis_limitations: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorPackageAuthorityBehaviorValidation:
        self._require_enterprise_human(actor)
        if not acknowledged_static_analysis_limitations:
            raise PackageAuthorityBehaviorValidationError(
                "package_authority_behavior_acknowledgement_required"
            )
        if validation_profile != AUTHORITY_BEHAVIOR_PROFILE:
            raise PackageAuthorityBehaviorValidationError(
                "package_authority_behavior_profile_unsupported"
            )
        if not 8 <= len(idempotency_key) <= 128:
            raise PackageAuthorityBehaviorValidationError(
                "package_authority_behavior_idempotency_key_invalid"
            )
        fingerprint = self._digest(
            {
                "source_schema_semantics_validation_id": source_schema_semantics_validation_id,
                "source_schema_semantics_validation_digest": (
                    source_schema_semantics_validation_digest
                ),
                "package_digest": package_digest,
                "validation_profile": validation_profile,
                "acknowledged_static_analysis_limitations": True,
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
            raise PackageAuthorityBehaviorValidationError(
                "package_authority_behavior_idempotency_conflict"
            )

        source = await self._schema_semantics_source.get_by_id(
            validation_id=source_schema_semantics_validation_id
        )
        if source is None:
            raise PackageAuthorityBehaviorValidationError(
                "package_authority_behavior_source_not_found"
            )
        self._require_scope(actor, source.organization_id, source.environment_id)
        self._require_separation(actor, source)
        self._verify_source(source)
        if (
            source.canonical_digest != source_schema_semantics_validation_digest
            or source.package_digest != package_digest
        ):
            raise PackageAuthorityBehaviorValidationError(
                "package_authority_behavior_source_not_found"
            )
        inventory = await self._inventory_source.get_by_id(inventory_id=source.source_inventory_id)
        if inventory is None:
            raise PackageAuthorityBehaviorValidationError(
                "package_authority_behavior_source_integrity_failed"
            )
        self._verify_inventory_binding(source, inventory)
        acquisition = await self._acquisition_source.get_by_id(
            acquisition_id=source.source_acquisition_id
        )
        if acquisition is None:
            raise PackageAuthorityBehaviorValidationError(
                "package_authority_behavior_source_integrity_failed"
            )
        self._verify_acquisition_binding(source, acquisition)
        try:
            content = await self._archive_source.read(
                package_digest=package_digest, size_bytes=source.package_size_bytes
            )
            files, _ = PackageValidationService._verify_archive(acquisition, content)
            self._verify_inventory_files(inventory, files)
        except PackageAuthorityBehaviorValidationError:
            raise
        except Exception as error:
            raise PackageAuthorityBehaviorValidationError(
                "package_authority_behavior_archive_integrity_failed"
            ) from error

        manifest = self._strict_object(files.get(_MANIFEST_PATH), "manifest")
        capabilities, findings = self._compare(package_digest, files, manifest)
        checks = self._checks(findings)
        outcome = (
            AuthorityBehaviorOutcome.PASSED
            if all(item.state is AuthorityBehaviorCheckState.PASSED for item in checks)
            else AuthorityBehaviorOutcome.FAILED
        )
        capability_set_digest = self._digest(self._capability_payload(capabilities))
        finding_set_digest = self._digest(self._finding_payload(findings))
        behavior_validation_digest = self._digest(
            {
                "analyzer_version": AUTHORITY_BEHAVIOR_ANALYZER,
                "package_digest": package_digest,
                "capability_set_digest": capability_set_digest,
                "finding_set_digest": finding_set_digest,
            }
        )
        payload = self._canonical_payload(
            source=source,
            actor_id=actor.subject_id,
            validation_profile=validation_profile,
            capabilities=capabilities,
            capability_set_digest=capability_set_digest,
            findings=findings,
            finding_set_digest=finding_set_digest,
            behavior_validation_digest=behavior_validation_digest,
            checks=checks,
            outcome=outcome,
        )
        canonical_digest = self._digest(payload)
        validation = ConnectorPackageAuthorityBehaviorValidation(
            validation_id=f"connector-authority-behavior-validation.{canonical_digest[:24]}",
            schema_version=AUTHORITY_BEHAVIOR_SCHEMA,
            version=1,
            lifecycle=AuthorityBehaviorLifecycle.VALIDATING,
            outcome=outcome,
            source_schema_semantics_validation_id=source.validation_id,
            source_schema_semantics_validation_digest=source.canonical_digest,
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
            source_schema_validated_by=source.validated_by,
            source_custodied_by=source.source_custodied_by,
            source_domain_reviewed_by=source.source_domain_reviewed_by,
            source_security_reviewed_by=source.source_security_reviewed_by,
            source_lab_operated_by=source.source_lab_operated_by,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            validated_by=actor.subject_id,
            validation_profile=validation_profile,
            analyzer_version=AUTHORITY_BEHAVIOR_ANALYZER,
            package_digest=source.package_digest,
            package_size_bytes=source.package_size_bytes,
            inventory_digest=source.inventory_digest,
            semantic_validation_digest=source.semantic_validation_digest,
            capabilities=capabilities,
            capability_set_digest=capability_set_digest,
            findings=findings,
            finding_set_digest=finding_set_digest,
            behavior_validation_digest=behavior_validation_digest,
            checks=checks,
            limitations=AUTHORITY_BEHAVIOR_LIMITATIONS,
            promotion_blocked=outcome is AuthorityBehaviorOutcome.FAILED,
            canonical_digest=canonical_digest,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            validated_at=self._clock(),
        )
        async with self._mutation_lock:
            existing = await self._repository.get_by_source_validation(
                source_schema_semantics_validation_id=source.validation_id
            )
            if existing is not None:
                self._verify_validation(existing)
                if (
                    existing.validated_by == actor.subject_id
                    and existing.idempotency_key == idempotency_key
                    and existing.request_fingerprint == fingerprint
                ):
                    return replace(existing, reused=True)
                raise PackageAuthorityBehaviorValidationError("package_authority_behavior_exists")
            await self._audit(
                actor=actor,
                correlation_id=correlation_id,
                permission_id=AUTHORITY_BEHAVIOR_CREATE_PERMISSION,
                result_code=f"connector_authority_behavior_validation_{outcome.value}",
                validation=validation,
            )
            if not await self._repository.add(validation):
                raced = await self._repository.get_by_create_key(
                    validated_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    raise PackageAuthorityBehaviorValidationError(
                        "package_authority_behavior_conflict"
                    )
                self._verify_validation(raced)
                return replace(raced, reused=True)
        return validation

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        validation_id: str,
        correlation_id: str,
    ) -> ConnectorPackageAuthorityBehaviorValidation:
        self._require_enterprise_human(actor)
        validation = await self._repository.get_by_id(validation_id=validation_id)
        if validation is None:
            raise PackageAuthorityBehaviorValidationError("package_authority_behavior_not_found")
        self._require_scope(actor, validation.organization_id, validation.environment_id)
        if actor.subject_id in self._validation_source_actors(validation):
            raise PackageAuthorityBehaviorValidationError("package_authority_behavior_not_found")
        self._verify_validation(validation)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=AUTHORITY_BEHAVIOR_READ_PERMISSION,
            result_code="connector_authority_behavior_validation_read",
            validation=validation,
        )
        return validation

    async def close(self) -> None:
        await self._repository.close()

    @property
    def repository(self) -> PackageAuthorityBehaviorValidationRepository:
        return self._repository

    @staticmethod
    def _strict_object(raw: bytes | None, label: str) -> dict[str, Any]:
        if raw is None or len(raw) > 100_000:
            raise PackageAuthorityBehaviorValidationError(
                f"package_authority_behavior_{label}_invalid"
            )

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
            raise PackageAuthorityBehaviorValidationError(
                f"package_authority_behavior_{label}_invalid"
            ) from error
        if not isinstance(value, dict):
            raise PackageAuthorityBehaviorValidationError(
                f"package_authority_behavior_{label}_invalid"
            )
        return value

    @classmethod
    def _compare(
        cls,
        package_digest: str,
        files: dict[str, bytes],
        manifest: dict[str, Any],
    ) -> tuple[tuple[CapabilityBehaviorSummary, ...], tuple[AuthorityBehaviorFinding, ...]]:
        findings: list[AuthorityBehaviorFinding] = []

        def add(
            rule: str,
            category: BehaviorCategory,
            path: str,
            line: int,
            summary: str,
            remediation: str,
        ) -> None:
            findings.append(
                cls._finding(package_digest, rule, category, path, line, summary, remediation)
            )

        manifest_capabilities = manifest.get("capabilities")
        destinations = manifest.get("network_destinations")
        if not isinstance(manifest_capabilities, list) or not manifest_capabilities:
            raise PackageAuthorityBehaviorValidationError(
                "package_authority_behavior_manifest_invalid"
            )
        if (
            not isinstance(destinations, list)
            or any(not isinstance(item, str) for item in destinations)
            or manifest.get("runtime_trust") is not False
            or manifest.get("execution_authorized") is not False
        ):
            add(
                "declaration.authority.inconsistent",
                BehaviorCategory.DECLARATION,
                _MANIFEST_PATH,
                0,
                "Network or broad-authority declarations are incomplete or inconsistent.",
                "Restore exact bounded network and least-privilege declarations.",
            )
        safe_destinations = tuple(item for item in destinations or () if isinstance(item, str))
        if any(not cls._safe_destination(item) for item in safe_destinations):
            add(
                "declaration.network-destination.unsafe",
                BehaviorCategory.DECLARATION,
                _MANIFEST_PATH,
                0,
                "A declared network destination is broad or unsafe.",
                "Declare exact credential-free host and port destinations.",
            )
        summaries: list[CapabilityBehaviorSummary] = []
        total_network_calls = 0
        for declaration in manifest_capabilities:
            if not isinstance(declaration, dict):
                raise PackageAuthorityBehaviorValidationError(
                    "package_authority_behavior_manifest_invalid"
                )
            capability_id = declaration.get("id")
            declared_class = declaration.get("class")
            required_permission = declaration.get("permission")
            if not all(
                isinstance(item, str)
                for item in (capability_id, declared_class, required_permission)
            ):
                raise PackageAuthorityBehaviorValidationError(
                    "package_authority_behavior_manifest_invalid"
                )
            capability_id = str(capability_id)
            declared_class = str(declared_class)
            required_permission = str(required_permission)
            module = PackageValidationService._module_name(capability_id)
            path = f"{_SOURCE_PREFIX}{module}.py"
            raw = files.get(path)
            observation = cls._analyze_module(package_digest, path, raw)
            findings.extend(observation.findings)
            declaration_matches = (
                observation.constants.get("CAPABILITY_ID") == capability_id
                and observation.constants.get("CAPABILITY_CLASS") == declared_class
                and observation.handler_count == 1
            )
            permission_matches = (
                observation.constants.get("REQUIRED_PERMISSION") == required_permission
            )
            if not declaration_matches:
                add(
                    "binding.capability.mismatch",
                    BehaviorCategory.DECLARATION,
                    path,
                    0,
                    "Capability module identity, class, or handler binding does not match the "
                    "manifest.",
                    "Bind one async handler and exact reviewed identity and class constants.",
                )
            if not permission_matches:
                add(
                    "binding.permission.mismatch",
                    BehaviorCategory.DECLARATION,
                    path,
                    0,
                    "Capability permission evidence does not match the manifest and module.",
                    "Use one exact least-privilege permission across all declarations.",
                )
            behavior_compatible = not any(
                item.category
                in {
                    BehaviorCategory.PROCESS,
                    BehaviorCategory.FILESYSTEM,
                    BehaviorCategory.DYNAMIC_EXECUTION,
                    BehaviorCategory.AMBIGUOUS,
                }
                for item in observation.findings
            )
            if declared_class in {"C0", "C1"} and (
                BehaviorCategory.MUTATION in observation.categories
                or any(
                    item.category
                    in {
                        BehaviorCategory.PROCESS,
                        BehaviorCategory.FILESYSTEM,
                        BehaviorCategory.DYNAMIC_EXECUTION,
                    }
                    for item in observation.findings
                )
            ):
                behavior_compatible = False
                add(
                    "behavior.risk-class.incompatible",
                    BehaviorCategory.MUTATION,
                    path,
                    0,
                    "Observed behavior is incompatible with the declared low-risk class.",
                    "Remove side effects or complete an independent higher-risk review.",
                )
            total_network_calls += observation.network_calls
            summaries.append(
                CapabilityBehaviorSummary(
                    capability_id=capability_id,
                    declared_class=declared_class,
                    required_permission=required_permission,
                    module_path=path,
                    source_digest=sha256(raw or b"").hexdigest(),
                    observed_categories=tuple(sorted(observation.categories)),
                    network_call_count=observation.network_calls,
                    mutation_call_count=observation.mutation_calls,
                    declaration_matches=declaration_matches,
                    permission_matches=permission_matches,
                    behavior_compatible=behavior_compatible,
                    statically_resolved=not any(
                        item.category is BehaviorCategory.AMBIGUOUS for item in observation.findings
                    ),
                )
            )
        if total_network_calls:
            add(
                "behavior.network.not-enabled",
                BehaviorCategory.NETWORK,
                _MANIFEST_PATH,
                0,
                "Network behavior is observed while network authority is disabled.",
                "Remove network calls or complete explicit bounded network review.",
            )
        return tuple(sorted(summaries, key=lambda item: item.capability_id)), tuple(
            sorted(
                findings, key=lambda item: (item.relative_path, item.line_number, item.rule_code)
            )
        )

    @classmethod
    def _analyze_module(
        cls, package_digest: str, path: str, raw: bytes | None
    ) -> _ModuleObservation:
        observation = _ModuleObservation(path, package_digest)
        if raw is None or len(raw) > 256_000 or b"\x00" in raw:
            observation.add(
                "binding.module.invalid",
                BehaviorCategory.DECLARATION,
                0,
                "Capability source is missing or outside the bounded profile.",
                "Restore one bounded UTF-8 Python capability module.",
            )
            return observation
        try:
            source = raw.decode("utf-8", errors="strict")
            tree = ast.parse(source, filename=path, mode="exec", feature_version=(3, 12))
            analyzer = _BoundedAstAnalyzer(observation)
            analyzer.visit(tree)
        except (UnicodeDecodeError, SyntaxError, ValueError):
            observation.add(
                "behavior.ast.unresolved",
                BehaviorCategory.AMBIGUOUS,
                0,
                "Capability source cannot be resolved within the bounded Python AST profile.",
                "Restore valid bounded Python 3.12 source without excessive complexity.",
            )
        return observation

    @staticmethod
    def _safe_destination(value: str) -> bool:
        if (
            not value
            or len(value) > 253
            or any(token in value for token in ("*", "@", "/", "?", "#"))
        ):
            return False
        parsed = urlsplit(f"//{value}")
        try:
            port = parsed.port
        except ValueError:
            return False
        return bool(parsed.hostname and port and parsed.hostname.casefold() == parsed.hostname)

    @classmethod
    def _checks(
        cls, findings: tuple[AuthorityBehaviorFinding, ...]
    ) -> tuple[AuthorityBehaviorCheck, ...]:
        declaration = tuple(item for item in findings if item.relative_path == _MANIFEST_PATH)
        binding = tuple(item for item in findings if item.rule_code.startswith("binding."))
        implementation = tuple(
            item for item in findings if item not in declaration and item not in binding
        )
        return (
            cls._check(
                "authority-behavior.source.accepted",
                True,
                (),
                "Restore exact passed schema-semantics evidence.",
            ),
            cls._check(
                "authority-behavior.archive.contract",
                True,
                (),
                "Restore exact acquired archive bytes.",
            ),
            cls._check(
                "authority-behavior.declarations.contract",
                not declaration,
                tuple(sorted({item.relative_path for item in declaration})),
                "Resolve every authority declaration finding.",
            ),
            cls._check(
                "authority-behavior.capability.bindings",
                not binding,
                tuple(sorted({item.relative_path for item in binding})),
                "Restore one-to-one capability, class, permission, module, and handler bindings.",
            ),
            cls._check(
                "authority-behavior.implementation.contract",
                not implementation,
                tuple(sorted({item.relative_path for item in implementation})),
                "Resolve every incompatible or ambiguous implementation behavior.",
            ),
        )

    @staticmethod
    def _check(
        code: str, passed: bool, evidence_paths: tuple[str, ...], remediation: str
    ) -> AuthorityBehaviorCheck:
        return AuthorityBehaviorCheck(
            code=code,
            state=AuthorityBehaviorCheckState.PASSED
            if passed
            else AuthorityBehaviorCheckState.FAILED,
            severity=AuthorityBehaviorSeverity.INFORMATIONAL
            if passed
            else AuthorityBehaviorSeverity.ERROR,
            summary="Bounded authority-behavior contract accepted."
            if passed
            else "Bounded authority-behavior contract has blocking findings.",
            evidence_paths=evidence_paths,
            remediation=remediation,
        )

    @classmethod
    def _finding(
        cls,
        package_digest: str,
        rule: str,
        category: BehaviorCategory,
        path: str,
        line: int,
        summary: str,
        remediation: str,
    ) -> AuthorityBehaviorFinding:
        return AuthorityBehaviorFinding(
            rule_code=rule,
            category=category,
            severity=AuthorityBehaviorSeverity.ERROR,
            relative_path=path,
            line_number=max(0, line),
            evidence_fingerprint=cls._digest(
                {"package_digest": package_digest, "path": path, "line": max(0, line), "rule": rule}
            ),
            summary=summary,
            remediation=remediation,
        )

    @classmethod
    def _canonical_payload(
        cls,
        *,
        source: ConnectorPackageSchemaSemanticsValidation,
        actor_id: str,
        validation_profile: str,
        capabilities: tuple[CapabilityBehaviorSummary, ...],
        capability_set_digest: str,
        findings: tuple[AuthorityBehaviorFinding, ...],
        finding_set_digest: str,
        behavior_validation_digest: str,
        checks: tuple[AuthorityBehaviorCheck, ...],
        outcome: AuthorityBehaviorOutcome,
    ) -> dict[str, object]:
        return {
            "lifecycle": AuthorityBehaviorLifecycle.VALIDATING.value,
            "outcome": outcome.value,
            "source_schema_semantics_validation_id": source.validation_id,
            "source_schema_semantics_validation_digest": source.canonical_digest,
            "source_content_policy_scan_id": source.source_content_policy_scan_id,
            "source_inventory_id": source.source_inventory_id,
            "source_validation_id": source.source_validation_id,
            "source_acquisition_id": source.source_acquisition_id,
            "source_handoff_id": source.source_handoff_id,
            "source_project_id": source.source_project_id,
            "source_acquired_by": source.source_acquired_by,
            "source_manifest_validated_by": source.source_manifest_validated_by,
            "source_inventoried_by": source.source_inventoried_by,
            "source_content_scanned_by": source.source_content_scanned_by,
            "source_schema_validated_by": source.validated_by,
            "source_custodied_by": source.source_custodied_by,
            "source_domain_reviewed_by": source.source_domain_reviewed_by,
            "source_security_reviewed_by": source.source_security_reviewed_by,
            "source_lab_operated_by": source.source_lab_operated_by,
            "organization_id": source.organization_id,
            "environment_id": source.environment_id,
            "validated_by": actor_id,
            "validation_profile": validation_profile,
            "analyzer_version": AUTHORITY_BEHAVIOR_ANALYZER,
            "package_digest": source.package_digest,
            "package_size_bytes": source.package_size_bytes,
            "inventory_digest": source.inventory_digest,
            "semantic_validation_digest": source.semantic_validation_digest,
            "capabilities": cls._capability_payload(capabilities),
            "capability_set_digest": capability_set_digest,
            "findings": cls._finding_payload(findings),
            "finding_set_digest": finding_set_digest,
            "behavior_validation_digest": behavior_validation_digest,
            "checks": cls._check_payload(checks),
            "limitations": AUTHORITY_BEHAVIOR_LIMITATIONS,
            "promotion_blocked": outcome is AuthorityBehaviorOutcome.FAILED,
        }

    @classmethod
    def _canonical_payload_from_validation(
        cls, validation: ConnectorPackageAuthorityBehaviorValidation
    ) -> dict[str, object]:
        fields = (
            "source_schema_semantics_validation_id",
            "source_schema_semantics_validation_digest",
            "source_content_policy_scan_id",
            "source_inventory_id",
            "source_validation_id",
            "source_acquisition_id",
            "source_handoff_id",
            "source_project_id",
            "source_acquired_by",
            "source_manifest_validated_by",
            "source_inventoried_by",
            "source_content_scanned_by",
            "source_schema_validated_by",
            "source_custodied_by",
            "source_domain_reviewed_by",
            "source_security_reviewed_by",
            "source_lab_operated_by",
            "organization_id",
            "environment_id",
            "validated_by",
            "validation_profile",
            "analyzer_version",
            "package_digest",
            "package_size_bytes",
            "inventory_digest",
            "semantic_validation_digest",
            "capability_set_digest",
            "finding_set_digest",
            "behavior_validation_digest",
            "limitations",
            "promotion_blocked",
        )
        return {
            "lifecycle": validation.lifecycle.value,
            "outcome": validation.outcome.value,
            **{field: getattr(validation, field) for field in fields},
            "capabilities": cls._capability_payload(validation.capabilities),
            "findings": cls._finding_payload(validation.findings),
            "checks": cls._check_payload(validation.checks),
        }

    @classmethod
    def _verify_validation(cls, validation: ConnectorPackageAuthorityBehaviorValidation) -> None:
        if (
            cls._digest(cls._canonical_payload_from_validation(validation))
            != validation.canonical_digest
        ):
            raise PackageAuthorityBehaviorValidationError(
                "package_authority_behavior_integrity_failed"
            )

    @staticmethod
    def _capability_payload(
        items: tuple[CapabilityBehaviorSummary, ...],
    ) -> list[dict[str, object]]:
        return [
            {
                "capability_id": item.capability_id,
                "declared_class": item.declared_class,
                "required_permission": item.required_permission,
                "module_path": item.module_path,
                "source_digest": item.source_digest,
                "observed_categories": [value.value for value in item.observed_categories],
                "network_call_count": item.network_call_count,
                "mutation_call_count": item.mutation_call_count,
                "declaration_matches": item.declaration_matches,
                "permission_matches": item.permission_matches,
                "behavior_compatible": item.behavior_compatible,
                "statically_resolved": item.statically_resolved,
            }
            for item in items
        ]

    @staticmethod
    def _finding_payload(items: tuple[AuthorityBehaviorFinding, ...]) -> list[dict[str, object]]:
        return [
            {
                "rule_code": item.rule_code,
                "category": item.category.value,
                "severity": item.severity.value,
                "relative_path": item.relative_path,
                "line_number": item.line_number,
                "evidence_fingerprint": item.evidence_fingerprint,
                "summary": item.summary,
                "remediation": item.remediation,
            }
            for item in items
        ]

    @staticmethod
    def _check_payload(items: tuple[AuthorityBehaviorCheck, ...]) -> list[dict[str, object]]:
        return [
            {
                "code": item.code,
                "state": item.state.value,
                "severity": item.severity.value,
                "summary": item.summary,
                "evidence_paths": list(item.evidence_paths),
                "remediation": item.remediation,
            }
            for item in items
        ]

    @staticmethod
    def _verify_source(source: ConnectorPackageSchemaSemanticsValidation) -> None:
        try:
            PackageSchemaSemanticsValidationService._verify_validation(source)
        except Exception as error:
            raise PackageAuthorityBehaviorValidationError(
                "package_authority_behavior_source_integrity_failed"
            ) from error
        if (
            source.outcome is not SchemaSemanticsOutcome.PASSED
            or source.promotion_blocked
            or source.validation_profile != SCHEMA_SEMANTICS_PROFILE
            or source.validator_version != SCHEMA_SEMANTICS_VALIDATOR
            or not source.schema_semantic_validation_completed
            or source.permission_behavior_validation_completed
            or source.connector_rejected
            or source.connector_registered
            or source.runtime_trust_granted
            or source.execution_authorized
            or source.infrastructure_mutation_performed
        ):
            raise PackageAuthorityBehaviorValidationError(
                "package_authority_behavior_source_unsupported"
            )

    @staticmethod
    def _verify_inventory_binding(
        source: ConnectorPackageSchemaSemanticsValidation,
        inventory: ConnectorPackageSupplyChainInventory,
    ) -> None:
        try:
            PackageSupplyChainInventoryService._verify_inventory(inventory)
        except Exception as error:
            raise PackageAuthorityBehaviorValidationError(
                "package_authority_behavior_source_integrity_failed"
            ) from error
        if (
            inventory.inventory_id != source.source_inventory_id
            or inventory.canonical_digest != source.source_inventory_digest
            or inventory.package_digest != source.package_digest
            or inventory.package_size_bytes != source.package_size_bytes
            or inventory.inventory_digest != source.inventory_digest
            or inventory.organization_id != source.organization_id
            or inventory.environment_id != source.environment_id
        ):
            raise PackageAuthorityBehaviorValidationError(
                "package_authority_behavior_source_integrity_failed"
            )

    @staticmethod
    def _verify_acquisition_binding(
        source: ConnectorPackageSchemaSemanticsValidation,
        acquisition: ConnectorPackageAcquisition,
    ) -> None:
        try:
            PackageAcquisitionService._verify_acquisition(acquisition)
        except Exception as error:
            raise PackageAuthorityBehaviorValidationError(
                "package_authority_behavior_source_integrity_failed"
            ) from error
        if (
            acquisition.acquisition_id != source.source_acquisition_id
            or acquisition.canonical_digest != source.source_acquisition_digest
            or acquisition.package_digest != source.package_digest
            or acquisition.package_size_bytes != source.package_size_bytes
            or acquisition.organization_id != source.organization_id
            or acquisition.environment_id != source.environment_id
        ):
            raise PackageAuthorityBehaviorValidationError(
                "package_authority_behavior_source_integrity_failed"
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
        source_items = tuple(
            item for item in inventory.files if item.content_class is PackageContentClass.SOURCE
        )
        if actual != expected or not source_items:
            raise PackageAuthorityBehaviorValidationError(
                "package_authority_behavior_inventory_mismatch"
            )

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
            raise PackageAuthorityBehaviorValidationError(
                "package_authority_behavior_enterprise_human_mfa_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise PackageAuthorityBehaviorValidationError("package_authority_behavior_not_found")

    @classmethod
    def _require_separation(
        cls, actor: AuthenticatedSubject, source: ConnectorPackageSchemaSemanticsValidation
    ) -> None:
        if actor.subject_id in cls._source_actors(source):
            raise PackageAuthorityBehaviorValidationError("package_authority_behavior_not_found")

    @staticmethod
    def _source_actors(source: ConnectorPackageSchemaSemanticsValidation) -> set[str]:
        return {
            source.source_acquired_by,
            source.source_manifest_validated_by,
            source.source_inventoried_by,
            source.source_content_scanned_by,
            source.validated_by,
            source.source_custodied_by,
            source.source_domain_reviewed_by,
            source.source_security_reviewed_by,
            source.source_lab_operated_by,
        }

    @staticmethod
    def _validation_source_actors(
        validation: ConnectorPackageAuthorityBehaviorValidation,
    ) -> set[str]:
        return {
            validation.source_acquired_by,
            validation.source_manifest_validated_by,
            validation.source_inventoried_by,
            validation.source_content_scanned_by,
            validation.source_schema_validated_by,
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
        validation: ConnectorPackageAuthorityBehaviorValidation,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.package-authority-behavior-validation",
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
                resource_type="resource.connector.package-authority-behavior-validation",
                scope_reference=validation.validation_id,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=validation.idempotency_key,
                target_metadata=(
                    ("validation_id", validation.validation_id),
                    (
                        "source_schema_semantics_validation_id",
                        validation.source_schema_semantics_validation_id,
                    ),
                    ("package_digest", validation.package_digest),
                    ("validation_outcome", validation.outcome.value),
                    ("finding_count", str(len(validation.findings))),
                ),
            )
        )
