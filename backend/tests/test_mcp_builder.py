from __future__ import annotations

import ast
import asyncio
import json
import tomllib
from dataclasses import replace
from datetime import UTC, date, datetime
from hashlib import sha256
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
from atlas.modules.mcp_builder.adapters.domain_review_memory import (
    InMemoryMcpBuilderDomainReviewRepository,
)
from atlas.modules.mcp_builder.adapters.generation_filesystem import (
    FileSystemMcpBuilderArtifactPublisher,
)
from atlas.modules.mcp_builder.adapters.generation_memory import (
    InMemoryMcpBuilderArtifactPublisher,
    InMemoryMcpBuilderGenerationRepository,
)
from atlas.modules.mcp_builder.adapters.lab_runner_subprocess import (
    SubprocessMcpBuilderLabRunner,
)
from atlas.modules.mcp_builder.adapters.lab_validation_memory import (
    InMemoryMcpBuilderLabValidationRepository,
)
from atlas.modules.mcp_builder.adapters.memory import InMemoryMcpBuilderProjectRepository
from atlas.modules.mcp_builder.adapters.security_review_memory import (
    InMemoryMcpBuilderSecurityReviewRepository,
)
from atlas.modules.mcp_builder.adapters.validation_memory import (
    InMemoryMcpBuilderValidationRepository,
)
from atlas.modules.mcp_builder.application.analyzer import BuilderSourceError, OpenApiSourceAnalyzer
from atlas.modules.mcp_builder.application.generator import (
    BuilderGeneratedContent,
    PythonScaffoldGenerator,
)
from atlas.modules.mcp_builder.application.ports import McpBuilderArtifactError, McpBuilderError
from atlas.modules.mcp_builder.application.service import (
    CANDIDATE_ARCHIVE_CONTRACT_VERSION,
    CANDIDATE_HANDOFF_PROFILE,
    DOMAIN_REVIEW_PROFILE,
    DOMAIN_REVIEWER_CONTRACT_VERSION,
    LAB_RUNNER_CONTRACT_VERSION,
    LAB_VALIDATION_PROFILE,
    SECURITY_REVIEW_PROFILE,
    SECURITY_REVIEWER_CONTRACT_VERSION,
    McpBuilderService,
)
from atlas.modules.mcp_builder.application.validator import (
    VALIDATION_PROFILE,
    VALIDATOR_VERSION,
    PythonScaffoldStaticValidator,
)
from atlas.modules.mcp_builder.domain.design_review import (
    BuilderCapabilityDecision,
    BuilderCapabilityDecisionKind,
    BuilderEntityMapping,
)
from atlas.modules.mcp_builder.domain.domain_review import (
    BuilderDomainCapabilityDecision,
    BuilderDomainCapabilityDecisionKind,
)
from atlas.modules.mcp_builder.domain.lab_validation import BuilderLabCheckCode
from atlas.modules.mcp_builder.domain.models import BuilderProjectState
from atlas.modules.mcp_builder.domain.security_review import (
    BuilderSecurityControl,
    BuilderSecurityControlAssessment,
    BuilderSecurityControlDecisionKind,
)

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
            validation_repository=InMemoryMcpBuilderValidationRepository(),
            domain_review_repository=InMemoryMcpBuilderDomainReviewRepository(),
            security_review_repository=InMemoryMcpBuilderSecurityReviewRepository(),
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


def validation_request(
    project: Any, checkpoint: Any, generation: Any, **overrides: Any
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "actor": actor(),
        "project_id": project.project_id,
        "project_version": project.version,
        "project_digest": project.canonical_digest,
        "source_digest": project.source_digest,
        "checkpoint_id": checkpoint.checkpoint_id,
        "checkpoint_digest": checkpoint.canonical_digest,
        "generation_id": generation.generation_id,
        "generation_digest": generation.canonical_digest,
        "artifact_digest": generation.artifact_digest,
        "validation_profile": VALIDATION_PROFILE,
        "acknowledged_static_only": True,
        "idempotency_key": "mcp-builder-validation-0001",
        "correlation_id": "correlation.mcp-builder-validation",
    }
    values.update(overrides)
    return values


def domain_review_request(
    project: Any,
    checkpoint: Any,
    generation: Any,
    validation: Any,
    *,
    decision_kind: BuilderDomainCapabilityDecisionKind = (
        BuilderDomainCapabilityDecisionKind.ACCEPTED
    ),
    **overrides: Any,
) -> dict[str, Any]:
    candidate_by_id = {item.candidate_id: item for item in project.capability_candidates}
    decisions = tuple(
        BuilderDomainCapabilityDecision(
            candidate_id=item.candidate_id,
            confirmed_class=item.confirmed_class,
            decision=decision_kind,
            supported_product_versions=project.intended_product_versions,
            vendor_permission=item.required_permission,
            authentication_assessment="API key authentication uses an external secret reference.",
            side_effect_assessment="The operation is read-only and has no documented side effect.",
            error_behavior_assessment=(
                "HTTP errors, timeouts, pagination, and rate limits fail closed."
            ),
            health_guidance_assessment=(
                "A successful bounded inventory response is informational health evidence."
            ),
            evidence_citations=(candidate_by_id[item.candidate_id].citation,),
            missing_case_codes=(
                ()
                if decision_kind is BuilderDomainCapabilityDecisionKind.ACCEPTED
                else ("domain.timeout-behavior-missing",)
            ),
            rationale=(
                "Authoritative synthetic API evidence supports the bounded connector behavior."
                if decision_kind is BuilderDomainCapabilityDecisionKind.ACCEPTED
                else "The declared gap prevents domain acceptance."
            ),
        )
        for item in checkpoint.capability_decisions
        if item.generation_eligible
    )
    values: dict[str, Any] = {
        "actor": actor(),
        "project_id": project.project_id,
        "project_version": project.version,
        "project_digest": project.canonical_digest,
        "source_digest": project.source_digest,
        "checkpoint_id": checkpoint.checkpoint_id,
        "checkpoint_digest": checkpoint.canonical_digest,
        "generation_id": generation.generation_id,
        "generation_digest": generation.canonical_digest,
        "artifact_digest": generation.artifact_digest,
        "validation_id": validation.validation_id,
        "validation_digest": validation.canonical_digest,
        "validation_profile": validation.validation_profile,
        "validator_version": validation.validator_version,
        "review_profile": DOMAIN_REVIEW_PROFILE,
        "acknowledged_human_domain_decision": True,
        "capability_decisions": decisions,
        "summary": "Human domain review completed against the exact analyzed source lineage.",
        "idempotency_key": "mcp-builder-domain-review-0001",
        "correlation_id": "correlation.mcp-builder-domain-review",
    }
    values.update(overrides)
    return values


def security_review_request(
    project: Any,
    checkpoint: Any,
    generation: Any,
    validation: Any,
    domain_review: Any,
    *,
    decision_kind: BuilderSecurityControlDecisionKind = (
        BuilderSecurityControlDecisionKind.ACCEPTED
    ),
    **overrides: Any,
) -> dict[str, Any]:
    evidence_reference = project.capability_candidates[0].citation
    assessments = tuple(
        BuilderSecurityControlAssessment(
            control=control,
            decision=decision_kind,
            assessment=(
                f"Independent human assessment confirms the bounded {control.value} posture."
            ),
            evidence_references=(evidence_reference,),
            finding_codes=(
                ()
                if decision_kind is BuilderSecurityControlDecisionKind.ACCEPTED
                else (f"security.{control.value}.finding",)
            ),
            required_controls=(
                f"Preserve the declared {control.value} boundary through later lifecycle gates.",
            ),
        )
        for control in BuilderSecurityControl
    )
    values: dict[str, Any] = {
        "actor": actor(subject_id="subject.security.reviewer"),
        "project_id": project.project_id,
        "project_version": project.version,
        "project_digest": project.canonical_digest,
        "source_digest": project.source_digest,
        "checkpoint_id": checkpoint.checkpoint_id,
        "checkpoint_digest": checkpoint.canonical_digest,
        "generation_id": generation.generation_id,
        "generation_digest": generation.canonical_digest,
        "artifact_digest": generation.artifact_digest,
        "validation_id": validation.validation_id,
        "validation_digest": validation.canonical_digest,
        "validation_profile": validation.validation_profile,
        "validator_version": validation.validator_version,
        "domain_review_id": domain_review.review_id,
        "domain_review_digest": domain_review.canonical_digest,
        "domain_review_profile": domain_review.review_profile,
        "domain_reviewer_contract_version": domain_review.reviewer_contract_version,
        "review_profile": SECURITY_REVIEW_PROFILE,
        "acknowledged_independent_security_decision": True,
        "control_assessments": assessments,
        "summary": "Independent security review completed against exact immutable evidence.",
        "idempotency_key": "mcp-builder-security-review-0001",
        "correlation_id": "correlation.mcp-builder-security-review",
    }
    values.update(overrides)
    return values


def lab_validation_request(
    project: Any,
    checkpoint: Any,
    generation: Any,
    validation: Any,
    domain_review: Any,
    security_review: Any,
    **overrides: Any,
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "actor": actor(subject_id="subject.lab.operator"),
        "project_id": project.project_id,
        "project_version": project.version,
        "project_digest": project.canonical_digest,
        "source_digest": project.source_digest,
        "checkpoint_id": checkpoint.checkpoint_id,
        "checkpoint_digest": checkpoint.canonical_digest,
        "generation_id": generation.generation_id,
        "generation_digest": generation.canonical_digest,
        "artifact_digest": generation.artifact_digest,
        "validation_id": validation.validation_id,
        "validation_digest": validation.canonical_digest,
        "domain_review_id": domain_review.review_id,
        "domain_review_digest": domain_review.canonical_digest,
        "security_review_id": security_review.review_id,
        "security_review_digest": security_review.canonical_digest,
        "lab_profile": LAB_VALIDATION_PROFILE,
        "acknowledged_isolated_synthetic_execution": True,
        "idempotency_key": "mcp-builder-lab-validation-0001",
        "correlation_id": "correlation.mcp-builder-lab-validation",
    }
    values.update(overrides)
    return values


async def accepted_security_chain(builder: McpBuilderService) -> tuple[Any, ...]:
    project = await builder.create_project(**create_request())
    checkpoint = await builder.create_design_checkpoint(**design_request(project))
    generation = await builder.create_generation(**generation_request(project, checkpoint))
    validation = await builder.create_validation(
        **validation_request(project, checkpoint, generation)
    )
    domain_review = await builder.create_domain_review(
        **domain_review_request(project, checkpoint, generation, validation)
    )
    security_review = await builder.create_security_review(
        **security_review_request(project, checkpoint, generation, validation, domain_review)
    )
    return project, checkpoint, generation, validation, domain_review, security_review


def candidate_handoff_request(chain: tuple[Any, ...], lab: Any, **overrides: Any) -> dict[str, Any]:
    project, checkpoint, generation, validation, domain_review, security_review = chain
    values: dict[str, Any] = {
        "actor": actor(subject_id="subject.package.custodian"),
        "project_id": project.project_id,
        "project_version": project.version,
        "project_digest": project.canonical_digest,
        "source_digest": project.source_digest,
        "checkpoint_id": checkpoint.checkpoint_id,
        "checkpoint_digest": checkpoint.canonical_digest,
        "generation_id": generation.generation_id,
        "generation_digest": generation.canonical_digest,
        "artifact_digest": generation.artifact_digest,
        "validation_id": validation.validation_id,
        "validation_digest": validation.canonical_digest,
        "domain_review_id": domain_review.review_id,
        "domain_review_digest": domain_review.canonical_digest,
        "security_review_id": security_review.review_id,
        "security_review_digest": security_review.canonical_digest,
        "lab_validation_id": lab.lab_validation_id,
        "lab_validation_digest": lab.canonical_digest,
        "handoff_profile": CANDIDATE_HANDOFF_PROFILE,
        "acknowledged_unsigned_quarantined_package": True,
        "idempotency_key": "mcp-builder-candidate-handoff-0001",
        "correlation_id": "correlation.mcp-builder-candidate-handoff",
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
        validation_repository=InMemoryMcpBuilderValidationRepository(),
        domain_review_repository=InMemoryMcpBuilderDomainReviewRepository(),
        security_review_repository=InMemoryMcpBuilderSecurityReviewRepository(),
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
        validation_repository=InMemoryMcpBuilderValidationRepository(),
        domain_review_repository=InMemoryMcpBuilderDomainReviewRepository(),
        security_review_repository=InMemoryMcpBuilderSecurityReviewRepository(),
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
        validation_repository=InMemoryMcpBuilderValidationRepository(),
        domain_review_repository=InMemoryMcpBuilderDomainReviewRepository(),
        security_review_repository=InMemoryMcpBuilderSecurityReviewRepository(),
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
        validation_repository=InMemoryMcpBuilderValidationRepository(),
        domain_review_repository=InMemoryMcpBuilderDomainReviewRepository(),
        security_review_repository=InMemoryMcpBuilderSecurityReviewRepository(),
        artifact_publisher=publisher,
        audit_sink=FailingAuditSink(),
        environment_id="environment.test",
        clock=lambda: NOW,
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        await failing_builder.create_generation(**generation_request(project, checkpoint))
    assert await generation_repository.get_by_project(project_id=project.project_id) is None


@pytest.mark.asyncio
async def test_static_validation_passes_replays_and_grants_no_downstream_authority() -> None:
    project_repository = InMemoryMcpBuilderProjectRepository()
    design_repository = InMemoryMcpBuilderDesignCheckpointRepository()
    generation_repository = InMemoryMcpBuilderGenerationRepository()
    validation_repository = InMemoryMcpBuilderValidationRepository()
    publisher = InMemoryMcpBuilderArtifactPublisher()
    sink = CollectingAuditSink()
    builder = McpBuilderService(
        repository=project_repository,
        design_repository=design_repository,
        generation_repository=generation_repository,
        validation_repository=validation_repository,
        domain_review_repository=InMemoryMcpBuilderDomainReviewRepository(),
        security_review_repository=InMemoryMcpBuilderSecurityReviewRepository(),
        artifact_publisher=publisher,
        audit_sink=sink,
        environment_id="environment.test",
        clock=lambda: NOW,
    )
    project = await builder.create_project(**create_request())
    checkpoint = await builder.create_design_checkpoint(**design_request(project))
    generation = await builder.create_generation(**generation_request(project, checkpoint))

    validation = await builder.create_validation(
        **validation_request(project, checkpoint, generation)
    )
    replay = await builder.create_validation(**validation_request(project, checkpoint, generation))
    loaded = await builder.get_validation(
        actor=actor(),
        project_id=project.project_id,
        correlation_id="correlation.mcp-builder-validation-read",
    )

    assert validation.state.value == "passed"
    assert validation.validation_profile == VALIDATION_PROFILE
    assert validation.validator_version == VALIDATOR_VERSION
    assert validation.validation_completed is True
    assert validation.static_validation_passed is True
    assert validation.passed_count == 15
    assert validation.failed_count == 0
    assert validation.skipped_count == 0
    assert len({item.code for item in validation.checks}) == 15
    assert replay == replace(validation, reused=True)
    assert loaded == validation
    for attribute in (
        "runtime_self_test_performed",
        "dependency_resolution_performed",
        "domain_review_completed",
        "security_review_completed",
        "lab_validation_completed",
        "candidate_package_created",
        "connector_registered",
        "connector_installed",
        "connector_enabled",
        "network_request_performed",
        "model_inference_performed",
        "subprocess_invoked",
        "dynamic_code_execution_performed",
        "runtime_trust_granted",
        "execution_authorized",
        "infrastructure_mutation_performed",
    ):
        assert getattr(validation, attribute) is False
    assert sink.records[-1].result_code == "mcp_builder_static_validation_read"


@pytest.mark.asyncio
async def test_static_validation_records_artifact_failure_and_skips_dependents() -> None:
    class FailingReadPublisher(InMemoryMcpBuilderArtifactPublisher):
        fail_reads = False

        async def read(
            self,
            *,
            generation_id: str,
            artifact_digest: str,
            inventory: tuple[Any, ...],
            relative_path: str,
        ) -> str:
            if self.fail_reads:
                raise McpBuilderArtifactError("builder_generation_artifact_integrity_failed")
            return await super().read(
                generation_id=generation_id,
                artifact_digest=artifact_digest,
                inventory=inventory,
                relative_path=relative_path,
            )

    validation_repository = InMemoryMcpBuilderValidationRepository()
    publisher = FailingReadPublisher()
    builder = McpBuilderService(
        repository=InMemoryMcpBuilderProjectRepository(),
        design_repository=InMemoryMcpBuilderDesignCheckpointRepository(),
        generation_repository=InMemoryMcpBuilderGenerationRepository(),
        validation_repository=validation_repository,
        domain_review_repository=InMemoryMcpBuilderDomainReviewRepository(),
        security_review_repository=InMemoryMcpBuilderSecurityReviewRepository(),
        artifact_publisher=publisher,
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        clock=lambda: NOW,
    )
    project = await builder.create_project(**create_request())
    checkpoint = await builder.create_design_checkpoint(**design_request(project))
    generation = await builder.create_generation(**generation_request(project, checkpoint))
    publisher.fail_reads = True

    validation = await builder.create_validation(
        **validation_request(project, checkpoint, generation)
    )

    assert validation.state.value == "failed"
    assert validation.static_validation_passed is False
    assert validation.passed_count == 0
    assert validation.failed_count == 1
    assert validation.skipped_count == 14
    assert validation.checks[0].code == "validation.artifact.integrity"
    assert validation.checks[0].state.value == "failed"
    assert all(item.state.value == "skipped" for item in validation.checks[1:])
    assert await validation_repository.get_by_project(project_id=project.project_id) == validation


@pytest.mark.asyncio
async def test_static_validation_rejects_stale_unsupported_and_unacknowledged_requests() -> None:
    builder, _, _, _ = service()
    project = await builder.create_project(**create_request())
    checkpoint = await builder.create_design_checkpoint(**design_request(project))
    generation = await builder.create_generation(**generation_request(project, checkpoint))

    with pytest.raises(McpBuilderError, match="builder_validation_source_stale"):
        await builder.create_validation(
            **validation_request(project, checkpoint, generation, generation_digest="0" * 64)
        )
    with pytest.raises(McpBuilderError, match="builder_validation_profile_unsupported"):
        await builder.create_validation(
            **validation_request(
                project,
                checkpoint,
                generation,
                validation_profile="atlas.static-validation.rust.v1",
            )
        )
    with pytest.raises(McpBuilderError, match="builder_validation_static_acknowledgement_required"):
        await builder.create_validation(
            **validation_request(project, checkpoint, generation, acknowledged_static_only=False)
        )


@pytest.mark.asyncio
async def test_static_validation_audit_failure_prevents_persistence() -> None:
    class FailingAuditSink(CollectingAuditSink):
        async def record(self, event: Any) -> None:
            raise RuntimeError("audit unavailable")

    project_repository = InMemoryMcpBuilderProjectRepository()
    design_repository = InMemoryMcpBuilderDesignCheckpointRepository()
    generation_repository = InMemoryMcpBuilderGenerationRepository()
    validation_repository = InMemoryMcpBuilderValidationRepository()
    publisher = InMemoryMcpBuilderArtifactPublisher()
    builder = McpBuilderService(
        repository=project_repository,
        design_repository=design_repository,
        generation_repository=generation_repository,
        validation_repository=validation_repository,
        domain_review_repository=InMemoryMcpBuilderDomainReviewRepository(),
        security_review_repository=InMemoryMcpBuilderSecurityReviewRepository(),
        artifact_publisher=publisher,
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        clock=lambda: NOW,
    )
    project = await builder.create_project(**create_request())
    checkpoint = await builder.create_design_checkpoint(**design_request(project))
    generation = await builder.create_generation(**generation_request(project, checkpoint))
    failing_builder = McpBuilderService(
        repository=project_repository,
        design_repository=design_repository,
        generation_repository=generation_repository,
        validation_repository=validation_repository,
        domain_review_repository=InMemoryMcpBuilderDomainReviewRepository(),
        security_review_repository=InMemoryMcpBuilderSecurityReviewRepository(),
        artifact_publisher=publisher,
        audit_sink=FailingAuditSink(),
        environment_id="environment.test",
        clock=lambda: NOW,
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        await failing_builder.create_validation(
            **validation_request(project, checkpoint, generation)
        )
    assert await validation_repository.get_by_project(project_id=project.project_id) is None


@pytest.mark.asyncio
async def test_domain_review_accepts_replays_and_grants_no_downstream_authority() -> None:
    project_repository = InMemoryMcpBuilderProjectRepository()
    design_repository = InMemoryMcpBuilderDesignCheckpointRepository()
    generation_repository = InMemoryMcpBuilderGenerationRepository()
    validation_repository = InMemoryMcpBuilderValidationRepository()
    domain_repository = InMemoryMcpBuilderDomainReviewRepository()
    publisher = InMemoryMcpBuilderArtifactPublisher()
    sink = CollectingAuditSink()
    builder = McpBuilderService(
        repository=project_repository,
        design_repository=design_repository,
        generation_repository=generation_repository,
        validation_repository=validation_repository,
        domain_review_repository=domain_repository,
        security_review_repository=InMemoryMcpBuilderSecurityReviewRepository(),
        artifact_publisher=publisher,
        audit_sink=sink,
        environment_id="environment.test",
        clock=lambda: NOW,
    )
    project = await builder.create_project(**create_request())
    checkpoint = await builder.create_design_checkpoint(**design_request(project))
    generation = await builder.create_generation(**generation_request(project, checkpoint))
    validation = await builder.create_validation(
        **validation_request(project, checkpoint, generation)
    )

    review = await builder.create_domain_review(
        **domain_review_request(project, checkpoint, generation, validation)
    )
    replay = await builder.create_domain_review(
        **domain_review_request(project, checkpoint, generation, validation)
    )
    loaded = await builder.get_domain_review(
        actor=actor(),
        project_id=project.project_id,
        correlation_id="correlation.mcp-builder-domain-review-read",
    )

    assert review.state.value == "accepted"
    assert review.review_profile == DOMAIN_REVIEW_PROFILE
    assert review.reviewer_contract_version == DOMAIN_REVIEWER_CONTRACT_VERSION
    assert review.accepted_count == 1
    assert review.needs_evidence_count == 0
    assert review.rejected_count == 0
    assert review.domain_review_completed is True
    assert review.domain_review_accepted is True
    assert replay == replace(review, reused=True)
    assert loaded == review
    for attribute in (
        "security_review_completed",
        "lab_validation_completed",
        "candidate_package_created",
        "connector_registered",
        "connector_installed",
        "connector_enabled",
        "network_request_performed",
        "model_inference_performed",
        "dependency_resolution_performed",
        "runtime_self_test_performed",
        "subprocess_invoked",
        "dynamic_code_execution_performed",
        "runtime_trust_granted",
        "execution_authorized",
        "infrastructure_mutation_performed",
    ):
        assert getattr(review, attribute) is False
    assert sink.records[-1].result_code == "mcp_builder_domain_review_read"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("decision_kind", "expected_state", "expected_count"),
    [
        (BuilderDomainCapabilityDecisionKind.NEEDS_EVIDENCE, "needs_evidence", 1),
        (BuilderDomainCapabilityDecisionKind.REJECTED, "rejected", 1),
    ],
)
async def test_domain_review_derives_non_accepting_states(
    decision_kind: BuilderDomainCapabilityDecisionKind,
    expected_state: str,
    expected_count: int,
) -> None:
    builder, _, _, _ = service()
    project = await builder.create_project(**create_request())
    checkpoint = await builder.create_design_checkpoint(**design_request(project))
    generation = await builder.create_generation(**generation_request(project, checkpoint))
    validation = await builder.create_validation(
        **validation_request(project, checkpoint, generation)
    )

    review = await builder.create_domain_review(
        **domain_review_request(
            project,
            checkpoint,
            generation,
            validation,
            decision_kind=decision_kind,
        )
    )

    assert review.state.value == expected_state
    assert review.domain_review_accepted is False
    assert getattr(review, f"{expected_state}_count") == expected_count


@pytest.mark.asyncio
async def test_domain_review_rejects_stale_profile_ack_and_semantic_mismatches() -> None:
    builder, _, _, _ = service()
    project = await builder.create_project(**create_request())
    checkpoint = await builder.create_design_checkpoint(**design_request(project))
    generation = await builder.create_generation(**generation_request(project, checkpoint))
    validation = await builder.create_validation(
        **validation_request(project, checkpoint, generation)
    )
    request = domain_review_request(project, checkpoint, generation, validation)
    decision = request["capability_decisions"][0]

    cases = (
        ({"validation_digest": "0" * 64}, "builder_domain_review_source_stale"),
        (
            {"review_profile": "atlas.domain-review.unsupported.v1"},
            "builder_domain_review_profile_unsupported",
        ),
        (
            {"acknowledged_human_domain_decision": False},
            "builder_domain_review_human_acknowledgement_required",
        ),
        (
            {"capability_decisions": (replace(decision, vendor_permission="storage.admin"),)},
            "builder_domain_review_permission_mismatch",
        ),
        (
            {"capability_decisions": (replace(decision, evidence_citations=("source.foreign",)),)},
            "builder_domain_review_evidence_lineage_mismatch",
        ),
        (
            {"capability_decisions": (replace(decision, supported_product_versions=("9.9",)),)},
            "builder_domain_review_product_version_mismatch",
        ),
    )
    for overrides, error_code in cases:
        with pytest.raises(McpBuilderError, match=error_code):
            await builder.create_domain_review(**{**request, **overrides})


@pytest.mark.asyncio
async def test_domain_review_requires_passed_static_validation() -> None:
    class FailingReadPublisher(InMemoryMcpBuilderArtifactPublisher):
        fail_reads = False

        async def read(
            self,
            *,
            generation_id: str,
            artifact_digest: str,
            inventory: tuple[Any, ...],
            relative_path: str,
        ) -> str:
            if self.fail_reads:
                raise McpBuilderArtifactError("builder_generation_artifact_integrity_failed")
            return await super().read(
                generation_id=generation_id,
                artifact_digest=artifact_digest,
                inventory=inventory,
                relative_path=relative_path,
            )

    publisher = FailingReadPublisher()
    builder = McpBuilderService(
        repository=InMemoryMcpBuilderProjectRepository(),
        design_repository=InMemoryMcpBuilderDesignCheckpointRepository(),
        generation_repository=InMemoryMcpBuilderGenerationRepository(),
        validation_repository=InMemoryMcpBuilderValidationRepository(),
        domain_review_repository=InMemoryMcpBuilderDomainReviewRepository(),
        security_review_repository=InMemoryMcpBuilderSecurityReviewRepository(),
        artifact_publisher=publisher,
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        clock=lambda: NOW,
    )
    project = await builder.create_project(**create_request())
    checkpoint = await builder.create_design_checkpoint(**design_request(project))
    generation = await builder.create_generation(**generation_request(project, checkpoint))
    publisher.fail_reads = True
    validation = await builder.create_validation(
        **validation_request(project, checkpoint, generation)
    )

    with pytest.raises(McpBuilderError, match="builder_domain_review_static_validation_required"):
        await builder.create_domain_review(
            **domain_review_request(project, checkpoint, generation, validation)
        )


@pytest.mark.asyncio
async def test_domain_review_audit_failure_prevents_persistence() -> None:
    class FailingAuditSink(CollectingAuditSink):
        async def record(self, event: Any) -> None:
            raise RuntimeError("audit unavailable")

    project_repository = InMemoryMcpBuilderProjectRepository()
    design_repository = InMemoryMcpBuilderDesignCheckpointRepository()
    generation_repository = InMemoryMcpBuilderGenerationRepository()
    validation_repository = InMemoryMcpBuilderValidationRepository()
    domain_repository = InMemoryMcpBuilderDomainReviewRepository()
    publisher = InMemoryMcpBuilderArtifactPublisher()
    builder = McpBuilderService(
        repository=project_repository,
        design_repository=design_repository,
        generation_repository=generation_repository,
        validation_repository=validation_repository,
        domain_review_repository=domain_repository,
        security_review_repository=InMemoryMcpBuilderSecurityReviewRepository(),
        artifact_publisher=publisher,
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        clock=lambda: NOW,
    )
    project = await builder.create_project(**create_request())
    checkpoint = await builder.create_design_checkpoint(**design_request(project))
    generation = await builder.create_generation(**generation_request(project, checkpoint))
    validation = await builder.create_validation(
        **validation_request(project, checkpoint, generation)
    )
    failing_builder = McpBuilderService(
        repository=project_repository,
        design_repository=design_repository,
        generation_repository=generation_repository,
        validation_repository=validation_repository,
        domain_review_repository=domain_repository,
        security_review_repository=InMemoryMcpBuilderSecurityReviewRepository(),
        artifact_publisher=publisher,
        audit_sink=FailingAuditSink(),
        environment_id="environment.test",
        clock=lambda: NOW,
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        await failing_builder.create_domain_review(
            **domain_review_request(project, checkpoint, generation, validation)
        )
    assert await domain_repository.get_by_project(project_id=project.project_id) is None


@pytest.mark.asyncio
async def test_security_review_accepts_replays_and_grants_no_downstream_authority() -> None:
    builder, _, _, sink = service()
    project = await builder.create_project(**create_request())
    checkpoint = await builder.create_design_checkpoint(**design_request(project))
    generation = await builder.create_generation(**generation_request(project, checkpoint))
    validation = await builder.create_validation(
        **validation_request(project, checkpoint, generation)
    )
    domain_review = await builder.create_domain_review(
        **domain_review_request(project, checkpoint, generation, validation)
    )

    review = await builder.create_security_review(
        **security_review_request(project, checkpoint, generation, validation, domain_review)
    )
    replay = await builder.create_security_review(
        **security_review_request(project, checkpoint, generation, validation, domain_review)
    )
    loaded = await builder.get_security_review(
        actor=actor(subject_id="subject.security.reviewer"),
        project_id=project.project_id,
        correlation_id="correlation.mcp-builder-security-review-read",
    )

    assert review.state.value == "accepted"
    assert review.review_profile == SECURITY_REVIEW_PROFILE
    assert review.reviewer_contract_version == SECURITY_REVIEWER_CONTRACT_VERSION
    assert review.domain_review_id == domain_review.review_id
    assert review.domain_reviewed_by == domain_review.reviewed_by
    assert review.reviewed_by != review.domain_reviewed_by
    assert review.accepted_count == 9
    assert review.needs_remediation_count == 0
    assert review.rejected_count == 0
    assert review.security_review_completed is True
    assert review.security_review_accepted is True
    assert replay == replace(review, reused=True)
    assert loaded == review
    for attribute in (
        "lab_validation_completed",
        "candidate_package_created",
        "connector_registered",
        "connector_installed",
        "connector_enabled",
        "network_request_performed",
        "model_inference_performed",
        "dependency_resolution_performed",
        "malware_or_dynamic_scan_performed",
        "runtime_self_test_performed",
        "subprocess_invoked",
        "dynamic_code_execution_performed",
        "runtime_trust_granted",
        "execution_authorized",
        "infrastructure_mutation_performed",
    ):
        assert getattr(review, attribute) is False
    assert sink.records[-1].result_code == "mcp_builder_security_review_read"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("decision_kind", "expected_state", "expected_count"),
    [
        (
            BuilderSecurityControlDecisionKind.NEEDS_REMEDIATION,
            "needs_remediation",
            9,
        ),
        (BuilderSecurityControlDecisionKind.REJECTED, "rejected", 9),
    ],
)
async def test_security_review_derives_non_accepting_states(
    decision_kind: BuilderSecurityControlDecisionKind,
    expected_state: str,
    expected_count: int,
) -> None:
    builder, _, _, _ = service()
    project = await builder.create_project(**create_request())
    checkpoint = await builder.create_design_checkpoint(**design_request(project))
    generation = await builder.create_generation(**generation_request(project, checkpoint))
    validation = await builder.create_validation(
        **validation_request(project, checkpoint, generation)
    )
    domain_review = await builder.create_domain_review(
        **domain_review_request(project, checkpoint, generation, validation)
    )

    review = await builder.create_security_review(
        **security_review_request(
            project,
            checkpoint,
            generation,
            validation,
            domain_review,
            decision_kind=decision_kind,
        )
    )

    assert review.state.value == expected_state
    assert review.security_review_accepted is False
    assert getattr(review, f"{expected_state}_count") == expected_count


@pytest.mark.asyncio
async def test_security_review_rejects_stale_profile_ack_sod_and_evidence_drift() -> None:
    builder, _, _, _ = service()
    project = await builder.create_project(**create_request())
    checkpoint = await builder.create_design_checkpoint(**design_request(project))
    generation = await builder.create_generation(**generation_request(project, checkpoint))
    validation = await builder.create_validation(
        **validation_request(project, checkpoint, generation)
    )
    domain_review = await builder.create_domain_review(
        **domain_review_request(project, checkpoint, generation, validation)
    )
    request = security_review_request(project, checkpoint, generation, validation, domain_review)
    first = request["control_assessments"][0]
    cases = (
        ({"domain_review_digest": "0" * 64}, "builder_security_review_source_stale"),
        (
            {"review_profile": "atlas.security-review.unsupported.v1"},
            "builder_security_review_profile_unsupported",
        ),
        (
            {"acknowledged_independent_security_decision": False},
            "builder_security_review_human_acknowledgement_required",
        ),
        (
            {"actor": actor()},
            "builder_security_review_separation_of_duties_required",
        ),
        (
            {
                "control_assessments": (
                    replace(first, evidence_references=("source.foreign",)),
                    *request["control_assessments"][1:],
                )
            },
            "builder_security_review_evidence_lineage_mismatch",
        ),
        (
            {"control_assessments": request["control_assessments"][:-1]},
            "builder_security_review_control_set_mismatch",
        ),
    )
    for overrides, error_code in cases:
        with pytest.raises(McpBuilderError, match=error_code):
            await builder.create_security_review(**{**request, **overrides})


@pytest.mark.asyncio
async def test_security_review_requires_accepted_domain_review() -> None:
    builder, _, _, _ = service()
    project = await builder.create_project(**create_request())
    checkpoint = await builder.create_design_checkpoint(**design_request(project))
    generation = await builder.create_generation(**generation_request(project, checkpoint))
    validation = await builder.create_validation(
        **validation_request(project, checkpoint, generation)
    )
    domain_review = await builder.create_domain_review(
        **domain_review_request(
            project,
            checkpoint,
            generation,
            validation,
            decision_kind=BuilderDomainCapabilityDecisionKind.NEEDS_EVIDENCE,
        )
    )

    with pytest.raises(
        McpBuilderError, match="builder_security_review_accepted_domain_review_required"
    ):
        await builder.create_security_review(
            **security_review_request(project, checkpoint, generation, validation, domain_review)
        )


@pytest.mark.asyncio
async def test_security_review_audit_failure_prevents_persistence() -> None:
    class FailingAuditSink(CollectingAuditSink):
        async def record(self, event: Any) -> None:
            raise RuntimeError("audit unavailable")

    project_repository = InMemoryMcpBuilderProjectRepository()
    design_repository = InMemoryMcpBuilderDesignCheckpointRepository()
    generation_repository = InMemoryMcpBuilderGenerationRepository()
    validation_repository = InMemoryMcpBuilderValidationRepository()
    domain_repository = InMemoryMcpBuilderDomainReviewRepository()
    security_repository = InMemoryMcpBuilderSecurityReviewRepository()
    publisher = InMemoryMcpBuilderArtifactPublisher()
    builder = McpBuilderService(
        repository=project_repository,
        design_repository=design_repository,
        generation_repository=generation_repository,
        validation_repository=validation_repository,
        domain_review_repository=domain_repository,
        security_review_repository=security_repository,
        artifact_publisher=publisher,
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        clock=lambda: NOW,
    )
    project = await builder.create_project(**create_request())
    checkpoint = await builder.create_design_checkpoint(**design_request(project))
    generation = await builder.create_generation(**generation_request(project, checkpoint))
    validation = await builder.create_validation(
        **validation_request(project, checkpoint, generation)
    )
    domain_review = await builder.create_domain_review(
        **domain_review_request(project, checkpoint, generation, validation)
    )
    failing_builder = McpBuilderService(
        repository=project_repository,
        design_repository=design_repository,
        generation_repository=generation_repository,
        validation_repository=validation_repository,
        domain_review_repository=domain_repository,
        security_review_repository=security_repository,
        artifact_publisher=publisher,
        audit_sink=FailingAuditSink(),
        environment_id="environment.test",
        clock=lambda: NOW,
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        await failing_builder.create_security_review(
            **security_review_request(project, checkpoint, generation, validation, domain_review)
        )
    assert await security_repository.get_by_project(project_id=project.project_id) is None


@pytest.mark.asyncio
async def test_lab_validation_runs_isolated_replays_and_grants_no_runtime_authority() -> None:
    builder, _, _, sink = service()
    (
        project,
        checkpoint,
        generation,
        validation,
        domain_review,
        security_review,
    ) = await accepted_security_chain(builder)
    request = lab_validation_request(
        project, checkpoint, generation, validation, domain_review, security_review
    )

    result = await builder.create_lab_validation(**request)
    replay = await builder.create_lab_validation(**request)
    loaded = await builder.get_lab_validation(
        actor=actor(subject_id="subject.lab.operator"),
        project_id=project.project_id,
        correlation_id="correlation.mcp-builder-lab-validation-read",
    )

    assert result.state.value == "passed", [
        (item.code.value, item.state.value, item.summary) for item in result.checks
    ]
    assert result.lab_profile == LAB_VALIDATION_PROFILE
    assert result.runner_contract_version == LAB_RUNNER_CONTRACT_VERSION
    assert result.passed_count == len(BuilderLabCheckCode) == 8
    assert result.failed_count == result.skipped_count == 0
    assert result.child_started is True
    assert result.child_exit_code == 0
    assert result.workspace_removed is True
    assert result.operated_by not in {result.domain_reviewed_by, result.security_reviewed_by}
    assert replay == replace(result, reused=True)
    assert loaded == result
    assert result.lab_validation_completed is True
    assert result.lab_validation_passed is True
    assert result.synthetic_fixture_used is True
    assert result.runtime_self_test_performed is True
    assert result.subprocess_invoked is True
    assert result.dynamic_code_execution_performed is True
    for attribute in (
        "secret_values_present",
        "target_connected",
        "network_request_performed",
        "dependency_resolution_performed",
        "malware_or_dynamic_scan_performed",
        "candidate_package_created",
        "connector_registered",
        "connector_installed",
        "connector_enabled",
        "runtime_trust_granted",
        "execution_authorized",
        "infrastructure_mutation_performed",
    ):
        assert getattr(result, attribute) is False
    assert sink.records[-1].result_code == "mcp_builder_lab_validation_read"


@pytest.mark.asyncio
async def test_lab_validation_rejects_stale_profile_ack_and_separation_of_duties() -> None:
    builder, _, _, _ = service()
    (
        project,
        checkpoint,
        generation,
        validation,
        domain_review,
        security_review,
    ) = await accepted_security_chain(builder)
    request = lab_validation_request(
        project, checkpoint, generation, validation, domain_review, security_review
    )
    cases = (
        ({"security_review_digest": "0" * 64}, "builder_lab_validation_source_stale"),
        (
            {"lab_profile": "atlas.lab-validation.unsupported.v1"},
            "builder_lab_validation_profile_unsupported",
        ),
        (
            {"acknowledged_isolated_synthetic_execution": False},
            "builder_lab_validation_execution_acknowledgement_required",
        ),
        (
            {"actor": actor(subject_id=domain_review.reviewed_by)},
            "builder_lab_validation_separation_of_duties_required",
        ),
        (
            {"actor": actor(subject_id=security_review.reviewed_by)},
            "builder_lab_validation_separation_of_duties_required",
        ),
    )
    for overrides, error_code in cases:
        with pytest.raises(McpBuilderError, match=error_code):
            await builder.create_lab_validation(**{**request, **overrides})


@pytest.mark.asyncio
async def test_lab_validation_persists_fail_closed_runner_result() -> None:
    lab_repository = InMemoryMcpBuilderLabValidationRepository()
    builder = McpBuilderService(
        repository=InMemoryMcpBuilderProjectRepository(),
        design_repository=InMemoryMcpBuilderDesignCheckpointRepository(),
        generation_repository=InMemoryMcpBuilderGenerationRepository(),
        validation_repository=InMemoryMcpBuilderValidationRepository(),
        domain_review_repository=InMemoryMcpBuilderDomainReviewRepository(),
        security_review_repository=InMemoryMcpBuilderSecurityReviewRepository(),
        lab_validation_repository=lab_repository,
        lab_runner=SubprocessMcpBuilderLabRunner(timeout_seconds=0.000001),
        artifact_publisher=InMemoryMcpBuilderArtifactPublisher(),
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        clock=lambda: NOW,
    )
    (
        project,
        checkpoint,
        generation,
        validation,
        domain_review,
        security_review,
    ) = await accepted_security_chain(builder)

    result = await builder.create_lab_validation(
        **lab_validation_request(
            project, checkpoint, generation, validation, domain_review, security_review
        )
    )
    stored = await lab_repository.get_by_project(project_id=project.project_id)

    assert result.state.value == "failed"
    assert result.lab_validation_passed is False
    assert result.failed_count > 0
    assert result.child_started is True
    assert result.workspace_removed is True
    assert stored == result


@pytest.mark.asyncio
async def test_candidate_handoff_is_deterministic_downloadable_and_grants_no_authority() -> None:
    builder, _, _, sink = service()
    chain = await accepted_security_chain(builder)
    lab = await builder.create_lab_validation(**lab_validation_request(*chain))
    request = candidate_handoff_request(chain, lab)

    result = await builder.create_candidate_handoff(**request)
    replay = await builder.create_candidate_handoff(**request)
    loaded = await builder.get_candidate_handoff(
        actor=actor(subject_id="subject.package.custodian"),
        project_id=chain[0].project_id,
        correlation_id="correlation.candidate.read",
    )
    downloaded, content = await builder.download_candidate_archive(
        actor=actor(subject_id="subject.package.custodian"),
        project_id=chain[0].project_id,
        correlation_id="correlation.candidate.download",
    )

    assert result.state.value == "candidate_quarantined"
    assert result.handoff_profile == CANDIDATE_HANDOFF_PROFILE
    assert result.archive_contract_version == CANDIDATE_ARCHIVE_CONTRACT_VERSION
    assert result.signature_state.value == "unsigned"
    assert result.package_digest == sha256(content).hexdigest()
    assert result.package_size_bytes == len(content)
    assert result.package_entry_count == result.generated_file_count + 1
    assert result.manual_change_count == 0
    assert replay == replace(result, reused=True)
    assert loaded == downloaded == result
    assert result.candidate_package_created is True
    for attribute in (
        "package_signed",
        "publisher_attested",
        "registry_validation_completed",
        "connector_registered",
        "connector_installed",
        "connector_enabled",
        "target_configured",
        "credentials_resolved",
        "runtime_trust_granted",
        "execution_authorized",
        "deployment_approved",
        "infrastructure_mutation_performed",
    ):
        assert getattr(result, attribute) is False
    assert sink.records[-1].result_code == "mcp_builder_candidate_archive_downloaded"


@pytest.mark.asyncio
async def test_static_validator_fails_unsafe_python_and_embedded_secret() -> None:
    builder, _, _, _ = service()
    project = await builder.create_project(**create_request())
    checkpoint = await builder.create_design_checkpoint(**design_request(project))
    generation = await builder.create_generation(**generation_request(project, checkpoint))
    draft = PythonScaffoldGenerator().generate(project=project, checkpoint=checkpoint)
    contents = {item.relative_path: item.content for item in draft.files}
    capability_path = next(
        path
        for path in contents
        if path.startswith("src/atlas_generated_connector/capabilities/capability_")
    )
    contents[capability_path] += '\nimport subprocess\napi_key = "unsafe-secret-value"\n'

    result = PythonScaffoldStaticValidator().validate(
        project=project,
        checkpoint=checkpoint,
        generation=generation,
        contents=contents,
    )
    failed_codes = {item.code for item in result.checks if item.state.value == "failed"}

    assert result.state.value == "failed"
    assert "validation.python.ast-safety" in failed_codes
    assert "validation.security.secret-scan" in failed_codes


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
                "project_id",
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
        generation_data = created_generation.json()["data"]
        validation_payload = {
            "schema_version": "atlas.mcp-builder-validation-request.v1",
            "project_version": project_data["version"],
            "project_digest": project_data["canonical_digest"],
            "source_digest": project_data["source_digest"],
            "checkpoint_id": checkpoint_data["checkpoint_id"],
            "checkpoint_digest": checkpoint_data["canonical_digest"],
            "generation_id": generation_data["generation_id"],
            "generation_digest": generation_data["canonical_digest"],
            "artifact_digest": generation_data["artifact_digest"],
            "validation_profile": VALIDATION_PROFILE,
            "acknowledged_static_only": True,
        }
        denied_validation = client.post(
            f"/api/v1/mcp-builder/projects/{project_id}/validations",
            json=validation_payload,
            headers={"Idempotency-Key": "mcp-builder-validation-api-0001"},
        )
        unsupported_validation = client.post(
            f"/api/v1/mcp-builder/projects/{project_id}/validations",
            json={
                **validation_payload,
                "validation_profile": "atlas.static-validation.rust.v1",
            },
            headers={
                "Idempotency-Key": "mcp-builder-validation-api-unsupported",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        stale_validation = client.post(
            f"/api/v1/mcp-builder/projects/{project_id}/validations",
            json={**validation_payload, "generation_digest": "0" * 64},
            headers={
                "Idempotency-Key": "mcp-builder-validation-api-stale",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        created_validation = client.post(
            f"/api/v1/mcp-builder/projects/{project_id}/validations",
            json=validation_payload,
            headers={
                "Idempotency-Key": "mcp-builder-validation-api-0001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        read_validation = client.get(f"/api/v1/mcp-builder/projects/{project_id}/validation")
        validation_data = created_validation.json()["data"]
        domain_review_payload = {
            "schema_version": "atlas.mcp-builder-domain-review-request.v1",
            "project_version": project_data["version"],
            "project_digest": project_data["canonical_digest"],
            "source_digest": project_data["source_digest"],
            "checkpoint_id": checkpoint_data["checkpoint_id"],
            "checkpoint_digest": checkpoint_data["canonical_digest"],
            "generation_id": generation_data["generation_id"],
            "generation_digest": generation_data["canonical_digest"],
            "artifact_digest": generation_data["artifact_digest"],
            "validation_id": validation_data["validation_id"],
            "validation_digest": validation_data["canonical_digest"],
            "validation_profile": validation_data["validation_profile"],
            "validator_version": validation_data["validator_version"],
            "review_profile": DOMAIN_REVIEW_PROFILE,
            "acknowledged_human_domain_decision": True,
            "capability_decisions": [
                {
                    "candidate_id": candidate["candidate_id"],
                    "confirmed_class": candidate["proposed_capability_class"],
                    "decision": "accepted",
                    "supported_product_versions": project_data["intended_product_versions"],
                    "vendor_permission": "storage.system.read",
                    "authentication_assessment": (
                        "API key authentication uses an external secret reference."
                    ),
                    "side_effect_assessment": (
                        "The operation is read-only and has no documented side effect."
                    ),
                    "error_behavior_assessment": (
                        "HTTP errors, timeouts, pagination, and rate limits fail closed."
                    ),
                    "health_guidance_assessment": (
                        "A bounded inventory response is informational health evidence."
                    ),
                    "evidence_citations": [candidate["citation"]],
                    "missing_case_codes": [],
                    "rationale": (
                        "Authoritative synthetic API evidence supports the bounded behavior."
                    ),
                }
            ],
            "summary": "Human domain review completed against exact source lineage.",
        }
        denied_domain_review = client.post(
            f"/api/v1/mcp-builder/projects/{project_id}/domain-reviews",
            json=domain_review_payload,
            headers={"Idempotency-Key": "mcp-builder-domain-review-api-0001"},
        )
        unsupported_domain_review = client.post(
            f"/api/v1/mcp-builder/projects/{project_id}/domain-reviews",
            json={
                **domain_review_payload,
                "review_profile": "atlas.domain-review.unsupported.v1",
            },
            headers={
                "Idempotency-Key": "mcp-builder-domain-review-api-unsupported",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        stale_domain_review = client.post(
            f"/api/v1/mcp-builder/projects/{project_id}/domain-reviews",
            json={**domain_review_payload, "validation_digest": "0" * 64},
            headers={
                "Idempotency-Key": "mcp-builder-domain-review-api-stale",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        created_domain_review = client.post(
            f"/api/v1/mcp-builder/projects/{project_id}/domain-reviews",
            json=domain_review_payload,
            headers={
                "Idempotency-Key": "mcp-builder-domain-review-api-0001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        read_domain_review = client.get(f"/api/v1/mcp-builder/projects/{project_id}/domain-review")

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
    assert denied_validation.status_code == 403
    assert unsupported_validation.status_code == 422
    assert stale_validation.status_code == 409
    assert created_validation.status_code == 201
    assert read_validation.status_code == 200
    assert denied_domain_review.status_code == 403
    assert unsupported_domain_review.status_code == 422
    assert stale_domain_review.status_code == 409
    assert created_domain_review.status_code == 201
    assert read_domain_review.status_code == 200
    assert created.headers["Cache-Control"] == "no-store"
    assert read.headers["Cache-Control"] == "no-store"
    assert created_design.headers["Cache-Control"] == "no-store"
    assert read_design.headers["Cache-Control"] == "no-store"
    assert created_generation.headers["Cache-Control"] == "no-store"
    assert read_generation.headers["Cache-Control"] == "no-store"
    assert read_file.headers["Cache-Control"] == "no-store"
    assert created_validation.headers["Cache-Control"] == "no-store"
    assert read_validation.headers["Cache-Control"] == "no-store"
    assert created_domain_review.headers["Cache-Control"] == "no-store"
    assert read_domain_review.headers["Cache-Control"] == "no-store"
    assert created.json()["data"]["state"] == "analyzed"
    assert created.json()["data"]["capability_candidates"][0]["proposed_capability_class"] == "C1"
    for forbidden in ("canonical_source_json", "source_document", "request_fingerprint"):
        assert forbidden not in created.text
        assert forbidden not in created_design.text
        assert forbidden not in created_generation.text
    assert created_design.json()["data"]["ready_for_generation_design"] is True
    assert created_design.json()["data"]["generated_artifact_created"] is False
    assert created_design.json()["data"]["execution_authorized"] is False
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
    assert validation_data["state"] == "passed"
    assert validation_data["validation_completed"] is True
    assert validation_data["static_validation_passed"] is True
    assert validation_data["validation_profile"] == VALIDATION_PROFILE
    assert validation_data["validator_version"] == VALIDATOR_VERSION
    assert validation_data["passed_count"] == 15
    assert validation_data["failed_count"] == 0
    assert validation_data["skipped_count"] == 0
    assert len(validation_data["checks"]) == 15
    for field in (
        "runtime_self_test_performed",
        "dependency_resolution_performed",
        "domain_review_completed",
        "security_review_completed",
        "lab_validation_completed",
        "candidate_package_created",
        "connector_registered",
        "connector_installed",
        "connector_enabled",
        "network_request_performed",
        "model_inference_performed",
        "subprocess_invoked",
        "dynamic_code_execution_performed",
        "runtime_trust_granted",
        "execution_authorized",
        "infrastructure_mutation_performed",
    ):
        assert validation_data[field] is False
    domain_review_data = created_domain_review.json()["data"]
    assert domain_review_data["state"] == "accepted"
    assert domain_review_data["review_profile"] == DOMAIN_REVIEW_PROFILE
    assert domain_review_data["reviewer_contract_version"] == DOMAIN_REVIEWER_CONTRACT_VERSION
    assert domain_review_data["domain_review_completed"] is True
    assert domain_review_data["domain_review_accepted"] is True
    assert domain_review_data["accepted_count"] == 1
    assert domain_review_data["needs_evidence_count"] == 0
    assert domain_review_data["rejected_count"] == 0
    assert domain_review_data["capability_decisions"][0]["decision"] == "accepted"
    for field in (
        "security_review_completed",
        "lab_validation_completed",
        "candidate_package_created",
        "connector_registered",
        "connector_installed",
        "connector_enabled",
        "network_request_performed",
        "model_inference_performed",
        "dependency_resolution_performed",
        "runtime_self_test_performed",
        "subprocess_invoked",
        "dynamic_code_execution_performed",
        "runtime_trust_granted",
        "execution_authorized",
        "infrastructure_mutation_performed",
    ):
        assert domain_review_data[field] is False


def test_security_review_api_requires_independent_csrf_scoped_human(tmp_path: Path) -> None:
    sink = CollectingAuditSink()
    builder, _, _, _ = service(sink)

    async def seed_domain_review() -> tuple[Any, Any, Any, Any, Any]:
        project = await builder.create_project(**create_request())
        checkpoint = await builder.create_design_checkpoint(**design_request(project))
        generation = await builder.create_generation(**generation_request(project, checkpoint))
        validation = await builder.create_validation(
            **validation_request(project, checkpoint, generation)
        )
        domain_review = await builder.create_domain_review(
            **domain_review_request(project, checkpoint, generation, validation)
        )
        return project, checkpoint, generation, validation, domain_review

    project, checkpoint, generation, validation, domain_review = asyncio.run(seed_domain_review())
    request = security_review_request(project, checkpoint, generation, validation, domain_review)
    payload = {
        "schema_version": "atlas.mcp-builder-security-review-request.v1",
        **{
            key: value
            for key, value in request.items()
            if key
            not in {
                "actor",
                "project_id",
                "idempotency_key",
                "correlation_id",
                "control_assessments",
            }
        },
        "control_assessments": [
            {
                "control": item.control.value,
                "decision": item.decision.value,
                "assessment": item.assessment,
                "evidence_references": list(item.evidence_references),
                "finding_codes": list(item.finding_codes),
                "required_controls": list(item.required_controls),
            }
            for item in request["control_assessments"]
        ],
    }
    security_reviewer = actor(subject_id="subject.security.reviewer")
    provider = BasicTestIdentityProvider(security_reviewer)
    app_settings = settings(
        development_subject_id=security_reviewer.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    with TestClient(
        create_app(
            app_settings,
            identity_provider=provider,
            audit_sink=sink,
            mcp_builder_service=builder,
        )
    ) as client:
        login_response = login(client)
        endpoint = f"/api/v1/mcp-builder/projects/{project.project_id}/security-reviews"
        denied = client.post(
            endpoint,
            json=payload,
            headers={"Idempotency-Key": "mcp-builder-security-api-0001"},
        )
        unsupported = client.post(
            endpoint,
            json={**payload, "review_profile": "atlas.security-review.unsupported.v1"},
            headers={
                "Idempotency-Key": "mcp-builder-security-api-unsupported",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        stale = client.post(
            endpoint,
            json={**payload, "domain_review_digest": "0" * 64},
            headers={
                "Idempotency-Key": "mcp-builder-security-api-stale",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "mcp-builder-security-api-0001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        read = client.get(f"/api/v1/mcp-builder/projects/{project.project_id}/security-review")

    assert denied.status_code == 403
    assert unsupported.status_code == 422
    assert stale.status_code == 409, stale.text
    assert created.status_code == 201
    assert read.status_code == 200
    assert created.headers["Cache-Control"] == "no-store"
    assert read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["state"] == "accepted"
    assert data["review_profile"] == SECURITY_REVIEW_PROFILE
    assert data["reviewer_contract_version"] == SECURITY_REVIEWER_CONTRACT_VERSION
    assert data["domain_review_id"] == domain_review.review_id
    assert data["domain_reviewed_by"] == domain_review.reviewed_by
    assert data["reviewed_by"] == security_reviewer.subject_id
    assert data["accepted_count"] == 9
    assert len(data["control_assessments"]) == 9
    for field in (
        "lab_validation_completed",
        "candidate_package_created",
        "connector_registered",
        "connector_installed",
        "connector_enabled",
        "network_request_performed",
        "model_inference_performed",
        "dependency_resolution_performed",
        "malware_or_dynamic_scan_performed",
        "runtime_self_test_performed",
        "subprocess_invoked",
        "dynamic_code_execution_performed",
        "runtime_trust_granted",
        "execution_authorized",
        "infrastructure_mutation_performed",
    ):
        assert data[field] is False


def test_lab_validation_api_requires_independent_csrf_scoped_operator(tmp_path: Path) -> None:
    sink = CollectingAuditSink()
    builder, _, _, _ = service(sink)
    chain = asyncio.run(accepted_security_chain(builder))
    project, checkpoint, generation, validation, domain_review, security_review = chain
    request = lab_validation_request(
        project, checkpoint, generation, validation, domain_review, security_review
    )
    payload = {
        "schema_version": "atlas.mcp-builder-lab-validation-request.v1",
        **{
            key: value
            for key, value in request.items()
            if key not in {"actor", "project_id", "idempotency_key", "correlation_id"}
        },
    }
    lab_operator = actor(subject_id="subject.lab.operator")
    provider = BasicTestIdentityProvider(lab_operator)
    app_settings = settings(
        development_subject_id=lab_operator.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    with TestClient(
        create_app(
            app_settings,
            identity_provider=provider,
            audit_sink=sink,
            mcp_builder_service=builder,
        )
    ) as client:
        login_response = login(client)
        endpoint = f"/api/v1/mcp-builder/projects/{project.project_id}/lab-validations"
        denied = client.post(
            endpoint,
            json=payload,
            headers={"Idempotency-Key": "mcp-builder-lab-api-0001"},
        )
        unsupported = client.post(
            endpoint,
            json={**payload, "lab_profile": "atlas.lab-validation.unsupported.v1"},
            headers={
                "Idempotency-Key": "mcp-builder-lab-api-unsupported",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        stale = client.post(
            endpoint,
            json={**payload, "security_review_digest": "0" * 64},
            headers={
                "Idempotency-Key": "mcp-builder-lab-api-stale",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "mcp-builder-lab-api-0001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        read = client.get(f"/api/v1/mcp-builder/projects/{project.project_id}/lab-validation")

    assert denied.status_code == 403
    assert unsupported.status_code == 422
    assert stale.status_code == 409
    assert created.status_code == 201, created.text
    assert read.status_code == 200
    assert created.headers["Cache-Control"] == "no-store"
    assert read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["state"] == "passed"
    assert data["lab_profile"] == LAB_VALIDATION_PROFILE
    assert data["runner_contract_version"] == LAB_RUNNER_CONTRACT_VERSION
    assert data["security_review_id"] == security_review.review_id
    assert data["operated_by"] == lab_operator.subject_id
    assert data["passed_count"] == 8
    assert len(data["checks"]) == 8
    assert data["child_started"] is True
    assert data["child_exit_code"] == 0
    assert data["workspace_removed"] is True
    assert data["lab_validation_completed"] is True
    assert data["lab_validation_passed"] is True
    assert data["runtime_self_test_performed"] is True
    assert data["subprocess_invoked"] is True
    assert data["dynamic_code_execution_performed"] is True
    for field in (
        "secret_values_present",
        "target_connected",
        "network_request_performed",
        "dependency_resolution_performed",
        "malware_or_dynamic_scan_performed",
        "candidate_package_created",
        "connector_registered",
        "connector_installed",
        "connector_enabled",
        "runtime_trust_granted",
        "execution_authorized",
        "infrastructure_mutation_performed",
    ):
        assert data[field] is False
