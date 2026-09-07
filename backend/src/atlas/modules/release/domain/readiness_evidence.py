"""ATLAS-059 SS16/SS17: readiness criteria and the release evidence package."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.guardrails.domain.input_guardrails import detect_secret_patterns
from atlas.modules.identity.domain.models import validate_stable_identifier


class ReadinessCategory(StrEnum):
    """SS16's six readiness categories."""

    PRODUCT = "product"
    ARCHITECTURE_AND_COMPATIBILITY = "architecture_and_compatibility"
    SECURITY_AND_GOVERNANCE = "security_and_governance"
    QUALITY_AND_AI = "quality_and_ai"
    OPERATIONS = "operations"
    DOCUMENTATION = "documentation"


@dataclass(frozen=True, slots=True)
class ReadinessCriterionResult:
    category: ReadinessCategory
    detail: str
    passed: bool

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("a readiness criterion result requires a detail")


@dataclass(frozen=True, slots=True)
class ReadinessAssessment:
    candidate_reference: str
    results: tuple[ReadinessCriterionResult, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.candidate_reference, "candidate_reference")
        categories_covered = {result.category for result in self.results}
        if categories_covered != set(ReadinessCategory):
            raise ValueError("a readiness assessment requires every readiness category")

    @property
    def is_ready(self) -> bool:
        return all(result.passed for result in self.results)


def false_safe_or_invariant_failure_can_be_accepted_through_aggregate_scoring() -> bool:
    """SS16 (Quality and AI): "no false-safe or invariant failure is accepted through aggregate
    scoring.\""""
    return False


@dataclass(frozen=True, slots=True)
class ReleaseEvidencePackage:
    """SS17's declared elements. "Evidence is immutable, access-controlled, secret-free, and
    retained by policy" -- immutability from the frozen dataclass, `access_control_reference` and
    `retention_policy_reference` as required fields, and `security_findings_and_remediation_state`/
    `test_and_evaluation_results` scanned with Guardrails' `detect_secret_patterns`."""

    package_id: str
    manifest_reference: str
    source_reference: str
    artifact_references: tuple[str, ...]
    digest_references: tuple[str, ...]
    signature_references: tuple[str, ...]
    sbom_reference: str
    provenance_reference: str
    requirement_and_document_versions: tuple[str, ...]
    component_versions: tuple[str, ...]
    test_and_evaluation_results: tuple[str, ...]
    security_findings_and_remediation_state: tuple[str, ...]
    operational_evidence: tuple[str, ...]
    deployment_path_evidence: tuple[str, ...]
    open_defects: tuple[str, ...]
    known_issues: tuple[str, ...]
    exceptions: tuple[str, ...]
    residual_risk_notes: tuple[str, ...]
    reviewer_decisions: tuple[str, ...]
    final_approval_reference: str | None
    access_control_reference: str
    retention_policy_reference: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.package_id, "package_id")
        if not self.manifest_reference.strip():
            raise ValueError("a release evidence package requires a manifest reference")
        if not self.source_reference.strip():
            raise ValueError("a release evidence package requires a source reference")
        if not self.artifact_references:
            raise ValueError("a release evidence package requires artifact references")
        if not self.sbom_reference.strip():
            raise ValueError("a release evidence package requires an SBOM reference")
        if not self.provenance_reference.strip():
            raise ValueError("a release evidence package requires a provenance reference")
        if not self.test_and_evaluation_results:
            raise ValueError("a release evidence package requires test and evaluation results")
        if not self.access_control_reference.strip():
            raise ValueError("SS17: evidence is access-controlled")
        if not self.retention_policy_reference.strip():
            raise ValueError("SS17: evidence is retained by policy")
        for text in (
            *self.test_and_evaluation_results,
            *self.security_findings_and_remediation_state,
        ):
            if detect_secret_patterns(text):
                raise ValueError("SS17: evidence is secret-free")
