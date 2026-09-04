from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.connectors.domain.models import ConnectorValidationReport, ValidationFinding
from atlas.modules.mcp_plugin_sdk.domain.validator_package import (
    ConnectorValidatorReport,
    PackageBuildArtifact,
    ValidatorCategoryResult,
    ValidatorCheckCategory,
    build_timestamp_affects_content_identity,
    validation_success_equals_production_approval,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def base_report() -> ConnectorValidationReport:
    return ConnectorValidationReport(
        report_id="validation-report.example",
        package_reference="connector.example.storage:v1.0.0",
        validated_at=NOW,
        findings=(),
    )


def full_category_results() -> tuple[ValidatorCategoryResult, ...]:
    return tuple(
        ValidatorCategoryResult(category=category, passed=True, findings=())
        for category in ValidatorCheckCategory
    )


def test_validator_report_requires_every_category() -> None:
    with pytest.raises(ValueError, match="every validator category"):
        ConnectorValidatorReport(
            base_report=base_report(),
            category_results=(
                ValidatorCategoryResult(
                    category=ValidatorCheckCategory.MANIFEST_AND_SCHEMA_VALIDITY,
                    passed=True,
                    findings=(),
                ),
            ),
        )


def test_validator_report_passed_true_when_all_pass() -> None:
    report = ConnectorValidatorReport(
        base_report=base_report(), category_results=full_category_results()
    )
    assert report.passed is True


def test_validator_report_passed_false_when_base_report_has_findings() -> None:
    failing_base = ConnectorValidationReport(
        report_id="validation-report.example",
        package_reference="connector.example.storage:v1.0.0",
        validated_at=NOW,
        findings=(ValidationFinding(code="missing_health_check", path="manifest", message="x"),),
    )
    report = ConnectorValidatorReport(
        base_report=failing_base, category_results=full_category_results()
    )
    assert report.passed is False


def test_validation_success_never_equals_production_approval() -> None:
    assert validation_success_equals_production_approval() is False


def artifact(**overrides: object) -> PackageBuildArtifact:
    defaults: dict[str, object] = {
        "package_reference": "connector.example.storage:v1.0.0",
        "canonical_manifest_digest": "a" * 64,
        "locked_dependency_digest": "b" * 64,
        "integrity_digest": "c" * 64,
        "signature_reference": None,
        "software_bill_of_materials_reference": None,
        "generated_documentation_reference": "docs.connector.example.storage.v1.0.0",
        "test_report_reference": "test-report.example",
        "validation_report_reference": "validation-report.example",
        "content_identity_digest": "d" * 64,
    }
    defaults.update(overrides)
    return PackageBuildArtifact(**defaults)  # type: ignore[arg-type]


def test_artifact_accepts_valid_state() -> None:
    assert artifact().package_reference == "connector.example.storage:v1.0.0"


def test_artifact_requires_integrity_digest() -> None:
    with pytest.raises(ValueError, match="integrity digest"):
        artifact(integrity_digest="")


def test_build_timestamp_never_affects_content_identity() -> None:
    assert build_timestamp_affects_content_identity() is False
