from __future__ import annotations

import ast
import asyncio
import json
import re
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import PurePosixPath
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.connectors.application.acquisition import PackageAcquisitionService
from atlas.modules.connectors.application.authority_behavior_validation import (
    AUTHORITY_BEHAVIOR_ANALYZER,
    AUTHORITY_BEHAVIOR_PROFILE,
    PackageAuthorityBehaviorValidationService,
)
from atlas.modules.connectors.application.static_dependency_analysis_ports import (
    PackageStaticDependencyAnalysisError,
    PackageStaticDependencyAnalysisRepository,
    StaticDependencyAcquisitionSource,
    StaticDependencyArchiveSource,
    StaticDependencyAuthorityBehaviorSource,
    StaticDependencyInventorySource,
)
from atlas.modules.connectors.application.supply_chain_inventory import (
    PackageSupplyChainInventoryService,
)
from atlas.modules.connectors.application.validation_intake import PackageValidationService
from atlas.modules.connectors.domain.acquisition import ConnectorPackageAcquisition
from atlas.modules.connectors.domain.authority_behavior_validation import (
    AuthorityBehaviorOutcome,
    ConnectorPackageAuthorityBehaviorValidation,
)
from atlas.modules.connectors.domain.static_dependency_analysis import (
    ConnectorPackageStaticDependencyAnalysis,
    DependencyHygieneSummary,
    StaticDependencyCategory,
    StaticDependencyCheck,
    StaticDependencyCheckState,
    StaticDependencyFinding,
    StaticDependencyLifecycle,
    StaticDependencyOutcome,
    StaticDependencySeverity,
    StaticSourceSummary,
)
from atlas.modules.connectors.domain.supply_chain_inventory import (
    ConnectorPackageSupplyChainInventory,
    DependencyKind,
    PackageContentClass,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

STATIC_DEPENDENCY_CREATE_PERMISSION = "connectors.package-static-dependency-analyses.create"
STATIC_DEPENDENCY_READ_PERMISSION = "connectors.package-static-dependency-analyses.read"
STATIC_DEPENDENCY_SCHEMA = "atlas.connector-package-static-dependency-analysis.v1"
STATIC_DEPENDENCY_PROFILE = "atlas.connector-static-dependency.python312.v1"
STATIC_DEPENDENCY_ANALYZER = "atlas.connector-static-dependency-analyzer.v1"

STATIC_DEPENDENCY_LIMITATIONS = (
    "This report covers bounded Python structure, imports, and dependency declaration "
    "hygiene only.",
    "Source, tokens, literals, import targets, dependency values, URLs, and indexes are "
    "not retained.",
    "Vulnerability, malware, license, contract, runner, self-test, and lab validation "
    "remain incomplete.",
    "Rejection, registration, approval, installation, enablement, runtime trust, execution, and "
    "deployment remain prohibited.",
)

_SOURCE_PREFIX = "src/atlas_generated_connector/"
_PACKAGE_ROOT = "atlas_generated_connector"
_PYPROJECT_PATH = "pyproject.toml"
_APPROVED_STDLIB_ROOTS = frozenset(
    {
        "abc",
        "collections",
        "contextlib",
        "dataclasses",
        "datetime",
        "decimal",
        "enum",
        "functools",
        "hashlib",
        "itertools",
        "json",
        "math",
        "pathlib",
        "re",
        "statistics",
        "time",
        "types",
        "typing",
        "uuid",
    }
)
_EXACT_RUNTIME = re.compile(r"^==[0-9]+(?:\.[0-9]+){1,3}$")
_BOUNDED_BUILD = re.compile(r"^>=[0-9]+(?:\.[0-9]+){0,3},<[0-9]+(?:\.[0-9]+){0,3}$")


class _FindingCollector:
    def __init__(self, package_digest: str) -> None:
        self.package_digest = package_digest
        self.items: list[StaticDependencyFinding] = []

    def add(
        self,
        rule: str,
        category: StaticDependencyCategory,
        path: str,
        line: int,
        summary: str,
        remediation: str,
    ) -> None:
        if len(self.items) >= 500:
            raise ValueError("finding budget exceeded")
        self.items.append(
            StaticDependencyFinding(
                rule_code=rule,
                category=category,
                severity=StaticDependencySeverity.ERROR,
                relative_path=path,
                line_number=max(0, line),
                evidence_fingerprint=PackageStaticDependencyAnalysisService._digest(
                    {
                        "package_digest": self.package_digest,
                        "path": path,
                        "line": max(0, line),
                        "rule": rule,
                    }
                ),
                summary=summary,
                remediation=remediation,
            )
        )


class _SourceAnalyzer(ast.NodeVisitor):
    def __init__(
        self, *, path: str, module: str, package_digest: str, collector: _FindingCollector
    ) -> None:
        self.path = path
        self.module = module
        self.package_digest = package_digest
        self.collector = collector
        self.node_count = 0
        self.function_count = 0
        self.imports: list[tuple[str, int, int]] = []
        self._function_branches: list[int] = []
        self._nesting = 0

    def inspect(self, tree: ast.Module) -> None:
        self._inspect_top_level(tree)
        self.visit(tree)

    def generic_visit(self, node: ast.AST) -> None:
        self.node_count += 1
        if self.node_count > 30_000:
            raise ValueError("AST node budget exceeded")
        nested = isinstance(
            node,
            (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try, ast.Match),
        )
        if nested:
            self._nesting += 1
            if self._nesting > 8:
                self.collector.add(
                    "static.complexity.nesting",
                    StaticDependencyCategory.COMPLEXITY,
                    self.path,
                    getattr(node, "lineno", 0),
                    "Source nesting exceeds the bounded review profile.",
                    "Split the logic into smaller explicitly typed functions.",
                )
        super().generic_visit(node)
        if nested:
            self._nesting -= 1

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append((alias.name, 0, node.lineno))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if any(alias.name == "*" for alias in node.names):
            self.collector.add(
                "static.import.wildcard",
                StaticDependencyCategory.IMPORT_GRAPH,
                self.path,
                node.lineno,
                "Wildcard import is not allowed by the bounded profile.",
                "Import explicit reviewed names.",
            )
        self.imports.append((node.module or "", node.level, node.lineno))
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.function_count += 1
        if self.function_count > 100:
            raise ValueError("function budget exceeded")
        if not node.name.startswith("_") and not self._fully_annotated(node):
            self.collector.add(
                "static.type.public-annotation",
                StaticDependencyCategory.TYPE_CONTRACT,
                self.path,
                node.lineno,
                "Public function annotations are incomplete.",
                "Annotate every public parameter and return value.",
            )
        self._function_branches.append(0)
        self.generic_visit(node)
        branches = self._function_branches.pop()
        if branches > 20:
            self.collector.add(
                "static.complexity.branch-budget",
                StaticDependencyCategory.COMPLEXITY,
                self.path,
                node.lineno,
                "Function branch count exceeds the bounded review profile.",
                "Split the function into smaller deterministic units.",
            )

    def visit_If(self, node: ast.If) -> None:
        self._branch(node)

    def visit_For(self, node: ast.For) -> None:
        self._branch(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._branch(node)

    def visit_While(self, node: ast.While) -> None:
        self._branch(node)

    def visit_Match(self, node: ast.Match) -> None:
        if self._function_branches:
            self._function_branches[-1] += len(node.cases)
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self.collector.add(
                "static.exception.bare",
                StaticDependencyCategory.EXCEPTION_HANDLING,
                self.path,
                node.lineno,
                "Bare exception handling is not allowed.",
                "Catch an explicit bounded exception type.",
            )
        if not node.body or all(isinstance(item, ast.Pass) for item in node.body):
            self.collector.add(
                "static.exception.suppressed",
                StaticDependencyCategory.EXCEPTION_HANDLING,
                self.path,
                node.lineno,
                "Exception handling silently suppresses failure.",
                "Fail closed or return typed bounded failure evidence.",
            )
        self.generic_visit(node)

    def visit_Global(self, node: ast.Global) -> None:
        self.collector.add(
            "static.state.global-mutation",
            StaticDependencyCategory.STATE_MANAGEMENT,
            self.path,
            node.lineno,
            "Global state mutation is not allowed.",
            "Use request-local immutable state.",
        )
        self.generic_visit(node)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.collector.add(
            "static.state.nonlocal-mutation",
            StaticDependencyCategory.STATE_MANAGEMENT,
            self.path,
            node.lineno,
            "Nonlocal state mutation is not allowed.",
            "Use explicit immutable function inputs and outputs.",
        )
        self.generic_visit(node)

    def _branch(self, node: ast.AST) -> None:
        if self._function_branches:
            self._function_branches[-1] += 1
        self.generic_visit(node)

    def _inspect_top_level(self, tree: ast.Module) -> None:
        for index, node in enumerate(tree.body):
            if isinstance(
                node,
                (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            ):
                continue
            if (
                isinstance(node, ast.Expr)
                and index == 0
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                continue
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = node.value
                if value is not None and self._literal(value):
                    continue
                self.collector.add(
                    "static.state.mutable-top-level",
                    StaticDependencyCategory.STATE_MANAGEMENT,
                    self.path,
                    getattr(node, "lineno", 0),
                    "Top-level state is not an immutable literal declaration.",
                    "Move mutable state into request-local execution scope.",
                )
                continue
            self.collector.add(
                "static.structure.top-level-execution",
                StaticDependencyCategory.SOURCE_STRUCTURE,
                self.path,
                getattr(node, "lineno", 0),
                "Executable top-level source is not allowed.",
                "Keep top-level source limited to imports and declarations.",
            )

    @classmethod
    def _literal(cls, node: ast.AST) -> bool:
        if isinstance(node, ast.Constant):
            return True
        if isinstance(node, ast.Tuple):
            return all(cls._literal(item) for item in node.elts)
        return False

    @staticmethod
    def _fully_annotated(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        args = [item for item in args if item.arg not in {"self", "cls"}]
        return bool(
            node.returns is not None
            and all(item.annotation is not None for item in args)
            and (node.args.vararg is None or node.args.vararg.annotation is not None)
            and (node.args.kwarg is None or node.args.kwarg.annotation is not None)
        )


class PackageStaticDependencyAnalysisService:
    def __init__(
        self,
        *,
        repository: PackageStaticDependencyAnalysisRepository,
        authority_behavior_source: StaticDependencyAuthorityBehaviorSource,
        inventory_source: StaticDependencyInventorySource,
        acquisition_source: StaticDependencyAcquisitionSource,
        archive_source: StaticDependencyArchiveSource,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._authority_behavior_source = authority_behavior_source
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
        source_authority_behavior_validation_id: str,
        source_authority_behavior_validation_digest: str,
        package_digest: str,
        analysis_profile: str,
        acknowledged_offline_static_dependency_limitations: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorPackageStaticDependencyAnalysis:
        self._require_enterprise_human(actor)
        if not acknowledged_offline_static_dependency_limitations:
            raise PackageStaticDependencyAnalysisError(
                "package_static_dependency_acknowledgement_required"
            )
        if analysis_profile != STATIC_DEPENDENCY_PROFILE:
            raise PackageStaticDependencyAnalysisError(
                "package_static_dependency_profile_unsupported"
            )
        if not 8 <= len(idempotency_key) <= 128:
            raise PackageStaticDependencyAnalysisError(
                "package_static_dependency_idempotency_key_invalid"
            )
        fingerprint = self._digest(
            {
                "source_authority_behavior_validation_id": (
                    source_authority_behavior_validation_id
                ),
                "source_authority_behavior_validation_digest": (
                    source_authority_behavior_validation_digest
                ),
                "package_digest": package_digest,
                "analysis_profile": analysis_profile,
                "acknowledged_offline_static_dependency_limitations": True,
                "analyzed_by": actor.subject_id,
            }
        )
        replay = await self._repository.get_by_create_key(
            analyzed_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if replay is not None:
            self._verify_analysis(replay)
            if replay.request_fingerprint == fingerprint:
                return replace(replay, reused=True)
            raise PackageStaticDependencyAnalysisError(
                "package_static_dependency_idempotency_conflict"
            )

        source = await self._authority_behavior_source.get_by_id(
            validation_id=source_authority_behavior_validation_id
        )
        if source is None:
            raise PackageStaticDependencyAnalysisError("package_static_dependency_source_not_found")
        self._require_scope(actor, source.organization_id, source.environment_id)
        self._require_separation(actor, source)
        self._verify_source(source)
        if (
            source.canonical_digest != source_authority_behavior_validation_digest
            or source.package_digest != package_digest
        ):
            raise PackageStaticDependencyAnalysisError("package_static_dependency_source_not_found")
        inventory = await self._inventory_source.get_by_id(inventory_id=source.source_inventory_id)
        if inventory is None:
            raise PackageStaticDependencyAnalysisError(
                "package_static_dependency_source_integrity_failed"
            )
        self._verify_inventory_binding(source, inventory)
        acquisition = await self._acquisition_source.get_by_id(
            acquisition_id=source.source_acquisition_id
        )
        if acquisition is None:
            raise PackageStaticDependencyAnalysisError(
                "package_static_dependency_source_integrity_failed"
            )
        self._verify_acquisition_binding(source, acquisition)
        try:
            content = await self._archive_source.read(
                package_digest=package_digest, size_bytes=source.package_size_bytes
            )
            files, _ = PackageValidationService._verify_archive(acquisition, content)
            self._verify_inventory_files(inventory, files)
        except PackageStaticDependencyAnalysisError:
            raise
        except Exception as error:
            raise PackageStaticDependencyAnalysisError(
                "package_static_dependency_archive_integrity_failed"
            ) from error

        try:
            source_summary, dependency_summary, findings = self._analyze(
                package_digest, files, inventory
            )
        except PackageStaticDependencyAnalysisError:
            raise
        except Exception as error:
            raise PackageStaticDependencyAnalysisError(
                "package_static_dependency_analysis_failed"
            ) from error
        checks = self._checks(findings)
        outcome = (
            StaticDependencyOutcome.PASSED
            if all(item.state is StaticDependencyCheckState.PASSED for item in checks)
            else StaticDependencyOutcome.FAILED
        )
        finding_set_digest = self._digest(self._finding_payload(findings))
        analysis_digest = self._digest(
            {
                "analyzer_version": STATIC_DEPENDENCY_ANALYZER,
                "package_digest": package_digest,
                "source_set_digest": source_summary.source_set_digest,
                "dependency_set_digest": dependency_summary.dependency_set_digest,
                "finding_set_digest": finding_set_digest,
            }
        )
        payload = self._canonical_payload(
            source=source,
            actor_id=actor.subject_id,
            analysis_profile=analysis_profile,
            source_summary=source_summary,
            dependency_summary=dependency_summary,
            findings=findings,
            finding_set_digest=finding_set_digest,
            analysis_digest=analysis_digest,
            checks=checks,
            outcome=outcome,
        )
        canonical_digest = self._digest(payload)
        analysis = ConnectorPackageStaticDependencyAnalysis(
            analysis_id=f"connector-static-dependency-analysis.{canonical_digest[:24]}",
            schema_version=STATIC_DEPENDENCY_SCHEMA,
            version=1,
            lifecycle=StaticDependencyLifecycle.VALIDATING,
            outcome=outcome,
            source_authority_behavior_validation_id=source.validation_id,
            source_authority_behavior_validation_digest=source.canonical_digest,
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
            source_authority_validated_by=source.validated_by,
            source_custodied_by=source.source_custodied_by,
            source_domain_reviewed_by=source.source_domain_reviewed_by,
            source_security_reviewed_by=source.source_security_reviewed_by,
            source_lab_operated_by=source.source_lab_operated_by,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            analyzed_by=actor.subject_id,
            analysis_profile=analysis_profile,
            analyzer_version=STATIC_DEPENDENCY_ANALYZER,
            package_digest=source.package_digest,
            package_size_bytes=source.package_size_bytes,
            inventory_digest=source.inventory_digest,
            source_summary=source_summary,
            dependency_summary=dependency_summary,
            findings=findings,
            finding_set_digest=finding_set_digest,
            analysis_digest=analysis_digest,
            checks=checks,
            limitations=STATIC_DEPENDENCY_LIMITATIONS,
            promotion_blocked=outcome is StaticDependencyOutcome.FAILED,
            canonical_digest=canonical_digest,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            analyzed_at=self._clock(),
        )
        async with self._mutation_lock:
            existing = await self._repository.get_by_source_validation(
                source_authority_behavior_validation_id=source.validation_id
            )
            if existing is not None:
                self._verify_analysis(existing)
                if (
                    existing.analyzed_by == actor.subject_id
                    and existing.idempotency_key == idempotency_key
                    and existing.request_fingerprint == fingerprint
                ):
                    return replace(existing, reused=True)
                raise PackageStaticDependencyAnalysisError("package_static_dependency_exists")
            await self._audit(
                actor=actor,
                correlation_id=correlation_id,
                permission_id=STATIC_DEPENDENCY_CREATE_PERMISSION,
                result_code=f"connector_static_dependency_analysis_{outcome.value}",
                analysis=analysis,
            )
            if not await self._repository.add(analysis):
                raced = await self._repository.get_by_create_key(
                    analyzed_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    raise PackageStaticDependencyAnalysisError("package_static_dependency_conflict")
                self._verify_analysis(raced)
                return replace(raced, reused=True)
        return analysis

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        analysis_id: str,
        correlation_id: str,
    ) -> ConnectorPackageStaticDependencyAnalysis:
        self._require_enterprise_human(actor)
        analysis = await self._repository.get_by_id(analysis_id=analysis_id)
        if analysis is None:
            raise PackageStaticDependencyAnalysisError("package_static_dependency_not_found")
        self._require_scope(actor, analysis.organization_id, analysis.environment_id)
        if actor.subject_id in self._analysis_source_actors(analysis):
            raise PackageStaticDependencyAnalysisError("package_static_dependency_not_found")
        self._verify_analysis(analysis)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=STATIC_DEPENDENCY_READ_PERMISSION,
            result_code="connector_static_dependency_analysis_read",
            analysis=analysis,
        )
        return analysis

    async def close(self) -> None:
        await self._repository.close()

    @property
    def repository(self) -> PackageStaticDependencyAnalysisRepository:
        return self._repository

    @classmethod
    def _analyze(
        cls,
        package_digest: str,
        files: dict[str, bytes],
        inventory: ConnectorPackageSupplyChainInventory,
    ) -> tuple[
        StaticSourceSummary,
        DependencyHygieneSummary,
        tuple[StaticDependencyFinding, ...],
    ]:
        collector = _FindingCollector(package_digest)
        source_evidence = tuple(
            item for item in inventory.files if item.content_class is PackageContentClass.SOURCE
        )
        if not source_evidence or len(source_evidence) > 500:
            raise PackageStaticDependencyAnalysisError("package_static_dependency_source_invalid")
        module_paths = {
            item.relative_path: cls._module_name(item.relative_path) for item in source_evidence
        }
        if len(set(module_paths.values())) != len(module_paths):
            raise PackageStaticDependencyAnalysisError("package_static_dependency_source_invalid")
        known_modules = set(module_paths.values())
        analyzers: list[_SourceAnalyzer] = []
        for evidence in source_evidence:
            raw = files.get(evidence.relative_path)
            if raw is None or len(raw) > 200_000 or b"\x00" in raw:
                raise PackageStaticDependencyAnalysisError(
                    "package_static_dependency_source_invalid"
                )
            try:
                source_text = raw.decode("utf-8", errors="strict")
                tree = ast.parse(source_text, filename=evidence.relative_path, mode="exec")
            except (UnicodeDecodeError, SyntaxError) as error:
                raise PackageStaticDependencyAnalysisError(
                    "package_static_dependency_source_invalid"
                ) from error
            analyzer = _SourceAnalyzer(
                path=evidence.relative_path,
                module=module_paths[evidence.relative_path],
                package_digest=package_digest,
                collector=collector,
            )
            analyzer.inspect(tree)
            if len(analyzer.imports) > 100:
                raise PackageStaticDependencyAnalysisError(
                    "package_static_dependency_source_invalid"
                )
            analyzers.append(analyzer)

        runtime_dependencies = tuple(
            item for item in inventory.dependencies if item.kind is DependencyKind.RUNTIME
        )
        build_dependencies = tuple(
            item for item in inventory.dependencies if item.kind is DependencyKind.BUILD
        )
        runtime_roots = {cls._dependency_root(item.name) for item in runtime_dependencies}
        external_roots: set[str] = set()
        unresolved_count = 0
        import_count = 0
        for analyzer in analyzers:
            for imported, level, line in analyzer.imports:
                import_count += 1
                state, root = cls._classify_import(
                    analyzer.module, imported, level, known_modules, runtime_roots
                )
                if state == "external":
                    external_roots.add(root)
                elif state == "unresolved":
                    unresolved_count += 1
                    collector.add(
                        "static.import.unresolved",
                        StaticDependencyCategory.IMPORT_GRAPH,
                        analyzer.path,
                        line,
                        "Import cannot be reconciled to package or dependency metadata.",
                        "Use an approved standard-library, internal, or declared runtime import.",
                    )

        normalized, metadata_valid = PackageSupplyChainInventoryService._inventory_dependencies(
            files
        )
        metadata_consistent = bool(metadata_valid and normalized == inventory.dependencies)
        if not metadata_consistent:
            collector.add(
                "dependency.metadata.inconsistent",
                StaticDependencyCategory.DEPENDENCY_METADATA,
                _PYPROJECT_PATH,
                0,
                "Project dependency metadata does not match the accepted inventory.",
                "Restore exact reviewed project metadata and regenerate the inventory.",
            )
        deterministic_constraints = True
        for dependency in runtime_dependencies:
            if _EXACT_RUNTIME.fullmatch(dependency.version_constraint) is None:
                deterministic_constraints = False
                collector.add(
                    "dependency.runtime.not-exact",
                    StaticDependencyCategory.DEPENDENCY_METADATA,
                    _PYPROJECT_PATH,
                    0,
                    "Runtime dependency is not exact-pinned.",
                    "Use an exact stable runtime version and regenerate reviewed evidence.",
                )
        for dependency in build_dependencies:
            if _BOUNDED_BUILD.fullmatch(dependency.version_constraint) is None:
                deterministic_constraints = False
                collector.add(
                    "dependency.build.not-bounded",
                    StaticDependencyCategory.DEPENDENCY_METADATA,
                    _PYPROJECT_PATH,
                    0,
                    "Build dependency does not have bounded lower and upper versions.",
                    "Use reviewed lower and exclusive upper build bounds.",
                )
        lock_required = bool(runtime_dependencies)
        if lock_required and not inventory.dependency_lock_present:
            deterministic_constraints = False
            collector.add(
                "dependency.lock.required",
                StaticDependencyCategory.DEPENDENCY_LOCK,
                _PYPROJECT_PATH,
                0,
                "Runtime dependencies require a deterministic hashed lock artifact.",
                "Add a reviewed lock artifact and regenerate package inventory evidence.",
            )
        imports_reconciled = unresolved_count == 0 and external_roots == runtime_roots
        if external_roots != runtime_roots:
            collector.add(
                "dependency.import-set.mismatch",
                StaticDependencyCategory.DEPENDENCY_METADATA,
                _PYPROJECT_PATH,
                0,
                "Runtime imports and declared dependencies do not reconcile.",
                "Align reviewed runtime imports and exact dependency declarations.",
            )

        source_set_digest = cls._digest(
            [
                {"path": item.relative_path, "digest": item.digest, "size": item.size_bytes}
                for item in source_evidence
            ]
        )
        source_summary = StaticSourceSummary(
            source_file_count=len(source_evidence),
            module_count=len(known_modules),
            function_count=sum(item.function_count for item in analyzers),
            import_count=import_count,
            external_import_count=len(external_roots),
            unresolved_import_count=unresolved_count,
            source_set_digest=source_set_digest,
        )
        dependency_summary = DependencyHygieneSummary(
            runtime_dependency_count=len(runtime_dependencies),
            build_dependency_count=len(build_dependencies),
            imported_dependency_count=len(external_roots),
            dependency_lock_present=inventory.dependency_lock_present,
            dependency_lock_required=lock_required,
            dependency_set_digest=inventory.dependency_set_digest,
            metadata_consistent=metadata_consistent,
            imports_reconciled=imports_reconciled,
            deterministic_constraints=deterministic_constraints,
        )
        findings = tuple(
            sorted(
                collector.items,
                key=lambda item: (item.relative_path, item.line_number, item.rule_code),
            )
        )
        return source_summary, dependency_summary, findings

    @staticmethod
    def _module_name(path: str) -> str:
        if not path.startswith(_SOURCE_PREFIX) or not path.endswith(".py"):
            raise PackageStaticDependencyAnalysisError("package_static_dependency_source_invalid")
        relative = path.removeprefix("src/").removesuffix(".py")
        parts = list(PurePosixPath(relative).parts)
        if parts[-1] == "__init__":
            parts.pop()
        if not parts or any(not part.isidentifier() for part in parts):
            raise PackageStaticDependencyAnalysisError("package_static_dependency_source_invalid")
        return ".".join(parts)

    @classmethod
    def _classify_import(
        cls,
        current_module: str,
        imported: str,
        level: int,
        known_modules: set[str],
        runtime_roots: set[str],
    ) -> tuple[str, str]:
        if level:
            package_parts = current_module.split(".")
            if not any(item.startswith(f"{current_module}.") for item in known_modules):
                package_parts = package_parts[:-1]
            keep = len(package_parts) - level + 1
            if keep < 1:
                return "unresolved", ""
            target = ".".join([*package_parts[:keep], *([imported] if imported else [])])
            return (
                ("internal", "")
                if cls._internal_exists(target, known_modules)
                else ("unresolved", "")
            )
        root = imported.split(".", 1)[0]
        if not root:
            return "unresolved", ""
        if root == _PACKAGE_ROOT:
            return (
                ("internal", "")
                if cls._internal_exists(imported, known_modules)
                else ("unresolved", "")
            )
        if root in _APPROVED_STDLIB_ROOTS:
            return "stdlib", ""
        if root in runtime_roots:
            return "external", root
        return "unresolved", root

    @staticmethod
    def _internal_exists(target: str, known_modules: set[str]) -> bool:
        return target in known_modules or any(
            item.startswith(f"{target}.") for item in known_modules
        )

    @staticmethod
    def _dependency_root(name: str) -> str:
        return name.casefold().replace("-", "_").replace(".", "_")

    @classmethod
    def _checks(
        cls, findings: tuple[StaticDependencyFinding, ...]
    ) -> tuple[StaticDependencyCheck, ...]:
        source_categories = {
            StaticDependencyCategory.SOURCE_STRUCTURE,
            StaticDependencyCategory.EXCEPTION_HANDLING,
            StaticDependencyCategory.STATE_MANAGEMENT,
            StaticDependencyCategory.TYPE_CONTRACT,
            StaticDependencyCategory.COMPLEXITY,
        }
        return (
            cls._check(
                "static-dependency.source.accepted",
                True,
                (),
                "Restore exact passed source evidence.",
            ),
            cls._check(
                "static-dependency.archive.contract",
                True,
                (),
                "Restore exact immutable archive bytes.",
            ),
            cls._check(
                "static-dependency.source.structure",
                not any(item.category in source_categories for item in findings),
                tuple(
                    sorted(
                        {
                            item.relative_path
                            for item in findings
                            if item.category in source_categories
                        }
                    )
                ),
                "Resolve blocking source-structure findings.",
            ),
            cls._check(
                "static-dependency.import.graph",
                not any(
                    item.category is StaticDependencyCategory.IMPORT_GRAPH for item in findings
                ),
                tuple(
                    sorted(
                        {
                            item.relative_path
                            for item in findings
                            if item.category is StaticDependencyCategory.IMPORT_GRAPH
                        }
                    )
                ),
                "Resolve blocking import-graph findings.",
            ),
            cls._check(
                "static-dependency.metadata.hygiene",
                not any(
                    item.category
                    in {
                        StaticDependencyCategory.DEPENDENCY_METADATA,
                        StaticDependencyCategory.DEPENDENCY_LOCK,
                    }
                    for item in findings
                ),
                tuple(
                    sorted(
                        {
                            item.relative_path
                            for item in findings
                            if item.category
                            in {
                                StaticDependencyCategory.DEPENDENCY_METADATA,
                                StaticDependencyCategory.DEPENDENCY_LOCK,
                            }
                        }
                    )
                ),
                "Resolve blocking dependency-hygiene findings.",
            ),
        )

    @staticmethod
    def _check(
        code: str, passed: bool, paths: tuple[str, ...], remediation: str
    ) -> StaticDependencyCheck:
        return StaticDependencyCheck(
            code=code,
            state=StaticDependencyCheckState.PASSED
            if passed
            else StaticDependencyCheckState.FAILED,
            severity=StaticDependencySeverity.INFORMATIONAL
            if passed
            else StaticDependencySeverity.ERROR,
            summary="Bounded check passed."
            if passed
            else "Bounded check produced blocking findings.",
            evidence_paths=paths,
            remediation=remediation,
        )

    @classmethod
    def _canonical_payload(
        cls,
        *,
        source: ConnectorPackageAuthorityBehaviorValidation,
        actor_id: str,
        analysis_profile: str,
        source_summary: StaticSourceSummary,
        dependency_summary: DependencyHygieneSummary,
        findings: tuple[StaticDependencyFinding, ...],
        finding_set_digest: str,
        analysis_digest: str,
        checks: tuple[StaticDependencyCheck, ...],
        outcome: StaticDependencyOutcome,
    ) -> dict[str, object]:
        return {
            "schema_version": STATIC_DEPENDENCY_SCHEMA,
            "version": 1,
            "lifecycle": StaticDependencyLifecycle.VALIDATING.value,
            "outcome": outcome.value,
            "source_authority_behavior_validation_id": source.validation_id,
            "source_authority_behavior_validation_digest": source.canonical_digest,
            "source_schema_semantics_validation_id": source.source_schema_semantics_validation_id,
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
            "source_schema_validated_by": source.source_schema_validated_by,
            "source_authority_validated_by": source.validated_by,
            "source_custodied_by": source.source_custodied_by,
            "source_domain_reviewed_by": source.source_domain_reviewed_by,
            "source_security_reviewed_by": source.source_security_reviewed_by,
            "source_lab_operated_by": source.source_lab_operated_by,
            "organization_id": source.organization_id,
            "environment_id": source.environment_id,
            "analyzed_by": actor_id,
            "analysis_profile": analysis_profile,
            "analyzer_version": STATIC_DEPENDENCY_ANALYZER,
            "package_digest": source.package_digest,
            "package_size_bytes": source.package_size_bytes,
            "inventory_digest": source.inventory_digest,
            "source_summary": cls._source_summary_payload(source_summary),
            "dependency_summary": cls._dependency_summary_payload(dependency_summary),
            "findings": cls._finding_payload(findings),
            "finding_set_digest": finding_set_digest,
            "analysis_digest": analysis_digest,
            "checks": cls._check_payload(checks),
            "limitations": STATIC_DEPENDENCY_LIMITATIONS,
            "promotion_blocked": outcome is StaticDependencyOutcome.FAILED,
        }

    @classmethod
    def _canonical_payload_from_analysis(
        cls, analysis: ConnectorPackageStaticDependencyAnalysis
    ) -> dict[str, object]:
        return {
            "schema_version": analysis.schema_version,
            "version": analysis.version,
            "lifecycle": analysis.lifecycle.value,
            "outcome": analysis.outcome.value,
            "source_authority_behavior_validation_id": (
                analysis.source_authority_behavior_validation_id
            ),
            "source_authority_behavior_validation_digest": (
                analysis.source_authority_behavior_validation_digest
            ),
            "source_schema_semantics_validation_id": (
                analysis.source_schema_semantics_validation_id
            ),
            "source_content_policy_scan_id": analysis.source_content_policy_scan_id,
            "source_inventory_id": analysis.source_inventory_id,
            "source_validation_id": analysis.source_validation_id,
            "source_acquisition_id": analysis.source_acquisition_id,
            "source_handoff_id": analysis.source_handoff_id,
            "source_project_id": analysis.source_project_id,
            "source_acquired_by": analysis.source_acquired_by,
            "source_manifest_validated_by": analysis.source_manifest_validated_by,
            "source_inventoried_by": analysis.source_inventoried_by,
            "source_content_scanned_by": analysis.source_content_scanned_by,
            "source_schema_validated_by": analysis.source_schema_validated_by,
            "source_authority_validated_by": analysis.source_authority_validated_by,
            "source_custodied_by": analysis.source_custodied_by,
            "source_domain_reviewed_by": analysis.source_domain_reviewed_by,
            "source_security_reviewed_by": analysis.source_security_reviewed_by,
            "source_lab_operated_by": analysis.source_lab_operated_by,
            "organization_id": analysis.organization_id,
            "environment_id": analysis.environment_id,
            "analyzed_by": analysis.analyzed_by,
            "analysis_profile": analysis.analysis_profile,
            "analyzer_version": analysis.analyzer_version,
            "package_digest": analysis.package_digest,
            "package_size_bytes": analysis.package_size_bytes,
            "inventory_digest": analysis.inventory_digest,
            "source_summary": cls._source_summary_payload(analysis.source_summary),
            "dependency_summary": cls._dependency_summary_payload(analysis.dependency_summary),
            "findings": cls._finding_payload(analysis.findings),
            "finding_set_digest": analysis.finding_set_digest,
            "analysis_digest": analysis.analysis_digest,
            "checks": cls._check_payload(analysis.checks),
            "limitations": analysis.limitations,
            "promotion_blocked": analysis.promotion_blocked,
        }

    @classmethod
    def _verify_analysis(cls, analysis: ConnectorPackageStaticDependencyAnalysis) -> None:
        try:
            analysis.__post_init__()
        except ValueError as error:
            raise PackageStaticDependencyAnalysisError(
                "package_static_dependency_integrity_failed"
            ) from error
        if cls._digest(cls._canonical_payload_from_analysis(analysis)) != analysis.canonical_digest:
            raise PackageStaticDependencyAnalysisError("package_static_dependency_integrity_failed")

    @staticmethod
    def _source_summary_payload(item: StaticSourceSummary) -> dict[str, object]:
        return {
            "source_file_count": item.source_file_count,
            "module_count": item.module_count,
            "function_count": item.function_count,
            "import_count": item.import_count,
            "external_import_count": item.external_import_count,
            "unresolved_import_count": item.unresolved_import_count,
            "source_set_digest": item.source_set_digest,
        }

    @staticmethod
    def _dependency_summary_payload(item: DependencyHygieneSummary) -> dict[str, object]:
        return {
            "runtime_dependency_count": item.runtime_dependency_count,
            "build_dependency_count": item.build_dependency_count,
            "imported_dependency_count": item.imported_dependency_count,
            "dependency_lock_present": item.dependency_lock_present,
            "dependency_lock_required": item.dependency_lock_required,
            "dependency_set_digest": item.dependency_set_digest,
            "metadata_consistent": item.metadata_consistent,
            "imports_reconciled": item.imports_reconciled,
            "deterministic_constraints": item.deterministic_constraints,
        }

    @staticmethod
    def _finding_payload(items: tuple[StaticDependencyFinding, ...]) -> list[dict[str, object]]:
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
    def _check_payload(items: tuple[StaticDependencyCheck, ...]) -> list[dict[str, object]]:
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
    def _verify_source(source: ConnectorPackageAuthorityBehaviorValidation) -> None:
        try:
            PackageAuthorityBehaviorValidationService._verify_validation(source)
        except Exception as error:
            raise PackageStaticDependencyAnalysisError(
                "package_static_dependency_source_integrity_failed"
            ) from error
        if (
            source.outcome is not AuthorityBehaviorOutcome.PASSED
            or source.promotion_blocked
            or source.validation_profile != AUTHORITY_BEHAVIOR_PROFILE
            or source.analyzer_version != AUTHORITY_BEHAVIOR_ANALYZER
            or not source.permission_behavior_validation_completed
            or source.static_code_validation_completed
            or source.vulnerability_scan_completed
            or source.connector_rejected
            or source.connector_registered
            or source.runtime_trust_granted
            or source.execution_authorized
            or source.infrastructure_mutation_performed
        ):
            raise PackageStaticDependencyAnalysisError(
                "package_static_dependency_source_unsupported"
            )

    @staticmethod
    def _verify_inventory_binding(
        source: ConnectorPackageAuthorityBehaviorValidation,
        inventory: ConnectorPackageSupplyChainInventory,
    ) -> None:
        try:
            PackageSupplyChainInventoryService._verify_inventory(inventory)
        except Exception as error:
            raise PackageStaticDependencyAnalysisError(
                "package_static_dependency_source_integrity_failed"
            ) from error
        if (
            inventory.inventory_id != source.source_inventory_id
            or inventory.package_digest != source.package_digest
            or inventory.package_size_bytes != source.package_size_bytes
            or inventory.inventory_digest != source.inventory_digest
            or inventory.organization_id != source.organization_id
            or inventory.environment_id != source.environment_id
        ):
            raise PackageStaticDependencyAnalysisError(
                "package_static_dependency_source_integrity_failed"
            )

    @staticmethod
    def _verify_acquisition_binding(
        source: ConnectorPackageAuthorityBehaviorValidation,
        acquisition: ConnectorPackageAcquisition,
    ) -> None:
        try:
            PackageAcquisitionService._verify_acquisition(acquisition)
        except Exception as error:
            raise PackageStaticDependencyAnalysisError(
                "package_static_dependency_source_integrity_failed"
            ) from error
        if (
            acquisition.acquisition_id != source.source_acquisition_id
            or acquisition.package_digest != source.package_digest
            or acquisition.package_size_bytes != source.package_size_bytes
            or acquisition.organization_id != source.organization_id
            or acquisition.environment_id != source.environment_id
        ):
            raise PackageStaticDependencyAnalysisError(
                "package_static_dependency_source_integrity_failed"
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
        if actual != expected:
            raise PackageStaticDependencyAnalysisError(
                "package_static_dependency_inventory_mismatch"
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
            raise PackageStaticDependencyAnalysisError(
                "package_static_dependency_enterprise_human_mfa_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise PackageStaticDependencyAnalysisError("package_static_dependency_not_found")

    @classmethod
    def _require_separation(
        cls, actor: AuthenticatedSubject, source: ConnectorPackageAuthorityBehaviorValidation
    ) -> None:
        if actor.subject_id in cls._source_actors(source):
            raise PackageStaticDependencyAnalysisError("package_static_dependency_not_found")

    @staticmethod
    def _source_actors(source: ConnectorPackageAuthorityBehaviorValidation) -> set[str]:
        return {
            source.source_acquired_by,
            source.source_manifest_validated_by,
            source.source_inventoried_by,
            source.source_content_scanned_by,
            source.source_schema_validated_by,
            source.validated_by,
            source.source_custodied_by,
            source.source_domain_reviewed_by,
            source.source_security_reviewed_by,
            source.source_lab_operated_by,
        }

    @staticmethod
    def _analysis_source_actors(analysis: ConnectorPackageStaticDependencyAnalysis) -> set[str]:
        return {
            analysis.source_acquired_by,
            analysis.source_manifest_validated_by,
            analysis.source_inventoried_by,
            analysis.source_content_scanned_by,
            analysis.source_schema_validated_by,
            analysis.source_authority_validated_by,
            analysis.source_custodied_by,
            analysis.source_domain_reviewed_by,
            analysis.source_security_reviewed_by,
            analysis.source_lab_operated_by,
        }

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        analysis: ConnectorPackageStaticDependencyAnalysis,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.package-static-dependency-analysis",
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
                resource_type="resource.connector.package-static-dependency-analysis",
                scope_reference=analysis.analysis_id,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=analysis.idempotency_key,
                target_metadata=(
                    ("analysis_id", analysis.analysis_id),
                    (
                        "source_authority_behavior_validation_id",
                        analysis.source_authority_behavior_validation_id,
                    ),
                    ("package_digest", analysis.package_digest),
                    ("analysis_outcome", analysis.outcome.value),
                    ("finding_count", str(len(analysis.findings))),
                ),
            )
        )
