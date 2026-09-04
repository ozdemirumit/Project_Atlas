"""ATLAS-021 SS24/SS25: the connector validator and package builder.

`ConnectorValidatorReport` wraps `connectors.domain.models.ConnectorValidationReport`/
`ValidationFinding` (already the runtime registry's own validation report shape) directly,
adding SS24's richer nine-category breakdown that the simpler runtime type's flat findings list
does not carry.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.connectors.domain.models import ConnectorValidationReport, ValidationFinding
from atlas.modules.identity.domain.models import validate_stable_identifier


class ValidatorCheckCategory(StrEnum):
    """SS24's nine validator report categories."""

    MANIFEST_AND_SCHEMA_VALIDITY = "manifest_and_schema_validity"
    SDK_AND_ATLAS_COMPATIBILITY = "sdk_and_atlas_compatibility"
    DEPENDENCY_LOCK_AND_VULNERABILITY_STATE = "dependency_lock_and_vulnerability_state"
    PROHIBITED_FILE_AND_SECRET_SCAN = "prohibited_file_and_secret_scan"
    CAPABILITY_RISK_AND_PERMISSION_COMPLETENESS = "capability_risk_and_permission_completeness"
    TEST_COVERAGE_AND_REQUIRED_SCENARIO_RESULTS = "test_coverage_and_required_scenario_results"
    DOCUMENTATION_COMPLETENESS = "documentation_completeness"
    PACKAGE_REPRODUCIBILITY_AND_INTEGRITY = "package_reproducibility_and_integrity"
    RUNTIME_SELF_TEST_AND_RESOURCE_BEHAVIOR = "runtime_self_test_and_resource_behavior"


def validation_success_equals_production_approval() -> bool:
    """SS24: "validation success does not equal production approval.\""""
    return False


@dataclass(frozen=True, slots=True)
class ValidatorCategoryResult:
    category: ValidatorCheckCategory
    passed: bool
    findings: tuple[ValidationFinding, ...]


@dataclass(frozen=True, slots=True)
class ConnectorValidatorReport:
    base_report: ConnectorValidationReport
    category_results: tuple[ValidatorCategoryResult, ...]

    def __post_init__(self) -> None:
        categories = [result.category for result in self.category_results]
        if len(set(categories)) != len(categories):
            raise ValueError("a connector validator report must not repeat a category")
        if set(categories) != set(ValidatorCheckCategory):
            raise ValueError("a connector validator report requires every validator category")

    @property
    def passed(self) -> bool:
        return self.base_report.passed and all(result.passed for result in self.category_results)


def build_timestamp_affects_content_identity() -> bool:
    """SS25: "build timestamps or non-deterministic files should not alter content identity
    unnecessarily.\""""
    return False


@dataclass(frozen=True, slots=True)
class PackageBuildArtifact:
    """SS25's declared elements."""

    package_reference: str
    canonical_manifest_digest: str
    locked_dependency_digest: str
    integrity_digest: str
    signature_reference: str | None
    software_bill_of_materials_reference: str | None
    generated_documentation_reference: str
    test_report_reference: str
    validation_report_reference: str
    content_identity_digest: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.package_reference, "package_reference")
        if not self.canonical_manifest_digest.strip():
            raise ValueError("a package build artifact requires a canonical manifest digest")
        if not self.locked_dependency_digest.strip():
            raise ValueError("a package build artifact requires a locked dependency digest")
        if not self.integrity_digest.strip():
            raise ValueError("a package build artifact requires an integrity digest")
        if not self.generated_documentation_reference.strip():
            raise ValueError("a package build artifact requires generated documentation")
        if not self.test_report_reference.strip():
            raise ValueError("a package build artifact requires a test report reference")
        if not self.validation_report_reference.strip():
            raise ValueError("a package build artifact requires a validation report reference")
        if not self.content_identity_digest.strip():
            raise ValueError("a package build artifact requires a content identity digest")
