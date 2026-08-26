from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from atlas.modules.storage.domain.models import (
    EvidenceRecord,
    FindingSeverity,
    FreshnessState,
    HealthFinding,
    InvestigationHypothesis,
    InvestigationState,
    StorageAsset,
    StorageHealthState,
    StorageInvestigation,
    StorageOverview,
    StorageReport,
)


def _reference(kind: str, content: str) -> str:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"synthetic-hitachi://{kind}#sha256:{digest}"


def build_synthetic_storage_overview(
    *, organization_id: str, environment: str, generated_at: datetime | None = None
) -> StorageOverview:
    observed_at = generated_at or datetime.now(UTC)
    inventory_ref = _reference("inventory", "A34000800556|VSP One B28|800556")
    healthy_ref = _reference("health/836000123456", "CTL1=Normal|CTL2=Normal")
    warning_ref = _reference("health/A34000800556", "CTL01=Warning|CTL02=Normal")
    evidence = (
        EvidenceRecord(
            reference=inventory_ref,
            source="Hitachi Ops Center synthetic fixture",
            source_version="11.0.x-contract.1",
            observed_at=observed_at,
            freshness=FreshnessState.CURRENT,
            trust_basis="Documentation-derived synthetic inventory fixture",
        ),
        EvidenceRecord(
            reference=healthy_ref,
            source="Hitachi Ops Center synthetic fixture",
            source_version="11.0.x-contract.1",
            observed_at=observed_at,
            freshness=FreshnessState.CURRENT,
            trust_basis="Documentation-derived synthetic hardware fixture",
        ),
        EvidenceRecord(
            reference=warning_ref,
            source="Hitachi Ops Center synthetic fixture",
            source_version="11.0.x-contract.1",
            observed_at=observed_at,
            freshness=FreshnessState.CURRENT,
            trust_basis="Documentation-derived synthetic warning fixture",
        ),
    )
    assets = (
        StorageAsset(
            asset_id="asset.storage.lab.g400",
            storage_device_id="836000123456",
            vendor="Hitachi Vantara",
            model="VSP G400",
            serial_number=123456,
            health=StorageHealthState.HEALTHY,
            observed_at=observed_at,
            evidence_references=(inventory_ref, healthy_ref),
        ),
        StorageAsset(
            asset_id="asset.storage.lab.b28",
            storage_device_id="A34000800556",
            vendor="Hitachi Vantara",
            model="VSP One B28",
            serial_number=800556,
            health=StorageHealthState.WARNING,
            observed_at=observed_at,
            evidence_references=(inventory_ref, warning_ref),
        ),
    )
    findings = (
        HealthFinding(
            finding_id="finding.storage.lab.controller-warning",
            asset_id="asset.storage.lab.b28",
            severity=FindingSeverity.WARNING,
            component="CTL01",
            summary="Controller CTL01 reports a vendor warning while its peer reports Normal.",
            observed_at=observed_at,
            evidence_references=(warning_ref,),
        ),
    )
    investigation = StorageInvestigation(
        investigation_id="investigation.storage.lab.001",
        title="VSP One B28 controller warning",
        state=InvestigationState.PROVISIONAL,
        summary=(
            "A localized controller warning is present in synthetic lab evidence. "
            "No root cause or service impact is confirmed."
        ),
        hypotheses=(
            InvestigationHypothesis(
                hypothesis_id="hypothesis.storage.lab.thermal",
                title="Localized controller condition",
                state="possible",
                rationale=(
                    "Only CTL01 reports a warning; peer controller and the second array "
                    "remain healthy."
                ),
                confidence_basis="Single documentation-derived health observation",
                evidence_references=(warning_ref, healthy_ref),
                contradicting_evidence=(
                    "No corroborating facility or event-log evidence is loaded.",
                ),
            ),
        ),
        unknowns=(
            "The warning duration and recurrence are unknown.",
            "No business-service dependency map is available in this synthetic slice.",
            "No approved vendor lab response has been compared with this fixture.",
        ),
        next_checks=(
            "Repeat the approved C1 hardware-health read to confirm persistence.",
            "Review an authorized storage event-log source for the same observation window.",
            "Correlate facility temperature evidence before drawing a thermal conclusion.",
        ),
        evidence_references=(warning_ref, healthy_ref),
        updated_at=observed_at,
    )
    report = StorageReport(
        report_id="report.storage.lab.001",
        title="Synthetic storage health assessment",
        generated_at=observed_at,
        executive_summary=(
            "One of two synthetic Hitachi arrays has a controller warning. "
            "The evidence supports investigation, not a confirmed root cause or outage claim."
        ),
        confirmed_facts=(
            "Two allowlisted storage systems are represented in the current snapshot.",
            "CTL01 on VSP One B28 reports Warning; its peer reports Normal.",
            "The VSP G400 synthetic health observation reports both controllers Normal.",
        ),
        provisional_findings=(
            "The condition appears localized to one controller based on current evidence.",
        ),
        unknowns=investigation.unknowns,
        evidence_references=(inventory_ref, warning_ref, healthy_ref),
        safety_notice=(
            "Decision support only. No infrastructure change or service-impacting action "
            "is authorized."
        ),
    )
    return StorageOverview(
        snapshot_id="snapshot.storage.lab.001",
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        target_id="target.hitachi.opscenter.lab",
        data_profile="synthetic_lab",
        generated_at=observed_at,
        assets=assets,
        findings=findings,
        evidence=evidence,
        investigation=investigation,
        report=report,
    )


class SyntheticStorageOverviewProvider:
    """Serves the fixed synthetic storage overview as a StorageOverviewProvider."""

    def __init__(self, *, organization_id: str, environment: str) -> None:
        self._organization_id = organization_id
        self._environment = environment

    async def get_overview(self, *, requested_at: datetime) -> StorageOverview:
        return build_synthetic_storage_overview(
            organization_id=self._organization_id,
            environment=self._environment,
            generated_at=requested_at,
        )
