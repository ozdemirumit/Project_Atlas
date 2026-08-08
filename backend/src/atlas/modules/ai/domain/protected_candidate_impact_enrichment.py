from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


def _ids(*values: str) -> bool:
    return all(value.strip() and len(value) <= 256 for value in values)


def _digests(*values: str) -> bool:
    return all(
        len(value) == 64 and all(char in "0123456789abcdef" for char in value) for value in values
    )


@dataclass(frozen=True, slots=True)
class ProtectedCandidateImpactPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_candidate_set_schema: str
    required_candidate_state: str
    required_graph_schema: str
    required_graph_snapshot_id: str
    required_report_schema: str
    required_receipt_schema: str
    required_analyzer_id: str
    required_analyzer_attestor_id: str
    start_entity_id: str
    maximum_depth: int
    maximum_candidate_count: int
    maximum_path_count: int
    maximum_entity_count: int
    maximum_service_count: int
    maximum_gap_count: int
    maximum_unknown_count: int
    maximum_output_bytes: int
    retention_minutes: int
    classification_ceiling: str
    browser_binding_key_digest: str
    safety_profile_digest: str
    signed_by: str
    signature_verified: bool
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            self.version != 1
            or not _ids(
                self.policy_id,
                self.schema_version,
                self.organization_id,
                self.environment_id,
                self.policy_version,
                self.required_candidate_set_schema,
                self.required_candidate_state,
                self.required_graph_schema,
                self.required_graph_snapshot_id,
                self.required_report_schema,
                self.required_receipt_schema,
                self.required_analyzer_id,
                self.required_analyzer_attestor_id,
                self.start_entity_id,
                self.classification_ceiling,
                self.signed_by,
            )
            or not 1 <= self.maximum_depth <= 5
            or not 3 <= self.maximum_candidate_count <= 5
            or min(
                self.maximum_path_count,
                self.maximum_entity_count,
                self.maximum_service_count,
                self.maximum_gap_count,
                self.maximum_unknown_count,
                self.maximum_output_bytes,
                self.retention_minutes,
            )
            < 1
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.issued_at < self.expires_at
            or not self.signature_verified
            or not _digests(
                self.browser_binding_key_digest,
                self.safety_profile_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Protected candidate-impact policy is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedCandidateImpactInstruction:
    impact_analysis_id: str
    candidate_set_id: str
    candidate_set_digest: str
    candidate_source_binding_digest: str
    impact_authorization_digest: str
    policy_id: str
    policy_digest: str
    graph_snapshot_id: str
    graph_snapshot_digest: str
    start_entity_id: str
    maximum_depth: int
    maximum_candidate_count: int
    maximum_path_count: int
    maximum_entity_count: int
    maximum_service_count: int
    maximum_gap_count: int
    maximum_unknown_count: int
    maximum_output_bytes: int
    required_report_schema: str
    safety_profile_digest: str
    requested_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ProtectedCandidateImpactPath:
    scope: str
    entity_ids: tuple[str, ...]
    relationship_ids: tuple[str, ...]
    evidence_references: tuple[str, ...]
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            self.scope not in {"direct", "possible"}
            or len(self.entity_ids) != len(self.relationship_ids) + 1
            or not self.evidence_references
            or not _digests(self.canonical_digest)
        ):
            raise ValueError("Protected candidate-impact path is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedCandidateImpactEntry:
    candidate_id: str
    candidate_digest: str
    paths: tuple[ProtectedCandidateImpactPath, ...]
    direct_entity_ids: tuple[str, ...]
    possible_entity_ids: tuple[str, ...]
    technical_service_ids: tuple[str, ...]
    business_service_ids: tuple[str, ...]
    known_gaps: tuple[str, ...]
    unknowns: tuple[str, ...]
    outage_confirmed: bool = False
    interruption_established: bool = False
    duration_established: bool = False
    risk_completed: bool = False
    recovery_completed: bool = False
    canonical_digest: str = ""

    def __post_init__(self) -> None:
        if (
            not _ids(self.candidate_id)
            or not _digests(self.candidate_digest, self.canonical_digest)
            or not self.unknowns
            or any(
                (
                    self.outage_confirmed,
                    self.interruption_established,
                    self.duration_established,
                    self.risk_completed,
                    self.recovery_completed,
                )
            )
        ):
            raise ValueError("Protected candidate-impact entry is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedCandidateImpactReport:
    impact_analysis_id: str
    schema_version: str
    version: int
    candidate_set_id: str
    candidate_set_digest: str
    policy_digest: str
    graph_snapshot_id: str
    graph_snapshot_digest: str
    graph_snapshot_generated_at: datetime
    graph_freshness: str
    graph_completeness: str
    graph_maturity: str
    entries: tuple[ProtectedCandidateImpactEntry, ...]
    modeled_entity_ids: tuple[str, ...]
    technical_service_ids: tuple[str, ...]
    business_service_ids: tuple[str, ...]
    graph_gap_digest: str
    unknown_digest: str
    safety_digest: str
    byte_count: int
    analyzed_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            self.version != 1
            or not _ids(
                self.impact_analysis_id,
                self.schema_version,
                self.candidate_set_id,
                self.graph_snapshot_id,
                self.graph_freshness,
                self.graph_completeness,
                self.graph_maturity,
            )
            or not 3 <= len(self.entries) <= 5
            or len({entry.candidate_id for entry in self.entries}) != len(self.entries)
            or self.byte_count < 1
            or self.graph_snapshot_generated_at.tzinfo is None
            or self.analyzed_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.analyzed_at < self.expires_at
            or not _digests(
                self.candidate_set_digest,
                self.policy_digest,
                self.graph_snapshot_digest,
                self.graph_gap_digest,
                self.unknown_digest,
                self.safety_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Protected candidate-impact report is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedCandidateImpactReceipt:
    impact_analysis_id: str
    schema_version: str
    version: int
    analyzer_id: str
    attested_by: str
    candidate_set_id: str
    candidate_set_digest: str
    impact_authorization_digest: str
    policy_digest: str
    graph_snapshot_id: str
    graph_snapshot_digest: str
    report_digest: str
    coverage_digest: str
    unknown_digest: str
    safety_digest: str
    cleanup_digest: str
    candidate_count: int
    path_count: int
    modeled_entity_count: int
    technical_service_count: int
    business_service_count: int
    gap_count: int
    unknown_count: int
    byte_count: int
    analyzed_at: datetime
    expires_at: datetime
    candidate_source_verified: bool
    graph_snapshot_verified: bool
    bounded_traversal_verified: bool
    complete_candidate_coverage_verified: bool
    unknowns_preserved: bool
    no_outage_claim_verified: bool
    no_preference_assigned: bool
    no_model_used: bool
    cleanup_verified: bool
    signature_verified: bool
    canonical_digest: str


@dataclass(frozen=True, slots=True)
class ProtectedCandidateImpactClaim:
    claim_id: str
    schema_version: str
    version: int
    impact_analysis_id: str
    candidate_set_id: str
    claimed_by_subject_digest: str
    browser_session_binding_digest: str
    request_binding_digest: str
    idempotency_digest: str
    organization_id: str
    environment_id: str
    claimed_at: datetime
    canonical_digest: str


@dataclass(frozen=True, slots=True)
class ProtectedCandidateImpactRecord:
    impact_analysis_id: str
    schema_version: str
    version: int
    claim_id: str
    candidate_set_id: str
    candidate_set_digest: str
    candidate_source_binding_digest: str
    presentation_id: str
    answer_digest: str
    adjudication_id: str
    invocation_id: str
    context_id: str
    organization_id: str
    environment_id: str
    classification: str
    consumer_subject_digest: str
    browser_session_binding_digest: str
    impact_policy_id: str
    impact_policy_digest: str
    impact_policy_version: str
    analyzer_id: str
    analysis_receipt_digest: str
    impact_authorization_digest: str
    protected_report_digest: str
    graph_snapshot_id: str
    graph_snapshot_digest: str
    graph_snapshot_generated_at: datetime
    graph_freshness: str
    graph_completeness: str
    graph_maturity: str
    coverage_digest: str
    graph_gap_digest: str
    unknown_digest: str
    safety_digest: str
    cleanup_digest: str
    candidate_count: int
    path_count: int
    modeled_entity_count: int
    technical_service_count: int
    business_service_count: int
    gap_count: int
    unknown_count: int
    byte_count: int
    analyzed_at: datetime
    expires_at: datetime
    instance_state: str
    purpose: str
    safety_notice: str
    canonical_digest: str
    service_impact_analyzed: bool = True
    impact_complete: bool = False
    outage_confirmed: bool = False
    interruption_established: bool = False
    duration_established: bool = False
    risk_completed: bool = False
    recovery_completed: bool = False
    recommendation_complete: bool = False
    recommendation_presented: bool = False
    recommendation_ready_for_review: bool = False
    recommendation_approved: bool = False
    workflow_created: bool = False
    execution_authorized: bool = False
    deployment_authorized: bool = False
    infrastructure_mutated: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        later = (
            self.impact_complete,
            self.outage_confirmed,
            self.interruption_established,
            self.duration_established,
            self.risk_completed,
            self.recovery_completed,
            self.recommendation_complete,
            self.recommendation_presented,
            self.recommendation_ready_for_review,
            self.recommendation_approved,
            self.workflow_created,
            self.execution_authorized,
            self.deployment_authorized,
            self.infrastructure_mutated,
        )
        if (
            self.version != 1
            or self.instance_state != "protected_candidate_service_impact_analyzed"
            or not self.service_impact_analyzed
            or any(later)
            or not 3 <= self.candidate_count <= 5
            or min(
                self.path_count,
                self.modeled_entity_count,
                self.gap_count,
                self.unknown_count,
                self.byte_count,
            )
            < 1
            or self.technical_service_count < 0
            or self.business_service_count < 0
            or not 20 <= len(self.purpose.strip()) <= 1_000
            or not self.safety_notice.strip()
            or self.graph_snapshot_generated_at.tzinfo is None
            or self.analyzed_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.analyzed_at < self.expires_at
        ):
            raise ValueError("Protected candidate-impact record is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedCandidateImpactManifest:
    impact_analysis_id: str
    candidate_set_id: str
    presentation_id: str
    graph_snapshot_id: str
    graph_snapshot_digest: str
    graph_snapshot_generated_at: datetime
    graph_freshness: str
    graph_completeness: str
    graph_maturity: str
    candidate_count: int
    path_count: int
    modeled_entity_count: int
    technical_service_count: int
    business_service_count: int
    gap_count: int
    unknown_count: int
    coverage_digest: str
    graph_gap_digest: str
    unknown_digest: str
    safety_digest: str
    analyzed_at: datetime
    expires_at: datetime
    safety_notice: str


@dataclass(frozen=True, slots=True)
class ProtectedCandidateImpactResult:
    record: ProtectedCandidateImpactRecord
    manifest: ProtectedCandidateImpactManifest
