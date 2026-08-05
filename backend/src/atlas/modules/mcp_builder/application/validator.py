from __future__ import annotations

import ast
import json
import re
import tomllib
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from atlas.modules.mcp_builder.application.generator import PythonScaffoldGenerator
from atlas.modules.mcp_builder.domain.design_review import McpBuilderDesignCheckpoint
from atlas.modules.mcp_builder.domain.generation import McpBuilderGeneration
from atlas.modules.mcp_builder.domain.models import McpBuilderProject
from atlas.modules.mcp_builder.domain.validation import (
    BuilderValidationCheck,
    BuilderValidationCheckState,
    BuilderValidationSeverity,
    BuilderValidationState,
)

VALIDATION_PROFILE = "atlas.static-validation.python312.v1"
VALIDATOR_VERSION = "mcp-builder-static-validator.v1"

_PROHIBITED_IMPORT_ROOTS = frozenset(
    {
        "aiohttp",
        "ftplib",
        "http",
        "httpx",
        "os",
        "paramiko",
        "requests",
        "shutil",
        "smtplib",
        "socket",
        "subprocess",
        "telnetlib",
        "urllib",
    }
)
_PROHIBITED_CALLS = frozenset(
    {
        "__import__",
        "compile",
        "eval",
        "exec",
        "open",
        "system",
        "popen",
    }
)
_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]{16,}"),
    re.compile(r"(?i)\b(?:password|token|api[_-]?key|secret)\s*[:=]\s*['\"][^'\"]{4,}['\"]"),
    re.compile(r"(?i)https?://[^\s/:]+:[^\s/@]+@"),
)
_REQUIRED_FOUNDATION = frozenset(
    {
        "README.md",
        "atlas-connector.yaml",
        "docs/entity-mappings.json",
        "docs/network-boundary.json",
        "docs/permissions.json",
        "docs/source-traceability.json",
        "pyproject.toml",
        "schemas/config/config.schema.json",
        "src/atlas_generated_connector/__init__.py",
        "src/atlas_generated_connector/capabilities/__init__.py",
        "src/atlas_generated_connector/errors.py",
        "tests/contract/test_quarantine_contract.py",
        "tests/fixtures/synthetic-empty.json",
    }
)
_PROHIBITED_SUFFIXES = frozenset(
    {".bat", ".cmd", ".com", ".dll", ".exe", ".jar", ".p12", ".pfx", ".ps1", ".pyc", ".so"}
)
_LIMITATIONS = (
    "Generated code was parsed but was not imported, compiled, executed, or tested.",
    "Build dependencies and vulnerability feeds were not resolved.",
    "Vendor semantics, target behavior, and lab compatibility were not established.",
    "A passing static report does not authorize packaging, registration, "
    "installation, or execution.",
)


@dataclass(frozen=True, slots=True)
class BuilderStaticValidationResult:
    state: BuilderValidationState
    checks: tuple[BuilderValidationCheck, ...]
    limitations: tuple[str, ...] = _LIMITATIONS


class PythonScaffoldStaticValidator:
    def __init__(self, generator: PythonScaffoldGenerator | None = None) -> None:
        self._generator = generator or PythonScaffoldGenerator()

    def validate(
        self,
        *,
        project: McpBuilderProject,
        checkpoint: McpBuilderDesignCheckpoint,
        generation: McpBuilderGeneration,
        contents: dict[str, str] | None,
        artifact_error_code: str | None = None,
    ) -> BuilderStaticValidationResult:
        if contents is None:
            integrity = self._failed(
                "validation.artifact.integrity",
                "Generated artifact inventory could not be verified.",
                "Restore the exact quarantined artifact and retry validation.",
            )
            return BuilderStaticValidationResult(
                state=BuilderValidationState.FAILED,
                checks=(
                    integrity,
                    *self._skipped_checks(
                        "Dependent checks were skipped after "
                        f"{artifact_error_code or 'artifact failure'}."
                    ),
                ),
            )

        checks = (
            self._inventory_check(generation, contents),
            self._regeneration_check(project, checkpoint, contents),
            self._required_files_check(checkpoint, contents),
            self._manifest_check(checkpoint, generation, contents),
            self._pyproject_check(contents),
            self._python_ast_check(contents),
            self._schema_fixture_check(checkpoint, contents),
            self._test_contract_check(contents),
            self._permissions_check(checkpoint, contents),
            self._network_check(checkpoint, contents),
            self._traceability_check(project, checkpoint, generation, contents),
            self._entity_mapping_check(checkpoint, contents),
            self._secret_scan_check(contents),
            self._documentation_check(project, checkpoint, generation, contents),
            self._authority_check(contents),
        )
        state = (
            BuilderValidationState.FAILED
            if any(item.state is BuilderValidationCheckState.FAILED for item in checks)
            else BuilderValidationState.PASSED
        )
        return BuilderStaticValidationResult(state=state, checks=checks)

    @staticmethod
    def _inventory_check(
        generation: McpBuilderGeneration, contents: dict[str, str]
    ) -> BuilderValidationCheck:
        expected = {item.relative_path: item for item in generation.files}
        valid = set(contents) == set(expected)
        for path, content in contents.items():
            metadata = expected.get(path)
            encoded = content.encode("utf-8")
            valid = valid and metadata is not None and metadata.size_bytes == len(encoded)
            valid = (
                valid and metadata is not None and metadata.sha256 == sha256(encoded).hexdigest()
            )
        return PythonScaffoldStaticValidator._check(
            "validation.artifact.integrity",
            valid,
            "Every generated file matches the immutable quarantine inventory.",
            tuple(sorted(contents)),
            "Restore the exact generation-digest artifact before retrying validation.",
        )

    def _regeneration_check(
        self,
        project: McpBuilderProject,
        checkpoint: McpBuilderDesignCheckpoint,
        contents: dict[str, str],
    ) -> BuilderValidationCheck:
        expected = {
            item.relative_path: item.content
            for item in self._generator.generate(project=project, checkpoint=checkpoint).files
        }
        return self._check(
            "validation.artifact.reproducible",
            expected == contents,
            "Artifact content exactly matches deterministic regeneration.",
            tuple(sorted(contents)),
            "Regenerate into a new quarantine workspace from the exact approved design.",
        )

    @staticmethod
    def _required_files_check(
        checkpoint: McpBuilderDesignCheckpoint, contents: dict[str, str]
    ) -> BuilderValidationCheck:
        included_count = sum(item.generation_eligible for item in checkpoint.capability_decisions)
        capability_sources = {
            path
            for path in contents
            if path.startswith("src/atlas_generated_connector/capabilities/capability_")
            and path.endswith(".py")
        }
        input_schemas = {
            path
            for path in contents
            if path.startswith("schemas/inputs/") and path.endswith(".json")
        }
        output_schemas = {
            path
            for path in contents
            if path.startswith("schemas/outputs/") and path.endswith(".json")
        }
        prohibited = {
            path
            for path in contents
            if any(path.casefold().endswith(suffix) for suffix in _PROHIBITED_SUFFIXES)
            or path.startswith((".git/", ".github/", "dist/", "build/", "vendor/"))
        }
        valid = (
            _REQUIRED_FOUNDATION.issubset(contents)
            and len(capability_sources) == included_count
            and len(input_schemas) == included_count
            and len(output_schemas) == included_count
            and not prohibited
        )
        return PythonScaffoldStaticValidator._check(
            "validation.artifact.file-set",
            valid,
            "Required generated files are complete and prohibited files are absent.",
            tuple(sorted(_REQUIRED_FOUNDATION & contents.keys())),
            "Regenerate the scaffold and remove unapproved binaries, scripts, or build output.",
        )

    @staticmethod
    def _manifest_check(
        checkpoint: McpBuilderDesignCheckpoint,
        generation: McpBuilderGeneration,
        contents: dict[str, str],
    ) -> BuilderValidationCheck:
        manifest = PythonScaffoldStaticValidator._json_object(contents.get("atlas-connector.yaml"))
        expected_capabilities = [
            {
                "id": item.candidate_id,
                "class": item.confirmed_class.value,
                "permission": item.required_permission,
                "handler_status": "draft_fail_closed",
            }
            for item in sorted(
                (item for item in checkpoint.capability_decisions if item.generation_eligible),
                key=lambda item: item.candidate_id,
            )
        ]
        valid = manifest is not None and all(
            (
                manifest.get("schema_version") == "atlas.connector-manifest.v1",
                manifest.get("status") == "quarantined_generated_draft",
                manifest.get("sdk_profile") == generation.language_profile,
                manifest.get("target_products") == list(checkpoint.target_products),
                manifest.get("network_destinations") == list(checkpoint.network_destinations),
                manifest.get("configuration_keys") == list(checkpoint.configuration_keys),
                manifest.get("secret_reference_ids") == list(checkpoint.secret_reference_ids),
                manifest.get("capabilities") == expected_capabilities,
                manifest.get("runtime_trust") is False,
                manifest.get("execution_authorized") is False,
            )
        )
        return PythonScaffoldStaticValidator._check(
            "validation.manifest.contract",
            valid,
            "Connector manifest matches the confirmed design and remains quarantined.",
            ("atlas-connector.yaml",),
            "Restore the deterministic manifest generated from the approved checkpoint.",
        )

    @staticmethod
    def _pyproject_check(contents: dict[str, str]) -> BuilderValidationCheck:
        try:
            project = tomllib.loads(contents.get("pyproject.toml", ""))
        except (tomllib.TOMLDecodeError, UnicodeError):
            project = {}
        build = project.get("build-system") if isinstance(project, dict) else None
        metadata = project.get("project") if isinstance(project, dict) else None
        valid = (
            isinstance(build, dict)
            and build.get("build-backend") == "setuptools.build_meta"
            and build.get("requires") == ["setuptools>=75,<76"]
            and isinstance(metadata, dict)
            and metadata.get("requires-python") == ">=3.12,<3.13"
            and metadata.get("dependencies") == []
        )
        return PythonScaffoldStaticValidator._check(
            "validation.python.project",
            valid,
            "Python project metadata uses the approved profile with no runtime dependencies.",
            ("pyproject.toml",),
            "Restore the approved Python 3.12 project metadata and empty dependency set.",
        )

    @staticmethod
    def _python_ast_check(contents: dict[str, str]) -> BuilderValidationCheck:
        python_paths = tuple(sorted(path for path in contents if path.endswith(".py")))
        valid = bool(python_paths)
        for path in python_paths:
            try:
                tree = ast.parse(contents[path], filename=path)
            except (SyntaxError, ValueError):
                valid = False
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    valid = valid and all(
                        alias.name.split(".", 1)[0] not in _PROHIBITED_IMPORT_ROOTS
                        for alias in node.names
                    )
                elif isinstance(node, ast.ImportFrom):
                    root = (node.module or "").split(".", 1)[0]
                    valid = valid and root not in _PROHIBITED_IMPORT_ROOTS
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        valid = valid and node.func.id not in _PROHIBITED_CALLS
                    elif isinstance(node.func, ast.Attribute):
                        valid = valid and node.func.attr not in _PROHIBITED_CALLS
        return PythonScaffoldStaticValidator._check(
            "validation.python.ast-safety",
            valid,
            "Python files parse as source and contain no prohibited static execution constructs.",
            python_paths,
            "Remove prohibited imports or calls and regenerate or review the source.",
        )

    @staticmethod
    def _schema_fixture_check(
        checkpoint: McpBuilderDesignCheckpoint, contents: dict[str, str]
    ) -> BuilderValidationCheck:
        schema_paths = tuple(
            sorted(
                path for path in contents if path.startswith("schemas/") and path.endswith(".json")
            )
        )
        valid = bool(schema_paths)
        parsed: dict[str, dict[str, Any]] = {}
        for path in schema_paths:
            value = PythonScaffoldStaticValidator._json_object(contents.get(path))
            valid = valid and value is not None
            if value is not None:
                parsed[path] = value
                valid = (
                    valid and value.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
                )
                valid = valid and value.get("type") == "object"
        config = parsed.get("schemas/config/config.schema.json")
        expected_required = sorted(
            (*checkpoint.configuration_keys, *checkpoint.secret_reference_ids)
        )
        valid = valid and config is not None and config.get("required") == expected_required
        valid = valid and config is not None and config.get("additionalProperties") is False
        fixture = PythonScaffoldStaticValidator._json_object(
            contents.get("tests/fixtures/synthetic-empty.json")
        )
        valid = valid and fixture is not None and fixture.get("classification") == "synthetic"
        valid = valid and fixture is not None and fixture.get("target_connected") is False
        valid = valid and fixture is not None and fixture.get("secret_values_present") is False
        return PythonScaffoldStaticValidator._check(
            "validation.schemas.contract",
            valid,
            "Generated schemas and synthetic fixture retain bounded draft contracts.",
            (*schema_paths, "tests/fixtures/synthetic-empty.json"),
            "Restore draft 2020-12 schemas and a disconnected secret-free synthetic fixture.",
        )

    @staticmethod
    def _test_contract_check(contents: dict[str, str]) -> BuilderValidationCheck:
        path = "tests/contract/test_quarantine_contract.py"
        source = contents.get(path, "")
        required = (
            "quarantined_generated_draft",
            "manifest['runtime_trust'] is False",
            "manifest['execution_authorized'] is False",
        )
        valid = all(item in source for item in required)
        return PythonScaffoldStaticValidator._check(
            "validation.tests.fail-closed",
            valid,
            "Generated contract test declares quarantine and denies runtime authority.",
            (path,),
            "Restore the generated fail-closed quarantine contract test.",
        )

    @staticmethod
    def _permissions_check(
        checkpoint: McpBuilderDesignCheckpoint, contents: dict[str, str]
    ) -> BuilderValidationCheck:
        value = PythonScaffoldStaticValidator._json_object(contents.get("docs/permissions.json"))
        expected = [
            {"candidate_id": item.candidate_id, "required_permission": item.required_permission}
            for item in sorted(
                (item for item in checkpoint.capability_decisions if item.generation_eligible),
                key=lambda item: item.candidate_id,
            )
        ]
        valid = value is not None and value.get("capabilities") == expected
        valid = (
            valid
            and value is not None
            and value.get("broad_administrator_permission_allowed") is False
        )
        return PythonScaffoldStaticValidator._check(
            "validation.permissions.complete",
            valid,
            "Capability permissions exactly match the human-confirmed least-privilege design.",
            ("docs/permissions.json",),
            "Restore the exact confirmed permission matrix.",
        )

    @staticmethod
    def _network_check(
        checkpoint: McpBuilderDesignCheckpoint, contents: dict[str, str]
    ) -> BuilderValidationCheck:
        value = PythonScaffoldStaticValidator._json_object(
            contents.get("docs/network-boundary.json")
        )
        valid = value is not None and value.get("network_access_enabled") is False
        valid = (
            valid
            and value is not None
            and value.get("declared_review_destinations") == list(checkpoint.network_destinations)
        )
        valid = (
            valid
            and value is not None
            and value.get("redirect_policy") == ("disabled_pending_security_validation")
        )
        return PythonScaffoldStaticValidator._check(
            "validation.network.boundary",
            valid,
            "Network access remains disabled and destinations match the approved design.",
            ("docs/network-boundary.json",),
            "Disable network access and restore the exact approved destination list.",
        )

    @staticmethod
    def _traceability_check(
        project: McpBuilderProject,
        checkpoint: McpBuilderDesignCheckpoint,
        generation: McpBuilderGeneration,
        contents: dict[str, str],
    ) -> BuilderValidationCheck:
        value = PythonScaffoldStaticValidator._json_object(
            contents.get("docs/source-traceability.json")
        )
        expected_ids = sorted(
            item.candidate_id
            for item in checkpoint.capability_decisions
            if item.generation_eligible
        )
        observed = [] if value is None else value.get("capabilities", [])
        observed_ids = (
            sorted(
                candidate_id
                for item in observed
                if isinstance(item, dict)
                and isinstance((candidate_id := item.get("candidate_id")), str)
            )
            if isinstance(observed, list)
            else []
        )
        valid = value is not None and all(
            (
                value.get("project_id") == project.project_id,
                value.get("project_digest") == project.canonical_digest,
                value.get("source_digest") == project.source_digest,
                value.get("design_checkpoint_id") == checkpoint.checkpoint_id,
                value.get("design_checkpoint_digest") == checkpoint.canonical_digest,
                value.get("language_profile") == generation.language_profile,
                value.get("template_version") == generation.template_version,
                observed_ids == expected_ids,
                value.get("model_inference_performed") is False,
                value.get("runtime_trust_granted") is False,
            )
        )
        return PythonScaffoldStaticValidator._check(
            "validation.traceability.complete",
            valid,
            "Source, design, generation profile, and capability lineage are complete.",
            ("docs/source-traceability.json",),
            "Regenerate traceability from the exact source and design checkpoint.",
        )

    @staticmethod
    def _entity_mapping_check(
        checkpoint: McpBuilderDesignCheckpoint, contents: dict[str, str]
    ) -> BuilderValidationCheck:
        value = PythonScaffoldStaticValidator._json_object(
            contents.get("docs/entity-mappings.json")
        )
        expected = [
            {"source_entity": item.source_entity, "atlas_entity": item.atlas_entity}
            for item in checkpoint.entity_mappings
        ]
        valid = value is not None and value.get("mappings") == expected
        return PythonScaffoldStaticValidator._check(
            "validation.entities.complete",
            valid,
            "Generated entity mappings exactly match the confirmed design.",
            ("docs/entity-mappings.json",),
            "Restore the exact confirmed entity mapping set.",
        )

    @staticmethod
    def _secret_scan_check(contents: dict[str, str]) -> BuilderValidationCheck:
        findings = [
            path
            for path, content in contents.items()
            if any(pattern.search(content) is not None for pattern in _SECRET_PATTERNS)
        ]
        return PythonScaffoldStaticValidator._check(
            "validation.security.secret-scan",
            not findings,
            "No private key, bearer credential, embedded secret, or credentialed URL was detected.",
            tuple(sorted(findings)),
            "Remove credential material, rotate exposed credentials, and regenerate the artifact.",
        )

    @staticmethod
    def _documentation_check(
        project: McpBuilderProject,
        checkpoint: McpBuilderDesignCheckpoint,
        generation: McpBuilderGeneration,
        contents: dict[str, str],
    ) -> BuilderValidationCheck:
        readme = contents.get("README.md", "")
        required = (
            "# Quarantined Atlas Connector Draft",
            project.project_id,
            checkpoint.checkpoint_id,
            project.source_digest,
            generation.language_profile,
            "not been validated, packaged, signed, registered, installed, enabled, or executed",
        )
        valid = all(item in readme for item in required)
        return PythonScaffoldStaticValidator._check(
            "validation.documentation.complete",
            valid,
            "Generated documentation identifies provenance and the quarantine boundary.",
            ("README.md",),
            "Restore provenance and explicit non-approval language in generated documentation.",
        )

    @staticmethod
    def _authority_check(contents: dict[str, str]) -> BuilderValidationCheck:
        manifest = PythonScaffoldStaticValidator._json_object(contents.get("atlas-connector.yaml"))
        network = PythonScaffoldStaticValidator._json_object(
            contents.get("docs/network-boundary.json")
        )
        traceability = PythonScaffoldStaticValidator._json_object(
            contents.get("docs/source-traceability.json")
        )
        valid = all(
            (
                manifest is not None and manifest.get("runtime_trust") is False,
                manifest is not None and manifest.get("execution_authorized") is False,
                network is not None and network.get("network_access_enabled") is False,
                traceability is not None and traceability.get("model_inference_performed") is False,
                traceability is not None and traceability.get("runtime_trust_granted") is False,
            )
        )
        return PythonScaffoldStaticValidator._check(
            "validation.isolation.authority",
            valid,
            "Generated evidence grants no network, model, runtime, or execution authority.",
            (
                "atlas-connector.yaml",
                "docs/network-boundary.json",
                "docs/source-traceability.json",
            ),
            "Restore all quarantine authority flags to false and repeat review.",
        )

    @staticmethod
    def _json_object(content: str | None) -> dict[str, Any] | None:
        if content is None:
            return None
        try:
            value = json.loads(content)
        except (json.JSONDecodeError, UnicodeError):
            return None
        return value if isinstance(value, dict) else None

    @staticmethod
    def _check(
        code: str,
        valid: bool,
        summary: str,
        evidence_paths: tuple[str, ...],
        remediation: str,
    ) -> BuilderValidationCheck:
        return BuilderValidationCheck(
            code=code,
            state=(
                BuilderValidationCheckState.PASSED if valid else BuilderValidationCheckState.FAILED
            ),
            severity=(
                BuilderValidationSeverity.INFORMATIONAL
                if valid
                else BuilderValidationSeverity.ERROR
            ),
            summary=summary,
            evidence_paths=evidence_paths,
            remediation=None if valid else remediation,
        )

    @staticmethod
    def _failed(code: str, summary: str, remediation: str) -> BuilderValidationCheck:
        return BuilderValidationCheck(
            code=code,
            state=BuilderValidationCheckState.FAILED,
            severity=BuilderValidationSeverity.ERROR,
            summary=summary,
            evidence_paths=(),
            remediation=remediation,
        )

    @staticmethod
    def _skipped_checks(summary: str) -> tuple[BuilderValidationCheck, ...]:
        codes = (
            "validation.artifact.reproducible",
            "validation.artifact.file-set",
            "validation.manifest.contract",
            "validation.python.project",
            "validation.python.ast-safety",
            "validation.schemas.contract",
            "validation.tests.fail-closed",
            "validation.permissions.complete",
            "validation.network.boundary",
            "validation.traceability.complete",
            "validation.entities.complete",
            "validation.security.secret-scan",
            "validation.documentation.complete",
            "validation.isolation.authority",
        )
        return tuple(
            BuilderValidationCheck(
                code=code,
                state=BuilderValidationCheckState.SKIPPED,
                severity=BuilderValidationSeverity.WARNING,
                summary=summary,
                evidence_paths=(),
                remediation="Resolve artifact integrity before retrying dependent validation.",
            )
            for code in codes
        )
