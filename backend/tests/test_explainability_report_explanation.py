from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.classification import DataClassification
from atlas.modules.explainability.domain.confidence import ConfidenceExplanation
from atlas.modules.explainability.domain.report_explanation import (
    ExportedLink,
    ExportLinkReauthorization,
    OfflineExportPackage,
    ReportExplainabilityAddendum,
    explain_report,
)
from atlas.modules.guardrails.domain.reasoning_guardrails import ConfidenceLevel
from atlas.modules.reports.domain.models import (
    RedactionState,
    ReportAudience,
    ReportReview,
    ReportSection,
    ReportSourceLineage,
    ReportState,
    ReportType,
    ReviewStatus,
    SectionState,
    TechnicalReport,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
DIGEST = "a" * 64


def section(**overrides: object) -> ReportSection:
    defaults: dict[str, object] = {
        "section_id": "report.section.scope",
        "title": "Scope and source lineage",
        "state": SectionState.COMPLETE,
        "statements": ("Target: target.example.",),
        "evidence_references": (),
        "limitations": (),
    }
    defaults.update(overrides)
    return ReportSection(**defaults)  # type: ignore[arg-type]


def report(**overrides: object) -> TechnicalReport:
    lineage = ReportSourceLineage(
        recommendation_id="recommendation.example",
        recommendation_version=1,
        recommendation_state="published",
        recommendation_created_at=NOW - timedelta(hours=2),
        recommendation_expires_at=NOW + timedelta(hours=2),
        rca_case_id="case.example",
        rca_case_version=1,
        target_id="target.example",
        evidence_ids=("evidence.example",),
        component_versions=("technical-decision-report.v1",),
    )
    defaults: dict[str, object] = {
        "report_id": "report.example",
        "version": 1,
        "prior_version_id": None,
        "owner": "Storage Operations",
        "state": ReportState.READY_FOR_REVIEW,
        "requested_by": "subject.requester",
        "created_at": NOW,
        "expires_at": NOW + timedelta(hours=4),
        "organization_id": "organization.example",
        "environment_id": "environment.production",
        "site_id": "site.example",
        "target_id": "target.example",
        "report_type": ReportType.TECHNICAL_DECISION,
        "audience": ReportAudience.TECHNICAL_OPERATIONS,
        "classification": DataClassification.INTERNAL,
        "redaction_state": RedactionState.COMPLETE,
        "source": lineage,
        "sections": (section(),),
        "review": ReportReview(ReviewStatus.PENDING, None, None, None),
        "itsm_handoff": None,
        "rendered_markdown": "# Report",
        "content_digest": DIGEST,
        "component_versions": ("technical-decision-report.v1",),
        "data_profile": "synthetic_lab",
        "execution_authorized": False,
        "external_mutation_authorized": False,
        "safety_notice": "Decision support only.",
    }
    defaults.update(overrides)
    return TechnicalReport(**defaults)  # type: ignore[arg-type]


def confidence(**overrides: object) -> ConfidenceExplanation:
    defaults: dict[str, object] = {
        "category": ConfidenceLevel.HIGH,
        "category_definition": "High confidence: multiple independent, current signals agree.",
        "supporting_factors": ("Matches a known, resolved fault pattern.",),
        "limiting_factors": (),
        "remaining_alternatives": (),
        "missing_or_conflicting_evidence": (),
        "what_would_change_the_category": "A repeat occurrence after the fix would lower it.",
        "is_confirmed": False,
        "domain_criteria_met": False,
    }
    defaults.update(overrides)
    return ConfidenceExplanation(**defaults)  # type: ignore[arg-type]


def test_explain_report_binds_to_the_exact_report_and_version() -> None:
    addendum = explain_report(
        report(),
        purpose="Summarize the storage remediation decision for the change board.",
        data_freshness_boundary=NOW,
        ai_generated_section_ids=("report.section.scope",),
        excluded_evidence=(),
        access_boundary="Visible to the requesting organization's technical operations role.",
        confidence=confidence(),
        assumptions=(),
        unknowns=(),
    )
    assert addendum.report_id == "report.example"
    assert addendum.report_version == 1
    assert addendum.ai_generated_section_ids == ("report.section.scope",)


def test_explain_report_rejects_a_section_id_not_on_the_report() -> None:
    with pytest.raises(ValueError, match="not on this report"):
        explain_report(
            report(),
            purpose="Summarize the storage remediation decision for the change board.",
            data_freshness_boundary=NOW,
            ai_generated_section_ids=("report.section.does-not-exist",),
            excluded_evidence=(),
            access_boundary="Visible to the requesting organization's technical operations role.",
            confidence=confidence(),
            assumptions=(),
            unknowns=(),
        )


def _addendum(**overrides: object) -> ReportExplainabilityAddendum:
    defaults: dict[str, object] = {
        "report_id": "report.example",
        "report_version": 1,
        "purpose": "Summarize the storage remediation decision for the change board.",
        "data_freshness_boundary": NOW,
        "ai_generated_section_ids": (),
        "excluded_evidence": (),
        "access_boundary": "Visible to the requesting organization's technical operations role.",
        "confidence": confidence(),
        "assumptions": (),
        "unknowns": (),
    }
    defaults.update(overrides)
    return ReportExplainabilityAddendum(**defaults)  # type: ignore[arg-type]


def test_rejects_non_positive_report_version() -> None:
    with pytest.raises(ValueError, match="positive report version"):
        _addendum(report_version=0)


def test_rejects_blank_purpose() -> None:
    with pytest.raises(ValueError, match="purpose"):
        _addendum(purpose="   ")


def test_rejects_blank_access_boundary() -> None:
    with pytest.raises(ValueError, match="access boundary"):
        _addendum(access_boundary="   ")


def test_rejects_naive_data_freshness_boundary() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _addendum(data_freshness_boundary=NOW.replace(tzinfo=None))


def test_data_freshness_boundary_may_be_none() -> None:
    addendum = _addendum(data_freshness_boundary=None)
    assert addendum.data_freshness_boundary is None


def test_exported_link_requires_timezone_aware_expiry() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ExportedLink(
            link_id="export-link.example",
            reauthorization=ExportLinkReauthorization.REAUTHORIZES_ON_ACCESS,
            expires_at=NOW.replace(tzinfo=None),
        )


def test_exported_link_constructs_cleanly() -> None:
    link = ExportedLink(
        link_id="export-link.example",
        reauthorization=ExportLinkReauthorization.STATIC_UNTIL_EXPIRY,
        expires_at=NOW,
    )
    assert link.reauthorization is ExportLinkReauthorization.STATIC_UNTIL_EXPIRY


def _package(**overrides: object) -> OfflineExportPackage:
    defaults: dict[str, object] = {
        "package_id": "offline-export-package.example",
        "classification": DataClassification.CONFIDENTIAL,
        "encryption_algorithm": "AES-256-GCM",
        "checksum_sha256": DIGEST,
        "custody_chain": ("subject.requester exported this package.",),
        "created_at": NOW,
    }
    defaults.update(overrides)
    return OfflineExportPackage(**defaults)  # type: ignore[arg-type]


def test_offline_export_package_requires_an_encryption_algorithm() -> None:
    with pytest.raises(ValueError, match="encryption algorithm"):
        _package(encryption_algorithm="   ")


def test_offline_export_package_requires_a_sha256_checksum() -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        _package(checksum_sha256="not-a-real-checksum")


def test_offline_export_package_requires_custody_metadata() -> None:
    with pytest.raises(ValueError, match="custody metadata"):
        _package(custody_chain=())


def test_offline_export_package_requires_timezone_aware_created_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _package(created_at=NOW.replace(tzinfo=None))


def test_offline_export_package_constructs_cleanly() -> None:
    package = _package()
    assert package.classification is DataClassification.CONFIDENTIAL
