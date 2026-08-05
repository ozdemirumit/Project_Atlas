from __future__ import annotations

import ast
import json
import tomllib
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, CollectingAuditSink, login, settings

from atlas.api.app import create_app
from atlas.core.capabilities import CapabilityClass
from atlas.core.classification import DataClassification
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.mcp_builder.adapters.design_review_memory import (
    InMemoryMcpBuilderDesignCheckpointRepository,
)
from atlas.modules.mcp_builder.adapters.generation_filesystem import (
    FileSystemMcpBuilderArtifactPublisher,
)
from atlas.modules.mcp_builder.adapters.generation_memory import (
    InMemoryMcpBuilderArtifactPublisher,
    InMemoryMcpBuilderGenerationRepository,
)
from atlas.modules.mcp_builder.adapters.memory import InMemoryMcpBuilderProjectRepository
from atlas.modules.mcp_builder.application.analyzer import BuilderSourceError, OpenApiSourceAnalyzer
from atlas.modules.mcp_builder.application.generator import BuilderGeneratedContent
from atlas.modules.mcp_builder.application.ports import McpBuilderArtifactError, McpBuilderError
from atlas.modules.mcp_builder.application.service import McpBuilderService
from atlas.modules.mcp_builder.domain.design_review import (
    BuilderCapabilityDecision,
    BuilderCapabilityDecisionKind,
    BuilderEntityMapping,
)
from atlas.modules.mcp_builder.domain.models import BuilderProjectState

NOW = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)


def actor(*, subject_id: str = "subject.development.operator") -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id=subject_id,
        display_name="MCP Builder Reviewer",
        kind=SubjectKind.HUMAN,
        provider_id="provider.ldap.test",
        authentication_method=AuthenticationMethod.LDAP,
        assurance_level=AssuranceLevel.MULTI_FACTOR,
        authenticated_at=NOW,
        organization_id="organization.development",
        role_ids=("role.development.operator",),
    )


def openapi_spec(*, method: str = "get", operation_id: str = "getSystems") -> str:
    return json.dumps(
        {
            "openapi": "3.1.0",
            "info": {"title": "Synthetic Storage API", "version": "1.0"},
            "servers": [{"url": "https://lab-api.example.invalid"}],
            "security": [{"apiKey": []}],
            "paths": {
                "/systems": {
                    method: {
                        "operationId": operation_id,
                        "summary": "Read synthetic storage systems",
                        "x-atlas-side-effects": "read",
                        "responses": {"200": {"description": "Synthetic response"}},
                    }
                }
            },
            "components": {
                "securitySchemes": {
                    "apiKey": {"type": "apiKey", "in": "header", "name": "X-API-Key"}
                }
            },
        },
        sort_keys=True,
    )


def create_request(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "actor": actor(),
        "vendor": "Atlas Synthetic",
        "product": "Storage Lab",
        "intended_product_versions": ("1.0",),
        "target_environment": "isolated synthetic lab",
        "sdk_profile": "sdk.python.synthetic",
        "source_id": "source.openapi.synthetic-storage",
        "source_authority": "Atlas test fixture",
        "source_owner": "Platform engineering",
        "documentation_version": "1.0",
        "publication_date": date(2026, 8, 5),
        "license_id": "license.internal-test",
        "redistribution_allowed": False,
        "classification": DataClassification.INTERNAL,
        "source_document": openapi_spec(),
        "confirmed_synthetic_or_lab_only": True,
        "idempotency_key": "mcp-builder-test-0001",
        "correlation_id": "correlation.mcp-builder-test",
    }
    values.update(overrides)
    return values


def service(
    sink: CollectingAuditSink | None = None,
) -> tuple[
    McpBuilderService,
    InMemoryMcpBuilderProjectRepository,
    InMemoryMcpBuilderDesignCheckpointRepository,
    CollectingAuditSink,
]:
    repository = InMemoryMcpBuilderProjectRepository()
    design_repository = InMemoryMcpBuilderDesignCheckpointRepository()
    resolved_sink = sink or CollectingAuditSink()
    return (
        McpBuilderService(
            repository=repository,
            design_repository=design_repository,
            generation_repository=InMemoryMcpBuilderGenerationRepository(),
            artifact_publisher=InMemoryMcpBuilderArtifactPublisher(),
            audit_sink=resolved_sink,
            environment_id="environment.test",
            clock=lambda: NOW,
        ),
        repository,
        design_repository,
        resolved_sink,
    )


def design_request(project: Any, **overrides: Any) -> dict[str, Any]:
    decisions = tuple(
        BuilderCapabilityDecision(
            candidate_id=item.candidate_id,
            decision=(
                BuilderCapabilityDecisionKind.EXCLUDE
                if item.generation_blocked
                else BuilderCapabilityDecisionKind.INCLUDE
            ),
            analyzed_class=item.proposed_capability_class,
            confirmed_class=item.proposed_capability_class,
            required_permission="storage.system.read",
            rationale=(
                "Excluded because the analyzed operation remains blocked."
                if item.generation_blocked
                else "Included as an authenticated, bounded read-only operation."
            ),
            generation_eligible=not item.generation_blocked,
        )
        for item in project.capability_candidates
    )
    values: dict[str, Any] = {
        "actor": actor(),
        "project_id": project.project_id,
        "project_version": project.version,
        "project_digest": project.canonical_digest,
        "source_digest": project.source_digest,
        "connector_boundary": "Synthetic storage inventory reads only.",
        "target_products": (project.product,),
        "network_destinations": project.declared_servers,
        "configuration_keys": ("config.vendor-endpoint",),
        "secret_reference_ids": ("secret.vendor-api-key",),
        "entity_mappings": (
            BuilderEntityMapping(
                source_entity="vendor.storage-system", atlas_entity="atlas.storage-system"
            ),
        ),
        "capability_decisions": decisions,
        "idempotency_key": "mcp-builder-design-0001",
        "correlation_id": "correlation.mcp-builder-design",
    }
    values.update(overrides)
    return values


def generation_request(project: Any, checkpoint: Any, **overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "actor": actor(),
        "project_id": project.project_id,
        "project_version": project.version,
        "project_digest": project.canonical_digest,
        "source_digest": project.source_digest,
        "checkpoint_id": checkpoint.checkpoint_id,
        "checkpoint_digest": checkpoint.canonical_digest,
        "language_profile": "atlas.python312.v1",
        "acknowledged_quarantine": True,
        "idempotency_key": "mcp-builder-generation-0001",
        "correlation_id": "correlation.mcp-builder-generation",
    }
    values.update(overrides)
    return values


def test_analyzer_extracts_only_explicit_read_only_capability() -> None:
    analysis = OpenApiSourceAnalyzer().analyze(openapi_spec())

    assert analysis.openapi_version == "3.1.0"
    assert analysis.declared_servers == ("https://lab-api.example.invalid",)
    assert len(analysis.authentication_schemes) == 1
    assert len(analysis.capability_candidates) == 1
    candidate = analysis.capability_candidates[0]
    assert candidate.proposed_capability_class.value == "C1"
    assert candidate.generation_blocked is False
    assert candidate.clarification_codes == ()
    assert analysis.findings == ()


def test_analyzer_blocks_write_and_ambiguous_read_style_actions() -> None:
    write = OpenApiSourceAnalyzer().analyze(
        openapi_spec(method="post", operation_id="restartSystems")
    )
    candidate = write.capability_candidates[0]

    assert candidate.proposed_capability_class.value == "C5"
    assert candidate.generation_blocked is True
    assert "builder_write_method_blocked" in candidate.clarification_codes
    assert "builder_read_style_action_ambiguous" in candidate.clarification_codes


@pytest.mark.parametrize(
    ("source", "code"),
    [
        ('{"openapi":"3.1.0","openapi":"3.0.3"}', "builder_source_duplicate_key"),
        (
            json.dumps(
                {
                    "openapi": "3.1.0",
                    "info": {"title": "Bad", "version": "1"},
                    "paths": {"/x": {}},
                    "password": "embedded-production-secret",
                }
            ),
            "builder_source_secret_detected",
        ),
        (
            openapi_spec().replace(
                "https://lab-api.example.invalid",
                "https://lab-api.example.invalid?api_key=embedded-production-secret",
            ),
            "builder_source_secret_detected",
        ),
    ],
)
def test_analyzer_rejects_ambiguous_or_secret_sources(source: str, code: str) -> None:
    with pytest.raises(BuilderSourceError, match=code):
        OpenApiSourceAnalyzer().analyze(source)


def test_analyzer_propagates_external_reference_block_to_candidates() -> None:
    document = json.loads(openapi_spec())
    document["paths"]["/systems"]["get"]["responses"]["200"]["content"] = {
        "application/json": {
            "schema": {"$ref": "https://vendor.example.invalid/schemas/system.json"}
        }
    }

    analysis = OpenApiSourceAnalyzer().analyze(json.dumps(document))
    candidate = analysis.capability_candidates[0]

    assert candidate.proposed_capability_class.value == "C5"
    assert candidate.generation_blocked is True
    assert "builder_external_reference_blocked" in candidate.clarification_codes


@pytest.mark.asyncio
async def test_service_persists_audited_project_and_replays_idempotently() -> None:
    builder, repository, _, sink = service()
    project = await builder.create_project(**create_request())
    replay = await builder.create_project(**create_request())
    loaded = await builder.get_project(
        actor=actor(),
        project_id=project.project_id,
        correlation_id="correlation.mcp-builder-read",
    )

    assert project.state is BuilderProjectState.ANALYZED
    assert replay == replace(project, reused=True)
    assert loaded == project
    assert (
        await repository.get(owner_id=actor().subject_id, idempotency_key="mcp-builder-test-0001")
        == project
    )
    assert [record.result_code for record in sink.records] == [
        "mcp_builder_source_analyzed",
        "mcp_builder_project_read",
    ]
    assert not any(
        (
            project.generated_artifact_created,
            project.candidate_package_created,
            project.connector_registered,
            project.connector_installed,
            project.connector_enabled,
            project.network_request_performed,
            project.model_inference_performed,
            project.dynamic_code_execution_performed,
            project.runtime_trust_granted,
        )
    )


@pytest.mark.asyncio
async def test_service_rejects_changed_replay_non_mfa_and_foreign_owner() -> None:
    builder, _, _, _ = service()
    project = await builder.create_project(**create_request())
    with pytest.raises(McpBuilderError, match="builder_idempotency_conflict"):
        await builder.create_project(**create_request(product="Different product"))
    with pytest.raises(McpBuilderError, match="builder_enterprise_human_mfa_required"):
        await builder.create_project(
            **create_request(
                actor=replace(actor(), assurance_level=AssuranceLevel.SINGLE_FACTOR),
                idempotency_key="mcp-builder-test-0002",
            )
        )
    with pytest.raises(McpBuilderError, match="builder_project_not_found"):
        await builder.get_project(
            actor=actor(subject_id="subject.foreign.reviewer"),
            project_id=project.project_id,
            correlation_id="correlation.mcp-builder-foreign",
        )


@pytest.mark.asyncio
async def test_audit_failure_prevents_project_persistence() -> None:
    class FailingAuditSink(CollectingAuditSink):
        async def record(self, event: Any) -> None:
            raise RuntimeError("audit unavailable")

    builder, repository, _, _ = service(FailingAuditSink())
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await builder.create_project(**create_request())
    assert (
        await repository.get(owner_id=actor().subject_id, idempotency_key="mcp-builder-test-0001")
        is None
    )


@pytest.mark.asyncio
async def test_design_checkpoint_is_complete_immutable_and_idempotent() -> None:
    builder, _, design_repository, sink = service()
    project = await builder.create_project(**create_request())
    checkpoint = await builder.create_design_checkpoint(**design_request(project))
    replay = await builder.create_design_checkpoint(**design_request(project))
    loaded = await builder.get_design_checkpoint(
        actor=actor(),
        project_id=project.project_id,
        correlation_id="correlation.mcp-builder-design-read",
    )

    assert replay == replace(checkpoint, reused=True)
    assert loaded == checkpoint
    assert checkpoint.ready_for_generation_design is True
    assert checkpoint.capability_decisions[0].generation_eligible is True
    assert await design_repository.get_by_project(project_id=project.project_id) == checkpoint
    assert [record.result_code for record in sink.records] == [
        "mcp_builder_source_analyzed",
        "mcp_builder_design_confirmed",
        "mcp_builder_design_read",
    ]
    assert not any(
        (
            checkpoint.generated_artifact_created,
            checkpoint.candidate_package_created,
            checkpoint.connector_registered,
            checkpoint.connector_installed,
            checkpoint.connector_enabled,
            checkpoint.network_request_performed,
            checkpoint.model_inference_performed,
            checkpoint.dynamic_code_execution_performed,
            checkpoint.runtime_trust_granted,
            checkpoint.execution_authorized,
            checkpoint.infrastructure_mutation_performed,
        )
    )


@pytest.mark.asyncio
async def test_design_checkpoint_rejects_stale_scope_risk_and_candidate_drift() -> None:
    builder, _, _, _ = service()
    project = await builder.create_project(**create_request())
    decision = design_request(project)["capability_decisions"][0]

    with pytest.raises(McpBuilderError, match="builder_design_project_stale"):
        await builder.create_design_checkpoint(**design_request(project, project_digest="0" * 64))
    with pytest.raises(McpBuilderError, match="builder_design_network_destination_unapproved"):
        await builder.create_design_checkpoint(
            **design_request(project, network_destinations=("https://other.example.invalid",))
        )
    with pytest.raises(McpBuilderError, match="builder_design_risk_class_mismatch"):
        await builder.create_design_checkpoint(
            **design_request(
                project,
                capability_decisions=(
                    replace(decision, confirmed_class=CapabilityClass.C0_INFORMATIONAL),
                ),
            )
        )
    with pytest.raises(McpBuilderError, match="builder_design_candidate_set_mismatch"):
        await builder.create_design_checkpoint(**design_request(project, capability_decisions=()))
    with pytest.raises(McpBuilderError, match="builder_design_broad_permission_rejected"):
        await builder.create_design_checkpoint(
            **design_request(
                project,
                capability_decisions=(replace(decision, required_permission="administrator"),),
            )
        )
    with pytest.raises(McpBuilderError, match="builder_enterprise_human_mfa_required"):
        await builder.create_design_checkpoint(
            **design_request(
                project,
                actor=replace(
                    actor(),
                    kind=SubjectKind.SERVICE,
                    authentication_method=AuthenticationMethod.WORKLOAD_TOKEN,
                    assurance_level=AssuranceLevel.HARDWARE_BACKED,
                ),
            )
        )
    with pytest.raises(McpBuilderError, match="builder_stored_source_integrity_failed"):
        builder._verify_stored(replace(project, product="Tampered product"))


@pytest.mark.asyncio
async def test_design_checkpoint_requires_blocked_candidate_exclusion() -> None:
    document = json.loads(openapi_spec())
    document["paths"]["/systems/restart"] = {
        "post": {
            "operationId": "restartSystems",
            "responses": {"202": {"description": "Synthetic response"}},
        }
    }
    builder, _, _, _ = service()
    project = await builder.create_project(
        **create_request(source_document=json.dumps(document), idempotency_key="mixed-source-0001")
    )
    request = design_request(project)
    blocked = next(item for item in request["capability_decisions"] if not item.generation_eligible)
    unsafe = replace(
        blocked,
        decision=BuilderCapabilityDecisionKind.INCLUDE,
        generation_eligible=True,
    )

    with pytest.raises(McpBuilderError, match="builder_design_blocked_candidate_included"):
        await builder.create_design_checkpoint(
            **design_request(
                project,
                capability_decisions=tuple(
                    unsafe if item.candidate_id == unsafe.candidate_id else item
                    for item in request["capability_decisions"]
                ),
            )
        )


@pytest.mark.asyncio
async def test_design_audit_failure_prevents_checkpoint_persistence() -> None:
    class FailingAuditSink(CollectingAuditSink):
        async def record(self, event: Any) -> None:
            raise RuntimeError("audit unavailable")

    builder, repository, design_repository, _ = service()
    project = await builder.create_project(**create_request())
    failing_builder = McpBuilderService(
        repository=repository,
        design_repository=design_repository,
        generation_repository=InMemoryMcpBuilderGenerationRepository(),
        artifact_publisher=InMemoryMcpBuilderArtifactPublisher(),
        audit_sink=FailingAuditSink(),
        environment_id="environment.test",
        clock=lambda: NOW,
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await failing_builder.create_design_checkpoint(**design_request(project))
    assert await design_repository.get_by_project(project_id=project.project_id) is None


@pytest.mark.asyncio
async def test_generation_is_deterministic_quarantined_and_structurally_valid() -> None:
    project_repository = InMemoryMcpBuilderProjectRepository()
    design_repository = InMemoryMcpBuilderDesignCheckpointRepository()
    generation_repository = InMemoryMcpBuilderGenerationRepository()
    publisher = InMemoryMcpBuilderArtifactPublisher()
    sink = CollectingAuditSink()
    builder = McpBuilderService(
        repository=project_repository,
        design_repository=design_repository,
        generation_repository=generation_repository,
        artifact_publisher=publisher,
        audit_sink=sink,
        environment_id="environment.test",
        clock=lambda: NOW,
    )
    project = await builder.create_project(**create_request())
    checkpoint = await builder.create_design_checkpoint(**design_request(project))

    generation = await builder.create_generation(**generation_request(project, checkpoint))
    replay = await builder.create_generation(**generation_request(project, checkpoint))
    loaded = await builder.get_generation(
        actor=actor(),
        project_id=project.project_id,
        correlation_id="correlation.mcp-builder-generation-read",
    )

    assert replay == replace(generation, reused=True)
    assert loaded == generation
    assert generation.state.value == "quarantined"
    assert generation.generated_artifact_created is True
    assert generation.artifact_published is True
    assert generation.validation_completed is False
    assert generation.candidate_package_created is False
    assert generation.connector_registered is False
    assert generation.connector_installed is False
    assert generation.connector_enabled is False
    assert generation.network_request_performed is False
    assert generation.model_inference_performed is False
    assert generation.subprocess_invoked is False
    assert generation.dynamic_code_execution_performed is False
    assert generation.runtime_trust_granted is False
    assert generation.execution_authorized is False
    assert generation.infrastructure_mutation_performed is False
    assert 10 <= len(generation.files) <= 256

    observed_candidates: set[str] = set()
    for metadata in generation.files:
        _, verified, content = await builder.get_generated_file(
            actor=actor(),
            project_id=project.project_id,
            relative_path=metadata.relative_path,
            correlation_id="correlation.mcp-builder-generated-file",
        )
        assert verified == metadata
        assert project.canonical_source_json not in content
        assert "X-API-Key" not in content
        observed_candidates.update(metadata.source_candidate_ids)
        if metadata.media_type == "text/x-python":
            ast.parse(content)
        elif metadata.media_type in {"application/json", "application/yaml"}:
            json.loads(content)
        elif metadata.media_type == "application/toml":
            tomllib.loads(content)
    assert observed_candidates == {
        item.candidate_id for item in checkpoint.capability_decisions if item.generation_eligible
    }
    assert sink.records[-1].result_code == "mcp_builder_generation_file_read"


@pytest.mark.asyncio
async def test_generation_rejects_stale_unsupported_and_unacknowledged_requests() -> None:
    builder, _, _, _ = service()
    project = await builder.create_project(**create_request())
    checkpoint = await builder.create_design_checkpoint(**design_request(project))

    with pytest.raises(McpBuilderError, match="builder_generation_source_stale"):
        await builder.create_generation(
            **generation_request(project, checkpoint, checkpoint_digest="0" * 64)
        )
    with pytest.raises(McpBuilderError, match="builder_generation_language_profile_unsupported"):
        await builder.create_generation(
            **generation_request(project, checkpoint, language_profile="atlas.rust.v1")
        )
    with pytest.raises(
        McpBuilderError, match="builder_generation_quarantine_acknowledgement_required"
    ):
        await builder.create_generation(
            **generation_request(project, checkpoint, acknowledged_quarantine=False)
        )


@pytest.mark.asyncio
async def test_generation_audit_failure_prevents_publication_and_metadata() -> None:
    class FailingAuditSink(CollectingAuditSink):
        async def record(self, event: Any) -> None:
            raise RuntimeError("audit unavailable")

    project_repository = InMemoryMcpBuilderProjectRepository()
    design_repository = InMemoryMcpBuilderDesignCheckpointRepository()
    generation_repository = InMemoryMcpBuilderGenerationRepository()
    publisher = InMemoryMcpBuilderArtifactPublisher()
    builder = McpBuilderService(
        repository=project_repository,
        design_repository=design_repository,
        generation_repository=generation_repository,
        artifact_publisher=publisher,
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        clock=lambda: NOW,
    )
    project = await builder.create_project(**create_request())
    checkpoint = await builder.create_design_checkpoint(**design_request(project))
    failing_builder = McpBuilderService(
        repository=project_repository,
        design_repository=design_repository,
        generation_repository=generation_repository,
        artifact_publisher=publisher,
        audit_sink=FailingAuditSink(),
        environment_id="environment.test",
        clock=lambda: NOW,
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        await failing_builder.create_generation(**generation_request(project, checkpoint))
    assert await generation_repository.get_by_project(project_id=project.project_id) is None


@pytest.mark.asyncio
async def test_filesystem_generation_publisher_reuses_exact_output_and_detects_tampering(
    tmp_path: Path,
) -> None:
    publisher = FileSystemMcpBuilderArtifactPublisher(root=tmp_path / "quarantine")
    files = (
        BuilderGeneratedContent(
            relative_path="README.md",
            media_type="text/markdown",
            content="# Generated\n",
        ),
        BuilderGeneratedContent(
            relative_path="src/connector.py",
            media_type="text/x-python",
            content="QUARANTINED = True\n",
        ),
    )
    inventory = tuple(item.metadata for item in files)
    published = await publisher.publish(
        generation_id="mcp-builder-generation.test0001",
        artifact_digest="a" * 64,
        files=files,
    )
    reused = await publisher.publish(
        generation_id="mcp-builder-generation.test0001",
        artifact_digest="a" * 64,
        files=files,
    )
    content = await publisher.read(
        generation_id="mcp-builder-generation.test0001",
        artifact_digest="a" * 64,
        inventory=inventory,
        relative_path="src/connector.py",
    )

    assert published is True
    assert reused is False
    assert content == "QUARANTINED = True\n"
    target = (
        tmp_path
        / "quarantine"
        / "generations"
        / "mcp-builder-generation.test0001"
        / ("a" * 64)
        / "src"
        / "connector.py"
    )
    target.write_text("QUARANTINED = False\n", encoding="utf-8")
    with pytest.raises(McpBuilderArtifactError, match="artifact_integrity_failed"):
        await publisher.read(
            generation_id="mcp-builder-generation.test0001",
            artifact_digest="a" * 64,
            inventory=inventory,
            relative_path="README.md",
        )


def api_payload() -> dict[str, Any]:
    request = create_request()
    return {
        "schema_version": "atlas.mcp-builder-project-request.v1",
        **{
            key: value
            for key, value in request.items()
            if key
            not in {
                "actor",
                "idempotency_key",
                "correlation_id",
            }
        },
        "publication_date": request["publication_date"].isoformat(),
        "classification": request["classification"].value,
        "intended_product_versions": list(request["intended_product_versions"]),
    }


def test_api_requires_csrf_and_returns_secret_free_no_store_evidence(tmp_path: Path) -> None:
    sink = CollectingAuditSink()
    provider = BasicTestIdentityProvider(actor())
    app_settings = settings().model_copy(
        update={"mcp_builder_generation_root": tmp_path / "mcp-builder-generations"}
    )
    with TestClient(
        create_app(app_settings, identity_provider=provider, audit_sink=sink)
    ) as client:
        login_response = login(client)
        denied = client.post(
            "/api/v1/mcp-builder/projects",
            json=api_payload(),
            headers={"Idempotency-Key": "mcp-builder-api-0001"},
        )
        created = client.post(
            "/api/v1/mcp-builder/projects",
            json=api_payload(),
            headers={
                "Idempotency-Key": "mcp-builder-api-0001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        project_data = created.json()["data"]
        project_id = project_data["project_id"]
        read = client.get(f"/api/v1/mcp-builder/projects/{project_id}")
        candidate = project_data["capability_candidates"][0]
        design_payload = {
            "schema_version": "atlas.mcp-builder-design-checkpoint-request.v1",
            "project_version": project_data["version"],
            "project_digest": project_data["canonical_digest"],
            "source_digest": project_data["source_digest"],
            "connector_boundary": "Synthetic storage inventory reads only.",
            "target_products": [project_data["product"]],
            "network_destinations": project_data["declared_servers"],
            "configuration_keys": ["config.vendor-endpoint"],
            "secret_reference_ids": ["secret.vendor-api-key"],
            "entity_mappings": [
                {
                    "source_entity": "vendor.storage-system",
                    "atlas_entity": "atlas.storage-system",
                }
            ],
            "capability_decisions": [
                {
                    "candidate_id": candidate["candidate_id"],
                    "decision": "include",
                    "analyzed_class": candidate["proposed_capability_class"],
                    "confirmed_class": candidate["proposed_capability_class"],
                    "required_permission": "storage.system.read",
                    "rationale": "Confirmed as a bounded read-only operation.",
                }
            ],
        }
        denied_design = client.post(
            f"/api/v1/mcp-builder/projects/{project_id}/design-checkpoints",
            json=design_payload,
            headers={"Idempotency-Key": "mcp-builder-design-api-0001"},
        )
        created_design = client.post(
            f"/api/v1/mcp-builder/projects/{project_id}/design-checkpoints",
            json=design_payload,
            headers={
                "Idempotency-Key": "mcp-builder-design-api-0001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        read_design = client.get(f"/api/v1/mcp-builder/projects/{project_id}/design-checkpoint")
        checkpoint_data = created_design.json()["data"]
        generation_payload = {
            "schema_version": "atlas.mcp-builder-generation-request.v1",
            "project_version": project_data["version"],
            "project_digest": project_data["canonical_digest"],
            "source_digest": project_data["source_digest"],
            "checkpoint_id": checkpoint_data["checkpoint_id"],
            "checkpoint_digest": checkpoint_data["canonical_digest"],
            "language_profile": "atlas.python312.v1",
            "acknowledged_quarantine": True,
        }
        denied_generation = client.post(
            f"/api/v1/mcp-builder/projects/{project_id}/generations",
            json=generation_payload,
            headers={"Idempotency-Key": "mcp-builder-generation-api-0001"},
        )
        created_generation = client.post(
            f"/api/v1/mcp-builder/projects/{project_id}/generations",
            json=generation_payload,
            headers={
                "Idempotency-Key": "mcp-builder-generation-api-0001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        read_generation = client.get(f"/api/v1/mcp-builder/projects/{project_id}/generation")
        read_file = client.get(
            f"/api/v1/mcp-builder/projects/{project_id}/generation/files/"
            "docs/source-traceability.json"
        )

    assert denied.status_code == 403
    assert created.status_code == 201
    assert read.status_code == 200
    assert denied_design.status_code == 403
    assert created_design.status_code == 201
    assert read_design.status_code == 200
    assert denied_generation.status_code == 403
    assert created_generation.status_code == 201
    assert read_generation.status_code == 200
    assert read_file.status_code == 200
    assert created.headers["Cache-Control"] == "no-store"
    assert read.headers["Cache-Control"] == "no-store"
    assert created_design.headers["Cache-Control"] == "no-store"
    assert read_design.headers["Cache-Control"] == "no-store"
    assert created_generation.headers["Cache-Control"] == "no-store"
    assert read_generation.headers["Cache-Control"] == "no-store"
    assert read_file.headers["Cache-Control"] == "no-store"
    assert created.json()["data"]["state"] == "analyzed"
    assert created.json()["data"]["capability_candidates"][0]["proposed_capability_class"] == "C1"
    for forbidden in ("canonical_source_json", "source_document", "request_fingerprint"):
        assert forbidden not in created.text
        assert forbidden not in created_design.text
        assert forbidden not in created_generation.text
    assert created_design.json()["data"]["ready_for_generation_design"] is True
    assert created_design.json()["data"]["generated_artifact_created"] is False
    assert created_design.json()["data"]["execution_authorized"] is False
    generation_data = created_generation.json()["data"]
    assert generation_data["state"] == "quarantined"
    assert generation_data["generated_artifact_created"] is True
    assert generation_data["validation_completed"] is False
    assert generation_data["candidate_package_created"] is False
    assert generation_data["network_request_performed"] is False
    assert generation_data["model_inference_performed"] is False
    assert generation_data["subprocess_invoked"] is False
    assert generation_data["dynamic_code_execution_performed"] is False
    assert generation_data["runtime_trust_granted"] is False
    assert generation_data["execution_authorized"] is False
    assert read_file.json()["data"]["content_verified"] is True
    assert read_file.json()["data"]["quarantined"] is True
    assert project_data["source_digest"] in read_file.json()["data"]["content"]
