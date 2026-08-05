from __future__ import annotations

import json
import re
from dataclasses import dataclass
from hashlib import sha256

from atlas.modules.mcp_builder.domain.design_review import (
    BuilderCapabilityDecisionKind,
    McpBuilderDesignCheckpoint,
)
from atlas.modules.mcp_builder.domain.generation import (
    BuilderGeneratedFile,
    validate_generated_path,
)
from atlas.modules.mcp_builder.domain.models import BuilderCapabilityCandidate, McpBuilderProject

LANGUAGE_PROFILE = "atlas.python312.v1"
TEMPLATE_VERSION = "mcp-builder-python.v1"
MAX_GENERATED_CAPABILITIES = 64


class BuilderGenerationError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class BuilderGeneratedContent:
    relative_path: str
    media_type: str
    content: str
    source_candidate_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        validate_generated_path(self.relative_path)
        encoded = self.content.encode("utf-8")
        if not encoded or len(encoded) > 65_536 or "\x00" in self.content:
            raise ValueError("generated file content is outside platform bounds")
        if "\r" in self.content:
            raise ValueError("generated files must use LF line endings")

    @property
    def metadata(self) -> BuilderGeneratedFile:
        encoded = self.content.encode("utf-8")
        return BuilderGeneratedFile(
            relative_path=self.relative_path,
            media_type=self.media_type,
            sha256=sha256(encoded).hexdigest(),
            size_bytes=len(encoded),
            source_candidate_ids=self.source_candidate_ids,
        )


@dataclass(frozen=True, slots=True)
class BuilderGenerationDraft:
    language_profile: str
    template_version: str
    files: tuple[BuilderGeneratedContent, ...]

    @property
    def metadata(self) -> tuple[BuilderGeneratedFile, ...]:
        return tuple(item.metadata for item in self.files)


class PythonScaffoldGenerator:
    def generate(
        self, *, project: McpBuilderProject, checkpoint: McpBuilderDesignCheckpoint
    ) -> BuilderGenerationDraft:
        if project.sdk_profile not in {"sdk.python.openapi", "sdk.python.synthetic"}:
            raise BuilderGenerationError("builder_generation_sdk_profile_unsupported")
        candidates = {item.candidate_id: item for item in project.capability_candidates}
        included = tuple(
            sorted(
                (
                    (candidates[item.candidate_id], item.required_permission)
                    for item in checkpoint.capability_decisions
                    if item.decision is BuilderCapabilityDecisionKind.INCLUDE
                ),
                key=lambda item: item[0].candidate_id,
            )
        )
        if not 1 <= len(included) <= MAX_GENERATED_CAPABILITIES:
            raise BuilderGenerationError("builder_generation_capability_budget_exceeded")

        connector_id = f"generated.{project.canonical_digest[:24]}"
        files: list[BuilderGeneratedContent] = []
        files.extend(self._foundation_files(project, checkpoint, connector_id, included))
        for candidate, permission in included:
            files.extend(self._capability_files(candidate, permission))
        files.extend(self._traceability_files(project, checkpoint, included))
        paths = [item.relative_path for item in files]
        if len(paths) != len(set(paths)) or len(paths) != len({path.casefold() for path in paths}):
            raise BuilderGenerationError("builder_generation_file_collision")
        if len(files) > 256 or sum(len(item.content.encode("utf-8")) for item in files) > 2_097_152:
            raise BuilderGenerationError("builder_generation_artifact_budget_exceeded")
        return BuilderGenerationDraft(
            language_profile=LANGUAGE_PROFILE,
            template_version=TEMPLATE_VERSION,
            files=tuple(sorted(files, key=lambda item: item.relative_path)),
        )

    def _foundation_files(
        self,
        project: McpBuilderProject,
        checkpoint: McpBuilderDesignCheckpoint,
        connector_id: str,
        included: tuple[tuple[BuilderCapabilityCandidate, str], ...],
    ) -> tuple[BuilderGeneratedContent, ...]:
        capability_manifest = [
            {
                "id": candidate.candidate_id,
                "class": candidate.proposed_capability_class.value,
                "permission": permission,
                "handler_status": "draft_fail_closed",
            }
            for candidate, permission in included
        ]
        manifest = {
            "schema_version": "atlas.connector-manifest.v1",
            "connector_id": connector_id,
            "version": "0.1.0-draft",
            "status": "quarantined_generated_draft",
            "sdk_profile": LANGUAGE_PROFILE,
            "target_products": list(checkpoint.target_products),
            "network_destinations": list(checkpoint.network_destinations),
            "configuration_keys": list(checkpoint.configuration_keys),
            "secret_reference_ids": list(checkpoint.secret_reference_ids),
            "capabilities": capability_manifest,
            "runtime_trust": False,
            "execution_authorized": False,
        }
        config_schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "atlas://generated/config.schema.json",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                **{
                    key: {"type": "string", "x-atlas-sensitive": False}
                    for key in checkpoint.configuration_keys
                },
                **{
                    key: {
                        "type": "string",
                        "format": "atlas-secret-reference",
                        "x-atlas-secret-value": False,
                    }
                    for key in checkpoint.secret_reference_ids
                },
            },
            "required": sorted((*checkpoint.configuration_keys, *checkpoint.secret_reference_ids)),
        }
        init_source = (
            '"""Generated connector review scaffold.\n\n'
            "This module grants no runtime authority.\n"
            '"""\n\n'
            f"CONNECTOR_ID = {connector_id!r}\n"
            f"LANGUAGE_PROFILE = {LANGUAGE_PROFILE!r}\n"
            "QUARANTINED = True\n"
            "RUNTIME_TRUST_GRANTED = False\n"
        )
        errors_source = (
            '"""Fail-closed errors for generated connector drafts."""\n\n'
            "class GeneratedDraftNotExecutable(RuntimeError):\n"
            '    """Raised because generated handlers require later validation and review."""\n\n'
        )
        capability_exports = [self._module_name(candidate) for candidate, _ in included]
        capabilities_init = (
            '"""Generated capability drafts. No module is imported automatically."""\n\n'
            f"GENERATED_CAPABILITY_MODULES = {tuple(capability_exports)!r}\n"
        )
        pyproject = (
            "[build-system]\n"
            'requires = ["setuptools>=75,<76"]\n'
            'build-backend = "setuptools.build_meta"\n\n'
            "[project]\n"
            f'name = "atlas-generated-{project.canonical_digest[:12]}"\n'
            'version = "0.1.0.dev0"\n'
            'description = "Quarantined Project Atlas connector review scaffold"\n'
            'requires-python = ">=3.12,<3.13"\n'
            "dependencies = []\n\n"
            "[tool.ruff]\n"
            'target-version = "py312"\n'
            "line-length = 100\n\n"
            "[tool.mypy]\n"
            'python_version = "3.12"\n'
            "strict = true\n\n"
            "[tool.pytest.ini_options]\n"
            'testpaths = ["tests"]\n'
        )
        readme = (
            "# Quarantined Atlas Connector Draft\n\n"
            f"- Project: `{project.project_id}`\n"
            f"- Design checkpoint: `{checkpoint.checkpoint_id}`\n"
            f"- Source digest: `{project.source_digest}`\n"
            f"- Profile: `{LANGUAGE_PROFILE}`\n\n"
            "This deterministic scaffold is a review artifact. Its handlers fail closed. "
            "It has not been validated, packaged, signed, registered, installed, enabled, "
            "or executed.\n"
        )
        quarantine_test = (
            '"""Contract declarations for the later isolated validator."""\n\n'
            "import json\n"
            "from pathlib import Path\n\n"
            "def test_generated_scaffold_declares_quarantine() -> None:\n"
            "    manifest = json.loads(Path('atlas-connector.yaml').read_text(encoding='utf-8'))\n"
            "    assert manifest['status'] == 'quarantined_generated_draft'\n"
            "    assert manifest['runtime_trust'] is False\n"
            "    assert manifest['execution_authorized'] is False\n"
        )
        synthetic_fixture = {
            "schema_version": "atlas.generated.synthetic-fixture.v1",
            "classification": "synthetic",
            "target_connected": False,
            "secret_values_present": False,
            "responses": [],
        }
        return (
            self._file(
                "atlas-connector.yaml",
                "application/yaml",
                self._json(manifest),
            ),
            self._file("pyproject.toml", "application/toml", pyproject),
            self._file("README.md", "text/markdown", readme),
            self._file("src/atlas_generated_connector/__init__.py", "text/x-python", init_source),
            self._file("src/atlas_generated_connector/errors.py", "text/x-python", errors_source),
            self._file(
                "src/atlas_generated_connector/capabilities/__init__.py",
                "text/x-python",
                capabilities_init,
            ),
            self._file(
                "schemas/config/config.schema.json", "application/json", self._json(config_schema)
            ),
            self._file(
                "tests/contract/test_quarantine_contract.py", "text/x-python", quarantine_test
            ),
            self._file(
                "tests/fixtures/synthetic-empty.json",
                "application/json",
                self._json(synthetic_fixture),
            ),
        )

    def _capability_files(
        self, candidate: BuilderCapabilityCandidate, permission: str
    ) -> tuple[BuilderGeneratedContent, ...]:
        module = self._module_name(candidate)
        source = (
            '"""Generated fail-closed capability draft."""\n\n'
            "from typing import Any, Never\n\n"
            "from atlas_generated_connector.errors import GeneratedDraftNotExecutable\n\n"
            f"CAPABILITY_ID = {candidate.candidate_id!r}\n"
            f"CAPABILITY_CLASS = {candidate.proposed_capability_class.value!r}\n"
            f"REQUIRED_PERMISSION = {permission!r}\n"
            f"SOURCE_CITATION = {candidate.citation!r}\n"
            f"HTTP_METHOD = {candidate.method.upper()!r}\n"
            f"PATH_TEMPLATE = {candidate.path!r}\n\n"
            "async def handle(_input: dict[str, Any]) -> Never:\n"
            "    raise GeneratedDraftNotExecutable(\n"
            "        'Generated capability requires isolated validation and human review.'\n"
            "    )\n"
        )
        input_schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"atlas://generated/{candidate.candidate_id}/input.schema.json",
            "type": "object",
            "additionalProperties": False,
            "properties": {},
            "x-atlas-parameter-evidence-count": candidate.parameter_count,
            "x-atlas-generation-status": "draft_requires_schema_review",
        }
        output_schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"atlas://generated/{candidate.candidate_id}/output.schema.json",
            "type": "object",
            "additionalProperties": True,
            "x-atlas-response-code-evidence": list(candidate.response_codes),
            "x-atlas-generation-status": "draft_requires_schema_review",
        }
        lineage = (candidate.candidate_id,)
        return (
            self._file(
                f"src/atlas_generated_connector/capabilities/{module}.py",
                "text/x-python",
                source,
                lineage,
            ),
            self._file(
                f"schemas/inputs/{module}.schema.json",
                "application/json",
                self._json(input_schema),
                lineage,
            ),
            self._file(
                f"schemas/outputs/{module}.schema.json",
                "application/json",
                self._json(output_schema),
                lineage,
            ),
        )

    def _traceability_files(
        self,
        project: McpBuilderProject,
        checkpoint: McpBuilderDesignCheckpoint,
        included: tuple[tuple[BuilderCapabilityCandidate, str], ...],
    ) -> tuple[BuilderGeneratedContent, ...]:
        permissions = {
            "schema_version": "atlas.generated.permissions.v1",
            "broad_administrator_permission_allowed": False,
            "capabilities": [
                {"candidate_id": candidate.candidate_id, "required_permission": permission}
                for candidate, permission in included
            ],
        }
        network = {
            "schema_version": "atlas.generated.network-boundary.v1",
            "network_access_enabled": False,
            "declared_review_destinations": list(checkpoint.network_destinations),
            "redirect_policy": "disabled_pending_security_validation",
        }
        mappings = {
            "schema_version": "atlas.generated.entity-mappings.v1",
            "mappings": [
                {"source_entity": item.source_entity, "atlas_entity": item.atlas_entity}
                for item in checkpoint.entity_mappings
            ],
        }
        traceability = {
            "schema_version": "atlas.generated.traceability.v1",
            "project_id": project.project_id,
            "project_version": project.version,
            "project_digest": project.canonical_digest,
            "source_digest": project.source_digest,
            "design_checkpoint_id": checkpoint.checkpoint_id,
            "design_checkpoint_digest": checkpoint.canonical_digest,
            "language_profile": LANGUAGE_PROFILE,
            "template_version": TEMPLATE_VERSION,
            "capabilities": [
                {
                    "candidate_id": candidate.candidate_id,
                    "citation": candidate.citation,
                    "confirmed_class": candidate.proposed_capability_class.value,
                    "generated_module": self._module_name(candidate),
                }
                for candidate, _ in included
            ],
            "model_inference_performed": False,
            "runtime_trust_granted": False,
        }
        all_ids = tuple(candidate.candidate_id for candidate, _ in included)
        return (
            self._file(
                "docs/permissions.json", "application/json", self._json(permissions), all_ids
            ),
            self._file("docs/network-boundary.json", "application/json", self._json(network)),
            self._file("docs/entity-mappings.json", "application/json", self._json(mappings)),
            self._file(
                "docs/source-traceability.json",
                "application/json",
                self._json(traceability),
                all_ids,
            ),
        )

    @staticmethod
    def _module_name(candidate: BuilderCapabilityCandidate) -> str:
        suffix = candidate.candidate_id.rsplit(".", 1)[-1]
        return f"capability_{re.sub(r'[^a-z0-9_]', '_', suffix.lower())}"

    @staticmethod
    def _json(value: object) -> str:
        return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n"

    @staticmethod
    def _file(
        path: str,
        media_type: str,
        content: str,
        lineage: tuple[str, ...] = (),
    ) -> BuilderGeneratedContent:
        return BuilderGeneratedContent(
            relative_path=path,
            media_type=media_type,
            content=content if content.endswith("\n") else f"{content}\n",
            source_candidate_ids=lineage,
        )
