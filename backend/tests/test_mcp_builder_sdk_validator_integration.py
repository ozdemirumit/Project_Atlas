"""ATLAS-022 SS32's "SDK validator integration" MVP-included item was not real: MCP Builder's
live validator (`PythonScaffoldStaticValidator`, 15 specific checks) and ATLAS-021 MCP Plugin
SDK's `ConnectorValidatorReport` (SS24's nine-category shape) were two independently-built
systems for the same doc requirement -- only Builder's own scheme was ever actually constructed
by live code; the SDK's types had no caller outside their own unit test. Per the user's explicit
decision (pass 21 of the standing audit loop), the two are now unified: Builder's real check
results are projected onto the SDK's report shape and exposed through the real API response,
rather than either system silently diverging from the other. These tests prove that projection is
genuine -- built from the same check outcomes, not a second independent judgment -- and that it
reaches a real API response via `McpBuilderValidationData.from_domain`.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from test_mcp_builder import (
    NOW,
    create_request,
    design_request,
    generation_request,
    validation_request,
)
from test_package_acquisition import CollectingAuditSink

from atlas.api.mcp_builder_schemas import McpBuilderValidationData
from atlas.modules.mcp_builder.adapters.design_review_memory import (
    InMemoryMcpBuilderDesignCheckpointRepository,
)
from atlas.modules.mcp_builder.adapters.domain_review_memory import (
    InMemoryMcpBuilderDomainReviewRepository,
)
from atlas.modules.mcp_builder.adapters.generation_memory import (
    InMemoryMcpBuilderArtifactPublisher,
    InMemoryMcpBuilderGenerationRepository,
)
from atlas.modules.mcp_builder.adapters.memory import InMemoryMcpBuilderProjectRepository
from atlas.modules.mcp_builder.adapters.security_review_memory import (
    InMemoryMcpBuilderSecurityReviewRepository,
)
from atlas.modules.mcp_builder.adapters.validation_memory import (
    InMemoryMcpBuilderValidationRepository,
)
from atlas.modules.mcp_builder.application.service import McpBuilderService
from atlas.modules.mcp_builder.application.validator import build_connector_validator_report
from atlas.modules.mcp_builder.domain.validation import (
    BuilderValidationCheckState,
    McpBuilderValidation,
)
from atlas.modules.mcp_plugin_sdk.domain.validator_package import ValidatorCheckCategory


async def _passing_validation() -> McpBuilderValidation:
    builder = McpBuilderService(
        repository=InMemoryMcpBuilderProjectRepository(),
        design_repository=InMemoryMcpBuilderDesignCheckpointRepository(),
        generation_repository=InMemoryMcpBuilderGenerationRepository(),
        validation_repository=InMemoryMcpBuilderValidationRepository(),
        domain_review_repository=InMemoryMcpBuilderDomainReviewRepository(),
        security_review_repository=InMemoryMcpBuilderSecurityReviewRepository(),
        artifact_publisher=InMemoryMcpBuilderArtifactPublisher(),
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        clock=lambda: NOW,
    )
    project = await builder.create_project(**create_request())
    checkpoint = await builder.create_design_checkpoint(**design_request(project))
    generation = await builder.create_generation(**generation_request(project, checkpoint))
    return await builder.create_validation(**validation_request(project, checkpoint, generation))


@pytest.mark.asyncio
async def test_sdk_validator_report_reflects_a_fully_passing_builder_validation() -> None:
    validation = await _passing_validation()
    report = build_connector_validator_report(
        validation.checks,
        report_id="connector-validator-report.wiring-test",
        package_reference=validation.generation_id,
        validated_at=validation.completed_at,
    )
    assert report.passed is True
    assert report.base_report.passed is True
    assert not report.base_report.findings
    assert {result.category for result in report.category_results} == set(ValidatorCheckCategory)
    assert all(result.passed for result in report.category_results)


@pytest.mark.asyncio
async def test_sdk_validator_report_surfaces_a_failed_builder_check_as_a_real_finding() -> None:
    validation = await _passing_validation()
    # Simulate one real Builder check failing (e.g. a secret slipped into generated output) --
    # the projection must surface it under its real category, not silently drop it.
    tampered_checks = tuple(
        replace(check, state=BuilderValidationCheckState.FAILED)
        if check.code == "validation.security.secret-scan"
        else check
        for check in validation.checks
    )
    report = build_connector_validator_report(
        tampered_checks,
        report_id="connector-validator-report.wiring-test-failed",
        package_reference=validation.generation_id,
        validated_at=validation.completed_at,
    )
    assert report.passed is False
    assert report.base_report.passed is False
    finding_codes = {finding.code for finding in report.base_report.findings}
    assert "validation.security.secret-scan" in finding_codes
    prohibited_category = next(
        result
        for result in report.category_results
        if result.category is ValidatorCheckCategory.PROHIBITED_FILE_AND_SECRET_SCAN
    )
    assert prohibited_category.passed is False
    assert any(
        finding.code == "validation.security.secret-scan"
        for finding in prohibited_category.findings
    )
    # Categories with no failing check in their mapped set stay passed -- the projection is
    # per-category, not an all-or-nothing collapse.
    documentation_category = next(
        result
        for result in report.category_results
        if result.category is ValidatorCheckCategory.DOCUMENTATION_COMPLETENESS
    )
    assert documentation_category.passed is True


@pytest.mark.asyncio
async def test_mcp_builder_validation_api_response_includes_the_sdk_validator_report() -> None:
    validation = await _passing_validation()
    data = McpBuilderValidationData.from_domain(validation)
    assert data.sdk_validator_report.passed is True
    assert len(data.sdk_validator_report.categories) == 9
    assert {item.category for item in data.sdk_validator_report.categories} == {
        category.value for category in ValidatorCheckCategory
    }
