"""ATLAS-046 SS21: reports and exports.

`reports.domain.models.TechnicalReport` already models most of SS21's declared elements --
audience, generation time (`created_at`), source lineage and versions, classification,
redaction state, reviewer status (`ReportReview`), an integrity digest, and expiry -- so this
module adds only what SS21 asks for beyond it, bound to an exact report/version the same way
`ItsmHandoffDraft` already binds to one: purpose, data freshness, which sections are AI-generated,
excluded evidence and an access-boundary statement, and confidence/assumptions/unknowns (reusing
`ConfidenceExplanation`, SS12).

Nothing in this codebase yet models export-link re-authorization or offline export packages
(classification, encryption, checksums, custody metadata) -- SS21's last two requirements --
so `ExportedLink` and `OfflineExportPackage` are new, narrowly-scoped types rather than a
retrofit of unrelated infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.core.classification import DataClassification
from atlas.modules.explainability.domain.confidence import ConfidenceExplanation
from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.reports.domain.models import TechnicalReport


@dataclass(frozen=True, slots=True)
class ReportExplainabilityAddendum:
    """SS21's elements not already covered by `TechnicalReport`, bound to one exact report and
    version."""

    report_id: str
    report_version: int
    purpose: str
    data_freshness_boundary: datetime | None
    ai_generated_section_ids: tuple[str, ...]
    excluded_evidence: tuple[str, ...]
    access_boundary: str
    confidence: ConfidenceExplanation
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.report_version < 1:
            raise ValueError("a report addendum requires a positive report version")
        if not self.purpose.strip():
            raise ValueError("a report addendum requires a purpose")
        if not self.access_boundary.strip():
            raise ValueError("a report addendum requires an access boundary statement")
        if self.data_freshness_boundary is not None and self.data_freshness_boundary.tzinfo is None:
            raise ValueError("data_freshness_boundary must be timezone-aware")


def explain_report(
    report: TechnicalReport,
    *,
    purpose: str,
    data_freshness_boundary: datetime | None,
    ai_generated_section_ids: tuple[str, ...],
    excluded_evidence: tuple[str, ...],
    access_boundary: str,
    confidence: ConfidenceExplanation,
    assumptions: tuple[str, ...],
    unknowns: tuple[str, ...],
) -> ReportExplainabilityAddendum:
    known_section_ids = {section.section_id for section in report.sections}
    unknown_ids = set(ai_generated_section_ids) - known_section_ids
    if unknown_ids:
        raise ValueError(
            "ai_generated_section_ids references sections not on this report:"
            f" {sorted(unknown_ids)}"
        )
    return ReportExplainabilityAddendum(
        report_id=report.report_id,
        report_version=report.version,
        purpose=purpose,
        data_freshness_boundary=data_freshness_boundary,
        ai_generated_section_ids=ai_generated_section_ids,
        excluded_evidence=excluded_evidence,
        access_boundary=access_boundary,
        confidence=confidence,
        assumptions=assumptions,
        unknowns=unknowns,
    )


class ExportLinkReauthorization(StrEnum):
    """SS21: "exported links re-authorize where possible.\""""

    REAUTHORIZES_ON_ACCESS = "reauthorizes_on_access"
    STATIC_UNTIL_EXPIRY = "static_until_expiry"


@dataclass(frozen=True, slots=True)
class ExportedLink:
    link_id: str
    reauthorization: ExportLinkReauthorization
    expires_at: datetime

    def __post_init__(self) -> None:
        validate_stable_identifier(self.link_id, "link_id")
        if self.expires_at.tzinfo is None:
            raise ValueError("an exported link's expires_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class OfflineExportPackage:
    """SS21: "offline packages use classification, encryption, checksums, and custody
    metadata.\""""

    package_id: str
    classification: DataClassification
    encryption_algorithm: str
    checksum_sha256: str
    custody_chain: tuple[str, ...]
    created_at: datetime

    def __post_init__(self) -> None:
        validate_stable_identifier(self.package_id, "package_id")
        if not self.encryption_algorithm.strip():
            raise ValueError("an offline export package requires an encryption algorithm")
        if len(self.checksum_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.checksum_sha256
        ):
            raise ValueError("an offline export package checksum must be SHA-256")
        if not self.custody_chain:
            raise ValueError("an offline export package requires custody metadata")
        if self.created_at.tzinfo is None:
            raise ValueError("an offline export package's created_at must be timezone-aware")
