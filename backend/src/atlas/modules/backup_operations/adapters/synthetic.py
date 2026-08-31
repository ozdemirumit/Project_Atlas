from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from atlas.modules.backup_operations.domain.models import (
    BackupFinding,
    BackupInvestigation,
    BackupOverview,
    BackupProtectedClient,
    BackupRecoveryPoint,
    BackupReport,
    BackupStoragePolicy,
    EvidenceRecord,
    FindingSeverity,
    FreshnessState,
    InvestigationHypothesis,
    InvestigationState,
)


def _reference(kind: str, content: str) -> str:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"synthetic-commvault://{kind}#sha256:{digest}"


def build_synthetic_backup_overview(
    *, organization_id: str, environment: str, generated_at: datetime | None = None
) -> BackupOverview:
    observed_at = generated_at or datetime.now(UTC)
    client_ref = _reference("client", "client-101=active|client-102=deleted")
    policy_ref = _reference("storagepolicy", "policy-1=copies:2|policy-2=copies:0")
    recovery_point_ref = _reference("recoverypoint", "subclient-1=sample.xml")
    evidence = (
        EvidenceRecord(
            reference=client_ref,
            source="Commvault synthetic client-inventory fixture",
            source_version="11.3x-contract.1",
            observed_at=observed_at,
            freshness=FreshnessState.CURRENT,
            trust_basis="Documentation-derived synthetic inventory fixture",
        ),
        EvidenceRecord(
            reference=policy_ref,
            source="Commvault synthetic storage-policy fixture",
            source_version="11.3x-contract.1",
            observed_at=observed_at,
            freshness=FreshnessState.CURRENT,
            trust_basis="Documentation-derived synthetic policy fixture",
        ),
        EvidenceRecord(
            reference=recovery_point_ref,
            source="Commvault synthetic subclient-browse fixture",
            source_version="11.3x-contract.1",
            observed_at=observed_at,
            freshness=FreshnessState.CURRENT,
            trust_basis="Documentation-derived synthetic browse fixture",
        ),
    )
    recovery_points = (
        BackupRecoveryPoint(
            client_id="101",
            client_name="app-server-01",
            subclient_id="1",
            subclient_name="default",
            name="sample_meta.xml",
            path="\\c:\\test_data\\sample_meta.xml",
            size=2048,
            modification_time=observed_at,
            backup_job_id=4501,
            backup_time=observed_at,
            observed_at=observed_at,
            evidence_references=(recovery_point_ref,),
        ),
    )
    clients = (
        BackupProtectedClient(
            client_id="101",
            client_name="app-server-01",
            host_name="app-server-01.lab.example",
            os_type="Windows",
            is_deleted=False,
            observed_at=observed_at,
            evidence_references=(client_ref,),
        ),
        BackupProtectedClient(
            client_id="102",
            client_name="app-server-02",
            host_name="app-server-02.lab.example",
            os_type="Windows",
            is_deleted=True,
            observed_at=observed_at,
            evidence_references=(client_ref,),
        ),
    )
    policies = (
        BackupStoragePolicy(
            policy_id="1",
            policy_name="Primary-Policy",
            number_of_copies=2,
            number_of_streams=1,
            observed_at=observed_at,
            evidence_references=(policy_ref,),
        ),
        BackupStoragePolicy(
            policy_id="2",
            policy_name="Legacy-Policy",
            number_of_copies=0,
            number_of_streams=1,
            observed_at=observed_at,
            evidence_references=(policy_ref,),
        ),
    )
    findings = (
        BackupFinding(
            finding_id="finding.backup.lab.deleted-client",
            subject_id="client.102",
            severity=FindingSeverity.WARNING,
            component="client:app-server-02",
            summary="Protected client app-server-02 is marked deleted in Commvault.",
            observed_at=observed_at,
            evidence_references=(client_ref,),
        ),
        BackupFinding(
            finding_id="finding.backup.lab.zero-copy-policy",
            subject_id="policy.2",
            severity=FindingSeverity.WARNING,
            component="policy:Legacy-Policy",
            summary="Storage policy Legacy-Policy retains zero copies of backed-up data.",
            observed_at=observed_at,
            evidence_references=(policy_ref,),
        ),
    )
    investigation = BackupInvestigation(
        investigation_id="investigation.backup.lab.001",
        title="Commvault protection coverage review",
        state=InvestigationState.PROVISIONAL,
        summary=(
            "One protected client is marked deleted and one storage policy retains no copies "
            "in synthetic lab evidence. No root cause or data-loss impact is confirmed."
        ),
        hypotheses=(
            InvestigationHypothesis(
                hypothesis_id="hypothesis.backup.lab.stale-registration",
                title="Stale client registration",
                state="possible",
                rationale=(
                    "A deleted client and a zero-copy policy are both consistent with a "
                    "decommissioned or migrated workload rather than an active protection gap."
                ),
                confidence_basis="Single documentation-derived inventory observation",
                evidence_references=(client_ref, policy_ref),
                contradicting_evidence=(
                    "No corroborating job-history or decommission record is loaded.",
                ),
            ),
        ),
        unknowns=(
            "Whether app-server-02 was intentionally decommissioned.",
            "Whether Legacy-Policy is still assigned to any active subclient.",
            "No business-service dependency map is available in this synthetic slice.",
        ),
        next_checks=(
            "Confirm decommission status for app-server-02 with a change record.",
            "Check whether any active subclient still references Legacy-Policy.",
        ),
        evidence_references=(client_ref, policy_ref),
        updated_at=observed_at,
    )
    report = BackupReport(
        report_id="report.backup.lab.001",
        title="Synthetic backup protection assessment",
        generated_at=observed_at,
        executive_summary=(
            "One of two synthetic protected clients is marked deleted, and one of two storage "
            "policies retains no copies. The evidence supports investigation, not a confirmed "
            "coverage gap."
        ),
        confirmed_facts=(
            "Two registered clients are represented in the current snapshot.",
            "app-server-02 is marked deleted; app-server-01 is not.",
            "Legacy-Policy retains zero copies; Primary-Policy retains two.",
        ),
        provisional_findings=(
            "The deleted-client and zero-copy conditions appear isolated based on current "
            "evidence.",
        ),
        unknowns=investigation.unknowns,
        evidence_references=(client_ref, policy_ref),
        safety_notice=(
            "Decision support only. No infrastructure change or service-impacting action "
            "is authorized."
        ),
    )
    return BackupOverview(
        snapshot_id="snapshot.backup.lab.001",
        organization_id=organization_id,
        environment_id=f"environment.{environment}",
        site_id="site.local",
        target_id="target.commvault.commserve.lab",
        data_profile="synthetic_lab",
        generated_at=observed_at,
        clients=clients,
        policies=policies,
        recovery_points=recovery_points,
        findings=findings,
        evidence=evidence,
        investigation=investigation,
        report=report,
    )


class SyntheticBackupOverviewProvider:
    """Serves the fixed synthetic backup overview as a BackupOverviewProvider."""

    def __init__(self, *, organization_id: str, environment: str) -> None:
        self._organization_id = organization_id
        self._environment = environment

    async def get_overview(self, *, requested_at: datetime) -> BackupOverview:
        return build_synthetic_backup_overview(
            organization_id=self._organization_id,
            environment=self._environment,
            generated_at=requested_at,
        )
